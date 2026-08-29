package app

import (
	"slices"
	"strings"
	"testing"
)

func TestParseGlobalFlagsAfterCommand(t *testing.T) {
	o, cmd, args, err := parse([]string{"health", "--json", "--profile", "staging", "--wait"})
	if err != nil {
		t.Fatal(err)
	}
	if cmd != "health" || !o.json || o.profile != "staging" || !slices.Equal(args, []string{"--wait"}) {
		t.Fatalf("unexpected parse result: %+v %s %v", o, cmd, args)
	}
}

func TestProfilesGuardMutation(t *testing.T) {
	local, err := defaults("local")
	if err != nil {
		t.Fatal(err)
	}
	production, err := defaults("production")
	if err != nil {
		t.Fatal(err)
	}
	if !local.allowPurge || !local.allowBuild {
		t.Fatal("local must permit guarded purge and build")
	}
	if production.allowPurge || production.allowBuild {
		t.Fatal("production must reject purge and local build")
	}
}

func TestSplitServices(t *testing.T) {
	svc, flags, err := splitServices([]string{"--service", "ai-gateway", "--pull", "--no-cache"})
	if err != nil {
		t.Fatal(err)
	}
	if !slices.Equal(svc, []string{"ai-gateway"}) || !slices.Equal(flags, []string{"--pull", "--no-cache"}) {
		t.Fatalf("%v %v", svc, flags)
	}
}

func TestRejectUnknownFlag(t *testing.T) {
	if err := reject([]string{"--unsafe"}, "--wait"); err == nil {
		t.Fatal("expected rejection")
	}
}

func TestRedact(t *testing.T) {
	got := redact("request failed token=super-secret")
	if strings.Contains(got, "super-secret") {
		t.Fatalf("secret leaked: %s", got)
	}
}

func TestChecksumStable(t *testing.T) {
	if checksum("release") != checksum("release") {
		t.Fatal("checksum is not stable")
	}
	if checksum("release") == checksum("different") {
		t.Fatal("checksum collision in test values")
	}
}

func TestVersionAdvancedForPhase3(t *testing.T) {
	if Version != "0.3.0" {
		t.Fatalf("unexpected version %s", Version)
	}
}
