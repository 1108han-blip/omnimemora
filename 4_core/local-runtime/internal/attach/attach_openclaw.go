// internal/attach/attach_openclaw.go - OpenClaw Attachment Implementation
package attach

import (
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

const (
	openClawMainAgentID = "main"
)

type openClawConfigLayer string

const (
	openClawConfigLayerGlobal openClawConfigLayer = "global"
	openClawConfigLayerAgent  openClawConfigLayer = "agent"
)

type openClawResolvedConfig struct {
	globalPath      string
	agentModelsPath string
	globalCfg       map[string]interface{}
	agentCfg        map[string]interface{}
	mainModel       string
	providerID      string
	effectiveLayer  openClawConfigLayer
}

// AttachOpenClaw attaches OmniMemora to OpenClaw.
func AttachOpenClaw() *AttachResult {
	result := &AttachResult{Agent: AgentOpenClaw, Success: false}

	resolved, err := loadOpenClawResolvedConfig()
	if err != nil {
		result.Message = err.Error()
		return result
	}

	if err := EnsureConfigDir(AgentOpenClaw); err != nil {
		result.Message = "Failed to create OpenClaw config directory"
		return result
	}
	if err := os.MkdirAll(filepath.Dir(resolved.agentModelsPath), 0o755); err != nil {
		result.Message = "Failed to create OpenClaw agent config directory"
		return result
	}
	if err := backupOpenClawConfigs(resolved.globalPath, resolved.agentModelsPath); err != nil {
		result.Message = "Failed to back up OpenClaw config layers"
		return result
	}

	delete(resolved.globalCfg, "omnimemora")
	ensureOpenClawMCPAttachment(resolved.globalCfg)

	targetCfg := resolved.globalCfg
	targetProviders := ensureOpenClawGlobalProviders(resolved.globalCfg)
	if resolved.effectiveLayer == openClawConfigLayerAgent {
		targetCfg = resolved.agentCfg
		targetProviders = ensureOpenClawAgentProviders(resolved.agentCfg)
	}

	currentProvider, ok := asStringMap(targetProviders[resolved.providerID])
	if !ok {
		result.Message = fmt.Sprintf("OpenClaw main provider %q missing from %s layer", resolved.providerID, resolved.effectiveLayer)
		return result
	}
	currentProvider["baseUrl"] = openClawProductBaseURL(currentProvider)
	targetProviders[resolved.providerID] = currentProvider

	if resolved.effectiveLayer == openClawConfigLayerAgent {
		targetCfg["providers"] = targetProviders
	} else {
		models := ensureStringMap(resolved.globalCfg, "models")
		models["providers"] = targetProviders
		resolved.globalCfg["models"] = models
	}

	if err := WriteConfig(resolved.globalPath, resolved.globalCfg); err != nil {
		result.Message = "Failed to write OpenClaw global config"
		return result
	}
	result.ConfigWriten = true

	if resolved.effectiveLayer == openClawConfigLayerAgent || fileExists(resolved.agentModelsPath) {
		if err := WriteConfig(resolved.agentModelsPath, resolved.agentCfg); err != nil {
			result.Message = "Failed to write OpenClaw agent models config"
			return result
		}
		result.ConfigWriten = true
	}

	if !isOpenClawAttached(ProductAdapterPort()) {
		result.Message = "OpenClaw config written but effective request ingress is not attached to product"
		return result
	}

	validateCmd := exec.Command("openclaw", "config", "validate")
	output, err := validateCmd.CombinedOutput()
	if err != nil {
		result.Message = fmt.Sprintf("Config written and verified, but openclaw config validate failed: %s", strings.TrimSpace(string(output)))
		return result
	}

	result.Success = true
	result.Message = fmt.Sprintf("Attached successfully via %s layer", resolved.effectiveLayer)
	_ = RestartAgent(AgentOpenClaw)
	return result
}

// DetachOpenClaw removes OmniMemora from OpenClaw config.
func DetachOpenClaw() error {
	if restored, err := RestoreBackup(AgentOpenClaw); err != nil {
		return err
	} else if restored {
		return nil
	}

	configPath, err := GetConfigPath(AgentOpenClaw)
	if err != nil {
		return err
	}

	var cfg map[string]interface{}
	if data, err := os.ReadFile(configPath); err == nil {
		if err := json.Unmarshal(data, &cfg); err == nil {
			modified := false

			if _, ok := cfg["omnimemora"]; ok {
				delete(cfg, "omnimemora")
				modified = true
			}

			if mcp, ok := cfg["mcp"].(map[string]interface{}); ok {
				if servers, ok := mcp["servers"].(map[string]interface{}); ok {
					if _, ok := servers["omnimemora"]; ok {
						delete(servers, "omnimemora")
						modified = true
					}
					if len(servers) == 0 {
						delete(mcp, "servers")
					} else {
						mcp["servers"] = servers
					}
				}
				if len(mcp) == 0 {
					delete(cfg, "mcp")
				} else {
					cfg["mcp"] = mcp
				}
			}

			if modified {
				data, err := json.MarshalIndent(cfg, "", "  ")
				if err != nil {
					return err
				}
				return os.WriteFile(configPath, data, 0o644)
			}
		}
	}

	return fmt.Errorf("config not found")
}

func isOpenClawAttached(port int) bool {
	resolved, err := loadOpenClawResolvedConfig()
	if err != nil {
		return false
	}

	if !hasOpenClawMCPAttachment(resolved.globalCfg, port) {
		return false
	}

	providers := openClawEffectiveProviders(resolved)
	providerCfg, ok := asStringMap(providers[resolved.providerID])
	if !ok {
		return false
	}
	baseURL, _ := providerCfg["baseUrl"].(string)
	return openClawTargetsProductIngress(baseURL, port)
}

func loadOpenClawResolvedConfig() (*openClawResolvedConfig, error) {
	globalPath, err := GetConfigPath(AgentOpenClaw)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve OpenClaw config path")
	}
	agentModelsPath, err := getOpenClawAgentModelsPath()
	if err != nil {
		return nil, fmt.Errorf("failed to resolve OpenClaw agent models path")
	}

	globalCfg, err := ReadConfig(globalPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read OpenClaw global config: %w", err)
	}
	agentCfg, err := ReadConfig(agentModelsPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read OpenClaw agent models config: %w", err)
	}

	mainModel := openClawMainModel(globalCfg)
	if mainModel == "" {
		return nil, fmt.Errorf("failed to resolve OpenClaw main agent model")
	}
	providerID := openClawProviderID(mainModel)
	if providerID == "" {
		return nil, fmt.Errorf("failed to resolve OpenClaw provider from main model %q", mainModel)
	}

	layer := openClawConfigLayerGlobal
	if _, ok := asStringMap(openClawAgentProviders(agentCfg)[providerID]); ok {
		layer = openClawConfigLayerAgent
	}

	return &openClawResolvedConfig{
		globalPath:      globalPath,
		agentModelsPath: agentModelsPath,
		globalCfg:       globalCfg,
		agentCfg:        agentCfg,
		mainModel:       mainModel,
		providerID:      providerID,
		effectiveLayer:  layer,
	}, nil
}

