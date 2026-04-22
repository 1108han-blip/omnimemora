# Cloud Candidate Sources (Batch 1 Skeleton)

This directory defines the minimum contract for recommendation cloud candidates.

- `cloudflare_control_plane.py`: fetches latest candidate pointer
- `railway_state_store.py`: fetches candidate snapshot/state by snapshot id
- `service.py`: orchestrates pointer -> snapshot and returns candidate policy

Rules:

- local active policy is authoritative
- cloud candidate is optional
- cloud candidate does not directly promote/override local active
