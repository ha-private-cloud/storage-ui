import json
import os
import re
from datetime import datetime, timezone

import requests
from flask import Flask, Response, abort, g, redirect, render_template, request, stream_with_context

app = Flask(__name__)

APP_TITLE = os.environ.get("APP_TITLE", "ClusterKeep")
SESSION_COOKIE_NAME = "ck_sso"
ADMIN_GROUPS = ("cluster-admins", "admin")

app.config["AUTH_API_INTERNAL_URL"] = os.environ.get(
    "AUTH_API_INTERNAL_URL", "http://auth-api.auth-dev-pub.svc.cluster.local"
).strip()
app.config["CLUSTERKEEP_UI_URL"] = os.environ.get(
    "CLUSTERKEEP_UI_URL", "https://dev.clusterkeep.dev.net"
).strip()
app.config["ADMIN_UI_URL"] = os.environ.get("ADMIN_UI_URL", "").strip()
app.config["STORAGE_API_URL"] = os.environ.get("STORAGE_API_URL", "").strip()
app.config["STORAGE_API_TOKEN"] = os.environ.get("STORAGE_API_TOKEN", "").strip()

ID = r"[0-9a-f]{32}"
ID_RE = re.compile(f"^{ID}$")
STORAGE_ROUTES = [
    (method, re.compile(f"^{pattern}$"))
    for method, pattern in [
        ("GET", f"uploads/{ID}"),
        ("GET", f"files/{ID}/(content|thumbnail)"),
        ("POST", "uploads"),
        ("POST", f"uploads/{ID}/complete"),
        ("DELETE", f"uploads/{ID}"),
        ("PUT", rf"uploads/{ID}/chunks/\d{{1,6}}"),
    ]
]
FORWARDED_REQUEST_HEADERS = ("Content-Type", "Range")
RETURNED_HEADERS = (
    "Content-Type",
    "Content-Length",
    "Content-Range",
    "Accept-Ranges",
    "Content-Disposition",
    "Content-Security-Policy",
    "Cache-Control",
    "X-Frame-Options",
)

CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "font-src 'self'",
        "img-src 'self'",
        "connect-src 'self'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    ]
)

SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), interest-cohort=()",
}


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html", home_url=app.config["CLUSTERKEEP_UI_URL"]), 404


@app.after_request
def set_security_headers(response):
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


def logout_url():
    return f"{app.config['CLUSTERKEEP_UI_URL'].rstrip('/')}/logout"


@app.context_processor
def inject_globals():
    return {
        "title": APP_TITLE,
        "year": datetime.now(timezone.utc).year,
        "is_admin": getattr(g, "is_admin", False),
        "admin_ui_url": app.config["ADMIN_UI_URL"],
        "logout_url": logout_url(),
    }


@app.before_request
def require_session():
    if request.path == "/healthz" or request.path.startswith("/static/"):
        return None

    token = request.cookies.get(SESSION_COOKIE_NAME)
    if request.path.startswith("/api/"):
        return None if token else ({"detail": "not_signed_in"}, 401)

    def to_sign_in():
        if is_htmx():
            return Response(status=204, headers={"HX-Redirect": sign_in_url()})
        return redirect(sign_in_url())

    if not token:
        return to_sign_in()

    try:
        response = requests.get(
            f"{app.config['AUTH_API_INTERNAL_URL']}/session",
            cookies={SESSION_COOKIE_NAME: token},
            timeout=3,
        )
    except requests.RequestException:
        return to_sign_in()

    if response.status_code != 200:
        return to_sign_in()

    g.is_admin = any(group in ADMIN_GROUPS for group in response.json().get("groups", []))
    return None


SECTIONS = {"photos": "Photos", "videos": "Videos", "music": "Music", "documents": "Documents"}
SECTION_ACCEPT = {
    "photos": "image/*,.heic,.heif,.dng",
    "videos": "video/*,.mkv",
    "music": "audio/*,.flac,.opus",
    "documents": ".pdf,.txt,.md,.rtf,.doc,.docx,.odt,.xls,.xlsx,.ods,.csv,.ppt,.pptx,.odp,.pages,.numbers,.key,.epub,.json,.xml",
}
SECTION_RULES = {
    "photos": "Photos only accepts images.",
    "videos": "Videos only accepts video files.",
    "music": "Music only accepts audio files.",
    "documents": "Documents only accepts documents, such as PDFs, text and Office files.",
}
MESSAGES = {
    "name_taken": "Something with that name is already here.",
    "invalid_name": "That name can't be used.",
    "quota_exceeded": "There isn't enough space left for that.",
    "default_folder": "That folder can't be changed.",
    "cannot_move_into_itself": "A folder can't be moved into itself.",
    "not_found": "That item no longer exists.",
    "storage_unavailable": "Storage is unavailable right now. Try again shortly.",
    "storage_not_configured": "Storage isn't set up here yet.",
}
FALLBACK_MESSAGE = "Something went wrong. Try again."
PREVIEW_KINDS = ("image", "video", "audio", "pdf")


