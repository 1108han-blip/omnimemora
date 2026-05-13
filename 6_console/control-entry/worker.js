const PACKAGE_VERSION = "__PACKAGE_VERSION__";
const DOWNLOAD_BASE_URL = `https://assets.doloclaw.com/omnimemora/beta/${PACKAGE_VERSION}`;
const SUPPORT_EMAIL = "__SUPPORT_EMAIL__";
const CANDIDATE_POINTER_SCHEMA = "omnimemora-cloud-candidate-pointer-v1";
const PROMPT_OS_URL = "https://prompt.doloclaw.com/";
const PROMO_VIDEO_FILENAME = "omnimemora-promo-guide.mp4";
const TOKEN_INTELLIGENCE_VERSION = "0.1.0-beta.1";
const TOKEN_INTELLIGENCE_BASE_URL = `https://assets.doloclaw.com/omnimemora/token-intelligence/${TOKEN_INTELLIGENCE_VERSION}`;
const TOKEN_INTELLIGENCE_PACKAGE = `omni-token-audit-${TOKEN_INTELLIGENCE_VERSION}-local.zip`;
const DOWNLOAD_FILES = {
  "darwin-arm64": `OmniMemora-Desktop-${PACKAGE_VERSION}-darwin-arm64.dmg`,
  "darwin-arm64-components": "omnimemora-darwin-arm64.zip",
  "darwin-amd64": "omnimemora-darwin-amd64.zip",
  "darwin-amd64-components": "omnimemora-darwin-amd64.zip",
  "windows-amd64": "omnimemora-windows-amd64.zip",
  "windows-amd64-components": "omnimemora-windows-amd64.zip",
  "sha256sums": "SHA256SUMS.txt",
  "release-index": "RELEASE_INDEX.txt",
  "latest-manifest": "latest.json",
  "version-manifest": `${PACKAGE_VERSION}.json`
};
const TOKEN_INTELLIGENCE_FILES = {
  [TOKEN_INTELLIGENCE_PACKAGE]: TOKEN_INTELLIGENCE_PACKAGE,
  "sha256sums": "SHA256SUMS.txt",
  "latest-manifest": "latest.json",
  "version-manifest": `${TOKEN_INTELLIGENCE_VERSION}.json`
};
const MEDIA_FILES = {
  "omnimemora-promo-guide.mp4": PROMO_VIDEO_FILENAME,
  "omnimemora-promo-guide-poster.png": "omnimemora-promo-guide-poster.png"
};
const DOWNLOAD_EVENT_PREFIX = "download:v1:";
const DOWNLOAD_EVENT_RETENTION_SECONDS = 60 * 60 * 24 * 7;

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

function downloadStatsStore() {
  return typeof DOWNLOAD_STATS === "undefined" ? null : DOWNLOAD_STATS;
}

function classifyClient(userAgent) {
  const value = String(userAgent || "").toLowerCase();
  if (!value) return "unknown";
  if (value.includes("bot") || value.includes("spider") || value.includes("crawler")) return "bot";
  if (value.includes("curl") || value.includes("wget") || value.includes("python") || value.includes("httpie")) return "automation";
  if (value.includes("mozilla") || value.includes("safari") || value.includes("chrome") || value.includes("firefox")) return "browser";
  return "unknown";
}

function trackDownloadAttempt(event, url, key, filename) {
  const store = downloadStatsStore();
  if (!store) return;
  const now = new Date();
  const date = now.toISOString().slice(0, 10);
  const id = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const userAgent = event.request.headers.get("user-agent") || "";
  const payload = {
    schema_version: "omnimemora-download-event-v1",
    timestamp: now.toISOString(),
    date,
    product: "omnimemora",
    version: PACKAGE_VERSION,
    file_key: key,
    filename,
    path: url.pathname,
    client_type: classifyClient(userAgent),
    country: event.request.cf?.country || "unknown"
  };
  const eventKey = `${DOWNLOAD_EVENT_PREFIX}${date}:${key}:${id}`;
  event.waitUntil(
    store.put(eventKey, JSON.stringify(payload), {
      expirationTtl: DOWNLOAD_EVENT_RETENTION_SECONDS
    }).catch(() => undefined)
  );
}

