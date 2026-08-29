package app

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const planSchemaVersion = "1.0.0"

type upgradePlan struct {
	SchemaVersion  string            `json:"schemaVersion"`
	PlanID         string            `json:"planId"`
	Checksum       string            `json:"checksum"`
	Profile        string            `json:"profile"`
	CreatedAt      time.Time         `json:"createdAt"`
	BeforeRevision string            `json:"beforeRevision"`
	TargetRevision string            `json:"targetRevision"`
	TargetRef      string            `json:"targetRef"`
	Images         []string          `json:"images,omitempty"`
	Hooks          map[string]string `json:"hooks,omitempty"`
	Risks          []string          `json:"risks,omitempty"`
}

type releaseEvidence struct {
	SchemaVersion  string            `json:"schemaVersion"`
	ReleaseID      string            `json:"releaseId"`
	PlanID         string            `json:"planId"`
	Profile        string            `json:"profile"`
	StartedAt      time.Time         `json:"startedAt"`
	CompletedAt    time.Time         `json:"completedAt"`
	BeforeRevision string            `json:"beforeRevision"`
	TargetRevision string            `json:"targetRevision"`
	Result         string            `json:"result"`
	Checks         map[string]string `json:"checks"`
	Error          string            `json:"error,omitempty"`
}

func (a application) upgrade(ctx context.Context, args []string, rec *auditRecord) error {
	mode, target, planID, confirmation, err := parseUpgradeArgs(args)
	if err != nil {
		return codedError{2, err}
	}
	switch mode {
	case "plan":
		plan, err := a.createUpgradePlan(ctx, target)
		if err != nil {
			return err
		}
		rec.BeforeRevision, rec.TargetRevision, rec.PlanID = plan.BeforeRevision, plan.TargetRevision, plan.PlanID
		return a.writePlan(plan)
	case "apply":
		plan, err := a.loadPlan(planID)
		if err != nil {
			return err
		}
		rec.BeforeRevision, rec.TargetRevision, rec.PlanID = plan.BeforeRevision, plan.TargetRevision, plan.PlanID
		return a.applyUpgrade(ctx, plan, confirmation)
	case "rollback":
		return a.rollbackRelease(ctx, planID, confirmation, rec)
	default:
		return codedError{2, errors.New("upgrade requires exactly one of --plan, --apply, or --rollback")}
	}
}

func parseUpgradeArgs(args []string) (mode, target, planID, confirmation string, err error) {
	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--plan":
			mode, err = setMode(mode, "plan")
		case "--apply":
			mode, err = setMode(mode, "apply")
		case "--rollback":
			mode, err = setMode(mode, "rollback")
		case "--to", "--revision":
			if i+1 >= len(args) {
				return "", "", "", "", fmt.Errorf("%s requires a value", args[i])
			}
			i++
			target = args[i]
		case "--plan-id":
			if i+1 >= len(args) {
				return "", "", "", "", errors.New("--plan-id requires a value")
			}
			i++
			planID = args[i]
		case "--confirm-environment":
			if i+1 >= len(args) {
				return "", "", "", "", errors.New("--confirm-environment requires a value")
			}
			i++
			confirmation = args[i]
		default:
			return "", "", "", "", fmt.Errorf("unknown upgrade flag %q", args[i])
		}
		if err != nil {
			return "", "", "", "", err
		}
	}
	if mode == "plan" && target == "" {
		return "", "", "", "", errors.New("upgrade --plan requires --to or --revision")
	}
	if (mode == "apply" || mode == "rollback") && planID == "" {
		return "", "", "", "", fmt.Errorf("upgrade --%s requires --plan-id", mode)
	}
	return mode, target, planID, confirmation, nil
}

func setMode(current, next string) (string, error) {
	if current != "" && current != next {
		return "", errors.New("upgrade modes are mutually exclusive")
	}
	return next, nil
}

