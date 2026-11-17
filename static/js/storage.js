(function () {
  "use strict";

  const dialog = document.getElementById("viewer");
  const content = document.getElementById("dialog-content");
  const statusLine = document.getElementById("status");
  const uploadsPanel = document.getElementById("uploads");
  if (!dialog || !content) return;

  const NODE_TYPE = "application/x-clusterkeep-node";
  const DROP_HIGHLIGHT = ["ring-2", "ring-amber-600"];
  const ZONE_HIGHLIGHT = ["border-amber-600", "bg-amber-50", "dark:bg-stone-900"];
  const MAX_CHUNK_ATTEMPTS = 4;
  const FALLBACK = "Something went wrong. Try again.";
  const MESSAGES = {
    name_taken: "Something with that name is already here.",
    invalid_name: "That name can't be used.",
    quota_exceeded: "There isn't enough space left for that.",
    storage_unavailable: "Storage is unavailable right now. Try again shortly.",
    storage_not_configured: "Storage isn't set up here yet.",
  };
  const SECTION_RULES = {
    photos: "Photos only accepts images.",
    videos: "Videos only accepts video files.",
    music: "Music only accepts audio files.",
    documents: "Documents only accepts documents, such as PDFs, text and Office files.",
  };
  let uploadQueue = Promise.resolve();

  function say(text) {
    statusLine.textContent = text;
    statusLine.classList.remove("hidden");
    clearTimeout(say.timer);
    say.timer = setTimeout(() => statusLine.classList.add("hidden"), 4000);
  }

  function filesChanged() {
    htmx.trigger(document.body, "files-changed");
  }

  document.body.addEventListener("notify", (event) => say(event.detail.value));
  document.body.addEventListener("close-dialog", () => {
    if (dialog.open) dialog.close();
  });
  document.body.addEventListener("htmx:responseError", () => say(FALLBACK));
  document.body.addEventListener("htmx:sendError", () => say(MESSAGES.storage_unavailable));

  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (event.detail.target !== content) return;
    const wide = Boolean(content.querySelector("[data-dialog-wide]"));
    dialog.classList.toggle("max-w-5xl", wide);
    dialog.classList.toggle("max-w-md", !wide);
    if (!dialog.open) dialog.showModal();
    const field = content.querySelector("[data-select-stem]");
    if (field) {
      const dot = field.value.lastIndexOf(".");
      field.setSelectionRange(0, dot > 0 ? dot : field.value.length);
    }
  });

  dialog.addEventListener("close", () => content.replaceChildren());
  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-close-dialog]")) dialog.close();
  });

  function hasType(event, type) {
    return Boolean(event.dataTransfer) && Array.from(event.dataTransfer.types).includes(type);
  }

  function isItemDrag(event) {
    return hasType(event, NODE_TYPE);
  }

  function isFileDrag(event) {
    return hasType(event, "Files") && !isItemDrag(event);
  }

  function dropTarget(event) {
    return event.target.closest("[data-drop-parent],[data-drop-section],[data-drop-bin]");
  }

  document.addEventListener("dragstart", (event) => {
    const tile = event.target.closest("[data-node-id]");
    if (!tile) return;
    event.dataTransfer.setData(NODE_TYPE, tile.dataset.nodeId);
    event.dataTransfer.effectAllowed = "move";
  });

  document.addEventListener("dragover", (event) => {
    if (isItemDrag(event)) {
      const target = dropTarget(event);
      if (!target) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      target.classList.add(...DROP_HIGHLIGHT);
      return;
    }
    if (!isFileDrag(event)) return;
    const zone = event.target.closest("[data-upload-zone]");
    if (zone) zone.classList.add(...ZONE_HIGHLIGHT);
    const app = event.target.closest("#app");
    if (zone || (app && app.dataset.acceptsUploads === "true")) event.preventDefault();
  });

  document.addEventListener("dragleave", (event) => {
    const target = dropTarget(event);
    if (target) target.classList.remove(...DROP_HIGHLIGHT);
    const zone = event.target.closest("[data-upload-zone]");
    if (zone) zone.classList.remove(...ZONE_HIGHLIGHT);
  });

  document.addEventListener("drop", (event) => {
    if (isItemDrag(event)) {
      const target = dropTarget(event);
      if (!target) return;
      event.preventDefault();
      target.classList.remove(...DROP_HIGHLIGHT);
      const nodeId = event.dataTransfer.getData(NODE_TYPE);
      if (!nodeId) return;
      if ("dropBin" in target.dataset) {
        htmx.ajax("POST", `/nodes/${nodeId}/bin`, { swap: "none" });
      } else if (target.dataset.dropSection) {
        htmx.ajax("POST", `/nodes/${nodeId}/move`, { swap: "none", values: { section: target.dataset.dropSection } });
      } else if (target.dataset.dropParent !== nodeId) {
        htmx.ajax("POST", `/nodes/${nodeId}/move`, { swap: "none", values: { parent_id: target.dataset.dropParent } });
      }
      return;
    }
    if (!isFileDrag(event)) return;
    const files = Array.from(event.dataTransfer.files);
    const zone = event.target.closest("[data-upload-zone]");
    if (zone) {
      event.preventDefault();
      const input = zone.querySelector("[data-upload-input]");
      dialog.close();
      queueUploads(files, input ? input.dataset.parentId : "");
      return;
    }
    const app = event.target.closest("#app");
    if (app && app.dataset.acceptsUploads === "true") {
      event.preventDefault();
      queueUploads(files, app.dataset.uploadParent);
    }
  });

  document.addEventListener("change", (event) => {
    const input = event.target.closest("[data-upload-input]");
    if (!input) return;
    const files = Array.from(input.files);
    const parentId = input.dataset.parentId;
    dialog.close();
    queueUploads(files, parentId);
  });

  class ApiError extends Error {
    constructor(status, data) {
      super((data && data.detail) || `Request failed (${status})`);
      this.status = status;
      this.detail = data && data.detail;
      this.section = data && data.section;
    }
  }

  function errorMessage(err, fallback) {
    if (err instanceof ApiError && err.detail === "wrong_type") return SECTION_RULES[err.section] || fallback;
    return (err instanceof ApiError && MESSAGES[err.detail]) || fallback;
  }

  async function api(path, options) {
    const opts = options || {};
    const method = opts.method || "GET";
    const headers = Object.assign({ "X-Requested-With": "storage-ui" }, opts.headers);
    let body = opts.body;
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
    if (!response.ok) throw new ApiError(response.status, data);
    return data;
  }

  function uploadRow(file) {
    const row = document.createElement("div");
    row.className = "flex flex-col gap-1 p-3 rounded-lg border border-stone-200 dark:border-stone-800 bg-stone-50 dark:bg-stone-950 shadow-lg";
    const name = document.createElement("p");
    name.className = "text-xs font-medium text-stone-700 dark:text-stone-200 truncate";
    name.title = file.name;
    name.textContent = file.name;
    const progress = document.createElement("progress");
    progress.className = "usage-bar";
    progress.max = 100;
    progress.value = 0;
    const label = document.createElement("p");
    label.className = "text-xs text-stone-500 dark:text-stone-400";
    label.textContent = "Waiting…";
    row.append(name, progress, label);
    uploadsPanel.append(row);
    return {
      progress(fraction) {
        progress.value = Math.round(fraction * 100);
        label.textContent = `${progress.value}%`;
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
        json: { parent_id: parentId || null, name: file.name, size: file.size, mime_type: file.type || "application/octet-stream" },
      });
      for (let index = 0; index < upload.chunk_count; index += 1) {
        const start = index * upload.chunk_size;
        await sendChunk(upload.id, index, file.slice(start, Math.min(start + upload.chunk_size, file.size)));
        row.progress((index + 1) / upload.chunk_count);
      }
      await api(`uploads/${upload.id}/complete`, { method: "POST" });
      row.done("Uploaded");
      filesChanged();
    } catch (err) {
      row.done(errorMessage(err, "Upload failed"));
      if (upload) api(`uploads/${upload.id}`, { method: "DELETE" }).catch(() => {});
      if (err instanceof ApiError && (err.status === 401 || err.status === 423)) window.location.reload();
    }
  }

  function queueUploads(files, parentId) {
    for (const file of files) {
      uploadQueue = uploadQueue.then(() => uploadFile(file, parentId));
    }
  }
})();
