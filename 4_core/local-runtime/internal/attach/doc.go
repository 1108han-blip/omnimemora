// Package attach implements runtime-local integration carrier actions.
//
// Scope:
//   - low-frequency attach/detach/install/uninstall flows
//   - backup/restore/detect helpers for supported agent configs
//   - runtime-local quick-select and strategy helpers
//
// Non-scope:
//   - not the memory plane
//   - not a product data entry surface
//   - not product routing policy authority
//
// Product-facing data entry remains at :18011 (gateway). Runtime port :8765
// stays internal for memory-plane and runtime-local carrier/operator surfaces.
package attach
