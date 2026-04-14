interface Env {
  LEADS_DB: D1Database;
  ADAPTER_API_URL?: string;
  INTERNAL_ADAPTER_TOKEN?: string;
}

interface MemoryWriteRequest {
  text?: string;
  content?: string;
  type?: string;
  tags?: string[];
  metadata?: Record<string, unknown>;
  agent?: string;
}

const json = (body: unknown, init?: ResponseInit) =>
  new Response(JSON.stringify(body, null, 2), {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "Access-Control-Allow-Origin": "*",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

function normalize(value: string | undefined, max: number) {
  return (value ?? "").trim().slice(0, max);
}

async function sha256Hex(value: string) {
  const encoded = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest))
    .map((part) => part.toString(16).padStart(2, "0"))
    .join("");
}

export const onRequest: PagesFunction<Env> = async ({ request, env }) => {
  // ---- CORS preflight ----
  if (request.method === "OPTIONS") {
    return new Response(null, {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Max-Age": "86400",
      },
    });
  }

  if (request.method !== "POST") {
    return json({ ok: false, error: "Method Not Allowed." }, { status: 405 });
  }

  // ---- Extract Bearer token ----
  const authHeader = normalize(request.headers.get("Authorization"), 256);
  const rawApiKey = authHeader.startsWith("Bearer ")
    ? authHeader.slice(7)
    : authHeader;

  if (!rawApiKey) {
    return json({ ok: false, error: "Authorization header with API key is required." }, { status: 401 });
  }

  // ---- Hash and look up API key in D1 ----
  let apiKeyHash: string;
  try {
    apiKeyHash = await sha256Hex(rawApiKey);
  } catch {
    return json({ ok: false, error: "Failed to hash API key." }, { status: 500 });
  }

  let tenantRow: Record<string, unknown> | null = null;
  try {
    const result = await env.LEADS_DB.prepare(
      `SELECT tenant_id, display_name, plan, status, token_id, created_at, updated_at
       FROM tenant_registry
       WHERE api_key_hash = ?`,
    ).bind(apiKeyHash).first();
    tenantRow = result ?? null;
  } catch (error) {
    return json(
      { ok: false, error: error instanceof Error ? error.message : "Database lookup failed." },
      { status: 500 },
    );
  }

  if (!tenantRow) {
    return json({ ok: false, error: "Invalid API key." }, { status: 401 });
  }

  const tenantStatus = String(tenantRow["status"] ?? "").toLowerCase();
  if (tenantStatus !== "active") {
    return json({ ok: false, error: "Tenant account is disabled.", tenantId: tenantRow["tenant_id"] }, { status: 403 });
  }

  const tenantId = String(tenantRow["tenant_id"] ?? "");

  // ---- Parse request body ----
  let payload: MemoryWriteRequest;
  try {
    payload = (await request.json()) as MemoryWriteRequest;
  } catch {
    return json({ ok: false, error: "Invalid JSON body." }, { status: 400 });
  }

  const content = normalize(payload.text ?? payload.content, 100000);
  if (!content) {
    return json({ ok: false, error: "text or content field is required." }, { status: 400 });
  }

  // ---- Proxy to Railway adapter ----
  const adapterUrl = normalize(env.ADAPTER_API_URL, 512);
  const internalToken = normalize(env.INTERNAL_ADAPTER_TOKEN, 256);

  if (!adapterUrl) {
    return json({ ok: false, error: "Adapter not configured." }, { status: 503 });
  }

  try {
    const adapterResponse = await fetch(`${adapterUrl}/memory/write`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Internal-Token": internalToken,
        "X-OmniMemora-Tenant": tenantId,
      },
      body: JSON.stringify({
        tenant: tenantId,
        user: String(tenantRow["display_name"] || "user"),
        agent: normalize(payload.agent, 128) || "omnimemora-api",
        type: normalize(payload.type, 64) || "general",
        content,
        tags: payload.tags ?? [],
        metadata: payload.metadata ?? {},
      }),
    });

    const result = await adapterResponse.json() as Record<string, unknown>;
    return json({
      ok: adapterResponse.ok,
      tenantId,
      ...result,
    }, { status: adapterResponse.status });
  } catch (err) {
    return json(
      { ok: false, error: `Failed to reach adapter: ${err instanceof Error ? err.message : String(err)}` },
      { status: 502 },
    );
  }
};
