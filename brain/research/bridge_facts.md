# Helicover Brain: script <-> native bridge on the player's CLEO build

Subject: `libSAcleo64.so` "CLEO ANDROID (64-260403)" (packed file sha1 `03276a2e...`, unpacked inner library sha1
`1f21bba1...`) and `libGTASA.so` 2.10 arm64 with fastman92 sections (54 731 968 bytes, sha1 `7fc29a2b...`).

Address conventions
- **CLEO addresses** are *image-relative*: offset inside the unpacked library = offset in `cleolib/inner.bin`.
  At run time: `dl_iterate_phdr` base of `libSAcleo64.so` + `0x88000` + offset (the same convention as `cleoui.c`,
  where `CLEO_IMAGE = 0x88000`). Below, `I` = that run-time start of the unpacked library.
- **Game addresses** are offsets from the load base of `libGTASA.so` (`G` below).

Levels of proof used in this file
- **[E]** executed: the real code of the image was run in unicorn (`test_bridge.py`, `test_loop.py`, all checks pass).
- **[D]** read from the disassembly (address given), not executed.
- **[S]** read from upstream source/header (AML, SAUtils, Sanny library), not from the binaries on the device.
- **[I]** inferred. Nothing in this file was run on the phone.

---------------------------------------------------------------------------------------------------------------------

## 0. The short answer

1. **Primary bridge: a private opcode registered through CLEO's own plugin interface.** This CLEO build contains the
   classic CLEO-Android plugin interface (`cleo_ifs_t`, 28 function pointers) as a static table at `I+0x27d9b8`. Slot 17
   is `RegisterOpcode(u16 opcode, handler)`. CLEO's script loop asks this opcode map *before* it hands an opcode to the
   game. The handler gets the real 64-bit `CRunningScript*`, so it can take a pointer to script variables and read or
   write a whole block (locals are contiguous `int32` at `script+0x6c`). One opcode per frame, synchronous, no 32-bit
   pointer problem at all. [E]
2. **Fallback and handshake: the 0DDC/0DDD storage read and written in place.** It is a `std::vector` of 8-byte
   `{u32 key, u32 value}` whose header (begin, end, capacity) sits at `I+0x7d1f8`. The native mod may change the value
   of an entry that a script has created; it must never append. [E]
3. Scripts must not run the private opcode before a handshake says the mod is there (an unknown opcode is not skipped:
   its parameter bytes get executed as opcodes). [E]
4. What does **not** work: `0DD1` cannot see symbols of another `.so` (it only asks `libGTASA.so`) [D]; a block mapped
   below 4 GB cannot be addressed by `0DD8/0DD9` (refused, or silently redirected to another address) [E]; `0DD3`
   cannot pass a 64-bit pointer (zero-extends 32 bits) [E]; no opcode loads a library or does `dlsym` [D].

---------------------------------------------------------------------------------------------------------------------

## 1. How CLEO runs scripts (answers question 3)

| Fact | Evidence |
|---|---|
| CLEO resolves game symbols with `GlossSymbol(handle of "libGTASA.so", name)` in `0x2efac` and stores them: `[0x7d220]` ScriptParams, `[0x7d218]` &CTimer::m_snTimeInMilliseconds, `[0x7d238]` CTheScripts::StartNewScript, `[0x7d240]` CRunningScript::GetPointerToScriptVariable, `[0x7d248]` CRunningScript::CollectParameters, `[0x7d250]` CRunningScript::UpdateCompareFlag, `[0x7d2a0]` and `[0x7d2a8]` CRunningScript::ProcessOneCommand, `[0x7d1a0]` = `[0x27d318]` load bias of libGTASA, `[0x27d320]` Gloss handle of libGTASA | [D] 0x2efac..0x2f4f0, 0x2f538..0x2f5c0 |
| It installs inline hooks (GlossHook) on `CTheScripts::Load` (handler 0x2d384), `CTheScripts::Save` (0x2dccc), `CTheScripts::Init` (0x2dbc0), `CRunningScript::Process` (0x2de20, original via `[0x7d298]`), `CText::Get` (0x2e23c), `AND_TouchEvent` (0x2e50c), `AND_KeyboardEvent` (0x2e564), `OS_FileOpen` (0x2e758), and `CHud::Draw` (0x363c0). `ProcessOneCommand` is **not** hooked: CLEO calls it by address | [D] 0x2f31c..0x2f3f8 |
| Script files: every `*.csa` / `*.csi` in `getenv("EXTERNAL_STORAGE") + "/cleo/sa/"`; log `EXTERNAL_STORAGE/cleo/cleo.log` | [D] 0x2e5c0, 0x2e6b4, 0x32554 |
| Script code is copied into a **static arena inside the CLEO image**: `I+0x7d310`, bytes used = `u32 [I+0x27d310]` (room 0x200000). So every label address of a CLEO script lies inside the CLEO image | [D] 0x2f630 |
| Per script a heap object of 0x148 bytes: `+0x00` std::string name, `+0x18` i32 invokable index (-1 = normal script), `+0x20` `CRunningScript*`, `+0x28` code base, `+0x30` u32 code size, `+0x38` code start, `+0x40` u8 "start delay armed", `+0x48` u64 ctx[32] (registers of 0DD2..0DD4). List: `std::vector<obj*>` begin `I+0x7d188`, end `I+0x7d190`, cap `I+0x7d198` | [D] 0x2f630, 0x2de20 |
| After the original `CTheScripts::Init` and after the original `CTheScripts::Load` CLEO reloads all scripts (0x2d480), **empties the 0DDC/0DDD vector** (`end = begin`), and starts every normal script with `CTheScripts::StartNewScript(code)`; the returned `CRunningScript*` goes to `obj+0x20` | [D] 0x2dbc0..0x2dcc8, 0x2d384..0x2d47c |
| So CLEO scripts are ordinary members of `CTheScripts::pActiveScripts` and are executed by the game's own loop: `CTheScripts::Process` (G+0x3f3ad8) walks the list and calls `CRunningScript::Process` (`bl` at G+0x3f3e1c) | [D] G+0x3f3dc4..0x3f3e2c |
| CLEO's hook of `CRunningScript::Process` (0x2de20): a script that is not in CLEO's list goes to the original. A CLEO script is interpreted by CLEO's own loop: opcodes 0002, 004C, 004D, 0050, 0051, 004E, 05DC and a special form of 00E1/80E1 are done by CLEO; every other opcode goes 1) to the built-in handler `0x2fb2c` (0DD0..0DF6), 2) if that returns 0, to the plugin dispatcher `0x37904`, 3) if that returns 0, `ip -= 2` and the game's `ProcessOneCommand` is called; the loop ends when `ProcessOneCommand` returns non-zero | [D] 0x2de90..0x2e120, [E] test_loop.py |
| The first pass after a (re)start only arms a delay: `script+0x11c = now + 3000` ms; the script really starts 3 s later | [E] test_loop.py, [D] 0x2df28, 0x2e190 |
| Jumps and gosubs of a CLEO script are done by CLEO because the code is outside `ScriptSpace`: target = `obj.code_base + abs(offset)`. The label parameter must be type 01 (int32); any other type -> log "wrong param type in '%s' at %ld, terminating" and `exit(1)` | [D] 0x2e028..0x2e098, 0x2e1b4..0x2e1f4 |
| Frame: `Idle` (G+0x4d8e60) -> `CGame::Process` (G+0x4d62d4) -> `if (!(CTimer::m_CodePause \| CTimer::m_UserPause)) { ... CTheScripts::Process(); ... }` (the `bl` at G+0x4d63dc goes through PLT stub G+0x228710 and GOT slot **G+0x845438**) | [D] G+0x4d6394..0x4d63dc |
| `CTheScripts::Process` has 4 more callers through the same PLT slot: `CEntryExit::TransitionFinished+0x7e4`, `CGame::Initialise+0x64`, `CGame::ReInitGameObjectVariables+0x1bc`, `CGenericGameStorage::DoGameSpecificStuffAfterSucessLoad+0xbc` | [D] gcallers.py |
| arm64 `CRunningScript` fields seen in the code: `+0x00` next, `+0x10` name, `+0x20` ip (64-bit pointer), `+0x28` gosub stack (8 pointers), `+0x68` u16 stack depth, **`+0x6c` local variables, 4 bytes each, contiguous** (index*4), `+0x10c`/`+0x110` the two timers (= locals 40 and 41), `+0x115` condition result, `+0x11c` wake time, `+0x122` "not" flag, `+0x12c` is-mission flag (mission scripts use `CTheScripts::LocalVariablesForCurrentMission` instead) | [D] G+0x3f2654.., G+0x3f1fcc.., G+0x3f3ddc, 0x2de68 |

