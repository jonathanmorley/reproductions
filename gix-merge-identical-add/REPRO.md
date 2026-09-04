# gix-merge: identical add/add reported as `Err(Unknown)`

**Crates:** `gix-merge 0.20.1` (via `gix 0.87.1`)
**Status:** reproduced, minimization open (see below)

## Symptom

In a multi-file three-way tree merge, when both sides add the same path
with the **byte-identical blob**, `merge_trees` reports the entry as
`Err(Unknown)` instead of auto-resolving. Git merges the identical inputs
cleanly.

Observed conflict entry (shortened):

```
ours=Addition {
  location: "examples/resources/repository_private_vulnerability_reporting/example_1.tf",
  entry_mode: 100644,
  id: 049444c2236ddc48c12ac711498a17fb04629d83,   // <-- same blob
}
theirs=Addition {
  location: "examples/resources/repository_private_vulnerability_reporting/example_1.tf",
  entry_mode: 100644,
  id: 049444c2236ddc48c12ac711498a17fb04629d83,   // <-- same blob
}
resolution=Err(Unknown)
```

## Full-fidelity reproduction (git side)

The inputs are public, immutable SHAs in
`jonathanmorley/terraform-provider-github` (a fork whose branches share
history with `integrations/terraform-provider-github@main`):

```bash
git clone --bare https://github.com/jonathanmorley/terraform-provider-github.git repro.git
cd repro.git
git fetch https://github.com/integrations/terraform-provider-github.git \
  "refs/heads/main:refs/heads/upstream-main"

# Layer-1 equivalent: ancestor = merge-base, ours = patch-0 tip, theirs = patch-1 tip.
# Ancestor and ours here:
git merge-tree 3ac346fdfbee2e19589a6203b20d936189ba0760 \
  f1beca348f4beb80688c0046aec6cbfb4c435596 \
  2b8bcab30cc83260154dce6a885a29cb17e6ffcf
# => exit 0, no conflict markers. Git is clean.
```

The gix side (same ancestor/ours/theirs through
`Repository::merge_trees` with default `tree_merge_options`) reports two
conflicts: the identical-add above, plus an auto-resolved content merge
(which is listed by design — see `Outcome::conflicts` docs — and is *not*
part of this report).

## Fixtures

`provider_v*.go` are the three states of an adjacent auto-resolved file
from the same merge (`github/provider.go` at ancestor / layer result /
stacked tip), useful for testing `has_unresolved_conflicts` semantics:

| file | role | blob |
|---|---|---|
| `provider_v0.go` | ancestor | `73e93dc5…` |
| `provider_v1.go` | ours (layer result) | `ec0fa30e…` |
| `provider_v2.go` | theirs (stacked tip) | `6f2bf85f…` |

## What was ruled out

- **Single-file identical-add is clean.** Ancestor empty (or `{base.txt}`),
  both sides adding the same file and blob: zero conflicts listed, with and
  without rename tracking. The trigger needs multi-file/tree context —
  the live entries carried differing `ChildOfParent` directory relations
  (`(2)` vs `(3)`), suggesting directory-level rename pairing sweeps the
  agreed file into `Unknown`.
- **Rename toggle is not the (whole) story.** Disabling rewrites
  (`Options::with_rewrites(None)`) does not change the outcome on the live
  inputs; the identical-add entry persists.
- **Not this:** gix listing auto-resolved entries in `conflicts` is
  documented behavior (`Outcome::conflicts` — "listed here for
  completeness", judge with `has_unresolved_conflicts()`). Only the
  identical-add `Err(Unknown)` is reported here.

## Minimal trigger: open

A single-file synthetic repro does not trigger it; the exact minimal
conditions (tree size? directory similarity? relation state?) are
unestablished. The SHAs above reproduce it at full fidelity.
