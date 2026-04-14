// lifecycle/health.go - Lifecycle and health check utilities
// Aligns with RUNTIME_ARCHITECTURE.md Section 12
package lifecycle

import (
	"context"
	"time"

	"github.com/omnimemora/local-runtime/config"
	"github.com/omnimemora/local-runtime/store"
)

// RuntimeContext holds runtime state for lifecycle management
type RuntimeContext struct {
	Config    *config.RuntimeConfig
	Store     store.Store
	Version   string
	StartedAt time.Time
}

// HealthChecker performs health checks
type HealthChecker struct {
	ctx *RuntimeContext
}

// NewHealthChecker creates a new health checker
func NewHealthChecker(rtCtx *RuntimeContext) *HealthChecker {
	return &HealthChecker{ctx: rtCtx}
}

// HealthStatus represents the health status of the runtime
type HealthStatus struct {
	Status         string `json:"status"`
	Version        string `json:"version"`
	Mode           string `json:"mode"`
	UptimeSeconds  int64  `json:"uptime_seconds"`
	StoreAvailable bool   `json:"store_available"`
	MemoryCount    int64  `json:"memory_count"`
}

// Check performs a full health check
func (h *HealthChecker) Check(ctx context.Context) (*HealthStatus, error) {
	status := &HealthStatus{
		Status:        "ok",
		Version:       h.ctx.Version,
		Mode:          h.ctx.Config.Mode,
		UptimeSeconds: int64(time.Since(h.ctx.StartedAt).Seconds()),
	}

	// Check store availability
	if h.ctx.Store != nil {
		count, err := h.ctx.Store.Count(ctx)
		if err != nil {
			status.StoreAvailable = false
			status.Status = "degraded"
		} else {
			status.StoreAvailable = true
			status.MemoryCount = count
		}
	} else {
		status.StoreAvailable = false
		status.Status = "unhealthy"
	}

	return status, nil
}

// LivenessCheck performs a simple liveness check
func (h *HealthChecker) LivenessCheck() error {
	if h.ctx.Store == nil {
		return ErrStoreNotAvailable
	}
	return nil
}

// ReadinessCheck performs a readiness check
func (h *HealthChecker) ReadinessCheck(ctx context.Context) error {
	if h.ctx.Store == nil {
		return ErrStoreNotAvailable
	}

	// Try a simple count operation
	_, err := h.ctx.Store.Count(ctx)
	if err != nil {
		return err
	}

	return nil
}

// Error definitions
type lifecycleError struct {
	msg string
}

func (e *lifecycleError) Error() string {
	return e.msg
}

var (
	ErrStoreNotAvailable = &lifecycleError{msg: "store not available"}
	ErrConfigInvalid     = &lifecycleError{msg: "invalid configuration"}
)