### Where the native per-frame hook should sit

- **Before the scripts, once per frame, only while unpaused: swap GOT slot `G+0x845438`** (JUMP_SLOT of
  `_ZN11CTheScripts7ProcessEv`, expected content `G+0x3f3ad8`). Your function does its work and then calls the saved
  pointer. The only code that reads this slot is PLT stub `G+0x228710` [D]. The slot is inside PT_GNU_RELRO
  (`G+0x821958 .. G+0x852000`), so it needs `mprotect(RW)` / write / `mprotect(R)`, exactly what `touch4.c` already does
  for its GOT entry.
  - Unpaused only: proven by the test in `CGame::Process` quoted above [D].
  - "Once per frame" needs one guard: the 4 extra callers (new game, load, entering/leaving an interior) call it again
    outside the normal place. Compare `CTimer::m_FrameCounter` (`u32` at G+0xbdc590; used by `CTimer::Update` and
    compared per frame in `CHud::Draw`; its exact update was not traced [I]) or `CTimer::m_snTimeInMilliseconds`
    (G+0xbdc558) with the value of the previous call.
  - The slot holds `G+0x3f3ad8` only because Android's linker binds PLT slots when the library is loaded (the file
    itself holds the lazy stub `G+0x218e90`) [I]; the value check before the swap covers this.
  - First 4 words of `CTheScripts::Process`: `d10203ff fd000be8 a9026ffc a90367fa` (sub sp / str d8 / stp / stp), all
    position-independent, if an inline hook is ever wanted. The GOT slot is preferable: no code is changed.
- **With the primary bridge the opcode handler itself is the second per-frame entry**: it runs inside the script's
  turn, exactly when the script asks, and only while scripts run (so only unpaused).
- Do **not** inline-hook `CRunningScript::Process` or `CHud::Draw`: CLEO has already rewritten their first
  instructions at run time (GlossHook) [D for the hook calls, I for the exact bytes on the device].
- `CRunningScript::Process` contains its own copy of the opcode loop (G+0x3f400c..0x3f4060) and does not call
  `ProcessOneCommand`; only CLEO calls `ProcessOneCommand` (for CLEO scripts) [D].

---------------------------------------------------------------------------------------------------------------------

## 2. CLEO opcodes 0DD0..0DF6 on this build (answers question 1)

Dispatcher: `0x2fb2c(obj, opcode)`; jump table of 0x27 16-bit entries at `0x1c0ca`, target = `0x2fb88 + 4*entry`.
It compares the full 16-bit opcode: the "not" forms (8DDx) are **not** recognised [D 0x2fb50]. Returns 1 = handled.
"var" = a variable parameter read with `GetPointerToScriptVariable` (the handler writes 32 bits through the pointer);
"int" = a value read with `CollectParameters`. The order below is the order in the bytecode (output variable first),
and it matches what `build_v25.py` already emits for 0DD0, 0DD8, 0DDC, 0DDD, 0DF2, 0DF4.

