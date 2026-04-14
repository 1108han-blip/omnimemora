/**
 * functions/api/billing/checkout-session.ts  --  POST /api/billing/checkout-session
 *
 * Creates a Stripe Checkout Session (mode: subscription) and returns
 * { checkoutUrl } so the client can redirect the user to Stripe.
 *
 * SKELETON STATUS:
 *   - Stripe SDK call is syntactically correct and will execute once secrets are set.
 *   - Returns HTTP 503 with { stub: true } until STRIPE_SECRET_KEY is configured.
 *   - Live vs test mode driven entirely by STRIPE_SECRET_KEY value.
 *
 * Secrets required: STRIPE_SECRET_KEY, STARTER_MONTHLY_PRICE_ID, PRO_MONTHLY_PRICE_ID
 *
 * Request body: { tenantId, planId, successUrl, cancelUrl, customerEmail? }
 * Responses:
 *   200 { ok: true,  checkoutUrl }
 *   400 { ok: false, error }
 *   404 { ok: false, error }  -- tenant not found in tenant_registry
 *   503 { ok: false, error, stub: true }  -- Stripe not configured
 */

interface Env {
  LEADS_DB: D1Database;
  STRIPE_SECRET_KEY?: string;
  STARTER_MONTHLY_PRICE_ID?: string;
  PRO_MONTHLY_PRICE_ID?: string;
}

interface CheckoutPayload {
  tenantId?: string;
  planId?: string;
  successUrl?: string;
  cancelUrl?: string;
  customerEmail?: string;
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
      error:
        "Stripe is not configured in this environment. " +
        "Set STRIPE_SECRET_KEY, STARTER_MONTHLY_PRICE_ID, and PRO_MONTHLY_PRICE_ID " +
        "as wrangler secrets to enable checkout.",
      stub: true,
    }, { status: 503 });
  }

  let payload: CheckoutPayload;
  try { payload = (await request.json()) as CheckoutPayload; }
  catch { return json({ ok: false, error: "Invalid JSON body." }, { status: 400 }); }

  const tenantId   = norm(payload.tenantId, 120);
  const planId     = norm(payload.planId, 80);
  const successUrl = norm(payload.successUrl, 1024);
  const cancelUrl  = norm(payload.cancelUrl, 1024);

  if (!tenantId)   return json({ ok: false, error: "tenantId is required." }, { status: 400 });
  if (!planId)     return json({ ok: false, error: "planId is required." }, { status: 400 });
  if (!successUrl || !cancelUrl)
    return json({ ok: false, error: "successUrl and cancelUrl are required." }, { status: 400 });

  let priceId: string;
  if (planId === "starter_monthly") priceId = norm(env.STARTER_MONTHLY_PRICE_ID, 128);
  else if (planId === "pro_monthly") priceId = norm(env.PRO_MONTHLY_PRICE_ID, 128);
  else return json(
    { ok: false, error: "planId must be starter_monthly or pro_monthly." },
    { status: 400 },
  );

  if (!priceId) {
    const missing = planId === "starter_monthly" ? "STARTER_MONTHLY_PRICE_ID" : "PRO_MONTHLY_PRICE_ID";
    return json({
      ok: false,
      error: "Price ID for plan [" + planId + "] is not configured. Set " + missing + " as a wrangler secret.",
    }, { status: 503 });
  }

  const tenant = await env.LEADS_DB
    .prepare("SELECT tenant_id FROM tenant_registry WHERE tenant_id = ?")
    .bind(tenantId).first();

  if (!tenant)
    return json({ ok: false, error: "Tenant [" + tenantId + "] not found in tenant_registry." }, { status: 404 });

  // @ts-ignore
  let StripeConstructor: new (key: string, opts: Record<string, unknown>) => {
    checkout: { sessions: { create: (o: Record<string, unknown>) => Promise<{ url: string }> } }
  };
  try { StripeConstructor = (await import("stripe")).default as unknown as typeof StripeConstructor; }
  catch {
    return json({ ok: false, error: "Stripe SDK not installed. Run: npm install stripe" }, { status: 500 });
  }

  try {
    // @ts-ignore
    const stripe = new StripeConstructor(secretKey, { apiVersion: "2024-11-20.acacia" });
    const session = await stripe.checkout.sessions.create({
      mode: "subscription",
      line_items: [{ price: priceId, quantity: 1 }],
      success_url: successUrl,
      cancel_url: cancelUrl,
      customer_email: norm(payload.customerEmail, 254) || undefined,
      metadata: { tenant_id: tenantId, plan_id: planId },
      subscription_data: { metadata: { tenant_id: tenantId } },
    });
    return json({ ok: true, checkoutUrl: session.url });
  } catch (err) {
    return json({
      ok: false,
      error: err instanceof Error ? err.message : "Stripe checkout session creation failed.",
    }, { status: 500 });
  }
};