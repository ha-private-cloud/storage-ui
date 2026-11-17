import json
import re
from pathlib import Path

import pytest
import responses as responses_lib

from app import app

ROOT = Path(__file__).resolve().parent.parent
AUTH = "http://auth-api.auth-dev-pub.svc.cluster.local"
STORAGE = "http://storage-api.storage-dev-priv.svc.cluster.local/api/v1"
NODE = "0123456789abcdef0123456789abcdef"
FOLDER = "fedcba9876543210fedcba9876543210"
HTMX = {"HX-Request": "true"}
NOW = "2026-11-17T10:30:00+00:00"


def item(name, kind="file", mime="text/plain", node_id=NODE, **extra):
    return {"id": node_id, "name": name, "kind": kind, "section": None, "parent_id": None, "mime_type": mime,
            "size": 2048, "has_thumbnail": False, "modified_at": NOW, "trashed_at": None, **extra}


def listing(items, name="My storage", folder_id=None, path=None, section=None):
    return {"folder": {"id": folder_id, "name": name, "section": section, "path": path or []}, "items": items}


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setitem(app.config, "STORAGE_API_URL", STORAGE.removesuffix("/api/v1"))
    monkeypatch.setitem(app.config, "STORAGE_API_TOKEN", "test-storage-token")
    app.config["TESTING"] = True
    with app.test_client() as client, responses_lib.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        client.set_cookie("ck_sso", "session")
        rsps.add(responses_lib.GET, f"{AUTH}/session", json={"groups": []})
        rsps.add(responses_lib.GET, f"{STORAGE}/usage", json={"used": 100, "quota": 1000})
        yield client, rsps


def triggers(response):
    return json.loads(response.headers["HX-Trigger"])


def test_folder_page_renders_cards_server_side(api):
    client, rsps = api
    rsps.add(responses_lib.GET, f"{STORAGE}/folders", json=listing([
        item("Work", kind="folder", mime=None, node_id=FOLDER),
        item("beach.jpg", mime="image/jpeg"),
        item("notes", mime="application/octet-stream", node_id="1" * 32),
    ]))
    body = client.get("/").get_data(as_text=True)
    assert f'href="/folder/{FOLDER}"' in body
    assert f'hx-get="/dialogs/preview/{NODE}"' in body
    assert f'href="/api/files/{"1" * 32}/content?download=1"' in body
    assert "2.0 KB · JPG · 17 Nov 2026" in body
    assert "100 B of 1000 B used." in body
    assert 'hx-boost="true"' in body


def test_htmx_navigation_gets_only_the_app_region(api):
    client, rsps = api
    rsps.add(responses_lib.GET, f"{STORAGE}/folders", json=listing([]))
    body = client.get("/", headers={**HTMX, "HX-Target": "app"}).get_data(as_text=True)
    assert body.lstrip().startswith('<div id="app"')
    assert "<html" not in body


def test_history_restore_gets_the_full_page(api):
    client, rsps = api
    rsps.add(responses_lib.GET, f"{STORAGE}/folders", json=listing([]))
    body = client.get("/", headers={**HTMX, "HX-Target": "app", "HX-History-Restore-Request": "true"}).get_data(as_text=True)
    assert "<html" in body


def test_sections_say_where_each_file_lives(api):
    client, rsps = api
    work = {"id": FOLDER, "name": "Work"}
    rsps.add(responses_lib.GET, f"{STORAGE}/sections/photos", json=listing(
        [item("desk.png", mime="image/png", location=[work])], name="Photos", folder_id="2" * 32, section="photos"))
    body = client.get("/section/photos").get_data(as_text=True)
    assert "All your photos, from every folder." in body
    assert f'href="/folder/{FOLDER}"' in body
    assert "In My storage / Work" in body
    assert 'aria-current="page"' in body