function trackTokenIntelligenceDownloadAttempt(event, url, key, filename) {
  trackDownloadAttempt(event, url, `token-intelligence/${key}`, filename);
}

function emptyStats(days) {
  return {
    schema_version: "omnimemora-download-stats-v1",
    source: "worker-kv-download-attempts",
    generated_at: new Date().toISOString(),
    window_days: days,
    retention_days: Math.floor(DOWNLOAD_EVENT_RETENTION_SECONDS / 86400),
    total_attempts: 0,
    product_file_attempts: 0,
    desktop_installer_attempts: 0,
    browser_like_attempts: 0,
    automation_or_bot_attempts: 0,
    by_file: {},
    by_version: {},
    by_day: {},
    note: "Counts download redirect attempts at /download/file/...; this does not prove the redirected R2 file was fully downloaded."
  };
}

function addStat(bucket, key, amount = 1) {
  bucket[key] = (bucket[key] || 0) + amount;
}

async function downloadStatsResponse(url) {
  const store = downloadStatsStore();
  if (!store) {
    return json(
      {
        schema_version: "omnimemora-download-stats-v1",
        status: "not_configured",
        message: "DOWNLOAD_STATS KV binding is not configured."
      },
      { status: 503 }
    );
  }

  const requestedDays = Number(url.searchParams.get("days") || "7");
  const days = Number.isFinite(requestedDays) ? Math.min(30, Math.max(1, Math.floor(requestedDays))) : 7;
  const since = new Date(Date.now() - days * 86400 * 1000);
  const stats = emptyStats(days);
  let cursor;
  do {
    const page = await store.list({ prefix: DOWNLOAD_EVENT_PREFIX, cursor });
    for (const item of page.keys) {
      const raw = await store.get(item.name);
      if (!raw) continue;
      let event;
      try {
        event = JSON.parse(raw);
      } catch {
        continue;
      }
      const timestamp = new Date(event.timestamp);
      if (!Number.isFinite(timestamp.getTime()) || timestamp < since) continue;
      stats.total_attempts += 1;
      if (event.file_key !== "sha256sums" && event.file_key !== "release-index" && event.file_key !== "latest-manifest" && event.file_key !== "version-manifest") {
        stats.product_file_attempts += 1;
      }
      if (event.file_key === "darwin-arm64") {
        stats.desktop_installer_attempts += 1;
      }
      if (event.client_type === "browser") {
        stats.browser_like_attempts += 1;
      }
      if (event.client_type === "automation" || event.client_type === "bot") {
        stats.automation_or_bot_attempts += 1;
      }
      addStat(stats.by_file, event.file_key || "unknown");
      addStat(stats.by_version, event.version || "unknown");
      addStat(stats.by_day, event.date || timestamp.toISOString().slice(0, 10));
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return json(stats);
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

function faviconResponse() {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="16" fill="#f7f2e8"/>
  <circle cx="32" cy="32" r="19" fill="#0f6258"/>
  <circle cx="32" cy="32" r="9" fill="#f7f2e8"/>
  <path d="M17 45 45 17" stroke="#b95d31" stroke-width="6" stroke-linecap="round"/>
</svg>`;
  return new Response(svg, {
    status: 200,
    headers: {
      "content-type": "image/svg+xml; charset=utf-8",
      "cache-control": "public, max-age=86400"
    }
  });
}

function rootResponse(url) {
  const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Dolo Claw | Product Entry</title>
  <link rel="icon" href="/favicon.ico" type="image/svg+xml" />
  <style>
    :root {
      color-scheme: light;
      --paper: #f7f2e8;
      --surface: #fffaf0;
      --surface-strong: #ffffff;
      --ink: #151711;
      --soft-ink: #4e554b;
      --muted: #767263;
      --line: rgba(21, 23, 17, 0.13);
      --line-strong: rgba(21, 23, 17, 0.22);
      --forest: #0f6258;
      --forest-ink: #073b35;
      --copper: #b95d31;
      --blue: #2f5b83;
      --sand: #e9dcc7;
      --shadow: 0 26px 90px rgba(38, 35, 26, 0.15);
      --radius-xl: 34px;
      --radius-lg: 24px;
      --radius-md: 16px;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 8% 12%, rgba(15, 98, 88, 0.16), transparent 29rem),
        radial-gradient(circle at 86% 4%, rgba(185, 93, 49, 0.16), transparent 25rem),
        linear-gradient(135deg, rgba(47, 91, 131, 0.10), transparent 45%),
        var(--paper);
      color: var(--ink);
      font: 16px/1.55 Charter, "Iowan Old Style", "Palatino Linotype", Georgia, serif;
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
    }
    body::before {
      position: fixed;
      inset: 0;
      z-index: -1;
      pointer-events: none;
      content: "";
      background-image:
        linear-gradient(rgba(21, 23, 17, 0.045) 1px, transparent 1px),
        linear-gradient(90deg, rgba(21, 23, 17, 0.045) 1px, transparent 1px);
      background-size: 42px 42px;
      mask-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.62), transparent 82%);
    }
    a { color: inherit; }
    main {
      width: min(1180px, calc(100% - 40px));
      margin: 0 auto;
      padding: 22px 0 42px;
    }
    .nav {
      position: sticky;
      top: 14px;
      z-index: 5;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 46px;
      padding: 12px 14px 12px 18px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 250, 240, 0.78);
      box-shadow: 0 12px 42px rgba(38, 35, 26, 0.09);
      backdrop-filter: blur(18px);
    }
    .brand {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      min-width: max-content;
      color: var(--forest-ink);
      font: 800 13px/1.1 Optima, Candara, "Gill Sans", sans-serif;
      letter-spacing: 0.15em;
      text-transform: uppercase;
    }
    .mark {
      width: 34px;
      height: 34px;
      border: 1px solid rgba(15, 98, 88, 0.35);
      border-radius: 50%;
      background:
        linear-gradient(135deg, rgba(15, 98, 88, 0.90), rgba(47, 91, 131, 0.85)),
        var(--forest);
      box-shadow: inset 0 0 0 7px rgba(255, 250, 240, 0.82);
    }
    .navlinks {
      display: flex;
      align-items: center;
      gap: 6px;
      font: 800 13px/1 Optima, Candara, "Gill Sans", sans-serif;
    }
    .navlinks a {
      display: inline-flex;
      min-height: 38px;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      padding: 0 14px;
      color: var(--soft-ink);
      text-decoration: none;
      transition: background 160ms ease, color 160ms ease, transform 160ms ease;
    }
    .navlinks a:hover {
      background: rgba(15, 98, 88, 0.09);
      color: var(--forest-ink);
      transform: translateY(-1px);
    }
    .shell {
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(300px, 0.95fr);
      gap: 24px;
      align-items: stretch;
    }
    .hero {
      position: relative;
      min-height: 610px;
      overflow: hidden;
      padding: clamp(30px, 5vw, 58px);
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      background:
        linear-gradient(145deg, rgba(255, 255, 255, 0.56), rgba(255, 250, 240, 0.72) 46%, rgba(233, 220, 199, 0.88)),
        var(--surface);
      box-shadow: var(--shadow);
    }
    .hero::after {
      position: absolute;
      right: -160px;
      bottom: -210px;
      width: 420px;
      height: 420px;
      border-radius: 50%;
      content: "";
      background:
        radial-gradient(circle, rgba(15, 98, 88, 0.18), transparent 63%),
        conic-gradient(from 120deg, rgba(15, 98, 88, 0.16), rgba(185, 93, 49, 0.14), rgba(47, 91, 131, 0.13), rgba(15, 98, 88, 0.16));
      filter: blur(2px);
    }
    .kicker {
      position: relative;
      z-index: 1;
      display: inline-flex;
      width: fit-content;
      align-items: center;
      gap: 10px;
      padding: 9px 12px;
      border: 1px solid rgba(15, 98, 88, 0.24);
      border-radius: 999px;
      color: var(--forest-ink);
      background: rgba(255, 255, 255, 0.56);
      font: 800 12px/1.2 Optima, Candara, "Gill Sans", sans-serif;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    .kicker::before {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      content: "";
      background: var(--forest);
      box-shadow: 0 0 0 5px rgba(15, 98, 88, 0.11);
    }
    h1 {
      position: relative;
      z-index: 1;
      max-width: 860px;
      margin: 30px 0 0;
      font-size: clamp(54px, 8vw, 116px);
      line-height: 0.88;
      letter-spacing: -0.07em;
      font-weight: 760;
    }
    .hero .lead {
      position: relative;
      z-index: 1;
      max-width: 640px;
      margin: 30px 0 0;
      color: var(--soft-ink);
      font-size: clamp(18px, 2vw, 23px);
      line-height: 1.45;
    }
    .hero-actions {
      position: relative;
      z-index: 1;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 34px;
    }
    .proof-strip {
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-top: 54px;
    }
    .proof {
      min-height: 112px;
      padding: 18px;
      border: 1px solid rgba(21, 23, 17, 0.10);
      border-radius: 22px;
      background: rgba(255, 255, 255, 0.47);
    }
    .proof strong {
      display: block;
      font: 900 25px/1 Optima, Candara, "Gill Sans", sans-serif;
      letter-spacing: -0.02em;
    }
    .proof span {
      display: block;
      margin-top: 10px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.35;
    }
    .side {
      display: grid;
      gap: 16px;
    }
    .product {
      position: relative;
      display: flex;
      min-height: 294px;
      flex-direction: column;
      justify-content: space-between;
      overflow: hidden;
      padding: 28px;
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      background: rgba(255, 250, 240, 0.86);
      box-shadow: 0 18px 52px rgba(38, 35, 26, 0.10);
      transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
    }
    .product:hover {
      transform: translateY(-3px);
      border-color: var(--line-strong);
      box-shadow: 0 28px 70px rgba(38, 35, 26, 0.14);
    }
    .product::before {
      position: absolute;
      top: 0;
      right: 0;
      left: 0;
      height: 7px;
      content: "";
      background: linear-gradient(90deg, var(--accent), rgba(255, 255, 255, 0));
    }
    .prompt { --accent: var(--copper); }
    .omni { --accent: var(--forest); }
    .product-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
    }
    .product h2 {
      margin: 16px 0 12px;
      font-size: clamp(27px, 3vw, 39px);
      line-height: 1;
      letter-spacing: -0.04em;
    }
    .product p {
      margin: 0;
      color: var(--soft-ink);
      font-size: 16px;
    }
    .tag {
      width: fit-content;
      color: var(--accent);
      font: 900 12px/1 Optima, Candara, "Gill Sans", sans-serif;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }
    .status {
      min-width: max-content;
      padding: 7px 10px;
      border: 1px solid rgba(21, 23, 17, 0.11);
      border-radius: 999px;
      color: var(--soft-ink);
      background: rgba(255, 255, 255, 0.55);
      font: 800 12px/1 Optima, Candara, "Gill Sans", sans-serif;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 11px;
      margin-top: 24px;
    }
    .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 48px;
      padding: 0 18px;
      border: 1px solid rgba(21, 23, 17, 0.92);
      border-radius: 999px;
      background: var(--ink);
      color: var(--surface);
      text-decoration: none;
      font: 900 14px/1 Optima, Candara, "Gill Sans", sans-serif;
      letter-spacing: 0.01em;
      box-shadow: 0 10px 26px rgba(21, 23, 17, 0.16);
      transition: transform 160ms ease, box-shadow 160ms ease, background 160ms ease, border-color 160ms ease, color 160ms ease;
    }
    .button:hover {
      transform: translateY(-2px);
      background: var(--forest-ink);
      box-shadow: 0 16px 34px rgba(21, 23, 17, 0.18);
    }
    .button:active {
      transform: translateY(0);
      box-shadow: 0 8px 20px rgba(21, 23, 17, 0.12);
    }
    .button:focus-visible,
    .navlinks a:focus-visible {
      outline: 3px solid rgba(185, 93, 49, 0.34);
      outline-offset: 3px;
    }
    .button.secondary {
      background: rgba(255, 255, 255, 0.42);
      color: var(--forest-ink);
      border-color: rgba(15, 98, 88, 0.34);
      box-shadow: none;
    }
    .button.secondary:hover {
      background: rgba(15, 98, 88, 0.09);
      border-color: rgba(15, 98, 88, 0.58);
      color: var(--forest-ink);
      box-shadow: none;
    }
    .button.disabled,
    .button[aria-disabled="true"] {
      cursor: not-allowed;
      background: rgba(21, 23, 17, 0.07);
      border-color: rgba(21, 23, 17, 0.12);
      color: rgba(21, 23, 17, 0.42);
      box-shadow: none;
      pointer-events: none;
    }
    .operations {
      display: grid;
      grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.15fr);
      gap: 16px;
      margin-top: 24px;
    }
    .panel {
      padding: 24px;
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      background: rgba(255, 250, 240, 0.78);
      box-shadow: 0 16px 48px rgba(38, 35, 26, 0.08);
    }
    .panel h3 {
      margin: 0 0 14px;
      font-size: 24px;
      line-height: 1.05;
      letter-spacing: -0.03em;
    }
    .panel p {
      margin: 0;
      color: var(--soft-ink);
    }
    .empty {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 16px;
      align-items: start;
    }
    .empty-icon {
      display: grid;
      width: 48px;
      height: 48px;
      place-items: center;
      border: 1px dashed rgba(47, 91, 131, 0.38);
      border-radius: 16px;
      color: var(--blue);
      background: rgba(47, 91, 131, 0.08);
      font: 900 22px/1 Optima, Candara, "Gill Sans", sans-serif;
    }
    .list {
      display: grid;
      gap: 11px;
      margin: 18px 0 0;
      padding: 0;
      list-style: none;
    }
    .list li {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      padding: 12px 0;
      border-top: 1px solid rgba(21, 23, 17, 0.09);
      color: var(--soft-ink);
    }
    .list strong {
      color: var(--ink);
      font: 900 13px/1.2 Optima, Candara, "Gill Sans", sans-serif;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .footer {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 12px;
      margin-top: 24px;
      padding: 18px 4px 0;
      color: rgba(21, 23, 17, 0.56);
      font: 800 12px/1.5 Optima, Candara, "Gill Sans", sans-serif;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    @media (max-width: 980px) {
      .shell,
      .operations {
        grid-template-columns: 1fr;
      }
      .hero {
        min-height: auto;
      }
    }
    @media (max-width: 720px) {
      main {
        width: min(100% - 24px, 1180px);
        padding-top: 12px;
      }
      .nav {
        position: static;
        align-items: flex-start;
        border-radius: 24px;
      }
      .navlinks {
        width: 100%;
        justify-content: flex-end;
        flex-wrap: wrap;
      }
      .navlinks a {
        min-height: 34px;
        padding-inline: 10px;
      }
      .shell {
        gap: 14px;
      }
      .hero,
      .product,
      .panel {
        border-radius: 24px;
      }
      .hero {
        padding: 26px;
      }
      .hero-actions,
      .actions {
        flex-direction: column;
      }
      .button {
        width: 100%;
      }
      .proof-strip {
        grid-template-columns: 1fr;
        margin-top: 34px;
      }
      .empty {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main>
    <nav class="nav" aria-label="Dolo Claw product navigation">
      <a class="brand" href="/" aria-label="Dolo Claw home"><span class="mark" aria-hidden="true"></span><span>Dolo Claw</span></a>
      <div class="navlinks">
        <a href="#products">Products</a>
        <a href="/download">Download</a>
        <a href="/health">Status</a>
      </div>
    </nav>

    <section class="shell" aria-label="Dolo Claw product entry">
      <div class="hero">
        <span class="kicker">Product entry · controlled beta</span>
        <h1>AI, under control.</h1>
        <p class="lead">Prompt calibration and local-first memory control, organized as two focused product paths under one Dolo Claw entry.</p>
        <div class="hero-actions" aria-label="Primary actions">
          <a class="button" href="${PROMPT_OS_URL}">进入 Prompt_OS</a>
          <a class="button secondary" href="/download">下载 OmniMemora</a>
        </div>
        <div class="proof-strip" aria-label="Platform principles">
          <div class="proof"><strong>2</strong><span>active product entries with isolated cloud surfaces.</span></div>
          <div class="proof"><strong>5173</strong><span>OmniMemora user control and display surface.</span></div>
          <div class="proof"><strong>18011</strong><span>opt-in product ingress for token-saving requests.</span></div>
        </div>
      </div>

      <div class="side" id="products">
        <article class="product prompt">
          <div>
            <div class="product-head">
              <div class="tag">Prompt_OS</div>
              <span class="status">Live</span>
            </div>
            <h2>Prompt calibration for image and video generation.</h2>
            <p>把自然语言输入整理成更稳定的图像 / 视频生成提示词，保留创作意图，同时降低反复试错成本。</p>
          </div>
          <div class="actions">
            <a class="button" href="${PROMPT_OS_URL}">Open Prompt_OS</a>
            <a class="button secondary" href="${PROMPT_OS_URL}" aria-label="Open Prompt_OS in dedicated product site">独立产品站</a>
          </div>
        </article>

        <article class="product omni">
          <div>
            <div class="product-head">
              <div class="tag">OmniMemora</div>
              <span class="status">Beta ${PACKAGE_VERSION}</span>
            </div>
            <h2>Local-first memory control for real LLM requests.</h2>
            <p>用户显式开启后，经由本地网关执行 recall、compress、inject，目标是让真实请求省 token、省成本，并保持上游模型语义。</p>
          </div>
          <div class="actions">
            <a class="button" href="/download">Download OmniMemora</a>
            <a class="button secondary" href="/health">Health status</a>
          </div>
        </article>
      </div>
    </section>

    <section class="operations" aria-label="Operational state">
      <div class="panel">
        <h3>Clear operating boundaries.</h3>
        <p>Prompt_OS and OmniMemora share the Dolo Claw entry, but keep separate product surfaces, domains, and runtime responsibilities.</p>
        <ul class="list" aria-label="Boundary map">
          <li><strong>Prompt_OS</strong><span>prompt.doloclaw.com</span></li>
          <li><strong>OmniMemora</strong><span>download + control entry</span></li>
          <li><strong>Support</strong><span>${SUPPORT_EMAIL}</span></li>
        </ul>
      </div>

      <div class="panel empty" aria-label="Cloud candidate empty state">
        <div class="empty-icon" aria-hidden="true">Ø</div>
        <div>
          <h3>No cloud candidate is currently promoted.</h3>
          <p>Candidate promotion is intentionally empty until an operator publishes a verified cloud target. Local OmniMemora policy remains authoritative.</p>
          <div class="actions">
            <a class="button secondary" href="/candidate-pointer.json">View candidate pointer</a>
            <span class="button disabled" aria-disabled="true">Auto-promote disabled</span>
          </div>
        </div>
      </div>
    </section>

    <div class="footer">
      <span>Host: ${url.hostname}</span>
      <span>OmniMemora ${PACKAGE_VERSION}</span>
      <span>Support: ${SUPPORT_EMAIL}</span>
    </div>
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
      download_stats: Boolean(downloadStatsStore()),
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

function downloadRedirectResponse(event, url) {
  const parts = url.pathname.split("/").filter(Boolean);
  const key = parts[2] || "";
  const filename = DOWNLOAD_FILES[key];
  if (!filename) {
    return notFoundResponse(url);
  }
  trackDownloadAttempt(event, url, key, filename);
  return new Response(null, {
    status: 302,
    headers: {
      location: `${DOWNLOAD_BASE_URL}/${filename}`,
      "cache-control": "no-store"
    }
  });
}

function tokenIntelligenceDownloadRedirectResponse(event, url) {
  const parts = url.pathname.split("/").filter(Boolean);
  const key = parts[3] || "";
  const filename = TOKEN_INTELLIGENCE_FILES[key];
  if (!filename) {
    return notFoundResponse(url);
  }
  trackTokenIntelligenceDownloadAttempt(event, url, key, filename);
  return new Response(null, {
    status: 302,
    headers: {
      location: `${TOKEN_INTELLIGENCE_BASE_URL}/${filename}`,
      "cache-control": "no-store"
    }
  });
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

function tokenIntelligenceReleaseManifestResponse(url) {
  const parts = url.pathname.split("/").filter(Boolean);
  const name = parts[2] || "";
  if (name === "latest.json") {
    return Response.redirect(`${TOKEN_INTELLIGENCE_BASE_URL}/latest.json`, 302);
  }
  if (name === `${TOKEN_INTELLIGENCE_VERSION}.json`) {
    return Response.redirect(`${TOKEN_INTELLIGENCE_BASE_URL}/${TOKEN_INTELLIGENCE_VERSION}.json`, 302);
  }
  return notFoundResponse(url);
}

function desktopUpdaterResponse(url) {
  const parts = url.pathname.split("/").filter(Boolean);
  const name = parts[2] || "";
  if (!/^[a-z]+-[A-Za-z0-9_]+\.json$/.test(name)) {
    return notFoundResponse(url);
  }
  return Response.redirect(`${DOWNLOAD_BASE_URL}/desktop-updater/${name}`, 302);
}

function downloadHtml() {
  const downloads = [
    {
      label: "macOS (Apple Silicon DMG)",
      href: `/download/file/darwin-arm64`
    },
    {
      label: "macOS (Intel component zip, installer pending)",
      href: `/download/file/darwin-amd64`
    },
    {
      label: "Windows (x64 component zip, installer validation pending)",
      href: `/download/file/windows-amd64`
    },
    {
      label: "DoloToken CLI (local token audit beta)",
      href: `/download/file/token-intelligence/${TOKEN_INTELLIGENCE_PACKAGE}`
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
      <p><a href="/releases/token-intelligence/latest.json">View DoloToken release manifest</a></p>

      <h2>Install Steps</h2>
      <ul>
        <li>Download the installer for your platform.</li>
        <li>On macOS controlled beta builds, use System Settings privacy/security approval if Gatekeeper blocks first launch.</li>
        <li>Open OmniMemora from the desktop app.</li>
        <li>Use the app status screen for startup, repair, update, and feedback.</li>
      </ul>

      <h2>Known Limits</h2>
      <ul>
        <li>This is a controlled beta installer, not a public production release.</li>
        <li>macOS beta builds are ad-hoc signed and updater-signed, but not Apple Developer ID notarized; users may need to approve first launch manually.</li>
        <li>The desktop app checks the release manifest, surfaces app updates in-product, verifies signed updater artifacts, and installs app updates through Tauri updater.</li>
        <li>Cloud policy candidates are visible but are not auto-promoted over local active policy.</li>
        <li>Feedback should include version, system, <code>request_id</code>, <code>error_code</code>, and reproduction steps.</li>
      </ul>

      <div class="actions">
        <a class="button" id="report-link" href="mailto:${SUPPORT_EMAIL}?subject=OmniMemora%20Beta%20Feedback">Report an Issue</a>
      </div>

      <div class="meta">
        <div>Feedback: <a href="mailto:${SUPPORT_EMAIL}?subject=OmniMemora%20Beta%20Feedback">${SUPPORT_EMAIL}</a></div>
        <div>DoloToken: <code>${TOKEN_INTELLIGENCE_VERSION}</code>, local token audit beta, checksum required before replacement.</div>
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
  if (url.pathname === "/favicon.ico") {
    event.respondWith(faviconResponse());
    return;
  }
  if (url.pathname === "/download") {
    event.respondWith(downloadHtml());
    return;
  }
  if (url.pathname.startsWith("/download/file/token-intelligence/")) {
    event.respondWith(tokenIntelligenceDownloadRedirectResponse(event, url));
    return;
  }
  if (url.pathname.startsWith("/download/file/")) {
    event.respondWith(downloadRedirectResponse(event, url));
    return;
  }
  if (url.pathname === "/api/download/stats") {
    event.respondWith(downloadStatsResponse(url));
    return;
  }
  if (url.pathname.startsWith("/media/")) {
    event.respondWith(mediaRedirectResponse(url));
    return;
  }
  if (url.pathname.startsWith("/releases/desktop-updater/")) {
    event.respondWith(desktopUpdaterResponse(url));
    return;
  }
  if (url.pathname.startsWith("/releases/token-intelligence/")) {
    event.respondWith(tokenIntelligenceReleaseManifestResponse(url));
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
