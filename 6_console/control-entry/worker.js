const PACKAGE_VERSION = "__PACKAGE_VERSION__";
const DOWNLOAD_BASE_URL = `https://assets.doloclaw.com/omnimemora/beta/${PACKAGE_VERSION}`;
const SUPPORT_EMAIL = "__SUPPORT_EMAIL__";
const CANDIDATE_POINTER_SCHEMA = "omnimemora-cloud-candidate-pointer-v1";
const DOWNLOAD_FILES = {
  "darwin-arm64": "omnimemora-darwin-arm64.zip",
  "darwin-amd64": "omnimemora-darwin-amd64.zip",
  "windows-amd64": "omnimemora-windows-amd64.zip",
  "sha256sums": "SHA256SUMS.txt",
  "release-index": "RELEASE_INDEX.txt",
  "latest-manifest": "latest.json",
  "version-manifest": `${PACKAGE_VERSION}.json`
};

function json(payload, init = {}) {
  return new Response(JSON.stringify(payload), {
    status: init.status || 200,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      ...(init.headers || {})
    }
  });
}

function rootResponse(url) {
  return json({
      service: "omnimemora-control-entry",
      role: "control-plane-entry",
      host: url.hostname,
      path: url.pathname,
      message: "OmniMemora control entry is active."
  });
}

function healthResponse(url) {
  return json({
    status: "healthy",
    service: "omnimemora-control-entry",
    role: "control-plane-entry",
    host: url.hostname,
    product: "omnimemora",
    release_posture: "proprietary-controlled-beta",
    capabilities: {
      download_entry: true,
      candidate_pointer_reserved: true,
      candidate_auto_promote: false,
      cloud_compile: false
    }
  });
}

function candidatePointerResponse(url) {
  return json({
    schema_version: CANDIDATE_POINTER_SCHEMA,
    status: "not_configured",
    candidate: null,
    source: "cloudflare-control-entry",
    product: "omnimemora",
    host: url.hostname,
    message: "Cloud candidate pointer endpoint is reserved. Local active policy remains authoritative."
  });
}

function notFoundResponse(url) {
  return json(
    {
      error: "not_found",
      service: "omnimemora-control-entry",
      path: url.pathname
    },
    { status: 404 }
  );
}

function downloadRedirectResponse(url) {
  const parts = url.pathname.split("/").filter(Boolean);
  const key = parts[2] || "";
  const filename = DOWNLOAD_FILES[key];
  if (!filename) {
    return notFoundResponse(url);
  }
  return Response.redirect(`${DOWNLOAD_BASE_URL}/${filename}`, 302);
}

function releaseManifestResponse(url) {
  const parts = url.pathname.split("/").filter(Boolean);
  const name = parts[1] || "";
  if (name === "latest.json") {
    return Response.redirect(`${DOWNLOAD_BASE_URL}/latest.json`, 302);
  }
  if (name === `${PACKAGE_VERSION}.json`) {
    return Response.redirect(`${DOWNLOAD_BASE_URL}/${PACKAGE_VERSION}.json`, 302);
  }
  return notFoundResponse(url);
}

