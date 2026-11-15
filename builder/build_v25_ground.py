"""Experimental SWAT rope insertion worker for Helicover v15.
Experimental scripted reverse-animation ascent; gameplay is not tested on Android.
"""
from asm_v25 import *
from msg_v42 import say
GROUND_TEXTS={'RGDEP': '~b~PILOT:~w~ team going down the ropes.', 'RGDONE': '~g~SQUAD:~w~ team back aboard.', 'RGFAIL': '~r~HELICOVER:~w~ could not load the team.', 'RGHOLD': '~y~PILOT:~w~ need a steady hover first.', 'RGHIGH': '~y~PILOT:~w~ wrong height for ropes. Try open ground.', 'RGMOVE': '~y~PILOT:~w~ wait until we are steady.', 'RGBLOCK': '~y~PILOT:~w~ no clear drop zone. Try open ground.', 'RGUP': '~b~PILOT:~w~ pulling you up.', 'RGABO': '~b~PILOT:~w~ CJ aboard. Team climbing up.', 'RGSEAT': '~y~PILOT:~w~ no free seat.', 'RGANIM': '~y~HELICOVER:~w~ rope animation unavailable.', 'RPDFAIL': '~y~PILOT:~w~ cannot lower the rope here. Try another spot.', 'SQIN': '~g~SQUAD:~w~ on the ground. Escorting CJ.', 'SQBACK': '~g~SQUAD:~w~ team back aboard.', 'SQLOST': '~r~SQUAD LOST!~w~ The escort team is down.', 'SQCOVER': '~g~SQUAD:~w~ covering your extraction.', 'SQAWAY': '~g~SQUAD:~w~ lost you. Team stands down.', 'SQSTAY': '~g~SQUAD:~w~ staying on the ground.', 'RGLATE': '~y~PILOT:~w~ you did not come. Ropes up.'}
import build_v25 as b
s=Script();a=s.add
# v32: an invisible flat platform (a51_jetdoor) kept 0.45 m below CJ's feet during scripted rope
# moves. CPedGeometryAnalyser::IsInAir looks 1.5 m below the ped centre for buildings, vehicles
# or objects; with the platform there the game never switches CJ into the free-fall task.
PLATFORM_MODEL=3095
_plat=[0]
def plat_create():
 _plat[0]+=1;k=str(_plat[0]);skip='PLAT_CREATE_SKIP_'+k
 a(6,V(6),I(-1));a(0x0247,I(PLATFORM_MODEL));a(0x038b);s.check(0x0248,[I(PLATFORM_MODEL)],skip)
 a(0x00a0,V(0),V(12),V(13),V(14));a(0x000b,V(14),F(-1.45));a(0x0107,I(PLATFORM_MODEL),V(12),V(13),V(14),V(6));a(0x0750,V(6),I(0));s.label(skip)
def plat_follow():
 _plat[0]+=1;skip='PLAT_FOLLOW_SKIP_'+str(_plat[0])
 s.check(0x03ca,[V(6)],skip);a(0x00a0,V(0),V(12),V(13),V(14));a(0x000b,V(14),F(-1.45));a(0x01bc,V(6),V(12),V(13),V(14));s.label(skip)
def plat_ride():
 # v37 descent: the platform follows its own schedule (start + 9@ * t), like a lift, so CJ rides
 # down even if the slab's top is level with his feet; CJ's own velocity keeps the same pace.
 _plat[0]+=1;skip='PLAT_RIDE_SKIP_'+str(_plat[0])
 s.check(0x03ca,[V(6)],skip);a(0x00a0,V(0),V(12),V(13),V(14));a(0x0087,V(14),V(11));a(0x0013,V(14),F(.001));a(0x006b,V(14),V(9));a(0x005b,V(14),V(7));a(0x01bc,V(6),V(12),V(13),V(14));s.label(skip)
def plat_delete():
 _plat[0]+=1;skip='PLAT_DELETE_SKIP_'+str(_plat[0])
 s.check(0x03ca,[V(6)],skip);a(0x0108,V(6));s.label(skip);a(6,V(6),I(-1));a(0x0249,I(PLATFORM_MODEL))
_rel=[0]
def release_guard(i,var):
 """1.2: a guard who stays behind is never deleted in view: out of sight he is deleted, in view the game gets him back (01C2)."""
 _rel[0]+=1;n=str(_rel[0]);seen='REL_SEEN_'+n;done='REL_DONE_'+n;skip='REL_SKIP_'+n
 s.set(b.GROUND_PUB+i,-1);s.check(0x056d,[V(var)],skip);s.check(0x82cb,[V(var)],seen);a(0x009b,V(var));s.go(done)
 s.label(seen);a(0x01c2,V(var));s.label(done);a(6,V(var),I(-1));s.label(skip)
