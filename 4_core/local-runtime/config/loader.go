// config/loader.go - Configuration loading and validation
package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// LoadDefault loads configuration from default paths or creates default
func LoadDefault() (*RuntimeConfig, error) {
	// Explicit config file has highest priority.
	if explicit := strings.TrimSpace(os.Getenv("OMNIMEMORA_CONFIG")); explicit != "" {
		return LoadFromFile(ExpandPath(explicit))
	}

	// Try to find config in standard locations
	paths := []string{
		"config.json",
		"~/.omnimemora/config.json",
		"/etc/omnimemora/config.json",
	}

	for _, path := range paths {
		expanded := ExpandPath(path)
		if data, err := os.ReadFile(expanded); err == nil {
			cfg, err := LoadFromJSON(data)
			if err != nil {
				return nil, err
			}
			applyEnvOverrides(cfg)
			return cfg, nil
		}
	}

	// No config found, return defaults
	cfg := DefaultRuntimeConfig()
	applyEnvOverrides(cfg)
	return cfg, nil
}

// LoadFromJSON loads configuration from JSON data
func LoadFromJSON(data []byte) (*RuntimeConfig, error) {
	var cfg RuntimeConfig
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("invalid config JSON: %w", err)
	}

	if err := Validate(&cfg); err != nil {
		return nil, fmt.Errorf("config validation failed: %w", err)
	}

	return &cfg, nil
}

// LoadFromFile loads configuration from a file path
func LoadFromFile(path string) (*RuntimeConfig, error) {
	expanded := ExpandPath(path)
	data, err := os.ReadFile(expanded)
	if err != nil {
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}
	cfg, err := LoadFromJSON(data)
	if err != nil {
		return nil, err
	}
	applyEnvOverrides(cfg)
	return cfg, nil
}

// Validate validates the configuration
func Validate(cfg *RuntimeConfig) error {
	if cfg == nil {
		return fmt.Errorf("config is nil")
	}

	if cfg.Mode != "local" && cfg.Mode != "cloud" {
		return fmt.Errorf("invalid mode: %s (must be 'local' or 'cloud')", cfg.Mode)
	}

	if cfg.Local.DBType != "sqlite" && cfg.Local.DBType != "" {
		return fmt.Errorf("unsupported db_type: %s", cfg.Local.DBType)
	}

	validScopes := map[string]bool{
		"agent":     true,
		"workspace": true,
		"user":      true,
		"custom":    true,
	}
	if !validScopes[cfg.Scope.Default] {
		return fmt.Errorf("invalid default scope: %s", cfg.Scope.Default)
	}

	validSharingModes := map[string]bool{
		"isolated":         true,
		"shared":           true,
		"shared_read_only": true,
		"custom":           true,
	}
	if !validSharingModes[cfg.Scope.DefaultSharingMode] {
		return fmt.Errorf("invalid default_sharing_mode: %s", cfg.Scope.DefaultSharingMode)
	}

	return nil
}

// EnsureDataDir ensures the data directory exists
func EnsureDataDir(cfg *RuntimeConfig) error {
	dir := filepath.Clean(ExpandPath(cfg.Local.DataPath))

	// Create directory if not exists
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create data directory: %w", err)
	}

	return nil
}

// ExpandPath expands ~ and environment variables in a path
func ExpandPath(path string) string {
	if strings.HasPrefix(path, "~/") {
		home, err := os.UserHomeDir()
		if err == nil {
			path = filepath.Join(home, path[2:])
		}
	}
	return os.ExpandEnv(path)
}

func applyEnvOverrides(cfg *RuntimeConfig) {
	if cfg == nil {
		return
	}

	if v := strings.TrimSpace(os.Getenv("OMNIMEMORA_DATA_DIR")); v != "" {
		cfg.Local.DataPath = v
	}
	if v := strings.TrimSpace(os.Getenv("OMNIMEMORA_RUNTIME_DATA_DIR")); v != "" {
		cfg.Local.DataPath = v
	}
	if v := strings.TrimSpace(os.Getenv("OMNIMEMORA_RUNTIME_ENDPOINT")); v != "" {
		cfg.Local.Endpoint = v
	}
	if v := strings.TrimSpace(os.Getenv("OMNIMEMORA_RUNTIME_DB_TYPE")); v != "" {
		cfg.Local.DBType = v
	}
	if v := strings.TrimSpace(os.Getenv("OMNIMEMORA_RUNTIME_LOG_LEVEL")); v != "" {
		cfg.Local.LogLevel = v
	}
	if v := strings.TrimSpace(os.Getenv("OMNIMEMORA_CLOUD_BASE_URL")); v != "" {
		cfg.Cloud.BaseURL = v
	}
	if v := strings.TrimSpace(os.Getenv("OMNIMEMORA_CLOUD_API_KEY")); v != "" {
		cfg.Cloud.APIKey = v
	}
	if v := strings.TrimSpace(os.Getenv("OMNIMEMORA_CLOUD_ENABLED")); v != "" {
		if parsed, err := strconv.ParseBool(v); err == nil {
			cfg.Cloud.Enabled = parsed
		}
	}
	if v := strings.TrimSpace(os.Getenv("OMNIMEMORA_CLOUD_SYNC_INTERVAL_SECONDS")); v != "" {
		if parsed, err := strconv.Atoi(v); err == nil && parsed > 0 {
			cfg.Cloud.SyncIntervalSeconds = parsed
		}
	}
}
