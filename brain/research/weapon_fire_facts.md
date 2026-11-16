# Weapon fire facts (CWeapon::Fire / FireInstantHit) for door gunners

Binary: the same `libGTASA.so` as `game_facts.md` (54731968 bytes, sha256 `92b37145...562234f9e`, re-checked). Addresses are offsets from the load base.
Method: capstone disassembly of the functions with PLT stubs and GOT slots resolved through the relocations; class layouts from the DWARF in the same file (`gdb ptype /o`).
Scripts: `scratchpad/wfresearch/{dis,got,callers,words}.py`.

Confidence: **proven** = an instruction at the given address does it; **dwarf** = layout/name only from DWARF; **inferred** = PC knowledge / reasoning, not checked here.

## 1. Functions

| function | address | size | callable directly? |
|---|---|---|---|
| `bool CWeapon::Fire(CEntity* firer, CVector* start, CVector* barrel, CEntity* targetEnt, CVector* targetPos, CVector* altStart)` `_ZN7CWeapon4FireEP7CEntityP7CVectorS3_S1_S3_S3_` | 0x700c64 | 0x830 | yes. Its only callers use the PLT (JUMP_SLOT 0x845578) |
| `bool CWeapon::FireInstantHit(CEntity* firer, CVector* start, CVector* barrel, CEntity* targetEnt, CVector* targetPos, CVector* altStart, bool bCrossHairGun, bool bCreateGunFx)` | 0x701494 | 0x168c | yes |
| `void CWeapon::DoBulletImpact(CEntity* firer, CEntity* hit, CVector* origin, CVector* end, CColPoint*, int)` | 0x705c7c | 0xc0c | yes, but do not call it yourself (see 3) |
| `bool CPed::DoGunFlash(CPed* this, int blendOutDivisor, bool leftHand)` `_ZN4CPed10DoGunFlashEib` | 0x59bcb0 | 0xa8 | yes |
| `void CWeapon::Update(CPed*)` / `void CWeapon::Reload(CPed*)` | 0x707730 / 0x700a2c | 0x4e8 / 0x60 | yes |
| `CPed::GetBonePosition(RwV3d&, unsigned bone, bool)` / `CPed::GetTransformedBonePosition` | 0x59aee4 / 0x598670 | | symbols only, not analysed |
| `CTimer::m_snTimeInMilliseconds` | 0xbdc558 (uint32) | | proven in game_facts.md |

All parameters are pointers; the first parameter is `this` (CWeapon*). Return value in w0 (bool).

## 2. CWeapon layout (0x20 bytes, slot = ped + 0x730 + slot*0x20)

