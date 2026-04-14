/**
 * functions/api/billing/webhook.ts  --  POST /api/billing/webhook
 *
 * Receives Stripe webhook events, verifies the signature, and upserts
 * billing_subscriptions, billing_customers, and billing_events rows.
 *
 * SKELETON STATUS:
 *   - Signature verification is real and correct.
 *   - Lifecycle handlers (checkout.session.completed, subscription.updated,
 *     subscription.deleted, invoice.payment_failed) are fully implemented.
 *   - Returns 503 stub until STRIPE_SECRET_KEY + STRIPE_WEBHOOK_SECRET are set.
 *   - Live vs test mode driven by STRIPE_SECRET_KEY value.
 *
 * IMPORTANT: Register endpoint in Stripe Dashboard -> Webhooks:
 *   https://dashboard.stripe.com/webhooks
 *   -> https://<your-site>/api/billing/webhook
 *   Subscribe to: checkout.session.completed, customer.subscription.updated,
 *                 customer.subscription.deleted, invoice.payment_failed
 *
 * Secrets required:
 *   STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET (from Stripe Dashboard)
 *   STARTER_MONTHLY_PRICE_ID, PRO_MONTHLY_PRICE_ID
 */

interface Env {
  LEADS_DB: D1Database;
  STRIPE_SECRET_KEY?: string;
  STRIPE_WEBHOOK_SECRET?: string;
  STARTER_MONTHLY_PRICE_ID?: string;
  PRO_MONTHLY_PRICE_ID?: string;
}

const HANDLED_EVENTS = [
  "checkout.session.completed",
  "customer.subscription.updated",
  "customer.subscription.deleted",
  "invoice.payment_failed",
] as const;

const json = (body: unknown, init?: ResponseInit) =>
  new Response(JSON.stringify(body, null, 2), {
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
    ...init,
  });

function norm(v: string | undefined, max: number) { return (v ?? "").trim().slice(0, max); }

