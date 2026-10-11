#!/bin/bash
# First-boot setup inside the TCG Debian guest (written by cloud-init
# write_files, run via runcmd). Everything below goes to the serial
# console (host greps it) AND /root/setup.log. Stage gates abort with
# SETUP-FAILED — distinct from a meaningful NOT-REPRODUCED.
exec > >(tee /dev/console /root/setup.log) 2>&1
set -u

echo "=== net probe (apt needs it; torch does not) ==="
ip -brief addr || true
curl -sSI --max-time 20 http://deb.debian.org/ -o /dev/null -w "debian http=%{http_code}\n" || echo "NETWORK DOWN (apt will fail)"

echo "=== payload mount (already mounted by runcmd; tolerate) ==="
mkdir -p /mnt/data
mount -L DATA /mnt/data 2>/dev/null || true
ls /mnt/data | head -8
test -d /mnt/data/wheels || { echo "SETUP-FAILED: no wheels dir"; poweroff -f; }

echo "=== python env ==="
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv python3-pip
python3 --version
python3 -m venv /root/venv
test -x /root/venv/bin/pip || { echo "SETUP-FAILED: no venv pip"; poweroff -f; }

echo "=== torch offline install (host-pinned wheels, no index) ==="
/root/venv/bin/pip install -q --no-index --find-links=/mnt/data/wheels "torch==2.14.1" || { echo "SETUP-FAILED: torch install"; poweroff -f; }
/root/venv/bin/python3 -c "import torch; print('torch', torch.__version__)" || { echo "SETUP-FAILED: torch import"; poweroff -f; }

cp /mnt/data/repro.py /root/repro.py
cd /root
: > repro-serial.log
for seed in 7 11 23 42 99; do
  echo "=== seed $seed ===" | tee -a repro-serial.log
  /root/venv/bin/python3 -u repro.py --seed "$seed" 2>&1 | tee -a repro-serial.log
  grep -q "mkl_vml_kernel_sSqrt" repro-serial.log && break
done
if grep -q "mkl_vml_kernel_sSqrt" repro-serial.log; then
  echo "GUEST VERDICT: REPRODUCED"
else
  echo "GUEST VERDICT: NOT-REPRODUCED"
fi
poweroff -f
