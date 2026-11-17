import re
from pathlib import Path

import pytest
import requests
import responses as responses_lib

from app import app

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = REPO_ROOT / "templates"
STATIC = REPO_ROOT / "static"

AUTH_API_INTERNAL_URL = "http://auth-api.auth-dev-pub.svc.cluster.local"
CLUSTERKEEP_UI_URL = "https://dev.clusterkeep.dev.net"

@pytest.fixture
def client():
    """Authenticated by default -- most tests are about page content, not the auth gate itself."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.set_cookie("ck_sso", "test-session-token")
        with responses_lib.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(responses_lib.GET, f"{AUTH_API_INTERNAL_URL}/session", json={}, status=200)
            yield c

@pytest.fixture
def anonymous_client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

def test_index_renders_title(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"ClusterKeep" in resp.data

def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}

def test_index_renders_banner(client):
    """From base.html, so every page inherits it."""
    body = client.get("/").get_data(as_text=True)
    assert "<header" in body
    assert 'class="brand-mark"' in body

def test_index_links_favicon(client):
    body = client.get("/").get_data(as_text=True)
    assert 'type="image/svg+xml"' in body
    assert "images/favicon.svg" in body

def test_favicon_is_served(client):
    resp = client.get("/static/images/favicon.svg")
    assert resp.status_code == 200
    assert "svg" in resp.headers["Content-Type"]

def test_security_headers_on_every_response(client):
    """after_request, so static files carry them too."""
    for path in ["/", "/healthz", "/static/css/style.css"]:
        headers = client.get(path).headers
        assert headers["X-Content-Type-Options"] == "nosniff", path
        assert headers["X-Frame-Options"] == "DENY", path
        assert headers["Referrer-Policy"] == "no-referrer", path
        assert "Content-Security-Policy" in headers, path

def test_content_security_policy_stays_strict(client):
    """Relaxing any of these is a real change in exposure - do it knowingly."""
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "default-src 'self'" in csp

def test_no_inline_scripts_or_handlers():
    """CSP blocks these at runtime; catch them at author time instead."""
    for template in TEMPLATES.rglob("*.html"):
        markup = template.read_text()
        assert not re.search(r"<script(?![^>]*\bsrc=)", markup), (
            f"{template.name} has an inline <script>; CSP blocks it - put the "
            "code in static/js/ and load it with src="
        )
        assert not re.search(r"\son[a-z]+\s*=\s*[\"']", markup), (
            f"{template.name} has an inline event handler; CSP blocks it"
        )

def test_logo_and_favicon_geometry_match():
    """Nothing else would catch the two copies of the mark drifting apart."""
    inline = (TEMPLATES / "partials" / "logo.html").read_text()
    favicon = (STATIC / "images" / "favicon.svg").read_text()
    assert re.findall(r'd="([^"]+)"', inline) == re.findall(r'd="([^"]+)"', favicon)

def test_mark_is_built_on_the_cell_grid():
    """Integer coordinates are what make the mark exact at 16px."""
    inline = (TEMPLATES / "partials" / "logo.html").read_text()
    assert 'viewBox="0 0 16 16"' in inline
    assert 'shape-rendering="crispEdges"' in inline
    (data,) = re.findall(r'd="([^"]+)"', inline)
    for number in re.findall(r"-?\d+(?:\.\d+)?", data):
        assert "." not in number, f"non-integer coordinate {number!r} in the mark"

def test_mark_path_is_not_duplicated_into_pages():
    """A third copy would escape the drift guard, which only checks two."""
    for template in TEMPLATES.rglob("*.html"):
        if template.name == "logo.html":
            continue
        assert 'fill-rule="evenodd"' not in template.read_text(), (
            f"{template.name} appears to inline the mark; include the partial instead"
        )

FETCHING_TAGS = r"link|script|img|iframe|source|video|audio|embed|object|track"

def test_templates_request_no_third_party_assets():
    tags = re.compile(rf"<(?:{FETCHING_TAGS})\b[^>]*>", re.I | re.S)
    urls = re.compile(r'(?:href|src)\s*=\s*"(https?://[^"]+)"', re.I)
    for template in TEMPLATES.rglob("*.html"):
        for tag in tags.findall(template.read_text()):
            for url in urls.findall(tag):
                assert False, f"{template.name} loads a remote asset: {url}"

def test_fonts_are_self_hosted():
    """@font-face sources must be local and must actually exist."""
    css = (STATIC / "css" / "style.css").read_text()
    sources = re.findall(r'src:\s*url\("([^"]+)"\)', css)
    assert sources, "no @font-face rules found in the built stylesheet"
    for src in sources:
        assert not src.startswith("http"), f"remote font source: {src}"
        resolved = (STATIC / "css" / src).resolve()
        assert resolved.is_file(), f"missing font file: {resolved}"

def test_stylesheet_is_built_from_current_source():
    """Marker classes the templates rely on must be in the build."""
    css = (STATIC / "css" / "style.css").read_text()
    for marker in [".mark-lg .brand-mark", "Cinzel", "Inter"]:
        assert marker in css, f"{marker!r} missing - run `npm run build:css`"

LOCAL_CLASSES = {"brand-mark", "mark-lg", "group", "antialiased", "nav-link"}

def tailwind_selector(cls):
    """Keeps the variant prefix (`hover:bg-x` -> `.hover\\:bg-x:hover`) - do not strip it."""
    return "." + re.sub(r"([^A-Za-z0-9_-])", r"\\\1", cls)

JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)
CLASS_TOKEN = re.compile(r"[a-z!-][a-z0-9:/\[\]().%_-]*")


def class_lists_in_jinja(markup):
    """Class strings held in Jinja set constants and expressions, which class=\"...\" alone misses."""
    for block in re.findall(r"\{%-?\s*set [^\n%]*%\}|\{\{.*?\}\}", markup):
        for value in re.findall(r'"([^"]*)"|\'([^\']*)\'', block):
            tokens = (value[0] or value[1]).split()
            if any(re.search(r"\.(js|css|png|svg|woff2)$", t) for t in tokens):
                continue
            if tokens and all(CLASS_TOKEN.fullmatch(t) for t in tokens) and any("-" in t for t in tokens):
                yield " ".join(tokens)


