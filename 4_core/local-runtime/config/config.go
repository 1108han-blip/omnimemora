// config/config.go - Configuration structures
// Aligns with RUNTIME_ARCHITECTURE.md Section 5.1
package config

// RuntimeConfig represents the runtime configuration
type RuntimeConfig struct {
	Version string         `json:"version"`
	Mode    string         `json:"mode"`
	Local   LocalConfig    `json:"local"`
	Cloud   CloudConfig    `json:"cloud"`
	Scope   ScopeConfig    `json:"scope"`
	Cache   CacheConfig    `json:"cache"`
}

// LocalConfig contains local runtime settings
type LocalConfig struct {
	Endpoint  string `json:"endpoint"`
	DataPath  string `json:"data_path"`
	DBType    string `json:"db_type"`
	LogLevel  string `json:"log_level"`
}

// CloudConfig contains optional cloud settings
type CloudConfig struct {
	Enabled            bool   `json:"enabled"`
	BaseURL            string `json:"base_url"`
	APIKey             string `json:"api_key"`
	SyncIntervalSeconds int   `json:"sync_interval_seconds"`
}

// ScopeConfig contains default scope settings
type ScopeConfig struct {
	Default           string `json:"default"`
	DefaultWorkspace  string `json:"default_workspace"`
	DefaultSharingMode string `json:"default_sharing_mode"`
}

// CacheConfig contains cache settings
type CacheConfig struct {
	Enabled    bool `json:"enabled"`
	MaxEntries int  `json:"max_entries"`
	TTLSeconds int  `json:"ttl_seconds"`
}

// DefaultRuntimeConfig returns a default configuration
func DefaultRuntimeConfig() *RuntimeConfig {
	return &RuntimeConfig{
		Version: "1.0.0",
		Mode:    "local",
		Local: LocalConfig{
			Endpoint:  "127.0.0.1",
			DataPath:  "~/.omnimemora/runtime",
			DBType:    "sqlite",
			LogLevel:  "info",
		},
		Cloud: CloudConfig{
			Enabled:            false,
			BaseURL:            "",
			APIKey:             "",
			SyncIntervalSeconds: 300,
		},
		Scope: ScopeConfig{
			Default:           "agent",
			DefaultWorkspace:  "default",
			DefaultSharingMode: "isolated",
		},
		Cache: CacheConfig{
			Enabled:    true,
			MaxEntries: 10000,
			TTLSeconds: 3600,
		},
	}
}
