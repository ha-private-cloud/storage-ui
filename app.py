import os
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from flask import Flask, g, redirect, render_template, request

app = Flask(__name__)

APP_TITLE = os.environ.get("APP_TITLE", "ClusterKeep")
SESSION_COOKIE_NAME = "ck_sso"
ADMIN_GROUPS = ("cluster-admins", "admin")

app.config["AUTH_API_BASE_URL"] = os.environ.get(
    "AUTH_API_BASE_URL", "https://auth-dev.clusterkeep.dev.net"
).strip()
app.config["AUTH_API_INTERNAL_URL"] = os.environ.get(
    "AUTH_API_INTERNAL_URL", "http://auth-api.clusterkeep-dev-priv.svc.cluster.local"
).strip()
app.config["CLUSTERKEEP_UI_URL"] = os.environ.get(
    "CLUSTERKEEP_UI_URL", "https://dev.clusterkeep.dev.net"
).strip()
app.config["ADMIN_UI_URL"] = os.environ.get("ADMIN_UI_URL", "").strip()

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


@app.after_request
def set_security_headers(response):
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


def logout_url():
    query = urlencode({"post_logout_redirect_uri": app.config["CLUSTERKEEP_UI_URL"]})
    return f"{app.config['AUTH_API_BASE_URL'].rstrip('/')}/logout?{query}"


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
    clusterkeep_ui_url = app.config["CLUSTERKEEP_UI_URL"]
    if not token:
        return redirect(clusterkeep_ui_url)

    try:
        response = requests.get(
            f"{app.config['AUTH_API_INTERNAL_URL']}/session",
            cookies={SESSION_COOKIE_NAME: token},
            timeout=3,
        )
    except requests.RequestException:
        return redirect(clusterkeep_ui_url)

    if response.status_code != 200:
        return redirect(clusterkeep_ui_url)

    g.is_admin = any(group in ADMIN_GROUPS for group in response.json().get("groups", []))
    return None


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
