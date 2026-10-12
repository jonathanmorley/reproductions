# Reproductions

House (and share) reproductions of problematic situations — one
independent repro per branch.

## For humans and AI agents alike

- Start at the index below, then read the branch's root `README.md`
  — every repro is self-contained (symptom, environment, run
  instructions, verdict).
- Layout convention: a repro branch carries its files at the TOP
  level — root `README.md` (required: the repro doc; overwrites
  this file as inherited from `main`), an executable `repro.sh`
  (required: no args; see exit codes below), supporting files
  beside them. No subdirectories for separation; the branch is the
  namespace. (One legacy branch keeps its doc nested; the index
  tolerates exactly one level.)
- Branches are the unit of separation and are generally NOT
  merged. `main` carries only shared plumbing: this file, generic
  CI, license. Short-lived automation (`ci/*`, `renovate/*`,
  `github/*`) is exempt from the repro rule and ignored by the
  index.
- CI semantics are inverted by design: a repro job is RED when the
  bug manifests — that is the finding, not a failure of the repo.
  Read the branch's `REPRO.md` before interpreting any check.

## Running any repro

Manual dispatch: Actions → `repro.yaml` → Run workflow → enter the
repro branch name. The generic job checks out that branch and runs
`./repro.sh`, streaming everything to the job log.

Contract for `repro.sh`: executable, no arguments; exit `1` iff the
bug manifests, `2` on infra failure (environment never reached the
bug), `3` on timeout/incomplete (no verdict possible — never report
these runs as clean), `0` only on a proven-clean run. Echo
`SETUP-FAILED` (infra) or the branch's documented signature (bug)
so the log is greppable. The workflow passes the exit code through
unchanged.

Runner requirements: x86_64 Linux, root or passwordless sudo,
~15 GB free disk, generous wall clock (lottery-class bugs need
repeated attempts; see the branch for budgets).

## Adding a repro

1. Branch from `main`: `<area>/<short-slug>`.
2. Flat files at root: `README.md` (symptom, environment, run,
   verdict, negatives — overwrites this file), executable `repro.sh`
   per the contract above, supporting files.
3. Push — the index below updates itself via PR (see
   `index-branches.yml`).

## Index

<!-- REPRO-INDEX:START -->
<!-- REPRO-INDEX:END -->
