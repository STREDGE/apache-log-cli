"""Helicover 1.4.1: the second four of the ground team (Helicover_Team2.csa).

The ground worker drops and recalls the first four (the commander - a soldier, 287 - and three agents in black). This worker
mirrors them with four more agents in black (164 / 165), so the detail on the ground is eight, as the player asked; the
brain gives all eight their posts (roles: the second bodyguard, the second man of the advance pair, the second man of the
counter-assault pair and the marksman) and the second squad worker (Helicover_Squad2) carries them out.

  - The first four are on foot with CJ (SQ_ROPE = 1 and at least one of them alive): the four come down beside them
    (created behind the first living guard, out of CJ's way), armed by their role - MP5, M4, AK, sniper rifle - with the same
    health, armour and loyalty as the first four, and published in GROUND_PUB2.
  - The first four are gone (recalled up the rope, stood down, the helicopter left): the four put their weapons away and walk
    off; each one is deleted the moment he is off the screen (never in view, never handed to the game armed).
  - A dead one stays dead (his slot is cleared after 10 s so the brain forgets him).
Registers: 0 CJ, 1 first living guard of the first four, 2-5 the four, 6 scratch, 7 the man being set up, 8-12 scratch,
13 now, 14-17 death times, 18 state (0 none, 1 on the ground, 2 leaving).
"""
from asm_v25 import *
import build_v25 as b
s=Script();a=s.add
MODELS=[165,164,165,164]            # agents in black
WEAPONS=[(29,353),(31,356),(30,355),(34,358)]   # by role: second bodyguard MP5, Bravo 2 M4, Charlie 2 AK, Delta sniper rifle
SPOTS=[(-1.5,-2.0),(1.5,-2.0),(-1.5,-3.5),(1.5,-3.5)]
def alive(var,fail):s.check(0x056d,[V(var)],fail);s.check(0x8118,[V(var)],fail)

s.label('INIT');a(0)
for i in range(4):s.set(b.GROUND_PUB2+i,-1);a(6,V(2+i),I(-1));a(6,V(14+i),I(0))
s.set(b.TEAM2_STATE,0);a(6,V(18),I(0))
s.label('LOOP');a(1,I(250));a(0x01bd,V(13))
s.check(0x0256,[I(0)],'LOOP')
# are the first four on foot with CJ?
a(6,V(1),I(-1));s.get(6,b.SQ_ROPE);s.eq(6,1,'MAIN_GONE')
for i in range(4):
 nx='MAIN_NEXT_%d'%i;s.get(8,b.GROUND_PUB+i);alive(8,nx);a(0x0085,V(1),V(8));s.go('MAIN_HERE');s.label(nx)
s.label('MAIN_GONE');s.eq(18,1,'LOOP');s.go('LEAVE')
s.label('MAIN_HERE');s.eq(18,0,'KEEP');s.go('SPAWN')
# ---- on the ground: a dead man's slot is cleared 10 s after he fell
s.label('KEEP')
for i in range(4):
 var=2+i;nx='KEEP_NEXT_%d'%i;live='KEEP_LIVE_%d'%i
 s.check(0x056d,[V(var)],nx);s.check(0x0118,[V(var)],live)          # (check jumps when the condition is false)
 s.check(0x0039,[V(14+i),I(0)],'KEEP_OLD_%d'%i);a(0x0085,V(14+i),V(13));s.go(nx)
 s.label(live);a(6,V(14+i),I(0));s.go(nx)
 s.label('KEEP_OLD_%d'%i);a(0x0085,V(8),V(13));a(0x0062,V(8),V(14+i));s.check(0x0019,[V(8),I(10000)],nx);s.set(b.GROUND_PUB2+i,-1)
 s.label(nx)