s.label('INIT');a(0);a(6,V(6),I(-1))
for i in range(5):s.set(b.GROUND_PUB+i,-1)
s.set(b.ROPE_COMMAND,0);s.set(b.GROUND_MOVE_NEXT,0);s.set(b.DROP_COMMAND,0);s.set(b.SQ_ROPE,0);s.set(b.ESCORT_ON,0);s.set(b.ESCORT_CMD,0)
s.label('WAIT');a(1,I(100));s.set(b.ROPE_BUSY,0);s.get(19,b.ESCORT_CMD);s.eq(19,1,'WAIT_ESCORT_OTHER');s.set(b.ESCORT_CMD,0);s.set(b.ESCORT_ON,2);s.go('PICKUP_VALIDATE')
s.label('WAIT_ESCORT_OTHER');s.eq(19,0,'WAIT_ESCORT_CLEAR');s.go('WAIT_DROP_CHECK');s.label('WAIT_ESCORT_CLEAR');s.set(b.ESCORT_CMD,0)
s.label('WAIT_DROP_CHECK');s.get(19,b.DROP_COMMAND);s.eq(19,1,'WAIT_PICKUP');s.set(b.DROP_COMMAND,0);s.go('DROP_START')
s.label('WAIT_PICKUP');s.get(19,b.ROPE_COMMAND);s.eq(19,1,'WAIT');s.set(b.ROPE_COMMAND,0)
s.label('PICKUP_VALIDATE');s.get(19,b.STATE);s.eq(19,3,'NOHOLD');s.get(1,b.PUB+1);s.get(0,b.PUB);s.check(0x0256,[I(0)],'ABANDON');s.check(0x056e,[V(1)],'NOHOLD');s.check(0x8119,[V(1)],'NOHOLD');s.check(0x056d,[V(0)],'NOHOLD');s.check(0x80db,[V(0),V(1)],'BLOCKED')
a(0x00aa,V(1),V(2),V(3),V(4));a(0x00a0,V(0),V(5),V(6),V(7));a(0x0509,V(2),V(3),V(5),V(6),V(8));s.check(0x0023,[F(55),V(8)],'BLOCKED');a(0x01bd,V(31));a(0x000a,V(31),I(15000))
s.label('WAIT_STABLE');a(0x02e3,V(1),V(8));s.check(0x0023,[F(1.5),V(8)],'WAIT_STABLE_RETRY');s.go('WAIT_STABLE_DONE')
s.label('WAIT_STABLE_RETRY');a(0x01bd,V(19));s.check(0x001d,[V(19),V(31)],'WAIT_STABLE_CONTINUE');s.go('MOVING')
s.label('WAIT_STABLE_CONTINUE');a(1,I(500));s.check(0x0256,[I(0)],'ABANDON');s.check(0x056e,[V(1)],'NOHOLD');s.get(19,b.STATE);s.eq(19,3,'NOHOLD');s.go('WAIT_STABLE')
s.label('WAIT_STABLE_DONE');a(0x00aa,V(1),V(2),V(3),V(4));a(0x02ce,V(2),V(3),V(4),V(8));a(0x0087,V(9),V(4));a(0x0063,V(9),V(8));s.check(0x0021,[V(9),F(12)],'ALTITUDE');s.check(0x0023,[F(22),V(9)],'ALTITUDE')
for var in [17,20,21,22,23]:a(6,V(var),I(-1))
a(6,V(26),I(0))
for x,y in [(-1.5,1.2),(1.5,1.2),(-1.5,-1.2),(1.5,-1.2)]:
 a(0x0407,V(1),F(x),F(y),F(-1),V(10),V(11),V(12));a(0x02ce,V(10),V(11),V(12),V(13));a(0x0087,V(15),V(13));a(0x0063,V(15),V(8));s.check(0x0023,[F(3),V(15)],'BLOCKED');s.check(0x0021,[V(15),F(-3)],'BLOCKED');a(0x000b,V(13),F(1));s.check(0x06bd,[V(10),V(11),V(13),V(10),V(11),V(12),I(1),I(0),I(0),I(1),I(0)],'BLOCKED')
# 1.2: the team wears the crew setting (Grove 106/107 alternating, Army 287, SWAT 285); 285 stays loaded for the invisible rope actor
s.call('GROUND_MODELS');a(0xddc,I(b.TEAM_CREW),V(19))
a(0x0247,I(285));a(0x0247,V(2));a(0x0247,V(3));a(0x038b);a(1,I(0));s.check(0x0248,[I(285)],'LOAD_FAILED');s.check(0x0248,[V(2)],'LOAD_FAILED');s.check(0x0248,[V(3)],'LOAD_FAILED');s.check(0x056e,[V(1)],'LOAD_FAILED');s.get(19,b.STATE);s.eq(19,3,'LOAD_FAILED');a(0x02e3,V(1),V(8));s.check(0x0023,[F(1.5),V(8)],'LOAD_FAILED')
a(0x0574,V(1),I(1));s.set(b.FROZEN,1)
for i,(var,x,y) in enumerate([(20,-1.5,1.2),(21,1.5,1.2),(22,-1.5,-1.2),(23,1.5,-1.2)]):
 a(0x0407,V(1),F(x),F(y),F(-1),V(10),V(11),V(12));a(0x0503,I(8),V(2 if i%2==0 else 3),V(10),V(11),V(12),V(var));s.check(0x056d,[V(var)],'CLEANUP');a(0xddc,I(b.GROUND_PUB+i),V(var));a(0x0085,V(7),V(var));s.call('GSETUP');a(0x0223,V(var),I(150));a(0x035f,V(var),I(50))
