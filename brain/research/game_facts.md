# GTA San Andreas Android arm64 - game facts for the Helicover Brain mod

Source binary: `libGTASA.so`, 54731968 bytes, sha256 `92b3714534742cf8e31eba35dbfd5e83871ecb5b936f5519d9b6ef3562234f9e`, 
aarch64, built with "Android clang 5.0.300080", NDK r15c. The file keeps `.symtab` and full DWARF (`.debug_info`), and has
`.fastman92.*` sections (it was post-processed by the fastman92 tool; program headers were moved, 3 MB RWX trampoline area at 0xd48000).

All addresses are offsets from the load base of libGTASA.so. All structure offsets are for THIS build (64-bit pointers; they do not match the PC layout).

## How to read the confidence column

- **proven**: an instruction of a named game function was disassembled and uses exactly this offset/size; the instruction word is in `BRAIN_ANCHORS` of `brain_offsets_draft.h` so the mod can re-check it at load. Every offset was also compared with the DWARF class layout of the same file by `dwarf_check.py`: 130 header offsets/sizes agree, 0 disagree.
- **dwarf**: taken from the DWARF class layout / enumerators inside this same libGTASA.so (read with `gdb ptype /o`). No instruction was collected for it. Reliable for layout, but the mod can not re-check it by an instruction word.
- **inferred**: reasoning or knowledge of the PC game, not checked in this binary.

Re-check everything: `python3 -I gen_header.py libGTASA.so` regenerates the header and fails if any of the 146 anchor instructions does not disassemble as stated; `python3 -P -E verify_header.py libGTASA.so` compares the header words with the file without a disassembler and runs 30 emulated calls (unicorn) of the game's own accessors on fake data laid out with the header offsets (all pass).

## A. Pools

| what | address / offset | type | evidence | conf. |
|---|---|---|---|---|
| `CPools::ms_pPedPool` | 0xbc3bb8 | pointer variable (.bss) to a CPool | symbol; `CPools::GetPed` @0x4f2388 `ldr x8, [x8]` | proven |
| `CPools::ms_pVehiclePool` | 0xbc3bc0 | pointer variable to a CPool | symbol; read in `CPools::GetVehicle` @0x4f2404 | proven |
| `CPools::ms_pObjectPool` | 0xbc3bd0 | pointer variable to a CPool | symbol; read in `CPools::GetObject` @0x4f2478 | proven |
| CPool.m_aStorage (objects) | +0x0 | uint8* (element array) | `CPools::GetPed` @0x4f239c `ldr x8, [x8]` | proven |
| CPool.m_aFlags (byte map) | +0x8 | uint8* (one byte per slot) | `CPools::GetPed` @0x4f238c `ldr x10, [x8, #8]` | proven |
| CPool.m_nSize | +0x10 | int32 slot count | `CPools::SavePedPool` @0x57acc0 `ldr w24, [x8, #0x10]` | proven |
| CPool.m_nFreeIndex | +0x14 | int32 (last allocated index) | `CPed::operator new` @0x59577c `ldp w9, w10, [x8, #0x10]` | proven |
| CPool.m_bOwnsArrays, m_bDealWithNoMemory | +0x18, +0x19 | bool; sizeof(CPool)=0x20 | DWARF `CPool<CPed,CCopPed>` | dwarf |
| ped pool element size | 0x9c8 (2504) | = sizeof(CCopPed); CPed is 0x988, CPlayerPed 0x998 | `CPools::GetPed` @0x4f23a0 `mov w10, #0x9c8` | proven |
| vehicle pool element size | 0xc68 (3176) | = sizeof(CPlane), the largest class; CVehicle base part is 0x758, CAutomobile 0xbc8, CBike 0xa18, CBoat 0x9e0, CHeli 0xc60, CTrain 0x8b8 | `CPools::GetVehicle` @0x4f241c `mov w10, #0xc68` | proven |
| object pool element size | 0x220 (544) | = sizeof(CCutsceneObject); CObject/CProjectile are 0x1f8 | `CPools::GetObject` @0x4f2490 `mov w10, #0x220` | proven |
| flags byte | bit 7 = slot free; bits 0-6 = reuse counter |  | `CPools::SavePedPool` @0x57ace4 `ldrsb w13, [x9]`; `CPools::SavePedPool` @0x57ace8 `tbnz w13, #0x1f, #0x57ad2c`; `CPed::operator new` @0x5957b0 `and w9, w14, #0x7f`; `CPed::operator delete` @0x595750 `orr w12, w12, #0x80` | proven |
| script handle | `(index << 8) \| flags[index]` | int | `CPools::GetPedRef` @0x4f2370 `bfi w0, w9, #8, #0x18`; `CPools::GetPed` @0x4f2384 `lsr w9, w0, #8`; `CPools::GetPed` @0x4f2394 `cmp w10, w0, uxtb` | proven |
| default slot counts | peds 140, vehicles 110, objects 350 | sizes of the flag arrays allocated in `CPools::Initialise` (0x8c, 0x6e, 0x15e) | `CPools::Initialise` @0x4f1564, @0x4f15fc, @0x4f1730 | proven for the file; always read m_nSize at run time (a limit adjuster can change it) |

Functions (all tiny, start with `adrp`/`tbnz`: call them, do not inline-hook them):

| function | address | behaviour |
|---|---|---|
| `CPed* CPools::GetPed(int handle)` | 0x4f2378 | NULL when handle < 0 or `flags[handle>>8] != (handle & 0xff)`; else `objects + (handle>>8)*0x9c8` |
| `int CPools::GetPedRef(CPed*)` | 0x4f2340 | index = (ped - objects)/0x9c8; returns `(index<<8) \| flags[index]`; no validity check |
| `CVehicle* CPools::GetVehicle(int)` | 0x4f23f4 | same with 0xc68 |
| `int CPools::GetVehicleRef(CVehicle*)` | 0x4f23bc | same with 0xc68 |
| `CObject* CPools::GetObject(int)` / `GetObjectRef(CObject*)` | 0x4f2468 / 0x4f2438 | same with 0x220 |

Safe iteration of all live peds (exactly what `CPools::SavePedPool` @0x57ac84 does):

```c
void *pool = *(void **)(base + 0xbc3bb8);            /* may be NULL before the game is loaded */
uint8_t *objs = *(uint8_t **)pool, *flags = *(uint8_t **)((char *)pool + 8);
int n = *(int32_t *)((char *)pool + 0x10);
for (int i = 0; i < n; i++)
    if ((int8_t)flags[i] >= 0) { CPed *ped = (CPed *)(objs + (size_t)i * 0x9c8); int handle = (i << 8) | flags[i]; ... }
```
Same for vehicles with 0xc68. Run it on the game thread only (the pools are not locked). A handle kept across frames must be re-validated with `GetPed` (the counter in bits 0-6 changes when the slot is reused).

## B. Player

| what | address / offset | type | evidence | conf. |
|---|---|---|---|---|
| `CWorld::Players` | 0xbdc738 | CPlayerInfo[2] (symbol size 944) | symbol; `FindPlayerPed` @0x4efb14 `mov w10, #0x1d8` | proven |
| sizeof(CPlayerInfo) | 0x1d8 (472) |  | `FindPlayerPed` @0x4efb14 `mov w10, #0x1d8` | proven |
| `CWorld::PlayerInFocus` | 0xbdcae8 | uint8 | symbol; read in `FindPlayerPed` @0x4efb18 | proven |
| `CHID::currentInstanceIndex` | 0x8be728 | int; when == 1 `FindPlayerPed` returns Players[1].pPed whatever the argument | `FindPlayerPed` @0x4efae8..0x4efb00 | proven |
| CPlayerInfo.pPed | +0x0 | CPlayerPed* | `FindPlayerPed` @0x4efb24 `ldr x0, [x8]` | proven |
| CPlayerInfo.PlayerPedData | +0x8 | CPlayerPedData (0xd8 bytes) embedded; `ped->m_pPlayerData` points here | DWARF; `FindPlayerWanted` @0x4f0478 `ldr x0, [x8, #8]` | proven |
| CPlayerInfo.pRemoteVehicle | +0xe0 | CVehicle* (RC vehicle) | `FindPlayerVehicle` @0x4efe40 `ldr x0, [x9, #0xe0]` | proven |
| CPlayerInfo.Score (money) | +0xf0 | int32 | DWARF | dwarf |
| CPlayerInfo.LastTimeEnergyLost / LastTimeArmourLost | +0x120 / +0x124 | uint32 ms | DWARF; `ComputeDamageResponse` @0x443e68 `str w8, [x9, #0x120]` | dwarf |
| wanted level (stars 0..6) | `FindPlayerWanted(i)` + 0x2c | int32 (DWARF name `m_WantedLevel`) | `CRunningScript::ProcessCommands200To299` @0x3f69c0 `ldr w8, [x0, #0x2c]`; `CRunningScript::ProcessCommands400To499` @0x40eb18 `ldr w9, [x9, #0x2c]` | proven |
| CWanted +0x0 |  | int32, DWARF name `m_nWantedLevel`; NOT what the script star commands read (chaos points on PC) | DWARF | dwarf (offset), inferred (meaning) |
| CWanted.m_nCopsInPursuit | +0x18 | uint8 | DWARF | dwarf |

| function | address | behaviour (read from the code) |
|---|---|---|
| `CPlayerPed* FindPlayerPed(int player)` | 0x4efae0 | player < 0 uses PlayerInFocus; returns Players[n].pPed |
| `CVehicle* FindPlayerVehicle(int player, bool bIncludeRemote)` | 0x4efdec | NULL when the ped is NULL or its bInVehicle flag is clear; else pRemoteVehicle (if asked and set) or ped->m_pMyVehicle |
| `CVector FindPlayerCoors(int player)` | 0x4efea8 | returns x,y,z in s0,s1,s2 (declare the C prototype as returning a struct of 3 floats); uses the vehicle when in one; (0,0,0) when no ped |
| `CWanted* FindPlayerWanted(int player)` | 0x4f0454 | Players[n].PlayerPedData.m_Wanted |
| `FindPlayerSpeed(int)` / `FindPlayerHeading(int)` | 0x4f0378 / 0x4f06c0 | pointer to m_vecMoveSpeed of ped or its vehicle / heading in radians |

## C. CPlaceable / CEntity / CPhysical / CPed

Sizes (DWARF): CPlaceable 0x20, CEntity 0x60, CPhysical 0x198, CPed 0x988, CPlayerPed 0x998, CWeapon 0x20, CPlayerPedData 0xd8, CPedIntelligence 0x440.

