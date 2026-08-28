package app

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/user"
	"path/filepath"
	"slices"
	"strings"
	"time"
)

const Version = "0.3.0"

type codedError struct {
	code int
	err  error
}

func (e codedError) Error() string { return e.err.Error() }

func ExitCode(err error) int {
	var e codedError
	if errors.As(err, &e) {
		return e.code
	}
	return 1
}

type options struct {
	profile               string
	dryRun, json, verbose bool
	timeout               time.Duration
}

type config struct {
	compose, project, env, lock, audit string
	remote, branch, sbomDir            string
	planDir, releaseDir                string
	allowPurge, allowBuild             bool
	healthTimeout                      time.Duration
}

type runner struct {
	dryRun, verbose bool
	stderr          io.Writer
}

func (r runner) run(ctx context.Context, stdout io.Writer, name string, args ...string) error {
	if r.verbose || r.dryRun {
		fmt.Fprintf(r.stderr, "+ %s %s\n", name, strings.Join(args, " "))
	}
	if r.dryRun {
		return nil
	}
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Stdout = stdout
	cmd.Stderr = r.stderr
	cmd.Stdin = os.Stdin
	return cmd.Run()
}

func (r runner) output(ctx context.Context, name string, args ...string) ([]byte, error) {
	if r.verbose || r.dryRun {
		fmt.Fprintf(r.stderr, "+ %s %s\n", name, strings.Join(args, " "))
	}
	if r.dryRun {
		return nil, nil
	}
	return exec.CommandContext(ctx, name, args...).Output()
}

type application struct {
	opts           options
	cfg            config
	run            runner
	stdout, stderr io.Writer
}

type auditRecord struct {
	SchemaVersion  string            `json:"schemaVersion"`
	OperationID    string            `json:"operationId"`
	PlanID         string            `json:"planId,omitempty"`
	Command        string            `json:"command"`
	Profile        string            `json:"profile"`
	Actor          string            `json:"actor"`
	StartedAt      time.Time         `json:"startedAt"`
	CompletedAt    time.Time         `json:"completedAt"`
	BeforeRevision string            `json:"beforeRevision,omitempty"`
	TargetRevision string            `json:"targetRevision,omitempty"`
	ImageDigests   map[string]string `json:"imageDigests,omitempty"`
	Result         string            `json:"result"`
	Error          string            `json:"error,omitempty"`
}

func Run(parent context.Context, args []string, stdout, stderr io.Writer) error {
	opts, command, rest, err := parse(args)
	if err != nil {
		return codedError{2, err}
	}
	cfg, err := defaults(opts.profile)
	if err != nil {
		return codedError{2, err}
	}
	a := application{opts: opts, cfg: cfg, run: runner{opts.dryRun, opts.verbose, stderr}, stdout: stdout, stderr: stderr}

	if command == "help" {
		a.help()
		return nil
	}
	if command == "version" {
		fmt.Fprintf(stdout, "zctl %s\n", Version)
		return nil
	}
	if !slices.Contains([]string{"start", "stop", "restart", "status", "health", "logs", "doctor", "build", "update", "upgrade"}, command) {
		return codedError{2, fmt.Errorf("unknown command %q", command)}
	}

	ctx, cancel := context.WithTimeout(parent, opts.timeout)
	defer cancel()
	rec := auditRecord{SchemaVersion: "1.0.0", OperationID: id(), Command: command, Profile: opts.profile, Actor: actor(), StartedAt: time.Now().UTC(), Result: "failed"}
	defer func() {
		rec.CompletedAt = time.Now().UTC()
		_ = a.audit(rec)
	}()

	switch command {
	case "doctor":
		err = a.doctor(ctx)
	case "update":
		err = a.locked(command, func() error { return a.update(ctx, rest, &rec) })
	default:
		if err = a.preflight(ctx); err == nil {
			switch command {
			case "start":
				err = a.locked(command, func() error { return a.start(ctx, rest) })
			case "stop":
				err = a.locked(command, func() error { return a.stop(ctx, rest) })
			case "restart":
				err = a.locked(command, func() error { return a.restart(ctx, rest) })
			case "build":
				err = a.locked(command, func() error { return a.build(ctx, rest, &rec) })
			case "upgrade":
				err = a.locked(command, func() error { return a.upgrade(ctx, rest, &rec) })
			case "status":
				err = a.compose(ctx, "ps")
			case "health":
				err = a.health(ctx, rest)
			case "logs":
				err = a.logs(ctx, rest)
			}
		}
	}

	if err == nil {
		rec.Result = "success"
	} else {
		rec.Error = redact(err.Error())
	}
	return err
}