s.get(19,b.ESCORT_ON);s.eq(19,2,'PICKUP_DEPLOYED');s.go('ESCORT_LAND')
s.label('PICKUP_DEPLOYED');s.set(b.ROPE_BUSY,1);a(0x01bd,V(19));a(0xddc,I(b.ROPE_T0),V(19));say(s,'RGDEP');a(0x01bd,V(27));a(0x000a,V(27),I(5000));a(6,V(25),I(-1));a(6,V(26),I(0));a(6,V(30),I(0));a(6,V(18),I(0))
s.label('ACTIVE');a(1,I(500));s.get(19,b.BUSY);s.eq(19,1,'ACT_NOT_BUSY');s.go('ACTIVE')   # 1.2: the core is swapping the model / crew (states 16 / 17): sit this cycle out
s.label('ACT_NOT_BUSY');s.get(1,b.PUB+1);s.set(b.SQ_ROPE,1);s.check(0x0256,[I(0)],'CLEANUP');s.check(0x056e,[V(1)],'CLEANUP');s.check(0x8119,[V(1)],'CLEANUP');s.check(0x056d,[V(0)],'CLEANUP');s.get(19,b.STATE);s.eq(19,3,'CLEANUP');s.get(19,b.ROPE_COMMAND);s.eq(19,1,'CONTINUE');s.set(b.ROPE_COMMAND,0);s.go('CLEANUP')
s.label('CONTINUE');a(0x01bd,V(19))
# 1.2: nobody climbs for 90 s: the pilot pulls the ropes up instead of hovering frozen for ever
s.get(15,b.ROPE_T0);a(0x0085,V(16),V(19));a(0x0062,V(16),V(15));s.check(0x0019,[V(16),I(90000)],'ACTIVE_FRESH');say(s,'RGLATE');s.go('CLEANUP')
s.label('ACTIVE_FRESH');s.call('TEAM_DECOR');a(0x01bd,V(19))
# Refresh a fifth rope while waiting; the invisible temporary actor only provides the rope visual.
s.check(0x001d,[V(19),V(18)],'PICKUP_GATE')
s.check(0x056d,[V(17)],'FIFTH_NEW');a(0x009b,V(17))
s.label('FIFTH_NEW');a(0x0407,V(1),F(0),F(-3.0),F(-1),V(10),V(11),V(12));a(0x0503,I(8),I(285),V(10),V(11),V(12),V(17));a(0xddc,I(b.GROUND_PUB+4),V(17));s.check(0x056d,[V(17)],'FIFTH_NEXT');a(0x0337,V(17),I(0));a(0x0619,V(17),I(0));a(0x048f,V(17))
s.label('FIFTH_NEXT');a(0x01bd,V(18));a(0x000a,V(18),I(2500))
s.label('PICKUP_GATE');a(0x01bd,V(19));s.check(0x001d,[V(19),V(27)],'ACTIVE')
s.label('PICKUP_CHECK');s.set(b.ROPE_BUSY,0)   # the guards are down: waiting for CJ is not a rope motion
# Do not interrupt a descending guard: enter only after all living guards are on the ground.
for var in [20,21,22,23]:
 skip='PICKUP_LANDED_SKIP_'+str(var);s.check(0x056d,[V(var)],skip);s.check(0x8118,[V(var)],skip);a(0x00a0,V(var),V(10),V(11),V(12));a(0x02ce,V(10),V(11),V(12),V(13));a(0x0063,V(12),V(13));s.check(0x0023,[F(2.5),V(12)],'UPDATE_FIRE');s.label(skip)
a(0x0407,V(1),F(0),F(-3.0),F(-1),V(10),V(11),V(12));a(0x02ce,V(10),V(11),V(12),V(12));a(0x000b,V(12),F(.7));a(0x00a0,V(0),V(13),V(14),V(15));a(0x050a,V(10),V(11),V(12),V(13),V(14),V(15),V(16));s.check(0x0023,[F(1.7),V(16)],'UPDATE_FIRE');s.go('CJ_ASCENT')
s.label('UPDATE_FIRE');s.get(24,b.FIRE_TARGET);s.get(28,b.FIRE_ACTIVE);s.get(29,b.WPN)
# Refresh fighting tasks only when target changes or the prior task nears expiry.
a(6,V(31),I(0));s.eq(28,1,'TASK_READY');s.check(0x803b,[V(24),V(25)],'TASK_CHECK_TIMER');s.go('TASK_REFRESH')
s.label('TASK_CHECK_TIMER');a(0x01bd,V(19));s.check(0x001d,[V(19),V(30)],'TASK_READY')
s.label('TASK_REFRESH');a(6,V(31),I(1));a(0x0085,V(25),V(24));a(0x01bd,V(30));a(0x000a,V(30),I(1500))
s.label('TASK_READY')
# Refresh movement at most once per second, so run tasks are not restarted every tick.
a(6,V(7),I(0));s.get(19,b.GROUND_MOVE_NEXT);a(0x01bd,V(15));s.check(0x001d,[V(15),V(19)],'MOVE_TICK_READY');a(6,V(7),I(1));a(0x000a,V(15),I(1000));a(0xddc,I(b.GROUND_MOVE_NEXT),V(15));s.label('MOVE_TICK_READY')
for var,x,y in [(20,-2.5,-2.0),(21,2.5,-2.0),(22,-6.,1.),(23,6.,1.)]:
 skip='WORK_SKIP_'+str(var);walk='WALK_'+str(var);watch='WATCH_'+str(var);fire='FIRE_'+str(var)
 s.check(0x056d,[V(var)],skip);s.check(0x8118,[V(var)],skip);a(0x0819,V(var),V(19));s.check(0x0023,[F(2.5),V(19)],skip);a(0x0470,V(var),V(19));s.check(0x003b,[V(19),V(29)],'ARM_'+str(var));s.go('ARM_DONE_'+str(var));s.label('ARM_'+str(var));a(0x01b2,V(var),V(29),I(30000));a(0x01b9,V(var),V(29));s.label('ARM_DONE_'+str(var))
 # v40: the squad worker gives the orders while its heartbeat is fresh
 s.get(19,b.SQ_HEART);a(0x0085,V(16),V(15));a(0x0062,V(16),V(19));s.check(0x0019,[V(16),I(1000)],skip)
 s.eq(28,1,walk);s.check(0x056d,[V(24)],walk);s.check(0x8118,[V(24)],walk);s.eq(31,1,skip);a(0x074d,V(var),V(24),I(2000));s.go(skip)
 s.label(walk);a(0x04c4,V(0),F(x),F(y),F(0),V(10),V(11),V(12));a(0x00a0,V(var),V(13),V(14),V(15));a(0x050a,V(10),V(11),V(12),V(13),V(14),V(15),V(16));s.check(0x0021,[V(16),F(3)],watch);s.eq(7,1,skip);a(0x04eb,V(var),I(0));a(0x05d3,V(var),V(10),V(11),V(12),I(6),I(1800));s.go(skip);s.label(watch);a(0x04eb,V(var),I(1));s.label(skip)