| field | offset | type | evidence | conf. |
|---|---|---|---|---|
| vtable | +0x0 | pointer | ctor writes, e.g. `CPed::~CPed` @0x595440 | proven |
| CPlaceable.m_transform.m_translate | +0x8 | CVector (3 float) - valid only when m_pMat == NULL | `FindPlayerCoors` @0x4efeec `add x8, x8, #8` | proven |
| CPlaceable.m_transform.m_heading | +0x14 | float rad - valid only when m_pMat == NULL | `FindPlayerHeading` @0x4f072c `ldr s0, [x9, #0x14]` | proven |
| CPlaceable.m_pMat | +0x18 | CMatrix* (may be NULL) | `FindPlayerCoors` @0x4efee8 `ldr x9, [x8, #0x18]` | proven |
| CMatrix right / forward / up / pos | +0x00 / +0x10 / +0x20 / +0x30 | 3 floats each (+pad), sizeof 0x50 | `FindPlayerCoors` @0x4efef0 `add x10, x9, #0x30`; `FindPlayerHeading` @0x4f0720 `ldp s0, s1, [x8, #0x10]`; rest DWARF | proven |
| position rule |  | `m_pMat ? (CVector*)(m_pMat+0x30) : (CVector*)(ent+8)` | `FindPlayerCoors` @0x4efee8..0x4efefc | proven |
| heading rule |  | `m_pMat ? atan2f(-fwd.x, fwd.y) : *(float*)(ent+0x14)` | `FindPlayerHeading` @0x4f0718..0x4f072c; GET_CHAR_HEADING @0x40e5e4 | proven |
| CEntity.m_pRwObject | +0x20 | RwObject* | DWARF | dwarf |
| CEntity.m_nFlags | +0x28 | uint32 bit field (bit0 bUsesCollision, bit7 bIsVisible, ...) | DWARF | dwarf |
| CEntity.m_nModelIndex | +0x32 | int16 | `CRunningScript::ProcessCommands1600To1699` @0x4269a0 `ldrsh w8, [x8, #0x32]`; `CRunningScript::ProcessCommands1000To1099` @0x41b284 `ldrsh w8, [x8, #0x32]` | proven |
| CEntity type/status byte | +0x5a | uint8: type = bits 0-2, status = bits 3-7 | `CRunningScript::ProcessCommands1100To1199` @0x41c800 `ldrb w9, [x8, #0x5a]`; `CRunningScript::ProcessCommands1100To1199` @0x41c804 `and w9, w9, #7`; `CRunningScript::ProcessCommands1100To1199` @0x41c808 `cmp w9, #3`; `CRunningScript::ProcessCommands200To299` @0x3f6ba4 `and w10, w10, #0xf8`; `CRunningScript::ProcessCommands200To299` @0x3f6ba8 `cmp w10, #0x28` | proven |
| entity type values |  | 0 nothing, 1 building, 2 vehicle, 3 ped, 4 object, 5 dummy, 6 not in pools | 3 and 2: `CRunningScript::ProcessCommands1100To1199` @0x41c808 `cmp w9, #3`; `CVehicle::CVehicle` @0x6a5200 `orr w9, w9, #2`; all names: DWARF enumerators `ENTITY_TYPE_*` | proven |
| entity status values |  | 0 player, 1 playback, 2 simple, 3 physics, 4 abandoned, 5 wrecked, 6/7 train moving/not, 8 player remote, 9 player disabled, 10 trailer, 11 simple trailer, 12 ghost | 5: `CRunningScript::ProcessCommands200To299` @0x3f6ba8 `cmp w10, #0x28`; names: DWARF `STATUS_*` | proven (5), dwarf (rest) |
| CPhysical.m_nPhysicalFlags | +0x64 | uint32 | DWARF | dwarf |
| CPhysical.m_vecMoveSpeed | +0x68 | CVector, units per 1/50 s frame (x50 = m/s) | `FindPlayerSpeed` @0x4f03b4 `add x0, x8, #0x68` | proven (offset), inferred (unit) |
| CPhysical.m_vecTurnSpeed | +0x74 | CVector | DWARF | dwarf |
| CPhysical.m_fMass | +0xb0 | float | DWARF | dwarf |
| CPhysical.m_fDamageImpulseMagnitude / m_pDamageEntity | +0x124 / +0x128 | float / CEntity* - last COLLISION damage (not weapons) | DWARF | dwarf |
| CPed.m_pPedIntelligence | +0x538 | CPedIntelligence* | `CPed::SetCharCreatedBy` @0x5958d0 `ldr x0, [x19, #0x538]`; `CPedIntelligence::AreFriends` @0x5bdfe0 `ldr x24, [x19, #0x538]` | proven |
| CPed.m_pPlayerData | +0x540 | CPlayerPedData* (NULL for non-players) | `CRunningScript::ProcessCommands400To499` @0x40eb10 `ldr x9, [x9, #0x540]`; `CPedGroups::IsInPlayersGroup` @0x5b2b48 `ldr x8, [x0, #0x540]` | proven |
| CPed.CharCreatedBy | +0x548 | uint8: 1 RANDOM_CHAR, 2 MISSION_CHAR, 3 REPLAY_CHAR | `CPed::SetCharCreatedBy` @0x5958c4 `strb w1, [x19, #0x548]`; ctor default 1 @0x594e20; names DWARF | proven |
| CPed.m_nPedState | +0x54c | int32 ePedState (list in section I) | `CPed::IsAlive` @0x59afc8 `ldr w8, [x0, #0x54c]`; `CPed::IsAlive` @0x59afd0 `cmp w8, #0x36`; `CRunningScript::ProcessCommands200To299` @0x3f6b28 `ldr w8, [x8, #0x54c]` | proven |
| dead test |  | `state == 54 (DIE) or 55 (DEAD)` (`CPed::IsAlive`); script IS_CHAR_DEAD also counts 56 (DIE_BY_STEALTH) | `CPed::IsAlive` @0x59afd0 `cmp w8, #0x36`; IS_CHAR_DEAD @0x3f6b2c..0x3f6b40 | proven |
| CPed.m_eMoveState | +0x550 | int32: 0 none, 1 still, 2/3 turn, 4 walk, 5 jog, 6 run, 7 sprint | DWARF | dwarf |
| CPed.m_nPedFlags | +0x584 | 4 x uint32 bit fields (+0x584..+0x593) | `CRunningScript::ProcessCommands200To299` @0x3f65dc `ldrb w10, [x10, #0x585]` | proven |
| - bInVehicle | +0x585 bit 0 (word0 bit 8) |  | `CRunningScript::ProcessCommands200To299` @0x3f65dc `ldrb w10, [x10, #0x585]`; `CRunningScript::ProcessCommands200To299` @0x3f65e0 `tbz w10, #0, #0x3f6c0c` | proven |
| - bFiringWeapon | +0x586 bit 0 (word0 bit 16) | set while the fire animation shoots | `CRunningScript::ProcessCommands700To799` @0x4113a0 `ldrb w8, [x8, #0x586]`; `CRunningScript::ProcessCommands700To799` @0x4113a4 `and w1, w8, #1` | proven |
| - bIsDucking | +0x587 bit 2 (word0 bit 26) |  | `CRunningScript::ProcessCommands1400To1499` @0x41f974 `ldr w8, [x8, #0x584]`; `CRunningScript::ProcessCommands1400To1499` @0x41f978 `ubfx w1, w8, #0x1a, #1` | proven |
| - bIsStanding, bIsAimingGun, bIsInTheAir, bIsLanding | word0 bits 0, 4, 9, 10 |  | DWARF `CPedFlags` | dwarf |
| - bHasACamera, bPedIsBleeding, bIsPedDieAnimPlaying, bBeingChasedByPolice | word0 bits 17, 18, 20, 23 |  | DWARF | dwarf |
| - bDontFight, bNeverEverTargetThisPed, bThisPedIsATargetPriority | +0x58b bits 0, 4, 5 (word1 bits 24, 28, 29) |  | DWARF | dwarf |
| CPed.m_acquaintances | +0x63c | uint32[5] (see section H) - inside CPed on this build | `CPedIntelligence::IsFriendlyWith` @0x5bde98 `add x0, x8, #0x63c` | proven |
| CPed.m_nHealth | +0x6ac | float | `CRunningScript::ProcessCommands500To599` @0x40fb74 `ldr s0, [x8, #0x6ac]` | proven |
| CPed.m_nMaxHealth | +0x6b0 | float | DWARF; a script handler writes +0x6ac and +0x6b0 together @0x40df5c / @0x40df60 | dwarf |
| CPed.m_nArmour | +0x6b4 | float | `CRunningScript::ProcessCommands1200To1299` @0x41d648 `ldr s0, [x8, #0x6b4]`; `CPedDamageResponseCalculator::ComputeDamageResponse` @0x443bd8 `ldr s0, [x19, #0x6b4]` | proven |
| CPed.m_fCurrentHeading / m_fDesiredHeading | +0x6c4 / +0x6c8 | float rad | DWARF | dwarf |
| CPed.m_pMyVehicle | +0x708 | CVehicle* - use only when bInVehicle is set | `CRunningScript::ProcessCommands200To299` @0x3f65ec `ldr x8, [x8, #0x708]`; `CRunningScript::ProcessCommands900To999` @0x4159f0 `ldr x9, [x9, #0x708]` | proven |
| CPed.m_nPedType | +0x720 | int32 ePedType (0/1 = players) | `CRunningScript::ProcessCommands2200To2299` @0x404fa4 `ldr w8, [x8, #0x720]`; `CPed::IsPlayer` @0x595400 `ldr w8, [x0, #0x720]` | proven |
| CPed.m_pPedStats | +0x728 | CPedStats* | DWARF; `CPed::SetCharCreatedBy` @0x5958f4 | dwarf |
| CPed.m_WeaponSlots | +0x730 | CWeapon[13], 0x20 each | `CRunningScript::ProcessCommands1100To1199` @0x41c2a8 `ldr w8, [x8, #0x730]`; `CRunningScript::ProcessCommands1100To1199` @0x41c2a4 `add x8, x8, x10, lsl #5` | proven |
| CPed.m_nCurrentWeapon | +0x8dc | int8 slot index 0..12 | `CRunningScript::ProcessCommands1100To1199` @0x41c2a0 `ldrsb x10, [x8, #0x8dc]` | proven |
| current weapon type |  | `*(int32*)(ped + 0x730 + slot*0x20)` | GET_CURRENT_CHAR_WEAPON @0x41c2a0..0x41c2a8 | proven |
| CWeapon.m_eWeaponType | +0x0 | int32 eWeaponType | `CRunningScript::ProcessCommands1100To1199` @0x41c2a8 `ldr w8, [x8, #0x730]` | proven |
| CWeapon.m_eState | +0x4 | int32: 0 ready, 1 firing, 2 reloading, 3 out of ammo, 4 melee made contact | `CWeapon::Fire` @0x700dc4 `ldr w8, [x19, #4]`; `CWeapon::Fire` @0x701348 `str w9, [x19, #4]`; names DWARF | proven |
| CWeapon.m_nAmmoInClip | +0x8 | int32 | `CWeapon::Fire` @0x700dd0 `ldr w8, [x19, #8]` | proven |
| CWeapon.m_nAmmoTotal | +0xc | int32 | `CRunningScript::ProcessCommands1000To1099` @0x41b458 `ldr w11, [x9, #0x73c]` | proven |
| CWeapon.m_nTimer | +0x10 | uint32 ms (next shot time) | DWARF | dwarf |
| CPed.m_nShootRate / m_nShootingAccuracy | +0x8dd / +0x8de | uint8 | DWARF | dwarf |
| CPed.m_pEntLockOnTarget (PC name m_pTargetedObject) | +0x8e0 | CEntity* - set through `CPed::SetWeaponLockOnTarget`, whose 20 callers are player/pad/script code + CCopPed ctor: in practice the PLAYER's lock-on target | `CRunningScript::ProcessCommands1100To1199` @0x41c7f8 `ldr x8, [x8, #0x8e0]`; `CPed::SetWeaponLockOnTarget` @0x59f400 `ldr x8, [x21, #0x8e0]` | proven |
| CPed.m_pEntMagnetizeTarget | +0x8e8 | CEntity* (free-aim assist) | DWARF; `SetWeaponLockOnTarget` @0x59f46c | dwarf |
| CPed.m_nWeaponSkill | +0x8fc | uint8 | DWARF | dwarf |
| CPed.m_pFire | +0x900 | CFire* (non-NULL = burning) | DWARF | dwarf |
| CPed.m_pEntLookEntity | +0x910 | CEntity* | DWARF | dwarf |
| CPed.m_nTimeOfDeath | +0x92c | uint32 ms | DWARF | dwarf |
| CPed.LastDamagedWeaponType | +0x93c | int8 eWeaponType (49 rammed, 50 run over, 51 explosion, 53 drowning, 54 fall) | `CRunningScript::ProcessCommands700To799` @0x411ba8 `ldrsb w0, [x8, #0x93c]`; `CPedDamageResponseCalculator::ComputeDamageResponse` @0x443e70 `strb w8, [x19, #0x93c]` | proven |
| CPed.pLastDamageEntity | +0x940 | CEntity* (registered reference: the game NULLs it when the entity is deleted); a ped or the vehicle that hit | `CRunningScript::ProcessCommands1300To1399` @0x41f3d8 `ldr x8, [x8, #0x940]`; `CPedDamageResponseCalculator::ComputeDamageResponse` @0x443e80 `str x0, [x19, #0x940]` | proven |
| CPed.LastDamagedTime | +0x948 | uint32 = CTimer::m_snTimeInMilliseconds of the last damage with a non-NULL inflictor | `CPedDamageResponseCalculator::ComputeDamageResponse` @0x443e94 `str w8, [x19, #0x948]` | proven |
| CPlayerPed.m_pMouseLockOnRecruitPed | +0x988 | CPed* | DWARF; IS_PLAYER_TARGETTING_CHAR @0x41c8f4 | dwarf |
| CPlayerPedData.m_Wanted | +0x0 | CWanted* | STORE_WANTED_LEVEL @0x40eb14 | proven |
| CPlayerPedData.m_nChosenWeapon | +0x2c | int8 | `CPed::SetCurrentWeapon(int)` @0x59b824 | proven |
| CPlayerPedData flags | +0x48 | uint32: bit 2 m_bHaveTargetSelected, bit 3 m_bFreeAiming, bit 1 m_bAdrenaline | `CTaskSimplePlayerOnFoot::ProcessPlayerWeapon` @0x6533a4 `ldrb w9, [x9, #0x48]`; `CTaskSimplePlayerOnFoot::ProcessPlayerWeapon` @0x6533a8 `tbz w9, #2, #0x6533c4`; `CTaskSimplePlayerOnFoot::ProcessPlayerWeapon` @0x653adc `tbnz w8, #3, #0x653ae8`; bit names DWARF | proven (offset, bits 2/3 are tested), dwarf (names) |
| CPlayerPedData.m_PlayerGroup | +0x4c | int32 index into CPedGroups::ms_groups | `CRunningScript::ProcessCommands1900To1999` @0x3fcfb0 `ldr w0, [x8, #0x4c]` | proven |
| CPlayerPedData.m_LastTimeFiring | +0x88 | uint32 ms | DWARF | dwarf |

Notes:
- "Who is this NPC attacking" is NOT a CPed field. It lives in the ped's tasks (section H.3). `m_pEntLockOnTarget` is only meaningful for the player.
- "Who damaged whom" without hooks: poll `LastDamagedTime`/`pLastDamageEntity`/`LastDamagedWeaponType` per ped; they are written in one place, `CPedDamageResponseCalculator::ComputeDamageResponse` @0x443e6c..0x443e94 (weapon type always; entity and time only when the inflictor is not NULL).
- `CPed::IsPlayer` @0x595400 = `m_nPedType < 2`. `CPed::IsAlive` @0x59afc8.

## D. CVehicle

| field | offset | type | evidence | conf. |
|---|---|---|---|---|
| position / matrix / model / type-status / m_vecMoveSpeed | as CEntity/CPhysical above |  | same base classes | proven |
| CVehicle.pHandling | +0x4a8 | tHandlingData* | `CVehicle::GetVehicleAppearance` @0x6a65dc `ldr x8, [x0, #0x4a8]` | proven |
| CVehicle flags | +0x568 | 2 x uint32 bit fields | `CRunningScript::ProcessCommands200To299` @0x3f71ac `ldr w8, [x8, #0x568]` | proven |
| - bIsDrowning | word0 bit 30 |  | `CRunningScript::ProcessCommands200To299` @0x3f71b0 `ubfx w20, w8, #0x1e, #1` | proven |
| - bTyresDontBurst | word0 bit 31 | BurstTyre refuses | `CAutomobile::BurstTyre` @0x67ddc0 `ldr w8,[x19,#0x568]` + `tbnz w8,#0x1f` | proven |
| - bIsLawEnforcer, bIsLocked, bEngineOn, bIsHandbrakeOn, bLightsOn | word0 bits 0, 3, 4, 5, 6 |  | DWARF `CVehicleFlags` | dwarf |
| - bCanBeDamaged, bEngineBroken, bSirenOrAlarm | word0 bit 21; word1 bits 9, 15 |  | DWARF | dwarf |
| CVehicle.pDriver | +0x5a0 | CPed* | `CRunningScript::ProcessCommands1100To1199` @0x41c228 `ldr x9, [x9, #0x5a0]` | proven |
| CVehicle.pPassengers | +0x5a8 | CPed*[8] | `CRunningScript::ProcessCommands1000To1099` @0x41b170 `ldr x8, [x8, #0x5a8]` | proven |
| CVehicle.m_nNumPassengers | +0x5e8 | uint8 | `CRunningScript::ProcessCommands400To499` @0x40eef8 `ldrb w8, [x8, #0x5e8]` | proven |
| CVehicle.m_nMaxPassengers | +0x5ec | uint8 | `CRunningScript::ProcessCommands400To499` @0x40ef34 `ldrb w8, [x8, #0x5ec]` | proven |
| CVehicle.m_pFire | +0x5f8 | CFire* (non-NULL = burning) | `CRunningScript::ProcessCommands1100To1199` @0x41bc70 `ldr x9, [x8, #0x5f8]` | proven |
| CVehicle.VehicleCreatedBy | +0x610 | uint8: 1 random, 2 mission, 3 parked, 4 permanent | `CVehicle::CVehicle` @0x6a51f8 `strb w20, [x19, #0x610]`; names DWARF | proven |
| CVehicle.m_nHealth | +0x634 | float (1000 new; < 250 = on fire) | `CRunningScript::ProcessCommands500To599` @0x40fbb0 `ldr s0, [x8, #0x634]`; `CRunningScript::ProcessCommands1100To1199` @0x41bcb4 `ldr s0, [x9, #0x634]` | proven |
| CVehicle.m_pTowingVehicle / pBombOwner / m_nTimeOfDeath | +0x638 / +0x650 / +0x660 |  | DWARF | dwarf |
| CVehicle.m_eDoorLockState | +0x684 | int32: 0 none, 1 unlocked, 2 locked, 3 lockout player only, 4 locked player inside, 5 locked initially, 6 force shut doors, 7 locked but can be damaged | `CRunningScript::ProcessCommands500To599` @0x40f740 `str w8, [x9, #0x684]`; names DWARF `eCarLockState` | proven |
| CVehicle.LastDamagedWeaponType | +0x694 | int8 | `CVehicle::InflictDamage` @0x6a7bd4 `strb w21, [x20, #0x694]` | proven |
| CVehicle.pLastDamageEntity | +0x698 | CEntity* | `CRunningScript::ProcessCommands1300To1399` @0x41f438 `ldr x8, [x8, #0x698]`; `CVehicle::InflictDamage` @0x6a7be4 `str x19, [x20, #0x698]` | proven |
| CVehicle.m_baseVehicleType | +0x734 | int32: 0 automobile family, 5 boat, 6 train, 9 bike family | `CRunningScript::ProcessCommands1100To1199` @0x41bc74 `ldr w10, [x8, #0x734]`; ctors write the pair: CAutomobile {0,0} @0x66e5a4, CBike {9,9} @0x6814ac, CBoat {5,5} @0x68cc74, CTrain {6,6} constant @0x69fe40 | proven |
| CVehicle.m_vehicleType | +0x738 | int32: 0 car, 1 monster truck, 2 quad, 3 heli, 4 plane, 5 boat, 6 train, 9 bike, 10 bmx, 11 trailer | `CHeli::CHeli` @0x693794 `str w9, [x19, #0x738]`; `CPlane::CPlane` @0x698fa4 `str w10, [x19, #0x738]`; CMonsterTruck=1 @0x697dac, CQuadBike=2 @0x69da70, CBmx=10 @0x68a81c, CTrailer=11 @0x69e6d8 | proven |
| "wrecked" |  | `ENT_STATUS == 5` or bIsDrowning (script IS_CAR_DEAD) | IS_CAR_DEAD @0x3f6ba0..0x3f6bac, @0x3f71ac | proven |
| "burning" |  | `m_pFire != NULL` or `m_nHealth < 250.0` or (base type 0 and engine damage status > 0xe0) | IS_CAR_ON_FIRE @0x41bc70..0x41bcc4 (constant 250.0 at 0x73ac98) | proven |
| CAutomobile.m_damageManager | +0x758 | CDamageManager (0x18): +4 engine status, +5 wheel status[4], +9 door status[6] | `CRunningScript::ProcessCommands1100To1199` @0x41bc90 `add x0, x8, #0x758`; `CDamageManager::GetWheelStatus` @0x6909c8 `ldrb w0, [x8, #5]` | proven |
| car wheel status | veh + 0x75d + wheel | uint8: 0 intact, 1 burst, 2 missing; wheel 0 front-left, 1 rear-left, 2 front-right, 3 rear-right | `CDamageManager::GetWheelStatus` @0x6909c8 `ldrb w0, [x8, #5]`; values/names DWARF (`DT_WHEEL_*`, `FRONT_LEFT_WHEEL`..) | proven (location), dwarf (names) |
| bike wheel status | +0x84c (front), +0x84d (rear) | uint8, 1 = burst | `CRunningScript::ProcessCommands1100To1199` @0x41cb28 `ldrb w8, [x9, #0x84c]` | proven |
| CAutomobile.m_aWheelColPoints | +0x940 | CColPoint[4] (0x2c each, world position at +0): last ground contact of each wheel | DWARF | dwarf |
| wheel positions (model space) | `CVehicleModelInfo::GetWheelPosn(int wheel, CVector&, bool)` @0x45fb68 | model info = `CModelInfo::ms_modelInfoPtrs[model]` (array at 0xb666e0) | symbol only, not analysed | inferred |

`BurstTyre` is virtual, vtable slot +0x168 (`CRunningScript::ProcessCommands1200To1299` @0x41e1f4 `ldr x9, [x9, #0x168]`). Signature (DWARF names): `bool CAutomobile::BurstTyre(uint8 nWheelPieceType, bool bApplyForce)` @0x67dd98; `CBike::BurstTyre` @0x687a04.
`CAutomobile::BurstTyre` (@0x67ddd0..0x67ddec) accepts collision piece ids 13..16 (mapped to wheel 0,2,1,3) or a wheel index 0..3 directly; it returns 0 without doing anything when the model is 432 (Rhino), bTyresDontBurst is set, physical flag byte +0x67 bit 5 is set, or the wheel is not intact. Script BURST_CAR_TYRE passes (wheel, 1); for bikes it maps script wheel 2->0 and 3->1 (@0x41e13c..0x41e2a8). Call it through the vtable, on the game thread.

`int CVehicle::GetVehicleAppearance()` @0x6a65dc returns 1 car, 2 bike, 3 heli, 4 boat, 5 plane (script IS_CHAR_ON_ANY_BIKE compares with 2, IN_ANY_BOAT 4, IN_ANY_HELI 3, IN_ANY_PLANE 5: @0x41bb40, @0x41c684, @0x41c6d8, @0x41c72c).

## E. Events to hook

"PIC" = the first 4 instructions (16 bytes) contain no adrp/adr/b/bl/cbz/tbz/literal load and no branch of the function targets bytes 4..15, so they can be copied to a trampoline unchanged. "callers" = number of `bl`/`b` instructions in .text that reach the function directly / through its PLT stub (found by scanning all of .text). When all callers go through the PLT, patching the JUMP_SLOT is an alternative to an inline hook; the slot lies in PT_GNU_RELRO (0x821958..0x852000, library is BIND_NOW) so it is read-only until mprotect.

