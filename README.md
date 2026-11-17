# storage-ui

The file browser for ClusterKeep. This is where people upload, organise, view and download their files. All the storage itself happens in storage-api. storage-ui renders the pages from storage-api's data and passes uploads and downloads through to it.

## What it does

- Photos, Videos, Music and Documents sections in the sidebar, plus All Files and a Bin.
- Browse folders with breadcrumbs and a back button. Every folder, section, search and the bin has its own address, so the browser's back button and bookmarks work.
- Each file shows its size, type and when it was last changed.
- Create, rename and move folders and files. Items can be dragged onto a folder, a breadcrumb or a sidebar section to move them, or onto the Bin to delete them.
- Upload by choosing files or dropping them on the page. Large files go up in 8 MiB chunks with a progress bar, and a failed chunk is retried.
- The default folders only take their own kind of file, so Photos only accepts images. The file picker is filtered to match.
- Each section lists its kind of file from every folder, and says which folder each one is in.
- View photos and PDFs, play videos and music in the browser, and download anything.
- Thumbnails for photos and video posters.
- Search by file or folder name, with each result showing the folder it's in.
- The bin keeps deleted items for 30 days and they can be restored.
- A bar showing how much of the quota is used, which turns red and warns when it's nearly full.
- Unknown pages show the same 404 page as the other sites.

Signed-out visitors are sent to the clusterkeep-ui login page. If someone's storage is locked, the page asks them to log in again.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/`, `/folder/<id>`, `/section/<name>`, `/search?q=`, `/bin` | The file browser pages |
| GET | `/dialogs/...` | Fragments for the new folder, rename, move, bin, delete, upload and preview dialogs |
| POST | `/folders`, `/nodes/<id>/rename`, `/nodes/<id>/move`, `/nodes/<id>/bin`, `/bin/<id>/restore`, `/bin/<id>/delete` | Changes, passed on to storage-api |
| GET, POST, PUT, DELETE | `/api/<path>` | Uploads and file downloads, passed through to storage-api's `/api/v1/<path>` |
| GET | `/healthz` | Kubernetes health check |

storage-ui fetches the data for each page from storage-api and renders it as HTML. htmx swaps just the main part of the page when you follow a link or search, and the change routes reply with events that refresh the listing, close the dialog and show a notice. The change routes only accept requests from htmx, which stops other sites posting to them.

The `/api/` pass-through only allows uploads, upload status, file contents and thumbnails, and returns 404 for anything else, so the vault endpoints can't be reached from the browser. It adds storage-api's service token and the user's session cookie. Uploads and downloads are streamed through without being held in memory, and the `Range` header is passed on so videos can seek. Anything that changes data must carry an `X-Requested-With: storage-ui` header.

## Technologies

- Python 3.13 and Flask, served by gunicorn
- Jinja templates for every page and dialog, which escape file names so they're never treated as HTML
- htmx for navigation and changes. It's kept in `static/js/vendor/` rather than loaded from a CDN, pinned in `package.json`, and configured so it can't run code from the page or keep pages in the browser's history cache
- One small vanilla JavaScript file for what htmx can't do, which is chunked uploads, drag and drop, and opening dialogs
- Tailwind CSS, built ahead of time
- requests for the calls to auth-api and storage-api
- pytest with the responses library for the tests
- uv for dependencies, Docker for the image, Helm and OpenTofu for deployment

## Configuration

| Variable | What it's for |
|---|---|
| `STORAGE_API_URL` | storage-api's address inside the cluster |
| `STORAGE_API_TOKEN` | Service token for storage-api |
| `AUTH_API_INTERNAL_URL` | auth-api's address inside the cluster, used to check the session when the page loads |
| `CLUSTERKEEP_UI_URL` | clusterkeep-ui's address, for log in, log out and the 404 page |
| `ADMIN_UI_URL` | admin-ui's address, shown to admins |
| `APP_TITLE` | Site title, defaults to ClusterKeep |

## Running locally

The easiest way is [common-dev-env](https://github.com/LandRegistry/common-dev-env) with the [dev-env-config](https://github.com/ha-private-cloud/dev-env-config) repository, set up as the [organisation README](https://github.com/ha-private-cloud/.github/blob/main/profile/README.md#running-it-locally) describes. That runs it on http://localhost:9081 alongside storage-api and the other services. You can also run it on its own.

```sh
uv sync
npm install
npm run build:css
uv run flask --app app run --debug
```

Run the tests with `uv run pytest`. Rebuild the CSS after changing a template or the JavaScript. After updating htmx in `package.json`, run `npm install` and copy `node_modules/htmx.org/dist/htmx.min.js` into `static/js/vendor/`, otherwise the tests fail.

## Deployment

The GitHub workflows come from the shared `pipelines` repo.

- Pushes to `development` and `preview` build the image in the cluster through cluster-ci and deploy it to dev and preview.
- Merges to `main` build the image without deploying it.
- Pushing a `vX.Y.Z` tag builds the release image, and running the release workflow with that tag deploys it to production.

`preview` and `main` only take changes through pull requests. The Helm chart is in `charts/storage-ui` and the OpenTofu config is in `tofu/`. Deploy storage-api to an environment before storage-ui.