| Opcode | Handler | Bytecode parameters | Behaviour | Proof |
|---|---|---|---|---|
| 0DD0 | 0x2fb88 | var, int label | `p = obj.code_base + abs(label)`; var = low 32 bits of p; `map[low32] = p` (see 2.1) | [E] |
| 0DD1 | 0x30014 -> 0x30f28 | var, int pointer to a C string | string pointer resolved by 2.1; `p = GlossSymbol([0x27d320] = handle of libGTASA.so, name, 0)` (xdl_sym then xdl_dsym on that one library); var = low 32 bits; `map[low32] = p`; if the symbol's first qwords look like pointers it is also remembered as a pointer table (set at `0x7d1e0`). **Only libGTASA.so is searched; a symbol of another .so cannot be found.** No dlsym/dlopen here | [D] |
| 0DD2 | 0x30178 -> 0x30cb0 | int address | address resolved by 2.1 (no image-base flag); if its high 32 bits are 0 nothing happens; else `asm_call(obj+0x48, addr)` = load x0..x7 from ctx[0..7], `blr`, store x0 to ctx[0] (0x3a460) | [E] |
| 0DD3 | 0x2ff80 | int reg, int value | if reg < 32: `ctx[reg] = (u64)(u32)value` (zero-extended; no pointer resolution). Only ctx[0..7] are ever loaded into registers | [E] |
| 0DD4 | 0x2ffbc | var, int reg | var = low 32 bits of ctx[reg] (0 if reg >= 32). Only ctx[0] is updated by a call | [E] |
| 0DD5 | 0x30228 | var | var = 2 | [E] |
| 0DD6 | 0x2fe9c | var | var = `[0x7d148]`; the only writer stores 1 (0x2f5d4, next to the log line "game ver: GTASA 2.10 arm64-v8a") | [D] |
| 0DD7 | 0x2febc | var | var = low 32 bits of `[0x7d1a0]` (load bias of **libGTASA.so**); `map[low32] = full` | [E] |
| 0DD8 | 0x300e8 | var, int address, int size, int add_ib | see 2.2 | [E] |
| 0DD9 | 0x300a8 | int address, int value, int size, int add_ib, int vp | see 2.2 | [E] |
| 0DDA | 0x30264 -> 0x310d0 | var, int pointer to pattern, int index | pattern pointer resolved by 2.1; `0x39734(&out, pattern, index)` searches the executable part of libGTASA; var = low 32 bits of the hit (and `map` entry), 0 if not found | [D] |
| 0DDB | 0x2fdf0 | var, var, var | hash of the package name (string `0x7d150`), hash of the version string (`0x7d168`), version code (`[0x7d180]`) | [D] |
| 0DDC | 0x2fd78 | int key, int value | set shared value, see 3 | [E] |
| 0DDD | 0x30340 | var, int key | var = shared value, 0 if the key does not exist | [E] |
| 0DDE | 0x30140 -> 0x3099c | int address, int add_ib, then pairs {8 raw bytes type text, parameter}, then one 0 byte | call a function with typed arguments, see 2.3 | [E] |
| 0DDF, 0DE4..0DED | - | - | not handled here (0 is returned; the opcode goes on to the plugin map, then to the game) | [D] jump table |
| 0DE0 | 0x301e4 | var, int touch point, int min time | var = 0/1 from 0x361b4 (touch point state) | [D] skimmed |
| 0DE1 | 0x302ec | var, int from, int to, int min time, int max time | var = 0/1 from 0x3624c (slide) | [D] skimmed |
| 0DE2 | 0x30244 | var | var = byte `[0x27d3b0]` (menu button state) | [D] |
| 0DE3 | 0x2fc7c | var, int min time | var = 0/1 from 0x3637c (menu button pressed) | [D] skimmed |
| 0DEE | 0x2fe68 | var, var | number of invokable scripts, and that number / 12 + 1 | [D], meaning [I] |
| 0DEF | 0x303c4 | var, int index | start invokable script: var = 0 started, 1 restarted, 2 already running, -1 not found | [D] |
| 0DF0 | 0x2fcc0 | none | show the "OPEN CLEO MENU" hint for 7 s (0x36924) | [D] |
| 0DF1 | 0x2fe60 | none | hide the hint (0x36964) | [D] |
| 0DF2 | 0x2fd0c | int pointer, int item count | create the touch menu from the description at the pointer (resolved by 2.1) | [D] |
| 0DF3 | 0x300a0 | none | delete the menu (0x36a9c) | [D] |
| 0DF4 | 0x2fcc8 | var, int max time | var = selected item if it was touched less than max time ms ago, else -1 (0x36a54) | [D] |
| 0DF5 | 0x3047c | int index | set the active item / page (0x36acc) | [D] |
| 0DF6 | 0x30450 | var | var = active item `[0x7cfd0]` (0x36b10) | [D] |
| 1000 | 0x37904 | long string (type 0E, length byte, text) | call a function a plugin registered by name (`RegisterOpcodeFunction`). **If the name is unknown CLEO logs "1000: func '%s' not found" and calls `exit(1)`** | [D] 0x37994..0x37c4c |

Nothing in this range (or elsewhere) loads a library or resolves a symbol in another library: `dlopen` is called only
from the plugin loader (0x38338), GlossOpen (0x41a18) and xdl (0x45600); `dlsym` only from the plugin loader
(0x38370, for `plugin_init`) [D, xref.py].

### 2.1 How a 32-bit script value becomes a 64-bit address

Script variables are 32-bit. CLEO keeps a table of the pointers it has handed out and widens 32-bit values with
`resolve(v, obj)` at `0x2d288` (the same logic is inlined in several handlers):

1. Look `v` up in a `std::map<u32, u64>` (libc++ tree: begin-node pointer `I+0x7d1c8`, end node whose `left` is the
   root `I+0x7d1d0`, size `I+0x7d1d8`; node = left `+0`, right `+8`, parent `+0x10`, colour `+0x18`, key u32 `+0x20`,
   value u64 `+0x28`, 0x30 bytes). Found -> that 64-bit value.