function priceIdToPlanId(id: string, env: Env): string {
  if (id === norm(env.STARTER_MONTHLY_PRICE_ID, 128)) return "starter_monthly";
  if (id === norm(env.PRO_MONTHLY_PRICE_ID, 128)) return "pro_monthly";
  return "unknown";
}

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  const secretKey      = norm(env.STRIPE_SECRET_KEY, 256);
  const webhookSecret  = norm(env.STRIPE_WEBHOOK_SECRET, 256);

  if (!secretKey || !webhookSecret) {
    return json({
      ok: false,
      error:
        "Stripe webhook secrets not configured. " +
        "Set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET as wrangler secrets.",
      stub: true,
    }, { status: 503 });
  }

  const rawBody = await request.text();
  const sig = request.headers.get("stripe-signature") ?? "";

  // Dynamic import so file compiles before Stripe is called.
  // Stripe v21 exports: createFetchHttpClient, createSubtleCryptoProvider
  // @ts-ignore
  let StripeConstructor: new (key: string, opts: Record<string, unknown>) => {
    createFetchHttpClient: () => unknown;
    createSubtleCryptoProvider: (subtle: unknown) => unknown;
    webhooks: {
      constructEventAsync: (
        body: string, sig: string, secret: string,
        tolerance: number | undefined,
        cryptoProvider: unknown,
      ) => Promise<Record<string, unknown>>;
    };
    subscriptions: { retrieve: (id: string) => Promise<Record<string, unknown>> };
  };
  try { StripeConstructor = (await import("stripe")).default as unknown as typeof StripeConstructor; }
  catch { return json({ ok: false, error: "Stripe SDK not installed. Run: npm install stripe" }, { status: 500 }); }

  let event: Record<string, unknown>;
  try {
    // Workers-compatible Stripe client using globalThis.crypto.subtle for HMAC
    // verification via Stripe's SubtleCryptoProvider.  createFetchHttpClient()
    // uses the native globalThis.fetch available in CF Workers.
    // @ts-ignore
    const stripe = new StripeConstructor(secretKey, {
      apiVersion: "2024-11-20.acacia",
      // @ts-ignore
      httpClient: StripeConstructor.createFetchHttpClient(),
    });
    // @ts-ignore
    const subtleProvider = StripeConstructor.createSubtleCryptoProvider(crypto.subtle);
    // SubtleCryptoProvider is async-only → must use constructEventAsync;
    // pass it as the 5th positional argument (not a constructor option).
    // @ts-ignore
    event = await stripe.webhooks.constructEventAsync(
      rawBody, sig, webhookSecret, undefined, subtleProvider,
    );
  } catch (err) {
    return json({
      ok: false,
      error: "Webhook signature verification failed: " + (err instanceof Error ? err.message : "unknown"),
    }, { status: 400 });
  }

  const eventType = event.type as string;
  if (!(HANDLED_EVENTS as readonly string[]).includes(eventType)) {
    return json({ ok: true, handled: false, eventType });
  }

  const data = event.data as { object: Record<string, unknown> };
  const eventId = (event.id as string) ?? crypto.randomUUID();
  const now = new Date().toISOString();

  try {
    if (eventType === "checkout.session.completed") {
      const s = data.object;
      const tenantId         = (s.metadata as Record<string, string>)?.tenant_id;
      const stripeCustomerId = s.customer as string;
      const subscriptionId   = s.subscription as string;
      if (!tenantId || !stripeCustomerId || !subscriptionId)
        return json({ ok: false, error: "Missing tenant_id or subscription in checkout session." }, { status: 400 });

      // @ts-ignore
      const stripe = new StripeConstructor(secretKey, {
        apiVersion: "2024-11-20.acacia",
        // @ts-ignore
        httpClient: StripeConstructor.createFetchHttpClient(),
      });
      const sub = await stripe.subscriptions.retrieve(subscriptionId) as Record<string, unknown>;
      const item = (sub.items as { data: Array<Record<string, unknown>> }).data[0];
      const stripePriceId = item.price as string;
      const planId      = priceIdToPlanId(stripePriceId, env);
      const periodStart = new Date((sub.current_period_start as number) * 1000).toISOString();
      const periodEnd   = new Date((sub.current_period_end   as number) * 1000).toISOString();

      const existing = await env.LEADS_DB
        .prepare("SELECT id FROM billing_subscriptions WHERE stripe_subscription_id = ?")
        .bind(subscriptionId).first();
      if (existing) return json({ ok: true, action: "already_exists", subscriptionId });

      await env.LEADS_DB.prepare(
        "INSERT OR REPLACE INTO billing_customers " +
        "(id, tenant_id, stripe_customer_id, email, name, created_at, updated_at) " +
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
      ).bind(
        crypto.randomUUID(), tenantId, stripeCustomerId,
        (s.customer_details as Record<string, string>)?.email ?? null,
        (s.customer_details as Record<string, string>)?.name ?? null,
        now, now,
      ).run();

      await env.LEADS_DB.prepare(
        "INSERT INTO billing_subscriptions " +
        "(id, tenant_id, stripe_customer_id, stripe_subscription_id, stripe_price_id, plan_id, " +
        " status, current_period_start, current_period_end, cancel_at_period_end, created_at, updated_at) " +
        "VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, 0, ?, ?)"
      ).bind(
        crypto.randomUUID(), tenantId, stripeCustomerId, subscriptionId, stripePriceId, planId,
        periodStart, periodEnd, now, now,
      ).run();

      await env.LEADS_DB.prepare(
        "INSERT OR IGNORE INTO billing_events " +
        "(id, tenant_id, stripe_event_id, event_type, api_version, raw_payload, processed_at) " +
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
      ).bind(
        crypto.randomUUID(), tenantId, eventId, eventType,
        (event.api_version as string) ?? null, rawBody, now,
      ).run();

      return json({ ok: true, action: "created", subscriptionId, planId });
    }

    if (eventType === "customer.subscription.updated") {
      const sub = data.object;
      const periodStart = new Date((sub.current_period_start as number) * 1000).toISOString();
      const periodEnd   = new Date((sub.current_period_end   as number) * 1000).toISOString();
      const cancel = (sub.cancel_at_period_end as boolean) ? 1 : 0;

      // Resolve tenant_id from stripe_customer_id for billing_events
      const stripeCustomerId = sub.customer as string;
      const tenantRow = stripeCustomerId
        ? await env.LEADS_DB
            .prepare("SELECT tenant_id FROM billing_customers WHERE stripe_customer_id = ?")
            .bind(stripeCustomerId).first()
        : null;
      const tenantId = tenantRow ? (tenantRow as Record<string, string>).tenant_id : null;

      const result = await env.LEADS_DB.prepare(
        "UPDATE billing_subscriptions SET status = ?, current_period_start = ?, " +
        "current_period_end = ?, cancel_at_period_end = ?, updated_at = ? " +
        "WHERE stripe_subscription_id = ?"
      ).bind(sub.status as string, periodStart, periodEnd, cancel, now, sub.id as string).run();

      await env.LEADS_DB.prepare(
        "INSERT OR IGNORE INTO billing_events " +
        "(id, tenant_id, stripe_event_id, event_type, api_version, raw_payload, processed_at) " +
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
      ).bind(
        crypto.randomUUID(), tenantId, eventId, eventType,
        (event.api_version as string) ?? null, rawBody, now,
      ).run();

      return json({ ok: true, action: "updated", rowsAffected: result.meta.changes ?? 0 });
    }

    if (eventType === "customer.subscription.deleted") {
      const sub = data.object;

      // Resolve tenant_id from stripe_customer_id for billing_events
      const stripeCustomerId = sub.customer as string;
      const tenantRow = stripeCustomerId
        ? await env.LEADS_DB
            .prepare("SELECT tenant_id FROM billing_customers WHERE stripe_customer_id = ?")
            .bind(stripeCustomerId).first()
        : null;
      const tenantId = tenantRow ? (tenantRow as Record<string, string>).tenant_id : null;

      await env.LEADS_DB.prepare(
        "UPDATE billing_subscriptions SET status = 'canceled', updated_at = ? WHERE stripe_subscription_id = ?"
      ).bind(now, sub.id as string).run();

      await env.LEADS_DB.prepare(
        "INSERT OR IGNORE INTO billing_events " +
        "(id, tenant_id, stripe_event_id, event_type, api_version, raw_payload, processed_at) " +
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
      ).bind(
        crypto.randomUUID(), tenantId, eventId, eventType,
        (event.api_version as string) ?? null, rawBody, now,
      ).run();

      return json({ ok: true, action: "canceled" });
    }

    if (eventType === "invoice.payment_failed") {
      const inv = data.object;
      const subId = (inv.subscription as string) ?? "";
      if (subId) {
        await env.LEADS_DB.prepare(
          "UPDATE billing_subscriptions SET status = 'past_due', updated_at = ? WHERE stripe_subscription_id = ?"
        ).bind(now, subId).run();
      }

      await env.LEADS_DB.prepare(
        "INSERT OR IGNORE INTO billing_events " +
        "(id, tenant_id, stripe_event_id, event_type, api_version, raw_payload, processed_at) " +
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
      ).bind(
        crypto.randomUUID(), null, eventId, eventType,
        (event.api_version as string) ?? null, rawBody, now,
      ).run();

      return json({ ok: true, action: "past_due" });
    }

    return json({ ok: true, handled: false, eventType });
  } catch (err) {
    return json({
      ok: false,
      error: err instanceof Error ? err.message : "Webhook processing failed.",
    }, { status: 500 });
  }
};