def test_search_shows_locations_and_an_empty_state(api):
    client, rsps = api
    rsps.add(responses_lib.GET, f"{STORAGE}/search", json={"items": [item("plan.txt", location=[])]},
             match=[responses_lib.matchers.query_param_matcher({"q": "plan"})])
    body = client.get("/search?q=plan").get_data(as_text=True)
    assert "Results for “plan”" in body
    assert "In My storage" in body
    assert client.get("/search?q=").status_code == 302


def test_bin_offers_restore_and_says_how_long_items_last(api):
    client, rsps = api
    rsps.add(responses_lib.GET, f"{STORAGE}/trash", json={"items": [item("old.txt")], "retention_days": 30})
    body = client.get("/bin").get_data(as_text=True)
    assert f'hx-post="/bin/{NODE}/restore"' in body
    assert "deleted for good after 30 days" in body


def test_missing_folders_and_bad_ids(api):
    client, rsps = api
    rsps.add(responses_lib.GET, f"{STORAGE}/folders", json={"detail": "not_found"}, status=404)
    assert "doesn't exist or is in the bin" in client.get(f"/folder/{FOLDER}").get_data(as_text=True)
    assert client.get("/folder/not-an-id").status_code == 404
    assert client.get("/section/nope").status_code == 404


def test_storage_nearly_full_warns(api):
    client, rsps = api
    rsps.replace(responses_lib.GET, f"{STORAGE}/usage", json={"used": 950, "quota": 1000})
    rsps.add(responses_lib.GET, f"{STORAGE}/folders", json=listing([]))
    body = client.get("/").get_data(as_text=True)
    assert "You're nearly out of space." in body
    assert "usage-bar-warn" in body


def test_dialogs_are_only_served_to_htmx_and_escape_names(api):
    client, _ = api
    name = '<img src=x onerror="alert(1)">.txt'
    assert client.get(f"/dialogs/rename/{NODE}", query_string={"name": name}).status_code == 404
    body = client.get(f"/dialogs/rename/{NODE}", query_string={"name": name}, headers=HTMX).get_data(as_text=True)
    assert "<img src=x" not in body
    assert "&lt;img src=x" in body
    assert f'hx-post="/nodes/{NODE}/rename"' in body


def test_move_dialog_leaves_out_the_folder_and_everything_inside_it(api):
    client, rsps = api
    rsps.add(responses_lib.GET, f"{STORAGE}/folder-tree", json={"items": [
        {"id": FOLDER, "path": "Work"}, {"id": "3" * 32, "path": "Work/2026"}, {"id": "4" * 32, "path": "Photos"}]})
    body = client.get(f"/dialogs/move/{FOLDER}", query_string={"name": "Work", "kind": "folder"}, headers=HTMX).get_data(as_text=True)
    assert ">Photos<" in body
    assert ">Work/2026<" not in body
    assert f'value="{FOLDER}"' not in body


def test_pdf_preview_is_a_frame_and_other_files_have_no_preview(api):
    client, _ = api
    body = client.get(f"/dialogs/preview/{NODE}", query_string={"name": "a.pdf", "mime": "application/pdf"}, headers=HTMX).get_data(as_text=True)
    assert f'<iframe src="/api/files/{NODE}/content"' in body
    assert client.get(f"/dialogs/preview/{NODE}", query_string={"name": "a.zip", "mime": "application/zip"}, headers=HTMX).status_code == 404


def test_rename_tells_the_page_to_refresh_close_and_notify(api):
    client, rsps = api
    rsps.add(responses_lib.PATCH, f"{STORAGE}/nodes/{NODE}", json=item("new.txt"),
             match=[responses_lib.matchers.json_params_matcher({"name": "new.txt"})])
    response = client.post(f"/nodes/{NODE}/rename", data={"name": " new.txt "}, headers=HTMX)
    assert response.status_code == 204
    assert triggers(response) == {"close-dialog": True, "notify": "Renamed.", "files-changed": True}


