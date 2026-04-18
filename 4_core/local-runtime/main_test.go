package main

import "testing"

func TestResolveCommandDefaultsToHelp(t *testing.T) {
	command, args := resolveCommand(nil)
	if command != "help" {
		t.Fatalf("expected help command, got %q", command)
	}
	if len(args) != 0 {
		t.Fatalf("expected no args, got %#v", args)
	}
}

func TestResolveCommandServe(t *testing.T) {
	command, args := resolveCommand([]string{"serve", "--port=8765"})
	if command != "serve" {
		t.Fatalf("expected serve command, got %q", command)
	}
	if len(args) != 1 || args[0] != "--port=8765" {
		t.Fatalf("unexpected args: %#v", args)
	}
}

func TestResolveCommandAttach(t *testing.T) {
	command, args := resolveCommand([]string{"attach", "claude"})
	if command != "attach" {
		t.Fatalf("expected attach command, got %q", command)
	}
	if len(args) != 1 || args[0] != "claude" {
		t.Fatalf("unexpected args: %#v", args)
	}
}

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