| field | off | evidence | conf. |
|---|---|---|---|
| m_eWeaponType | +0x0 | `Fire` @0x700c9c `ldr w0, [x19]` -> GetWeaponInfo | proven |
| m_eState (0 ready, 1 firing, 2 reloading, 3 out of ammo, 4 melee contact) | +0x4 | `Fire` @0x700dc4 `ldr w8, [x19, #4]` + `cmp w8, #1; b.hi` (refuses state > 1); @0x701348 writes 1; @0x701380 writes 2; `Update` @0x7078c0 writes 0 or 3 | proven |
| m_nAmmoInClip | +0x8 | `Fire` @0x700dd0 `ldr w8, [x19, #8]`; decremented @0x7012e0..0x7012ec | proven |
| m_nAmmoTotal | +0xc | `Fire` @0x700ddc `ldr w8, [x19, #0xc]`; decremented @0x701334..0x70133c | proven |
| m_nTimer (next shot time, ms) | +0x10 | written by `Fire` @0x7013a0 / @0x7013f4 / @0x701428; read by `Update` @0x707898 | proven |
| m_bFirstPersonWeaponModeSelected | +0x14 | `Fire` @0x700d38 `ldrb w8, [x19, #0x14]`: when set, Fire MOVES *start sideways by heading (writes into the caller's vector) | proven (offset), dwarf (name) |
| m_bDontPlaceInHand | +0x15 | | dwarf |
| m_pWeaponFxSys | +0x18 | `Update` @0x707be4 | proven |

CWeaponInfo (0x70, `GetWeaponInfo(type, skill)` @0x709ba8): +0 fire type, +8 m_fWeaponRange, +0x20 int16 m_nAmmo (clip size, `Fire` @0x700df4 `ldrsh w8, [x0, #0x20]`), +0x24 m_vecFireOffset (muzzle offset in hand space, used by the drive-by task @0x5e918c), +0x38 m_fAccuracy (@0x701588), +0x40/+0x44 anim loop start/end (fire rate @0x70140c). Proven at those addresses, names DWARF.

## 3. CWeapon::Fire @0x700c64, step by step (proven)

| step | addresses | behaviour |
|---|---|---|
| args | 0x700c90..0x700cb8 | x19 this, x21 firer, x26 start, x24 barrel, x22 targetEnt, x23 targetPos, x25 altStart |
| weapon info | 0x700cbc..0x700cf4 | firer type 3 (ped): info for the ped's skill (`CPed::GetWeaponSkill`); x28 = firer if ped, else 0 |
| start == NULL | 0x700cfc..0x700d34 | start = barrel = firer matrix * (0,0,0.6) (local on stack). **firer is dereferenced without a NULL check** (0x700d00) |
| state check | 0x700dc4..0x700dcc | `state > 1` -> return false (reloading, out of ammo) |
| clip | 0x700dd0..0x700e04 | clip <= 0: total < 1 -> return false; else clip = min(total, info.m_nAmmo) (instant refill, no animation) |
| dispatch | 0x700e08..0x700e2c | jump table at 0x765348 on type-16 (types 16..43); types < 16 or > 43 skip the shot but still run the bookkeeping below |
| types 22-24, 28-33, 38 (pistols, SMGs, rifles, minigun) | 0x700e30 -> 0x700e3c..0x700e64 | ped with `m_nPedType == 0` (player 1) goes to the camera/first-person path (`TheCamera`+0x80c mode 0x22/0x2d -> FireM16_1stPerson @0x700f94); every other ped / non-ped: `FireInstantHit(this, firer, start, barrel, targetEnt, targetPos, altStart, bCrossHairGun=0, bCreateGunFx=1)` |
| after instant hit | 0x700e68..0x700ea0 | if ped `bInVehicle` (+0x585 bit0): `pedIntelligence(+0x538)+8 -> CTaskManager::GetActiveTask`; if it is type 1022 (GangDriveBy, `cmp w0, #0x3fe` @0x700e98) the fire-rate delay is 0 |
| types 25-27 (shotguns) | 0x700ed4..0x700efc | FireInstantHit always, same flags |
| type 34 sniper | 0x7010b4 | player in camera mode 7 -> FireSniper, else FireInstantHit with altStart = NULL |
| 16-18, 39 thrown; 35/36 rockets; 37/41/42 flame/spray; 40 detonator; 43 camera | jump table | FireProjectile / FireAreaEffect / UseDetonator / TakePhotograph |
| ped bookkeeping | 0x701158..0x7011a8 | firer is a ped and type != 43: sets `bFiringWeapon` (ped+0x584 `orr #0x10000` @0x701190); **plays the gun sound**: `CAEPedWeaponAudioEntity::AddAudioEvent(ped+0x470, 0x91)` @0x7011a8 |
| player only | 0x7011ac..0x7012cc | CPed::Say / CStats only when the firer IsPlayer |
| ammo | 0x7012d0..0x70133c | skipped while cheat `CCheat::m_aCheatsActive[0x50]` is on. clip--; total-- only if `total >= 1` and (`total < 25000` (`mov w9, #0x61a8` @0x7012f4) or player stats). **NPC with total >= 25000 never loses total ammo** |
| state/timer | 0x701340..0x701428 | state = 1. clip now 0: total 0 -> keep state 1, return true; else state = 2 (reloading), timer = now + GetWeaponReloadTime (/4 for a player with a perk). clip > 0: timer = now (drive-by) or now + (animLoopEnd - animLoopStart)*900 (0x70140c..0x701424) |
| return | 0x701430..0x701448 | true when fired (also always true for types 0 and 5); false when refused or the projectile/sniper/m16/photo sub-call failed |

**Fire does NOT read m_nTimer**: no rate limit inside. The callers (tasks) wait for it. The mod must rate-limit itself, e.g. fire only when `CTimer::m_snTimeInMilliseconds >= weapon.m_nTimer` (Fire writes it, proven) or with its own interval.

## 4. CWeapon::FireInstantHit @0x701494 (proven unless marked)

Arguments saved @0x7014c4..0x7014e0 (w7 = bCrossHairGun), 9th argument bCreateGunFx read from the stack @0x701610 `ldrb w21, [x29, #0x10]`.

**How the bullet direction is chosen** (the critical part for door gunners):

| condition | addresses | shot line |
|---|---|---|
| firer is a ped and `CPedIntelligence::GetTaskUseGun()` (@0x7015b8) returns a task with `m_bSkipAim` (+0x16) set | 0x701618..0x7016b8 | from the right-hand bone along the hand (ignores targetPos) |
| ped, (targetEnt or targetPos given) and (**CPedIK.m_flags bit0, ped+0x698** or bCrossHairGun) | 0x7016bc..0x7016d0 `ldr w8, [x22, #0x698]; tbnz w8, #0` | toward *targetPos (0x7019e4 -> 0x70268c); if targetPos is NULL: target entity position / bone 3 (`GetBonePosition` @0x702b04) / gas tank of the player's car |
| otherwise (ped not "aiming") | 0x70174c / 0x701894..0x7019d4 | **straight along the ped's forward vector** (matrix +0x10) for m_fWeaponRange, optional `DoDoomAiming`; targetPos ignored |

The game's own tasks set the IK bit just before `Fire`: `CTaskSimpleUseGun::FireGun` @0x5dfeac `orr w8, w8, #1; str w8, [x19, #0x698]` (cleared @0x5dff50 when not facing), `CTaskSimpleGangDriveBy::FireGun` @0x5e957c..0x5e9584. ped+0x698 = CPedIK.m_flags (DWARF: CPedIK at +0x678, m_flags +0x20).

Target path details: direction = normalize(targetPos - start); end = start + dir * m_fWeaponRange * mult (mult 3 when targetEnt is in a non-bike vehicle, else 1; 0x7026f4..0x7027dc), so the bullet continues past the target to weapon range. Spread: s8 = (100 - ped.m_nShootingAccuracy(+0x8de, uint8, @0x70157c)) / info.m_fAccuracy (0x701580..0x701598, 100.0 at 0x738f6c); random offset added when s8 > 0 (0x7028a4..0x70298c). **ped+0x8de = 100 -> no spread.**

LOS ignore entity (`CWorld::pIgnoreEntity` GOT 0x84b180): the vehicle the ped is in (bInVehicle + m_pMyVehicle) or the vehicle it is attached to (`CPhysical.m_pAttachToEntity` **+0x150**, type 2), unless that vehicle has `bVehicleCanBeTargetted` (+0x56d bit 2) set (0x702a80..0x702ac4). Then `CWorld::ProcessLineOfSight` (buildings, cars, peds, objects, dummies on; shoot-through on) @0x7019d4 / via 0x701834..0x701ba4.

Calls made, in order (all proven by address):

| what | address | condition |
|---|---|---|
| `CBirds::HandleGunShot`, `CShadows::GunShotSetsOilOnFire` | 0x701994 / 0x7019a0 (and other paths) | always |
| `CWorld::ProcessLineOfSight` | 0x7019d4 / 0x701ba4 / 0x702538 | always |
| `CEventGunShot` + `CEventGroup::Add(GetEventGlobalGroup())` | 0x701be0 / 0x701bf0 | always (AI hears the shot) |
| `CEventGunShotWhizzedBy` + Add | 0x701c10 / 0x701c20 | always |
| `CInterestingEvents::Add(0x16, firer)` | 0x701c34 | always |
| `CPointLights::AddLight` (muzzle light) | 0x701d1c | bCreateGunFx and type 22..32, 34 or 38 (jump table 0x7653b8; 33, 35-37 get no fx; for 30/31/38 the fx is skipped every other shot when the fire interval is < 50 ms, counter byte 0xd2b068) |
| `Fx_c::TriggerGunshot(g_fx, firer, barrel, dir, flashParticle)` | 0x701d58 | same; flashParticle = (ped+0x658 m_pWeaponFlashFrame == NULL). Inside (0x436594): **nothing if the camera is more than 25 m away** (625.0 at 0x7442f8) or firer has no RwObject |
| `CWeapon::AddGunshell` | 0x701dd8 | same |
| water splash `Fx_c::TriggerBulletSplash` + `CAudioEngine::ReportBulletHit` | 0x701ea4 / 0x701ec0 | bullet line crosses water |
| `CWeapon::DoBulletImpact(this, firer, hitEnt, barrel, end, colPoint, 0)` | 0x701f1c | always for non-shotguns (hit or miss); shotguns use pellets (0x701f80, 0x7020c0, 0x702138) |
| `CWorld::ResetLineTestOptions`, event destructors | 0x7021e4..0x7021f4 | always |

DoBulletImpact @0x705c7c: `CBulletTraces::AddTrace(origin, end, weaponType, firer)` @0x705d40 (miss) / @0x705db4 (hit) **always**; the wrapper @0x6e612c skips the trace only when the firer is the player (or his car) in some aiming camera modes while slow. For NPCs it adds a random 2-5 m streak along the line, 300 ms (`AddTrace(.., 0.01, 0x12c, 0x46)` @0x6e6314). Damage: `GenerateDamageEvent` @0x7063e0 (ped), `CVehicle::InflictDamage` @0x7064a4, `CObject::ObjectDamage` @0x706728, `CGlass::WasGlassHitByBullet`, tyre bursts, `Fx_c::AddBulletImpact` / `AddBlood`, `CAudioEngine::ReportBulletHit` (impact sounds). `CCrime::ReportCrime` only for a player firer (0x705d10..0x705d24).

Sound: the shot sound is NOT in FireInstantHit; it is `Fire` @0x7011a8. `CAEPedWeaponAudioEntity::AddAudioEvent` @0x4798b8 needs `ped+0x528` (m_bInitialised) and `ped+0x530` (m_pParentPed) set (true for every created ped, inferred) and plays the sound of the ped's **current** slot (`ldrsb x10, [x2, #0x8dc]` @0x4798e0), not of the CWeapon passed.

## 5. Gun flash on the weapon model (proven)

`CPed::DoGunFlash(ped, divisor, leftHand)` @0x59bcb0: returns 0 unless `ped+0x650` (m_pWeaponClump) and `ped+0x658` (m_pWeaponFlashFrame) are non-NULL (= the ped holds a gun model). Sets m_nGunFlashBlendAmount = `CPed::m_sGunFlashBlendStart` (0x88bdf8) at +0x670 (right) / +0x674 (left) and blend-out rate = start/divisor at +0x672/+0x676, then rotates the flash frame randomly. Fire never calls it: the tasks do, right after Fire: `CTaskSimpleUseGun::FireGun` @0x5dff18..0x5dff38 (only when the weapon state is now 1, divisor 0xfa = 250), `CTaskSimpleGangDriveBy::FireGun` @0x5e9628..0x5e9634 (250, right hand). The flash is drawn by `CVisibilityPlugins::RenderWeaponPedsForPC` (SetGunFlashAlpha).

So "visible" = model flash (DoGunFlash, any distance) + point light + gunshot particles (only < 25 m from the camera) + tracer streak + impact fx + sound from Fire.

## 6. Other entries considered

| entry | verdict |
|---|---|
| `CTaskSimpleGangDriveBy::FireGun` @0x5e9174 | reads `ped->m_pMyVehicle` (+0x708) without a NULL check (@0x5e91e0..0x5e91f4) and the task's own fields: **crash for an attached ped that is not in a vehicle**. Use only as the model: muzzle = hand bone * info.m_vecFireOffset, set IK bit, `Fire(slot, ped, &muzzle, &muzzle, target, &targetPos or NULL, &alt)`, `DoGunFlash(ped, 250, 0)` |
| `CWeapon::FireFromCar(CVehicle*, bool, bool)` @0x7042d4 / `FireInstantHitFromCar` @0x704418 | the shooter is `vehicle->pDriver` (+0x5a0, @0x704318), player drive-by (`CVehicle::DoDriveByShootings`). Not for passengers / attached peds |
| `FireOneInstantHitRound(CVector*, CVector*, int)` @0x707c9c | heli/vehicle guns and a script opcode: light, LOS, trace, damage with no owner; no ped sound, no gunflash |
| calling `FireInstantHit` directly with bCrossHairGun = 1 | aims at targetPos without the IK bit (0x7016d0), but skips Fire's sound, ammo, state, timer and bFiringWeapon |
| `DoBulletImpact` directly | only trace + damage; no flash, light, sound, AI events |

## 7. Pitfalls

1. **firer must be non-NULL** (Fire @0x700d00 / 0x701158, FireInstantHit @0x70156c dereference it), and **start and barrel must both be non-NULL** when start is given (FireInstantHit @0x701530 / 0x701548 dereference both). Pass the same muzzle vector twice.
2. Without the IK bit (ped+0x698 bit0) the shot goes along the ped's facing, not to targetPos (0x7016c8). Set it before Fire; restore the old value after (the game's tasks overwrite it every shot anyway).
3. If the gunner has a CTaskSimpleUseGun with m_bSkipAim set, the hand-bone path wins and targetPos is ignored (0x701618..0x701620).
4. Player-only paths (camera, FireM16_1stPerson, FireSniper, Say, stats, crime, Pad) are gated by `m_nPedType == 0` / `IsPlayer` / `FindPlayerPed() == firer`. With an NPC firer the remaining global reads are `TheCamera` (always valid) and `FindPlayerPed` comparisons: safe.
5. Dereferenced for a ped firer: `m_pPedIntelligence` (+0x538, GetTaskUseGun, and GetActiveTask when bInVehicle), `m_pRwObject`/matrix (allocates a matrix if missing), `m_pPlayerData` (+0x540, NULL-checked @0x70158c / 0x7027f0). Vehicle fields only after NULL checks (+0x708 only when bInVehicle; +0x150 checked).
6. Reload stall: state 2 blocks Fire until `CWeapon::Update` (run from `CCivilianPed/CCopPed/CEmergencyPed/CPlayerPed::ProcessControl`, and the drive-by task) sees the timer expire; for weapons with the reload-anim flag (info.m_nFlags bit 12) Update waits for the reload animation (0x7078d8..0x707930). Avoid it: before each shot set clip >= 2 (+0x8) and total >= 25000 (+0xc, then never decremented for NPCs), and if state (+0x4) is 2 or 3 set it to 0. Whether ProcessControl/Update runs for 06A7-attached peds was not checked (inferred yes).
7. Own helicopter: the attached-to vehicle is ignored by the LOS only when its `bVehicleCanBeTargetted` (+0x56d bit 2) is clear; otherwise the gunner can hit his own heli.
8. `m_bFirstPersonWeaponModeSelected` (+0x14) set -> Fire modifies *start. Keep it 0 (it is 0 for NPCs, inferred).
9. Sound uses the ped's current slot: fire the CWeapon at `ped + 0x730 + cur*0x20`, cur = `*(int8*)(ped+0x8dc)`.
10. Fire has no rate limit; also each call creates AI events (gunshot, whizzed-by) that make nearby peds react/flee.
11. Instant-hit types only (22-34, 38). Other types go to projectiles/area effects.
12. Run on the game thread only (it uses `CWorld::pIgnoreEntity` and line-test globals; `ResetLineTestOptions` at the end).

