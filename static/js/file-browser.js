(function () {
  "use strict";

  const main = document.getElementById("main-content");
  if (!main) return;

  const loginUrl = main.dataset.loginUrl;
  const navLinks = Array.from(document.querySelectorAll(".nav-link"));
  const usageBar = document.getElementById("usage-bar");
  const usageText = document.getElementById("usage-text");
  const uploadsPanel = document.getElementById("uploads");
  const fileInput = document.getElementById("file-input");
  const statusLine = document.getElementById("status");
  const viewer = document.getElementById("viewer");
  const viewerTitle = document.getElementById("viewer-title");
  const viewerBody = document.getElementById("viewer-body");

  const SECTIONS = { photos: "Photos", videos: "Videos", music: "Music", documents: "Documents" };
  const MAX_CHUNK_ATTEMPTS = 4;
  const MESSAGES = {
    name_taken: "Something with that name is already here.",
    invalid_name: "That name can't be used.",
    quota_exceeded: "There isn't enough space left for that.",
    default_folder: "That folder can't be changed.",
    cannot_move_into_itself: "A folder can't be moved into itself.",
    storage_unavailable: "Storage is unavailable right now. Try again shortly.",
    storage_not_configured: "Storage isn't set up here yet.",
  };

  const ACTIVE = ["bg-stone-200", "dark:bg-stone-800", "text-stone-900", "dark:text-stone-50"];
  const INACTIVE = ["text-stone-600", "dark:text-stone-400", "hover:bg-stone-100", "dark:hover:bg-stone-900", "hover:text-stone-900", "dark:hover:text-stone-50"];
  const BUTTON = "inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-700";
  const SECONDARY = `${BUTTON} text-stone-700 dark:text-stone-200 bg-stone-100 hover:bg-stone-200 dark:bg-stone-900 dark:hover:bg-stone-800 border border-stone-300 dark:border-stone-700`;
  const PRIMARY = `${BUTTON} text-white bg-amber-700 hover:bg-amber-800 shadow-sm`;
  const ICON_BUTTON = "p-1.5 rounded-md bg-white/90 dark:bg-stone-900/90 text-stone-700 dark:text-stone-200 hover:text-amber-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-700";

  const ICON_PATHS = {
    folder: "M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z",
    image: "M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z",
    video: "M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z",
    audio: "M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3",
    file: "M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z",
    upload: "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12",
    newFolder: "M9 13h6m-3-3v6M3 7a2 2 0 012-2h4l2 2h6a2 2 0 012 2v7a2 2 0 01-2 2H5a2 2 0 01-2-2V7z",
    download: "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4",
    rename: "M15.232 5.232l3.536 3.536M9 13l6.232-6.232a2.5 2.5 0 113.536 3.536L12.536 16.5H9V13z",
    move: "M13 7l5 5m0 0l-5 5m5-5H6",
    bin: "M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16",
    restore: "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15",
  };

  let currentFolderId = null;
  let uploadTarget = null;
  let uploadQueue = Promise.resolve();

  function el(tag, props, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props || {})) {
      if (value === undefined || value === null || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? "" : value);
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function icon(name, classes) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", classes || "w-5 h-5");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    path.setAttribute("stroke-width", "1.5");
    path.setAttribute("d", ICON_PATHS[name]);
    svg.append(path);
    return svg;
  }

  function kindOf(item) {
    if (item.kind === "folder") return "folder";
    const mime = item.mime_type || "";
    if (mime.startsWith("image/")) return "image";
    if (mime.startsWith("video/")) return "video";
    if (mime.startsWith("audio/")) return "audio";
    return "file";
  }

  function formatBytes(bytes) {
    const units = ["B", "KB", "MB", "GB", "TB"];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024;
      unit += 1;
    }
    return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
  }

  class ApiError extends Error {
    constructor(status, detail) {
      super(detail || `Request failed (${status})`);
      this.status = status;
      this.detail = detail;
    }
  }

  async function api(path, options) {
    const opts = options || {};
    const method = opts.method || "GET";
    const headers = Object.assign({}, opts.headers);
    let body = opts.body;
    if (method !== "GET") headers["X-Requested-With"] = "storage-ui";
    if (opts.json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.json);
    }
    const response = await fetch(`/api/${path}`, { method, headers, body, credentials: "same-origin" });
    if (response.status === 204) return null;
    let data = null;
    try {
      data = await response.json();
    } catch (err) {
      data = null;
    }
    if (!response.ok) throw new ApiError(response.status, data && data.detail);
    return data;
  }

  function say(text) {
    statusLine.textContent = text;
    statusLine.classList.remove("hidden");
    clearTimeout(say.timer);
    say.timer = setTimeout(() => statusLine.classList.add("hidden"), 4000);
  }

  function showLocked() {
    const next = encodeURIComponent(`${window.location.origin}/`);
    main.replaceChildren(
      el("div", { class: "max-w-md mx-auto text-center py-16" },
        el("h2", { class: "font-display text-2xl font-semibold text-stone-900 dark:text-stone-50 mb-4", text: "Your storage is locked" }),
        el("p", { class: "text-stone-600 dark:text-stone-300 mb-8", text: "Log in again to unlock your files." }),
        el("a", { class: PRIMARY, href: `${loginUrl}?next=${next}`, text: "Log in" }),
      ),
    );
  }

  function handleError(err) {
    if (err instanceof ApiError && (err.status === 401 || err.status === 423)) {
      showLocked();
      return;
    }
    say((err instanceof ApiError && MESSAGES[err.detail]) || "Something went wrong. Try again.");
  }

  async function refreshUsage() {
    try {
      const usage = await api("usage");
      const percent = usage.quota ? Math.min(100, (usage.used / usage.quota) * 100) : 0;
      usageBar.style.width = `${percent}%`;
      usageText.textContent = `${formatBytes(usage.used)} of ${formatBytes(usage.quota)} used`;
    } catch (err) {
      usageText.textContent = "";
    }
  }

  function setActiveNav(section) {
    for (const link of navLinks) {
      const active = link.dataset.section === section;
      link.classList.remove(...(active ? INACTIVE : ACTIVE));
      link.classList.add(...(active ? ACTIVE : INACTIVE));
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
  }

  function spinner() {
    main.replaceChildren(el("div", { class: "flex items-center justify-center h-64 text-stone-500 dark:text-stone-400", text: "Loading…" }));
  }

  function route() {
    const hash = decodeURIComponent(window.location.hash.slice(1));
    if (!hash || hash === "all") return { view: "folder", id: null, nav: "all" };
    if (hash.startsWith("folder/")) return { view: "folder", id: hash.slice(7), nav: "all" };
    if (hash.startsWith("search/")) return { view: "search", query: hash.slice(7), nav: null };
    if (hash === "trash") return { view: "trash", nav: "trash" };
    if (SECTIONS[hash]) return { view: "section", section: hash, nav: hash };
    return { view: "folder", id: null, nav: "all" };
  }

  function go(hash) {
    if (window.location.hash === `#${hash}`) render();
    else window.location.hash = hash;
  }

  function folderHash(item) {
    return item.section ? item.section : `folder/${item.id}`;
  }

  function searchForm(initial) {
    const input = el("input", {
      type: "search",
      name: "q",
      value: initial || "",
      placeholder: "Search files",
      "aria-label": "Search files",
      class: "w-full sm:w-56 px-3 py-2 text-sm rounded-lg border border-stone-300 dark:border-stone-700 bg-white dark:bg-stone-900 text-stone-900 dark:text-stone-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-700",
    });
    return el("form", {
      class: "w-full sm:w-auto",
      role: "search",
      onsubmit: (event) => {
        event.preventDefault();
        const query = input.value.trim();
        if (query) go(`search/${encodeURIComponent(query)}`);
      },
    }, input);
  }

  function header(title, crumbs, options) {
    const opts = options || {};
    const trail = crumbs && crumbs.length
      ? el("nav", { class: "flex flex-wrap items-center gap-1 text-sm text-stone-500 dark:text-stone-400 mb-1", "aria-label": "Folder path" },
          el("a", { href: "#all", class: "hover:text-amber-700", text: "My storage" }),
          crumbs.slice(0, -1).map((crumb) => [" / ", el("a", { href: `#folder/${crumb.id}`, class: "hover:text-amber-700", text: crumb.name })]),
        )
      : null;
    const actions = el("div", { class: "flex flex-wrap items-center gap-3" }, searchForm(opts.query));
    if (opts.canAdd) {
      actions.append(
        el("button", { type: "button", class: SECONDARY, onclick: newFolder }, icon("newFolder", "w-4 h-4"), "New folder"),
        el("button", { type: "button", class: PRIMARY, onclick: () => fileInput.click() }, icon("upload", "w-4 h-4"), "Upload"),
      );
    }
    return el("div", { class: "flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6" },
      el("div", { class: "min-w-0" }, trail, el("h2", { class: "text-2xl font-display font-semibold text-stone-900 dark:text-stone-50 truncate", text: title })),
      actions,
    );
  }

  function emptyState(text) {
    return el("p", { class: "text-stone-500 dark:text-stone-400 mt-8", text });
  }

  function actionButton(name, label, handler) {
    return el("button", {
      type: "button",
      class: ICON_BUTTON,
      "aria-label": label,
      title: label,
      onclick: (event) => {
        event.stopPropagation();
        handler();
      },
    }, icon(name, "w-4 h-4"));
  }

  function card(item, options) {
    const opts = options || {};
    const kind = kindOf(item);
    const open = () => (kind === "folder" ? go(folderHash(item)) : openFile(item));
    const preview = item.has_thumbnail
      ? el("img", { src: `/api/files/${item.id}/thumbnail`, alt: "", loading: "lazy", class: "absolute inset-0 w-full h-full object-cover" })
      : el("div", { class: "absolute inset-0 flex items-center justify-center" },
          icon(kind, kind === "folder" ? "w-14 h-14 text-amber-500" : "w-12 h-12 text-stone-300 dark:text-stone-700"));

    const actions = el("div", { class: "absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity" });
    if (opts.trash) {
      actions.append(
        actionButton("restore", "Restore", () => restore(item)),
        actionButton("bin", "Delete forever", () => deleteForever(item)),
      );
    } else if (!item.section) {
      if (kind !== "folder") actions.append(actionButton("download", "Download", () => download(item)));
      actions.append(
        actionButton("rename", "Rename", () => rename(item)),
        actionButton("move", "Move", () => move(item)),
        actionButton("bin", "Move to bin", () => binItem(item)),
      );
    }

    const tile = el("div", {
      class: "group relative aspect-square bg-stone-100 dark:bg-stone-900 rounded-xl overflow-hidden border border-stone-200 dark:border-stone-800 cursor-pointer hover:border-amber-500 dark:hover:border-amber-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-700 transition-all",
      tabindex: "0",
      role: "button",
      "aria-label": item.name,
      onclick: opts.trash ? null : open,
      onkeydown: (event) => {
        if (!opts.trash && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          open();
        }
      },
    }, preview, actions);

    const detail = kind === "folder" ? "Folder" : formatBytes(item.size);
    return el("div", { class: "flex flex-col gap-1 min-w-0" },
      tile,
      el("p", { class: "text-stone-700 dark:text-stone-200 text-xs font-medium truncate", title: item.name, text: item.name }),
      el("p", { class: "text-stone-500 dark:text-stone-400 text-xs", text: detail }),
    );
  }

  function grid(items, options) {
    return el("div", { class: "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5 gap-4 fade-in" },
      items.map((item) => card(item, options)));
  }

  async function render() {
    const state = route();
    setActiveNav(state.nav);
    spinner();
    try {
      if (state.view === "trash") return renderTrash();
      if (state.view === "search") return renderSearch(state.query);
      const data = state.view === "section"
        ? await api(`sections/${state.section}`)
        : await api(state.id ? `folders?parent_id=${encodeURIComponent(state.id)}` : "folders");
      currentFolderId = data.folder.id;
      const crumbs = state.view === "section" ? null : data.folder.path;
      main.replaceChildren(
        header(data.folder.name, crumbs, { canAdd: true }),
        data.items.length ? grid(data.items) : emptyState("Nothing here yet. Upload files or drop them on this page."),
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        main.replaceChildren(header("Not found", null, {}), emptyState("That folder doesn't exist or is in the bin."));
        return;
      }
      handleError(err);
    }
  }

  async function renderTrash() {
    currentFolderId = null;
    const data = await api("trash");
    main.replaceChildren(
      header("Bin", null, {}),
      el("p", { class: "text-sm text-stone-500 dark:text-stone-400 mb-6", text: `Items in the bin are deleted for good after ${data.retention_days} days.` }),
      data.items.length ? grid(data.items, { trash: true }) : emptyState("The bin is empty."),
    );
  }

  async function renderSearch(query) {
    currentFolderId = null;
    const data = await api(`search?q=${encodeURIComponent(query)}`);
    main.replaceChildren(
      header(`Results for “${query}”`, null, { query }),
      data.items.length ? grid(data.items) : emptyState("No files or folders match that name."),
    );
  }

  async function newFolder() {
    const name = window.prompt("Folder name");
    if (!name || !name.trim()) return;
    try {
      await api("folders", { method: "POST", json: { parent_id: currentFolderId, name: name.trim() } });
      render();
    } catch (err) {
      handleError(err);
    }
  }

  async function rename(item) {
    const name = window.prompt("New name", item.name);
    if (!name || !name.trim() || name.trim() === item.name) return;
    try {
      await api(`nodes/${item.id}`, { method: "PATCH", json: { name: name.trim() } });
      render();
    } catch (err) {
      handleError(err);
    }
  }

  async function move(item) {
    let folders;
    try {
      folders = (await api("folder-tree")).items;
    } catch (err) {
      handleError(err);
      return;
    }
    const own = item.kind === "folder" ? folders.find((f) => f.id === item.id) : null;
    const choices = folders.filter((f) => !own || (f.id !== own.id && !f.path.startsWith(`${own.path}/`)));
    const select = el("select", {
      class: "w-full px-3 py-2 rounded-lg border border-stone-300 dark:border-stone-700 bg-white dark:bg-stone-900 text-stone-900 dark:text-stone-100",
      "aria-label": "Destination folder",
    },
      el("option", { value: "", text: "My storage" }),
      choices.map((f) => el("option", { value: f.id, text: f.path, selected: f.id === item.parent_id })),
    );
    const confirm = el("button", {
      type: "button",
      class: PRIMARY,
      onclick: async () => {
        try {
          await api(`nodes/${item.id}`, { method: "PATCH", json: { parent_id: select.value || null } });
          viewer.close();
          render();
        } catch (err) {
          viewer.close();
          handleError(err);
        }
      },
    }, "Move here");
    showDialog(`Move “${item.name}”`, el("div", { class: "w-full max-w-md flex flex-col gap-4" }, select, confirm));
  }

  async function binItem(item) {
    if (!window.confirm(`Move “${item.name}” to the bin?`)) return;
    try {
      await api(`nodes/${item.id}`, { method: "DELETE" });
      say("Moved to the bin.");
      render();
    } catch (err) {
      handleError(err);
    }
  }

  async function restore(item) {
    try {
      await api(`trash/${item.id}/restore`, { method: "POST" });
      say("Restored.");
      render();
    } catch (err) {
      handleError(err);
    }
  }

  async function deleteForever(item) {
    if (!window.confirm(`Delete “${item.name}” for good? This can't be undone.`)) return;
    try {
      await api(`trash/${item.id}`, { method: "DELETE" });
      render();
      refreshUsage();
    } catch (err) {
      handleError(err);
    }
  }

  function download(item) {
    const link = el("a", { href: `/api/files/${item.id}/content?download=1`, download: item.name });
    document.body.append(link);
    link.click();
    link.remove();
  }

  function showDialog(title, content) {
    viewerTitle.textContent = title;
    viewerBody.replaceChildren(content);
    viewer.showModal();
  }

  function openFile(item) {
    const source = `/api/files/${item.id}/content`;
    const kind = kindOf(item);
    let content;
    if (kind === "image") content = el("img", { src: source, alt: item.name, class: "max-h-[75vh] max-w-full object-contain" });
    else if (kind === "video") content = el("video", { src: source, controls: true, autoplay: true, class: "max-h-[75vh] max-w-full" });
    else if (kind === "audio") content = el("audio", { src: source, controls: true, autoplay: true, class: "w-full" });
    else {
      download(item);
      return;
    }
    showDialog(item.name, el("div", { class: "w-full flex flex-col items-center gap-4" },
      content,
      el("button", { type: "button", class: SECONDARY, onclick: () => download(item) }, icon("download", "w-4 h-4"), "Download")));
  }

  function uploadRow(file) {
    const bar = el("div", { class: "bg-amber-600 h-1.5 rounded-full w-0" });
    const label = el("p", { class: "text-xs text-stone-500 dark:text-stone-400", text: "Waiting…" });
    const row = el("div", { class: "flex flex-col gap-1" },
      el("p", { class: "text-xs font-medium text-stone-700 dark:text-stone-200 truncate", title: file.name, text: file.name }),
      el("div", { class: "w-full bg-stone-200 dark:bg-stone-800 rounded-full h-1.5" }, bar),
      label);
    uploadsPanel.append(row);
    return {
      progress(fraction) {
        bar.style.width = `${Math.round(fraction * 100)}%`;
        label.textContent = `${Math.round(fraction * 100)}%`;
      },
      done(text) {
        label.textContent = text;
        setTimeout(() => row.remove(), 6000);
      },
    };
  }

  function wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function sendChunk(uploadId, index, blob) {
    for (let attempt = 1; ; attempt += 1) {
      try {
        await api(`uploads/${uploadId}/chunks/${index}`, { method: "PUT", body: blob, headers: { "Content-Type": "application/octet-stream" } });
        return;
      } catch (err) {
        const retryable = !(err instanceof ApiError) || err.status >= 500;
        if (!retryable || attempt >= MAX_CHUNK_ATTEMPTS) throw err;
        await wait(1000 * 2 ** (attempt - 1));
      }
    }
  }

  async function uploadFile(file, parentId) {
    const row = uploadRow(file);
    let upload;
    try {
      upload = await api("uploads", {
        method: "POST",
        json: { parent_id: parentId, name: file.name, size: file.size, mime_type: file.type || "application/octet-stream" },
      });
      for (let index = 0; index < upload.chunk_count; index += 1) {
        const start = index * upload.chunk_size;
        await sendChunk(upload.id, index, file.slice(start, Math.min(start + upload.chunk_size, file.size)));
        row.progress((index + 1) / upload.chunk_count);
      }
      await api(`uploads/${upload.id}/complete`, { method: "POST" });
      row.done("Uploaded");
      if (currentFolderId === parentId) render();
      refreshUsage();
    } catch (err) {
      row.done((err instanceof ApiError && MESSAGES[err.detail]) || "Upload failed");
      if (upload) api(`uploads/${upload.id}`, { method: "DELETE" }).catch(() => {});
      if (err instanceof ApiError && (err.status === 401 || err.status === 423)) showLocked();
    }
  }

  function queueUploads(files) {
    const target = uploadTarget;
    for (const file of files) {
      uploadQueue = uploadQueue.then(() => uploadFile(file, target));
    }
  }

  fileInput.addEventListener("change", () => {
    uploadTarget = currentFolderId;
    queueUploads(Array.from(fileInput.files));
    fileInput.value = "";
  });

  main.addEventListener("dragover", (event) => {
    if (route().view === "folder" || route().view === "section") event.preventDefault();
  });
  main.addEventListener("drop", (event) => {
    const view = route().view;
    if (view !== "folder" && view !== "section") return;
    event.preventDefault();
    uploadTarget = currentFolderId;
    queueUploads(Array.from(event.dataTransfer.files));
  });

  document.getElementById("viewer-close").addEventListener("click", () => viewer.close());
  viewer.addEventListener("close", () => viewerBody.replaceChildren());

  window.addEventListener("hashchange", render);
  render();
  refreshUsage();
})();
