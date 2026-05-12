const DEFAULT_BASE_URL = "http://127.0.0.1:18011";
const DEFAULT_TIMEOUT_SECONDS = 12;
const DEFAULT_MAX_CHARS = 6000;

const searchParameters = {
  type: "object",
  properties: {
    query: {
      type: "string",
      description: "Search query string."
    },
    count: {
      type: "number",
      description: "Number of results to return.",
      minimum: 1,
      maximum: 10
    }
  },
  additionalProperties: false
};

function readString(value, fallback) {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function readNumber(value, fallback, min, max) {
  const parsed = typeof value === "number" && Number.isFinite(value) ? value : fallback;
  return Math.max(min, Math.min(max, parsed));
}

function pluginConfig(ctx) {
  const entry = ctx?.config?.plugins?.entries?.["omnimemora-tool-plane"]?.config;
  return entry && typeof entry === "object" && !Array.isArray(entry) ? entry : {};
}

function webSearchConfig(ctx) {
  const cfg = pluginConfig(ctx).webSearch;
  return cfg && typeof cfg === "object" && !Array.isArray(cfg) ? cfg : {};
}

function normalizeBaseUrl(value) {
  return readString(value, DEFAULT_BASE_URL).replace(/\/+$/, "");
}

async function fetchWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal
    });
  } finally {
    clearTimeout(timer);
  }
}

function compactText(value, maxChars) {
  const text = typeof value === "string" ? value : JSON.stringify(value ?? "");
  if (text.length <= maxChars) {
    return text;
  }
  return `${text.slice(0, Math.max(0, maxChars - 32))}\n[omnimemora_truncated]`;
}

function parseOmniContent(content) {
  if (typeof content !== "string" || !content.trim()) {
    return {};
  }
  try {
    return JSON.parse(content);
  } catch {
    return { text: content };
  }
}

function siteName(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return undefined;
  }
}

function normalizeResults(payload, count) {
  const organic = Array.isArray(payload.organic)
    ? payload.organic
    : Array.isArray(payload.results)
      ? payload.results
      : [];
  return organic.slice(0, count).map((entry) => {
    const url = entry.link || entry.url || "";
    return {
      title: entry.title || "",
      url,
      description: entry.snippet || entry.description || entry.content || "",
      published: entry.date || entry.published || undefined,
      siteName: siteName(url)
    };
  });
}

async function executeOmniSearch(ctx, args) {
  const cfg = webSearchConfig(ctx);
  const query = readString(args?.query, "");
  if (!query) {
    return { error: "empty_query", message: "web_search requires a non-empty query." };
  }
  const count = Math.floor(readNumber(args?.count, 5, 1, 10));
  const timeoutSeconds = readNumber(cfg.timeoutSeconds, DEFAULT_TIMEOUT_SECONDS, 1, 30);
  const maxChars = Math.floor(readNumber(cfg.maxChars, DEFAULT_MAX_CHARS, 512, 20000));
  const baseUrl = normalizeBaseUrl(cfg.baseUrl);
  const started = Date.now();

  const response = await fetchWithTimeout(
    `${baseUrl}/tools/search`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        query,
        provider: "mmx",
        max_chars: maxChars,
        timeout_seconds: timeoutSeconds,
        agent_id: "openclaw",
        trace_id: "openclaw-web-search"
      })
    },
    Math.ceil((timeoutSeconds + 1) * 1000)
  );

  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { content: text };
  }
  if (!response.ok) {
    return {
      error: "omnimemora_tool_search_failed",
      status: response.status,
      message: compactText(data?.detail || data, 1000)
    };
  }

  const payload = parseOmniContent(data.content);
  const results = normalizeResults(payload, count);
  if (results.length === 0 && payload.text) {
    results.push({
      title: "OmniMemora search result",
      url: "",
      description: compactText(payload.text, maxChars)
    });
  }
  return {
    query,
    provider: "omnimemora",
    upstreamProvider: data.provider || "unknown",
    count: results.length,
    tookMs: Date.now() - started,
    externalContent: {
      untrusted: true,
      source: "web_search",
      provider: "omnimemora",
      wrapped: true
    },
    results
  };
}

export function createOmniMemoraWebSearchProvider() {
  return {
    id: "omnimemora",
    label: "OmniMemora Search",
    hint: "Routes web_search through local OmniMemora Tool Plane",
    requiresCredential: false,
    envVars: [],
    placeholder: "(uses local OmniMemora)",
    docsUrl: "http://127.0.0.1:18011/health",
    autoDetectOrder: 1,
    credentialPath: "",
    createTool: (ctx) => ({
      description: "Search the web through OmniMemora local Tool Plane. Returns capped structured results.",
      parameters: searchParameters,
      execute: async (args) => executeOmniSearch(ctx, args)
    })
  };
}

export default {
  id: "omnimemora-tool-plane",
  name: "OmniMemora Tool Plane",
  description: "OpenClaw web_search provider routed through OmniMemora local product ingress",
  register(api) {
    api.registerWebSearchProvider(createOmniMemoraWebSearchProvider());
  }
};
