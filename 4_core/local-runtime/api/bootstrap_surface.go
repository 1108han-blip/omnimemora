package api

import (
	"encoding/json"
	"net/http"
)

type bootstrapMetricsRequest struct {
	Type  string `json:"type"`
	Value int    `json:"value"`
}

func registerBootstrapRoutes(mux *http.ServeMux, server *Server) {
	mux.HandleFunc("POST /internal/metrics", server.handleInternalMetrics)
}

// handleInternalMetrics handles POST /internal/metrics for bootstrap verification.
// It is an internal bootstrap/control surface, not a capability-plane endpoint.
func (s *Server) handleInternalMetrics(w http.ResponseWriter, r *http.Request) {
	var req bootstrapMetricsRequest

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, 400, "INVALID_REQUEST", "invalid JSON body")
		return
	}

	switch req.Type {
	case "bootstrap_success":
		s.bootstrap.setSuccess(true)
		writeJSON(w, 200, map[string]string{"status": "ok"})
	default:
		writeError(w, 400, "UNKNOWN_TYPE", "unknown metrics type")
	}
}
