interface Env {
  LEADS_DB: D1Database;
  ADAPTER_API_URL?: string;
  INTERNAL_ADAPTER_TOKEN?: string;
}

interface TrialQueryPayload {
  query?: string;
  limit?: number;
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

// Single unified handler: OPTIONS → CORS preflight, POST → logic, all else → 405.
export const onRequest: PagesFunction<Env> = async ({ request, env }) => {
  // ---- CORS preflight ----
  if (request.method === "OPTIONS") {
    return new Response(null, {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-API-Key",
        "Access-Control-Max-Age": "86400",
      },
    });
  }

  // ---- Reject non-POST ----
  if (request.method !== "POST") {
    return json({ ok: false, error: "Method Not Allowed." }, { status: 405 });
  }

  // ---- From here: POST logic ----
  // ---- Validate content-type ----
  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return json(
      { ok: false, error: "Expected application/json request body." },
      { status: 415 },
    );
  }

  // ---- Read and hash API key ----
  const rawApiKey = normalize(request.headers.get("X-API-Key"), 256);
  if (!rawApiKey) {
    return json({ ok: false, error: "X-API-Key header is required." }, { status: 401 });
  }

  let apiKeyHash: string;
  try {
    apiKeyHash = await sha256Hex(rawApiKey);
  } catch {
    return json({ ok: false, error: "Failed to hash API key." }, { status: 500 });
  }

  // ---- Look up tenant by hashed API key ----
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

  const tenantId = String(tenantRow["tenant_id"] ?? "");
  const tenantStatus = String(tenantRow["status"] ?? "").toLowerCase();

  if (tenantStatus !== "active") {
    return json(
      { ok: false, error: "Tenant account is disabled.", tenantId },
      { status: 403 },
    );
  }

  // ---- Parse request body ----
  let payload: TrialQueryPayload;
  try {
    payload = (await request.json()) as TrialQueryPayload;
  } catch {
    return json({ ok: false, error: "Invalid JSON body." }, { status: 400 });
  }

  const query = normalize(payload.query, 4000);
  if (!query) {
    return json(
      { ok: false, error: "query field is required." },
      { status: 400 },
    );
  }

  const limit = Math.max(1, Math.min(Number(payload.limit) || 10, 100));

  // ---- Proxy to real adapter query engine ----
  const adapterUrl = normalize(env.ADAPTER_API_URL, 512);
  const internalToken = normalize(env.INTERNAL_ADAPTER_TOKEN, 256);

  if (!adapterUrl) {
    // Adapter URL not configured — degrade gracefully with structured placeholder
    return json({
      ok: true,
      v: "v1",
      tenantId,
      query,
      limit,
      selectedMemories: [],
      packedContext: "",
      adapterConfigured: false,
      tokenSavingsMeter: {
        estimatedSavings: 0,
      },
    });
  }

  // Call the adapter's internal trial-query endpoint.
  // We have already validated the API key against D1; the adapter trusts
  // this internal call via X-Internal-Token header.
  try {
    const adapterResponse = await fetch(`${adapterUrl}/internal/trial-query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Internal-Token": internalToken,
        "X-OmniMemora-Tenant": tenantId,
      },
      body: JSON.stringify({
        tenant: tenantId,
        user: String(tenantRow["display_name"] || "trial-user"),
        agent: "omnimemora-trial",
        query,
        limit,
      }),
    });

    if (!adapterResponse.ok) {
      const errText = await adapterResponse.text();
      return json(
        { ok: false, error: `Adapter error ${adapterResponse.status}: ${errText}` },
        { status: 502 },
      );
    }

    const adapterResult = await adapterResponse.json() as Record<string, unknown>;
    return json({
      ok: true,
      v: "v2",
      tenantId,
      query,
      limit,
      adapterConfigured: true,
      ...adapterResult,
    });
  } catch (err) {
    return json(
      { ok: false, error: `Failed to reach adapter: ${err instanceof Error ? err.message : String(err)}` },
      { status: 502 },
    );
  }
};