func defaults(profile string) (config, error) {
	cfg := config{compose: "compose.yml", project: "z-platform", lock: ".zctl/operation.lock", audit: ".zctl/audit", remote: "origin", branch: "main", sbomDir: ".zctl/sbom", planDir: ".zctl/plans", releaseDir: ".zctl/releases", healthTimeout: 180 * time.Second}
	switch profile {
	case "local":
		cfg.env, cfg.allowPurge, cfg.allowBuild = ".env", true, true
	case "staging":
		cfg.env = ".env.staging"
	case "production":
		cfg.env = ".env.production"
	default:
		return cfg, fmt.Errorf("unknown profile %q", profile)
	}
	return cfg, nil
}

func parse(args []string) (options, string, []string, error) {
	opts := options{profile: "local", timeout: 3 * time.Minute}
	command := ""
	rest := []string{}
	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--profile", "--timeout":
			if i+1 >= len(args) {
				return opts, "", nil, fmt.Errorf("%s requires a value", args[i])
			}
			flag := args[i]
			i++
			if flag == "--profile" {
				opts.profile = args[i]
			} else {
				d, err := time.ParseDuration(args[i])
				if err != nil {
					return opts, "", nil, err
				}
				opts.timeout = d
			}
		case "--dry-run":
			opts.dryRun = true
		case "--json":
			opts.json = true
		case "--verbose":
			opts.verbose = true
		default:
			if command == "" && !strings.HasPrefix(args[i], "-") {
				command = args[i]
			} else {
				rest = append(rest, args[i])
			}
		}
	}
	if command == "" {
		command = "help"
	}
	return opts, command, rest, nil
}

func (a application) base() []string {
	return []string{"compose", "-f", a.cfg.compose, "--project-name", a.cfg.project, "--env-file", a.cfg.env}
}
func (a application) compose(ctx context.Context, args ...string) error {
	return a.run.run(ctx, a.stdout, "docker", append(a.base(), args...)...)
}
func (a application) output(ctx context.Context, args ...string) ([]byte, error) {
	return a.run.output(ctx, "docker", append(a.base(), args...)...)
}
func (a application) gitOutput(ctx context.Context, args ...string) ([]byte, error) {
	return a.run.output(ctx, "git", args...)
}
func (a application) gitRun(ctx context.Context, args ...string) error {
	return a.run.run(ctx, a.stdout, "git", args...)
}

func (a application) preflight(ctx context.Context) error {
	if _, err := exec.LookPath("docker"); err != nil {
		return codedError{3, errors.New("docker is unavailable")}
	}
	if !a.opts.dryRun {
		for _, path := range []string{a.cfg.compose, a.cfg.env} {
			if _, err := os.Stat(path); err != nil {
				return codedError{2, fmt.Errorf("missing required file %s", path)}
			}
		}
	}
	if err := a.compose(ctx, "config", "--quiet"); err != nil {
		return codedError{2, fmt.Errorf("compose validation failed: %v", err)}
	}
	return nil
}

func splitServices(args []string) ([]string, []string, error) {
	services, flags := []string{}, []string{}
	for i := 0; i < len(args); i++ {
		if args[i] == "--service" {
			if i+1 >= len(args) {
				return nil, nil, errors.New("--service requires a value")
			}
			i++
			services = append(services, args[i])
		} else {
			flags = append(flags, args[i])
		}
	}
	return services, flags, nil
}

func (a application) validate(ctx context.Context, services []string) error {
	if len(services) == 0 {
		return nil
	}
	out, err := a.output(ctx, "config", "--services")
	if err != nil {
		return err
	}
	allowed := strings.Fields(string(out))
	for _, service := range services {
		if !slices.Contains(allowed, service) {
			return codedError{2, fmt.Errorf("unknown service %q", service)}
		}
	}
	return nil
}

func reject(flags []string, allowed ...string) error {
	for _, flag := range flags {
		if !slices.Contains(allowed, flag) {
			return fmt.Errorf("unknown flag %q", flag)
		}
	}
	return nil
}

func (a application) start(ctx context.Context, args []string) error {
	services, flags, err := splitServices(args)
	if err != nil {
		return codedError{2, err}
	}
	if err = reject(flags, "--wait", "--build"); err != nil {
		return codedError{2, err}
	}
	if slices.Contains(flags, "--build") && !a.cfg.allowBuild {
		return codedError{4, errors.New("build is forbidden for this profile")}
	}
	if err = a.validate(ctx, services); err != nil {
		return err
	}
	cmd := []string{"up", "-d"}
	if slices.Contains(flags, "--build") {
		cmd = append(cmd, "--build")
	}
	cmd = append(cmd, services...)
	if err = a.compose(ctx, cmd...); err != nil {
		return err
	}
	if slices.Contains(flags, "--wait") {
		return a.wait(ctx, services)
	}
	return a.compose(ctx, "ps")
}