s.go('ACTIVE')
# The reverse clip is cosmetic; vertical position is moved explicitly.
s.label('CJ_ASCENT');s.set(b.ROPE_BUSY,1);s.set(b.SQ_ROPE,0);s.check(0x0431,[V(1),I(0)],'NO_SEAT');s.check(0x04ee,[S('PED')],'ANIM_FAIL');s.check(0x056e,[V(1)],'CLEANUP');s.get(19,b.STATE);s.eq(19,3,'CLEANUP')
# Save a ground position for cancellation and disable player control only during ascent.
a(0x0407,V(1),F(0),F(-3),F(-1),V(2),V(3),V(4));a(0x02ce,V(2),V(3),V(4),V(4));a(0x000b,V(4),F(.7));a(0x0087,V(8),V(4));# v35: stop 4.5 m below the helicopter centre, clear of the tail boom above the rope, then warp in
a(0x00aa,V(1),V(10),V(11),V(9));a(0x000b,V(9),F(-4.5));a(0x0063,V(9),V(8));a(0x0013,V(9),F(1000.0/1500.0));a(0x01b4,I(0),I(0));a(6,V(26),I(1))
# v33: no snap to the rope point (that was the abrupt frame change). CJ drifts onto the rope line
# during the climb (5@/7@ horizontal speed) and the clip blends in more slowly.
a(0x00a0,V(0),V(12),V(13),V(14));a(0x0087,V(5),V(2));a(0x0063,V(5),V(12));a(0x0013,V(5),F(1000.0/1500.0));a(0x0087,V(7),V(3));a(0x0063,V(7),V(13));a(0x0013,V(7),F(1000.0/1500.0))
a(0x0605,V(0),S('ABSEIL'),S('PED'),F(2),I(1),I(1),I(1),I(1),I(-1));a(1,I(100));s.check(0x0611,[V(0),S('ABSEIL')],'CJ_ANIM_NOT_RUNNING');a(0x0614,V(0),S('ABSEIL'),F(.99));a(0x0393,V(0),S('ABSEIL'),F(-1));s.label('CJ_ANIM_NOT_RUNNING')
plat_create()
a(0x01bd,V(16));say(s,'RGUP')
s.label('CJ_UP_TICK');a(1,I(0));s.check(0x0256,[I(0)],'ASCENT_ABORT');s.check(0x056d,[V(0)],'ASCENT_ABORT');s.check(0x8118,[V(0)],'ASCENT_ABORT');s.check(0x056e,[V(1)],'ASCENT_ABORT');s.check(0x8119,[V(1)],'ASCENT_ABORT');s.get(19,b.STATE);s.eq(19,3,'ASCENT_ABORT');a(0x01bd,V(15));a(0x0062,V(15),V(16));s.check(0x0019,[V(15),I(1500)],'CJ_TIME_READY');a(6,V(15),I(1500));s.label('CJ_TIME_READY');s.check(0x0611,[V(0),S('ABSEIL')],'CJ_FRAME_ANIM_SKIP');a(0x0093,V(11),V(15));a(0x0013,V(11),F(1.0/1500.0));a(0x0007,V(12),F(1));a(0x0063,V(12),V(11));a(0x0614,V(0),S('ABSEIL'),V(12));s.label('CJ_FRAME_ANIM_SKIP')
plat_follow()
a(0x083c,V(0),V(5),V(7),V(9));s.check(0x0019,[V(15),I(1499)],'CJ_UP_TICK');a(0x083c,V(0),F(0),F(0),F(0))
plat_delete()
s.check(0x0431,[V(1),I(0)],'ASCENT_ABORT');a(0x0430,V(0),V(1),I(0));s.check(0x0448,[V(0),V(1)],'ASCENT_ABORT');a(0x01b4,I(0),I(1));a(6,V(26),I(0));say(s,'RGABO')
# v33: once CJ is aboard the four rope guards return together: sprint to their ropes (<= 2.5 s),
# then all rise at once in 1.2 s with the reversed ABSEIL clip, and board (are removed).
GR=[(20,-1.5,1.2),(21,1.5,1.2),(22,-1.5,-1.2),(23,1.5,-1.2)]
def gr_alive(var,skip):s.check(0x056d,[V(var)],skip);s.check(0x8118,[V(var)],skip)
def gr_rope(x,y,dx,dy,dz):a(0x0407,V(1),F(x),F(y),F(-1),V(dx),V(dy),V(dz));a(0x02ce,V(dx),V(dy),V(dz),V(dz));a(0x000b,V(dz),F(.7))
def gr_checks():s.check(0x0256,[I(0)],'CLEANUP');s.check(0x056e,[V(1)],'CLEANUP');s.check(0x8119,[V(1)],'CLEANUP');s.get(19,b.STATE);s.eq(19,3,'CLEANUP')
s.label('GR_RETURN');s.set(b.ROPE_BUSY,1);s.set(b.SQ_ROPE,0)
# 1.2: the guards run to their ropes and the pilot waits up to 25 s for them (it was 2.5 s, then everybody was warped to
# the rope); a guard in a car gets out first (0633, it was a teleport out of the car); whoever has not arrived stays behind
a(0x01bd,V(18));a(0x000a,V(18),I(25000));a(6,V(24),I(0))
s.label('GR_WAIT');a(1,I(100));gr_checks();a(0x01bd,V(9));a(6,V(19),I(1));a(6,V(8),I(0))
s.check(0x001d,[V(9),V(24)],'GR_NO_ORDER');a(6,V(8),I(1));a(0x0085,V(24),V(9));a(0x000a,V(24),I(1500));s.label('GR_NO_ORDER')
for var,x,y in GR:
 skip='GR_AT_'+str(var);gr_alive(var,skip);gr_rope(x,y,10,11,12);a(0x00a0,V(var),V(13),V(14),V(15));a(0x050a,V(10),V(11),V(12),V(13),V(14),V(15),V(16));s.check(0x0021,[V(16),F(2)],skip);a(6,V(19),I(0))
 s.eq(8,1,skip);s.check(0x00df,[V(var)],'GR_RUN_'+str(var));a(0x0633,V(var));s.go(skip)
 s.label('GR_RUN_'+str(var));a(0x04eb,V(var),I(0));a(0x05d3,V(var),V(10),V(11),V(12),I(7),I(2500));s.label(skip)