## 8. Recommended call

```c
typedef struct { float x, y, z; } CVector;
typedef int  (*fire_t)(void *weapon, void *firer, CVector *start, CVector *barrel,
                       void *targetEnt, CVector *targetPos, CVector *altStart);   /* base + 0x700c64, returns bool in w0 */
typedef int  (*gunflash_t)(void *ped, int divisor, int leftHand);                 /* base + 0x59bcb0 */

/* game thread; ped alive; weapon type in 22..34 or 38; muzzle and target already line-checked by the mod */
static int gunner_fire(uintptr_t base, char *ped, CVector *muzzle, CVector *target)
{
    char *w = ped + 0x730 + 0x20 * (int)*(signed char *)(ped + 0x8dc);   /* current slot */
    unsigned now = *(unsigned *)(base + 0xbdc558);
    if (now < *(unsigned *)(w + 0x10)) return 0;                        /* own rate limit (Fire has none) */
    int *st = (int *)(w + 4), *clip = (int *)(w + 8), *tot = (int *)(w + 0xc);
    if (*st > 1) *st = 0;                                               /* never wait for a reload */
    if (*clip < 2) *clip = 2;  if (*tot < 25000) *tot = 30000;          /* NPC infinite ammo threshold 0x7012f4 */
    *(unsigned char *)(ped + 0x8de) = 100;                              /* optional: no spread */
    unsigned *ik = (unsigned *)(ped + 0x698), old = *ik;
    *ik = old | 1;                                                      /* aim at targetPos (0x7016c8) */
    CVector s = *muzzle, b = *muzzle;                                   /* Fire may write into start */
    int ok = ((fire_t)(base + 0x700c64))(w, ped, &s, &b, 0, target, 0);
    *ik = old;
    if (ok && *st == 1) ((gunflash_t)(base + 0x59bcb0))(ped, 250, 0);  /* model flash, as CTaskSimpleUseGun does */
    return ok;
}
```

