#!/bin/bash
# First-boot setup inside the TCG Debian guest (cloud-init runcmd).
# Serial console carries everything; host greps it for the verdict.
set -u
REPRO_REF="mkl/vml-sqrt-sigill-ivy-bridge"

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv python3-pip curl
python3 -m venv /root/venv
/root/venv/bin/pip install -q "torch==2.14.1" --index-url https://download.pytorch.org/whl/cpu
curl -fsSL "https://raw.githubusercontent.com/jonathanmorley/reproductions/${REPRO_REF}/mkl-vml-sqrt-sigill/repro.py" -o /root/repro.py
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
