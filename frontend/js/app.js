(function () {
  const API_BASE = "";

  function $(sel) { return document.querySelector(sel); }

  // Router
  function showPage(name) {
    document.querySelectorAll(".page").forEach(p => p.classList.add("hidden"));
    document.querySelectorAll(".nav-link").forEach(a => a.classList.remove("active"));
    const page = $(`#page-${name}`);
    if (page) page.classList.remove("hidden");
    const link = $(`.nav-link[data-page="${name}"]`);
    if (link) link.classList.add("active");

    if (name === "overview") loadOverview();
    if (name === "log") loadLog(1);
    if (name === "ingest") loadRecent();
    if (name === "wiki") {
      loadWikiTree();
      const path = window.location.pathname.replace(/^\/wiki\/?/, "").replace(/\/$/, "");
      if (path) {
        loadWikiPage(path);
      } else {
        loadWikiPage("index.md");
      }
    }
    if (name === "graph") {
      // Graph tab is handled by graph.js
    }
  }

  function route() {
    const path = window.location.pathname.replace(/\/$/, "");
    if (path === "/overview") showPage("overview");
    else if (path === "/log") showPage("log");
    else if (path.startsWith("/wiki")) showPage("wiki");
    else showPage("ingest");
  }

  window.addEventListener("popstate", route);
  document.querySelectorAll(".nav-link").forEach(a => {
    a.addEventListener("click", e => {
      e.preventDefault();
      history.pushState({}, "", a.getAttribute("href"));
      route();
    });
  });

  // Intercept wiki link clicks inside rendered content
  document.addEventListener("click", e => {
    const a = e.target.closest("a");
    if (!a) return;
    const href = a.getAttribute("href");
    if (!href) return;
    if (href.startsWith("/wiki/")) {
      e.preventDefault();
      const path = href.replace("/wiki/", "");
      history.pushState({}, "", `/wiki/${path}`);
      showPage("wiki");
    }
  });

  // URL ingest
  $("#url-form").addEventListener("submit", async e => {
    e.preventDefault();
    const url = $("#url-input").value.trim();
    const statusEl = $("#url-status");
    statusEl.textContent = "Queueing...";
    statusEl.className = "status running";
    try {
      const res = await fetch(`${API_BASE}/api/ingest/url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed");
      statusEl.textContent = `Job ${data.job_id} queued.`;
      statusEl.className = "status success";
      pollJob(data.job_id, statusEl);
      loadRecent();
    } catch (err) {
      statusEl.textContent = err.message;
      statusEl.className = "status error";
    }
  });

  // File upload
  const dropzone = $("#dropzone");
  const fileInput = $("#file-input");
  let selectedFile = null;

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("dragover", e => { e.preventDefault(); dropzone.classList.add("dragover"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", e => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      selectedFile = e.dataTransfer.files[0];
      dropzone.querySelector("p").textContent = selectedFile.name;
      $("#file-submit").disabled = false;
    }
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) {
      selectedFile = fileInput.files[0];
      dropzone.querySelector("p").textContent = selectedFile.name;
      $("#file-submit").disabled = false;
    }
  });

  $("#file-submit").addEventListener("click", async () => {
    if (!selectedFile) return;
    const statusEl = $("#file-status");
    statusEl.textContent = "Uploading...";
    statusEl.className = "status running";
    const form = new FormData();
    form.append("file", selectedFile);
    try {
      const res = await fetch(`${API_BASE}/api/ingest/upload`, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed");
      statusEl.textContent = `Job ${data.job_id} queued.`;
      statusEl.className = "status success";
      pollJob(data.job_id, statusEl);
      loadRecent();
    } catch (err) {
      statusEl.textContent = err.message;
      statusEl.className = "status error";
    }
  });

  // Poll job status
  function pollJob(jobId, el) {
    const iv = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/status/${jobId}`);
        const data = await res.json();
        if (!res.ok) { clearInterval(iv); return; }
        if (data.status === "done") {
          el.textContent = `Done: ${data.message}`;
          el.className = "status success";
          clearInterval(iv);
          loadRecent();
        } else if (data.status === "failed") {
          el.textContent = `Failed: ${data.message}`;
          el.className = "status error";
          clearInterval(iv);
          loadRecent();
        } else {
          el.textContent = `${data.status}: ${data.message}`;
          el.className = "status running";
        }
      } catch (err) {
        // ignore polling errors
      }
    }, 3000);
  }

  // Load overview
  async function loadOverview() {
    const el = $("#overview-content");
    el.innerHTML = "Loading...";
    try {
      const res = await fetch(`${API_BASE}/api/overview`);
      const data = await res.json();
      el.innerHTML = data.html;
    } catch (err) {
      el.textContent = "Error loading overview.";
    }
  }

  // Load log
  async function loadLog(page) {
    const el = $("#log-content");
    const pagEl = $("#log-pagination");
    el.innerHTML = "Loading...";
    pagEl.innerHTML = "";
    try {
      const res = await fetch(`${API_BASE}/api/log?page=${page}&per_page=50`);
      const data = await res.json();
      el.innerHTML = data.html || "<p>No entries.</p>";
      if (data.pages > 1) {
        for (let i = 1; i <= data.pages; i++) {
          const btn = document.createElement("button");
          btn.textContent = i;
          if (i === data.page) btn.disabled = true;
          btn.addEventListener("click", () => loadLog(i));
          pagEl.appendChild(btn);
        }
      }
    } catch (err) {
      el.textContent = "Error loading log.";
    }
  }

  // Store jobs globally for filtering
  let recentJobsCache = null;

  // Load recent jobs
  async function loadRecent() {
    const el = $("#recent-jobs");
    try {
      const res = await fetch(`${API_BASE}/api/recent`);
      const data = await res.json();
      if (!data.jobs || !data.jobs.length) {
        el.innerHTML = "<p>No recent jobs.</p>";
        recentJobsCache = [];
        return;
      }
      recentJobsCache = data.jobs;
      renderJobs(recentJobsCache);
    } catch (err) {
      el.textContent = "Error loading recent jobs.";
    }
  }

  // Render jobs with optional filtering
  function renderJobs(jobs) {
    const el = $("#recent-jobs");
    const nameFilter = ($("#job-filter-name")?.value || "").toLowerCase();
    const dateFilter = $("#job-filter-date")?.value || "";
    const statusFilter = $("#job-filter-status")?.value || "";

    let filtered = jobs;

    if (nameFilter) {
      filtered = filtered.filter(j => (j.title || "").toLowerCase().includes(nameFilter));
    }

    if (dateFilter) {
      filtered = filtered.filter(j => {
        const jobDate = j.date ? new Date(j.date).toISOString().split('T')[0] : "";
        return jobDate === dateFilter;
      });
    }

    if (statusFilter) {
      filtered = filtered.filter(j => j.status === statusFilter);
    }

    if (!filtered.length) {
      el.innerHTML = "<p>No jobs match the current filters.</p>";
      return;
    }

    el.innerHTML = `<div class="job-list">${filtered.map(j => {
      const source = j.source ? `<span class="job-source">${escapeHtml(j.source)}</span>` : '';
      return `<div class="job-item" data-job-id="${escapeHtml(j.job_id || "")}">
        <div class="job-info">
          <span class="job-title">${escapeHtml(j.title || "Untitled")}</span>
          ${source}
          <span class="job-date">${formatJobDate(j.date)}</span>
        </div>
        <span class="job-status ${j.status}">${j.status}</span>
      </div>`;
    }).join("")}</div>`;
  }

  function formatJobDate(dateStr) {
    if (!dateStr) return "Unknown date";
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "Invalid date";
    return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  // Filter event listeners
  $("#job-filter-name")?.addEventListener("input", () => {
    if (recentJobsCache) renderJobs(recentJobsCache);
  });

  $("#job-filter-date")?.addEventListener("change", () => {
    if (recentJobsCache) renderJobs(recentJobsCache);
  });

  $("#job-filter-status")?.addEventListener("change", () => {
    if (recentJobsCache) renderJobs(recentJobsCache);
  });

  $("#job-filter-clear")?.addEventListener("click", () => {
    $("#job-filter-name").value = "";
    $("#job-filter-date").value = "";
    $("#job-filter-status").value = "";
    if (recentJobsCache) renderJobs(recentJobsCache);
  });

  // Wiki tree
  let wikiPagesCache = null;

  async function loadWikiTree() {
    const el = $("#wiki-tree");
    if (wikiPagesCache) {
      renderWikiTree(wikiPagesCache);
      return;
    }
    el.textContent = "Loading...";
    try {
      const res = await fetch(`${API_BASE}/api/pages`);
      const data = await res.json();
      wikiPagesCache = data.pages || [];
      renderWikiTree(wikiPagesCache);
    } catch (err) {
      el.textContent = "Error loading wiki tree.";
    }
  }

  function renderWikiTree(pages) {
    const el = $("#wiki-tree");
    const byFolder = {};
    pages.forEach(p => {
      const folder = p.folder || "(root)";
      if (!byFolder[folder]) byFolder[folder] = [];
      byFolder[folder].push(p);
    });

    let html = "";
    Object.keys(byFolder).sort().forEach(folder => {
      html += `<details ${folder === "(root)" ? "open" : ""}>`;
      html += `<summary class="folder-name">${escapeHtml(folder)}</summary>`;
      html += `<ul class="page-list">`;
      byFolder[folder].sort((a, b) => a.title.localeCompare(b.title)).forEach(p => {
        html += `<li><a href="/wiki/${p.path.replace(/\.md$/, "")}" class="page-link" data-path="${p.path}">${escapeHtml(p.title)}</a></li>`;
      });
      html += `</ul></details>`;
    });
    el.innerHTML = html;

    // Highlight current page in tree
    const current = window.location.pathname.replace(/^\/wiki\/?/, "").replace(/\/$/, "");
    el.querySelectorAll(".page-link").forEach(a => {
      if (a.getAttribute("data-path").replace(/\.md$/, "") === current) {
        a.classList.add("active");
      }
    });
  }

  async function loadWikiPage(path) {
    const contentEl = $("#wiki-content");
    const titleEl = $("#wiki-title");
    const bcEl = $("#wiki-breadcrumbs");
    contentEl.innerHTML = "Loading...";
    try {
      const apiPath = path.endsWith(".md") ? path : path + ".md";
      const res = await fetch(`${API_BASE}/api/pages/${encodeURIComponent(apiPath)}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed");
      titleEl.textContent = data.title;
      contentEl.innerHTML = data.html;
      bcEl.innerHTML = buildBreadcrumbs(data.path);
    } catch (err) {
      contentEl.innerHTML = `<p class="error">${escapeHtml(err.message)}</p>`;
      titleEl.textContent = "Error";
      bcEl.innerHTML = "";
    }
    // Refresh active state in tree
    if (wikiPagesCache) renderWikiTree(wikiPagesCache);
  }

  function buildBreadcrumbs(path) {
    const parts = path.split("/");
    let accum = "";
    let html = `<a href="/wiki">Wiki</a>`;
    parts.forEach((part, i) => {
      accum = accum ? `${accum}/${part}` : part;
      const label = part.replace(/\.md$/, "").replace(/-/g, " ");
      const isLast = i === parts.length - 1;
      html += ` <span class="bc-sep">/</span> `;
      if (isLast) {
        html += `<span class="bc-current">${escapeHtml(label)}</span>`;
      } else {
        html += `<a href="/wiki/${accum.replace(/\.md$/, "")}">${escapeHtml(label)}</a>`;
      }
    });
    return html;
  }

  // Wiki search
  $("#wiki-search-btn").addEventListener("click", doWikiSearch);
  $("#wiki-search-input").addEventListener("keydown", e => {
    if (e.key === "Enter") doWikiSearch();
  });

  async function doWikiSearch() {
    const input = $("#wiki-search-input");
    const q = input.value.trim();
    const resultsEl = $("#wiki-search-results");
    if (!q) {
      resultsEl.classList.add("hidden");
      return;
    }
    resultsEl.innerHTML = "Searching...";
    resultsEl.classList.remove("hidden");
    try {
      const res = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      if (!data.results || !data.results.length) {
        resultsEl.innerHTML = "<p class='muted'>No results found.</p>";
        return;
      }
      resultsEl.innerHTML = `<div class="search-list">${data.results.map(r => `
        <a href="/wiki/${r.path.replace(/\.md$/, "")}" class="search-item">
          <div class="search-title">${escapeHtml(r.title)}</div>
          <div class="search-snippet">${escapeHtml(r.snippet)}</div>
        </a>
      `).join("")}</div>`;
    } catch (err) {
      resultsEl.innerHTML = "<p class='error'>Search failed.</p>";
    }
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // Init
  route();
})();