| function | addr | size | first 4 instruction words (u32 values, each stored little-endian in the file) | PIC | callers direct / PLT | JUMP_SLOT |
|---|---|---|---|---|---|---|
| `CWeapon::Fire` | 0x700c64 | 0x830 | `d10243ff 6d0223e9 a9036ffc a90467fa` | yes | 0 / 4 | 0x845578 |
| `CWeapon::FireInstantHit` | 0x701494 | 0x168c | `fc160fee 6d0133ed 6d022beb 6d0323e9` | yes | 2 / 5 | 0x842860 |
| `CWeapon::DoBulletImpact` | 0x705c7c | 0xc0c | `d10343ff 6d0623e9 a9076ffc a90867fa` | yes | 5 / 0 | - |
| `CWeapon::GenerateDamageEvent` | 0x706888 | 0x380 | `d102c3ff a9075ff8 a90857f6 a9094ff4` | yes | 2 / 9 | 0x83df78 |
| `CPedDamageResponseCalculator::ComputeDamageResponse` | 0x443b74 | 0x388 | `d10243ff f9002bf7 a90657f6 a9074ff4` | yes | 0 / 26 | 0x83eba8 |
| `CEventDamage::CEventDamage` | 0x444628 | 0xa0 | `f81e0ff3 a9017bfd 910043fd f000202c` | **NO** (adrp) | 0 / 26 | 0x8452f0 |
| `CVehicle::InflictDamage` | 0x6a7848 | 0x690 | `d10243ff 6d032beb 6d0423e9 f9002bf7` | yes | 0 / 5 | 0x842770 |
| `CExplosion::AddExplosion` | 0x6fcfac | 0xcdc | `d10443ff 6d073bef 6d0833ed 6d092beb` | yes | 1 / 18 | 0x83ea70 |
| `CProjectileInfo::AddProjectile` | 0x6fe51c | 0x9d8 | `d10483ff 6d083bef 6d0933ed 6d0a2beb` | yes | 0 / 7 | 0x843070 |
| `CEventGunShot::CEventGunShot` | 0x442854 | 0x50 | `32003fea 7900200a b000206a f946bd4a` | **NO** (adrp) | 0 / 4 | 0x843f10 |
| `CEventGroup::Add` | 0x4409a4 | 0x220 | `f81b0ff9 a9015ff8 a90257f6 a9034ff4` | yes | 1 / 209 | 0x83dc20 |
| `CWeapon::FireProjectile` | 0x703274 | 0x7b8 | `d103c3ff 6d072beb 6d0823e9 f9004bfb` | yes | 2 / 2 | 0x844bd0 |
| `CWeapon::FireAreaEffect` | 0x703a2c | 0x354 | `d10243ff fd001bec 6d03abeb 6d04a3e9` | yes | 1 / 0 | - |
| `CWeapon::FireSniper` | 0x702b20 | 0x334 | `d10403ff 6d0b2beb 6d0c23e9 f9006bf5` | yes | 1 / 0 | - |
| `CWeapon::FireM16_1stPerson` | 0x702e54 | 0x420 | `d103c3ff fd0043ea 6d08a3e9 f9004ffb` | yes | 1 / 0 | - |
| `CWeapon::FireFromCar` | 0x7042d4 | 0x144 | `f81d0ff5 a9014ff4 a9027bfd 910083fd` | yes | 1 / 0 | - |
| `CWeapon::FireInstantHitFromCar2` | 0x707098 | 0x1ec | `d104c3ff 6d0c33ed 6d0d2beb 6d0e23e9` | yes | 1 / 0 | - |
| `CBulletInfo::AddBullet` | 0x6fc55c | 0xdc | `6dbb33ed 6d012beb 6d0223e9 a9034ff4` | yes | 0 / 1 | 0x83e160 |
| `CShotInfo::AddShot` | 0x700294 | 0x214 | `6db933ed 6d012beb 6d0223e9 a9035ff8` | yes | 0 / 1 | 0x846360 |

Arguments (names from the DWARF of this binary; registers checked in the disassembly where noted):

