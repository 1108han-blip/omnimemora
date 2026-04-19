package attach

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type openClawLayeredBackupMetadata struct {
	GlobalConfigPath string `json:"global_config_path"`
	GlobalExisted    bool   `json:"global_existed"`
	AgentModelsPath  string `json:"agent_models_path"`
	AgentExisted     bool   `json:"agent_existed"`
}

func openClawLayeredBackupMetaPath() (string, error) {
	root, err := backupRootDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(root, "openclaw.layered.meta.json"), nil
}

func openClawLayeredGlobalBackupDataPath() (string, error) {
	root, err := backupRootDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(root, "openclaw.global.backup"), nil
}

func openClawLayeredAgentBackupDataPath() (string, error) {
	root, err := backupRootDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(root, "openclaw.agent_models.backup"), nil
}

func openClawLayeredBackupExists() bool {
	metaPath, err := openClawLayeredBackupMetaPath()
	if err != nil {
		return false
	}
	_, err = os.Stat(metaPath)
	return err == nil
}

func backupOpenClawConfigs(globalConfigPath, agentModelsPath string) error {
	if openClawLayeredBackupExists() || backupExistsLegacyOpenClaw() {
		return nil
	}

	root, err := backupRootDir()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(root, 0o755); err != nil {
		return err
	}

	meta := openClawLayeredBackupMetadata{
		GlobalConfigPath: globalConfigPath,
		AgentModelsPath:  agentModelsPath,
	}

	if data, err := os.ReadFile(globalConfigPath); err == nil {
		dataPath, pathErr := openClawLayeredGlobalBackupDataPath()
		if pathErr != nil {
			return pathErr
		}
		if err := os.WriteFile(dataPath, data, 0o644); err != nil {
			return err
		}
		meta.GlobalExisted = true
	} else if !os.IsNotExist(err) {
		return err
	}

	if data, err := os.ReadFile(agentModelsPath); err == nil {
		dataPath, pathErr := openClawLayeredAgentBackupDataPath()
		if pathErr != nil {
			return pathErr
		}
		if err := os.WriteFile(dataPath, data, 0o644); err != nil {
			return err
		}
		meta.AgentExisted = true
	} else if !os.IsNotExist(err) {
		return err
	}

	metaPath, err := openClawLayeredBackupMetaPath()
	if err != nil {
		return err
	}
	raw, err := json.MarshalIndent(meta, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(metaPath, raw, 0o644)
}

func restoreOpenClawLayeredBackup() (bool, error) {
	metaPath, err := openClawLayeredBackupMetaPath()
	if err != nil {
		return false, err
	}
	metaData, err := os.ReadFile(metaPath)
	if err != nil {
		if os.IsNotExist(err) {
			return false, nil
		}
		return false, err
	}

	var meta openClawLayeredBackupMetadata
	if err := json.Unmarshal(metaData, &meta); err != nil {
		return false, err
	}

	if err := restoreOpenClawLayer(meta.GlobalConfigPath, meta.GlobalExisted, openClawLayeredGlobalBackupDataPath); err != nil {
		return false, err
	}
	if err := restoreOpenClawLayer(meta.AgentModelsPath, meta.AgentExisted, openClawLayeredAgentBackupDataPath); err != nil {
		return false, err
	}

	globalDataPath, _ := openClawLayeredGlobalBackupDataPath()
	agentDataPath, _ := openClawLayeredAgentBackupDataPath()
	_ = os.Remove(globalDataPath)
	_ = os.Remove(agentDataPath)
	_ = os.Remove(metaPath)
	return true, nil
}

func restoreOpenClawLayer(targetPath string, existed bool, dataPathFn func() (string, error)) error {
	if err := os.MkdirAll(filepath.Dir(targetPath), 0o755); err != nil {
		return err
	}

	if existed {
		dataPath, err := dataPathFn()
		if err != nil {
			return err
		}
		data, err := os.ReadFile(dataPath)
		if err != nil {
			return err
		}
		return os.WriteFile(targetPath, data, 0o644)
	}

	if err := os.Remove(targetPath); err != nil && !os.IsNotExist(err) {
		return err
	}
	return nil
}

func backupExistsLegacyOpenClaw() bool {
	metaPath, err := backupMetaPath(AgentOpenClaw)
	if err != nil {
		return false
	}
	_, err = os.Stat(metaPath)
	return err == nil
}
