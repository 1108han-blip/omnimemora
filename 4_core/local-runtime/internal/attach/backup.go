package attach

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

type backupMetadata struct {
	Agent      string `json:"agent"`
	ConfigPath string `json:"config_path"`
	Existed    bool   `json:"existed"`
}

func backupRootDir() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(home, ".omnimemora", "agent-control", "backups"), nil
}

func backupDataPath(agent AgentType) (string, error) {
	root, err := backupRootDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(root, fmt.Sprintf("%s.backup", string(agent))), nil
}

func backupMetaPath(agent AgentType) (string, error) {
	root, err := backupRootDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(root, fmt.Sprintf("%s.meta.json", string(agent))), nil
}

func BackupExists(agent AgentType) bool {
	metaPath, err := backupMetaPath(agent)
	if err != nil {
		return false
	}
	_, err = os.Stat(metaPath)
	return err == nil
}

func BackupConfig(agent AgentType) error {
	if BackupExists(agent) {
		return nil
	}

	configPath, err := GetConfigPath(agent)
	if err != nil {
		return err
	}

	root, err := backupRootDir()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(root, 0755); err != nil {
		return err
	}

	meta := backupMetadata{
		Agent:      string(agent),
		ConfigPath: configPath,
	}

	dataPath, err := backupDataPath(agent)
	if err != nil {
		return err
	}
	if data, err := os.ReadFile(configPath); err == nil {
		if err := os.WriteFile(dataPath, data, 0644); err != nil {
			return err
		}
		meta.Existed = true
	} else if !os.IsNotExist(err) {
		return err
	}

	metaPath, err := backupMetaPath(agent)
	if err != nil {
		return err
	}
	metaData, err := json.MarshalIndent(meta, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(metaPath, metaData, 0644)
}

func RestoreBackup(agent AgentType) (bool, error) {
	metaPath, err := backupMetaPath(agent)
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

	var meta backupMetadata
	if err := json.Unmarshal(metaData, &meta); err != nil {
		return false, err
	}

	if err := os.MkdirAll(filepath.Dir(meta.ConfigPath), 0755); err != nil {
		return false, err
	}

	dataPath, err := backupDataPath(agent)
	if err != nil {
		return false, err
	}

	if meta.Existed {
		data, err := os.ReadFile(dataPath)
		if err != nil {
			return false, err
		}
		if err := os.WriteFile(meta.ConfigPath, data, 0644); err != nil {
			return false, err
		}
	} else if err := os.Remove(meta.ConfigPath); err != nil && !os.IsNotExist(err) {
		return false, err
	}

	_ = os.Remove(dataPath)
	_ = os.Remove(metaPath)
	return true, nil
}