def tailwind_classes_used():
    used = set()
    for template in TEMPLATES.rglob("*.html"):
        markup = template.read_text()
        values = [JINJA.sub(" ", v) for v in re.findall(r'class="([^"]*)"', markup)]
        values += class_lists_in_jinja(markup)
        for value in values:
            used.update(c for c in value.split() if c not in LOCAL_CLASSES)
    return used

def test_every_utility_used_by_a_template_is_in_the_build():
    """style.css is committed and CI never rebuilds it, so it can silently go stale after a template edit."""
    css = (STATIC / "css" / "style.css").read_text()
    missing = sorted(
        cls for cls in tailwind_classes_used() if tailwind_selector(cls) not in css
    )
    assert not missing, (
        f"utilities used in templates but absent from style.css: {missing}\n"
        "run `npm run build:css` and commit the result"
    )

def test_no_session_cookie_redirects_to_sign_in(anonymous_client):
    response = anonymous_client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"] == f"{CLUSTERKEEP_UI_URL}/login"

def test_invalid_session_redirects_to_sign_in(anonymous_client):
    anonymous_client.set_cookie("ck_sso", "not-a-real-session")
    with responses_lib.RequestsMock() as rsps:
        rsps.add(responses_lib.GET, f"{AUTH_API_INTERNAL_URL}/session", status=401)
        response = anonymous_client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"] == f"{CLUSTERKEEP_UI_URL}/login"

def test_auth_api_unreachable_fails_closed(anonymous_client):
    """A network blip must not accidentally let anyone in."""
    anonymous_client.set_cookie("ck_sso", "some-token")
    with responses_lib.RequestsMock() as rsps:
        rsps.add(
            responses_lib.GET,
            f"{AUTH_API_INTERNAL_URL}/session",
            body=requests.exceptions.ConnectionError("unreachable"),
        )
        response = anonymous_client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"] == f"{CLUSTERKEEP_UI_URL}/login"