func (a application) stop(ctx context.Context, args []string) error {
	services, flags, err := splitServices(args)
	if err != nil {
		return codedError{2, err}
	}
	if err = reject(flags, "--remove-orphans", "--purge", "--confirm-destroy"); err != nil {
		return codedError{2, err}
	}
	if err = a.validate(ctx, services); err != nil {
		return err
	}
	if slices.Contains(flags, "--purge") {
		if !a.cfg.allowPurge {
			return codedError{4, errors.New("purge is forbidden for this profile")}
		}
		if !slices.Contains(flags, "--confirm-destroy") {
			return codedError{4, errors.New("--purge requires --confirm-destroy")}
		}
		cmd := []string{"down", "--volumes"}
		if slices.Contains(flags, "--remove-orphans") {
			cmd = append(cmd, "--remove-orphans")
		}
		return a.compose(ctx, cmd...)
	}
	return a.compose(ctx, append([]string{"stop"}, services...)...)
}

func (a application) restart(ctx context.Context, args []string) error {
	services, flags, err := splitServices(args)
	if err != nil {
		return codedError{2, err}
	}
	if err = reject(flags, "--wait", "--recreate"); err != nil {
		return codedError{2, err}
	}
	if err = a.validate(ctx, services); err != nil {
		return err
	}
	cmd := []string{"restart"}
	if slices.Contains(flags, "--recreate") {
		cmd = []string{"up", "-d", "--force-recreate"}
	}
	cmd = append(cmd, services...)
	if err = a.compose(ctx, cmd...); err != nil {
		return err
	}
	if slices.Contains(flags, "--wait") {
		return a.wait(ctx, services)
	}
	return a.compose(ctx, "ps")
}

func (a application) logs(ctx context.Context, args []string) error {
	services, flags, err := splitServices(args)
	if err != nil {
		return codedError{2, err}
	}
	if err = a.validate(ctx, services); err != nil {
		return err
	}
	cmd := []string{"logs"}
	for i := 0; i < len(flags); i++ {
		if slices.Contains([]string{"--follow", "-f", "--timestamps"}, flags[i]) {
			cmd = append(cmd, flags[i])
			continue
		}
		if flags[i] == "--tail" && i+1 < len(flags) {
			cmd = append(cmd, flags[i], flags[i+1])
			i++
			continue
		}
		return codedError{2, fmt.Errorf("invalid logs flag %q", flags[i])}
	}
	return a.compose(ctx, append(cmd, services...)...)
}

func (a application) build(ctx context.Context, args []string, rec *auditRecord) error {
	if !a.cfg.allowBuild {
		return codedError{4, errors.New("build is forbidden for this profile")}
	}
	services, flags, err := splitServices(args)
	if err != nil {
		return codedError{2, err}
	}
	if err = reject(flags, "--no-cache", "--pull", "--push", "--skip-sbom"); err != nil {
		return codedError{2, err}
	}
	if err = a.validate(ctx, services); err != nil {
		return err
	}
	if dirty, err := a.gitOutput(ctx, "status", "--porcelain"); err != nil {
		return err
	} else if strings.TrimSpace(string(dirty)) != "" {
		return codedError{2, errors.New("build refused because the working tree is dirty")}
	}
	rev, err := a.gitOutput(ctx, "rev-parse", "HEAD")
	if err != nil {
		return err
	}
	revision := strings.TrimSpace(string(rev))
	rec.TargetRevision = revision
	created := time.Now().UTC().Format(time.RFC3339)
	cmd := []string{"build", "--build-arg", "OCI_REVISION=" + revision, "--build-arg", "OCI_SOURCE=https://github.com/cvsz/z-platform", "--build-arg", "OCI_CREATED=" + created, "--build-arg", "OCI_VERSION=" + revision[:min(12, len(revision))]}
	for _, flag := range flags {
		if flag != "--skip-sbom" && flag != "--push" {
			cmd = append(cmd, flag)
		}
	}
	cmd = append(cmd, services...)
	if err = a.compose(ctx, cmd...); err != nil {
		return err
	}
	if slices.Contains(flags, "--push") {
		if err = a.compose(ctx, append([]string{"push"}, services...)...); err != nil {
			return err
		}
	}
	images, err := a.output(ctx, "config", "--images")
	if err == nil {
		rec.ImageDigests = map[string]string{}
		for _, image := range strings.Fields(string(images)) {
			inspected, inspectErr := a.run.output(ctx, "docker", "image", "inspect", "--format", "{{index .RepoDigests 0}}", image)
			if inspectErr == nil {
				rec.ImageDigests[image] = strings.TrimSpace(string(inspected))
			}
		}
	}
	if !slices.Contains(flags, "--skip-sbom") {
		return a.sbom(ctx, revision, strings.Fields(string(images)))
	}
	return nil
}