def test_changes_need_htmx(api):
    client, _ = api
    assert client.post(f"/nodes/{NODE}/bin").status_code == 403
    assert client.post("/folders", data={"name": "x"}).status_code == 403


def test_errors_show_in_the_dialog_or_as_a_notice(api):
    client, rsps = api
    rsps.add(responses_lib.POST, f"{STORAGE}/folders", json={"detail": "name_taken"}, status=409)
    in_dialog = client.post("/folders", data={"name": "Work"}, headers={**HTMX, "HX-Target": "dialog-error"})
    assert in_dialog.status_code == 422
    assert "Something with that name is already here." in in_dialog.get_data(as_text=True)
    elsewhere = client.post("/folders", data={"name": "Work"}, headers=HTMX)
    assert elsewhere.status_code == 204
    assert triggers(elsewhere) == {"notify": "Something with that name is already here."}


def test_wrong_type_names_the_section_rule(api):
    client, rsps = api
    rsps.add(responses_lib.PATCH, f"{STORAGE}/nodes/{NODE}", json={"detail": "wrong_type", "section": "photos"}, status=400)
    response = client.post(f"/nodes/{NODE}/move", data={"parent_id": FOLDER}, headers=HTMX)
    assert triggers(response) == {"notify": "Photos only accepts images."}


def test_locked_storage_during_a_change_reloads_the_page(api):
    client, rsps = api
    rsps.add(responses_lib.DELETE, f"{STORAGE}/nodes/{NODE}", json={"detail": "locked"}, status=423)
    response = client.post(f"/nodes/{NODE}/bin", headers=HTMX)
    assert response.headers["HX-Refresh"] == "true"


def test_dropping_on_a_section_moves_into_its_folder(api):
    client, rsps = api
    rsps.add(responses_lib.GET, f"{STORAGE}/sections/music", json=listing([], name="Music", folder_id=FOLDER, section="music"))
    rsps.add(responses_lib.PATCH, f"{STORAGE}/nodes/{NODE}", json=item("song.mp3"),
             match=[responses_lib.matchers.json_params_matcher({"parent_id": FOLDER})])
    response = client.post(f"/nodes/{NODE}/move", data={"section": "music"}, headers=HTMX)
    assert triggers(response)["notify"] == "Moved."


def test_htmx_requests_without_a_session_are_sent_to_sign_in():
    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/", headers=HTMX)
    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == "https://dev.clusterkeep.dev.net/login"


def test_htmx_is_vendored_and_locked_down():
    """htmx must stay self-hosted, pinned, and unable to evaluate code from markup."""
    package = json.loads((ROOT / "package.json").read_text())
    version = package["devDependencies"]["htmx.org"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    assert f'version:"{version}"' in (ROOT / "static" / "js" / "vendor" / "htmx.min.js").read_text()
    index = (ROOT / "templates" / "index.html").read_text()
    config = json.loads(re.search(r"name=\"htmx-config\" content='([^']+)'", index).group(1))
    assert config["allowEval"] is False
    assert config["allowScriptTags"] is False
    assert config["includeIndicatorStyles"] is False
    assert config["selfRequestsOnly"] is True
    assert config["historyCacheSize"] == 0
    for template in (ROOT / "templates").rglob("*.html"):
        markup = template.read_text()
        assert "hx-on" not in markup, template.name
        assert "js:" not in markup, template.name
        assert "javascript:" not in markup, template.name


@pytest.mark.parametrize(("headers", "expected"), [
    ({"X-Forwarded-Proto": "https"}, "https%3A//localhost/"),
    ({}, "http%3A//localhost/"),
    ({"X-Forwarded-Proto": "javascript"}, "http%3A//localhost/"),
])
def test_locked_page_sends_people_back_to_the_address_they_used(api, headers, expected):
    client, rsps = api
    rsps.add(responses_lib.GET, f"{STORAGE}/folders", json={"detail": "locked"}, status=423)
    body = client.get("/", headers=headers).get_data(as_text=True)
    assert f"login?next={expected}" in body
