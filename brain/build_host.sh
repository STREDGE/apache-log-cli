#!/bin/sh
# Builds the brain's core for THIS computer (not the phone) so the tests and the simulated fights can drive it
# through ctypes. Same sources and the same floating-point rules as the phone build (-ffp-contract=off: a recorded
# fight must replay bit for bit), no libc.
set -e
cd "$(dirname "$0")"
OUT=${OUT:-../build/brain}
mkdir -p "$OUT"
clang -O2 -fPIC -ffreestanding -fno-builtin -fno-stack-protector -fvisibility=hidden -ffp-contract=off \
  -Wall -Wextra -Wno-unused-parameter -Wno-unused-function \
  -nostdlib -shared -o "$OUT/libhcbcore_host.so" core/hcb_core.c core/hcb_libc.c
if nm -D --undefined-only "$OUT/libhcbcore_host.so" | grep -q .; then
  echo "the core must not need anything from outside:"; nm -D --undefined-only "$OUT/libhcbcore_host.so"; exit 1
fi
echo "built $OUT/libhcbcore_host.so"
