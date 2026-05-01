const PACKAGE_VERSION = "__PACKAGE_VERSION__";
const DOWNLOAD_BASE_URL = `https://assets.doloclaw.com/omnimemora/beta/${PACKAGE_VERSION}`;
const SUPPORT_EMAIL = "__SUPPORT_EMAIL__";
const CANDIDATE_POINTER_SCHEMA = "omnimemora-cloud-candidate-pointer-v1";
const PROMPT_OS_URL = "https://prompt.doloclaw.com/";
const PROMO_VIDEO_FILENAME = "omnimemora-promo-guide.mp4";
const DOWNLOAD_FILES = {
  "darwin-arm64": "omnimemora-darwin-arm64.zip",
  "darwin-amd64": "omnimemora-darwin-amd64.zip",
  "windows-amd64": "omnimemora-windows-amd64.zip",
  "sha256sums": "SHA256SUMS.txt",
  "release-index": "RELEASE_INDEX.txt",
  "latest-manifest": "latest.json",
  "version-manifest": `${PACKAGE_VERSION}.json`
};
const MEDIA_FILES = {
  "omnimemora-promo-guide.mp4": PROMO_VIDEO_FILENAME,
  "omnimemora-promo-guide-poster.png": "omnimemora-promo-guide-poster.png"
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

function htmlResponse(html, init = {}) {
  return new Response(html, {
    status: init.status || 200,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      ...(init.headers || {})
    }
  });
}

function rootResponse(url) {
  const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Dolo Claw Products</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f1e7;
      --panel: #fffdf7;
      --ink: #15120d;
      --muted: #62594c;
      --line: #d8cfbf;
      --green: #1d6f63;
      --copper: #b85c38;
      --slate: #28323a;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(135deg, rgba(29, 111, 99, 0.11), transparent 38%),
        radial-gradient(circle at 80% 10%, rgba(184, 92, 56, 0.14), transparent 28%),
        var(--bg);
      color: var(--ink);
      font: 16px/1.6 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      width: min(1120px, calc(100% - 40px));
      margin: 0 auto;
      padding: 56px 0;
    }
    .hero {
      display: grid;
      gap: 18px;
      margin-bottom: 34px;
    }
    .kicker {
      width: max-content;
      padding: 7px 11px;
      border: 1px solid rgba(29, 111, 99, 0.35);
      color: var(--green);
      background: rgba(255, 253, 247, 0.7);
      font: 700 12px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    h1 {
      max-width: 860px;
      margin: 0;
      font-size: clamp(42px, 7vw, 82px);
      line-height: 0.98;
      letter-spacing: 0;
    }
    .hero p {
      max-width: 760px;
      margin: 0;
      color: var(--muted);
      font-size: 19px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }
    .product {
      display: flex;
      min-height: 360px;
      flex-direction: column;
      justify-content: space-between;
      padding: 28px;
      border: 1px solid var(--line);
      background: rgba(255, 253, 247, 0.86);
      box-shadow: 0 20px 58px rgba(21, 18, 13, 0.09);
    }
    .product h2 {
      margin: 14px 0 12px;
      font-size: 34px;
      line-height: 1.08;
    }
    .product p {
      margin: 0;
      color: var(--muted);
    }
    .tag {
      width: max-content;
      color: var(--slate);
      font: 700 13px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
      text-transform: uppercase;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 28px;
    }
    a.button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 44px;
      padding: 11px 15px;
      border: 1px solid var(--line);
      background: var(--ink);
      color: var(--panel);
      text-decoration: none;
      font-weight: 800;
    }
    a.button.secondary {
      background: transparent;
      color: var(--green);
      border-color: rgba(29, 111, 99, 0.35);
    }
    .omni { border-top: 7px solid var(--green); }
    .prompt { border-top: 7px solid var(--copper); }
    .footer {
      margin-top: 22px;
      color: rgba(21, 18, 13, 0.58);
      font: 600 13px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    @media (max-width: 760px) {
      main { padding: 34px 0; }
      .grid { grid-template-columns: 1fr; }
      .product { min-height: 300px; }
    }
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <span class="kicker">Dolo Claw Product Entry</span>
      <h1>两个产品，一个入口。</h1>
      <p>Prompt_OS 用来校准图像和视频生成提示词；OmniMemora 用本地控制面和网关路径，让真实请求更省 token、更可控。</p>
    </section>
    <section class="grid" aria-label="Dolo Claw products">
      <article class="product prompt">
        <div>
          <div class="tag">Prompt_OS</div>
          <h2>图像 / 视频 Prompt 校准工作台</h2>
          <p>把自然语言输入整理成更稳定的生成提示词，面向图片、视频和多参考素材场景。</p>
        </div>
        <div class="actions">
          <a class="button" href="${PROMPT_OS_URL}">进入 Prompt_OS</a>
        </div>
      </article>
      <article class="product omni">
        <div>
          <div class="tag">OmniMemora</div>
          <h2>本地优先的 LLM 请求控制入口</h2>
          <p>用户显式开启后，经由本地网关执行 recall、compress、inject，并保持原有上游模型语义。</p>
        </div>
        <div class="actions">
          <a class="button" href="/download">下载 OmniMemora</a>
          <a class="button secondary" href="/health">查看健康状态</a>
        </div>
      </article>
    </section>
    <div class="footer">Host: ${url.hostname} · OmniMemora ${PACKAGE_VERSION} · support: ${SUPPORT_EMAIL}</div>
  </main>
</body>
</html>`;
  return htmlResponse(html);
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

function mediaRedirectResponse(url) {
  const parts = url.pathname.split("/").filter(Boolean);
  const key = parts[1] || "";
  const filename = MEDIA_FILES[key];
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
      --copper: #b85c38;
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
    .video-wrap {
      margin: 22px 0 24px;
      overflow: hidden;
      border: 1px solid var(--line);
      background: #15120d;
    }
    video {
      display: block;
      width: 100%;
      aspect-ratio: 16 / 9;
      background: #15120d;
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
      <div class="video-wrap">
        <video controls preload="metadata" poster="/media/omnimemora-promo-guide-poster.png">
          <source src="/media/omnimemora-promo-guide.mp4" type="video/mp4" />
          Your browser does not support the video tag.
        </video>
      </div>

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
  if (url.pathname.startsWith("/media/")) {
    event.respondWith(mediaRedirectResponse(url));
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
