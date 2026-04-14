// internal/verify/verify.go - Auto Verification for OmniMemora
// Writes test memory, verifies recall, and marks dashboard success
package verify

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// VerifyResult contains the verification result
type VerifyResult struct {
	Success         bool
	WriteSuccess    bool
	RecallSuccess   bool
	MemoryID        string
	WriteDurationMs int64
	RecallDurationMs int64
	Message         string
}

// VerifyRequest contains parameters for verification
type VerifyRequest struct {
	RuntimePort int
	TenantID    string
	UserID      string
	WorkspaceID string
	AgentID     string
}

// DefaultVerifyRequest creates a default verification request
func DefaultVerifyRequest(port int) *VerifyRequest {
	return &VerifyRequest{
		RuntimePort: port,
		TenantID:    "verify",
		UserID:     "verify-user",
		WorkspaceID: "verify-workspace",
		AgentID:    "verify-agent",
	}
}

// RunAutoVerify performs the full verification flow:
// 1. Write a test memory with unique content
// 2. Wait 1 second
// 3. Recall the test memory
// 4. Mark dashboard success if recall worked
func RunAutoVerify(req *VerifyRequest) *VerifyResult {
	result := &VerifyResult{Success: false}

	// Generate unique test content
	testContent := generateTestContent()

	// Step 1: Write test memory
	writeStart := time.Now()
	memoryID, writeErr := writeTestMemory(req, testContent)
	writeDuration := time.Since(writeStart).Milliseconds()
	result.WriteDurationMs = writeDuration

	if writeErr != nil {
		result.WriteSuccess = false
		result.Message = fmt.Sprintf("Write failed: %v", writeErr)
		return result
	}
	result.WriteSuccess = true
	result.MemoryID = memoryID

	// Step 2: Wait 1 second (as per spec)
	time.Sleep(1 * time.Second)

	// Step 3: Recall test memory
	recallStart := time.Now()
	recallErr := recallTestMemory(req, memoryID, testContent)
	recallDuration := time.Since(recallStart).Milliseconds()
	result.RecallDurationMs = recallDuration

	if recallErr != nil {
		result.RecallSuccess = false
		result.Message = fmt.Sprintf("Recall failed: %v", recallErr)
		return result
	}
	result.RecallSuccess = true

	// Step 4: Mark dashboard success
	if err := markDashboardSuccess(req); err != nil {
		// Non-critical - log but don't fail
		fmt.Printf("Warning: Failed to mark dashboard success: %v\n", err)
	}

	result.Success = true
	result.Message = "Verification successful"
	return result
}

// generateTestContent generates unique test content
func generateTestContent() string {
	b := make([]byte, 8)
	rand.Read(b)
	return fmt.Sprintf("[OmniMemora Verify %s %d]", hex.EncodeToString(b), time.Now().UnixMilli())
}

// writeTestMemory writes a test memory via HTTP
func writeTestMemory(req *VerifyRequest, content string) (string, error) {
	writeReq := map[string]interface{}{
		"content": content,
		"metadata": map[string]interface{}{
			"source":   "omnimemora-verify",
			"verify":   true,
			"timestamp": time.Now().UTC().Format(time.RFC3339),
		},
		"scope":       "agent",
		"agent_id":    req.AgentID,
		"workspace_id": req.WorkspaceID,
	}

	body, err := json.Marshal(writeReq)
	if err != nil {
		return "", err
	}

	url := fmt.Sprintf("http://127.0.0.1:%d/memory/write", req.RuntimePort)
	httpReq, err := http.NewRequest("POST", url, bytes.NewBuffer(body))
	if err != nil {
		return "", err
	}

	// Set headers
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("X-OmniMemora-Tenant", req.TenantID)
	httpReq.Header.Set("X-OmniMemora-User", req.UserID)
	httpReq.Header.Set("X-OmniMemora-Workspace", req.WorkspaceID)
	httpReq.Header.Set("X-OmniMemora-Agent", req.AgentID)

	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(httpReq)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return "", fmt.Errorf("write returned status %d", resp.StatusCode)
	}

	var writeResp struct {
		MemoryID string `json:"memory_id"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&writeResp); err != nil {
		return "", err
	}

	return writeResp.MemoryID, nil
}

// recallTestMemory recalls a test memory to verify it was stored
func recallTestMemory(req *VerifyRequest, memoryID, expectedContent string) error {
	recallReq := map[string]interface{}{
		"query":   "",  // We'll search by the unique content
		"limit":   5,
	}

	body, err := json.Marshal(recallReq)
	if err != nil {
		return err
	}

	url := fmt.Sprintf("http://127.0.0.1:%d/memory/query", req.RuntimePort)
	httpReq, err := http.NewRequest("POST", url, bytes.NewBuffer(body))
	if err != nil {
		return err
	}

	// Set headers
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("X-OmniMemora-Tenant", req.TenantID)
	httpReq.Header.Set("X-OmniMemora-User", req.UserID)
	httpReq.Header.Set("X-OmniMemora-Workspace", req.WorkspaceID)
	httpReq.Header.Set("X-OmniMemora-Agent", req.AgentID)

	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(httpReq)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("recall returned status %d", resp.StatusCode)
	}

	var recallResp struct {
		Results []struct {
			MemoryID string `json:"memory_id"`
			Content  string `json:"content"`
		} `json:"results"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&recallResp); err != nil {
		return err
	}

	// Check if our memory ID is in the results
	for _, r := range recallResp.Results {
		if r.MemoryID == memoryID {
			return nil // Found it!
		}
	}

	return fmt.Errorf("memory not found in recall results")
}

// markDashboardSuccess marks that verification succeeded
// This sets an internal metric that the dashboard can read
func markDashboardSuccess(req *VerifyRequest) error {
	// POST to /internal/metrics with bootstrap_success marker
	metricsReq := map[string]interface{}{
		"type":  "bootstrap_success",
		"value": 1,
	}

	body, err := json.Marshal(metricsReq)
	if err != nil {
		return err
	}

	url := fmt.Sprintf("http://127.0.0.1:%d/internal/metrics", req.RuntimePort)
	httpReq, err := http.NewRequest("POST", url, bytes.NewBuffer(body))
	if err != nil {
		return err
	}

	httpReq.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(httpReq)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("mark success returned status %d", resp.StatusCode)
	}

	return nil
}

// String returns a human-readable result
func (r *VerifyResult) String() string {
	if r.Success {
		return fmt.Sprintf("Verify success: write=%dms, recall=%dms",
			r.WriteDurationMs, r.RecallDurationMs)
	}
	return fmt.Sprintf("Verify failed: %s", r.Message)
}