func getOpenClawAgentModelsPath() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(home, ".openclaw", "agents", openClawMainAgentID, "agent", "models.json"), nil
}

func openClawMainModel(cfg map[string]interface{}) string {
	agents, ok := asStringMap(cfg["agents"])
	if !ok {
		return ""
	}

	if rawList, ok := agents["list"].([]interface{}); ok {
		for _, item := range rawList {
			entry, ok := asStringMap(item)
			if !ok {
				continue
			}
			if entryID, _ := entry["id"].(string); entryID == openClawMainAgentID {
				if model, _ := entry["model"].(string); strings.TrimSpace(model) != "" {
					return strings.TrimSpace(model)
				}
			}
		}
	}

	defaults, ok := asStringMap(agents["defaults"])
	if !ok {
		return ""
	}
	modelCfg, ok := asStringMap(defaults["model"])
	if !ok {
		return ""
	}
	model, _ := modelCfg["primary"].(string)
	return strings.TrimSpace(model)
}

func openClawProviderID(model string) string {
	head, _, _ := strings.Cut(strings.TrimSpace(model), "/")
	return strings.TrimSpace(head)
}

func ensureOpenClawMCPAttachment(cfg map[string]interface{}) {
	mcp := ensureStringMap(cfg, "mcp")
	servers := ensureStringMap(mcp, "servers")
	servers["omnimemora"] = map[string]interface{}{
		"url":  ProductAdapterOpenClawMCPEndpoint(),
		"type": "http",
	}
	mcp["servers"] = servers
	cfg["mcp"] = mcp
}