`targetEnt = NULL` avoids the 3x range rule and the target-is-player spread; pass the victim instead only if needed. A muzzle position from the hand bone: `CPed::GetBonePosition(ped, &v, bone, 0)` @0x59aee4 (right hand bone id 24/25 is PC knowledge, inferred), or the start point of the mod's own line check.

## 9. Words to verify at load (all checked against the file)

For `gen_words.py`: `FUNCS += [('WEAPON_FIRE', 0x700c64, 4), ('PED_GUNFLASH', 0x59bcb0, 4)]` (4 prologue words each, no adrp/branch: PIC) and these ANCHORS:

```c
    {0x700c64, 0xd10243ffU},   /* WEAPON_FIRE + 0      sub sp, sp, #0x90 */
    {0x700c68, 0x6d0223e9U},   /* WEAPON_FIRE + 4      stp d9, d8, [sp, #0x20] */
    {0x700c6c, 0xa9036ffcU},   /* WEAPON_FIRE + 8      stp x28, x27, [sp, #0x30] */
    {0x700c70, 0xa90467faU},   /* WEAPON_FIRE + 12     stp x26, x25, [sp, #0x40] */
    {0x700dc4, 0xb9400668U},   /* Fire: ldr w8, [x19, #4]      weapon state +4 */
    {0x700dd0, 0xb9400a68U},   /* Fire: ldr w8, [x19, #8]      ammo in clip +8 */
    {0x700e64, 0x9400018cU},   /* Fire: bl 0x701494            FireInstantHit (NPC instant-hit path) */
    {0x7011a0, 0x9111c2a0U},   /* Fire: add x0, x21, #0x470    ped weapon audio entity (shot sound) */
    {0x7012f4, 0x528c3509U},   /* Fire: mov w9, #0x61a8        total ammo >= 25000 not decremented */
    {0x7013a0, 0xb9001268U},   /* Fire: str w8, [x19, #0x10]   weapon timer +0x10 */
    {0x701494, 0xfc160feeU},   /* FireInstantHit + 0  str d14, [sp, #-0xa0]! */
    {0x70157c, 0x3d637a60U},   /* FireInstantHit: ldr b0, [x19, #0x8de]  ped shooting accuracy */
    {0x7016c8, 0xb9469ac8U},   /* FireInstantHit: ldr w8, [x22, #0x698]  CPedIK flags ... */
    {0x7016cc, 0x370018c8U},   /* ... tbnz w8, #0, #0x7019e4  bit0 = shoot at targetPos */
    {0x702a9c, 0xf940aac9U},   /* FireInstantHit: ldr x9, [x22, #0x150]  m_pAttachToEntity (LOS ignore) */
    {0x59bcb0, 0xf81e0ff3U},   /* PED_GUNFLASH + 0    str x19, [sp, #-0x20]! */
    {0x59bcb4, 0xa9017bfdU},   /* PED_GUNFLASH + 4 */
    {0x59bcb8, 0x910043fdU},   /* PED_GUNFLASH + 8 */
    {0x59bcbc, 0xaa0003f3U},   /* PED_GUNFLASH + 12 */
    {0x59bcc8, 0xf9432e68U},   /* DoGunFlash: ldr x8, [x19, #0x658]  m_pWeaponFlashFrame */
```

Minimum set if only ~10 are wanted: 0x700c64, 0x700c68, 0x700dc4, 0x700dd0, 0x700e64, 0x7011a0, 0x7013a0, 0x7016c8, 0x7016cc, 0x59bcb0, 0x59bcc8, 0x70157c.