class StorageError(Exception):
    def __init__(self, status: int, data: dict | None = None) -> None:
        super().__init__(status)
        self.status = status
        self.data = data or {}

    @property
    def locked(self) -> bool:
        return self.status in (401, 423)

    @property
    def message(self) -> str:
        detail = self.data.get("detail")
        if detail == "wrong_type":
            return SECTION_RULES.get(self.data.get("section"), FALLBACK_MESSAGE)
        return MESSAGES.get(detail, FALLBACK_MESSAGE)


def storage(method: str, path: str, *, params=None, payload=None):
    base = app.config["STORAGE_API_URL"]
    token = app.config["STORAGE_API_TOKEN"]
    if not (base and token):
        raise StorageError(503, {"detail": "storage_not_configured"})
    try:
        response = requests.request(
            method,
            f"{base.rstrip('/')}/api/v1/{path}",
            params=params,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            cookies={SESSION_COOKIE_NAME: request.cookies.get(SESSION_COOKIE_NAME, "")},
            timeout=(5, 30),
        )
    except requests.RequestException:
        raise StorageError(502, {"detail": "storage_unavailable"}) from None
    data = None
    if response.content:
        try:
            data = response.json()
        except ValueError:
            data = None
    if not response.ok:
        raise StorageError(response.status_code, data if isinstance(data, dict) else None)
    return data


def kind_of(item: dict) -> str:
    if item.get("kind") == "folder":
        return "folder"
    mime = item.get("mime_type") or ""
    if mime == "application/pdf":
        return "pdf"
    for prefix in ("image", "video", "audio"):
        if mime.startswith(f"{prefix}/"):
            return prefix
    return "file"


@app.template_filter("filesize")
def filesize(size) -> str:
    value = float(size or 0)
    units = ["B", "KB", "MB", "GB", "TB"]
    unit = 0
    while value >= 1024 and unit < len(units) - 1:
        value /= 1024
        unit += 1
    return f"{value:.0f} {units[unit]}" if value >= 10 or unit == 0 else f"{value:.1f} {units[unit]}"


@app.template_filter("typelabel")
def typelabel(item: dict) -> str:
    name = item.get("name", "")
    dot = name.rfind(".")
    if 0 < dot < len(name) - 1:
        return name[dot + 1 :].upper()
    kind = kind_of(item)
    return "File" if kind == "file" else kind.upper() if kind == "pdf" else kind.capitalize()


@app.template_filter("shortdate")
def shortdate(value) -> str:
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return ""
    return f"{moment.day} {moment:%b %Y}"


app.jinja_env.filters["kind"] = kind_of


def is_htmx() -> bool:
    return request.headers.get("HX-Request") == "true"


def public_scheme() -> str:
    forwarded = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower()
    return forwarded if forwarded in ("http", "https") else request.scheme


def sign_in_url() -> str:
    return f"{app.config['CLUSTERKEEP_UI_URL'].rstrip('/')}/login"


def usage_summary() -> dict | None:
    try:
        usage = storage("GET", "usage")
    except StorageError:
        return None
    quota = usage.get("quota") or 0
    percent = min(100.0, usage.get("used", 0) / quota * 100) if quota else 0.0
    level = "full" if percent >= 100 else "high" if percent >= 90 else "ok"
    return {"used": usage.get("used", 0), "quota": quota, "percent": round(percent, 1), "level": level}


def render_page(nav: str, **view):
    view.setdefault("items", [])
    view.setdefault("crumbs", None)
    view.setdefault("can_add", False)
    view.setdefault("query", "")
    view.setdefault("folder_id", None)
    view.setdefault("section", None)
    view.setdefault("note", None)
    view.setdefault("empty", "Nothing here yet. Upload files or drop them on this page.")
    view.setdefault("state", "ok")
    context = {
        "nav": nav,
        "view": view,
        "sections": SECTIONS,
        "usage": usage_summary() if view["state"] == "ok" else None,
        "login_url": sign_in_url(),
        "next_url": f"{public_scheme()}://{request.host}/",
        "self_url": request.full_path.rstrip("?"),
    }
    partial = is_htmx() and request.headers.get("HX-Target") == "app" and not request.headers.get("HX-History-Restore-Request")
    return render_template("browser/app.html" if partial else "index.html", **context)