func (a application) createUpgradePlan(ctx context.Context, target string) (upgradePlan, error) {
	if dirty, err := a.gitOutput(ctx, "status", "--porcelain"); err != nil {
		return upgradePlan{}, err
	} else if strings.TrimSpace(string(dirty)) != "" {
		return upgradePlan{}, codedError{2, errors.New("upgrade planning refused because the working tree is dirty")}
	}
	beforeBytes, err := a.gitOutput(ctx, "rev-parse", "HEAD")
	if err != nil {
		return upgradePlan{}, err
	}
	targetBytes, err := a.gitOutput(ctx, "rev-parse", "--verify", target+"^{commit}")
	if err != nil {
		return upgradePlan{}, codedError{2, fmt.Errorf("cannot resolve immutable target %q", target)}
	}
	before, resolved := strings.TrimSpace(string(beforeBytes)), strings.TrimSpace(string(targetBytes))
	imagesBytes, _ := a.output(ctx, "config", "--images")
	plan := upgradePlan{SchemaVersion: planSchemaVersion, PlanID: id(), Profile: a.opts.profile, CreatedAt: time.Now().UTC(), BeforeRevision: before, TargetRevision: resolved, TargetRef: target, Images: strings.Fields(string(imagesBytes)), Hooks: map[string]string{}, Risks: []string{"service replacement may temporarily reduce availability", "database migrations may require application-compatible rollback"}}
	for _, name := range []string{"backup", "pre-migrate", "migrate", "rollback"} {
		path := filepath.Join("scripts", "zctl", name)
		if st, e := os.Stat(path); e == nil && st.Mode().IsRegular() {
			plan.Hooks[name] = path
		}
	}
	if a.opts.profile != "local" && plan.Hooks["backup"] == "" {
		return upgradePlan{}, codedError{4, errors.New("staging and production upgrade plans require scripts/zctl/backup")}
	}
	plan.Checksum = planChecksum(plan)
	return plan, nil
}

