#!/bin/sh
# Builds the CLEO UI mods without the Android NDK (same way as touch4/build.sh): clang + lld, linked against
# stub libc.so/libdl.so that only carry the symbol names (the real ones are on the phone).
set -e
cd "$(dirname "$0")"
OUT=${OUT:-../build/cleo-ui}
T="--target=aarch64-linux-android21"
mkdir -p "$OUT/stubs"
cat > "$OUT/stubs/c.c" <<'S'
void mprotect(void){} void getpagesize(void){}
void open(void){} void read(void){} void write(void){} void close(void){} void dl_iterate_phdr(void){}
S
cat > "$OUT/stubs/dl.c" <<'S'
void dladdr(void){} void dlopen(void){} void dlsym(void){}
S
clang $T -fPIC -nostdlib -shared -fuse-ld=lld -Wl,-soname,libc.so -o "$OUT/stubs/libc.so" "$OUT/stubs/c.c"
clang $T -fPIC -nostdlib -shared -fuse-ld=lld -Wl,-soname,libdl.so -o "$OUT/stubs/libdl.so" "$OUT/stubs/dl.c"
clang $T -O2 -fPIC -ffreestanding -fno-builtin -fno-stack-protector -fvisibility=hidden \
  -Wall -Wextra -Wno-unused-parameter \
  -nostdlib -shared -fuse-ld=lld -Wl,-soname,libCleoUIProbe64.so \
  -Wl,-z,max-page-size=16384 -Wl,--hash-style=both -Wl,-z,now -Wl,--no-undefined \
  -o "$OUT/libCleoUIProbe64.so" cleoui_probe.c -L"$OUT/stubs" -lc -ldl
llvm-strip --strip-unneeded "$OUT/libCleoUIProbe64.so" 2>/dev/null || true
echo "built $OUT/libCleoUIProbe64.so"
