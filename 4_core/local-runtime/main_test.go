package main

import "testing"

func TestResolvePreferredRuntimePortDefaults(t *testing.T) {
	t.Setenv("OMNIMEMORA_RUNTIME_PORT", "")

	got := resolvePreferredRuntimePort()
	if got != 8765 {
		t.Fatalf("expected default port 8765, got %d", got)
	}
}

func TestResolvePreferredRuntimePortUsesEnvOverride(t *testing.T) {
	t.Setenv("OMNIMEMORA_RUNTIME_PORT", "18765")

	got := resolvePreferredRuntimePort()
	if got != 18765 {
		t.Fatalf("expected env override port 18765, got %d", got)
	}
}

func TestResolvePreferredRuntimePortRejectsInvalidValues(t *testing.T) {
	t.Setenv("OMNIMEMORA_RUNTIME_PORT", "bad-port")

	got := resolvePreferredRuntimePort()
	if got != 8765 {
		t.Fatalf("expected invalid env to fall back to 8765, got %d", got)
	}
}
