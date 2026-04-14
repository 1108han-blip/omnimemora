// app/errors.go - Error types for OmniMemora Local Runtime
package app

import "errors"

// Error codes align with RUNTIME_ARCHITECTURE.md Section 14.1
var (
	// ErrConfigError - Configuration error
	ErrConfigError = errors.New("config_error")

	// ErrScopeError - Scope enforcement failure
	ErrScopeError = errors.New("scope_error")

	// ErrStoreError - Storage operation failure
	ErrStoreError = errors.New("store_error")

	// ErrPolicyError - Policy execution failure
	ErrPolicyError = errors.New("policy_error")

	// ErrConnectorError - Connector operation failure
	ErrConnectorError = errors.New("connector_error")

	// ErrNotImplemented - Feature not implemented
	ErrNotImplemented = errors.New("not_implemented")

	// ErrNotFound - Resource not found
	ErrNotFound = errors.New("not_found")

	// ErrUnauthorized - Unauthorized access
	ErrUnauthorized = errors.New("unauthorized")

	// ErrForbidden - Access forbidden
	ErrForbidden = errors.New("forbidden")

	// ErrDuplicateEntry - Duplicate entry detected
	ErrDuplicateEntry = errors.New("duplicate_entry")
)

// AppError represents an application-level error with context
type AppError struct {
	Err      error
	Code     string
	Message  string
	Details  string
	HTTPCode int
}

func (e *AppError) Error() string {
	if e.Message != "" {
		return e.Message
	}
	return e.Err.Error()
}

func (e *AppError) Unwrap() error {
	return e.Err
}

// NewAppError creates a new application error
func NewAppError(err error, code, message string, httpCode int) *AppError {
	return &AppError{
		Err:      err,
		Code:     code,
		Message:  message,
		HTTPCode: httpCode,
	}
}

// NewScopeError creates a scope-related error
func NewScopeError(message string) *AppError {
	return &AppError{
		Err:      ErrScopeError,
		Code:     "SCOPE_ERROR",
		Message:  message,
		HTTPCode: 400,
	}
}

// NewStoreError creates a store-related error
func NewStoreError(message string, err error) *AppError {
	return &AppError{
		Err:      err,
		Code:     "STORE_ERROR",
		Message:  message,
		HTTPCode: 500,
	}
}

// NewNotImplementedError creates a not-implemented error
func NewNotImplementedError(feature string) *AppError {
	return &AppError{
		Err:      ErrNotImplemented,
		Code:     "NOT_IMPLEMENTED",
		Message:  feature + " not implemented",
		HTTPCode: 501,
	}
}

// NewNotFoundError creates a not-found error
func NewNotFoundError(resource string) *AppError {
	return &AppError{
		Err:      ErrNotFound,
		Code:     "NOT_FOUND",
		Message:  resource + " not found",
		HTTPCode: 404,
	}
}

// NewForbiddenError creates a forbidden error
func NewForbiddenError(message string) *AppError {
	return &AppError{
		Err:      ErrForbidden,
		Code:     "FORBIDDEN",
		Message:  message,
		HTTPCode: 403,
	}
}
