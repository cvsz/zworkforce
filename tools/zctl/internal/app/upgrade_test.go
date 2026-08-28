package app

import (
	"testing"
	"time"
)

func TestParseUpgradePlan(t *testing.T) {
	mode, target, planID, confirmation, err := parseUpgradeArgs([]string{"--to", "v1.3.0", "--plan"})
	if err != nil {
		t.Fatal(err)
	}
	if mode != "plan" || target != "v1.3.0" || planID != "" || confirmation != "" {
		t.Fatalf("unexpected parse result: %q %q %q %q", mode, target, planID, confirmation)
	}
}

func TestParseUpgradeApplyRequiresPlanID(t *testing.T) {
	if _, _, _, _, err := parseUpgradeArgs([]string{"--apply"}); err == nil {
		t.Fatal("expected missing plan ID rejection")
	}
}

func TestParseUpgradeModesAreExclusive(t *testing.T) {
	if _, _, _, _, err := parseUpgradeArgs([]string{"--plan", "--apply", "--to", "main"}); err == nil {
		t.Fatal("expected mutually exclusive mode rejection")
	}
}

func TestUpgradePlanChecksumDetectsMutation(t *testing.T) {
	plan := upgradePlan{SchemaVersion: planSchemaVersion, PlanID: "0123456789abcdef", Profile: "local", CreatedAt: time.Unix(1, 0).UTC(), BeforeRevision: "before", TargetRevision: "target", TargetRef: "v1"}
	plan.Checksum = planChecksum(plan)
	original := plan.Checksum
	plan.TargetRevision = "tampered"
	if original == planChecksum(plan) {
		t.Fatal("checksum did not detect mutation")
	}
}

func TestProductionConfirmationRequired(t *testing.T) {
	cfg, err := defaults("production")
	if err != nil {
		t.Fatal(err)
	}
	a := application{opts: options{profile: "production"}, cfg: cfg}
	if err := a.requireEnvironmentConfirmation(""); err == nil {
		t.Fatal("expected production confirmation requirement")
	}
	if err := a.requireEnvironmentConfirmation("staging"); err == nil {
		t.Fatal("expected mismatched confirmation rejection")
	}
	if err := a.requireEnvironmentConfirmation("production"); err != nil {
		t.Fatal(err)
	}
}

func TestPlanIDValidation(t *testing.T) {
	if !validID("0123456789abcdef") {
		t.Fatal("valid ID rejected")
	}
	for _, value := range []string{"", "short", "0123456789abcdeg", "../../etc/passwd"} {
		if validID(value) {
			t.Fatalf("invalid ID accepted: %q", value)
		}
	}
}