s.eq(19,1,'GR_NOT_ALL');s.go('GR_RISE')
s.label('GR_NOT_ALL');a(0x01bd,V(15));s.check(0x001d,[V(15),V(18)],'GR_WAIT')
# time is up: whoever is not at his rope stays on the ground (released, not teleported); nobody left = the ropes go up empty
a(6,V(19),I(0))
for i,(var,x,y) in enumerate(GR):
 skip='GR_LEFT_'+str(var);keep='GR_KEEP_'+str(var);gr_alive(var,skip);gr_rope(x,y,10,11,12);a(0x00a0,V(var),V(13),V(14),V(15));a(0x050a,V(10),V(11),V(12),V(13),V(14),V(15),V(16));s.check(0x0021,[V(16),F(2.5)],keep)
 release_guard(i,var);s.go(skip);s.label(keep);a(6,V(19),I(1));s.label(skip)
s.eq(19,1,'CLEANUP')
s.label('GR_RISE');a(0x00aa,V(1),V(10),V(11),V(9));a(0x000b,V(9),F(-1));a(0x0007,V(8),F(0))
for var,x,y in GR:
 skip='GR_PLACE_'+str(var);gr_alive(var,skip);gr_rope(x,y,2,3,4);a(0x0087,V(8),V(4));a(0x00a1,V(var),V(2),V(3),V(4));a(0x0605,V(var),S('ABSEIL'),S('PED'),F(2),I(1),I(1),I(1),I(1),I(-1));s.label(skip)
a(0x0063,V(9),V(8));a(0x0013,V(9),F(1000.0/1200.0));a(1,I(100))
for var,x,y in GR:
 skip='GR_ANIM_'+str(var);gr_alive(var,skip);s.check(0x0611,[V(var),S('ABSEIL')],skip);a(0x0614,V(var),S('ABSEIL'),F(.99));a(0x0393,V(var),S('ABSEIL'),F(-1));s.label(skip)
a(0x01bd,V(16))
s.label('GR_TICK');a(1,I(0));gr_checks();a(0x01bd,V(15));a(0x0062,V(15),V(16));s.check(0x0019,[V(15),I(1200)],'GR_T_OK');a(6,V(15),I(1200));s.label('GR_T_OK')
a(0x0093,V(11),V(15));a(0x0013,V(11),F(1.0/1200.0));a(0x0007,V(12),F(1));a(0x0063,V(12),V(11))
for var,x,y in GR:
 skip='GR_UP_'+str(var);anim='GR_UP_ANIM_'+str(var);gr_alive(var,skip);s.check(0x0611,[V(var),S('ABSEIL')],anim);a(0x0614,V(var),S('ABSEIL'),V(12));s.label(anim);a(0x083c,V(var),F(0),F(0),V(9));s.label(skip)
s.check(0x0019,[V(15),I(1199)],'GR_TICK')
for var,x,y in GR:
 skip='GR_STOP_'+str(var);gr_alive(var,skip);a(0x083c,V(var),F(0),F(0),F(0));a(0x009b,V(var));s.label(skip)   # 1.2: they are at the door: boarding = removal there
