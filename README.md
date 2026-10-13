# MKL VML sqrt SIGILLs Adam on pre-AVX2 Intel (torch CPU)

> Single repro branch of [jonathanmorley/reproductions](https://github.com/jonathanmorley/reproductions) — start here. Repo conventions live on `main`.

## Symptom

Training a small word+char BiLSTM tagger with `torch.optim.Adam`
(CPU) dies with SIGILL (exit 132). Faulthandler localizes every
crash identically — Python side:

```
File "torch/optim/adam.py", line 544 in _single_tensor_adam
File "torch/optim/adam.py", line 970 in adam
File "torch/optim/adam.py", line 248 in step
```

C side (same symbol+offset every time):

```
libtorch_cpu.so, at mkl_vml_kernel_sSqrt_Z0HAynn+0x9a
```

Disassembly of the fault site (pure-Python ELF parse + capstone,
no binutils needed on the box) shows the instruction *at* `+0x9a`
is:

```
vmovups zmm5, zmmword ptr [rip + ...]
```

EVEX-encoded AVX-512 loads — preceded by an MXCSR save/restore
dance (`vldmxcsr`), i.e. this is genuinely MKL's AVX-512 kernel
entry, not a torn pointer landing mid-function (a corrupt jump
would not land five times running on the same valid AVX-512
prologue). On Ivy Bridge every EVEX instruction is `#UD`, hence
SIGILL. The `Z0` in MKL's variant name is the AVX-512/ZMM
family; H8/L9 siblings cover lower ISAs.

The fault is stochastic per run, not per batch: identical seeded
replays crash on some runs and sail through on others (a monkey-
patched tracing run survived 1100+ batches of the exact computation
that kills untraced runs). Measured hit rate on the reference box:
3/3 seeds crashed within one epoch (~850 batches each). A clean
exit therefore proves nothing — run several seeds before concluding
anything about a given machine/build.

## Environment (reference box)

- CPU: Intel(R) Core(TM) i5-3350P (Ivy Bridge — AVX yes,
  AVX2/FMA/AVX-512 no), KVM host-passthrough (guest CPUID matches
  the silicon; no phantom flags)
- Python 3.14.7, torch 2.14.1+cpu (bundled MKL, `mkl` backend on)
- Linux 6.18 guest

Any pre-AVX2 Intel with an MKL build that ships the `Z0HAynn`
variant is plausibly affected; AVX2-or-newer silicon is most likely
(but not proven) unaffected.

## Run

No downloads, no corpus — data is synthetic and seeded:

```sh
python3 repro.py [--seed S] [--epochs N] [--sents N] [--threads T]
```

On affected hardware expect SIGILL within an epoch or two
(faulthandler prints the stack above by itself) — usually, not
always: clean exits happen (lottery), so run several seeds. The
`MKL_ENABLE_INSTRUCTIONS=SSE4_2` cap does not prevent it; capped
runs die in the same kernel.

Isolated `Tensor.sqrt` / `torch.sqrt` / `foreach` calls over many
sizes (1–2M elements), value bands (1.0 down through denormals),
alignments, and 2000 bare Adam steps over the exact param shapes
all survive — the trigger needs the full training loop (or its
allocator/threading state). Minimizing further is open.

## Thread dependence (measured)

Four single-threaded seeds (`--threads 1` + `OMP_NUM_THREADS=1`
`MKL_NUM_THREADS=1`, full 854-batch epochs, ~5.5 min each): all
clean. Against ~60% crash multi-threaded, P(4/4 clean) ≈ 2.6% —
thread-interplay is load-bearing for *something* (which family it
unlocks is open: the dispatch race needs threads by construction,
and the hang family is threading all the way down). Prime suspect
remains the 16-byte dispatch-state objects
(`__intel_mkl_feature_indicator[_x]` are OBJECTs, not code):
a torn write or init race there explains per-run decisions with
per-call H8 uniformity. Untried mitigations, cheapest first:
`KMP_BLOCKTIME=0`, `MKL_DYNAMIC=TRUE`, hard thread caps, serial
job scheduling on small boxes.

## Load modulation (inconclusive, expensive lesson)

Crash counts by era: Oct 10–11 multi-threaded 7/7 (incl. 3 resumes
sharing one ep4 state — effectively fewer independent draws);
Oct 13 multi-threaded ~2/~30 with singles 4/4 clean. No single
rate fits both eras, so *something* differs — but the load
investigation failed to name it:
- CPU-spin contention (`yes` hogs): no measurable crash-rate
  effect (and no hangs).
- Page-cache churn (8 GB streaming loop): 7–8× slowdown, steady
  progress, 1 completion, zero hangs. Six siblings "failed" only
  because the 280 s cap was set from quiet-box timing — a pure
  methodology misfire, recorded so nobody re-runs it blind.
- Verdict: load-coupling UNPROVEN in both directions. The era gap
  could equally be small-sample luck on correlated draws, kernel
  freshness (post-reboot page tables), or contention of a kind not
  tested (real memory-bandwidth pressure was never safely
  reproducible here — no swap, shared box, OOM killer risk).
Process-hygiene scar: `pkill -f` with the victim string in your own
command line kills your own shell. Match PIDs, never patterns, on
shared boxes.

## SDE mix evidence (surviving run, 94 batches)

`sde -ivb -mix` on a clean run shows the steady state that the
rare excursion breaks out of:

- `mkl_vml_kernel_sSqrt_H8HAynn` executed **exactly 1880 times** —
  every Adam sqrt call of all 94 batches × 20 params took the H8
  (pre-AVX) variant. The selector is not per-call-random here; it
  picked H8 1880/1880, so whatever flips it to Z0 is a rare,
  call-specific condition, not a coin flip.
- 50.6B `avx256` + 8.0B `avx128` instructions, **zero `avx512`
  rows** — the entire surviving run executed nothing above AVX.
- Hottest sqrt work is SSE `rsqrtps` (torch's own vectorized
  Newton–Raphson path, 24M executions) — MKL VML handles only the
  Adam-denominator calls, which is why bare-sqrt sweeps (torch
  vectorized path) can never fault: they never reach VML at all.
- Open: what per-call input flips H8→Z0 (sizes/values/alignments
  all exonerated in isolation), and why the SSE4_2 pin doesn't
  exclude Z0. Live probe: `MKL_VERBOSE=1` streams per-call
  dispatch — a crashing verbose run's last lines *are* the
  selector evidence.

## Portable run (QEMU TCG, any x86_64 host)

`./repro.sh` runs the whole recipe end to end: Debian cloud image,
torch payload ISO, TCG IvyBridge guest, verdict. Exit 1 = bug
manifested (sSqrt signature), 2 = infra failure, 0 only on a PROVEN
clean run (every seed reached SURVIVED ALL), 3 = timeout/incomplete
(no verdict possible — never report these as clean). Needs root or
passwordless sudo, ~15 GB free, and hours of wall clock.
Same job runs in CI via manual dispatch (see repo README).

Measured TCG cost (GHA `ubuntu-latest`, probe run, guest Python
3.11): pure-Python loop 0.50s native → 3.4s emulated (~7×);
2000² single-thread matmul ~0.5s native → 111.6s emulated (~200×
on vectorized numerics — the workload's bulk). A native 4-minute
seed-epoch therefore costs ~13+ emulated hours: a full run cannot
fit any CI time budget, and a 300-minute attempt expired without
finishing (correctly reported INCOMPLETE, not clean). A follow-up
full-recipe run confirmed the plumbing (offline torch install
works, seed 7 trained all 854 batches clean) and measured the
real pace: ~1.1 epochs per 5 hours. TCG
portability is measured-impractical for this workload. The native
repro above stands as the evidence; this section documents the
attempt. A clean TCG run would be a lottery miss anyway — same
one-way-test caveat as bare metal.

## Workaround

None known. `MKL_ENABLE_INSTRUCTIONS=SSE4_2` was tried and shown
insufficient (capped runs still die in the same kernel) — do not
rely on it. The operational mitigation is crash-retry: the workload
is checkpointed per epoch, so resume (`--resume` with versioned
checkpoints) rather than restart; every completed run on record is
a lottery survivor. A real fix needs Intel: the `Z0` variant is
proven AVX-512 code (disassembled fault site), so dispatching it on
AVX1-max silicon is simply wrong — the remaining question is only
what selects it per call.

## A second family: hangs under concurrency (open)

Separately from the SIGILL lottery, multi-threaded torch+MKL runs
hang: a local run burned 24 CPU-min with zero epoch output (no
faulthandler dump — pure spin, not a fault), and a 5-hour TCG guest
run (smp 2, torch 2 threads + MKL pool) never finished (`qemu
exit: 124`, verdict correctly INCOMPLETE, not clean). Concurrent
executions on small boxes have also deadlocked outright. Common
thread (ha): oversubscribed threading layers — torch intra-op pool
× MKL/OpenMP pools × libgomp-vs-libiomp nesting — with MKL's
spin-waiting turning contention into livelock. Distinct from Family
A: no faulting instruction, just silence at full CPU.

Untried mitigations, cheapest first: `KMP_BLOCKTIME=0`
(spin→sleep), `MKL_DYNAMIC=TRUE`, hard thread caps
(`OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, torch 1 thread), and —
above all — not running two heavy torch jobs on a 2-CPU box.
Single-threaded crash runs are in flight: a Family-A crash under
one thread would prove dispatch independent of threading; 4/4
clean would implicate thread-interplay in *something* (which
family, TBD).

## Verdict (Family A)

MKL dispatches its AVX-512 (`Z0`) single-precision VML sqrt kernel
on AVX1-max silicon → first `zmm` touch faults `#UD` → SIGILL,
reached deterministically from Adam's `exp_avg_sq.sqrt()`. The
*selection* of the Z0 variant is stochastic per run (identical
seeded computations diverge; isolated sqrt in all forms/sizes/
values/alignments plus 2000 bare Adam steps never fault), so the
per-call selector remains the open question — but the faulting
bytes are not in doubt. The `MKL_ENABLE_INSTRUCTIONS=SSE4_2` pin
does not reliably exclude the Z0 path (capped runs die identically),
so a proper SSE4_2 cap would have to live somewhere the VML
dispatcher actually consults — currently unknown. Not a VM
misconfiguration: the hypervisor passes the host CPU through
unaltered, `/proc/cpuinfo` matches the silicon exactly, and AVX
workloads (torch/oneDNN/numpy, hundreds of epochs) are otherwise
healthy — only this dispatch path faults. Do not "fix" by
switching the VM to a named CPU model: that risks inventing the
phantom-flag problem this box demonstrably does not have.
