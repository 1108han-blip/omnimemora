# OmniMemora Compliance Documentation

**Version:** 1.0
**Last Updated:** 2026-04-08

---

## Data Handling Principles

OmniMemora is designed with the following data handling principles:

1. **Tenant Isolation** — Each tenant's memory data is strictly isolated. Cross-tenant access is prevented at the adapter layer.
2. **No Cross-Agent Sharing** — Memories are scoped to individual agent namespaces by default.
3. **API Key Security** — API keys are stored as salted hashes only. Plaintext keys are shown exactly once at provisioning.
4. **Audit Logging** — All write/delete operations carry a request ID for traceability.
5. **No Third-Party Data Sharing** — OmniMemora does not share, sell, or transfer tenant memory data to third parties.

---

## Memory Retention Policy

| Memory Level | Default TTL | Retention |
|-------------|-----------|-----------|
| L1 (Short-term) | 7 days | Automatically purged after 7 days |
| L2 (Experience) | 30 days | Automatically purged after 30 days |
| L3 (Core) | Permanent | Retained until explicitly deleted |

Expired memories are excluded from search results by default. Memory owners can override TTL at write time.

---

## API Key Security

- API keys are generated using cryptographically secure random generation (UUID4 hex)
- Only the **salted hash** of the API key is stored in the tenant registry
- The plaintext API key is returned **exactly once** at provisioning — it cannot be retrieved again
- All API key validation happens over TLS

---

## Error and Support Schema

Every error response includes a structured `support` object with:

- `category` — `input`, `dependency`, `runtime`, or `quota`
- `severity` — `low`, `medium`, `high`
- `retryable` — boolean indicating whether the operation can be retried
- `suggested_action` — actionable guidance for resolving the issue
- `operation` — the internal operation that failed

This allows API consumers to programmatically handle errors without parsing error messages.

---

## Support Contact

For compliance, privacy, or security concerns:

- Email: support@doloclaw.com
- Website: https://doloclaw.com/support
