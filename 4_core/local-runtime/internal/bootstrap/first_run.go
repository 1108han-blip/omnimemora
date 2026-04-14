// internal/bootstrap/first_run.go - First-Run Bootstrap for OmniMemora
// Handles initialization, demo data seeding, and first-run detection
package bootstrap

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/omnimemora/local-runtime/internal/demo"
	"github.com/omnimemora/local-runtime/internal/runtime"
)

// BootstrapResult contains the results of bootstrap operation
type BootstrapResult struct {
	Initialized   bool
	DemoExecuted  bool
	Port          int
	DataDir       string
	FirstRun      bool
}

// Bootstrap performs first-run initialization if needed
func Bootstrap() (*BootstrapResult, error) {
	result := &BootstrapResult{}

	// Get data directory
	dataDir, err := runtime.GetDataDir()
	if err != nil {
		return nil, fmt.Errorf("failed to get data directory: %w", err)
	}
	result.DataDir = dataDir

	// Create directory structure
	if err := createDirs(dataDir); err != nil {
		return nil, fmt.Errorf("failed to create directories: %w", err)
	}

	// Check if first run
	isFirstRun, err := isFirstRun(dataDir)
	if err != nil {
		return nil, fmt.Errorf("failed to check first run status: %w", err)
	}
	result.FirstRun = isFirstRun

	if isFirstRun {
		// Mark as initialized BEFORE demo seeding (prevents re-entry on crash)
		if err := markInitialized(dataDir); err != nil {
			return nil, fmt.Errorf("failed to mark initialized: %w", err)
		}
		result.Initialized = true

		// Execute demo seed
		if err := demo.SeedData(); err != nil {
			return nil, fmt.Errorf("demo seed failed: %w", err)
		}
		result.DemoExecuted = true
	}

	return result, nil
}

// createDirs creates the required directory structure
func createDirs(dataDir string) error {
	dirs := []string{
		dataDir,
		filepath.Join(dataDir, "config"),
		filepath.Join(dataDir, "runtime"),
		filepath.Join(dataDir, "logs"),
		filepath.Join(dataDir, "bootstrap"),
	}

	for _, dir := range dirs {
		if err := os.MkdirAll(dir, 0755); err != nil {
			return fmt.Errorf("failed to create directory %s: %w", dir, err)
		}
	}

	return nil
}

// isFirstRun checks if this is the first time OmniMemora is running
func isFirstRun(dataDir string) (bool, error) {
	bootstrapDir := filepath.Join(dataDir, "bootstrap")
	markerFile := filepath.Join(bootstrapDir, "first_run_done")

	// Check if marker exists
	if _, err := os.Stat(markerFile); err == nil {
		return false, nil // Marker exists, not first run
	} else if os.IsNotExist(err) {
		return true, nil // Marker doesn't exist, first run
	} else {
		return false, err // Other error
	}
}

// markInitialized marks that first run has completed
func markInitialized(dataDir string) error {
	bootstrapDir := filepath.Join(dataDir, "bootstrap")
	markerFile := filepath.Join(bootstrapDir, "first_run_done")

	content := fmt.Sprintf("# OmniMemora First Run Marker\n# Created: %s\ninitialized=true\n", time.Now().UTC().Format(time.RFC3339))

	return os.WriteFile(markerFile, []byte(content), 0644)
}

// GetDataDir returns the OmniMemora data directory
func GetDataDir() (string, error) {
	return runtime.GetDataDir()
}
