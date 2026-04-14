// api/middleware.go - HTTP middleware
// Scope resolution priority per RUNTIME_ARCHITECTURE.md: Header > Body > Config
package api

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/omnimemora/local-runtime/pkg"
	"github.com/omnimemora/local-runtime/scope"
)

// Context keys for middleware values
type contextKey string

const (
	scopeContextKey contextKey = "scope_ref"
	requestIDKey    contextKey = "request_id"
	startTimeKey    contextKey = "start_time"
)

// requestIDMiddleware injects request ID into context
func requestIDMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestID := r.Header.Get("X-OmniMemora-Request-Id")
		if requestID == "" {
			requestID = generateRequestID()
		}
		w.Header().Set("X-OmniMemora-Request-Id", requestID)

		ctx := context.WithValue(r.Context(), requestIDKey, requestID)
		ctx = context.WithValue(ctx, startTimeKey, time.Now())
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// loggingMiddleware logs requests
func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		startTime, _ := r.Context().Value(startTimeKey).(time.Time)
		requestID, _ := r.Context().Value(requestIDKey).(string)
		if startTime.IsZero() {
			startTime = time.Now()
		}

		// ADR-0006 §4: Warn if external (non-loopback) address accesses this internal backend
		if !isLoopback(r.RemoteAddr) {
			log.Printf("[WARN] [request_id=%s] external direct access to internal backend at %s%s — "+
				"external agents must use product entry at 127.0.0.1:18011",
				requestID, r.Host, r.URL.Path)
		}

		rec := &statusRecorder{ResponseWriter: w, statusCode: http.StatusOK}

		log.Printf(
			"[request_id=%s] start method=%s path=%s tenant=%s user=%s workspace=%s agent=%s scope=%s",
			requestID,
			r.Method,
			r.URL.Path,
			valueOrDash(r.Header.Get("X-OmniMemora-Tenant")),
			valueOrDash(r.Header.Get("X-OmniMemora-User")),
			valueOrDash(r.Header.Get("X-OmniMemora-Workspace")),
			valueOrDash(r.Header.Get("X-OmniMemora-Agent")),
			valueOrDash(r.Header.Get("X-OmniMemora-Scope")),
		)

		next.ServeHTTP(rec, r)

		took := time.Since(startTime)
		level := "INFO"
		if rec.statusCode >= http.StatusInternalServerError {
			level = "ERROR"
		} else if rec.statusCode >= http.StatusBadRequest {
			level = "WARN"
		}
		log.Printf(
			"[%s] [request_id=%s] done method=%s path=%s status=%d took_ms=%d bytes=%d",
			level,
			requestID,
			r.Method,
			r.URL.Path,
			rec.statusCode,
			took.Milliseconds(),
			rec.bytesWritten,
		)
	})
}

type statusRecorder struct {
	http.ResponseWriter
	statusCode   int
	bytesWritten int
}

func (r *statusRecorder) WriteHeader(statusCode int) {
	r.statusCode = statusCode
	r.ResponseWriter.WriteHeader(statusCode)
}

func (r *statusRecorder) Write(b []byte) (int, error) {
	// Ensure status is visible even when handler only calls Write.
	if r.statusCode == 0 {
		r.statusCode = http.StatusOK
	}
	n, err := r.ResponseWriter.Write(b)
	r.bytesWritten += n
	return n, err
}

func (r *statusRecorder) Unwrap() http.ResponseWriter {
	return r.ResponseWriter
}

func valueOrDash(v string) string {
	if strings.TrimSpace(v) == "" {
		return "-"
	}
	return sanitizeLogValue(v)
}

func sanitizeLogValue(v string) string {
	// Keep logs single-line and predictable.
	s := strings.ReplaceAll(v, "\n", " ")
	s = strings.ReplaceAll(s, "\r", " ")
	return strconv.Quote(strings.TrimSpace(s))
}

