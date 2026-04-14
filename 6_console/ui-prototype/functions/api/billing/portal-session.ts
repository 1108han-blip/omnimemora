/**
 * functions/api/billing/portal-session.ts  --  POST /api/billing/portal-session
 *
 * Creates a Stripe Customer Portal session for the named tenant,
 * enabling self-service subscription management.
 *
 * SKELETON STATUS:
 *   - Stripe SDK call is real and correct.
 *   - Returns 503 stub until STRIPE_SECRET_KEY is configured.
 *   - Live vs test mode driven by STRIPE_SECRET_KEY value.
 *
 * Secrets required: STRIPE_SECRET_KEY
 *
 * Request body: { tenantId, returnUrl? }
 * Responses: 200 | 400 | 404 | 503 (stub)
 */

interface Env {
  LEADS_DB: D1Database;
  STRIPE_SECRET_KEY?: string;
}

interface PortalPayload {
  tenantId?: string;
  returnUrl?: string;
}

const json = (body: unknown, init?: ResponseInit) =>
  new Response(JSON.stringify(body, null, 2), {
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
    ...init,
  });

function norm(v: string | undefined, max: number) { return (v ?? "").trim().slice(0, max); }

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  const secretKey = norm(env.STRIPE_SECRET_KEY, 256);

  if (!secretKey) {
    return json({
      ok: false,
      error: "Stripe is not configured. Set STRIPE_SECRET_KEY as a wrangler secret.",
      stub: true,
    }, { status: 503 });
  }

  let payload: PortalPayload;
  try { payload = (await request.json()) as PortalPayload; }
  catch { return json({ ok: false, error: "Invalid JSON body." }, { status: 400 }); }

  const tenantId = norm(payload.tenantId, 120);
  if (!tenantId) return json({ ok: false, error: "tenantId is required." }, { status: 400 });

  const sub = await env.LEADS_DB
    .prepare(
      "SELECT stripe_customer_id FROM billing_subscriptions " +
      "WHERE tenant_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1"
    ).bind(tenantId).first();

  if (!sub)
    return json({
      ok: false,
      error: "No active subscription found for tenant. Create one via POST /api/billing/checkout-session first.",
    }, { status: 404 });

  const stripeCustomerId = (sub as Record<string, string>).stripe_customer_id;

  // @ts-ignore
  let StripeConstructor: new (key: string, opts: Record<string, unknown>) => {
    billing: { portal: { sessions: { create: (o: Record<string, unknown>) => Promise<{ url: string }> } } }
  };
  try { StripeConstructor = (await import("stripe")).default as unknown as typeof StripeConstructor; }
  catch { return json({ ok: false, error: "Stripe SDK not installed. Run: npm install stripe" }, { status: 500 }); }

  try {
    // @ts-ignore
    const stripe = new StripeConstructor(secretKey, { apiVersion: "2024-11-20.acacia" });
    const session = await stripe.billing.portal.sessions.create({
      customer: stripeCustomerId,
      return_url: norm(payload.returnUrl, 1024) || undefined,
    });
    return json({ ok: true, portalUrl: session.url });
  } catch (err) {
    return json({
      ok: false,
      error: err instanceof Error ? err.message : "Stripe portal session creation failed.",
    }, { status: 500 });
  }
};