def failed_page(nav: str, title: str, error: StorageError):
    if error.locked:
        return render_page(nav, title=title, state="locked")
    if error.status == 404:
        return render_page(nav, title="Not found", state="missing")
    return render_page(nav, title=title, state="unavailable", message=error.message)


def listing_view(data: dict, *, section: str | None = None) -> dict:
    folder = data["folder"]
    crumbs = None if section else folder.get("path") or []
    back = None
    if crumbs:
        back = f"/folder/{crumbs[-2]['id']}" if len(crumbs) > 1 else "/"
    return {
        "title": folder["name"],
        "crumbs": crumbs,
        "back": back,
        "back_id": crumbs[-2]["id"] if crumbs and len(crumbs) > 1 else "",
        "items": data["items"],
        "can_add": True,
        "folder_id": folder.get("id"),
        "section": section or folder.get("section"),
    }


@app.get("/")
def index():
    try:
        data = storage("GET", "folders")
    except StorageError as error:
        return failed_page("all", "My storage", error)
    return render_page("all", **listing_view(data))


@app.get("/folder/<folder_id>")
def folder(folder_id):
    if not ID_RE.match(folder_id):
        abort(404)
    try:
        data = storage("GET", "folders", params={"parent_id": folder_id})
    except StorageError as error:
        return failed_page("all", "Folder", error)
    return render_page("all", **listing_view(data))


@app.get("/section/<name>")
def section(name):
    if name not in SECTIONS:
        abort(404)
    try:
        data = storage("GET", f"sections/{name}")
    except StorageError as error:
        return failed_page(name, SECTIONS[name], error)
    view = listing_view(data, section=name)
    view["note"] = f"All your {SECTIONS[name].lower()}, from every folder. Uploads here go into the {SECTIONS[name]} folder."
    return render_page(name, **view)


@app.get("/search")
def search():
    query = request.args.get("q", "").strip()[:255]
    if not query:
        return redirect("/")
    try:
        data = storage("GET", "search", params={"q": query})
    except StorageError as error:
        return failed_page("", f"Results for “{query}”", error)
    return render_page("", title=f"Results for “{query}”", items=data["items"], query=query,
                       empty="No files or folders match that name.")


@app.get("/bin")
def bin_view():
    try:
        data = storage("GET", "trash")
    except StorageError as error:
        return failed_page("trash", "Bin", error)
    return render_page("trash", title="Bin", items=data["items"], trash=True, empty="The bin is empty.",
                       note=f"Items in the bin are deleted for good after {data['retention_days']} days.")


def dialog(template: str, **context):
    if not is_htmx():
        abort(404)
    return render_template(f"browser/dialogs/{template}.html", **context)


def item_from_args(node_id: str) -> dict:
    if not ID_RE.match(node_id):
        abort(404)
    return {
        "id": node_id,
        "name": request.args.get("name", "")[:255],
        "kind": "folder" if request.args.get("kind") == "folder" else "file",
        "mime_type": request.args.get("mime", "")[:255],
        "parent_id": request.args.get("parent_id") or None,
    }


def optional_id(value: str | None) -> str | None:
    if not value:
        return None
    if not ID_RE.match(value):
        abort(400)
    return value


@app.get("/dialogs/new-folder")
def new_folder_dialog():
    return dialog("name", title="New folder", label="Folder name", value="", submit="Create folder",
                  action="/folders", parent_id=optional_id(request.args.get("parent_id")))


@app.get("/dialogs/rename/<node_id>")
def rename_dialog(node_id):
    item = item_from_args(node_id)
    return dialog("name", title=f"Rename “{item['name']}”", label="New name", value=item["name"], submit="Rename",
                  action=f"/nodes/{node_id}/rename", select_stem=item["kind"] == "file")


@app.get("/dialogs/move/<node_id>")
def move_dialog(node_id):
    item = item_from_args(node_id)
    try:
        folders = storage("GET", "folder-tree")["items"]
    except StorageError as error:
        return dialog("message", title=f"Move “{item['name']}”", message=error.message)
    own = next((f for f in folders if f["id"] == node_id), None) if item["kind"] == "folder" else None
    choices = [f for f in folders if not own or (f["id"] != own["id"] and not f["path"].startswith(f"{own['path']}/"))]
    return dialog("move", item=item, choices=choices)


@app.get("/dialogs/bin/<node_id>")
def bin_dialog(node_id):
    item = item_from_args(node_id)
    return dialog("confirm", title="Move to bin", submit="Move to bin", danger=False, action=f"/nodes/{node_id}/bin",
                  message=f"Move “{item['name']}” to the bin? You can restore it from the bin for 30 days.")


