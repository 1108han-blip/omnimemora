// OmniMemora Local Runtime - Phase 1 Minimal Runnable Implementation
// Local-first Memory Plane with SQLite store, scope governance, and metering
package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/omnimemora/local-runtime/api"
	"github.com/omnimemora/local-runtime/config"
	"github.com/omnimemora/local-runtime/internal/runtime"
	"github.com/omnimemora/local-runtime/lifecycle"
	"github.com/omnimemora/local-runtime/pkg"
	"github.com/omnimemora/local-runtime/store"
)

const (
	Version = "1.0.0"
)

func resolvePreferredRuntimePort() int {
	raw := os.Getenv("OMNIMEMORA_RUNTIME_PORT")
	if raw == "" {
		return pkg.PortRuntime
	}
	parsed, err := strconv.Atoi(raw)
	if err != nil || parsed <= 0 {
		log.Printf("Warning: invalid OMNIMEMORA_RUNTIME_PORT=%q, using default %d", raw, pkg.PortRuntime)
		return pkg.PortRuntime
	}
	return parsed
}

func main() {
	log.SetFlags(log.LstdFlags | log.Lshortfile)
	log.Printf("OmniMemora Local Runtime v%s starting...", Version)

	// Load configuration
	cfg, err := config.LoadDefault()
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	// Initialize store
	var s store.Store
	switch cfg.Local.DBType {
	case "sqlite", "":
		s, err = store.NewSQLiteStore(cfg.Local.DataPath)
	default:
		log.Fatalf("Unsupported DB type: %s", cfg.Local.DBType)
	}
	if err != nil {
		log.Fatalf("Failed to initialize store: %v", err)
	}
	defer s.Close()

	// Create runtime context
	rtCtx := &lifecycle.RuntimeContext{
		Config:    cfg,
		Store:      s,
		Version:    Version,
		StartedAt:  time.Now(),
	}

	// Resolve port (8765 or next available, see pkg/constants.go for canonical ports)
	preferredPort := resolvePreferredRuntimePort()
	port, fellBack, err := runtime.ResolvePort(preferredPort)
	if err != nil {
		log.Fatalf("Failed to resolve port: %v", err)
	}
	if fellBack {
		log.Printf("Warning: Preferred port %d unavailable, using %d", preferredPort, port)
	}

	// Save runtime state for adapter discovery
	if err := runtime.SaveRuntimeState(port, os.Getpid()); err != nil {
		log.Printf("Warning: Failed to save runtime state: %v", err)
	}

	// Initialize HTTP server
	server := api.NewServer(cfg, s, rtCtx, port)

	// Start server in goroutine
	serverAddr := fmt.Sprintf("%s:%d", cfg.Local.Endpoint, port)
	go func() {
		log.Printf("Server listening on %s (port %d)", serverAddr, port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	// Wait for shutdown signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")

	// Graceful shutdown with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		log.Printf("Server shutdown error: %v", err)
	}

	log.Println("Server stopped")
}