| function | arguments -> registers | notes |
|---|---|---|
| `bool CWeapon::Fire` | x0 this (CWeapon*, a slot of the shooter's m_WeaponSlots), x1 pEntity (firer), x2 pStartPosn, x3 pBarrelPosn, x4 pTargetEnt, x5 pTargetPosn, x6 pAltPosn | saved at entry @0x700ca0..0x700cb8. Pointers may be NULL. Called for guns, projectiles, flamethrower etc. by `CTaskSimpleUseGun::FireGun`, `CTaskSimpleThrowProjectile::ProcessPed`, `CTaskSimpleGangDriveBy::FireGun`, `CTaskSimplePlayerOnFoot::ProcessPlayerWeapon`. Returns false when nothing was fired (state > 1 or no ammo, @0x700dc4..0x700de4): read w0 after calling the original. Sets m_eState=1 on success. Melee does not come here. |
| `bool CWeapon::FireInstantHit` | x0 this, x1 pEntity, x2 pStartPosn, x3 pBarrelPosn, x4 pTargetEnt, x5 pTargetPosn, x6 pAltPosn, w7 bCrossHairGun, [sp] bCreateGunFx | w7 saved @0x7014c4, stack byte read @0x701610 `ldrb w21, [x29, #0x10]`. Called from Fire (2 direct calls) and through the PLT from script, `CPlayerCrossHair::Update`, `CAutomobile::TankControl`, `CVehicle::FirePlaneGuns`. Creates the CEventGunShot (@0x701be0) and calls DoBulletImpact. |
| `void CWeapon::DoBulletImpact` | x0 this, x1 pEntity (firer), x2 pHitEntity (victim or NULL), x3 pShotOrigin, x4 pShotTarget, x5 pColPoint, w6 nIncrementalHit | exact shooter + victim of every instant-hit bullet. Only direct callers (FireInstantHit x3, FireM16_1stPerson, FireInstantHitFromCar2): inline hook only. It calls GenerateDamageEvent @0x7063e0 (ped hit) and CVehicle::InflictDamage @0x7064a4 (vehicle hit); it tests the hit entity type against 3 and 2 (@0x705e50..0x705e60). |
| `static void CWeapon::GenerateDamageEvent` | x0 pHitPed, x1 pEntity (inflictor), w2 WeaponType, w3 WeaponDamage, w4 PieceType, w5 dir | static. Reached for bullets, heli/vehicle guns (`FireOneInstantHitRound`), explosions (`CWorld::TriggerExplosionSectorList`), tear gas, melee (`CTaskSimpleFight::FightHitPed`), sniper bullets (`CBulletInfo::Update`), flames (`CShotInfo::Update`), drowning. 2 direct + 9 PLT callers: inline hook to see all. |
| `void CPedDamageResponseCalculator::ComputeDamageResponse` | x0 this, x1 pVictim (CPed*), x2 damageResponse (CPedDamageResponse*), w3 bTriggerPainAudio | the single funnel of ped damage (26 callers, all PLT: weapons, explosions, collisions, run over, fire, falls, stealth kill, cheats, script). this: +0 m_pInflictor, +8 m_fRawDamage (float; the function lowers it while armour absorbs), +0xc m_eHitZone, +0x10 m_eWeaponUsed, +0x14 m_bJumpedOutOfMovingCar. Returns immediately when `response->m_bDamageCalculated` (+0xa) is already set (@0x443b90..0x443ba0) - count a hit only when that byte is 0 at entry. After the call: response +0 m_fHealthLost, +4 m_fArmourLost, +8 m_bKilled. |
| `CEventDamage::CEventDamage` | x0 this, x1 pInflictor, w2 damage time, w3 weapon type, w4 ped piece, w5 hit direction, w6, w7 bools | NOT PIC (4th instruction is adrp). All 26 callers use the PLT. Fields: +0x18 inflictor, +0x20 time, +0x24 weapon, +0x28 piece, +0x2c dir, +0x40 CPedDamageResponse. The victim is not an argument (the event is added to the victim's event group afterwards). |
| `void CVehicle::InflictDamage` | x0 this (victim vehicle), x1 pInflictor, w2 WeaponUsed, s0 damage, s1-s3 Pos | registers saved @0x6a786c..0x6a7884. Callers: bullets, explosions, fire, sniper bullets, vehicle guns (5, all PLT). Writes vehicle LastDamagedWeaponType/pLastDamageEntity. |
| `static bool CExplosion::AddExplosion` | x0 pExplodingEntity (victim/source object, may be NULL), x1 pEntExplosionOwner (creator), w2 ExplosionType, s0-s2 position, w3 ActivationDelay ms, w4 bMakeSound, s3 fCamShake, w5 noDamage | registers saved @0x6fcfdc..0x6fd010 (CVector by value is passed in 3 float registers). 16 slots; returns 0 when all are in use. |
| `static bool CProjectileInfo::AddProjectile` | x0 pEntProjOwner, w1 ProjType (eWeaponType 16..21, 39 ...), s0-s2 initial position, s3 ThrowForce, x2 pFireDirn, x3 pTargetEntity | registers saved @0x6fe54c..0x6fe56c. All 7 callers use the PLT (thrown weapons via `CWeapon::FireProjectile`, heli/plane rockets, SAM sites, heat seekers, bombs). |
| `CEventGunShot::CEventGunShot` | x0 this, x1 pFiringEntity, s0-s2 origin, s3-s5 target, w2 bSilent | NOT PIC (3rd instruction adrp), size 0x50. 4 callers, all PLT: FireInstantHit, FireSniper, FireProjectile, FireInstantHitFromCar2 -> JUMP_SLOT hook sees every gunshot event. Event type 15 (`EVENT_SHOT_FIRED`). |
| `CEvent* CEventGroup::Add` | x0 this (CEventGroup*; +8 m_pPed owner (DWARF); presumably NULL for the global group), x1 rEvent, w2 bForcePersistence | every AI event passes here; event type = virtual at vtable slot +0x10 (CEventDamage 9, CEventGunShot 15, vehicle weapon damage 41). High call rate. |
| `CBulletInfo::AddBullet` / `CShotInfo::AddShot` | x0 owner, w1 weapon type, s0-s2, s3-s5 | sniper rounds / flamethrower-spray-extinguisher shots; their damage arrives later through GenerateDamageEvent with the stored owner. |

Explosion table `gaExplosion` @0xd28c78 (local symbol, 16 x 0x88, addressed with adrp+add in the code):

| field | offset | type | evidence | conf. |
|---|---|---|---|---|
| m_eExplosionType | +0x0 | int32: 0 grenade, 1 molotov, 2 rocket, 3 rocket weak, 4 car, 5 car quick, 6 boat, 7 heli, 8 mine, 9 object, 10 tank grenade, 11 small, 12 tiny | `CExplosion::AddExplosion` @0x6fd0cc `stur w20, [x26, #-0x88]`; `GetExplosionType` @0x6fcf88; names DWARF | proven |
| m_vecExplosionPosition | +0x4 | CVector | `CExplosion::GetExplosionPosition` @0x6fcfa4 `add x0, x8, #4` | proven |
| m_fExplosionRadius | +0x10 | float | `CExplosion::AddExplosion` @0x6fd384 `stur s2, [x26, #-0x78]` | proven |
| m_fExplosionPropagationRate | +0x14 | float | DWARF | dwarf |
| m_pEntExplosionOwner (creator) | +0x18 | CEntity* | `CExplosion::AddExplosion` @0x6fd0f4 `stur x19, [x26, #-0x70]` | proven |
| m_pExplodingEntity (victim) | +0x20 | CEntity* | DWARF | dwarf |
| m_TimeExpires | +0x28 | float (ms) | DWARF | dwarf |
| m_cExplosionActive | +0x30 | uint8, non-zero = slot in use | `CExplosion::AddExplosion` @0x6fd09c `ldrb w10, [x9, #0x30]` | proven |
| active counter | +0x31 | uint8 (DWARF name m_nTriggerExplosionSfx) | `GetExplosionActiveCounter` @0x6fcf34 `ldrb w0, [x8, #0x31]` | proven |
| m_ActivationTime / m_fExplosionForce | +0x38 / +0x3c | uint32 / float | DWARF | dwarf |

Projectile tables: `gaProjectileInfo` @0xd29508 (32 x 0x38, exported) and `CProjectileInfo::ms_apProjectile` @0xd29c08 (CProjectile*[32], the CObject of the same slot; position = that object's CPlaceable position, section C):

| field | offset | type | evidence | conf. |
|---|---|---|---|---|
| m_eProjectileType | +0x0 | int32 eWeaponType | DWARF | dwarf |
| m_pEntProjectileOwner (creator) | +0x8 | CEntity* | DWARF | dwarf |
| m_pTargetEntity | +0x10 | CEntity* (heat seekers) | DWARF | dwarf |
| m_fTimeExpires | +0x18 | uint32 ms | DWARF | dwarf |
| m_bProjectileActive | +0x1c | bool | `CProjectileInfo::AddProjectile` @0x6feb0c `ldrb w10, [x9, #0x1c]`; `CProjectileInfo::AddProjectile` @0x6feafc `cmp x8, #0x1f` | proven |
| OldCoors | +0x20 | CVector (previous position) | DWARF | dwarf |
| sizeof | 0x38 |  | `CProjectileInfo::GetProjectileInfo` @0x6fe510 `mov w9, #0x38` | proven |
| ms_apProjectile[i] |  | set to the new CObject (0x1f8 bytes) when slot i is filled | `CProjectileInfo::AddProjectile` @0x6feb68 `str x23, [x22]` | proven |

Other tables: `gaBulletInfo` @0xd28a08 (8 x 0x38: +0 type, +8 owner, +0x10 float expiry, +0x14 active, +0x18 position, +0x24 velocity, +0x30 int16 damage; DWARF), `gaShotInfo` @0xd29d08 (0x30 each: +0 type, +4 position, +0x10 velocity, +0x1c radius, +0x20 owner, +0x28 float expiry, +0x2c active; DWARF).

## F. Per-frame hook and timers

| function | addr | first 4 words | PIC | callers direct / PLT | JUMP_SLOT | when it runs (from the call sites) |
|---|---|---|---|---|---|---|
| `CWorld::Process` | 0x50be40 | `a9bc5ff8 a90157f6 a9024ff4 a9037bfd` | yes | 0 / 2 | 0x843fb0 | Called from `CGame::Process` @0x4d64a8 inside the block that is skipped when `m_CodePause \| m_UserPause` (@0x4d63ac, @0x4d63b4). One more caller: `CGenericGameStorage::DoGameSpecificStuffAfterSucessLoad` @0x5d41dc (once after loading a save). Best candidate: runs once per unpaused game frame; hook it and do the work after calling the original (peds/vehicles have just been processed). |
| `CTheScripts::Process` | 0x3f3ad8 | `d10203ff fd000be8 a9026ffc a90367fa` | yes | 0 / 5 | 0x845438 | Called from `CGame::Process` @0x4d63dc (same unpaused block, before the world update) and from 4 other places: `CGame::Initialise`, `CGame::ReInitGameObjectVariables`, `CEntryExit::TransitionFinished` (interior transitions), after-load. So it can run more than once per frame and before the player exists. |
| `CGame::Process` | 0x4d62d4 | `fc1b0fe8 f90007f9 a9015ff8 a90257f6` | yes | 0 / 1 | 0x840198 | Only caller: `Idle(void*, bool)` @0x4d8f80 (skipped when the byte `pumpHack` 0xbc2878 is set). Runs every frame of the running game including while paused; check the pause flags yourself. |

Whether `Idle` itself runs in the front-end menus was not traced (inferred: it is the in-game frame function). The mod should still guard with `FindPlayerPed(-1) != NULL` and the pool pointers being non-NULL.

| global | address | type | evidence | conf. |
|---|---|---|---|---|
| `CTimer::m_snTimeInMilliseconds` | 0xbdc558 | uint32 game clock in ms (that it stops while paused is inferred) | symbol; read @0x443e54/0x443e90 for LastDamagedTime | proven |
| `CTimer::m_snTimeInMillisecondsNonClipped` / `...PauseMode` | 0xbdc55c / 0xbdc560 | uint32 | symbols | proven |
| `CTimer::m_FrameCounter` | 0xbdc590 | uint32 | symbol | proven |
| `CTimer::ms_fTimeStep` | 0xbdc580 | float | symbol; read in CGame::Process @0x4d6690 | proven |
| `CTimer::m_UserPause` | 0xbdc594 | bool | symbol; `CGame::Process` @0x4d63ac `orr w11, w9, w8`; `CGame::Process` @0x4d63b4 `cbnz w11, #0x4d66e8` | proven |
| `CTimer::m_CodePause` | 0xbdc595 | bool | same | proven |

## G. Line of sight

```c
/* @0x5075a4  returns true when nothing is in the way */
bool CWorld_GetIsLineOfSightClear(const CVector *vecStart, const CVector *vecEnd,
        bool bCheckBuildings, bool bCheckVehicles, bool bCheckPeds, bool bCheckObjects, bool bCheckDummies,
        bool bSeeThroughStuff, bool bIgnoreSomeObjectsForCamera);
/* @0x508c7c  returns true when something was hit; fills *colPoint (0x2c bytes: +0 position, +0x10 normal) and *refEntityPtr */
bool CWorld_ProcessLineOfSight(const CVector *vecStart, const CVector *vecEnd, CColPoint *colPoint, CEntity **refEntityPtr,
        bool bCheckBuildings, bool bCheckVehicles, bool bCheckPeds, bool bCheckObjects, bool bCheckDummies,
        bool bSeeThroughStuff, bool bIgnoreSomeObjectsForCamera, bool bShootThroughStuff);
```
- Argument names and order are from the DWARF of this binary (proven). GetIsLineOfSightClear: x0, x1, w2..w7, and the 9th argument on the stack (`CWorld::GetIsLineOfSightClear` @0x50760c `ldrb w9, [x29, #0x10]`). ProcessLineOfSight: x0..x3, w4..w7, and 4 stack arguments (`CWorld::ProcessLineOfSight` @0x508d40 `ldrb w25, [x29, #0x20]`; `CWorld::ProcessLineOfSight` @0x508d20 `ldrb w12, [x29, #0x28]`). A normal C prototype with 9 / 12 parameters produces exactly this on arm64.
- First 4 words: GetIsLineOfSightClear `d10343ff fd002bea 6d0623e9 a9076ffc` (PIC), ProcessLineOfSight `d104c3ff fd005bea 6d0c23e9 a90d6ffc` (PIC).
- Game thread only: both increment the global `CWorld::ms_nCurrentScanCode` (0xc18350, @0x5075f0/0x507610) and walk the sector lists without locks.
- `CWorld::pIgnoreEntity` (0xbdcaf8, CEntity*) makes the tests skip one entity (the game sets it and restores NULL around a call); `CWorld::bIncludeDeadPeds` 0xbdcaeb, `bIncludeCarTyres` 0xbdcaec, `bIncludeBikers` 0xbdcaed change what is hit (symbols; semantics inferred from the names).
- With bCheckPeds/bCheckVehicles = true the shooter or the target itself blocks the line; pass false for those and test buildings/objects only, or set pIgnoreEntity (inferred usage).

## H. Friend / foe, groups, mission, cutscene

### H.1 Acquaintances

| what | address / offset | type | evidence | conf. |
|---|---|---|---|---|
| ped acquaintances | CPed +0x63c | uint32[5]; index = acquaintance id; bit n set = applies to ped type n | `CPedIntelligence::IsFriendlyWith` @0x5bde98 `add x0, x8, #0x63c`; `CAcquaintance::GetAcquaintances` @0x5c0940 `ldr w0, [x0, w1, sxtw #2]` | proven |
| acquaintance ids |  | 0 respect, 1 like, 2 ignore, 3 dislike, 4 hate | DWARF `ACQUAINTANCE_TYPE_PED_*`; ids 3 and 4 used by IsThreatenedBy: `CPedIntelligence::IsThreatenedBy` @0x5bdf20 `mov w1, #3`; `CPedIntelligence::IsThreatenedBy` @0x5bdf34 `mov w1, #4` | proven |
| ped type bit | `1u << pedType` (0 for type >= 32) |  | `CPedType::GetPedFlag` @0x5c0820 `lsl w8, w8, w0` | proven |
| CPedIntelligence.m_pPed | +0x0 | CPed* (the functions below reach the acquaintances through it) | `CPedIntelligence::IsFriendlyWith` @0x5bde8c `ldr x8, [x20]` | proven |
| default table per ped type | `*(CPedType**)0xc8dcd8` + pedType*0x14 + id*4 | uint32 | `CPedType::GetPedTypeAcquaintances(int id, int pedType)` @0x5c0a30..0x5c0a48 | proven |

| function | address | exact logic (from the code) |
|---|---|---|
| `bool CPedIntelligence::Respects(const CPed& other) const` | 0x5b8bec | `acq[0] & (1 << other.m_nPedType)` |
| `bool CPedIntelligence::IsFriendlyWith(const CPed& other) const` | 0x5bde74 | respect bit set, OR same ped type, OR like bit set (@0x5bdec8..0x5bdee8) |
| `bool CPedIntelligence::IsThreatenedBy(const CPed& other) const` | 0x5bdf04 | `(acq[3] \| acq[4]) & (1 << other.m_nPedType)` |
| `static bool CPedIntelligence::AreFriends(const CPed&, const CPed&)` | 0x5bdfc8 | A respects/likes B or same type, else the same test B -> A |
| `uint32 CAcquaintance::GetAcquaintances(int id) const` | 0x5c0940 | 2 instructions; `this` = ped + 0x63c |
| `uint32 CPedType::GetPedFlag(int pedType)` | 0x5c081c |  |

`this` of the CPedIntelligence functions is `*(void**)(ped + 0x538)`. "Is ped A hostile to the player": `*(uint32*)(A + 0x63c + 4*4) & 1` (hate, PLAYER1) or `... + 3*4` (dislike); or call `IsThreatenedBy(A_intel, playerPed)`. These are static attitudes; a ped that is actually attacking is found through its tasks (H.3).

### H.2 Groups (recruited homies)

| what | address / offset | type | evidence | conf. |
|---|---|---|---|---|
| `CPedGroups::ms_groups` | 0xc89c20 | CPedGroup[8], 0x4a0 each | symbol (size 9472); `CRunningScript::ProcessCommands1700To1799` @0x42a5f4 `mov w9, #0x4a0` | proven |
| `CPedGroups::ms_activeGroups` | 0xc8c150 | bool[8] | symbol; IS_GROUP_MEMBER @0x42a5e4 | proven |
| CPedGroup.m_membership | +0x10 | CPedGroupMembership (0x50) | `CRunningScript::ProcessCommands1700To1799` @0x42a600 `add x0, x8, #0x10` | proven |
| CPedGroupMembership.m_pMembers | +0x8 | CPed*[8]; [0..6] followers, [7] leader | `CPedGroupMembership::IsMember` @0x5ab86c `ldr x8, [x0, #8]`; `CPedGroupMembership::GetLeader` @0x5ab860 `ldr x0, [x0, #0x40]` | proven |
| player's group index | `*(int32*)(playerPed->m_pPlayerData + 0x4c)` |  | `CRunningScript::ProcessCommands1900To1999` @0x3fcfb0 `ldr w0, [x8, #0x4c]` | proven |

| function | address | notes |
|---|---|---|
| `bool CPedGroups::IsInPlayersGroup(const CPed*)` | 0x5b2b48 | returns false for any ped with m_pPlayerData; otherwise compares the ped with the 8 member slots of ms_groups[0] (hard-coded group 0, @0x5b2b58..0x5b2bcc) |
| `bool CPedGroupMembership::IsMember(const CPed*) const` | 0x5ab868 | `this` = group + 0x10; true for followers and leader |
| `bool CPedGroups::AreInSameGroup(const CPed*, const CPed*)` | 0x5b2bd4 | scans the active groups |
| `CPedGroup* CPedGroups::GetPedsGroup(const CPed*)` | 0x5ae408 | not analysed beyond the symbol |

Homie test without a call: `g = base + 0xc89c20 + playerGroup*0x4a0; for i in 0..6: *(CPed**)(g + 0x18 + 8*i) == ped`.

### H.3 What a ped is attacking (tasks)

| what | address / offset | type | evidence | conf. |
|---|---|---|---|---|
| CPedIntelligence task manager | +0x8 | CTaskManager: m_tasks[5] at intel+0x8, m_tasksSecondary[6] at intel+0x30 | `CPedIntelligence::GetTaskUseGun` @0x5bcb8c `add x19, x0, #8`; `CTaskManager::GetTaskSecondary` @0x64e6d8 `ldr x0, [x8, #0x28]` | proven |
| primary slots | intel + 0x8 + 8*n | 0 physical response, 1 event response temp, 2 event response non-temp, 3 primary, 4 default | `CPedIntelligence::FindTaskByType` searches 4,3,1,2 (@0x5bc458..0x5bc4a4); slot names inferred from PC | proven (layout), inferred (names) |
| secondary slot 0 | intel + 0x30 | attack task (use gun / fight) | `GetTaskUseGun` calls GetTaskSecondary(0) @0x5bcb94; DWARF `TASK_SECONDARY_ATTACK` = 0 | proven |
| CTask vtable | +0x18 GetSubTask, +0x20 IsSimpleTask, +0x28 GetTaskType |  | `CPedIntelligence::GetTaskUseGun` @0x5bcbb0 `ldr x8, [x8, #0x28]`; vtable dump | proven |
| CTaskSimpleUseGun (type 1017) | m_pTargetEntity +0x28; vtable symbol 0x8338c8 (+0x10 = object vptr) | CEntity* the ped is aiming/shooting at; +0x13 m_bFiredGun, +0x15 m_nFireGunThisFrame | `CTaskSimpleUseGun::CTaskSimpleUseGun` @0x5dd8b0 `str x22, [x1, #0x28]!`; `CPedIntelligence::GetTaskUseGun` @0x5bcbb8 `cmp w0, #0x3f9` | proven (target, type), dwarf (bools) |
| CTaskComplexKillPedOnFoot (type 1000) | m_pTargetPed +0x20; vtable 0x833c80 | CPed* the ped has decided to kill | `CTaskComplexKillPedOnFoot::CTaskComplexKillPedOnFoot` @0x5e3020 `str x20, [x1, #0x20]!`; `CTaskComplexKillPedOnFoot::GetTaskType` @0x5ee9f0 `mov w0, #0x3e8` | proven |
| CTaskSimpleFight (type 1016) | m_pTargetEntity +0x20; vtable 0x8337f8 | melee target | DWARF; GetTaskType @0x5eddd8 `mov w0, #0x3f8` | dwarf (field), proven (type) |
| CTaskSimpleGangDriveBy (type 1022) | m_pTargetEntity +0x48; vtable 0x833e60 | drive-by target | DWARF; GetTaskType @0x5eedf4 `mov w0, #0x3fe` | dwarf (field), proven (type) |

| function | address | notes |
|---|---|---|
| `CTaskSimpleUseGun* CPedIntelligence::GetTaskUseGun() const` | 0x5bcb80 | secondary slot 0 if its GetTaskType() == 1017, else NULL (emulated in verify_header.py) |
| `CTaskSimpleFight* CPedIntelligence::GetTaskFighting() const` | 0x5bcb20 | same with 1016 |
| `CTask* CPedIntelligence::FindTaskByType(int) const` | 0x5bc444 | walks primary slots 4,3,1,2 and their sub-task chains; use with 1000 to get the kill target |

### H.4 Mission and cutscene flags

| what | address | type | evidence | conf. |
|---|---|---|---|---|
| `CTheScripts::IsPlayerOnAMission()` | 0x3f4158 | bool; 13 instructions, starts with adrp (call it, do not hook) | `OnAMissionFlag != 0 && *(int32*)(ScriptSpace + OnAMissionFlag) == 1` (@0x3f4158..0x3f4188; emulated) | proven |
| `CTheScripts::OnAMissionFlag` | 0x9f83f8 | uint32 byte offset of the script variable | same | proven |
| `CTheScripts::ScriptSpace` | 0x9a2038 | uint8[339000] | same | proven |
| `CCutsceneMgr::ms_running` | 0xba8925 | bool | symbol; set to 1 in `SetupCutsceneToStart` @0x5504fc; read by `CGame::Process` @0x4d6488, `CWorld::Process` @0x50bfc0 and 25 more functions | proven |
| `CCutsceneMgr::ms_cutsceneProcessing` | 0xba8926 | bool (cutscene data loaded/processing) | symbol; read by `CGame::Process` @0x4d6338 | proven |
| `CTheScripts::bMiniGameInProgress` / `bPlayerIsOffTheMap` | 0x9ff3a0 / 0x9ff3a4 | bool | symbols only | inferred |
| `CGangWars::bIsPlayerOnAMission`, `CPedGroups::ms_bIsPlayerOnAMission` | 0x9825a4, 0xc8c168 | bool copies used by those systems | symbols only | inferred |

## I. Enumerations (from the DWARF of this binary)

- ePedType: 0 PLAYER1, 1 PLAYER2, 2 PLAYER_NETWORK, 3 PLAYER_UNUSED, 4 CIVMALE, 5 CIVFEMALE, 6 COP, 7..16 GANG1..GANG10, 17 DEALER, 18 MEDIC, 19 FIRE, 20 CRIMINAL, 21 BUM, 22 PROSTITUTE, 23 SPECIAL, 24..31 MISSION1..MISSION8. (Which gang number is which gang is game data, not in the binary: PC data has GANG1 Ballas, GANG2 Grove, GANG3 Vagos - inferred.)
- eWeaponType: 0 UNARMED, 1 BRASSKNUCKLE, 2 GOLFCLUB, 3 NIGHTSTICK, 4 KNIFE, 5 BASEBALLBAT, 6 SHOVEL, 7 POOL_CUE, 8 KATANA, 9 CHAINSAW, 10 DILDO1, 11 DILDO2, 12 VIBE1, 13 VIBE2, 14 FLOWERS, 15 CANE, 16 GRENADE, 17 TEARGAS, 18 MOLOTOV, 19 ROCKET, 20 ROCKET_HS, 21 FREEFALL_BOMB, 22 PISTOL, 23 PISTOL_SILENCED, 24 DESERT_EAGLE, 25 SHOTGUN, 26 SAWNOFF_SHOTGUN, 27 SPAS12_SHOTGUN, 28 MICRO_UZI, 29 MP5, 30 AK47, 31 M4, 32 TEC9, 33 COUNTRYRIFLE, 34 SNIPERRIFLE, 35 ROCKETLAUNCHER, 36 ROCKETLAUNCHER_HS, 37 FLAMETHROWER, 38 MINIGUN, 39 REMOTE_SATCHEL_CHARGE, 40 DETONATOR, 41 SPRAYCAN, 42 EXTINGUISHER, 43 CAMERA, 44 NIGHTVISION, 45 INFRARED, 46 PARACHUTE, 47 LAST_WEAPONTYPE, 48 ARMOUR, 49 RAMMEDBYCAR, 50 RUNOVERBYCAR, 51 EXPLOSION, 52 UZI_DRIVEBY, 53 DROWNING, 54 FALL, 55 UNIDENTIFIED, 56 ANYMELEE, 57 ANYWEAPON, 58 FLARE.
- ePedState: 0 NONE, 1 IDLE, 2 LOOK_ENTITY, 3 LOOK_HEADING, 4 WANDER_RANGE, 5 WANDER_PATH, 6 SEEK_POSITION, 7 SEEK_ENTITY, 8 FLEE_POSITION, 9 FLEE_ENTITY, 10 PURSUE, 11 FOLLOW_PATH, 12 SNIPER_MODE, 13 ROCKETLAUNCHER_MODE, 14 DUMMY, 15 PAUSE, 16 ATTACK, 17 FIGHT, 18 FACE_PHONE, 19 MAKE_PHONECALL, 20 CHAT, 21 MUG, 22 AIMGUN, 23 AI_CONTROL, 24 SEEK_CAR, 25 SEEK_BOAT_POSITION, 26 FOLLOW_ROUTE, 27 CPR, 28 SOLICIT, 29 BUY_ICE_CREAM, 30 INVESTIGATE_EVENT, 31 EVADE_STEP, 32 ON_FIRE, 33 SUNBATHE, 34 FLASH, 35 JOG, 36 ANSWER_MOBILE, 37 HANG_OUT, 38 STATES_NO_AI, 39 ABSEIL_FROM_HELI, 40 SIT, 41 JUMP, 42 FALL, 43 GETUP, 44 STAGGER, 45 EVADE_DIVE, 46 STATES_CAN_SHOOT, 47 ENTER_TRAIN, 48 EXIT_TRAIN, 49 ARREST_PLAYER, 50 DRIVING, 51 PASSENGER, 52 TAXI_PASSENGER, 53 OPEN_DOOR, 54 DIE, 55 DEAD, 56 DIE_BY_STEALTH, 57 CARJACK, 58 DRAGGED_FROM_CAR, 59 ENTER_CAR, 60 STEAL_CAR, 61 EXIT_CAR, 62 HANDS_UP, 63 ARRESTED, 64 DEPLOY_STINGER. (In SA most AI peds sit in a few of these; the tasks say more.)
- ePedPieceTypes (hit zone): 0 COL_SPHERE_LEG, 1 COL_SPHERE_MID, 2 COL_SPHERE_HEAD, 3 CHEST, 4 MIDSECTION, 5 UPPERARM_L, 6 UPPERARM_R, 7 LEG_L, 8 LEG_R, 9 HEAD.
- eFireType (CWeaponInfo +0): 0 MELEE, 1 INSTANT_HIT, 2 PROJECTILE, 3 AREA_EFFECT, 4 CAMERA, 5 USE. `CWeaponInfo::GetWeaponInfo(type, skill)` @0x709ba8, table `aWeaponInfo` @0xd2b0fc (0x70 each; +4 target range, +8 weapon range, +0x14 slot, +0x22 int16 damage; DWARF). eWeaponSkill: 0 POOR, 1 STD, 2 PRO, 3 SPECIAL.
- Event types: 9 EVENT_DAMAGE, 15 EVENT_SHOT_FIRED (class CEventGunShot), 41 EVENT_VEHICLE_DAMAGE_WEAPON, 49 gun shot whizzed by (`GetEventType` bodies @0x44cdbc, @0x44c708, @0x44ec70).

## J. Traps noticed

- Nothing matches the PC offsets: pointers are 8 bytes and CPed/CVehicle contain large audio entities first (CPed fields start at +0x198 with 0x3a0 bytes of audio objects; m_pPedIntelligence is at +0x538).
- Acquaintances are in CPed (+0x63c), not in CPedIntelligence as on some PC layouts; CPedIntelligence +0 is the owner ped.
- `m_pMat` can be NULL (entity uses the simple transform at +8/+0x14). Always use the position rule of section C.
- `m_pMyVehicle` must only be trusted when bInVehicle (+0x585 bit 0) is set: every game function read here tests the flag first (that the pointer stays set after leaving the car is inferred from PC).
- CWanted +0 is named `m_nWantedLevel` in the DWARF but the script commands read the stars from +0x2c (`m_WantedLevel`); +0 is the chaos value on PC (inferred).
- Vehicle class: use `m_vehicleType` (+0x738). `m_baseVehicleType` (+0x734) is 0 for helis and planes too.
- The pool element is bigger than the class (ped 0x9c8 vs CPed 0x988, vehicle 0xc68 for every vehicle class). Stride = pool element size.
- Pool sizes 140/110/350 are only the defaults of this file; read m_nSize.
- `CEventDamage::CEventDamage` (4th instruction adrp) and `CEventGunShot::CEventGunShot` (3rd instruction adrp) can NOT be hooked by copying 16 bytes. Use their JUMP_SLOT (all their callers go through the PLT) or hook `ComputeDamageResponse` / `FireInstantHit` instead.
- `CWeapon::DoBulletImpact`, `FireSniper`, `FireM16_1stPerson`, `FireAreaEffect`, `FireInstantHitFromCar(2)` have no PLT stub (only direct calls from Weapon.cpp): inline hook is the only way. `FireInstantHit`, `FireProjectile`, `GenerateDamageEvent`, `AddExplosion` have both direct and PLT callers: a JUMP_SLOT hook alone misses the direct ones.
- JUMP_SLOTs are inside PT_GNU_RELRO and the library is BIND_NOW: the page is read-only at run time.
- Functions too short or not position independent at the start (call only): FindPlayerPed/Vehicle/Coors/Wanted, CPools::Get*, IsPlayerOnAMission, IsInPlayersGroup, IsMember, GetPedTypeAcquaintances, GetWeaponInfo, CPed::IsPlayer; `CDamageManager::GetWheelStatus` is 12 bytes, `CAcquaintance::GetAcquaintances` 8 bytes, `CPedDamageResponseCalculator` ctor 24 bytes.
- `CWeapon::Fire` is entered also when the weapon can not fire (reloading / no ammo) - use its return value. Vehicle-mounted guns, rockets from helis and script-fired bullets do not pass through `Fire`.
- `ComputeDamageResponse` returns at once when the response was already calculated and modifies the calculator's raw damage; read the arguments at entry.
- `FindPlayerPed` returns Players[1] when `CHID::currentInstanceIndex == 1`.
- `CTheScripts::Process` has 5 call sites (not strictly once per frame). `CGame::Process` also runs while paused.
- The explosion/bullet/shot tables are local symbols (not exported); only base+offset works. `gaProjectileInfo` and `ms_apProjectile` are exported.
- The library was post-processed by the fastman92 tool (`.fastman92.*` sections, RWX trampoline area). If the limit adjuster is active it may patch code in memory: compare the expected words against memory at load, not against the file.
- By-value CVector arguments travel in three float registers (s0-s2, next vector s3-s5); a returned CVector comes back in s0-s2.

## K. Not found / uncertain

- No per-ped "current target" field for NPCs exists; use the tasks (H.3). Coverage of every attack task type (e.g. kill-from-boat, destroy-car, throw projectile 1018) was not mapped; only use-gun, kill-ped-on-foot, fight, drive-by.
- Whether `Idle`/`CGame::Process` run in the front-end menus was not traced.
- Slot names of the primary task array and the meaning of `CWorld::bInclude*` flags are from PC knowledge.
- Speed unit of m_vecMoveSpeed and gang-number-to-gang mapping are from PC knowledge.
- Projectile owner/type offsets, explosion victim offset, CTaskSimpleFight/GangDriveBy target offsets and most flag bit names are DWARF-only (no instruction collected).
- Wheel world positions: only the helper symbol and the DWARF field `m_aWheelColPoints` were located; not analysed.

## Appendix 1. Functions to call (address, first 4 words)

| prototype (C view) | addr | size | first 4 words |
|---|---|---|---|
| `bool CAutomobile::BurstTyre(CAutomobile*this, uint8 nWheelPieceType /*13..16 or wheel index 0..3*/, bool bApplyForce)  [virtual, vtable slot +0x168]` | 0x67dd98 | 0x174 | `6dbc23e9 a90157f6 a9024ff4 a9037bfd` |
| `bool CBike::BurstTyre(CBike*this, uint8 nWheelPieceType, bool bApplyForce)  [virtual, vtable slot +0x168]` | 0x687a04 | 0x31c | `d103c3ff 6d0b23e9 a90c57f6 a90d4ff4` |
| `CPlayerPed* FindPlayerPed(int player /*-1 = player in focus*/)` | 0x4efae0 | 0x4c | `d0001b08 f941a108 b9400108 7100051f` |
| `CVehicle* FindPlayerVehicle(int player, bool bIncludeRemote)` | 0x4efdec | 0x68 | `d0001b08 f9436d08 7100001f 52803b09` |
| `CVector FindPlayerCoors(int player)  [returns in s0,s1,s2]` | 0x4efea8 | 0x70 | `d0001b08 f9436d08 7100001f 52803b09` |
| `CWanted* FindPlayerWanted(int player)` | 0x4f0454 | 0x2c | `b0001b08 f9436d08 d0001ae9 7100001f` |
| `CPed* CPools::GetPed(int handle)` | 0x4f2378 | 0x44 | `37f801a0 b0001ac8 f944b508 53087c09` |
| `int CPools::GetPedRef(CPed*)` | 0x4f2340 | 0x38 | `b0001ac8 f944b508 d293a12a f2a7280a` |
| `CVehicle* CPools::GetVehicle(int handle)` | 0x4f23f4 | 0x44 | `37f801a0 90001ae8 f9454908 53087c09` |
| `int CPools::GetVehicleRef(CVehicle*)` | 0x4f23bc | 0x38 | `90001ae8 f9454908 d28528aa f2b5d80a` |
| `CObject* CPools::GetObject(int handle)` | 0x4f2468 | 0x44 | `37f801a0 b0001ac8 f943e108 53087c09` |
| `int CPools::GetObjectRef(CObject*)` | 0x4f2438 | 0x30 | `b0001ac8 f943e108 b204cfea f29e1e2a` |
| `bool CWorld::GetIsLineOfSightClear(const CVector*vecStart, const CVector*vecEnd, bool bCheckBuildings, bool bCheckVehicles, bool bCheckPeds, bool bCheckObjects, bool bCheckDummies, bool bSeeThroughStuff, bool bIgnoreSomeObjectsForCamera /*9th: on stack*/)` | 0x5075a4 | 0x15cc | `d10343ff fd002bea 6d0623e9 a9076ffc` |
| `bool CWorld::ProcessLineOfSight(const CVector*vecStart, const CVector*vecEnd, CColPoint*colPoint, CEntity**refEntityPtr, bool bCheckBuildings, bool bCheckVehicles, bool bCheckPeds, bool bCheckObjects, bool bCheckDummies /*stack*/, bool bSeeThroughStuff /*stack*/, bool bIgnoreSomeObjectsForCamera /*stack*/, bool bShootThroughStuff /*stack*/)` | 0x508c7c | 0x1154 | `d104c3ff fd005bea 6d0c23e9 a90d6ffc` |
| `bool CTheScripts::IsPlayerOnAMission(void)` | 0x3f4158 | 0x34 | `f00022c8 f9451508 b9400108 34000108` |
| `bool CPedIntelligence::IsFriendlyWith(const CPedIntelligence*this, const CPed*other)` | 0x5bde74 | 0x90 | `f81c0ff7 a90157f6 a9024ff4 a9037bfd` |
| `bool CPedIntelligence::IsThreatenedBy(const CPedIntelligence*this, const CPed*other)` | 0x5bdf04 | 0x68 | `f81d0ff5 a9014ff4 a9027bfd 910083fd` |
| `bool CPedIntelligence::Respects(const CPedIntelligence*this, const CPed*other)` | 0x5b8bec | 0x44 | `f81e0ff3 a9017bfd 910043fd f9400008` |
| `static bool CPedIntelligence::AreFriends(const CPed*a, const CPed*b)` | 0x5bdfc8 | 0xf0 | `a9bc5ff8 a90157f6 a9024ff4 a9037bfd` |
| `CTask* CPedIntelligence::FindTaskByType(const CPedIntelligence*this, int taskType)` | 0x5bc444 | 0x74 | `a9be4ff4 a9017bfd 910043fd 2a0103f3` |
| `CTaskSimpleUseGun* CPedIntelligence::GetTaskUseGun(const CPedIntelligence*this)` | 0x5bcb80 | 0x60 | `f81e0ff3 a9017bfd 910043fd 91002013` |
| `CTaskSimpleFight* CPedIntelligence::GetTaskFighting(const CPedIntelligence*this)` | 0x5bcb20 | 0x60 | `f81e0ff3 a9017bfd 910043fd 91002013` |
| `uint32 CAcquaintance::GetAcquaintances(const CAcquaintance*this, int id /*0 respect,1 like,2 ignore,3 dislike,4 hate*/)` | 0x5c0940 | 0x8 | `b861d800 d65f03c0 b861d808 0a020109` |
| `uint32 CPedType::GetPedFlag(int pedType)  [= 1<<pedType, 0 if >=32]` | 0x5c081c | 0x14 | `320003e8 1ac02108 7100801f 1a9fb100` |
| `uint32 CPedType::GetPedTypeAcquaintances(int id, int pedType)` | 0x5c0a30 | 0x20 | `d0001468 f9452908 52800289 f9400108` |
| `bool CPedGroups::IsInPlayersGroup(const CPed*)  [false for the player himself]` | 0x5b2b48 | 0x8c | `f942a008 b4000068 2a1f03e0 d65f03c0` |
| `bool CPedGroups::AreInSameGroup(const CPed*, const CPed*)` | 0x5b2bd4 | 0x164 | `2a1f03e8 b40007c0 b40007a1 b00014c8` |
| `CPedGroup* CPedGroups::GetPedsGroup(const CPed*)` | 0x5ae408 | 0xb4 | `b00014ea f944454a d00014eb f943756b` |
| `bool CPedGroupMembership::IsMember(const CPedGroupMembership*this, const CPed*)` | 0x5ab868 | 0xa8 | `b4000341 f9400408 eb01011f 54000320` |
| `int CVehicle::GetVehicleAppearance(const CVehicle*this)  [0 unknown,1 car,2 bike,3 heli,4 boat,5 plane]` | 0x6a65dc | 0x54 | `f9425408 39433d08 12000d08 7100211f` |
| `int CDamageManager::GetWheelStatus(const CDamageManager*this, int wheel)  [0 ok,1 burst,2 missing]` | 0x6909c4 | 0xc | `8b21c008 39401500 d65f03c0 7100143f` |
| `CWeaponInfo* CWeaponInfo::GetWeaponInfo(eWeaponType type, signed char skill /*1 = std*/)` | 0x709ba8 | 0x54 | `12001c28 71000d1f 54000108 900002e9` |
| `bool CPed::IsPlayer(const CPed*this)` | 0x595400 | 0x1c | `b9472008 34000088 7100051f 1a9f17e0` |
| `bool CPed::IsAlive(const CPed*this)` | 0x59afc8 | 0x14 | `b9454c08 121f7908 7100d91f 1a9f07e0` |
| `CEventGlobalGroup* GetEventGlobalGroup(void)` | 0x441028 | 0x60 | `a9be4ff4 a9017bfd 910043fd b0002e34` |
| `void CVehicleModelInfo::GetWheelPosn(CVehicleModelInfo*this, int wheel, CVector*out, bool local)` | 0x45fb68 | 0xd8 | `f81d0ff5 a9014ff4 a9027bfd 910083fd` |

## Appendix 2. All anchor instructions (address, word, instruction, function, what it proves)

| addr | word | instruction | in function | proves |
|---|---|---|---|---|
| 0x4f2384 | `53087c09` | `lsr w9, w0, #8` | `CPools::GetPed` | CPools::GetPed: index = handle >> 8 |
| 0x4f2388 | `f9400108` | `ldr x8, [x8]` | `CPools::GetPed` | CPools::GetPed: pool = *ms_pPedPool |
| 0x4f238c | `f940050a` | `ldr x10, [x8, #8]` | `CPools::GetPed` | CPools::GetPed: flags = pool->m_byteMap (+8) |
| 0x4f2394 | `6b20015f` | `cmp w10, w0, uxtb` | `CPools::GetPed` | CPools::GetPed: flags[index] must equal the low byte of the handle |
| 0x4f239c | `f9400108` | `ldr x8, [x8]` | `CPools::GetPed` | CPools::GetPed: objects = pool->m_aStorage (+0) |
| 0x4f23a0 | `5281390a` | `mov w10, #0x9c8` | `CPools::GetPed` | CPools::GetPed: ped pool element size |
| 0x4f241c | `52818d0a` | `mov w10, #0xc68` | `CPools::GetVehicle` | CPools::GetVehicle: vehicle pool element size |
| 0x4f2490 | `5280440a` | `mov w10, #0x220` | `CPools::GetObject` | CPools::GetObject: object pool element size |
| 0x4f2370 | `33185d20` | `bfi w0, w9, #8, #0x18` | `CPools::GetPedRef` | CPools::GetPedRef: handle = (index << 8) / flags[index] |
| 0x57acc0 | `b9401118` | `ldr w24, [x8, #0x10]` | `CPools::SavePedPool` | CPools::SavePedPool: pool->m_nSize (+0x10) |
| 0x57ace4 | `39c0012d` | `ldrsb w13, [x9]` | `CPools::SavePedPool` | CPools::SavePedPool: flags byte read signed ... |
| 0x57ace8 | `37f8022d` | `tbnz w13, #0x1f, #0x57ad2c` | `CPools::SavePedPool` | CPools::SavePedPool: ... negative (bit 7) = free slot, skipped |
| 0x5957b0 | `120019c9` | `and w9, w14, #0x7f` | `CPed::operator new` | CPed::operator new: allocation clears bit 7 of the flags byte |
| 0x595750 | `3219018c` | `orr w12, w12, #0x80` | `CPed::operator delete` | CPed::operator delete: free sets bit 7 of the flags byte |
| 0x59577c | `29422909` | `ldp w9, w10, [x8, #0x10]` | `CPed::operator new` | CPed::operator new: m_nSize (+0x10), m_nFirstFree (+0x14) |
| 0x4efb14 | `52803b0a` | `mov w10, #0x1d8` | `FindPlayerPed` | FindPlayerPed: sizeof(CPlayerInfo) |
| 0x4efb24 | `f9400100` | `ldr x0, [x8]` | `FindPlayerPed` | FindPlayerPed: CPlayerInfo.pPed (+0) |
| 0x4f0478 | `f9400500` | `ldr x0, [x8, #8]` | `FindPlayerWanted` | FindPlayerWanted: CPlayerInfo.PlayerPedData.m_Wanted (+8) |
| 0x4efe40 | `f9407120` | `ldr x0, [x9, #0xe0]` | `FindPlayerVehicle` | FindPlayerVehicle: CPlayerInfo.pRemoteVehicle (+0xe0) |
| 0x3f69c0 | `b9402c08` | `ldr w8, [x0, #0x2c]` | `CRunningScript::ProcessCommands200To299` | IS_WANTED_LEVEL_GREATER (010F): CWanted.m_WantedLevel stars (+0x2c) |
| 0x40eb18 | `b9402d29` | `ldr w9, [x9, #0x2c]` | `CRunningScript::ProcessCommands400To499` | STORE_WANTED_LEVEL (01C0): second anchor for CWanted +0x2c |
| 0x4efee8 | `f9400d09` | `ldr x9, [x8, #0x18]` | `FindPlayerCoors` | FindPlayerCoors: CPlaceable.m_pMat (+0x18) |
| 0x4efeec | `91002108` | `add x8, x8, #8` | `FindPlayerCoors` | FindPlayerCoors: CPlaceable.m_transform.m_translate (+8) used when m_pMat == NULL |
| 0x4efef0 | `9100c12a` | `add x10, x9, #0x30` | `FindPlayerCoors` | FindPlayerCoors: position inside CMatrix (+0x30) |
| 0x4f0720 | `2d420500` | `ldp s0, s1, [x8, #0x10]` | `FindPlayerHeading` | FindPlayerHeading: CMatrix forward vector x,y (+0x10); heading = atan2(-fx, fy) |
| 0x4f072c | `bd401520` | `ldr s0, [x9, #0x14]` | `FindPlayerHeading` | FindPlayerHeading: CPlaceable.m_transform.m_heading (+0x14) when m_pMat == NULL |
| 0x4269a0 | `79c06508` | `ldrsh w8, [x8, #0x32]` | `CRunningScript::ProcessCommands1600To1699` | GET_CHAR_MODEL (0665): CEntity.m_nModelIndex int16 (+0x32) |
| 0x41b284 | `79c06508` | `ldrsh w8, [x8, #0x32]` | `CRunningScript::ProcessCommands1000To1099` | GET_CAR_MODEL (0441): same field on a vehicle |
| 0x41c800 | `39416909` | `ldrb w9, [x8, #0x5a]` | `CRunningScript::ProcessCommands1100To1199` | IS_PLAYER_TARGETTING_CHAR (0457): CEntity type/status byte (+0x5a) |
| 0x41c804 | `12000929` | `and w9, w9, #7` | `CRunningScript::ProcessCommands1100To1199` | ... type = low 3 bits |
| 0x41c808 | `71000d3f` | `cmp w9, #3` | `CRunningScript::ProcessCommands1100To1199` | ... 3 = ENTITY_TYPE_PED |
| 0x6a5200 | `321f0129` | `orr w9, w9, #2` | `CVehicle::CVehicle` | CVehicle::CVehicle: type 2 = ENTITY_TYPE_VEHICLE |
| 0x3f6ba4 | `121d114a` | `and w10, w10, #0xf8` | `CRunningScript::ProcessCommands200To299` | IS_CAR_DEAD (0119): status = high 5 bits of +0x5a ... |
| 0x3f6ba8 | `7100a15f` | `cmp w10, #0x28` | `CRunningScript::ProcessCommands200To299` | ... 5 << 3 = STATUS_WRECKED |
| 0x4f03b4 | `9101a100` | `add x0, x8, #0x68` | `FindPlayerSpeed` | FindPlayerSpeed: CPhysical.m_vecMoveSpeed (+0x68) |
| 0x40fb74 | `bd46ad00` | `ldr s0, [x8, #0x6ac]` | `CRunningScript::ProcessCommands500To599` | GET_CHAR_HEALTH (0226): CPed.m_nHealth float (+0x6ac) |
| 0x41d648 | `bd46b500` | `ldr s0, [x8, #0x6b4]` | `CRunningScript::ProcessCommands1200To1299` | GET_CHAR_ARMOUR (04DD): CPed.m_nArmour float (+0x6b4) |
| 0x443bd8 | `bd46b660` | `ldr s0, [x19, #0x6b4]` | `CPedDamageResponseCalculator::ComputeDamageResponse` | ComputeDamageResponse: second anchor for armour |
| 0x404fa4 | `b9472108` | `ldr w8, [x8, #0x720]` | `CRunningScript::ProcessCommands2200To2299` | GET_PED_TYPE (089F): CPed.m_nPedType (+0x720) |
| 0x595400 | `b9472008` | `ldr w8, [x0, #0x720]` | `CPed::IsPlayer` | CPed::IsPlayer: second anchor for m_nPedType |
| 0x5958c4 | `39152261` | `strb w1, [x19, #0x548]` | `CPed::SetCharCreatedBy` | CPed::SetCharCreatedBy: CPed.CharCreatedBy uint8 (+0x548); 1 random, 2 mission |
| 0x59afc8 | `b9454c08` | `ldr w8, [x0, #0x54c]` | `CPed::IsAlive` | CPed::IsAlive: CPed.m_nPedState (+0x54c) |
| 0x59afd0 | `7100d91f` | `cmp w8, #0x36` | `CPed::IsAlive` | CPed::IsAlive: (state & ~1) == 54 means PED_DIE(54) / PED_DEAD(55) |
| 0x3f6b28 | `b9454d08` | `ldr w8, [x8, #0x54c]` | `CRunningScript::ProcessCommands200To299` | IS_CHAR_DEAD (0118): second anchor for m_nPedState |
| 0x3f65dc | `3956154a` | `ldrb w10, [x10, #0x585]` | `CRunningScript::ProcessCommands200To299` | IS_CHAR_IN_ANY_CAR (00DF): ped flags byte +0x585 ... |
| 0x3f65e0 | `3600316a` | `tbz w10, #0, #0x3f6c0c` | `CRunningScript::ProcessCommands200To299` | ... bit 0 = bInVehicle |
| 0x3f65ec | `f9438508` | `ldr x8, [x8, #0x708]` | `CRunningScript::ProcessCommands200To299` | IS_CHAR_IN_ANY_CAR (00DF): CPed.m_pMyVehicle (+0x708) |
| 0x4159f0 | `f9438529` | `ldr x9, [x9, #0x708]` | `CRunningScript::ProcessCommands900To999` | STORE_CAR_CHAR_IS_IN_NO_SAVE (03C0): second anchor for m_pMyVehicle |
| 0x4113a0 | `39561908` | `ldrb w8, [x8, #0x586]` | `CRunningScript::ProcessCommands700To799` | IS_CHAR_SHOOTING (02E0): ped flags byte +0x586 ... |
| 0x4113a4 | `12000101` | `and w1, w8, #1` | `CRunningScript::ProcessCommands700To799` | ... bit 0 = bFiringWeapon |
| 0x41f974 | `b9458508` | `ldr w8, [x8, #0x584]` | `CRunningScript::ProcessCommands1400To1499` | IS_CHAR_DUCKING (0597): first ped flags word (+0x584) ... |
| 0x41f978 | `531a6901` | `ubfx w1, w8, #0x1a, #1` | `CRunningScript::ProcessCommands1400To1499` | ... bit 26 = bIsDucking |
| 0x41c2a0 | `39a3710a` | `ldrsb x10, [x8, #0x8dc]` | `CRunningScript::ProcessCommands1100To1199` | GET_CURRENT_CHAR_WEAPON (0470): CPed.m_nCurrentWeapon int8 slot (+0x8dc) |
| 0x41c2a4 | `8b0a1508` | `add x8, x8, x10, lsl #5` | `CRunningScript::ProcessCommands1100To1199` | GET_CURRENT_CHAR_WEAPON: sizeof(CWeapon) = 0x20 |
| 0x41c2a8 | `b9473108` | `ldr w8, [x8, #0x730]` | `CRunningScript::ProcessCommands1100To1199` | GET_CURRENT_CHAR_WEAPON: CPed.m_WeaponSlots[0].m_eWeaponType (+0x730) |
| 0x41b458 | `b9473d2b` | `ldr w11, [x9, #0x73c]` | `CRunningScript::ProcessCommands1000To1099` | GET_AMMO_IN_CHAR_WEAPON (041A): slot 0 m_nAmmoTotal = +0x730 + 0xc |
| 0x700dc4 | `b9400668` | `ldr w8, [x19, #4]` | `CWeapon::Fire` | CWeapon::Fire: CWeapon.m_eState (+4); only fires when <= 1 |
| 0x701348 | `b9000669` | `str w9, [x19, #4]` | `CWeapon::Fire` | CWeapon::Fire: sets m_eState = 1 (WEAPONSTATE_FIRING) after a shot |
| 0x700dd0 | `b9400a68` | `ldr w8, [x19, #8]` | `CWeapon::Fire` | CWeapon::Fire: CWeapon.m_nAmmoInClip (+8) |
| 0x41c7f8 | `f9447108` | `ldr x8, [x8, #0x8e0]` | `CRunningScript::ProcessCommands1100To1199` | IS_PLAYER_TARGETTING_CHAR (0457): CPed.m_pEntLockOnTarget (+0x8e0) |
| 0x59f400 | `f94472a8` | `ldr x8, [x21, #0x8e0]` | `CPed::SetWeaponLockOnTarget` | CPed::SetWeaponLockOnTarget: second anchor for m_pEntLockOnTarget |
| 0x41f3d8 | `f944a108` | `ldr x8, [x8, #0x940]` | `CRunningScript::ProcessCommands1300To1399` | HAS_CHAR_BEEN_DAMAGED_BY_CHAR (051A): CPed.pLastDamageEntity (+0x940) |
| 0x443e80 | `f904a260` | `str x0, [x19, #0x940]` | `CPedDamageResponseCalculator::ComputeDamageResponse` | ComputeDamageResponse: writes pLastDamageEntity = inflictor (second anchor) |
| 0x411ba8 | `39e4f100` | `ldrsb w0, [x8, #0x93c]` | `CRunningScript::ProcessCommands700To799` | HAS_CHAR_BEEN_DAMAGED_BY_WEAPON (031D): CPed.LastDamagedWeaponType int8 (+0x93c) |
| 0x443e70 | `3924f268` | `strb w8, [x19, #0x93c]` | `CPedDamageResponseCalculator::ComputeDamageResponse` | ComputeDamageResponse: writes LastDamagedWeaponType (second anchor) |
| 0x443e94 | `b9094a68` | `str w8, [x19, #0x948]` | `CPedDamageResponseCalculator::ComputeDamageResponse` | ComputeDamageResponse: CPed.LastDamagedTime = CTimer ms (+0x948) |
| 0x5958d0 | `f9429e60` | `ldr x0, [x19, #0x538]` | `CPed::SetCharCreatedBy` | CPed::SetCharCreatedBy: CPed.m_pPedIntelligence (+0x538) |
| 0x5bdfe0 | `f9429e78` | `ldr x24, [x19, #0x538]` | `CPedIntelligence::AreFriends` | CPedIntelligence::AreFriends: second anchor for m_pPedIntelligence |
| 0x40eb10 | `f942a129` | `ldr x9, [x9, #0x540]` | `CRunningScript::ProcessCommands400To499` | STORE_WANTED_LEVEL (01C0): CPed.m_pPlayerData (+0x540) |
| 0x5b2b48 | `f942a008` | `ldr x8, [x0, #0x540]` | `CPedGroups::IsInPlayersGroup` | CPedGroups::IsInPlayersGroup: second anchor for m_pPlayerData |
| 0x6533a4 | `39412129` | `ldrb w9, [x9, #0x48]` | `CTaskSimplePlayerOnFoot::ProcessPlayerWeapon` | CTaskSimplePlayerOnFoot::ProcessPlayerWeapon: CPlayerPedData flags (+0x48) ... |
| 0x6533a8 | `361000e9` | `tbz w9, #2, #0x6533c4` | `CTaskSimplePlayerOnFoot::ProcessPlayerWeapon` | ... bit 2 = m_bHaveTargetSelected |
| 0x653adc | `37180068` | `tbnz w8, #3, #0x653ae8` | `CTaskSimplePlayerOnFoot::ProcessPlayerWeapon` | ProcessPlayerWeapon: bit 3 = m_bFreeAiming |
| 0x3fcfb0 | `b9404d00` | `ldr w0, [x8, #0x4c]` | `CRunningScript::ProcessCommands1900To1999` | GET_PLAYER_GROUP (07AF): CPlayerPedData.m_PlayerGroup (+0x4c) |
| 0x5bde98 | `9118f100` | `add x0, x8, #0x63c` | `CPedIntelligence::IsFriendlyWith` | CPedIntelligence::IsFriendlyWith: CPed.m_acquaintances (+0x63c), 5 x uint32 |
| 0x5bde8c | `f9400288` | `ldr x8, [x20]` | `CPedIntelligence::IsFriendlyWith` | CPedIntelligence::IsFriendlyWith: CPedIntelligence.m_pPed (+0) |
| 0x40fbb0 | `bd463500` | `ldr s0, [x8, #0x634]` | `CRunningScript::ProcessCommands500To599` | GET_CAR_HEALTH (0227): CVehicle.m_nHealth float (+0x634) |
| 0x41c228 | `f942d129` | `ldr x9, [x9, #0x5a0]` | `CRunningScript::ProcessCommands1100To1199` | GET_DRIVER_OF_CAR (046C): CVehicle.pDriver (+0x5a0) |
| 0x41b170 | `f942d508` | `ldr x8, [x8, #0x5a8]` | `CRunningScript::ProcessCommands1000To1099` | GET_CHAR_IN_CAR_PASSENGER_SEAT (0432): CVehicle.pPassengers[8] (+0x5a8) |
| 0x40eef8 | `3957a108` | `ldrb w8, [x8, #0x5e8]` | `CRunningScript::ProcessCommands400To499` | GET_NUMBER_OF_PASSENGERS (01E9): CVehicle.m_nNumPassengers (+0x5e8) |
| 0x40ef34 | `3957b108` | `ldrb w8, [x8, #0x5ec]` | `CRunningScript::ProcessCommands400To499` | GET_MAXIMUM_NUMBER_OF_PASSENGERS (01EA): CVehicle.m_nMaxPassengers (+0x5ec) |
| 0x40f740 | `b9068528` | `str w8, [x9, #0x684]` | `CRunningScript::ProcessCommands500To599` | LOCK_CAR_DOORS (020A): CVehicle.m_eDoorLockState (+0x684) |
| 0x41bc70 | `f942fd09` | `ldr x9, [x8, #0x5f8]` | `CRunningScript::ProcessCommands1100To1199` | IS_CAR_ON_FIRE (0495): CVehicle.m_pFire (+0x5f8) |
| 0x41bc74 | `b947350a` | `ldr w10, [x8, #0x734]` | `CRunningScript::ProcessCommands1100To1199` | IS_CAR_ON_FIRE (0495): CVehicle.m_baseVehicleType (+0x734) |
| 0x693794 | `b9073a69` | `str w9, [x19, #0x738]` | `CHeli::CHeli` | CHeli::CHeli: CVehicle.m_vehicleType (+0x738) = 3 |
| 0x698fa4 | `b9073a6a` | `str w10, [x19, #0x738]` | `CPlane::CPlane` | CPlane::CPlane: m_vehicleType = 4 (second anchor) |
| 0x41bc90 | `911d6100` | `add x0, x8, #0x758` | `CRunningScript::ProcessCommands1100To1199` | IS_CAR_ON_FIRE (0495): CAutomobile.m_damageManager (+0x758) |
| 0x6909c8 | `39401500` | `ldrb w0, [x8, #5]` | `CDamageManager::GetWheelStatus` | CDamageManager::GetWheelStatus: m_Wheel[4] at +5 |
| 0x41cb28 | `39613128` | `ldrb w8, [x9, #0x84c]` | `CRunningScript::ProcessCommands1100To1199` | IS_CAR_TYRE_BURST (0496) on a bike: CBike wheel status bytes (+0x84c, +0x84d) |
| 0x3f71ac | `b9456908` | `ldr w8, [x8, #0x568]` | `CRunningScript::ProcessCommands200To299` | IS_CAR_DEAD (0119): CVehicle flags (+0x568) ... |
| 0x3f71b0 | `531e7914` | `ubfx w20, w8, #0x1e, #1` | `CRunningScript::ProcessCommands200To299` | ... bit 30 = bIsDrowning |
| 0x41f438 | `f9434d08` | `ldr x8, [x8, #0x698]` | `CRunningScript::ProcessCommands1300To1399` | HAS_CAR_BEEN_DAMAGED_BY_CHAR (051C): CVehicle.pLastDamageEntity (+0x698) |
| 0x6a7be4 | `f9034e93` | `str x19, [x20, #0x698]` | `CVehicle::InflictDamage` | CVehicle::InflictDamage: writes pLastDamageEntity (second anchor) |
| 0x6a7bd4 | `391a5295` | `strb w21, [x20, #0x694]` | `CVehicle::InflictDamage` | CVehicle::InflictDamage: CVehicle.LastDamagedWeaponType int8 (+0x694) |
| 0x6a51f8 | `39184274` | `strb w20, [x19, #0x610]` | `CVehicle::CVehicle` | CVehicle::CVehicle: CVehicle.VehicleCreatedBy uint8 (+0x610) |
| 0x6a65dc | `f9425408` | `ldr x8, [x0, #0x4a8]` | `CVehicle::GetVehicleAppearance` | CVehicle::GetVehicleAppearance: CVehicle.pHandling (+0x4a8) |
| 0x41e1f4 | `f940b529` | `ldr x9, [x9, #0x168]` | `CRunningScript::ProcessCommands1200To1299` | BURST_CAR_TYRE (04FE): virtual BurstTyre = vtable slot +0x168 |
| 0x41bcb4 | `bd463520` | `ldr s0, [x9, #0x634]` | `CRunningScript::ProcessCommands1100To1199` | IS_CAR_ON_FIRE (0495): health < 250.0 counts as burning (second anchor for m_nHealth) |
| 0x6fcf78 | `52801109` | `mov w9, #0x88` | `CExplosion::GetExplosionType` | CExplosion::GetExplosionType: sizeof(CExplosion) |
| 0x6fcfa4 | `91001100` | `add x0, x8, #4` | `CExplosion::GetExplosionPosition` | CExplosion::GetExplosionPosition: m_vecExplosionPosition (+4) |
| 0x6fd09c | `3940c12a` | `ldrb w10, [x9, #0x30]` | `CExplosion::AddExplosion` | CExplosion::AddExplosion: m_cExplosionActive (+0x30) scanned to find a free slot |
| 0x6fd08c | `f1003d1f` | `cmp x8, #0xf` | `CExplosion::AddExplosion` | CExplosion::AddExplosion: 16 slots |
| 0x6fd0f4 | `f8190353` | `stur x19, [x26, #-0x70]` | `CExplosion::AddExplosion` | CExplosion::AddExplosion: m_pEntExplosionOwner = arg x1 at entry+0x18 (x26 = entry+0x88) |
| 0x6fd0cc | `b8178354` | `stur w20, [x26, #-0x88]` | `CExplosion::AddExplosion` | CExplosion::AddExplosion: m_eExplosionType at +0 |
| 0x6fd384 | `bc188342` | `stur s2, [x26, #-0x78]` | `CExplosion::AddExplosion` | CExplosion::AddExplosion: m_fExplosionRadius at +0x10 |
| 0x6fe510 | `321d0be9` | `mov w9, #0x38` | `CProjectileInfo::GetProjectileInfo` | CProjectileInfo::GetProjectileInfo: sizeof(CProjectileInfo) |
| 0x6feb0c | `3940712a` | `ldrb w10, [x9, #0x1c]` | `CProjectileInfo::AddProjectile` | CProjectileInfo::AddProjectile: m_bProjectileActive (+0x1c) |
| 0x6feafc | `f1007d1f` | `cmp x8, #0x1f` | `CProjectileInfo::AddProjectile` | CProjectileInfo::AddProjectile: 32 slots |
| 0x6feb68 | `f90002d7` | `str x23, [x22]` | `CProjectileInfo::AddProjectile` | CProjectileInfo::AddProjectile: ms_apProjectile[slot] = new CProjectile |
| 0x443b5c | `f9000001` | `str x1, [x0]` | `CPedDamageResponseCalculator::CPedDamageResponseCalculator` | CPedDamageResponseCalculator ctor: m_pInflictor (+0) |
| 0x443b60 | `bd000800` | `str s0, [x0, #8]` | `CPedDamageResponseCalculator::CPedDamageResponseCalculator` | CPedDamageResponseCalculator ctor: m_fRawDamage (+8) |
| 0x443b64 | `29018803` | `stp w3, w2, [x0, #0xc]` | `CPedDamageResponseCalculator::CPedDamageResponseCalculator` | CPedDamageResponseCalculator ctor: m_eHitZone (+0xc), m_eWeaponUsed (+0x10) |
| 0x443be4 | `b9401288` | `ldr w8, [x20, #0x10]` | `CPedDamageResponseCalculator::ComputeDamageResponse` | ComputeDamageResponse: reads m_eWeaponUsed (+0x10) |
| 0x443b90 | `39402aa8` | `ldrb w8, [x21, #0xa]` | `CPedDamageResponseCalculator::ComputeDamageResponse` | ComputeDamageResponse: CPedDamageResponse.m_bDamageCalculated (+0xa); returns at once when set |
| 0x44465c | `f8018d01` | `str x1, [x8, #0x18]!` | `CEventDamage::CEventDamage` | CEventDamage ctor: m_pInflictor (+0x18) |
| 0x444688 | `29040e62` | `stp w2, w3, [x19, #0x20]` | `CEventDamage::CEventDamage` | CEventDamage ctor: m_nDamageTime (+0x20), m_eWeaponUsed (+0x24) |
| 0x44468c | `b9002a64` | `str w4, [x19, #0x28]` | `CEventDamage::CEventDamage` | CEventDamage ctor: m_eHitZone (+0x28) |
| 0x44287c | `f8018d01` | `str x1, [x8, #0x18]!` | `CEventGunShot::CEventGunShot` | CEventGunShot ctor: m_pFiringEntity (+0x18) |
| 0x442880 | `2d040400` | `stp s0, s1, [x0, #0x20]` | `CEventGunShot::CEventGunShot` | CEventGunShot ctor: m_vShotOrigin (+0x20); target follows at +0x2c |
| 0x44cdbc | `52800120` | `mov w0, #9` | `CEventDamage::GetEventType` | CEventDamage::GetEventType = 9 |
| 0x44c708 | `32000fe0` | `mov w0, #0xf` | `CEventGunShot::GetEventType` | CEventGunShot::GetEventType = 15 |
| 0x42a5f4 | `52809409` | `mov w9, #0x4a0` | `CRunningScript::ProcessCommands1700To1799` | IS_GROUP_MEMBER (06EE): sizeof(CPedGroup) |
| 0x42a600 | `91004100` | `add x0, x8, #0x10` | `CRunningScript::ProcessCommands1700To1799` | IS_GROUP_MEMBER (06EE): CPedGroup.m_membership (+0x10) |
| 0x5ab86c | `f9400408` | `ldr x8, [x0, #8]` | `CPedGroupMembership::IsMember` | CPedGroupMembership::IsMember: m_pMembers[8] start at +8 |
| 0x5ab860 | `f9402000` | `ldr x0, [x0, #0x40]` | `CPedGroupMembership::GetLeader` | CPedGroupMembership::GetLeader: leader = m_pMembers[7] (+0x40) |
| 0x64e6d8 | `f9401500` | `ldr x0, [x8, #0x28]` | `CTaskManager::GetTaskSecondary` | CTaskManager::GetTaskSecondary: m_tasksSecondary[] at +0x28 of the task manager |
| 0x5bcb8c | `91002013` | `add x19, x0, #8` | `CPedIntelligence::GetTaskUseGun` | CPedIntelligence::GetTaskUseGun: CPedIntelligence.m_taskManager (+8) |
| 0x5bcbb0 | `f9401508` | `ldr x8, [x8, #0x28]` | `CPedIntelligence::GetTaskUseGun` | CPedIntelligence::GetTaskUseGun: CTask vtable slot +0x28 = GetTaskType |
| 0x5bcbb8 | `710fe41f` | `cmp w0, #0x3f9` | `CPedIntelligence::GetTaskUseGun` | CPedIntelligence::GetTaskUseGun: TASK_SIMPLE_USE_GUN = 1017 |
| 0x5edf28 | `52807f20` | `mov w0, #0x3f9` | `CTaskSimpleUseGun::GetTaskType` | CTaskSimpleUseGun::GetTaskType (second anchor) |
| 0x5ee9f0 | `52807d00` | `mov w0, #0x3e8` | `CTaskComplexKillPedOnFoot::GetTaskType` | CTaskComplexKillPedOnFoot::GetTaskType = 1000 |
| 0x5dd8b0 | `f8028c36` | `str x22, [x1, #0x28]!` | `CTaskSimpleUseGun::CTaskSimpleUseGun` | CTaskSimpleUseGun ctor: m_pTargetEntity (+0x28) |
| 0x5e3020 | `f8020c34` | `str x20, [x1, #0x20]!` | `CTaskComplexKillPedOnFoot::CTaskComplexKillPedOnFoot` | CTaskComplexKillPedOnFoot ctor: m_pTargetPed (+0x20) |
| 0x4d63ac | `2a08012b` | `orr w11, w9, w8` | `CGame::Process` | CGame::Process: m_CodePause / m_UserPause ... |
| 0x4d63b4 | `350019ab` | `cbnz w11, #0x4d66e8` | `CGame::Process` | ... non-zero skips the block that calls CTheScripts::Process and CWorld::Process |
| 0x4d63dc | `97f548cd` | `bl #0x228710` | `CGame::Process` | CGame::Process: the call to CTheScripts::Process (through its PLT stub) |
| 0x4d64a8 | `97f53e56` | `bl #0x225e00` | `CGame::Process` | CGame::Process: the call to CWorld::Process (through its PLT stub) |
| 0x3f4170 | `b8686928` | `ldr w8, [x9, x8]` | `CTheScripts::IsPlayerOnAMission` | CTheScripts::IsPlayerOnAMission: *(int*)(ScriptSpace + OnAMissionFlag) ... |
| 0x3f4174 | `7100051f` | `cmp w8, #1` | `CTheScripts::IsPlayerOnAMission` | ... == 1 means on a mission |
| 0x50760c | `394043a9` | `ldrb w9, [x29, #0x10]` | `CWorld::GetIsLineOfSightClear` | CWorld::GetIsLineOfSightClear: 9th argument read from the caller stack |
| 0x508d40 | `394083b9` | `ldrb w25, [x29, #0x20]` | `CWorld::ProcessLineOfSight` | CWorld::ProcessLineOfSight: stack argument (bIgnoreSomeObjectsForCamera) |
| 0x508d20 | `3940a3ac` | `ldrb w12, [x29, #0x28]` | `CWorld::ProcessLineOfSight` | CWorld::ProcessLineOfSight: stack argument (bShootThroughStuff) |
| 0x5c0940 | `b861d800` | `ldr w0, [x0, w1, sxtw #2]` | `CAcquaintance::GetAcquaintances` | CAcquaintance::GetAcquaintances: uint32 m_nAcquaintances[id] |
| 0x5c0820 | `1ac02108` | `lsl w8, w8, w0` | `CPedType::GetPedFlag` | CPedType::GetPedFlag: 1 << pedType |
| 0x5bdf20 | `320007e1` | `mov w1, #3` | `CPedIntelligence::IsThreatenedBy` | CPedIntelligence::IsThreatenedBy: acquaintance id 3 (dislike) ... |
| 0x5bdf34 | `321e03e1` | `mov w1, #4` | `CPedIntelligence::IsThreatenedBy` | ... and id 4 (hate) |



## L. 1.0 (Helicover 2.0): the body and the map - functions the mod calls itself

Found in the player's `libGTASA.so` by symbol name, sizes and fields from the DWARF the file carries, behaviour read from the
disassembly (scratch tools: `dis.py`, `dwarf_dump.py`). `gta-reversed` / `aml-psdk` were used as a guide to WHAT to look for;
every address and offset below is from this binary. Checked at start-up by the first words (BODY_WORDS, GROUND_WORDS in
`brain/game/brain.c`); nothing is called when a word differs.

| What | Address | Proof / notes |
|---|---|---|
| `CTask::operator new(unsigned long)` | 0x5d7414 | takes from `CPools::ms_pTaskPool` (GOT 0x84a330); returns 0 when the pool is full (handled) |
| `CTaskComplexGoToPointAndStandStill(int moveState, const CVector&, float radius, float slowDown, bool, bool)` | 0x632400 | 0x38 bytes: +0x18 moveState, +0x1c target, +0x28 radius, +0x2c slowDownDistance, +0x30 bits (0x1 overshoot, 0x2 stop exactly, **0x4 new target**) |
| its `ControlSubTask` | 0x63296c | `tbnz w8,#2` at 0x632988: with the new-target bit it asks the sub-task to stop (vtable +0x38, priority 1) and calls CreateFirstSubTask (vtable +0x58) - so writing +0x1c / +0x18 and setting 0x4 re-aims the SAME task. It also turns RUN (6) into WALK (4) inside slowDownDistance and SPRINT (7) into RUN near the target |
| `CTaskComplexGoToPointShooting(int moveState, const CVector&, CEntity *aim, CVector aimPos, float radius, float slowDown)` | 0x633510 | 0x50 bytes (base GoToPointAiming: +0x18 moveState, +0x20 aim entity, +0x34 move target); CVector by value = v0-v2 |
| `CTaskManager::SetTask(CTask*, int slot, bool)` | 0x64e084 | deletes the old task of the slot (vtable +8), stores, builds the sub-task chain (+0x58 CreateFirstSubTask, +0x48 SetSubTask) |
| task vtable layout | | +0x08 deleting destructor, +0x18 GetSubTask, +0x20 IsSimple, +0x28 GetTaskType, +0x38 MakeAbortable(ped, priority, event), +0x58 CreateFirstSubTask |
| vtables (object vptr = symbol + 0x10) | | GoToPointAndStandStill 0x839040, GoToPointShooting 0x839b98, UseSwatRope 0x8381f8, SimpleUseGun 0x8338c8 |
| `CPedIntelligence` | ped +0x538 | task manager at +0x8: main slots 0 physical response, 1 event (temporary), 2 event, **3 primary**, 4 default; secondary from +0x28 (0 attack, 1 duck); manager +0x58 = ped |
| `CWorld::FindGroundZFor3DCoord(float x, float y, float z, bool *found, CEntity **)` | 0x50f408 | a vertical line check (buildings only) from z down; returns the height in s0 |
| ped flags | +0x584.. | +0x584 bit 0 standing; +0x585 bit 0 in a vehicle (used since 0.1), **bit 1 in the air** |
| velocity | entity +0x68 | per frame at 50 fps (x 50 = m/s) |
| pools | 0xbc3bc8 buildings (0x60), 0xbc3bd0 objects (0x1f8), 0xbc3bd8 dummies (0x60) | sizes from the DWARF; used to check the entity of a cover point (the kernel read of 0.8 was refused on the tablet: "live 23-86, read 0") |

Known and NOT used (kept for later): `CTaskManager::SetTaskSecondary` 0x64e5c8, `CTaskSimpleUseGun` ctor 0x5dd83c (0x58),
`CTaskSimpleDuck` ctor 0x660900 (0x38), `CTaskComplexUseSwatRope` ctors 0x623d84 / 0x623dcc (0x30), `CRopes::RegisterRope`
0x4f96d8, `CPedIntelligence::SetPedDecisionMakerType` 0x5ba338, `CPathFind::DoPathSearch` 0x3dbc30, `CTaskSimpleClimb::TestForClimb`
0x645c20, `CWorld::FindRoofZFor3DCoord` 0x50f4a4. Enums: eMoveState STILL 1, WALK 4, JOG 5, RUN 6, SPRINT 7.

Why the guards were late everywhere until 0.9 (the sixth log): the script gave a new go-to command every 0.1 s and the game
started the walk anew each time; a SPRINT move state keeps sprinting while the target is more than about 10 m off. Why the
second four fell: the ground worker let the helicopter go the moment the first four stood - the same moment the second four
were put on its ropes.
Not verified in the game (no device here): everything in this section runs on the emulator with recorders in place of the
game functions; the first real proof is the tablet's log (`body MOD: new tasks ... retargets ... refused ...`, `game tasks`).


## M. 1.1 (Helicover 2.0 beta 2): the game AI kept off the guards, the gun task, ropes, task types

All from the player's `libGTASA.so` (symbols, DWARF, disassembly). Checked at start-up by first words (MIND_WORDS, GUN_WORDS,
RELOAD_WORDS, ROPE_WORDS in `brain/game/brain.c`).

| What | Address | Proof / notes |
|---|---|---|
| `CPedIntelligence::SetPedDecisionMakerType(int)` | 0x5ba338 | 14 instructions of plain field logic: +0x160 the type in force, +0x164 the stored one (when +0x160 is 0 the new type is only stored; type 0 stores the current one and clears it; type 7 also sets +0x170) |
| `CTaskManager::ClearTaskEventResponse()` | 0x64e734 | deletes the temporary event task (slot 1, mgr+8) if there is one, ELSE the event task (slot 2, mgr+0x10), and clears the slot - so it is called only with slot 1 empty, after the task agreed to stop (vtable +0x38) |
| `CTaskManager::SetTaskSecondary(CTask*, int)` | 0x64e5c8 | secondary slots from mgr+0x28: 0 attack, 1 duck; deletes the old one, builds sub-tasks like SetTask |
| `CTaskSimpleUseGun(CEntity *target, CVector pos, signed char cmd, short burst, bool aimNow)` | 0x5dd83c | 0x58 bytes; +0x17 next command, +0x18 last command, +0x28 target entity, +0x50 burst length |
| `CTaskSimpleUseGun::ControlGun(CPed*, CEntity*, signed char)` | 0x5dfb64 | sets +0x11 "in control", swaps the target (with entity references), raises +0x17 to the command if it is higher; returns 1 |
| eGunCommand | | NONE 0, AIM 1, FIRE 2, FIREBURST 3, RELOAD 4, PISTOLWHIP 5, END_LEISURE 6, END_NOW 7 |
| `CWeapon::Reload(CPed*)` | 0x700a2c | clip (+8) = min(total (+0xc), the weapon info's clip size); nothing when total is 0 |
| CWeapon in the ped | ped+0x730 + slot*0x20 | +0 type, +4 state, +8 clip, +0xc total; active slot ped+0x8dc |
| `CRopes::aRopes` | 0xbd3e50 | 8 x 0x340: +0 node positions (32 x CVector, node 0 = top), +0x180 node speeds, +0x300 id (u64), +0x318 connected to, +0x334 TimeToBeKeptAliveTill, +0x339 type (0 = free), +0x338 fixed at node |
| `CRopes::CreateRopeForSwatPed(const CVector&)` | 0x4fa678 | id = counter (0xbd5854) + 100; RegisterRope(id, type 8, pos, true, 0, false, holder 0, 4000 ms) - the rope of the script command lives 4 s and has no holder |
| `CRopes::RegisterRope` | 0x4f96d8 | for an id already in the table: writes the position to node 0, clears its speed - the top is moved, the life is NOT renewed (that is `+0x334`, compared with the game clock in `CRope::Update` 0x4f7d1c) |
| `CTaskComplexUseSwatRope` | ctors 0x623d84 (id), 0x623dcc (id, CHeli*) | 0x30 bytes: +0x18 rope id (int), +0x20 bit 0 "from a helicopter", +0x28 the helicopter |
| eTaskType (the whole enum is in the DWARF) | | 108 USE_SWAT_ROPE, 203 STAND_STILL, 208 FALL_AND_GET_UP, 217 DIE, 240 IN_AIR_AND_LAND, 250 ON_FIRE, 412 COWER, 413 HANDS_UP, 415 DUCK, 500-512 hits and evasive steps, 601 REACT_TO_GUN_AIMED_AT, 900 GO_TO_POINT, 901 GO_TO_POINT_SHOOTING, 903 GO_TO_POINT_AND_STAND_STILL, 905-940 routes / seek / flee / wander / investigate, 1000-1032 kill ped ..., 1017 USE_GUN, 1100-1105 arrest / pursuit, 1200-1219 gang, 1500-1505 group follow |

What the mod removes from a guard's event slot ("wanders"): types 412, 413, 600-699, 905-940, 1000-1299, 1500-1599. Left alone:
everything else - falling, getting up, in the air, fire, hits, evasive steps and dives, water, cars.

The gun task for an NPC in the attack slot with nothing in his main slot is the way the game itself has peds fire (its gun
control tasks create a CTaskSimpleUseGun); whether it FIRES for a task made by the mod could not be proved here - so the mod
checks it in the game: fire ordered for 3 s and the weapon's rounds (clip + total) unchanged for every guard means "no", is
logged, and the scripts fire as before.

## N. 1.3 (Helicover 2.0 beta 4): fire on the move, arms on the target, climbing, the medic

Checked on the player's libGTASA.so (DWARF + disassembly), 16.11.2026.

- In the 1.2 game a guard with `CTaskSimpleUseGun` in his attack slot did not move (173 samples, 1 cm a sample); walking
  guards therefore carry no gun task of the mod's.
- `CTaskComplexGoToPointAiming` (base of GoToPointShooting 0x633510, 0x50 bytes): +0x18 move state, +0x20 aim entity
  (registered reference - never changed in place), +0x28 aim point, +0x34 move point, +0x40 target radius, +0x44 slow-down
  distance, +0x48 bit 0 = new target. `ControlSubTask` 0x633240: `ldrb w8,[x21,#0x48]` (0x394122a8) `tbnz w8,#0`
  (0x37000808) rebuilds the subtask; otherwise, while the subtask is GoToPointAndStandStill (903), it copies +0x34 into the
  subtask's +0x1c and sets the subtask's bit 0x4 when they differ (0x6332b0 `ldr s0,[x9,#0x34]!` 0xbc434d20 ... `orr w11,
  w11,#4` 0x321e016b). So the move point of a running go-and-shoot task is changed by writing +0x34 alone.
- `IKChainManager_c::PointArm` 0x5d3b94 (first words 6db82beb 6d0123e9 f90013fb a90367fa), this = `g_ikChainMan` 0xc98340.
  The game's own aiming (`CTaskSimpleUseGun::AimGun` 0x5deef4) calls it every frame as
  `PointArm(&g_ikChainMan, "CTaskSimpleUseGun", arm, ped, entity, bone, &pos, ARM_IK_AIM_RATE, ARM_IK_AIM_BLEND_TIME, 100.0)`:
  arm 0 = the weapon arm, 1 = the other arm too for two-handed weapons (CWeaponInfo flags +0x18 bit 3 at +0x19); entity 0 and
  bone -1 = `pos` is a world point. `ARM_IK_AIM_RATE` (float) and `ARM_IK_AIM_BLEND_TIME` (int) are globals read through the
  GOT (0x84b390, 0x850eb8). The chain lives in the ped's secondary task slot 5 (`IsArmPointing` / `AbortPointArm` read
  GetTaskSecondary(5)) - not the attack slot, so it does not hold the man still.
- `CTaskComplexJump` (0x20 bytes) ctor 0x647668 (`stp x20,x19` a9be4ff4): +0x18 `m_nForceClimb` (int), +0x1c
  `m_bUsePlayerLaunchForce`. The game gives it to ordinary peds itself: `CEventHandler::ComputeBuildingCollisionResponse`
  0x453c9c makes `CTaskComplexJump(0)` for a ped that walks into a building, and `CTaskSimpleClimb` directly when an edge is
  found (0x453d90); `CTaskSimpleJump::ProcessPed` 0x646d18 and `CTaskSimpleInAir::ProcessPed` 0x645bbc call
  `CTaskSimpleClimb::TestForClimb` 0x645c20. vtable `_ZTV16CTaskComplexJump` (GOT 0x850490).
- `CPed` +0x6ac health, +0x6b0 `m_nMaxHealth` (float), +0x6b4 armour.

## O. 2.0 beta 6: the commander's voice and his "come to me"

Checked on the player's libGTASA.so (DWARF + disassembly) and in the emulator on its real code, 16.11.2026.

- `CPed::Say(u16 ctx, u32 delay, float prob, u8 overrideSilence, u8 forceAudible, u8 frontEnd)` 0x5a57c4 =
  `CAEPedSpeechAudioEntity::AddSayEvent(this + 0x340, 52, ctx, delay, prob, ...)` 0x4757c0 (tail call; returns the sound id,
  -1 (0xffff) for every early return). The speech entity is `CPed` +0x340 (0x130 bytes, vtable 0x82f650): +8 the ped, +0xb8
  initialised, +0xba audio type (0 GEN, 1 EMG, 2 PLAYER, 3 GANG, 4 GFD, 5 SPC), +0xbc voice, +0xbe female, +0xc0 speaking,
  +0xc1 speech off (0489 "mute", being hit), +0xc2 off for a script line, +0xc3 front end, +0xc4 force audible, +0xd0 sound,
  +0xd2 bank, +0xd4 slot, +0xd8 volume, +0xdc last global context.
- `Initialise(CEntity*)` 0x4785f8 (called by the CCivilianPed / CCopPed / CEmergencyPed / CPlayerPed constructors): type =
  `CPedModelInfo` +0x6c (`m_AudioPedType`, from peds.ide), voice = +0x72 (`m_NextVoice`, then `IncrementVoice`), SPC models
  through `gSpecialPedVoiceLookup`; female from the default ped type (5 / 22); +0xb8 = 1 last. Type > 5 or voice < 0: not
  initialised (AddSayEvent then returns -1 at once).
- AddSayEvent returns -1 when: not initialised; `s_bAllSpeechDisabled` 0xbab97c (cutscenes); +0xc2; widescreen and not PLAYER /
  GFD; `CGameLogic::GameState` == 2; probability; +0xc1 unless overrideSilence; +0xc0 (speaking) for a non-pain line; dead;
  `CStreaming::IsVeryBusy()` (0x392dc4: `CRenderer::m_loadingPriority` or `ms_numModelsRequested` > 5) unless frontEnd,
  forceAudible or the context is "important for streaming" (jump table 0x74a154: only 13, 15, 48-64, 125-127, 161-171 -
  NOT MOVE_IN, NOT DUCK); farther than 40 m from the camera (0x740298 = 1600); no free speech slot of 5 or the context rested
  (`CanWePlayGlobalSpeechContext` 0x475fc8: `gGlobalSpeechContextNextPlayTime[ctx]` 0xbab058, set to now + repeat (7000 ms for
  most) + 1..1000 by anybody who says it); `GetSoundAndBankIDs` 0x476284 < 0.
- `GetSoundAndBankIDs`: `gSpeechContextLookup` 0x880c92 (GOT 0x851d88), rows of 8 int16 {global, GEN, EMG, PLAYER, GANG, GFD,
  repeat ms, 0}, -1 ends; column = type. EMG (type 1, jump table 0x74a64c entry 1 -> 0x4763e0): specific <= 34,
  `gEmgSpeechLookup` 0x874710 (GOT 0x8505c0) [35][46] {int16 first, last} (-1 = the voice has none), bank =
  `gEmgSpeechVoiceToBankLookup` 0x8746b4 [voice] (ARMY1-3 = banks 365-367). Voice names `gEmgSpeechVoiceLookup` 0x87431c (20 bytes
  each): 0-2 ARMY1-3, 3-7 EMT1-5, 8-12 FBI2-6, 13-20 LAPD1-8, 21-25 LVPD1-5, 26-31 MCOP1-6, 32 PULASKI, 33-36 RCOP1-4, 37-41 SFPD1-5,
  42-45 SWAT1, 2, 4, 6.
- The 0.8 table against EMG: MOVE_IN 144 (EMG 10: ARMY1-3, SWAT1, police), ORDER_WAIT_MANY 159 / ORDER_FOLLOW_NEAR_MANY 153 /
  CHASED 44 / ORDER_ATTACK_SINGLE 148 (PLAYER only), ENEMY_GANG_WASTED 258 / CAR_WAIT_FOR_ME 40 (GANG only), DUCK 85 (EMG 7: all
  army, SWAT, FBI, police), TARGET 220 (EMG 20: SWAT, FBI, police - no army voice). The GEN column is -1 for all of them.
- What the army voices have (global contexts): CHAT 45, COVER_ME 65, DODGE 74, DUCK 85, FIGHT 89, JACKING 121-124, MOVE_IN 144,
  SHOCKED 181, SHOOT_GENERIC 184, STEALTH_ALERT_SOUND 202 / SIGHT 203 / GENERIC 204, STEALTH_NOTHING_THERE 206. SWAT1: CHASE_FOOT
  43, COVER_ME, DODGE, DUCK, MOVE_IN, ROPE 177, SOLO 199, SURROUNDED 207, TARGET (SWAT2/4/6: no MOVE_IN).
- `PlayLoadedSound` 0x478e2c: forceAudible sets the sound's emitted volume to +3 dB (CAESound +0x20).
- `CTaskSimpleRunNamedAnim(anim, set, flags, blend, time, dontInterrupt, runInSequence, offsetPed, holdLastFrame)` ctor
  0x5d790c, 0x78 bytes (TASK_PLAY_ANIM: `CTask::operator new(0x78)` 0x3ff32c), vtable 0x8335f0, type 401. TASK_PLAY_ANIM
  (`CRunningScript::PlayAnimScriptCommand` 0x3ff208) passes flags 0x10, +2 looped (loop, or a time with lockF 0), +0x40 / +0x80 /
  +8 locks; the task goes to the ped as a `CEventScriptCommand` (`GivePedScriptedTask` 0x3f41b0) and ends up in the main slot.
  `StartAnim` 0x5d7d00 starts a timer for time >= 0 and blends with `CAnimManager::BlendAnimation`; without the set in memory
  the hierarchy is null and `ProcessPed` 0x5d7a10 ends the task at once. The task's destructor blends the anim out (-4.0).
- Anim sets: `CAnimManager::ms_aAnimBlocks` 0xba7220 (GOT 0x850780), 180 x 0x20 {name[16], loaded +0x10, refs +0x12, ...},
  count `ms_numAnimBlocks` 0xba88a4 (GOT 0x84f4b0); `GetAnimationBlock` 0x4668f0 compares names with strcasecmp.
  REQUEST_ANIMATION (04ED, 0x41d850): `CStreaming::RequestModel(index + 25575, 4)` 0x3949e0 + the script's resource manager;
  HAS_ANIMATION_LOADED (04EE): +0x10 of the set.
- The game has no arm-only "come here": its partial gestures are the gang hand signs (`CTaskComplexPlayHandSignalAnim`, GHANDS
  gsign*) and talk (GANGS prtial_gngtlkA-H); the always-loaded "ped" set has idle_taxi (a full-body hail). CopTraf_Come of the
  POLICE set is the traffic policeman's "come on".

## P. 1.6: aim-walk - the gun task's own stepping (ControlGunMove)

Checked on the player's libGTASA.so (symbols + disassembly with capstone; PLT targets resolved through `.rela.plt`), 17.11.2026.
Checked at start-up by AIM_WORDS in `brain/game/brain.c` (49 instruction words, the GOT slot of the time step and the five animation
names); nothing of it is called when one differs.

| What | Address | Proof / notes |
|---|---|---|
| `CTaskSimpleUseGun::ControlGunMove(CVector2D*)` | 0x5dfc38 | a leaf, 35 instructions. `step = CTimer::ms_fTimeStep (GOT 0x84ce50 -> 0xbdc580) x 0.07 (0x710ae8)`; y first: `task+0x20` moves towards `vec[1]` (`ldr s1,[x1,#4]`) by at most `step`, then `task+0x1c` towards `vec[0]`; `strb #1 -> task+0x12`; returns 1. No check of anything - the caller must hold a real gun task |
| `CTaskSimpleUseGun::ProcessPed(CPed*)` | 0x5dde2c | `ldrb w8,[x19,#0x11]` / `cbz` (0x5ddf84): NOT "in control" this frame -> `+0x13 = 0`, **the move vector zeroed** (`stur xzr,[x19,#0x1c]` 0x5de098), the countdown `+0x54` (set to 0xff by every controlled frame) goes down by one and at 0 the task ends itself; nothing else is done in such a frame. In control: the weapon info is fetched (`+0x48`), the animation started / fired, then `SetMoveAnim` (0x5deae8) - always for a weapon without the "aim with arm" flag (info `+0x18` bit 1), for a pistol only when `+0x12` is set or the ped ducks - and at the very end `+0x11 = 0` (0x5deb18). So "in control" (`ControlGun` 0x5dfb64 sets `+0x11`: `sturb w8,[x23,#-0x17]`, x23 = task+0x28) has to be renewed EVERY frame |
| ... its facing test | 0x5de9a8-0x5dea28 | bearing of the target `atan2f(-dx, dy)` minus the ped's heading (`+0x6c4`), wrapped to +-pi; outside about -2.27 .. +2.01 rad (0x75ed60, 0x75ed5c; 0.70 narrower each side for a dead target) `+0x16 = 1` and there is no aiming this frame (AbortIK instead of AimGun). The task itself never writes the heading to take (`+0x6c8`) except for the pistol-whip (0x5de328) |
| `CTaskSimpleUseGun::SetMoveAnim(CPed*)` | 0x5df684 | gets the five associations 0x31..0x35 (`RpAnimBlendClumpGetAssociation`). Ducking (`ped+0x587` bit 2, 0x5df714): no stepping at all - for commands 2..4 the duck task gets `ForceStopMove`, the vector and `+0x12` are cleared. Not ducking and `+0x12` set: if the last command (`+0x18`) is FIRE (2) and the weapon cannot fire on the move (info `+0x18` bit 5 clear) the length counts as 0; else `len = sqrt(x^2+y^2)`, `sum = |x|+|y|`. `sum < 0.1` (0x713514): Gun_stand is blended in (`BlendAnimation(clump, 0, 0x31, 8.0)`; for an aim-with-arm weapon the idle of his group and `SetMoveState(1)`), the four GunMove associations are stopped, vector cleared. Otherwise (weapon without "aim with arm"): `k = 1 - the blend of Gun_stand` (which this function itself fades out, 8 x step / 50 a frame), `wx = k * x / sum`, `wy = k * y / sum`; **x > 0: anim 0x35 gets blend wx (0x33 zeroed), x < 0: anim 0x33 gets -wx (0x35 zeroed); y < 0: anim 0x32 gets -wy (0x34 zeroed), y > 0: anim 0x34 gets wy (0x32 zeroed)**; each used one gets flag "playing" and speed `len x info+0x3c`. Aim-with-arm weapon: one of the four blended in whole (x > 0.75 -> 0x35, x < -0.75 -> 0x33, else y > 0 -> 0x34, else 0x32). At the end `+0x12 = 0` (0x5df8f4); with the last command AIM (1) and a weapon that cannot aim on the move (bit 4) the aim animation is blended out |
| the animation names by id | 0x88b7c0 (`char *[]`) | index 0 `Walk_civi`, 3 `idle_stance`, ..., **0x31 `Gun_stand`, 0x32 `GunMove_FWD`, 0x33 `GunMove_L`, 0x34 `GunMove_BWD`, 0x35 `GunMove_R`**, 0x36 `Gun_2_Idle` (pointers into .rodata, relocated) |
| `CTaskSimpleUseGun::StartAnim` | 0x5deb50 | command AIM (1) with a non-zero move vector and a weapon without bit 5: the aim animation is not started (he only steps). FIRE (2) and FIREBURST (3) start the fire animation whatever the vector |
| `CTaskSimpleGunControl::ProcessPed(CPed*)` | 0x5e0474 | the game's AI user of the gun task. Every frame: `CPed::SetMoveState(ped, 1)` (0x5e04dc; SetMoveState 0x596cac is `str w1,[x0,#0x550]; ret`), makes / controls the CTaskSimpleUseGun in the attack slot (the same inline code as ControlGun: `+0x11 = 1`, the target, `+0x17` raised to the command), **turns the ped to the target: `ped+0x6c8 = atan2f(-dx, dy)`** (0x5e0acc), and when the target is nearer than sqrt(6) m (with FIREBURST as the last command only for a weapon with bit 5) - also in one aim-only branch that was not decoded further (w27) - and never for a ped whose `+0x586` bit 5 is set ("stay in the same place" by the flag order of gta-reversed, not checked here) runs ControlGunMove inline with the asked vector **(0, +1.0)** (`fmov s1,#1.0` 0x5e0b30 for y, `fmov s2,wzr` 0x5e0d2c for x; stores 0x5e0d30 / 0x5e0d60, `+0x12 = 1` 0x5e0d64) |
| `CTaskManager::SetTask(task = 0, slot, bool)` | 0x64e084 | `cbz x20` 0x64e0a4 -> 0x64e128: the old task of the slot is deleted (vtable +8) and the slot set to 0 (0x64e138) - a main slot can be emptied with it |

The convention, and how it is established:
- **x (`+0x1c`) is to the man's right, y (`+0x20`) to his back, both in his own frame; length 1 is a full step.** y > 0 plays
  GunMove_BWD and y < 0 GunMove_FWD, x > 0 GunMove_R and x < 0 GunMove_L - read from SetMoveAnim and the game's own name table.
  The AI's use fixes the sign independently of the names: facing the target (it has just set his heading to the target's bearing)
  it asks (0, +1) to get AWAY from a target that is too near - +y is backwards.
- The frame is the ped's: the motion is the animations' own root motion, applied along the ped's matrix; nothing in these
  functions reads a world direction. The mod therefore projects the world direction to the next point of his way on his matrix's
  forward (`[ped+0x18]+0x10`, flat, normalised): `y = -(d . fwd)`, `x = d . right`, `right = (fwd.y, -fwd.x)`.
- What the mod does every frame for an aim-walker, mirroring the AI: `ped+0x6c8 = bearing of his man`, `ped+0x550 = 1`,
  `ControlGun(task, ped, his man, AIM or FIREBURST)`, `ControlGunMove(task, {x, y})`. It never asks FIRE (2).

Not verified (no device here; the emulator runs ControlGunMove's real code and records the rest): that the GunMove animations
move a guard whose main task slot is empty (his default task is whatever the game gave a script-made ped); how fast (`info+0x3c`
per weapon); that a guard already crouched by the scripts is un-ducked (a ducking man is not stepped - the mod then walks him
plainly); whether the default task of a script-made ped blends something over Gun_stand. The mod's watch covers the first: a man
whose step is asked and who has not got 0.4 m on in 1.5 s of stepping (only the frames he steps count) gets the plain walk for 6 s.

The standing guard (found here, mended in the same 1.6 - `gun_hold` in `brain/game/brain.c`). Until now `body_gun` called
ControlGun once a look (about ten times a second). By the above the gun task then did its work only in the frames that follow a
look - at 120 frames a second one frame in twelve; in the others ProcessPed returns at once (animations already started keep
playing, but the fire moment is tested against that frame's slice of the animation only, 0x5de44c-0x5de470, so most would be
missed - read from the code, not seen in a game). And nothing turned a standing guard to his man: the gun task aims within about
+-2 rad of his heading and never sets it, while the mod's `face_look` left a guard with his weapon on a man alone. What the code
says the mod has to do, and now does every frame for a guard who holds its gun task with an order (AIM / FIREBURST) at a living man:
- **ControlGun every frame** - exactly what the AI's CTaskSimpleGunControl does (its inline copy at 0x5e09f8-0x5e0a50 runs in every
  ProcessPed).
- **The heading: only `ped+0x6c8` is written.** `CPed::CalculateNewVelocity` 0x597518 reads it (`ldr s8,[x19,#0x6c8]` 0x597564) and
  eases the current heading `+0x6c4` towards it (stores at 0x597594 / 0x597674 / 0x5976a8) - the only place besides
  `CPed::UpdatePosition` and the car line-up utility that has both fields. The AI writes `+0x6c8` alone, so does the mod.
- **No ControlGunMove for a standing man.** SetMoveAnim with `+0x12` clear (0x5df718 `ldrb` / 0x5df720 `cbz` -> 0x5df788) takes
  the length as 0: Gun_stand is blended in, the four GunMove associations stopped, and the stored step cleared (0x5df8f0) - so a
  step left over from an aim-walk is gone in the first standing frame, no drift.
- **A ducking ped (`+0x587` bit 2): per-frame ControlGun is right for him too.** StartAnim (0x5deb50) takes his duck task
  (`GetTaskDuck(1)`, null-checked) and for AIM / FIRE / FIREBURST blends, in the weapon's group, animation **0xe1 when he ducks and
  the weapon info has `+0x19` bit 5** (0x5dece0-0x5dece8 -> 0x5dedc4), else 0xe0 - the crouched fire is the gun task's own
  choice; for a reload 0xe3 instead of 0xe2 the same way (0x5dee64-0x5dee80). SetMoveAnim for a ducking ped only tells the duck
  task `ForceStopMove` (commands 2..4) and clears the step. The AI's gun control has no "ducking" exit before it controls the gun
  task or writes the heading - it only adds `ForceStopMove` when the task has finished (0x5e0c30). Not seen here: the animation
  itself, and whether a weapon of the guards lacks that bit (then he fires with the standing animation while ducking).

Gone from the mod with 1.6 (the facts of sections L and N stay true, the mod no longer uses them): `CTaskComplexGoToPointShooting`
(0x633510, go-and-shoot), `IKChainManager_c::PointArm` / `AbortPointArm` and the mod's own `CWeapon::Fire` for a guard at a sprint;
crash step 28 and `RunFireOff` with them. Crash step 33 = aim-walk (`AimWalkOff` in the settings file).
