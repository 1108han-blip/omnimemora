---
doc_id: SPEC-BACKEND-ABSTRACTION-001
title: OmniMemora Backend Abstraction Layer Specification
owner: platform-team
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 2.0.0
effective_date: 2026-04-23
depends_on: [ADR-0001-PRODUCT-BOUNDARY, ADR-0007-BACKEND-ABSTRACTION, ADR-0003-INTERFACE-ACCESS-PATHS]
supersedes: [
  "1_architecture/archive/legacy/backend_abstraction/BACKEND_INTERFACE.md",
  "1_architecture/archive/legacy/backend_abstraction/BACKEND_ADAPTER_PATTERN.md",
  "1_architecture/archive/legacy/backend_abstraction/BACKEND_FACTORY.md",
  "1_architecture/archive/legacy/backend_abstraction/MIGRATION_PLAN_1933.md"
]
last_verified_commit: ""
---

# SPEC-BACKEND-ABSTRACTION-001: Backend Abstraction Layer

## 0. Summary

This spec defines the active backend abstraction contract for OmniMemora.

Current product facts:
- Product ingress: `:18011`
- Local memory plane: `:8765`
- Active backend type: `omnimemora_runtime` only
- Cloud candidate source is optional and does not replace local active state

## 1. Interface Principles

- Backend-neutral models only: request/record/scope/health
- Connector layer calls backend interface, not backend-specific wire protocol
- Local-first execution truth remains authoritative
- Any retired backend path is archive-only and not part of active runtime

## 2. Required Model Surface

```python
@dataclass
class MemorySearchRequest:
    query: str
    limit: int = 10
    scope: str = "agent"
    scope_ref: str = "default"
    score_threshold: float = 0.0
    metadata_filter: Optional[Dict[str, Any]] = None

@dataclass
class MemoryWriteRequest:
    content: str
    scope: str
    scope_ref: str
    metadata: Dict[str, Any]

@dataclass
class MemoryRecord:
    memory_id: str
    content: str
    scope: str
    scope_ref: str
    metadata: Dict[str, Any]

@dataclass
class MemorySearchResult:
    memories: List[MemoryRecord]
    total: int

@dataclass
class BackendHealth:
    healthy: bool
    backend_type: str
    details: Optional[Dict[str, Any]] = None
```

## 3. Active Backend Contract

### 3.1 Active backend type

- `memory_backend.backend_type = "omnimemora_runtime"`
- Unknown or retired backend types MUST fail fast

### 3.2 Active config keys

- `MEMORY_BACKEND_URL` (default `http://127.0.0.1:8765`)
- `MEMORY_BACKEND_API_KEY` (optional)
- `OMNIMEMORA_MEMORY_NAMESPACE_ROOT` (namespace root)

### 3.3 Runtime policy

- Connector `:18011` remains the external product ingress
- Backend adapter calls local runtime `:8765`
- Cloud control/candidate paths remain optional and non-authoritative for local active state

## 4. Architecture Notes

- `5_connectors/adapter/backends/base.py`: interface and models
- `5_connectors/adapter/backends/factory.py`: backend creation and retired-type rejection
- `5_connectors/adapter/backends/omnimemora_runtime_backend.py`: active backend implementation

Legacy backend abstraction documents are moved under:
`1_architecture/archive/legacy/backend_abstraction/`

## 5. Compatibility Boundary

- Retired backend symbols are not allowed as active config defaults or active backend options
- Legacy references may exist only in archive/legacy material

## 6. Change History

| Version | Date | Change |
|---|---|---|
| 2.0.0 | 2026-04-23 | Retired legacy backend vocabulary from active spec; fixed active backend contract to `omnimemora_runtime` only |
| 1.0.0 | 2026-04-14 | Initial canonical spec |
