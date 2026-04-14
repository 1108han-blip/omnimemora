/**
 * billing/plans.ts
 *
 * Plan -> Stripe Price-ID mapping.
 *
 * LIVE vs TEST behaviour:
 *   - STRIPE_SECRET_KEY absent/empty  -> throws; no real Stripe calls possible.
 *   - STRIPE_SECRET_KEY set (any value) -> price IDs resolved from secrets.
 *   - No Price IDs hard-coded here; injected via wrangler secrets:
 *       wrangler secret put STRIPE_SECRET_KEY
 *       wrangler secret put STARTER_MONTHLY_PRICE_ID
 *       wrangler secret put PRO_MONTHLY_PRICE_ID
 *
 * Plan-to-env-var mapping is serialisable so admin tooling can introspect
 * without calling the Stripe API.
 */

export type PlanId = "starter_monthly" | "pro_monthly";

export interface PlanEntry {
  planId: PlanId;
  label: string;
  displayPrice: string;
  recommended?: boolean;
  priceIdEnvVar: string;
}

export const PLANS: PlanEntry[] = [
  {
    planId: "starter_monthly",
    label: "Starter",
    displayPrice: "USD 29 / month",
    priceIdEnvVar: "STARTER_MONTHLY_PRICE_ID",
  },
  {
    planId: "pro_monthly",
    label: "Pro",
    displayPrice: "USD 99 / month",
    recommended: true,
    priceIdEnvVar: "PRO_MONTHLY_PRICE_ID",
  },
];

export function getPlan(planId: string): PlanEntry | undefined {
  return PLANS.find((p) => p.planId === planId);
}

export function getPriceIds(
  secretKey: string | undefined,
  starterMonthlyPriceId: string | undefined,
  proMonthlyPriceId: string | undefined,
): Record<PlanId, string> {
  if (!secretKey) {
    throw new Error(
      "Stripe is not configured. Set STRIPE_SECRET_KEY, STARTER_MONTHLY_PRICE_ID, and PRO_MONTHLY_PRICE_ID as wrangler secrets.",
    );
  }
  if (!starterMonthlyPriceId || !proMonthlyPriceId) {
    throw new Error(
      "Price ID secrets are incomplete. Set STARTER_MONTHLY_PRICE_ID and PRO_MONTHLY_PRICE_ID as wrangler secrets.",
    );
  }
  return { starter_monthly: starterMonthlyPriceId, pro_monthly: proMonthlyPriceId };
}
