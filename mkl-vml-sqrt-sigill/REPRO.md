# MKL VML sqrt SIGILLs Adam on pre-AVX2 Intel (torch CPU)

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

i.e. Adam's `denom = (exp_avg_sq.sqrt() / ...)` dispatches MKL's
single-precision VML sqrt `Z0HAynn` variant, and the CPU refuses
the instruction.

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

## Workaround

None known. `MKL_ENABLE_INSTRUCTIONS=SSE4_2` was tried and shown
insufficient (capped runs still die in the same kernel) — do not
rely on it. The operational mitigation is crash-retry: the workload
is checkpointed per epoch, so resume (`--resume` with versioned
checkpoints) rather than restart; every completed run on record is
a lottery survivor. A real fix needs Intel (dispatch bug) or newer
silicon (if the `Z0HAynn` variant genuinely requires post-AVX ISA
— unestablished; the pin's failure cuts against the simple
AVX2-dispatch story and toward a torn-dispatch-pointer race, but
neither is proven).

## Verdict

Something in MKL's sqrt dispatch path faults on pre-AVX2 silicon
(`#UD` inside `sSqrt_Z0HAynn`, reached deterministically from
Adam's `exp_avg_sq.sqrt()` but only on some runs). Two candidate
mechanisms, neither proven: (a) length/shape-dependent dispatch
emitting a post-AVX kernel the CPU lacks; (b) a torn dispatch
pointer / init race landing mid-function (`+0x9a`). The pin's
failure to prevent it cuts against the simple form of (a) — unless
the pin doesn't reach VML dispatch at all. Not a VM
misconfiguration: the hypervisor passes the host CPU through
unaltered, `/proc/cpuinfo` matches the silicon exactly, and AVX
workloads (torch/oneDNN/numpy, hundreds of epochs) are otherwise
healthy — only this dispatch path faults. Do not "fix" by
switching the VM to a named CPU model: that risks inventing the
phantom-flag problem this box demonstrably does not have.