function downloadHtml() {
  const downloads = [
    {
      label: "macOS (Apple Silicon)",
      href: `/download/file/darwin-arm64`
    },
    {
      label: "macOS (Intel)",
      href: `/download/file/darwin-amd64`
    },
    {
      label: "Windows (x64)",
      href: `/download/file/windows-amd64`
    }
  ];

  const list = downloads
    .map(
      (item) =>
        `<li><a href="${item.href}">${item.label}</a></li>`
    )
    .join("");

  const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>OmniMemora Desktop Beta Installer</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f1e8;
      --panel: #fffdf7;
      --ink: #17130d;
      --muted: #60574a;
      --line: #d8cfbf;
      --accent: #1d6f63;
    }
    body {
      margin: 0;
      background: radial-gradient(circle at top left, #fff6d8 0, var(--bg) 35%, #ece6da 100%);
      color: var(--ink);
      font: 16px/1.6 Georgia, "Iowan Old Style", serif;
    }
    main {
      max-width: 860px;
      margin: 48px auto;
      padding: 0 20px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 28px;
      box-shadow: 0 12px 50px rgba(23, 19, 13, 0.08);
    }
    h1, h2 {
      margin: 0 0 12px;
      line-height: 1.2;
    }
    h1 { font-size: 40px; }
    h2 { font-size: 20px; margin-top: 28px; }
    p, li { color: var(--muted); }
    ul { padding-left: 20px; }
    .badge {
      display: inline-block;
      margin-bottom: 16px;
      padding: 6px 10px;
      border-radius: 999px;
      background: #e4f3ef;
      color: var(--accent);
      font: 600 12px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    .downloads a, .meta a {
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 18px;
    }
    .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 14px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #f5fbf9;
      color: var(--accent);
      text-decoration: none;
      font: 600 13px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    .meta {
      display: grid;
      gap: 8px;
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--line);
    }
    code {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.92em;
      color: var(--ink);
    }
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <span class="badge">Desktop Beta</span>
      <h1>OmniMemora Desktop Beta Installer</h1>
      <p>Closed beta installer package. Source code is not included. Copyright is reserved. Commercial use and redistribution are prohibited.</p>

      <h2>Package Version</h2>
      <p><code>${PACKAGE_VERSION}</code></p>

      <h2>Supported Platforms</h2>
      <ul class="downloads">${list}</ul>
      <p><a href="/download/file/sha256sums">Download SHA256SUMS.txt</a></p>
      <p><a href="/releases/latest.json">View latest release manifest</a></p>

      <h2>Install Steps</h2>
      <ul>
        <li>Download the installer for your platform.</li>
        <li>Open OmniMemora from the desktop app.</li>
        <li>Use the app status screen for startup, repair, update, and feedback.</li>
      </ul>

      <h2>Known Limits</h2>
      <ul>
        <li>This is a controlled beta installer, not a public production release.</li>
        <li>Desktop-shell replacement is manual in this version; local component updates are manifest-based.</li>
        <li>Cloud policy candidates are visible but are not auto-promoted over local active policy.</li>
        <li>Feedback should include version, system, <code>request_id</code>, <code>error_code</code>, and reproduction steps.</li>
      </ul>

      <div class="actions">
        <a class="button" id="report-link" href="mailto:${SUPPORT_EMAIL}?subject=OmniMemora%20Beta%20Feedback">Report an Issue</a>
      </div>

      <div class="meta">
        <div>Feedback: <a href="mailto:${SUPPORT_EMAIL}?subject=OmniMemora%20Beta%20Feedback">${SUPPORT_EMAIL}</a></div>
        <div>License: all rights reserved, beta only, no redistribution, no commercial use.</div>
      </div>
    </section>
  </main>
  <script>
    const reportLink = document.getElementById("report-link");
    if (reportLink) {
      const platform = navigator.userAgent || "unknown";
      const subject = encodeURIComponent("OmniMemora Beta Feedback");
      const body = encodeURIComponent(
        [
          "version: ${PACKAGE_VERSION}",
          "platform: " + platform,
          "request_id: ",
          "error_code: ",
          "steps:",
          "- ",
        ].join("\\n")
      );
      reportLink.setAttribute("href", "mailto:${SUPPORT_EMAIL}?subject=" + subject + "&body=" + body);
    }
  </script>
</body>
</html>`;

  return new Response(html, {
    status: 200,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store"
    }
  });
}

addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname === "/" || url.pathname === "") {
    event.respondWith(rootResponse(url));
    return;
  }
  if (url.pathname === "/health") {
    event.respondWith(healthResponse(url));
    return;
  }
  if (url.pathname === "/download") {
    event.respondWith(downloadHtml());
    return;
  }
  if (url.pathname.startsWith("/download/file/")) {
    event.respondWith(downloadRedirectResponse(url));
    return;
  }
  if (url.pathname.startsWith("/releases/")) {
    event.respondWith(releaseManifestResponse(url));
    return;
  }
  if (
    url.pathname === "/api/control/recommendation/candidates/latest" ||
    url.pathname === "/api/policy/candidates/latest"
  ) {
    event.respondWith(candidatePointerResponse(url));
    return;
  }
  event.respondWith(notFoundResponse(url));
});