// isLoopback reports true if the peer's TCP address is on a loopback interface.
// Used to detect external agents that mistakenly bypass the product entry (18011)
// and call the internal backend (8765) directly — per ADR-0003 and ADR-0006.
func isLoopback(remoteAddr string) bool {
	// RemoteAddr may be "IP:port" or "[IPv6]:port"
	host, _, err := splitHostPort(remoteAddr)
	if err != nil {
		return false
	}
	h := strings.ToLower(host)
	if h == "localhost" || h == "127.0.0.1" || h == "::1" || h == "::ffff:127.0.0.1" {
		return true
	}
	if strings.HasPrefix(h, "127.") {
		return true
	}
	return false
}

// splitHostPort splits a "host:port" or "[host]:port" string.
func splitHostPort(addr string) (host string, port string, err error) {
	// Handle IPv6
	if strings.HasPrefix(addr, "[") {
		end := strings.LastIndex(addr, "]")
		if end == -1 {
			return "", "", nil
		}
		host = addr[1:end]
		rest := addr[end+1:]
		if len(rest) > 0 && rest[0] == ':' {
			return host, rest[1:], nil
		}
		return host, "", nil
	}
	// IPv4 or hostname
	if idx := strings.LastIndex(addr, ":"); idx != -1 {
		return addr[:idx], addr[idx+1:], nil
	}
	return addr, "", nil
}

// scopeMiddleware extracts and resolves scope from headers/body
// Priority: Header > Body > Config (per RUNTIME_ARCHITECTURE.md Section 7.2)
func scopeMiddleware(next http.Handler, resolver *scope.Resolver) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		headerAgent := r.Header.Get("X-OmniMemora-Agent")
		headerUser := r.Header.Get("X-OmniMemora-User")
		headerWorkspace := r.Header.Get("X-OmniMemora-Workspace")
		headerScope := r.Header.Get("X-OmniMemora-Scope")
		headerSharingMode := r.Header.Get("X-OmniMemora-Sharing-Mode")
		headerTenant := r.Header.Get("X-OmniMemora-Tenant")

		var bodyScopeRef *pkg.ScopeRef
		if r.ContentLength > 0 && isJSONContentType(r.Header.Get("Content-Type")) {
			bodyBytes, err := io.ReadAll(r.Body)
			if err == nil {
				r.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))
				bodyScopeRef = parseBodyScopeRef(bodyBytes)
			}
		}

		scopeRef := resolver.ResolveScopeRef(
			headerAgent, headerUser, headerWorkspace,
			headerScope, headerSharingMode, headerTenant,
			bodyScopeRef,
		)

		ctx := context.WithValue(r.Context(), scopeContextKey, scopeRef)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func isJSONContentType(ct string) bool {
	return strings.HasPrefix(ct, "application/json")
}

func parseBodyScopeRef(body []byte) *pkg.ScopeRef {
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(body, &raw); err != nil {
		return nil
	}

	ref := &pkg.ScopeRef{}

	if v, ok := raw["scope"]; ok {
		var s string
		if json.Unmarshal(v, &s) == nil {
			ref.Scope = pkg.ScopeType(s)
		}
	}
	if v, ok := raw["sharing_mode"]; ok {
		var s string
		if json.Unmarshal(v, &s) == nil {
			ref.SharingMode = pkg.SharingMode(s)
		}
	}
	if v, ok := raw["agent_id"]; ok {
		var s string
		if json.Unmarshal(v, &s) == nil {
			ref.AgentID = s
		}
	}
	if v, ok := raw["workspace_id"]; ok {
		var s string
		if json.Unmarshal(v, &s) == nil {
			ref.WorkspaceID = s
		}
	}
	if v, ok := raw["user_id"]; ok {
		var s string
		if json.Unmarshal(v, &s) == nil {
			ref.UserID = s
		}
	}
	if v, ok := raw["tenant_id"]; ok {
		var s string
		if json.Unmarshal(v, &s) == nil {
			ref.TenantID = s
		}
	}

	return ref
}

func getRequestID(ctx context.Context) string {
	if id, ok := ctx.Value(requestIDKey).(string); ok {
		return id
	}
	return ""
}

func getStartTime(ctx context.Context) time.Time {
	if t, ok := ctx.Value(startTimeKey).(time.Time); ok {
		return t
	}
	return time.Now()
}