2. Else, if `v - (u32)obj.code_base < obj.code_size` -> `(code_base & 0xFFFFFFFF00000000) | v` (a pointer into the
   script's own code; this is why "label address + offset" works without a map entry).
3. Else, with `B` = load bias of libGTASA: `p = (B & 0xFFFFFFFF00000000) | v`; if `p >= B` and the high half of `B`
   is not 0 -> `p`. **A plain number is silently placed into libGTASA's 4 GB window.**
4. Else `v` zero-extended; every user of the result then refuses an address whose high 32 bits are 0.

Map entries are created (key = low 32 bits, an existing key is overwritten) by: 0DD0, 0DD1, 0DD7, 0DDA, and by 0DD8
when the data it read looks like a pointer (2.2). 0DD4 does **not** create one; 0DD3 and the `i` arguments of 0DDE do
**not** resolve [E].

Consequences
- There is no real 64-bit value in a script; there are 32-bit "handles" that CLEO widens. Truncation is real: a
  handle plus an offset is a new number that is not in the map, and rule 3 will send it into libGTASA's window unless
  it lies inside the script's own code (rule 2).
- With `add_ib = 0` a script cannot name an arbitrary absolute address; it can only name: a mapped handle exactly,
  its own code, or libGTASA's 4 GB window at or above the base.

### 2.2 0DD8 / 0DD9 exactly

`addr = add_ib ? B + (u64)(u32)address : resolve(address, obj)` (so with the flag the reach is `B .. B + 4 GB`, never
below the base).

0DD8 (var is set to 0 first):
- size 1..4: refused if the high half of `addr` is 0. Otherwise `memcpy(var, addr, size)`.
- size 4 only: if `addr` is not inside an executable mapping of libGTASA (ranges parsed once from
  `/proc/self/maps`, lines containing "libGTASA.so" and "r-xp", vector at `0x7d1a8`), CLEO **also reads the 8 bytes at
  `addr`**; if that qword is >= 0x100000001 it adds `map[low32] = qword`.
  **Side effect [E]: every size-4 read of data whose next 4 bytes are not zero inserts a map node (0x30 bytes,
  never freed) for each new value.** `build_v25.py` does this when it reads coordinates and timers
  (`a(0x0dd8,V(16),I(base),I(4),I(1))` ...): a slow leak, and junk keys that could shadow a later handle.
  It is harmless for reads of code (GAME_SIG) and for sizes 1 and 2. Order of magnitude: ten such reads per second
  with changing values are about 36 000 nodes (roughly 2 MB) per hour of play. With the Brain present the mod can
  read those game values itself and hand them over in the exchange block.
- size 4, flag 0, address inside a registered pointer table (0DD1): the matching 8-byte entry is returned instead
  (a shim for 32-bit style scripts) [D 0x2d1c4].
- size 8: refused if the high half of `addr` is 0; var = low 32 bits of the qword; if qword >= 0x100000001 ->
  `map[low32] = qword`. This is how a script can obtain a usable handle of a 64-bit pointer stored in memory.
- other sizes: nothing.

0DD9:
- ignored (no error) if `addr` is inside an executable mapping of libGTASA (so `vp` cannot patch game code);
- size 1..4: refused if the high half of `addr` is 0; else `WriteMemory(addr, &value, size, vp != 0)` (0x4236c:
  optional permission change, atomic store for 2 and 4, memcpy otherwise, then a cache flush);
- size 8: the value is widened with `resolve(value, obj)` and 8 bytes are written;
- other sizes: nothing.

Checked in the emulator: flag 1 reads and writes; a number below 4 GB with flag 0 is refused when it is below the low
half of the base, and otherwise is **read from / written to `(high half of base | number)`**, a different address.

### 2.3 0DDE (call with typed arguments)

- `func = add_ib ? B + (u32)address : resolve(address, obj)`; no call if the high half is 0 (result 0).
- Then, while the next byte of the script is not 0: 8 raw bytes of type text (a C string inside 8 bytes, **no type
  byte in front**; lower-cased), followed by one ordinary parameter:
  - `i` -> integer (CollectParameters), zero-extended to 64 bits;
  - `f` -> the same: **the float's raw 32 bits go into an integer register**, not into v0..v7;
  - `ref` -> `GetPointerToScriptVariable`: the **real 64-bit address of the script variable**;
  - `resi` / `resf` -> the variable that receives the result;
  - anything else -> log "func call has unknown param type" and `exit(1)`; more than 32 -> log and `exit(1)`.
- The list ends with one 0 byte. Only the first 8 collected values are passed (x0..x7; nothing on the stack).
- Result: the **low 32 bits of x0** are stored in the result variable, for `resf` too (s0 is never read).

So a script can call an arbitrary native function pointer with up to 8 integer-register arguments, give it pointers
to its own variables, and read a 32-bit integer result. It cannot pass or receive values in floating-point registers,
and it cannot pass a 64-bit pointer other than `ref` [E].

---------------------------------------------------------------------------------------------------------------------

## 3. Storage of 0DDC / 0DDD (the "shared" or "mutex" variables)

| Item | Value |
|---|---|
| Container | `std::vector<{u32 key; u32 value;}>`, 8 bytes per entry, heap buffer |
| Header | `I+0x7d1f8` begin (u64), `I+0x7d200` end (u64), `I+0x7d208` end of capacity (u64) |
| 0DDC | linear search for the key from begin; found -> the value is overwritten in place; not found -> appended (`key | value << 32`), the buffer is reallocated when full |
| 0DDD | variable = 0, then linear search; found -> the value |
| Cleared | `end = begin` (buffer kept) in CLEO's hooks of `CTheScripts::Init` and `CTheScripts::Load`, i.e. on every new game and every load |
| Other readers | none in native CLEO code: the only references are 0x2fd90 (0DDC), 0x30378 (0DDD), 0x2d3d0 and 0x2dc1c (clear), 0x32228 (static init) |
| Locking | none. Scripts touch it on the game thread only |
| Proof | [E] test_bridge.py part 1 (contents, in-place native write seen by 0DDD, reallocation), [D] 0x2fd78..0x2fdec, 0x30d2c..0x30da4, 0x30340..0x303c0 |

Rules for a native mod
- Only on the game thread (from the `CTheScripts::Process` hook or from the opcode handler).
- Re-read `begin` and `end` on every use; never keep a pointer to an entry across frames (a later 0DDC can move the
  buffer; a load empties it).
- Sanity before walking: `begin != 0`, `begin <= end <= cap`, `(end - begin) % 8 == 0`, count below a sane limit.
- **Change values only. Never append**: the buffer belongs to CLEO's allocator. A key the mod wants to write must be
  created by a script first (`0DDC key 0`).
- Cost: each 0DDC/0DDD is a linear search; the scripts already keep about a hundred keys there, which is nothing.

---------------------------------------------------------------------------------------------------------------------

## 4. CLEO's plugin interface (the basis of the primary bridge)

`I+0x27d9b8`: 28 pointers, filled by a static initialiser (0x39608..) when the library's constructors run [D]; in
the unpacked image they are filled [E]. Layout = Alexander Blade's `cleo_ifs_t` with the two thumb entries removed.

| Slot | Target | Function |
|---|---|---|
| 0 | 0x386b0 | GetInterfaceVersion() -> 2 |
| 1 | 0x386b8 | GetGameIdentifier() -> 2 |
| 2 | 0x386c0 | GetGameVersionInternal() -> 0x64 |
| 3 | 0x386c8 | GetPackageName() |
| 4 | 0x386cc | GetPackageVersionStr() |
| 5 | 0x386d0 | GetPackageVersionCode() |
| 6 | 0x386d4 | GetCleoStorageDir() -> C string (std::string at 0x27d958) = the scripts folder |
| 7 | 0x386f0 | GetCleoPluginLoadDir() -> C string (0x27d970) |
| 8 | 0x3870c | PrintToCleoLog(const char*) |
| 9 | 0x38800 | GetMainLibraryFileName() |
| 10 | 0x3881c | GetMainLibraryLoadAddress() -> `[0x27d318]` |
| 11 | 0x38828 | GetMainLibraryExecutableSections(section_t*, u32) |
| 12 | 0x389b8 | FindExecutablePattern(const char*, u32) |
| 13 | 0x38a14 | GetMainLibrarySymbol(const char*) -> GlossSymbol on libGTASA |
| 14 | 0x38a48 | MemWriteArr(addr, bytes, size, protect) -> WriteMemory |
| 15 | 0x38a4c | hook function -> GlossHook(addr, new, &orig) |
| 16 | 0x38a50 | replace call (0x3ab98 with mode 3) |
| **17** | **0x38a58** | **bool RegisterOpcode(u16 opcode, handler)** |
| 18 | 0x38bc4 | bool RegisterOpcodeFunction(const char *name, handler) (for opcode 1000) |
| **19** | **0x38e84** | **data_t *ReadParam(script)** = `CollectParameters(script, 1)`, returns `&ScriptParams[0]` |
| **20** | **0x38e9c** | **data_t *GetPointerToScriptVar(script)** = `GetPointerToScriptVariable(script, 0)` (real pointer) |
| 21 | 0x38ea4 | bool ReadString8byte(script, char *buf, u32 size) (8 raw bytes at ip) |
| 22 | 0x38fb4 | bool ReadStringLong(script, char *buf, u32 size) (type 0E string) |
| 23 | 0x390c4 | bool IsParamListEnd(ip) (`*ip == 0`) |
| 24 | 0x390e4 | void SkipParamListEnd(&ip) |
| 25..27 | 0x3911c, 0x39120, 0x39124 | GetRealCodePointer / GetIpUsingRealCodePointer (identity), GetRealLabelPointer(script, offset) |

Facts [E unless marked]
- `RegisterOpcode` (0x38a58): locks pthread mutex number 1 of the array at `0x27da98` (0x28 bytes each), refuses a
  NULL handler, **returns 0 if the opcode is already registered**, otherwise inserts into `std::map<u16, handler>`
  (begin `0x27d988`, root `0x27d990`, size `0x27d998`; node key u16 `+0x20`, handler `+0x28`) and returns 1.
  There is no "unregister"; the map is never cleared (no other reference) [D].
- Dispatcher `0x37904(script, &script->ip, opcode)`: looks the full 16-bit opcode up **without taking the mutex**
  and calls `handler(x0 = CRunningScript*, x1 = &script->ip, w2 = opcode, x3 = "")`, then returns 1.
  Because there is no lock on this side, register on the game thread.
- When the handler is entered `script->ip` points just behind the 2 opcode bytes. The handler must consume exactly
  its parameters (each `ReadParam` / `GetPointerToScriptVar` call consumes one).
- C prototype on arm64: `void handler(void *script, uint8_t **ip, uint16_t opcode, const char *name);`
- The game's `ProcessOneCommand` is not run for a plugin opcode, so `script+0x122` (the "not" flag) is stale; do not
  rely on `UpdateCompareFlag` from a handler unless you clear that byte first [D G+0x3f4488, G+0x416474].
- Real plugins: every file with the extension `so` in the scripts folder is copied into the app-private directory
  `getDir("cleoplugins")` and `dlopen`ed; then `plugin_init(I+0x27d9b8)` is called [D 0x383f8, 0x37cd4, 0x380d0,
  0x382b0]. The AML mod does not need this: it can take the same table straight from the image (like `cleoui.c`
  takes CLEO's two drawing pointers).
- Any opcode number can be registered except the ones CLEO handles earlier (0002, 004C..004E, 0050, 0051, 05DC,
  the special 00E1 form, and the handled part of 0DD0..0DF6). The plugin map is asked before the game, so even a game
  opcode could be overridden for CLEO scripts.

---------------------------------------------------------------------------------------------------------------------

## 5. The candidates (answers question 2)

| Candidate | Verdict | Why |
|---|---|---|
| (a) mod reads/writes the 0DDC/0DDD storage directly | **Works. Fallback + handshake.** | Layout proven and executed (section 3). Limits: values only, script creates the keys, one opcode per value, inputs are one frame old when read in the pre-scripts hook |
| (b) script calls a function exported by the mod via 0DD1 + 0DD2.. | **Does not work as stated.** | 0DD1 = GlossSymbol on libGTASA only [D]. 0DD3 cannot pass pointers; 0DD4 returns 32 bits [E] |
| (b') script gets the mod's function pointer from an 8-byte cell with `0DD8 size 8`, then `0DDE handle 0 'ref' var ...` | Works in the emulator [E]; not recommended | Needs a cell the script can address and the mod can fill: either the unused tail of libGTASA's .bss (see e) or a cell inside the script's own code that the mod finds in the arena. More moving parts than the plugin opcode, and a wrong handle is a wild call |
| (c) private opcode | **Works. Primary**, done through CLEO's `RegisterOpcode` (section 4) [E] | No game code is touched; CLEO calls the handler before the game sees the opcode |
| (c') private opcode by swapping GOT slot `G+0x84e1a0` (`ProcessCommands2600To2699`) | Works by the disassembly [D]; spare route that does not depend on CLEO's internals | Every opcode above 0x0A8B (after masking 0x7FFF) is sent to the pointer in this slot, both by `ProcessOneCommand` (G+0x3f4490, used by CLEO for unknown opcodes) and by the game's own loop (G+0x3f3ff0). Handler: `u8 f(CRunningScript*, int opcode)`, return 0 to continue. Unknown opcodes must be passed on to the saved pointer (its default returns 0xFF) |
| (c'') inline hook of `ProcessOneCommand` / `CollectParameters` | Not needed | `ProcessOneCommand` starts with `adrp` (`d00022c8 f946cd08 79400109 11000529`, not position-independent) and is reached only from CLEO; `CRunningScript::Process` is already hooked by CLEO |
| (d) block mapped below 4 GB for 0DD8/0DD9 | **Does not work** [E] | Flag 0: a number below 4 GB is either refused or redirected into libGTASA's window (a wild read/write). Flag 1: reach is `B .. B+4 GB` only |
| (d') block mapped inside `B .. B+4 GB`, scripts use flag 1 with `offset = block - B` | Would work by the code [D]; not tested | Depends on getting such a mapping on the device (hint address, not guaranteed) and still costs one 4/5-parameter opcode per value, plus the size-4 side effect of 2.2 |
| (e) data in libGTASA's own unused memory, scripts use 0DD8/0DD9 with flag 1 | Works by the code [D]; weak fallback | `.bss` ends at `G+0xd3de90` (`_end`; last object `DisabledEffects` at 0xd3de80, 15 bytes). The rest of that page, **`G+0xd3de90 .. G+0xd3dfff` (368 bytes)**, is zero-filled, writable, outside RELRO, and no instruction of the file addresses it (scan of all `adrp` pairs) [D]. That the fastman92 limit adjuster does not use it at run time is [I]. Use 8-byte slots with the upper half 0, or sizes 1/2, to avoid the map side effect |

---------------------------------------------------------------------------------------------------------------------

## 6. Recommended bridge

### 6.1 Primary: private opcode + block of script variables

Suggested number: **0x0E48** (free in this build: outside 0DD0..0DF6, not 0x1000, above 0x0A8B so route c' also
fits). The number and the layout below are a proposal, not a finding.

Bytecode: `48 0E | 03 nn 00 (first local variable) | 04 cc (count) | 04 mm (command)`; for `asm_v25.py`:
`LIB[0x0e48] = {'id':'0E48','name':'BRAIN_EXCHANGE','num_params':3}` and `a(0x0e48, V(first), I(count), I(cmd))`.

Mod, once (any thread; repeat until both libraries are found)
1. `dl_iterate_phdr`: `G` = base of `libGTASA.so`; `C` = base of `libSAcleo64.so`, `I = C + 0x88000`; require the
   image size >= `0x88000 + 0x27e000` (as `cleoui.c`).
2. Check the game build: words at `G+0x3f3ad8` = `d10203ff fd000be8`, `G+0x3f1fcc` = `12003c28 34000b88`,
   `G+0x3f2654` = `f940100a aa1f03e8`; `*(u64*)(G+0x845438) == G+0x3f3ad8`.
3. Swap GOT slot `G+0x845438` to `brain_scripts_process` (mprotect RW, one aligned 8-byte store, mprotect R).
   If the slot holds something else, another mod is already there: store your function anyway and chain to the value
   found, and log it.

Mod, in `brain_scripts_process` (game thread, before the scripts)
4. Until CLEO is accepted (retry about once a second), check all of:
   - text at `I+0x1bc30` == "CLEO ANDROID (64-260403)";
   - the 28 table entries at `I+0x27d9b8` equal `I +` the targets of section 4 (at least slots 17, 19, 20);
   - first words: `I+0x38a58` = `a9bc7bfd a9015ff8`, `I+0x37904` = `d10343ff a9087bfd`, `I+0x2fb2c` =
     `a9ba7bfd a9016ffc`, `I+0x2fd78` = `d0000268 f9401260`, `I+0x30340` = `b0000268 f9401260`,
     `I+0x2de20` = `d503201f 10279b28`;
   - CLEO resolved the same game: `*(u64*)(I+0x7d248) == G+0x3f1fcc`, `*(u64*)(I+0x7d240) == G+0x3f2654`,
     `*(u64*)(I+0x7d220) == G+0xa001ac`, `*(u64*)(I+0x7d2a8) == G+0x3f445c`, `*(u64*)(I+0x7d1a0) == G`.
   Any mismatch: leave CLEO alone, log it, the bridge stays off.
5. Once accepted: `ok = ((int(*)(u16, void*))ifs[17])(0x0E48, brain_opcode)`. `ok == 0` means the number is taken
   (or this is a second call): opcode channel off, the fallback remains.
6. Handshake through the shared storage (section 3): find the key `HELLO` (for example `0x48456AF0`); if present,
   write `0x42520000 | version << 4 | (opcode_ready ? 1 : 0)`. Also bump a heartbeat key if the scripts created one.
7. Think for this frame, then call the saved `CTheScripts::Process`.

Handler
```c
static void brain_opcode(void *script, unsigned char **ip, unsigned short opcode, const char *name) {
    int *vars = ifs_GetPointerToScriptVar(script);      /* slot 20: address of the first variable        */
    int count = *(int *)ifs_ReadParam(script);          /* slot 19: copy the value at once,              */
    int cmd   = *(int *)ifs_ReadParam(script);          /*          the buffer is reused by the next call */
    long first = ((char *)vars - ((char *)script + 0x6c)) / 4;
    if (vars && first >= 0 && count > 0 && first + count <= 32) exchange(script, vars, count, cmd);
}
```
- Always read all three parameters, even when the request is rejected, or the script's ip is left in the middle.
- `vars[0..count-1]` are the script's local variables `first .. first+count-1` (`script+0x6c + 4*index`,
  non-mission scripts) [D]. Floats are the raw 32 bits.
- A global variable as first parameter gives a pointer into `CTheScripts::ScriptSpace`; reject it or handle it apart.

Script
1. At start: `0DDC HELLO 0`, wait at least one frame, `0DDD v HELLO`; repeat for a couple of seconds if 0.
2. `v >> 16 != 0x4252` -> no mod: run the built-in logic. `v & 1` -> use 0E48. Else -> fallback 6.2.
3. Every tick: put the inputs into the block of locals, `0E48 first count cmd`, read the outputs from the same locals.
4. After a load the script restarts and the storage is empty, so the handshake repeats by itself.

Why the handshake cannot be skipped: for an unregistered number CLEO rewinds the ip and calls the game's
`ProcessOneCommand`, which sends 0x0E48 to `ProcessCommands2600To2699`; its default returns 0xFF without reading the
parameters, and the next turn starts executing the parameter bytes as opcodes [E for the CLEO part, D G+0x40becc].

### 6.2 Fallback: shared storage only

1. The scripts create every key the mod may write (`0DDC key 0`) once after start, in the same place where they do the
   handshake, and write their own outputs with 0DDC as today.
2. In `brain_scripts_process`, before the scripts: walk the vector once; copy the values of the "script -> mod" keys
   out (they are from the previous frame), compute, write the "mod -> script" keys in place.
3. Scripts read the decisions with 0DDD in the same frame.
4. Checks before relying on it: the CLEO checks of step 4 above (version text and the words of 0x2fd78 / 0x30340 are
   the ones that matter here), the vector sanity checks of section 3, and a generation counter key written by the
   script so the mod notices a restart.

### 6.3 If the CLEO image is not the known build

Do not touch CLEO at all. The only bridge that then still stands on proven ground is route (c'): swap `G+0x84e1a0`
(expected `G+0x40bd74`), handle 0x0E48 in `u8 f(CRunningScript *s, int op)` with the game's own
`CollectParameters` (`G+0x3f1fcc`, `(script, short n)`, values in `ScriptParams` at `G+0xa001ac`, 32 ints) and
`GetPointerToScriptVariable` (`G+0x3f2654`, `(script, 0)`), return 0, and pass every other opcode to the saved
pointer. The handshake then needs a place that does not depend on CLEO's internals: a magic word in the unused .bss
tail (`G+0xd3de90`, written only if the 368 bytes are all zero) which the script reads with
`0DD8 v 0xD3DE90 4 1`, the same way it already reads its GAME_SIG words. This variant is [D] only.

---------------------------------------------------------------------------------------------------------------------

## 7. Drawing from the native mod (answers question 4)

### Hook point

- `Render2dStuff` (G+0x4d8994) sets the 2D render states (z test off, z write off, vertex alpha on, src blend 5,
  dest blend 6, fog off, cull 1), then calls `CHud::Draw` through PLT stub G+0x229c30 at **G+0x4d8a2c**, then the
  touch widgets, messages, and `CFont::RenderFontBuffer` (G+0x4d8a60) [D].
- **Swap GOT slot `G+0x845ec8`** (JUMP_SLOT of `_ZN4CHud4DrawEv`, expected `G+0x51f6f0`; read only by that PLT stub;
  single caller `Render2dStuff+0x98`). In your function call the saved pointer first, then draw. Calling the saved
  pointer enters `CHud::Draw` at its first instruction, i.e. through CLEO's inline hook, so CLEO's menu keeps working.
- `CHud::Draw` first 4 words in the file: `a9be4ff4 a9017bfd 910043fd f0001968` = stp, stp, add (position
  independent) and **`adrp x8` (PC-relative, not position-independent)**. On the device these words are already
  replaced by CLEO's GlossHook jump [I], so compare them only to learn "CLEO has hooked", never to hook inline.
- Alternative slot: `CHud::DrawAfterFade` `G+0x846618` (expected `G+0x51f9b0`, words `f81e0ff3 a9017bfd 910043fd
  52800120`, all position-independent). It is also called from `FrontendIdle` and `Render2dStuffAfterFade`, so it
  draws in menus too.
- `Idle` skips the scene and `Render2dStuff` (so the hook is not called at all) while `gMobileMenu` (G+0x8be780)
  has `+0x24 != 0` or `+0x30 != 0` (a menu screen is up) or the screen fade status is 2 [D G+0x4d8f00..0x4d8f2c,
  G+0x4d8fd4]. `CHud::Draw` itself returns early when a photo is taken, on the same two `gMobileMenu` tests, and when
  `gbCineyCamProcessedOnFrame == CTimer::m_FrameCounter`; near its end it returns if `CTimer::m_UserPause`
  (G+0xbdc594). Use the same tests before drawing.
- SAUtils also offers `AddOnRenderListener(ROfType_Hud = 2, void (*)(void*))` (vtable slot 40 by the current header)
  and `AddPlayerUpdateListener` (slot 17) [S]. Whether the SAUtils on the device has slot 40 is unknown; the GOT slot
  needs nothing from SAUtils.

### Text (the same preparation CLEO uses in 0x365dc, which is proven on the device by CLEO UI)

Functions (G+offset, arm64 calling convention)

| Function | Address | First words | Call |
|---|---|---|---|
| `CFont::PrintString(float x, float y, u16 *gxt)` | 0x6cdeb0 | d10143ff 6d0223e9 | s0 = x, s1 = y in pixels, x0 = text |
| `CFont::SetFontStyle(u8)` | 0x6ceff8 | f0000be8 d0000c09 | w0 = style (CLEO: 2 for lines, 3 for titles, 0 for its third style) |
| `CFont::SetScale(float)` | 0x6cefbc | d00004a8 bd456501 | stores y = s, x = s * constant |
| `CFont::SetColor(CRGBA)` | 0x6cee0c | d0000c08 39400009 | **x0 = pointer to 4 bytes r,g,b,a** |
| `CFont::SetDropColor(CRGBA)` | 0x6cf0f0 | | x0 = pointer to r,g,b,a |
| `CFont::SetOrientation(u8)` | 0x6cf1dc | 12001c08 7100091f | 0 centre, 1 left, 2 right |
| `CFont::SetJustify(u8)` | 0x6cf1cc | | |
| `CFont::SetProportional(u8)` | 0x6cf17c | | |
| `CFont::SetBackground(u8, u8)` | 0x6cf18c | | |
| `CFont::SetEdge(i8)` | 0x6cf148 | | outline |
| `CFont::SetDropShadowPosition(i8)` | 0x6cc8e8 | | shadow |
| `CFont::SetWrapx(float)` | 0x6cf0b0 | | |
| `CFont::SetCentreSize(float)` | 0x6cf0c0 | | |
| `CFont::SetRightJustifyWrap(float)` | 0x6cf0d0 | | |
| `CFont::GetStringWidth(u16*, bool, bool)` | 0x6ce760 | 6db923e9 a9016ffc | pixels, with the current Details |
| `CFont::RenderFontBuffer()` | 0x6ccea0 | fc170fec 6d012beb | flush queued text now |
| `AsciiToGxtChar(const char*, u16*)` | 0x6cbef0 | b4000120 39400009 | widen ASCII |

`CFont::Details` = G+0xccc324, 0x40 bytes [D from the setters]: `+0x00` colour RGBA, `+0x04` scale x, `+0x08` scale
y, `+0x0c` slant, `+0x10` slant ref x,y, `+0x18` justify, `+0x19` centre, `+0x1a` right, `+0x1b` background, `+0x1c`
background only text, `+0x1d` proportional, `+0x20` alpha fade (float), `+0x24` background colour, `+0x28` wrap x,
`+0x2c` centre size, `+0x30` right-justify wrap, `+0x36` shadow position, `+0x37..0x3a` drop colour, `+0x3b`,
`+0x3c` edge.

Recipe per text
1. Save the 0x40 bytes of `CFont::Details`.
2. `Details[0x18] = Details[0x19] = Details[0x1a] = 0`, then set one of them (left = 0x18 as CLEO does, centre =
   0x19, right = 0x1a).
3. `SetFontStyle(style)`.
4. Write colour (`+0`), scale x (`+4`), scale y (`+8`); `+0x1b = 0`, `+0x1d = 1`, `+0x1f = 0`, `+0x36 = 1`,
   `+0x37..0x3a = 00 00 00 FF` (black, opaque), `+0x3b = +0x3c = 0`. (CLEO multiplies its scale by 1.4 / 1.3 for
   style 2 and by 1.9 / 1.5 for style 3.) For long left-aligned text also set wrap x (`+0x28`) to the screen width;
   CLEO leaves it as the HUD left it.
5. `PrintString(x_px, y_px, gxt)`. Screen size: `RsGlobal` = G+0xc9b320, `+8` width (int), `+0xc` height (int).
6. Restore the 0x40 bytes.

The text is queued and appears at the next `CFont::RenderFontBuffer` (called by `Render2dStuff` after `CHud::Draw`),
so text is on top of rectangles drawn in the same hook. Call `RenderFontBuffer()` yourself when a rectangle must cover
earlier text. Russian needs the game's font codes (see `cleoui.c`).

### Rectangles and markers

- `CSprite2d::Draw2DPolygon(float x1,y1,x2,y2,x3,y3,x4,y4, const CRGBA&)` = G+0x6ee4a4 (words `f81e0ff3 a9017bfd
  910043fd f0000ac8`): s0..s7 = pixel coordinates, **x0 = pointer to r,g,b,a**. Point order: top-left, top-right,
  bottom-left, bottom-right (it draws a 4-vertex triangle strip in the order 3,4,1,2). It sets its own states:
  texture raster = 0, state 7 = 1, vertex alpha on if alpha != 255, then `RwIm2DRenderPrimitive(4, maVertices, 4)`.
  No other RenderWare setup is needed inside the `CHud::Draw` hook. This is the function CLEO's menu uses (and CLEO
  UI through it). [D]
- `CSprite2d::DrawRect(const CRect&, const CRGBA&)` = G+0x6ee91c (words `a9be4ff4 a9017bfd 910043fd aa0103f3`):
  x0 = pointer to 4 floats (x1, y1, x2, y2), x1 = pointer to r,g,b,a; also sets texture raster = 0 itself. [D]
- If needed: `RwRenderStateSet(int state, void *value)` = G+0x27d668.

### World position to screen

`bool CSprite::CalcScreenCoors(const RwV3d *in, RwV3d *out, float *w, float *h, bool farClip, bool nearClip)` =
G+0x6e9df8 (words `6dbb23e9 f9000bf7 a90257f6 a9034ff4`, position-independent).
- x0 = in, x1 = out, x2 = w (may be NULL), x3 = h (may be NULL), w4 = farClip, w5 = nearClip; returns w0.
- `out` = camera matrix (`TheCamera + 0xa10`, TheCamera = G+0xbba8d0) * in; returns 0 if `nearClip` and
  `z <= CDraw::ms_fNearClipZ + 1`, or if `farClip` and `z >= CDraw::ms_fFarClipZ`; otherwise `out.x`, `out.y` are
  **pixels** (`x * width / z`, `y * height / z`), `out.z` the depth, `*w`, `*h` the size of one world unit on screen.
- Always pass `nearClip = 1` (otherwise a point behind the camera gives nonsense). Call it from the draw hook.
- Entities from script handles: `CPools::GetPed(int handle)` = G+0x4f2378, `CPools::GetVehicle(int)` = G+0x4f23f4
  (return the object or 0; element sizes 0x9c8 and 0xc68). Position of a placeable: if the pointer at `+0x18` is not
  0 it is a matrix and the position is at `matrix+0x30`, else the position is at `object+0x8` (seen for TheCamera at
  G+0x4d6374; the same layout for peds/vehicles is [I] from inheritance).

### Not recommended

- Queuing through `CTheScripts::IntroTextLines` (G+0x9fb0bc, 96 entries of 0x44 bytes, re-initialised by
  `CTheScripts::Process` whenever `UseTextCommands` is set [D]): the drawing side was not analysed; the scripts can
  use the text opcodes themselves if that look is wanted.
- CLEO's two drawing pointers (`I+0x27d3b8`, `I+0x27d3c0`): CLEO UI already replaces them.

---------------------------------------------------------------------------------------------------------------------

## 8. Files and settings (answers question 5)

- The player's layout (works today for Touch x4 and CLEO UI): game folder
  `/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/` with `mods/` (logs:
  `mods/touch4_log.txt`, `mods/cleoui_log.txt`) and `configs/` (`configs/net.helicover.cleoui.ini`). Both mods try
  that fixed path first, then the folder of the loaded `.so` (`dladdr`), then
  `/storage/emulated/0/Android/data/com.rockstargames.gtasa/files/`.
- Asking AML at run time [S, upstream AML source `main.cpp` / `src/aml.cpp`; the version inside the player's APK was
  not examined]: `void *aml = GetInterface("AMLInterface")` (the same exported `GetInterface` of `libAML.so` the mods
  already use for "SAUtils"). `IAML` vtable slots: **1 `GetConfigPath()`** -> `<root>/configs/`,
  **15 `GetAndroidDataPath()`** -> `<root>/files/`, 14 `GetDataPath()` -> the app-private files dir
  (`/data/data/<pkg>/files`), 45 `GetAndroidDataRootPath()` -> `<root>/` (newer AML only). In a fastman92 build
  `<root>` is the FLA external directory (the `Android_unprotected/data/<pkg>` folder above); otherwise
  `<storage>/Android/data/<pkg>`. All returned strings end with `/`. Slots 1, 14, 15 exist since AML 1.0.0.5.
  Suggested: `GetConfigPath()`, cut the trailing `configs/`, append `mods/` -> the folder the player already opens;
  keep the fixed path and the `dladdr` folder as fallbacks.
- CLEO's own folder is also available without AML: interface slot 6 `GetCleoStorageDir()` (section 4) returns
  `<EXTERNAL_STORAGE>/cleo/sa/`, the folder where the player puts the `.csa` files; slot 8 `PrintToCleoLog(text)`
  appends a line to `<EXTERNAL_STORAGE>/cleo/cleo.log` [D]. Do not put a `.so` there: CLEO would load it as a plugin.
- Settings item: `ISAUtils` vtable slot 3 `AddClickableItem(self, type = 5 (SetType_Mods), name, init, min, max,
  const char **switches, void (*onChange)(int old, int new, void *data))`, exactly as in `touch4.c` / `cleoui.c`
  [works on the device]. Slot 4 is `AddSliderItem`, slot 5 `AddButton` [S].

---------------------------------------------------------------------------------------------------------------------

## 9. Uncertainties

1. Nothing here ran on the phone. [E] means the unpacked image's own code ran in unicorn with a faked game side.
2. The unpacked image is assumed to equal the library in memory on the device. CLEO UI already relies on this for
   0x3659c / 0x365dc / 0x27d3b8 and works; the mod must still verify the words listed in 6.1 at run time.
3. libGTASA may be patched at run time by the fastman92 limit adjuster or by other AML mods; hence the word and GOT
   value checks. What to do when a GOT slot already holds a foreign pointer (chain) is a design choice, not a finding.
4. "The 368 bytes after `_end` are unused at run time" is inferred from the file only.
5. `CTimer::m_FrameCounter` as a per-frame counter: from its name.
6. The exact bytes of CLEO's inline hooks on the device were not seen; only the hook calls.
7. AML path getters and SAUtils slots 4, 5, 17, 40: from current upstream headers/source, not from the binaries in
   the APK. Slot 3 of SAUtils and the fixed paths are proven by the existing mods.
8. Game thread: it is assumed that script processing and HUD drawing run on the same thread (both are called from
   `Idle`), so the two hooks and the opcode handler need no locking between them.
9. Whether another CLEO plugin on the device already owns 0x0E48: unknown; `RegisterOpcode` returning 0 reveals it.
10. 0DE0..0DE3, 0DEE..0DF6 were only skimmed (parameter counts and the called helper are from the code; the meaning
    partly from the Sanny library).
11. The position layout of peds/vehicles (`+0x18` matrix, `+0x30` position) is inferred from `TheCamera`.

---------------------------------------------------------------------------------------------------------------------

## 10. How this was established (files in this directory)

| File | Purpose |
|---|---|
| `common.py`, `d.py`, `dp.py`, `xref.py` | disassembly of `cleolib/inner.bin`, PLT names, cross references (`xref.pkl`) |
| `unpack_names.py`, `stubnames.json`, `plt.json` | names of CLEO's imports (re-run of the unpacker; needs `python3 -P`) |
| `disp.txt` | listing of the dispatcher 0x2fb2c..; `plug.txt` plugin loader |
| `g.py`, `gcallers.py`, `ggot.pkl`, `gplt.pkl`, `gsyms.pkl` | disassembly of libGTASA with GOT/PLT names, callers of a function |
| `emu.py` | unicorn harness around `cleolib/libSAcleo64.so.image` |
| `test_bridge.py` | 0DDC/0DDD storage, plugin interface, 0DD0/0DD2..0DD5/0DD7/0DD8/0DD9/0DDE: `python3 -P test_bridge.py` -> ALL PASS |
| `test_loop.py` | CLEO's script loop with a private opcode, start delay, fall-through to the game: `python3 -P test_loop.py` -> ALL PASS |
| `dl/` | downloaded `iaml.h`, `amlmod.h`, `isautils.h`, AML `main.cpp` / `src/aml.cpp`, Sanny `sa_mobile.json` |
