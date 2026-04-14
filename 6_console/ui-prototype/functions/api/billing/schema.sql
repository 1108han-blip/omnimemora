-- billing/schema.sql
--
-- D1 billing schema contract.
-- Fuses with tenant_registry via tenant_id.
-- (D1/SQLite does not enforce FK constraints; enforcement is app-layer only.)
--
-- APPLY MIGRATION:
--   dev/preview:  wrangler d1 execute omnimemora-leads --local --file=./functions/api/billing/schema.sql
--   production:   wrangler d1 execute omnimemora-leads --remote --file=./functions/api/billing/schema.sql

CREATE TABLE IF NOT EXISTS billing_subscriptions (
  id                       TEXT NOT NULL PRIMARY KEY,
  tenant_id                TEXT NOT NULL,
  stripe_customer_id        TEXT NOT NULL,
  stripe_subscription_id    TEXT NOT NULL,
  stripe_price_id           TEXT NOT NULL,
  plan_id                   TEXT NOT NULL,
  status                    TEXT NOT NULL DEFAULT 'incomplete',
  -- status: incomplete | active | past_due | canceled | trialing | unpaid
  current_period_start      TEXT NOT NULL,
  current_period_end        TEXT NOT NULL,
  cancel_at_period_end      INTEGER NOT NULL DEFAULT 0,
  created_at                TEXT NOT NULL,
  updated_at                TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_billing_subscriptions__tenant_id
  ON billing_subscriptions(tenant_id);

CREATE INDEX IF NOT EXISTS idx_billing_subscriptions__stripe_customer
  ON billing_subscriptions(stripe_customer_id);

-- billing_customers -----------------------------------------------------------
-- Mirror of Stripe customer objects; written once on first subscription event.
-- Provides a stable lookup by tenant_id without hitting the Stripe API.
CREATE TABLE IF NOT EXISTS billing_customers (
  id                   TEXT NOT NULL PRIMARY KEY,
  tenant_id            TEXT NOT NULL,
  stripe_customer_id   TEXT NOT NULL,
  email                TEXT,
  name                 TEXT,
  created_at           TEXT NOT NULL,
  updated_at           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_billing_customers__tenant_id
  ON billing_customers(tenant_id);

CREATE INDEX IF NOT EXISTS idx_billing_customers__stripe_customer_id
  ON billing_customers(stripe_customer_id);

-- billing_events ---------------------------------------------------------------
-- Append-only log of all Stripe webhook events received and processed.
-- Enables debugging, idempotency checks, and audit trails.
CREATE TABLE IF NOT EXISTS billing_events (
  id              TEXT NOT NULL PRIMARY KEY,
  tenant_id       TEXT,
  stripe_event_id TEXT NOT NULL UNIQUE,
  event_type      TEXT NOT NULL,
  api_version     TEXT,
  raw_payload     TEXT NOT NULL,   -- JSON string; retained for audit/replay
  processed_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_billing_events__tenant_id
  ON billing_events(tenant_id);

CREATE INDEX IF NOT EXISTS idx_billing_events__stripe_event_id
  ON billing_events(stripe_event_id);
