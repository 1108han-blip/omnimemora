interface Env {
  LEADS_DB: D1Database;
  ADMIN_API_TOKEN?: string;
  REGISTRY_SYNC_TOKEN?: string;
}

interface CreateTenantPayload {
  tenantId?: string;
  displayName?: string;
  contactEmail?: string;
  plan?: string;
  status?: string;
  apiKeyHash?: string;
  tokenId?: string;
}

interface UpdateTenantPayload {
  tenantId?: string;
  status?: string;
}

const json = (body: unknown, init?: ResponseInit) =>
  new Response(JSON.stringify(body, null, 2), {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
    ...init,
  });

function normalize(value: string | undefined, max: number) {
  return (value ?? "").trim().slice(0, max);
}

function isEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function checkAdmin(request: Request, env: Env) {
  const configured = normalize(env.ADMIN_API_TOKEN, 256);
  if (!configured) {
    return { ok: false as const, response: json({ ok: false, error: "ADMIN_API_TOKEN is not configured." }, { status: 500 }) };
  }

  const auth = request.headers.get("authorization") ?? "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  if (!token || token !== configured) {
    return { ok: false as const, response: json({ ok: false, error: "Unauthorized." }, { status: 401 }) };
  }

  return { ok: true as const };
}

function checkReadAccess(request: Request, env: Env) {
  // Accept either ADMIN_API_TOKEN (full access) or REGISTRY_SYNC_TOKEN (read-only)
  const adminToken = normalize(env.ADMIN_API_TOKEN, 256);
  const syncToken = normalize(env.REGISTRY_SYNC_TOKEN, 256);
  if (!adminToken && !syncToken) {
    return { ok: false as const, response: json({ ok: false, error: "No read auth token configured." }, { status: 500 }) };
  }

  const auth = request.headers.get("authorization") ?? "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  if (!token) {
    return { ok: false as const, response: json({ ok: false, error: "Unauthorized." }, { status: 401 }) };
  }
  if (token !== adminToken && token !== syncToken) {
    return { ok: false as const, response: json({ ok: false, error: "Unauthorized." }, { status: 401 }) };
  }

  return { ok: true as const };
}

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  const auth = checkReadAccess(request, env);
  if (!auth.ok) {
    return auth.response;
  }

  const url = new URL(request.url);
  const tenantId = normalize(url.searchParams.get("tenant_id") ?? "", 120);

  if (tenantId) {
    const result = await env.LEADS_DB.prepare(
      `
        SELECT tenant_id, display_name, contact_email, plan, status, api_key_hash, token_id, created_at, updated_at
        FROM tenant_registry
        WHERE tenant_id = ?
      `,
    )
      .bind(tenantId)
      .first();

    return json({ ok: true, tenant: result ?? null });
  }

  const result = await env.LEADS_DB.prepare(
    `
      SELECT tenant_id, display_name, contact_email, plan, status, created_at, updated_at
      FROM tenant_registry
      ORDER BY updated_at DESC
      LIMIT 100
    `,
  ).all();

  return json({ ok: true, tenants: result.results ?? [] });
};

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  const auth = checkAdmin(request, env);
  if (!auth.ok) {
    return auth.response;
  }

  try {
    const payload = (await request.json()) as CreateTenantPayload;
    const tenantId = normalize(payload.tenantId, 120);
    const displayName = normalize(payload.displayName, 200);
    const contactEmail = normalize(payload.contactEmail, 200);
    const plan = normalize(payload.plan || "starter", 80) || "starter";
    const status = normalize(payload.status || "active", 40) || "active";
    const apiKeyHash = normalize(payload.apiKeyHash, 256);
    const tokenId = normalize(payload.tokenId, 120);

    if (!tenantId || !displayName || !contactEmail) {
      return json({ ok: false, error: "tenantId, displayName, and contactEmail are required." }, { status: 400 });
    }
    if (!isEmail(contactEmail)) {
      return json({ ok: false, error: "Invalid contactEmail." }, { status: 400 });
    }

    const now = new Date().toISOString();

    await env.LEADS_DB.prepare(
      `
        INSERT INTO tenant_registry (
          tenant_id,
          display_name,
          contact_email,
          plan,
          status,
          api_key_hash,
          token_id,
          created_at,
          updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      `,
    )
      .bind(
        tenantId,
        displayName,
        contactEmail,
        plan,
        status,
        apiKeyHash || null,
        tokenId || null,
        now,
        now,
      )
      .run();

    return json({ ok: true, tenantId, createdAt: now });
  } catch (error) {
    return json(
      { ok: false, error: error instanceof Error ? error.message : "Tenant insert failed." },
      { status: 500 },
    );
  }
};

export const onRequestPatch: PagesFunction<Env> = async ({ request, env }) => {
  const auth = checkAdmin(request, env);
  if (!auth.ok) {
    return auth.response;
  }

  try {
    const payload = (await request.json()) as UpdateTenantPayload;
    const tenantId = normalize(payload.tenantId, 120);
    const status = normalize(payload.status, 40);

    if (!tenantId || !status) {
      return json({ ok: false, error: "tenantId and status are required." }, { status: 400 });
    }

    const now = new Date().toISOString();
    const result = await env.LEADS_DB.prepare(
      `
        UPDATE tenant_registry
        SET status = ?, updated_at = ?
        WHERE tenant_id = ?
      `,
    )
      .bind(status, now, tenantId)
      .run();

    return json({
      ok: true,
      tenantId,
      status,
      rowsAffected: result.meta.changes ?? 0,
      updatedAt: now,
    });
  } catch (error) {
    return json(
      { ok: false, error: error instanceof Error ? error.message : "Tenant update failed." },
      { status: 500 },
    );
  }
};