def test_healthz_is_reachable_without_a_session(anonymous_client):
    assert anonymous_client.get("/healthz").status_code == 200

def test_valid_session_reaches_the_page(client):
    assert client.get("/").status_code == 200

def test_admin_group_shows_the_admin_link(anonymous_client, monkeypatch):
    monkeypatch.setitem(app.config, "ADMIN_UI_URL", "http://localhost:9083")
    anonymous_client.set_cookie("ck_sso", "admin-token")
    with responses_lib.RequestsMock() as rsps:
        rsps.add(responses_lib.GET, f"{AUTH_API_INTERNAL_URL}/session", json={"groups": ["admin"]}, status=200)
        body = anonymous_client.get("/").get_data(as_text=True)
    assert "http://localhost:9083" in body

def test_sign_out_link_points_to_clusterkeep_ui_logout(client):
    body = client.get("/").get_data(as_text=True)
    assert 'href="https://dev.clusterkeep.dev.net/logout"' in body

def test_regular_user_does_not_see_the_admin_link(anonymous_client, monkeypatch):
    monkeypatch.setitem(app.config, "ADMIN_UI_URL", "http://localhost:9083")
    anonymous_client.set_cookie("ck_sso", "regular-token")
    with responses_lib.RequestsMock() as rsps:
        rsps.add(responses_lib.GET, f"{AUTH_API_INTERNAL_URL}/session", json={"groups": []}, status=200)
        body = anonymous_client.get("/").get_data(as_text=True)
    assert "http://localhost:9083" not in body


def test_unknown_path_shows_the_not_found_page(client):
    resp = client.get("/does-not-exist")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 404
    assert "Page not found" in body
    assert "Back to ClusterKeep" in body
    assert f'href="{CLUSTERKEEP_UI_URL}"' in body
    assert "Sign out" not in body


STORAGE_URL = "http://storage-api.storage-dev-priv.svc.cluster.local"
NODE = "0123456789abcdef0123456789abcdef"
CHANGE = {"X-Requested-With": "storage-ui"}


@pytest.fixture
def storage_client(anonymous_client, monkeypatch):
    monkeypatch.setitem(app.config, "STORAGE_API_URL", STORAGE_URL)
    monkeypatch.setitem(app.config, "STORAGE_API_TOKEN", "test-storage-token")
    anonymous_client.set_cookie("ck_sso", "test-session-token")
    return anonymous_client


def forwarded(extra=None):
    headers = {"Authorization": "Bearer test-storage-token", "Cookie": "ck_sso=test-session-token"}
    return [responses_lib.matchers.header_matcher({**headers, **(extra or {})})]


def test_locked_storage_links_back_to_sign_in(storage_client):
    with responses_lib.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses_lib.GET, f"{AUTH_API_INTERNAL_URL}/session", json={}, status=200)
        rsps.add(responses_lib.GET, f"{STORAGE_URL}/api/v1/folders", json={"detail": "locked"}, status=423)
        body = storage_client.get("/").get_data(as_text=True)
    assert "Your storage is locked" in body
    assert 'href="https://dev.clusterkeep.dev.net/login?next=' in body


def test_api_calls_are_passed_to_storage_api_with_the_service_token_and_session(storage_client):
    with responses_lib.RequestsMock() as rsps:
        rsps.add(responses_lib.GET, f"{STORAGE_URL}/api/v1/uploads/{NODE}", json={"received": [0]}, match=forwarded())
        response = storage_client.get(f"/api/uploads/{NODE}")
    assert response.status_code == 200
    assert response.get_json() == {"received": [0]}


def test_query_strings_are_passed_through(storage_client):
    with responses_lib.RequestsMock() as rsps:
        rsps.add(responses_lib.GET, f"{STORAGE_URL}/api/v1/files/{NODE}/content", body=b"x",
                 match=[responses_lib.matchers.query_param_matcher({"download": "1"})])
        assert storage_client.get(f"/api/files/{NODE}/content?download=1").status_code == 200


