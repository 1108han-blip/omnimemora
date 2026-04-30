# OmniMemora Cloud Platform Stewardship Rule (2026-04-30)

## Intent

This record fixes the cloud operating model for OmniMemora after the `openviking-site` cleanup.

The operator may run multiple small projects on shared platform accounts. Codex is expected to manage cloud work directly, keep projects separated, and remove obsolete same-project resources instead of preserving them indefinitely.

## Project Isolation

Cloud platform resources may be shared at the account level, but project resources must stay isolated.

Isolation dimensions:

- domain and subdomain
- Cloudflare Worker / Pages project
- Worker route
- DNS record
- Railway project / service / custom domain
- R2 bucket prefix
- environment variable namespace
- release artifact path
- support or email routing ownership
- documentation record

OmniMemora cloud work must not mutate unrelated projects such as other websites, product harnesses, or non-OmniMemora subdomains. When a platform account contains multiple projects, Codex must identify the target resource before making changes.

## Same-Project Replacement

Within OmniMemora, each iteration should replace the previous iteration when the previous one conflicts with current product identity.

Rules:

- Do not accumulate old OmniMemora Cloudflare Pages projects, Workers, routes, DNS entries, Railway custom domains, or deployment variables as informal fallbacks.
- Delete or disable obsolete OmniMemora resources after replacement continuity is verified.
- If an old OmniMemora resource is retained, record its reason, owner, and retirement condition.
- The `openviking-site` case is the negative example: it survived several iterations and created identity drift, so it was deleted once `omnimemora-control-entry` continuity was verified.

## Clean Rebuild Bias

These projects are small. If cloud state becomes tangled, Codex should prefer a clean rebuild over extended bug-by-bug repair when that is lower risk and faster.

Before rebuild:

- identify user-facing endpoints
- identify stored user data or support data
- check billing/account ownership blast radius
- preserve current release version and support contact
- verify replacement continuity before deleting the old surface

## Codex Authority

Codex is authorized to handle OmniMemora cloud work end-to-end when credentials are available:

- architecture setup
- DNS and route configuration
- Worker/Pages/Railway resource management
- release/version checks
- security configuration
- running health checks
- audit records
- user-data handling checks

Codex should not ask the operator to design cloud structure. The operator is not expected to know website architecture or English engineering terms.

Ask the operator only when:

- credentials are missing
- billing/account ownership could change
- user-facing data might be deleted or exposed
- two product/business directions are both plausible and cannot be inferred
- a destructive action affects another project

## Current OmniMemora Baseline

As of 2026-04-30:

- official domain entry: `doloclaw.com`
- active Cloudflare Worker: `omnimemora-control-entry`
- deleted legacy conflict: `openviking-site`
- preserved unrelated subdomain: `prompt.doloclaw.com`
- Railway role: candidate-state / async carrier only
- Railway custom domains: none
- local product ingress after opt-in: `18011`
- user control/display: `5173`
- internal memory plane: `8765`

## Reporting Standard

Every cloud operation report must label:

- repository reality
- cloud platform reality
- running reality
- project isolation impact
- user-data impact
- obsolete resource removal status
- release/version status

Default report language is plain Chinese.