# 1.5.4 (fifth log: two of the second four stood 57 s on a slope, 37 and 58 m from their posts, and the catch-up by footsteps
# did not get them off it): a man 45 m or more from CJ for 40 s who is not on the screen is deleted and a new one comes in
# where the screen does not show (14 m round the first living guard, like the second four when the helicopter has gone)
for i in range(4):
 var=2+i;nx='LAG_NEXT_%d'%i;clr='LAG_CLR_%d'%i;run='LAG_RUN_%d'%i
 alive(var,nx)
 a(0x00a0,V(0),V(10),V(11),V(6));a(0x00a0,V(var),V(8),V(9),V(6));a(0x0509,V(10),V(11),V(8),V(9),V(12));s.check(0x0021,[V(12),F(45)],clr)
 s.get(9,b.TEAM2_LAG+i);s.eq(9,0,run);a(0xddc,I(b.TEAM2_LAG+i),V(13));s.go(nx)
 s.label(run);a(0x0085,V(10),V(13));a(0x0062,V(10),V(9));s.check(0x0019,[V(10),I(40000)],nx)
 s.check(0x82cb,[V(var)],nx)                                          # (on the screen: wait until nobody sees him)
 a(0x009b,V(var));a(6,V(var),I(-1));s.set(b.GROUND_PUB2+i,-1);s.set(b.TEAM2_LAG+i,0);a(6,V(14+i),I(0))
 a(0x0247,I(MODELS[i]));a(0x0247,I(WEAPONS[i][1]));a(0x038b);a(1,I(0));s.check(0x0248,[I(MODELS[i])],nx);s.check(0x0248,[I(WEAPONS[i][1])],nx)
 s.check(0x056d,[V(1)],nx)
 for n_,(ox,oy) in enumerate([(-14.,-14.),(14.,-14.),(-14.,14.),(14.,14.)]):
  cand='LAG_CAND_%d_%d'%(i,n_);ok='LAG_OK_%d'%i
  a(0x00a0,V(1),V(10),V(11),V(12));a(0x000b,V(10),F(ox));a(0x000b,V(11),F(oy));a(0x000b,V(12),F(30));a(0x02ce,V(10),V(11),V(12),V(12))
  if n_<3:s.check(0x80c2,[V(10),V(11),V(12),F(3.0)],cand);s.go(ok);s.label(cand)
 s.label('LAG_OK_%d'%i);a(0x0172,V(1),V(9))
 a(0x0087,V(8),V(10));a(0x000b,V(8),F(SPOTS[i][0]));a(0x0087,V(6),V(11));a(0x000b,V(6),F(SPOTS[i][1]))
 a(0x009a,I(8),I(MODELS[i]),V(8),V(6),V(12),V(var));s.check(0x056d,[V(var)],nx)
 a(0x0173,V(var),V(9));a(0x0085,V(7),V(var));s.call('SETUP')
 wpn,_=WEAPONS[i];a(0x01b2,V(var),I(wpn),I(30000));a(0x01b9,V(var),I(wpn));a(0x0223,V(var),I(250));a(0x035f,V(var),I(100))
 a(0xddc,I(b.GROUND_PUB2+i),V(var))
 a(0x0249,I(MODELS[i]));a(0x0249,I(WEAPONS[i][1]));s.go(nx)
 s.label(clr);s.set(b.TEAM2_LAG+i,0)
 s.label(nx)
s.go('LOOP')
# ---- come down beside the first four
s.label('SPAWN')
for m in sorted(set(MODELS))+[w for _,w in WEAPONS]:a(0x0247,I(m))
a(0x038b);a(1,I(0))
for m in sorted(set(MODELS))+[w for _,w in WEAPONS]:s.check(0x0248,[I(m)],'LOOP')
alive(1,'LOOP')
# 1.5: down the ropes, like the first four (the player: "the second lot appears out of nowhere"). While the helicopter still
# hangs over the drop (within 25 s of the first four going down, standing still, 6-45 m above the guard) the four are created
# as rope men under it (0503, the game's own rope descent) 3 s after the first four, when those are clear of the ropes.
# Otherwise (the helicopter has gone): they are put where the screen does not show - the first of four spots 14 m round
# the guard that is not on the screen - and run in from there.
s.get(8,b.DEPLOY_T0);a(0x0085,V(9),V(13));a(0x0062,V(9),V(8));s.check(0x8019,[V(9),I(25000)],'SPAWN_GROUND')
s.get(6,b.PUB+1);s.check(0x056e,[V(6)],'SPAWN_GROUND');a(0x02e3,V(6),V(10));s.check(0x0023,[F(2.0),V(10)],'SPAWN_GROUND')
a(0x00aa,V(6),V(10),V(11),V(12));a(0x00a0,V(1),V(8),V(9),V(10));a(0x0063,V(12),V(10));s.check(0x0021,[V(12),F(6)],'SPAWN_GROUND');s.check(0x0023,[F(45),V(12)],'SPAWN_GROUND')
s.get(8,b.DEPLOY_T0);a(0x0085,V(9),V(13));a(0x0062,V(9),V(8));s.check(0x0019,[V(9),I(3000)],'LOOP')      # (not yet: the first four are still on the ropes)
for i,(x,y) in enumerate([(-1.5,0.0),(1.5,0.0),(-1.5,-2.4),(1.5,-2.4)]):
 var=2+i;nx='ROPE_NEXT_%d'%i
 a(0x0407,V(6),F(x),F(y),F(-1),V(10),V(11),V(12));a(0x0503,I(8),I(MODELS[i]),V(10),V(11),V(12),V(var));s.check(0x056d,[V(var)],nx)
 a(0x0085,V(7),V(var));s.call('SETUP')
 wpn,_=WEAPONS[i];a(0x01b2,V(var),I(wpn),I(30000));a(0x01b9,V(var),I(wpn));a(0x0223,V(var),I(250));a(0x035f,V(var),I(100))
 a(0xddc,I(b.GROUND_PUB2+i),V(var));a(6,V(14+i),I(0))
 s.label(nx)