func hasOpenClawMCPAttachment(cfg map[string]interface{}, port int) bool {
	mcp, ok := asStringMap(cfg["mcp"])
	if !ok {
		return false
	}
	servers, ok := asStringMap(mcp["servers"])
	if !ok {
		return false
	}
	entry, ok := asStringMap(servers["omnimemora"])
	if !ok {
		return false
	}
	rawURL, _ := entry["url"].(string)
	rawURL = strings.TrimSpace(rawURL)
	expectedSSE := fmt.Sprintf("http://127.0.0.1:%d/sse", port)
	expectedMCP := fmt.Sprintf("http://127.0.0.1:%d/mcp", port)
	return strings.EqualFold(rawURL, expectedSSE) ||
		strings.EqualFold(rawURL, expectedMCP) ||
		strings.Contains(strings.ToLower(rawURL), "omnimemora")
}

func openClawEffectiveProviders(resolved *openClawResolvedConfig) map[string]interface{} {
	if resolved.effectiveLayer == openClawConfigLayerAgent {
		return openClawAgentProviders(resolved.agentCfg)
	}
	return openClawGlobalProviders(resolved.globalCfg)
}

func openClawGlobalProviders(cfg map[string]interface{}) map[string]interface{} {
	models, ok := asStringMap(cfg["models"])
	if !ok {
		return map[string]interface{}{}
	}
	providers, ok := asStringMap(models["providers"])
	if !ok {
		return map[string]interface{}{}
	}
	return providers
}

func ensureOpenClawGlobalProviders(cfg map[string]interface{}) map[string]interface{} {
	models := ensureStringMap(cfg, "models")
	providers := ensureStringMap(models, "providers")
	models["providers"] = providers
	cfg["models"] = models
	return providers
}

func openClawAgentProviders(cfg map[string]interface{}) map[string]interface{} {
	providers, ok := asStringMap(cfg["providers"])
	if !ok {
		return map[string]interface{}{}
	}
	return providers
}

func ensureOpenClawAgentProviders(cfg map[string]interface{}) map[string]interface{} {
	providers := ensureStringMap(cfg, "providers")
	cfg["providers"] = providers
	return providers
}

func openClawProductBaseURL(providerCfg map[string]interface{}) string {
	api, _ := providerCfg["api"].(string)
	switch strings.TrimSpace(api) {
	case "anthropic-messages":
		return fmt.Sprintf("%s/llm", ProductAdapterEndpoint())
	case "openai-codex-responses":
		return ProductAdapterResponsesEndpoint()
	case "openai-completions":
		return fmt.Sprintf("%s/llm/v1", ProductAdapterEndpoint())
	default:
		existing, _ := providerCfg["baseUrl"].(string)
		switch {
		case strings.Contains(existing, "/v1"):
			return ProductAdapterResponsesEndpoint()
		case strings.Contains(existing, "/anthropic"):
			return fmt.Sprintf("%s/llm", ProductAdapterEndpoint())
		default:
			return ProductAdapterEndpoint()
		}
	}
}

func openClawTargetsProductIngress(raw string, port int) bool {
	parsed, err := url.Parse(strings.TrimSpace(raw))
	if err != nil {
		return false
	}
	if parsed.Hostname() != "127.0.0.1" && !strings.EqualFold(parsed.Hostname(), "localhost") {
		return false
	}
	if parsed.Port() != fmt.Sprintf("%d", port) {
		return false
	}

	switch strings.TrimRight(parsed.Path, "/") {
	case "", "/llm", "/llm/v1", "/v1":
		return true
	default:
		return false
	}
}

func ensureStringMap(parent map[string]interface{}, key string) map[string]interface{} {
	if existing, ok := asStringMap(parent[key]); ok {
		return existing
	}
	created := map[string]interface{}{}
	parent[key] = created
	return created
}

func asStringMap(value interface{}) (map[string]interface{}, bool) {
	if value == nil {
		return nil, false
	}
	if typed, ok := value.(map[string]interface{}); ok {
		return typed, true
	}
	return nil, false
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}
