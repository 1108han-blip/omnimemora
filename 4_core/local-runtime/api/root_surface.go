package api

import (
	"net/http"
	"strings"
)

func registerRootRoutes(mux *http.ServeMux, server *Server) {
	mux.HandleFunc("GET /", server.handleRoot)
}

func (s *Server) handleRoot(w http.ResponseWriter, r *http.Request) {
	if strings.Contains(strings.ToLower(r.Header.Get("Accept")), "text/event-stream") {
		s.handleMCPSSE(w, r)
		return
	}
	http.Redirect(w, r, "/dashboard", http.StatusTemporaryRedirect)
}