s.go('CLEANUP')
s.label('ASCENT_ABORT')
plat_delete()
s.eq(26,1,'CLEANUP');s.check(0x056d,[V(0)],'ASCENT_RESTORE');s.check(0x8118,[V(0)],'ASCENT_RESTORE');a(0x00a1,V(0),V(2),V(3),V(4))
s.label('ASCENT_RESTORE');a(0x01b4,I(0),I(1));a(6,V(26),I(0));s.go('CLEANUP')
s.label('NO_SEAT');say(s,'RGSEAT');s.go('ACTIVE')
s.label('ANIM_FAIL');say(s,'RGANIM');s.go('CLEANUP')
s.label('CLEANUP');s.set(b.SQ_ROPE,0)
plat_delete()
s.eq(26,1,'CLEANUP_CONTROL_DONE');a(0x01b4,I(0),I(1));a(6,V(26),I(0));s.label('CLEANUP_CONTROL_DONE');s.check(0x056d,[V(17)],'CLEANUP_ROPE_DONE');a(0x009b,V(17));s.label('CLEANUP_ROPE_DONE');s.set(b.GROUND_PUB+4,-1);s.check(0x056e,[V(1)],'CLEANUP_HELI_DONE');a(0x0574,V(1),I(0));s.set(b.FROZEN,0);s.label('CLEANUP_HELI_DONE')
for i,var in enumerate([20,21,22,23]):release_guard(i,var)
# v40 escort bookkeeping: 3 recalled (resume FOLLOW), 1 picked up / withdrawn, 4 lost, else plain rope work
a(0x0249,I(285));s.get(19,b.ESCORT_ON);s.set(b.ESCORT_ON,0)
s.eq(19,3,'CL_NOT_RECALL');say(s,'SQBACK');s.check(0x0256,[I(0)],'WAIT');s.check(0x056d,[V(0)],'WAIT');s.check(0x056e,[V(1)],'WAIT');s.check(0x8448,[V(0),V(1)],'WAIT');s.set(b.CMD,2);s.go('WAIT')
s.label('CL_NOT_RECALL');s.eq(19,1,'CL_NOT_ESCORT');say(s,'SQBACK');s.go('WAIT')
s.label('CL_NOT_ESCORT');s.eq(19,4,'CL_NOT_LOST');s.go('WAIT')
s.label('CL_NOT_LOST');s.eq(19,5,'CL_PLAIN');say(s,'SQSTAY');s.go('WAIT')
s.label('CL_PLAIN');say(s,'RGDONE');s.go('WAIT')
s.label('DROP_START');s.set(b.ROPE_BUSY,1);a(6,V(26),I(0));s.get(19,b.STATE);s.eq(19,23,'DROP_FAIL');s.get(1,b.PUB+1);s.get(0,b.PUB);s.check(0x0256,[I(0)],'WAIT');s.check(0x056e,[V(1)],'DROP_FAIL');s.check(0x8119,[V(1)],'DROP_FAIL');s.check(0x056d,[V(0)],'DROP_FAIL');s.check(0x0448,[V(0),V(1)],'DROP_FAIL');a(0x0407,V(1),F(0),F(-3),F(-1),V(2),V(3),V(8));a(0x02ce,V(2),V(3),V(8),V(4));a(0x000b,V(4),F(.7));a(0x0087,V(9),V(8));a(0x0063,V(9),V(4));s.check(0x0021,[V(9),F(4)],'DROP_FAIL');s.check(0x0023,[F(60),V(9)],'DROP_FAIL');a(0x0087,V(10),V(4));a(0x000b,V(10),F(1));s.check(0x06bd,[V(2),V(3),V(10),V(2),V(3),V(8),I(1),I(0),I(0),I(1),I(0)],'DROP_FAIL');a(0x0247,I(285));a(6,V(26),I(1));a(0x038b);a(1,I(0));s.check(0x0248,[I(285)],'DROP_FAIL');s.check(0x056e,[V(1)],'DROP_FAIL');a(0x0574,V(1),I(1));s.set(b.FROZEN,1);a(6,V(17),I(-1));a(0x0503,I(8),I(285),V(2),V(3),V(8),V(17));s.check(0x056d,[V(17)],'DROP_FAIL_UNFREEZE');a(0x0337,V(17),I(0));a(0x0619,V(17),I(0));a(0xddc,I(b.GROUND_PUB+4),V(17));a(0x01b4,I(0),I(0))
# v28: 1 m below the frozen helicopter's centre is inside its hull, which held CJ until the
# final ground warp ("teleport"). Start 3 m lower, below the skids, and recompute the descent speed.
a(0x000b,V(8),F(-2));a(0x0087,V(9),V(8));a(0x0063,V(9),V(4));a(0x0362,V(0),V(2),V(3),V(8));s.check(0x04ee,[S('PED')],'DROP_ANIM_SKIP');a(0x0605,V(0),S('ABSEIL'),S('PED'),F(4),I(1),I(1),I(1),I(1),I(-1));s.label('DROP_ANIM_SKIP')
plat_create()
a(0x00a0,V(0),V(12),V(13),V(7));a(0x000b,V(7),F(-1.45))
# v39.2: drop time scales with the height (~6 m/s, clamped 2-6 s) so a drop from wherever the
# helicopter froze looks like a controlled abseil. 5@ = duration ms, 10@ = .99/duration, 9@ = -m/s.
a(0x0087,V(5),V(9));a(0x0013,V(5),F(1000.0/6.0));s.check(0x0023,[F(2000),V(5)],'DROP_T_MIN_OK');a(0x0007,V(5),F(2000));s.label('DROP_T_MIN_OK');s.check(0x0021,[V(5),F(6000)],'DROP_T_MAX_OK');a(0x0007,V(5),F(6000));s.label('DROP_T_MAX_OK')
a(0x0073,V(9),V(5));a(0x0013,V(9),F(-1000.0));a(0x0007,V(10),F(.99));a(0x0073,V(10),V(5));a(0x01bd,V(16))
s.label('DROP_TICK');a(1,I(0));s.check(0x0256,[I(0)],'DROP_ABORT');s.check(0x056d,[V(0)],'DROP_ABORT');s.check(0x8118,[V(0)],'DROP_ABORT');s.check(0x056e,[V(1)],'DROP_ABORT');s.get(19,b.STATE);s.eq(19,23,'DROP_ABORT');a(0x01bd,V(15));a(0x0062,V(15),V(16));a(0x0093,V(11),V(15));s.check(0x0025,[V(11),V(5)],'DROP_TIME_READY');a(0x0087,V(11),V(5));s.label('DROP_TIME_READY')
# v31: like the ascent, drive the ABSEIL frame every tick (paused anim, time 0 -> .99 over 3 s);
# without it the ped dropped into a free-fall pose.
s.check(0x0611,[V(0),S('ABSEIL')],'DROP_FRAME_SKIP');a(0x0087,V(12),V(11));a(0x006b,V(12),V(10));a(0x0614,V(0),S('ABSEIL'),V(12));a(0x0393,V(0),S('ABSEIL'),F(0));s.label('DROP_FRAME_SKIP')
plat_ride()
a(0x083c,V(0),F(0),F(0),V(9));s.check(0x8025,[V(5),V(11)],'DROP_TICK')
plat_delete()
a(0x083c,V(0),F(0),F(0),F(0));a(0x00a1,V(0),V(2),V(3),V(4));a(0x01b4,I(0),I(1));s.check(0x056d,[V(17)],'DROP_NO_DUMMY');a(0x009b,V(17));s.label('DROP_NO_DUMMY');s.set(b.GROUND_PUB+4,-1);a(0x0574,V(1),I(0));s.set(b.FROZEN,0);s.set(b.STATE,3);s.set(b.DROP_RESULT,0);s.set(b.ROPE_PENDING,0);a(0x0249,I(285));s.go('WAIT')
s.label('DROP_ABORT')
plat_delete()
s.check(0x056d,[V(0)],'DROP_ABORT_CONTROL');s.check(0x8118,[V(0)],'DROP_ABORT_CONTROL');a(0x00a1,V(0),V(2),V(3),V(4));s.label('DROP_ABORT_CONTROL');a(0x01b4,I(0),I(1));s.check(0x056d,[V(17)],'DROP_FAIL_UNFREEZE');a(0x009b,V(17))
s.label('DROP_FAIL_UNFREEZE');s.set(b.GROUND_PUB+4,-1);s.check(0x056e,[V(1)],'DROP_FAIL');a(0x0574,V(1),I(0));s.set(b.FROZEN,0)
s.label('DROP_FAIL');s.eq(26,1,'DROP_FAIL_NO_MODEL');a(0x0249,I(285));s.label('DROP_FAIL_NO_MODEL');s.set(b.DROP_RESULT,1)
# v39b: when the core manages the attempt it retries elsewhere and reports the final failure itself
s.get(19,b.ROPE_PENDING);s.eq(19,1,'DROP_FAIL_SAY');s.go('WAIT');s.label('DROP_FAIL_SAY');say(s,'RPDFAIL');s.go('WAIT')