@app.get("/dialogs/delete/<node_id>")
def delete_dialog(node_id):
    item = item_from_args(node_id)
    return dialog("confirm", title="Delete forever", submit="Delete forever", danger=True, action=f"/bin/{node_id}/delete",
                  message=f"Delete “{item['name']}” for good? This can't be undone.")


@app.get("/dialogs/upload")
def upload_dialog():
    section_name = request.args.get("section")
    return dialog("upload", parent_id=optional_id(request.args.get("parent_id")) or "",
                  accept=SECTION_ACCEPT.get(section_name, ""))


@app.get("/dialogs/preview/<node_id>")
def preview_dialog(node_id):
    item = item_from_args(node_id)
    if kind_of(item) not in PREVIEW_KINDS:
        abort(404)
    return dialog("preview", item=item, kind=kind_of(item))


def changed(message: str, *, refresh_files: bool = True):
    events = {"close-dialog": True, "notify": message}
    if refresh_files:
        events["files-changed"] = True
    return Response(status=204, headers={"HX-Trigger": json.dumps(events)})


def refused(error: StorageError):
    if error.locked:
        return Response(status=204, headers={"HX-Refresh": "true"})
    if request.headers.get("HX-Target") == "dialog-error":
        return render_template("browser/dialogs/error.html", message=error.message), 422
    return Response(status=204, headers={"HX-Trigger": json.dumps({"notify": error.message})})


def act(method: str, path: str, payload, message: str):
    if not is_htmx():
        abort(403)
    try:
        storage(method, path, payload=payload)
    except StorageError as error:
        return refused(error)
    return changed(message)


def node_path(node_id: str) -> str:
    if not ID_RE.match(node_id):
        abort(404)
    return f"nodes/{node_id}"


@app.post("/folders")
def create_folder():
    name = request.form.get("name", "").strip()
    return act("POST", "folders", {"parent_id": optional_id(request.form.get("parent_id")), "name": name}, "Folder created.")


@app.post("/nodes/<node_id>/rename")
def rename_node(node_id):
    return act("PATCH", node_path(node_id), {"name": request.form.get("name", "").strip()}, "Renamed.")


@app.post("/nodes/<node_id>/move")
def move_node(node_id):
    path = node_path(node_id)
    target = request.form.get("section")
    if target is not None:
        if target not in SECTIONS:
            abort(400)
        if not is_htmx():
            abort(403)
        try:
            parent_id = storage("GET", f"sections/{target}")["folder"]["id"]
        except StorageError as error:
            return refused(error)
    else:
        parent_id = optional_id(request.form.get("parent_id"))
    return act("PATCH", path, {"parent_id": parent_id}, "Moved.")


@app.post("/nodes/<node_id>/bin")
def bin_node(node_id):
    return act("DELETE", node_path(node_id), None, "Moved to the bin.")


@app.post("/bin/<node_id>/restore")
def restore_node(node_id):
    if not ID_RE.match(node_id):
        abort(404)
    return act("POST", f"trash/{node_id}/restore", None, "Restored.")


@app.post("/bin/<node_id>/delete")
def delete_node(node_id):
    if not ID_RE.match(node_id):
        abort(404)
    return act("DELETE", f"trash/{node_id}", None, "Deleted.")


@app.route("/api/<path:subpath>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def storage_proxy(subpath):
    if not any(method == request.method and pattern.match(subpath) for method, pattern in STORAGE_ROUTES):
        return {"detail": "not_found"}, 404
    if request.method != "GET" and request.headers.get("X-Requested-With") != "storage-ui":
        return {"detail": "forbidden"}, 403
    base = app.config["STORAGE_API_URL"]
    token = app.config["STORAGE_API_TOKEN"]
    if not (base and token):
        return {"detail": "storage_not_configured"}, 503

    headers = {"Authorization": f"Bearer {token}"}
    headers.update({h: request.headers[h] for h in FORWARDED_REQUEST_HEADERS if h in request.headers})
    try:
        upstream = requests.request(
            request.method,
            f"{base.rstrip('/')}/api/v1/{subpath}",
            params=request.args,
            headers=headers,
            cookies={SESSION_COOKIE_NAME: request.cookies.get(SESSION_COOKIE_NAME, "")},
            data=request.get_data() if request.method in ("POST", "PUT", "PATCH") else None,
            stream=True,
            timeout=(5, 300),
        )
    except requests.RequestException:
        return {"detail": "storage_unavailable"}, 502

    def body():
        try:
            yield from upstream.iter_content(64 * 1024)
        finally:
            upstream.close()

    returned = {h: upstream.headers[h] for h in RETURNED_HEADERS if h in upstream.headers}
    return Response(stream_with_context(body()), status=upstream.status_code, headers=returned)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
