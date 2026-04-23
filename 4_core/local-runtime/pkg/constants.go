// pkg/constants.go - OmniMemora Canonical Port and Service Constants
// This file is the SINGLE SOURCE OF TRUTH for all port numbers and service identifiers.
// Design documents, code, and scripts must reference these constants.
package pkg

// =============================================================================
// Port Constants (SINGLE SOURCE OF TRUTH)
// =============================================================================
// These values are the authoritative port numbers for OmniMemora services.
// All code must use these constants, not hardcoded literals.
// Document reference: RUNTIME_ARCHITECTURE.md / SYSTEM_ARCHITECTURE.md

const (
	// OmniMemora Runtime HTTP server port (Go service)
	// - Primary API endpoint for memory operations
	// - Adapter (18011) connects to this port
	// - Default: 8765, falls back to 8766/8767/8775 if occupied
	PortRuntime = 8765

	// OmniMemora Memory Adapter HTTP server port (Python/Go service)
	// - Product-facing entry point for OpenClaw plugins and connectors
	// - Listens on 18011 for agent requests
	PortAdapter = 18011

	// Legacy OpenViking backend port (compatibility-only)
	// - Retained only to document historical deployments
	// - Not part of the current OmniMemora product topology
	PortLegacyOpenViking = 1933

	// Demo Dashboard UI port (Vite dev server)
	// - Frontend only, proxies API calls to Adapter (18011)
	PortDashboard = 5173

	// PortFallbackPorts defines the fallback port sequence when default is unavailable
	// Used by runtime.ResolvePort()
	PortFallback1 = 8766
	PortFallback2 = 8767
	PortFallback3 = 8775
)

// =============================================================================
// Service Name Constants
// =============================================================================

const (
	ServiceNameRuntime    = "omnimemora-runtime"
	ServiceNameAdapter    = "omnimemora-adapter"
	ServiceNameDashboard  = "omnimemora-dashboard"
	ServiceNameLegacyOpenViking = "openviking-backend"
)

// =============================================================================
// Data Directory
// =============================================================================

const (
	// DefaultDataDir is the default data storage directory
	DefaultDataDir = ".omnimemora"
	// StateFileName is the runtime state file name (stores port + PID)
	StateFileName = "runtime.state"
)
