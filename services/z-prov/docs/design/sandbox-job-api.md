# Sandbox job API

`zeaz-sandbox` is a separate process and Python distribution. The provider
gateway does not import it and never executes jobs.

Every job contains immutable argv: a JSON array of bounded strings. There is
no shell-command field, environment field, working-directory override, or
provider credential field. Images use an exact `name@sha256:<digest>`
reference. A single absolute workspace is mounted read-only by default;
read-write access is an explicit policy change.

The complete job specification is canonically serialized and SHA-256 hashed.
An execution approval binds that digest, job and session identifiers, actor,
permission-decision identifier, creation time, and expiry. The service rejects
an approval before or after its validity interval and changing argv, image,
workspace, network, or any resource limit invalidates it.

Networking is disabled by default. Allow-list mode requires exact hosts and
ports. Wildcards, loopback, multicast, unspecified, link-local, and cloud
metadata destinations are always forbidden.

Every terminal attempt produces an immutable receipt binding job, approval,
resolved image digest, policy digest, terminal state, bounded-output counts,
timestamps, cleanup state, and a sanitized failure code.