func (a application) sbom(ctx context.Context, revision string, images []string) error {
	if _, err := exec.LookPath("syft"); err != nil {
		return codedError{3, errors.New("syft is required for SBOM generation; install syft or use --skip-sbom")}
	}
	if a.opts.dryRun {
		return nil
	}
	if err := os.MkdirAll(a.cfg.sbomDir, 0o700); err != nil {
		return err
	}
	for _, image := range images {
		name := strings.NewReplacer("/", "_", ":", "_", "@", "_").Replace(image)
		path := filepath.Join(a.cfg.sbomDir, fmt.Sprintf("%s-%s.spdx.json", name, revision[:min(12, len(revision))]))
		file, err := os.OpenFile(path, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o600)
		if err != nil {
			return err
		}
		err = a.run.run(ctx, file, "syft", image, "-o", "spdx-json")
		closeErr := file.Close()
		if err != nil {
			return err
		}
		if closeErr != nil {
			return closeErr
		}
	}
	return nil
}

func (a application) update(ctx context.Context, args []string, rec *auditRecord) error {
	branch, restart, stash := a.cfg.branch, false, false
	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--branch":
			if i+1 >= len(args) {
				return codedError{2, errors.New("--branch requires a value")}
			}
			i++
			branch = args[i]
		case "--restart":
			restart = true
		case "--stash":
			stash = true
		default:
			return codedError{2, fmt.Errorf("unknown update flag %q", args[i])}
		}
	}
	if _, err := exec.LookPath("git"); err != nil {
		return codedError{3, errors.New("git is unavailable")}
	}
	before, err := a.gitOutput(ctx, "rev-parse", "HEAD")
	if err != nil {
		return err
	}
	rec.BeforeRevision = strings.TrimSpace(string(before))
	dirty, err := a.gitOutput(ctx, "status", "--porcelain")
	if err != nil {
		return err
	}
	hasChanges := strings.TrimSpace(string(dirty)) != ""
	if hasChanges && !stash {
		return codedError{2, errors.New("update refused because local changes exist")}
	}
	stashed := false
	if hasChanges {
		if err = a.gitRun(ctx, "stash", "push", "--include-untracked", "--message", "zctl-update-"+rec.OperationID); err != nil {
			return err
		}
		stashed = true
	}
	if stashed {
		defer func() { _ = a.gitRun(context.Background(), "stash", "pop") }()
	}
	if err = a.gitRun(ctx, "fetch", "--prune", a.cfg.remote, branch); err != nil {
		return err
	}
	target := a.cfg.remote + "/" + branch
	if err = a.gitRun(ctx, "merge-base", "--is-ancestor", "HEAD", target); err != nil {
		return codedError{2, errors.New("update refused because remote cannot be fast-forwarded from local HEAD")}
	}
	if err = a.gitRun(ctx, "merge", "--ff-only", target); err != nil {
		return err
	}
	after, err := a.gitOutput(ctx, "rev-parse", "HEAD")
	if err != nil {
		return err
	}
	rec.TargetRevision = strings.TrimSpace(string(after))
	if err = a.syncDependencies(ctx); err != nil {
		return err
	}
	if restart {
		if err = a.preflight(ctx); err != nil {
			return err
		}
		return a.compose(ctx, "up", "-d", "--build")
	}
	return nil
}

func (a application) syncDependencies(ctx context.Context) error {
	if _, err := os.Stat("pnpm-lock.yaml"); err == nil {
		if _, err = exec.LookPath("pnpm"); err != nil {
			return codedError{3, errors.New("pnpm-lock.yaml exists but pnpm is unavailable")}
		}
		return a.run.run(ctx, a.stdout, "pnpm", "install", "--frozen-lockfile")
	}
	if _, err := os.Stat("package-lock.json"); err == nil {
		return a.run.run(ctx, a.stdout, "npm", "ci")
	}
	return nil
}