func planChecksum(plan upgradePlan) string {
	plan.Checksum = ""
	b, _ := json.Marshal(plan)
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func (a application) writePlan(plan upgradePlan) error {
	if a.opts.dryRun {
		return json.NewEncoder(a.stdout).Encode(plan)
	}
	if err := os.MkdirAll(a.cfg.planDir, 0o700); err != nil {
		return err
	}
	path := filepath.Join(a.cfg.planDir, plan.PlanID+".json")
	if err := writeJSONExclusive(path, plan); err != nil {
		return err
	}
	if a.opts.json {
		return json.NewEncoder(a.stdout).Encode(plan)
	}
	fmt.Fprintf(a.stdout, "upgrade plan created: %s\ntarget revision: %s\nchecksum: %s\n", plan.PlanID, plan.TargetRevision, plan.Checksum)
	return nil
}

func (a application) loadPlan(planID string) (upgradePlan, error) {
	var plan upgradePlan
	if !validID(planID) {
		return plan, codedError{2, errors.New("invalid plan ID")}
	}
	b, err := os.ReadFile(filepath.Join(a.cfg.planDir, planID+".json"))
	if err != nil {
		return plan, codedError{2, fmt.Errorf("cannot read upgrade plan %q", planID)}
	}
	if err = json.Unmarshal(b, &plan); err != nil {
		return plan, codedError{2, errors.New("upgrade plan is invalid JSON")}
	}
	if plan.SchemaVersion != planSchemaVersion || plan.PlanID != planID || plan.Checksum != planChecksum(plan) {
		return plan, codedError{2, errors.New("upgrade plan checksum validation failed")}
	}
	if plan.Profile != a.opts.profile {
		return plan, codedError{4, fmt.Errorf("plan profile %q does not match selected profile %q", plan.Profile, a.opts.profile)}
	}
	return plan, nil
}

func (a application) applyUpgrade(ctx context.Context, plan upgradePlan, confirmation string) error {
	if err := a.requireEnvironmentConfirmation(confirmation); err != nil {
		return err
	}
	current, err := a.gitOutput(ctx, "rev-parse", "HEAD")
	if err != nil {
		return err
	}
	if strings.TrimSpace(string(current)) != plan.BeforeRevision {
		return codedError{2, errors.New("current revision no longer matches the upgrade plan")}
	}
	evidence := releaseEvidence{SchemaVersion: "1.0.0", ReleaseID: id(), PlanID: plan.PlanID, Profile: plan.Profile, StartedAt: time.Now().UTC(), BeforeRevision: plan.BeforeRevision, TargetRevision: plan.TargetRevision, Result: "RELEASE_FAILED", Checks: map[string]string{"plan": "passed"}}
	fail := func(cause error) error {
		evidence.Error = redact(cause.Error())
		evidence.Checks["deployment"] = "failed"
		if rb := a.rollbackTo(ctx, plan); rb == nil {
			evidence.Result = "ROLLED_BACK"
			evidence.Checks["rollback"] = "passed"
		} else {
			evidence.Checks["rollback"] = "failed"
			evidence.Error += "; rollback: " + redact(rb.Error())
		}
		evidence.CompletedAt = time.Now().UTC()
		_ = a.writeReleaseEvidence(evidence)
		return cause
	}
	if err = a.runHook(ctx, plan.Hooks["backup"], plan); err != nil {
		return fail(fmt.Errorf("backup failed: %w", err))
	}
	evidence.Checks["backup"] = hookStatus(plan.Hooks["backup"])
	if err = a.gitRun(ctx, "switch", "--detach", plan.TargetRevision); err != nil {
		return fail(err)
	}
	if err = a.compose(ctx, "pull"); err != nil {
		return fail(err)
	}
	if err = a.runHook(ctx, plan.Hooks["pre-migrate"], plan); err != nil {
		return fail(fmt.Errorf("pre-migration failed: %w", err))
	}
	if err = a.compose(ctx, "up", "-d", "--remove-orphans"); err != nil {
		return fail(err)
	}
	if err = a.runHook(ctx, plan.Hooks["migrate"], plan); err != nil {
		return fail(fmt.Errorf("migration failed: %w", err))
	}
	evidence.Checks["migration"] = hookStatus(plan.Hooks["migrate"])
	if err = a.wait(ctx, nil); err != nil {
		return fail(fmt.Errorf("health verification failed: %w", err))
	}
	evidence.Checks["deployment"], evidence.Checks["health"] = "passed", "passed"
	evidence.Result = "success"
	evidence.CompletedAt = time.Now().UTC()
	return a.writeReleaseEvidence(evidence)
}

func (a application) rollbackRelease(ctx context.Context, planID, confirmation string, rec *auditRecord) error {
	if err := a.requireEnvironmentConfirmation(confirmation); err != nil {
		return err
	}
	plan, err := a.loadPlan(planID)
	if err != nil {
		return err
	}
	rec.PlanID, rec.BeforeRevision, rec.TargetRevision = plan.PlanID, plan.TargetRevision, plan.BeforeRevision
	if err = a.rollbackTo(ctx, plan); err != nil {
		return err
	}
	e := releaseEvidence{SchemaVersion: "1.0.0", ReleaseID: id(), PlanID: plan.PlanID, Profile: plan.Profile, StartedAt: time.Now().UTC(), CompletedAt: time.Now().UTC(), BeforeRevision: plan.TargetRevision, TargetRevision: plan.BeforeRevision, Result: "ROLLED_BACK", Checks: map[string]string{"rollback": "passed", "health": "passed"}}
	return a.writeReleaseEvidence(e)
}

func (a application) rollbackTo(ctx context.Context, plan upgradePlan) error {
	if err := a.gitRun(ctx, "switch", "--detach", plan.BeforeRevision); err != nil {
		return err
	}
	if err := a.runHook(ctx, plan.Hooks["rollback"], plan); err != nil {
		return err
	}
	if err := a.compose(ctx, "pull"); err != nil {
		return err
	}
	if err := a.compose(ctx, "up", "-d", "--remove-orphans"); err != nil {
		return err
	}
	return a.wait(ctx, nil)
}

func (a application) runHook(ctx context.Context, path string, plan upgradePlan) error {
	if path == "" {
		return nil
	}
	st, err := os.Stat(path)
	if err != nil {
		return err
	}
	if st.Mode().Perm()&0o111 == 0 {
		return fmt.Errorf("hook %s is not executable", path)
	}
	return a.run.run(ctx, a.stdout, path, "--plan-id", plan.PlanID, "--before", plan.BeforeRevision, "--target", plan.TargetRevision, "--profile", plan.Profile)
}

func (a application) requireEnvironmentConfirmation(value string) error {
	if a.opts.profile == "production" && value != "production" {
		return codedError{4, errors.New("production upgrade requires --confirm-environment production")}
	}
	if value != "" && value != a.opts.profile {
		return codedError{4, errors.New("environment confirmation does not match selected profile")}
	}
	return nil
}

func (a application) writeReleaseEvidence(e releaseEvidence) error {
	if a.opts.dryRun {
		return nil
	}
	if err := os.MkdirAll(a.cfg.releaseDir, 0o700); err != nil {
		return err
	}
	return writeJSONExclusive(filepath.Join(a.cfg.releaseDir, e.StartedAt.Format("20060102T150405Z")+"-"+e.ReleaseID+".json"), e)
}

func writeJSONExclusive(path string, value any) error {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	defer f.Close()
	enc := json.NewEncoder(f)
	enc.SetIndent("", "  ")
	return enc.Encode(value)
}

func validID(value string) bool {
	if len(value) != 16 {
		return false
	}
	for _, r := range value {
		if !strings.ContainsRune("0123456789abcdef", r) {
			return false
		}
	}
	return true
}

func hookStatus(path string) string {
	if path == "" {
		return "not-configured"
	}
	return "passed"
}
