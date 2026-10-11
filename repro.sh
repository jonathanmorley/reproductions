#!/bin/bash
# Repro entrypoint: full TCG-IvyBridge run of the MKL SIGILL repro.
# Contract (see ../README.md): no args; exit 1 iff the bug manifests
# (sSqrt SIGILL signature in guest output), 2 on infra failure,
# 0 on a clean run. Everything streams to stdout (the CI log).
# Requirements: x86_64 Linux, root or passwordless sudo, ~15 GB free.
set -u
QEMU_TIMEOUT_MIN="${QEMU_TIMEOUT_MIN:-300}"

fail() { echo "SETUP-FAILED: $1"; exit 2; }

echo "=== host tools ==="
sudo apt-get update -qq
sudo apt-get install -y -qq qemu-system-x86 qemu-utils cloud-image-utils genisoimage python3-pip

echo "=== guest image ==="
test -f debian.qcow2 || curl -fSL -o debian.qcow2 https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-genericcloud-amd64.qcow2
qemu-img resize debian.qcow2 +10G

echo "=== payload ISO (torch wheels + repro, host-side) ==="
mkdir -p payload/wheels
python3 -m pip download -q --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple --dest payload/wheels "torch==2.14.1" || fail "pip download"
cp repro.py tcg/setup.sh payload/
ls payload/wheels/
test -f payload/wheels/torch-*.whl || fail "no torch wheel downloaded"
command -v genisoimage >/dev/null || fail "no genisoimage"
genisoimage -o data.iso -V DATA -R -J payload/

echo "=== NoCloud seed ==="
cloud-localds seed.iso tcg/user-data tcg/meta-data || fail "seed build"

echo "=== TCG IvyBridge guest (up to ${QEMU_TIMEOUT_MIN}m) ==="
timeout "${QEMU_TIMEOUT_MIN}m" qemu-system-x86_64 \
  -accel tcg -cpu IvyBridge -m 4096 -smp 2 \
  -drive file=debian.qcow2,format=qcow2,if=virtio \
  -drive file=seed.iso,format=raw,if=virtio \
  -drive file=data.iso,format=raw,if=virtio,readonly=on \
  -netdev user,id=n0 -device virtio-net-pci,netdev=n0 \
  -nographic > serial.log 2>&1 || echo "qemu exit: $?"
test -f serial.log || fail "no serial log"

echo "=== verdict ==="
if grep -q "mkl_vml_kernel_sSqrt" serial.log; then
  echo "REPRODUCED: sSqrt SIGILL signature in serial log"
  grep -B6 "mkl_vml_kernel_sSqrt" serial.log | head -14
  exit 1
elif grep -q "SETUP-FAILED" serial.log; then
  echo "INFRA FAILURE inside guest (see above)"; exit 2
else
  echo "NOT reproduced: clean run, no sSqrt signature"
  exit 0
fi
