import os
import re
from datetime import datetime, timezone

import requests
from flask import Flask, Response, g, redirect, render_template, request, stream_with_context

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
STORAGE_ROUTES = [
    (method, re.compile(f"^{pattern}$"))
    for method, pattern in [
        ("GET", "usage"),
        ("GET", "folders"),
        ("GET", "folder-tree"),
        ("GET", "sections/(photos|videos|music|documents)"),
        ("GET", "search"),
        ("GET", "trash"),
        ("GET", f"uploads/{ID}"),
        ("GET", f"files/{ID}/(content|thumbnail)"),
        ("POST", "folders"),
        ("POST", "uploads"),
        ("POST", f"uploads/{ID}/complete"),
        ("POST", f"trash/{ID}/restore"),
        ("PATCH", f"nodes/{ID}"),
        ("DELETE", f"nodes/{ID}"),
        ("DELETE", f"trash/{ID}"),
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
    sign_in_url = f"{app.config['CLUSTERKEEP_UI_URL'].rstrip('/')}/login"
    if not token:
        return redirect(sign_in_url)

    try:
        response = requests.get(
            f"{app.config['AUTH_API_INTERNAL_URL']}/session",
            cookies={SESSION_COOKIE_NAME: token},
            timeout=3,
        )
    except requests.RequestException:
        return redirect(sign_in_url)

    if response.status_code != 200:
        return redirect(sign_in_url)

    g.is_admin = any(group in ADMIN_GROUPS for group in response.json().get("groups", []))
    return None


@app.get("/")
def index():
    return render_template("index.html", login_url=f"{app.config['CLUSTERKEEP_UI_URL'].rstrip('/')}/login")


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
