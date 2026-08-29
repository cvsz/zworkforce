# zDash integration

`cvsz/zdash` is integrated into Z Platform as the Git-linked application at `apps/zdash`.

## Pinned source

- Repository: `https://github.com/cvsz/zdash`
- Branch policy: `main`
- Imported commit: `dc73d38fe38755ef777167101abf29707278db53`

The superproject pins an exact commit. Updating the `zdash` repository does not silently change a Z Platform release.

## Clone

```bash
git clone --recurse-submodules https://github.com/cvsz/z-platform.git
```

For an existing clone:

```bash
git submodule sync --recursive
git submodule update --init --recursive
```

## Update procedure

```bash
cd apps/zdash
git fetch origin main
git checkout <reviewed-zdash-commit>
cd ../..
git add apps/zdash
git commit -m "chore(zdash): update pinned application revision"
```

Open a Z Platform pull request and run both repositories' validation suites before changing the pinned revision.

## Boundaries

- `zdash` keeps its own application history, license, workflows, backend, frontend, deployment assets, and release process.
- Z Platform owns the pinned revision and integration/deployment contract.
- Root-level files from `zdash` do not overwrite Z Platform root configuration.
- GitHub Actions inside the submodule are not executed as Z Platform workflows; validate `cvsz/zdash` independently before updating the pin.