s.go('SPAWN_DONE')
s.label('SPAWN_GROUND')
for n_,(ox,oy) in enumerate([(-14.,-14.),(14.,-14.),(-14.,14.),(14.,14.)]):
 a(0x00a0,V(1),V(10),V(11),V(12));a(0x000b,V(10),F(ox));a(0x000b,V(11),F(oy));a(0x000b,V(12),F(30));a(0x02ce,V(10),V(11),V(12),V(12))
 if n_<3:s.check(0x80c2,[V(10),V(11),V(12),F(3.0)],'CAND_NEXT_%d'%n_);s.go('SPAWN_AT_OK');s.label('CAND_NEXT_%d'%n_)   # (on the screen: the next spot)
s.label('SPAWN_AT_OK');a(0x0172,V(1),V(9))
for i,(x,y) in enumerate(SPOTS):
 var=2+i;nx='SPAWN_NEXT_%d'%i
 a(0x0087,V(8),V(10));a(0x000b,V(8),F(x));a(0x0087,V(6),V(11));a(0x000b,V(6),F(y))
 a(0x009a,I(8),I(MODELS[i]),V(8),V(6),V(12),V(var));s.check(0x056d,[V(var)],nx)
 a(0x0173,V(var),V(9));a(0x0085,V(7),V(var));s.call('SETUP')
 wpn,_=WEAPONS[i];a(0x01b2,V(var),I(wpn),I(30000));a(0x01b9,V(var),I(wpn));a(0x0223,V(var),I(250));a(0x035f,V(var),I(100))
 a(0xddc,I(b.GROUND_PUB2+i),V(var));a(6,V(14+i),I(0))
 s.label(nx)
s.label('SPAWN_DONE')
for m in sorted(set(MODELS))+[w for _,w in WEAPONS]:a(0x0249,I(m))
a(6,V(18),I(1));s.set(b.TEAM2_STATE,1);s.go('LOOP')
# SETUP: V7 = a new man: mine, friendly to everybody, accurate, brave (the same as the first four: Ground's GSETUP)
s.label('SETUP');a(0x01c5,V(7));a(0x08af,V(7),I(250));a(0x02e2,V(7),I(100));a(0x02ab,V(7),I(0),I(0),I(0),I(1),I(0));
for typ in range(32):a(0x077a,V(7),I(2),I(typ))
a(0x077a,V(7),I(0),I(0));a(0x077a,V(7),I(0),I(8));b.brave(s,7,'SETUP_BRAVE');s.ret()
# ---- the first four are gone: weapons away, walk off, deleted out of view
s.label('LEAVE');a(6,V(18),I(2));s.set(b.TEAM2_STATE,2)
for i in range(4):s.set(b.GROUND_PUB2+i,-1)
s.get(0,b.PUB)
for i in range(4):
 var=2+i;nx='LEAVE_NEXT_%d'%i
 s.check(0x056d,[V(var)],nx);s.check(0x8118,[V(var)],'LEAVE_DEL_%d'%i)
 a(0x048f,V(var));a(0x00a0,V(var),V(10),V(11),V(12))
 s.check(0x056d,[V(0)],'LEAVE_WALK_%d'%i);a(0x00a0,V(0),V(8),V(9),V(6));a(0x0063,V(10),V(8));a(0x0063,V(11),V(9))   # away from CJ
 a(0x0013,V(10),F(4));a(0x0013,V(11),F(4));a(0x005b,V(10),V(8));a(0x005b,V(11),V(9))
 s.label('LEAVE_WALK_%d'%i);a(0x05d3,V(var),V(10),V(11),V(12),I(4),I(30000));s.go(nx)
 s.label('LEAVE_DEL_%d'%i);a(0x009b,V(var));a(6,V(var),I(-1))
 s.label(nx)
s.label('GONE_LOOP');a(1,I(500));a(6,V(6),I(0))
for i in range(4):
 var=2+i;nx='GONE_NEXT_%d'%i
 s.check(0x056d,[V(var)],nx);s.check(0x82cb,[V(var)],'GONE_SEEN_%d'%i);a(0x009b,V(var));a(6,V(var),I(-1));s.go(nx)   # out of view: gone
 s.label('GONE_SEEN_%d'%i);a(6,V(6),I(1))                                                                         # still in view: he walks on
 s.label(nx)
s.eq(6,0,'GONE_LOOP')
for i in range(4):a(6,V(2+i),I(-1))
a(6,V(18),I(0));s.set(b.TEAM2_STATE,0);s.go('LOOP')

if __name__=='__main__':
 OUT=b.OUT
 report=s.build('Helicover_Team2','csa');print(report)
 with (OUT/'validation.txt').open('a') as validation:validation.write(report+'\n')
