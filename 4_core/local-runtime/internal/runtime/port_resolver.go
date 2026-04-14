// internal/runtime/port_resolver.go - Port Management for OmniMemora
// Automatically finds available ports with user-friendly fallback
package runtime

import (
	"fmt"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
)

// Default ports to try in order
// NOTE: These MUST match pkg/constants.go PortRuntime and fallback values
// Canonical source: pkg/constants.go
var defaultPorts = []int{8765, 8766, 8767, 8775}

// StateFile stores the runtime state (port, PID)
const stateFileName = "runtime.state"

// ResolvePort finds an available port starting from preferredPort
func ResolvePort(preferredPort int) (int, bool, error) {
	ports := []int{preferredPort}
	for _, p := range defaultPorts {
		if p != preferredPort {
			ports = append(ports, p)
		}
	}

	for _, port := range ports {
		if isPortAvailable(port) {
			return port, port != preferredPort, nil
		}
	}

	return 0, false, fmt.Errorf("no available ports in range %v", ports)
}

// isPortAvailable checks if a port is available for binding
func isPortAvailable(port int) bool {
	ln, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
	if err != nil {
		return false
	}
	ln.Close()
	return true
}

// SaveRuntimeState saves the current runtime state to disk
func SaveRuntimeState(port int, pid int) error {
	dataDir, err := GetDataDir()
	if err != nil {
		return err
	}
	stateFile := filepath.Join(dataDir, stateFileName)
	content := fmt.Sprintf("port=%d\npid=%d\n", port, pid)
	return os.WriteFile(stateFile, []byte(content), 0644)
}

// LoadRuntimeState loads the saved runtime state
func LoadRuntimeState() (port int, pid int, exists bool, err error) {
	dataDir, err := GetDataDir()
	if err != nil {
		return 0, 0, false, err
	}
	stateFile := filepath.Join(dataDir, stateFileName)

	content, err := os.ReadFile(stateFile)
	if err != nil {
		if os.IsNotExist(err) {
			return 0, 0, false, nil
		}
		return 0, 0, false, err
	}

	port = 0
	pid = 0

	// Simple parsing: port=8765\npid=1234\n
	for _, line := range splitLines(string(content)) {
		if len(line) > 5 && line[:4] == "port" && line[4] == '=' {
			port, _ = strconv.Atoi(line[5:])
		}
		if len(line) > 4 && line[:3] == "pid" && line[3] == '=' {
			pid, _ = strconv.Atoi(line[4:])
		}
	}

	return port, pid, port > 0 && pid > 0, nil
}

// ClearRuntimeState removes the runtime state file
func ClearRuntimeState() error {
	dataDir, err := GetDataDir()
	if err != nil {
		return err
	}
	stateFile := filepath.Join(dataDir, stateFileName)
	err = os.Remove(stateFile)
	if os.IsNotExist(err) {
		return nil
	}
	return err
}

// IsProcessRunning checks if a process with given PID is running
func IsProcessRunning(pid int) bool {
	if pid <= 0 {
		return false
	}
	process, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	// On Unix, signal 0 doesn't send anything but checks if process exists
	err = process.Signal(os.Signal(nil))
	return err == nil
}

// GetDataDir returns the OmniMemora data directory
func GetDataDir() (string, error) {
	// Priority:
	// 1) OMNIMEMORA_RUNTIME_DATA_DIR
	// 2) OMNIMEMORA_DATA_DIR
	// 3) ~/.omnimemora
	if v := strings.TrimSpace(os.Getenv("OMNIMEMORA_RUNTIME_DATA_DIR")); v != "" {
		return filepath.Clean(os.ExpandEnv(v)), nil
	}
	if v := strings.TrimSpace(os.Getenv("OMNIMEMORA_DATA_DIR")); v != "" {
		return filepath.Clean(os.ExpandEnv(v)), nil
	}
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("failed to get home directory: %w", err)
	}
	return filepath.Join(homeDir, ".omnimemora"), nil
}

// GetRuntimePort returns the current runtime port from state file
func GetRuntimePort() (int, error) {
	port, _, exists, err := LoadRuntimeState()
	if err != nil {
		return 0, err
	}
	if !exists {
		return 0, fmt.Errorf("runtime not running (no state file)")
	}
	return port, nil
}

var (
	homeDirOnce sync.Once
	homeDir     string
	homeDirErr  error
)

func getHomeDir() (string, error) {
	homeDirOnce.Do(func() {
		homeDir, homeDirErr = os.UserHomeDir()
	})
	return homeDir, homeDirErr
}

func splitLines(s string) []string {
	var lines []string
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == '\n' {
			lines = append(lines, s[start:i])
			start = i + 1
		}
	}
	if start < len(s) {
		lines = append(lines, s[start:])
	}
	return lines
}