func (a application) health(ctx context.Context, args []string) error {
	if len(args) > 1 || (len(args) == 1 && args[0] != "--wait") {
		return codedError{2, errors.New("health only accepts --wait")}
	}
	if len(args) == 1 {
		return a.wait(ctx, nil)
	}
	return a.healthOnce(ctx, nil)
}

func (a application) healthOnce(ctx context.Context, services []string) error {
	if len(services) == 0 {
		out, err := a.output(ctx, "config", "--services")
		if err != nil {
			return err
		}
		services = strings.Fields(string(out))
	}
	out, err := a.output(ctx, "ps", "--status", "running", "--services")
	if err != nil {
		return err
	}
	running := strings.Fields(string(out))
	missing := []string{}
	for _, service := range services {
		if !slices.Contains(running, service) {
			missing = append(missing, service)
		}
	}
	if a.opts.json {
		_ = json.NewEncoder(a.stdout).Encode(map[string]any{"healthy": len(missing) == 0, "services": services, "missing": missing})
	} else if len(missing) == 0 {
		fmt.Fprintln(a.stdout, "healthy: all requested services are running")
	} else {
		fmt.Fprintf(a.stdout, "unhealthy: %s\n", strings.Join(missing, ", "))
	}
	if len(missing) > 0 {
		return errors.New("one or more services are not running")
	}
	return nil
}

func (a application) wait(ctx context.Context, services []string) error {
	deadline := time.Now().Add(a.cfg.healthTimeout)
	for {
		if err := a.healthOnce(ctx, services); err == nil {
			return nil
		} else if time.Now().After(deadline) {
			return err
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(2 * time.Second):
		}
	}
}

func (a application) doctor(ctx context.Context) error {
	checks := map[string]string{}
	for _, dependency := range []string{"docker", "git", "syft"} {
		if _, err := exec.LookPath(dependency); err == nil {
			checks[dependency] = "ok"
		} else {
			checks[dependency] = "missing"
		}
	}
	for key, path := range map[string]string{"composeFile": a.cfg.compose, "environmentFile": a.cfg.env} {
		if _, err := os.Stat(path); err == nil {
			checks[key] = "ok"
		} else {
			checks[key] = "missing"
		}
	}
	ok := checks["docker"] == "ok" && checks["git"] == "ok" && checks["composeFile"] == "ok" && checks["environmentFile"] == "ok"
	if a.opts.json {
		_ = json.NewEncoder(a.stdout).Encode(map[string]any{"healthy": ok, "checks": checks})
	} else {
		for _, key := range []string{"docker", "git", "syft", "composeFile", "environmentFile"} {
			fmt.Fprintf(a.stdout, "%-16s %s\n", key, checks[key])
		}
	}
	if !ok {
		return codedError{3, errors.New("doctor checks failed")}
	}
	return nil
}

func (a application) locked(operation string, fn func() error) error {
	if a.opts.dryRun {
		return fn()
	}
	if err := os.MkdirAll(filepath.Dir(a.cfg.lock), 0o700); err != nil {
		return err
	}
	file, err := os.OpenFile(a.cfg.lock, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return codedError{5, fmt.Errorf("operation conflict: %s", a.cfg.lock)}
	}
	_ = json.NewEncoder(file).Encode(map[string]any{"operation": operation, "pid": os.Getpid(), "actor": actor(), "startedAt": time.Now().UTC()})
	_ = file.Close()
	defer os.Remove(a.cfg.lock)
	return fn()
}

func (a application) audit(record auditRecord) error {
	if a.opts.dryRun {
		return nil
	}
	if err := os.MkdirAll(a.cfg.audit, 0o700); err != nil {
		return err
	}
	path := filepath.Join(a.cfg.audit, fmt.Sprintf("%s-%s-%s.json", record.StartedAt.Format("20060102T150405Z"), record.Command, record.OperationID))
	file, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	defer file.Close()
	encoder := json.NewEncoder(file)
	encoder.SetIndent("", "  ")
	return encoder.Encode(record)
}

func id() string {
	value := make([]byte, 8)
	_, _ = rand.Read(value)
	return hex.EncodeToString(value)
}

func actor() string {
	if current, err := user.Current(); err == nil {
		return current.Username
	}
	return "unknown"
}

func redact(value string) string {
	lower := strings.ToLower(value)
	for _, marker := range []string{"token=", "password=", "api_key=", "authorization:"} {
		if index := strings.Index(lower, marker); index >= 0 {
			return value[:index] + marker + "[REDACTED]"
		}
	}
	return value
}

func checksum(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])
}

func (a application) help() {
	fmt.Fprintln(a.stdout, "zctl [global flags] <start|stop|restart|build|update|upgrade|status|health|logs|doctor|version>")
}
