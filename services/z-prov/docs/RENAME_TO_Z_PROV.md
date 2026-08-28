# Source Repository Rename: `zeaz-provider` to `z-prov`

This migration renames the source checkout and GitHub repository slug from
`zeaz-provider` to `z-prov` for the `0.4.0rc1` release candidate. It does not
rename the installed application identity. Keeping runtime identifiers stable
allows existing installations, configuration, imports, service units, and
container deployments to continue working after the source checkout moves.

## Identity contract

| Surface | Keep or change | Value | Reason |
| --- | --- | --- | --- |
| Local checkout directory | Change | `z-prov` | Short source workspace name |
| GitHub repository slug | Change | `z-prov` | Short repository URL and remote name |
| Python distribution | Keep | `zeaz-provider` | Existing wheel/install identity |
| Python import package | Keep | `zeaz_provider` | Existing imports and package layout |
| CLI entry point | Keep | `zeaz-provider` | Existing scripts and user commands |
| Systemd units and install prefix | Keep | `zeaz-provider` | Existing service/state upgrade path |
| Environment variables | Keep | `ZEAZ_*` | Existing deployment configuration |
| Provider Docker image | Keep | `zeaz/provider` | Image namespace is independent of source slug |

Changing the kept identifiers is a separate breaking migration. If a future
release introduces a `z-prov` CLI or image namespace, it should provide an
explicit compatibility alias and a documented state migration first.

## Safe checkout migration

Run these commands from the parent directory of the checkout. Stop any local
development process that has the old directory as its working directory before
moving it.

```bash
mv zeaz-provider z-prov
cd z-prov
git remote set-url origin git@github.com:<OWNER>/z-prov.git
make validate
docker compose config --quiet
```

The installer state under `~/.local/share/zeaz-provider`, the user service
names, and the command in `~/.local/bin/zeaz-provider` are intentionally not
moved by this source checkout operation. They are runtime state, not source
repository paths.

## Release and update metadata

Release archives may be stored in the renamed GitHub repository, but their
wheel, executable, import package, and update-installation behavior must keep
the `zeaz-provider` names shown in the identity contract. Replace the
`OWNER/REPOSITORY` placeholders in a deployment-specific update manifest with
the actual `z-prov` repository URL; do not change the wheel or executable names
as part of this repository rename.