# ---------------------------------------------------------------- 1.2 decor: the team follows the settings at once
# GROUND_MODELS: V19 = crew setting, V2 / V3 = models of the even / odd guards (Grove 106 / 107, Army 287, SWAT 285).
s.label('GROUND_MODELS');s.get(19,b.CREW);a(6,V(2),I(106));a(6,V(3),I(107));s.eq(19,0,'GM_NOT_GROVE');s.ret()
s.label('GM_NOT_GROVE');a(6,V(2),I(287));a(6,V(3),I(287));s.eq(19,1,'GM_SWAT');s.ret()
s.label('GM_SWAT');a(6,V(2),I(285));a(6,V(3),I(285));s.ret()
# GSETUP: V7 = a new team member: mine, friendly to everybody, accurate.
s.label('GSETUP');a(0x01c5,V(7));a(0x08af,V(7),I(150));a(0x02e2,V(7),I(100))
for typ in range(32):a(0x077a,V(7),I(2),I(typ))
a(0x077a,V(7),I(0),I(0));a(0x077a,V(7),I(0),I(8));s.ret()
# TEAM_DECOR: every living guard holds the chosen weapon and wears the chosen crew's clothes; a guard in the wrong clothes is
# replaced in place (new one created at his spot with his heading / health / armour, then the old one is removed in the same
# tick; a guard in a car or a model that is not resident yet waits for the next cycle). Uses V2-V5, V7-V9-V16, V19 (never V6: the
# platform handle, nor V30: the fire task timer).
s.label('TEAM_DECOR');s.get(4,b.WPN);s.call('GROUND_MODELS');s.get(15,b.TEAM_CREW);a(6,V(16),I(1))
for i,var in enumerate([20,21,22,23]):
 skip='TD_SKIP_'+str(i);need='TD_NEED_'+str(i);mdl=2 if i%2==0 else 3;foot='TD_FOOT_'+str(i);load='TD_LOAD_'+str(i);noarm='TD_MODEL_'+str(i);noarm2='TD_NOARM_'+str(i)
 gr_alive(var,skip)
 s.check(0x0019,[V(4),I(0)],noarm);a(0x0470,V(var),V(5));s.check(0x803b,[V(5),V(4)],noarm);a(0x01b2,V(var),V(4),I(30000));a(0x01b9,V(var),V(4));a(0x02e2,V(var),I(100));s.label(noarm)
 s.check(0x02f2,[V(var),V(mdl)],need);s.go(skip)
 s.label(need);a(6,V(16),I(0));s.check(0x00df,[V(var)],foot);s.go(skip)
 s.label(foot);s.check(0x0248,[V(mdl)],load)
 a(0x00a0,V(var),V(10),V(11),V(12));a(0x0172,V(var),V(13));a(0x0226,V(var),V(14));a(0x04dd,V(var),V(9))
 a(0x009a,I(8),V(mdl),V(10),V(11),V(12),V(8));s.check(0x056d,[V(8)],skip)
 a(0x0173,V(8),V(13));a(0x0085,V(7),V(8));s.call('GSETUP');a(0x0223,V(8),V(14));a(0x035f,V(8),V(9))
 s.check(0x0019,[V(4),I(0)],noarm2);a(0x01b2,V(8),V(4),I(30000));a(0x01b9,V(8),V(4));s.label(noarm2)
 a(0x009b,V(var));a(0x0085,V(var),V(8));a(0xddc,I(b.GROUND_PUB+i),V(var));s.set(b.SQ_SLOT+i*b.SQ_SLOT_SIZE,-1);s.go(skip)
 s.label(load);a(0x0247,V(mdl));s.label(skip)
s.eq(16,1,'TD_RET');a(0xddc,I(b.TEAM_CREW),V(19))
s.label('TD_RET');s.ret()

# ---------------------------------------------------------------- v40 escort team
# The four rope guards stay on the ground with CJ (the squad worker leads them) while the helicopter
# returns to FOLLOW / overwatch. Ends with a recall (rope extraction), a rope pickup of CJ with the
# team covering, a withdrawal (CJ boarded another way, support leaving) or the loss of the team.
s.label('ESCORT_LAND');s.set(b.ROPE_BUSY,1);a(0x01bd,V(27));a(0x000a,V(27),I(12000))
s.label('ESCORT_LAND_WAIT');a(1,I(200));gr_checks();a(6,V(19),I(1))
for var in [20,21,22,23]:
 skip='ESCORT_LANDED_'+str(var);gr_alive(var,skip);a(0x0819,V(var),V(12));s.check(0x0021,[V(12),F(2.5)],skip);a(6,V(19),I(0));s.label(skip)
s.eq(19,1,'ESCORT_LAND_TIMER');s.go('ESCORT_READY')
s.label('ESCORT_LAND_TIMER');a(0x01bd,V(15));s.check(0x001d,[V(15),V(27)],'ESCORT_LAND_WAIT')
s.label('ESCORT_READY');s.get(29,b.WPN);s.set(b.ESC_LAGGED,0)
for i in range(4):s.set(b.SQ_LAG+i,0)
for var in [20,21,22,23]:
 skip='ESCORT_ARM_'+str(var);gr_alive(var,skip);a(0x01b2,V(var),V(29),I(30000));a(0x01b9,V(var),V(29));s.label(skip)