@pytest.mark.parametrize("path", ["/api/vault/unlock", "/api/vault/recover", "/api/docs", f"/api/nodes/{NODE}/../x",
                                  "/api/folders", "/api/search", "/api/trash", "/api/usage", f"/api/nodes/{NODE}"])
def test_only_listed_storage_routes_are_reachable(storage_client, path):
    with responses_lib.RequestsMock():
        assert storage_client.post(path, headers=CHANGE).status_code == 404
        assert storage_client.get(path).status_code == 404


def test_changes_need_the_same_site_header(storage_client):
    with responses_lib.RequestsMock():
        response = storage_client.delete(f"/api/uploads/{NODE}")
    assert response.status_code == 403


def test_upload_chunks_are_forwarded_byte_for_byte(storage_client):
    with responses_lib.RequestsMock() as rsps:
        rsps.add(responses_lib.PUT, f"{STORAGE_URL}/api/v1/uploads/{NODE}/chunks/3", status=204, match=forwarded())
        response = storage_client.put(f"/api/uploads/{NODE}/chunks/3", data=b"\x00\x01binary", headers=CHANGE)
        sent = rsps.calls[0].request.body
    assert response.status_code == 204
    assert sent == b"\x00\x01binary"


def test_file_ranges_and_headers_come_back_for_seeking(storage_client):
    upstream_headers = {"Content-Range": "bytes 0-3/10", "Accept-Ranges": "bytes",
                        "Content-Disposition": "inline; filename*=UTF-8''clip.mp4",
                        "Content-Security-Policy": "sandbox; default-src 'none'"}
    with responses_lib.RequestsMock() as rsps:
        rsps.add(responses_lib.GET, f"{STORAGE_URL}/api/v1/files/{NODE}/content", status=206, body=b"abcd",
                 content_type="video/mp4", headers=upstream_headers, match=forwarded({"Range": "bytes=0-3"}))
        response = storage_client.get(f"/api/files/{NODE}/content", headers={"Range": "bytes=0-3"})
    assert response.status_code == 206
    assert response.data == b"abcd"
    assert response.headers["Content-Range"] == "bytes 0-3/10"
    assert response.headers["Content-Type"] == "video/mp4"
    assert response.headers["Content-Security-Policy"] == "sandbox; default-src 'none'"


def test_pdfs_can_be_framed_by_this_site_but_other_files_cannot(storage_client):
    with responses_lib.RequestsMock() as rsps:
        rsps.add(responses_lib.GET, f"{STORAGE_URL}/api/v1/files/{NODE}/content", body=b"%PDF",
                 content_type="application/pdf",
                 headers={"Content-Security-Policy": "frame-ancestors 'self'", "X-Frame-Options": "SAMEORIGIN"})
        rsps.add(responses_lib.GET, f"{STORAGE_URL}/api/v1/files/{NODE}/thumbnail", body=b"jpeg",
                 content_type="image/jpeg")
        pdf = storage_client.get(f"/api/files/{NODE}/content")
        assert pdf.data == b"%PDF"
        thumb = storage_client.get(f"/api/files/{NODE}/thumbnail")
        assert thumb.data == b"jpeg"
    assert pdf.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert pdf.headers["Content-Security-Policy"] == "frame-ancestors 'self'"
    assert thumb.headers["X-Frame-Options"] == "DENY"


def test_api_without_a_session_gets_json_not_a_redirect(anonymous_client):
    response = anonymous_client.get(f"/api/uploads/{NODE}")
    assert response.status_code == 401
    assert response.get_json() == {"detail": "not_signed_in"}


def test_storage_not_configured_is_reported(anonymous_client):
    anonymous_client.set_cookie("ck_sso", "test-session-token")
    assert anonymous_client.get(f"/api/uploads/{NODE}").status_code == 503


def test_storage_unreachable_is_reported(storage_client):
    with responses_lib.RequestsMock() as rsps:
        rsps.add(responses_lib.GET, f"{STORAGE_URL}/api/v1/uploads/{NODE}", body=requests.exceptions.ConnectionError("down"))
        response = storage_client.get(f"/api/uploads/{NODE}")
    assert response.status_code == 502
