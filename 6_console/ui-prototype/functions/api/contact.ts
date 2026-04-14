interface Env {
  LEADS_DB: D1Database;
  OMNIMEMORA_TRIAL_DAYS?: string;
  OMNIMEMORA_TRIAL_QUOTA_TOKENS?: string;
}

interface LeadPayload {
  name?: string;
  email?: string;
  useCase?: string;
  tokenUsage?: string;
  goal?: string;
  companyWebsite?: string;
}

const json = (body: unknown, init?: ResponseInit) =>
  new Response(JSON.stringify(body, null, 2), {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
    ...init,
  });

function normalizeText(value: string | undefined, max: number) {
  return (value ?? "").trim().slice(0, max);
}

function isEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

async function sha256Hex(value: string) {
  const encoded = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest))
    .map((part) => part.toString(16).padStart(2, "0"))
    .join("");
}

function parsePositiveInt(value: string | undefined, fallback: number) {
  const parsed = Number.parseInt((value ?? "").trim(), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export const onRequestGet: PagesFunction<Env> = async () => {
  return json({
    ok: true,
    route: "/api/contact",
    accepts: ["POST"],
  });
};

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return json(
      {
        ok: false,
        error: "Expected application/json request body.",
      },
      { status: 415 },
    );
  }

  const payload = (await request.json()) as LeadPayload;

  // Simple honeypot against form-bot spam.
  if (normalizeText(payload.companyWebsite, 120)) {
    return json({ ok: true, skipped: true }, { status: 202 });
  }

  const name = normalizeText(payload.name, 120);
  const email = normalizeText(payload.email, 200);
  const useCase = normalizeText(payload.useCase, 120);
  const tokenUsage = normalizeText(payload.tokenUsage, 160);
  const goal = normalizeText(payload.goal, 4000);

  if (!name || !email || !useCase) {
    return json(
      {
        ok: false,
        error: "name, email, and useCase are required.",
      },
      { status: 400 },
    );
  }

  if (!isEmail(email)) {
    return json(
      {
        ok: false,
        error: "Invalid email address.",
      },
      { status: 400 },
    );
  }

  // ---- Lead insertion (always happens first) ----
  let leadId: string;
  let createdAt: string;
  let userAgent: string;
  try {
    leadId = crypto.randomUUID();
    createdAt = new Date().toISOString();
    userAgent = normalizeText(request.headers.get("user-agent") ?? "", 512);

    await env.LEADS_DB.prepare(
      `
        INSERT INTO private_leads (
          id,
          name,
          email,
          use_case,
          monthly_token_usage,
          message,
          source,
          status,
          created_at,
          user_agent
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)
      `,
    )
      .bind(
        leadId,
        name,
        email,
        useCase,
        tokenUsage || null,
        goal || null,
        "doloclaw.com/contact",
        createdAt,
        userAgent || null,
      )
      .run();
  } catch (error) {
    return json(
      {
        ok: false,
        error: error instanceof Error ? error.message : "Unknown insert failure.",
      },
      { status: 500 },
    );
  }

  // ---- Attempt automatic trial provisioning directly in D1 tenant_registry ----
  const trialDays = parsePositiveInt(env.OMNIMEMORA_TRIAL_DAYS, 14);
  const monthlyQuotaTokens = parsePositiveInt(
    env.OMNIMEMORA_TRIAL_QUOTA_TOKENS,
    500000,
  );

  try {
    const tenantId = `trial-${crypto.randomUUID().replace(/-/g, "").slice(0, 12)}`;
    const tokenId = `tk-${crypto.randomUUID().replace(/-/g, "").slice(0, 12)}`;
    const apiKey = `omni-${crypto.randomUUID()}-${crypto.randomUUID().replace(/-/g, "").slice(0, 8)}`;
    const apiKeyHash = await sha256Hex(apiKey);
    const tenantCreatedAt = new Date().toISOString();
    const trialExpiresAt = new Date(
      Date.now() + trialDays * 24 * 60 * 60 * 1000,
    ).toISOString();

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
        name,
        email,
        "starter",
        "active",
        apiKeyHash,
        tokenId,
        tenantCreatedAt,
        tenantCreatedAt,
      )
      .run();

    console.log(`[CONTACT_TRIAL] success tenant=${tenantId} lead=${leadId}`);

    return json({
      ok: true,
      leadId,
      trialProvisioned: true,
      tenantId,
      apiKey,
      plan: "starter",
      status: "active",
      monthlyQuotaTokens,
      trialExpiresAt,
      nextStep:
        "Your free trial identity is ready. Save your API key now — it will not be shown again.",
    });
  } catch (error) {
    console.warn(
      `[CONTACT_TRIAL] direct D1 provisioning failed: ${error instanceof Error ? error.message : String(error)}`,
    );
  }

  // ---- Graceful degradation: lead recorded, trial provisioning pending ----
  return json({
    ok: true,
    leadId,
    trialProvisioned: false,
    pending: true,
    nextStep:
      "Your inquiry has been received. Trial auto-provisioning is not yet configured in this environment, " +
      "but your lead is in the queue. We will follow up with API access instructions shortly.",
  });
};