s.set(b.SQ_ROPE,1);s.set(b.ESCORT_ON,1);a(0x0574,V(1),I(0));s.set(b.FROZEN,0);say(s,'SQIN');s.set(b.NOTICE_SKIP,2);s.set(b.CMD,2)
s.label('ESCORT_LOOP');a(1,I(250));s.get(19,b.BUSY);s.eq(19,1,'ESC_NOT_BUSY');s.go('ESCORT_LOOP')
s.label('ESC_NOT_BUSY');s.set(b.SQ_ROPE,1);s.check(0x0256,[I(0)],'CLEANUP');s.check(0x056d,[V(0)],'CLEANUP');s.check(0x8118,[V(0)],'CLEANUP')
s.get(1,b.PUB+1)   # 1.2: the helicopter and the guards are re-read every cycle (a model swap or a re-skin publishes new handles)
for i in range(4):s.get(20+i,b.GROUND_PUB+i)
s.set(b.ROPE_BUSY,0);s.call('TEAM_DECOR')
s.check(0x056e,[V(1)],'ESCORT_WITHDRAW');s.check(0x8119,[V(1)],'ESCORT_WITHDRAW');s.get(19,b.STATE)
for st in [0,4,5,13]:
 nxt='ESCORT_STATE_'+str(st);s.eq(19,st,nxt);s.go('ESCORT_WITHDRAW');s.label(nxt)
# 1.2 lag ladder: a guard more than 70 m from CJ for 60 s is let go (deleted out of sight, handed to the game in view)
a(0x01bd,V(15));a(0x00a0,V(0),V(13),V(14),V(16))
for i,var in enumerate([20,21,22,23]):
 clr='ESC_LAG_CLR_'+str(i);run='ESC_LAG_RUN_'+str(i);nxt='ESC_LAG_NEXT_'+str(i);gr_alive(var,clr)
 a(0x00a0,V(var),V(10),V(11),V(12));a(0x0509,V(10),V(11),V(13),V(14),V(8));s.check(0x0021,[V(8),F(70)],clr)
 s.get(9,b.SQ_LAG+i);s.eq(9,0,run);a(0xddc,I(b.SQ_LAG+i),V(15));s.go(nxt)
 s.label(run);a(0x0085,V(16),V(15));a(0x0062,V(16),V(9));s.check(0x0019,[V(16),I(60000)],nxt)
 s.set(b.ESC_LAGGED,1);s.set(b.SQ_LAG+i,0);release_guard(i,var);s.go(nxt)
 s.label(clr);s.set(b.SQ_LAG+i,0);s.label(nxt)
a(6,V(19),I(0))
for var in [20,21,22,23]:
 skip='ESCORT_ALIVE_'+str(var);gr_alive(var,skip);a(6,V(19),I(1));s.label(skip)
s.eq(19,1,'ESCORT_LOST')
# CJ asked for a rope pickup: the team on the ground covers him exactly like a rope evacuation
s.get(19,b.ROPE_COMMAND);s.eq(19,1,'ESCORT_NO_PICKUP');s.set(b.ROPE_COMMAND,0);s.get(19,b.STATE);s.eq(19,3,'ESCORT_LOOP')
a(6,V(17),I(-1));a(6,V(18),I(0));a(6,V(25),I(-1));a(6,V(26),I(0));a(6,V(30),I(0));a(0x01bd,V(27));a(0x000a,V(27),I(3000));a(0x0085,V(19),V(27));a(0xddc,I(b.ROPE_T0),V(19));say(s,'SQCOVER');s.go('ACTIVE')
s.label('ESCORT_NO_PICKUP');s.get(19,b.ESCORT_CMD);s.eq(19,2,'ESCORT_NO_RECALL');s.set(b.ESCORT_CMD,0);s.get(19,b.STATE);s.eq(19,3,'ESCORT_LOOP');s.set(b.ESCORT_ON,3)
s.go('GR_RETURN')   # 1.2: GR_WAIT gets guards out of cars and sends them to the ropes (no teleport out of a car)
s.label('ESCORT_NO_RECALL');s.eq(19,3,'ESCORT_NO_EXTRACT');s.set(b.ESCORT_CMD,0);s.go('ESCORT_WITHDRAW')
s.label('ESCORT_NO_EXTRACT');s.check(0x0448,[V(0),V(1)],'ESCORT_LOOP')
# CJ is in the helicopter, the helicopter is gone or support is leaving: the team runs to the
# helicopter and boards (is removed) at the door or once out of sight; 15 s at most.
s.label('ESCORT_WITHDRAW');s.set(b.SQ_ROPE,0);s.set(b.ESCORT_ON,5)
# 1.2: there is no helicopter to board (it is gone, leaving, or CJ is flying): the team stays where it is, deleted only out of sight
for i,var in enumerate([20,21,22,23]):release_guard(i,var)
s.go('CLEANUP')
s.label('ESCORT_LOST');s.set(b.ESCORT_ON,4);s.get(19,b.ESC_LAGGED);s.eq(19,1,'ESCORT_DOWN');say(s,'SQAWAY');s.go('CLEANUP')
s.label('ESCORT_DOWN');say(s,'SQLOST');s.go('CLEANUP')

s.label('ABANDON');s.set(b.ESCORT_ON,0);s.go('WAIT')
s.label('LOAD_FAILED');s.set(b.ESCORT_ON,0);a(0x0249,I(285));say(s,'RGFAIL');s.go('WAIT')
s.label('NOHOLD');s.set(b.ESCORT_ON,0);say(s,'RGHOLD');s.go('WAIT')
s.label('ALTITUDE');s.set(b.ESCORT_ON,0);say(s,'RGHIGH');s.go('WAIT')
s.label('MOVING');s.set(b.ESCORT_ON,0);say(s,'RGMOVE');s.go('WAIT')
s.label('BLOCKED');s.set(b.ESCORT_ON,0);say(s,'RGBLOCK');s.go('WAIT')
if __name__=='__main__':
 report=s.build('Helicover_Ground','csa');print(report)
 with (OUT/'validation.txt').open('a') as validation:validation.write(report+'\n')
 with (OUT/'Helicover.fxt').open('a') as f:f.write(''.join(k+' '+v+'\n' for k,v in GROUND_TEXTS.items()))
