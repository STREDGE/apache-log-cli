#!/bin/sh
# Builds libHelicoverBrain64.so (the phone build) without the Android NDK, the same way as touch4/build.sh:
# clang + lld, linked against stub libc.so / libdl.so that only carry the symbol names.
# The core is compiled with the same floating-point rules as the host build (-ffp-contract=off).
set -e
cd "$(dirname "$0")"
OUT=${OUT:-../build/brain}
T="--target=aarch64-linux-android21"
mkdir -p "$OUT/stubs"
cat > "$OUT/stubs/c.c" <<'S'
void mprotect(void){} void getpagesize(void){}
void open(void){} void read(void){} void write(void){} void close(void){} void dl_iterate_phdr(void){}
void pthread_create(void){} void usleep(void){} void clock_gettime(void){} void syscall(void){} void sigaction(void){}
S
cat > "$OUT/stubs/dl.c" <<'S'
void dladdr(void){} void dlopen(void){} void dlsym(void){}
S
clang $T -fPIC -nostdlib -shared -fuse-ld=lld -Wl,-soname,libc.so -o "$OUT/stubs/libc.so" "$OUT/stubs/c.c"
clang $T -fPIC -nostdlib -shared -fuse-ld=lld -Wl,-soname,libdl.so -o "$OUT/stubs/libdl.so" "$OUT/stubs/dl.c"
clang $T -O2 -fPIC -ffreestanding -fno-builtin -fno-stack-protector -fvisibility=hidden -ffp-contract=off $BRAIN_DEFS \
  -Wall -Wextra -Wno-unused-parameter -Wno-unused-function \
  -nostdlib -shared -fuse-ld=lld -Wl,-soname,libHelicoverBrain64.so \
  -Wl,-z,max-page-size=16384 -Wl,--hash-style=both -Wl,-z,now -Wl,--no-undefined \
  -o "$OUT/libHelicoverBrain64.so" game/brain.c core/hcb_core.c core/hcb_fire.c core/hcb_libc.c -L"$OUT/stubs" -lc -ldl
llvm-strip --strip-unneeded "$OUT/libHelicoverBrain64.so" 2>/dev/null || true
echo "built $OUT/libHelicoverBrain64.so"
