"""Experimental SWAT rope insertion worker for Helicover v15.
Experimental scripted reverse-animation ascent; gameplay is not tested on Android.
"""
from asm_v25 import *
import build_v25 as b
s=Script();a=s.add
s.label('INIT');a(0)
for i in range(5):s.set(b.GROUND_PUB+i,-1)
s.set(b.ROPE_COMMAND,0);s.set(b.GROUND_MOVE_NEXT,0);s.set(b.DROP_COMMAND,0)
s.label('WAIT');a(1,I(100));s.get(19,b.DROP_COMMAND);s.eq(19,1,'WAIT_PICKUP');s.set(b.DROP_COMMAND,0);s.go('DROP_START')
s.label('WAIT_PICKUP');s.get(19,b.ROPE_COMMAND);s.eq(19,1,'WAIT');s.set(b.ROPE_COMMAND,0);s.get(19,b.STATE);s.eq(19,3,'NOHOLD');s.get(1,b.PUB+1);s.get(0,b.PUB);s.check(0x0256,[I(0)],'WAIT');s.check(0x056e,[V(1)],'NOHOLD');s.check(0x8119,[V(1)],'NOHOLD');s.check(0x056d,[V(0)],'NOHOLD');s.check(0x80db,[V(0),V(1)],'BLOCKED')
a(0x00aa,V(1),V(2),V(3),V(4));a(0x00a0,V(0),V(5),V(6),V(7));a(0x0509,V(2),V(3),V(5),V(6),V(8));s.check(0x0023,[F(55),V(8)],'BLOCKED');a(0x01bd,V(31));a(0x000a,V(31),I(15000))
s.label('WAIT_STABLE');a(0x02e3,V(1),V(8));s.check(0x0023,[F(1.5),V(8)],'WAIT_STABLE_RETRY');s.go('WAIT_STABLE_DONE')
s.label('WAIT_STABLE_RETRY');a(0x01bd,V(19));s.check(0x001d,[V(19),V(31)],'WAIT_STABLE_CONTINUE');s.go('MOVING')
s.label('WAIT_STABLE_CONTINUE');a(1,I(500));s.check(0x0256,[I(0)],'WAIT');s.check(0x056e,[V(1)],'NOHOLD');s.get(19,b.STATE);s.eq(19,3,'NOHOLD');s.go('WAIT_STABLE')
s.label('WAIT_STABLE_DONE');a(0x00aa,V(1),V(2),V(3),V(4));a(0x02ce,V(2),V(3),V(4),V(8));a(0x0087,V(9),V(4));a(0x0063,V(9),V(8));s.check(0x0021,[V(9),F(12)],'ALTITUDE');s.check(0x0023,[F(22),V(9)],'ALTITUDE')
for var in [17,20,21,22,23]:a(6,V(var),I(-1))
a(6,V(26),I(0))
for x,y in [(-1.5,1.2),(1.5,1.2),(-1.5,-1.2),(1.5,-1.2)]:
 a(0x0407,V(1),F(x),F(y),F(-1),V(10),V(11),V(12));a(0x02ce,V(10),V(11),V(12),V(13));a(0x0087,V(15),V(13));a(0x0063,V(15),V(8));s.check(0x0023,[F(3),V(15)],'BLOCKED');s.check(0x0021,[V(15),F(-3)],'BLOCKED');a(0x000b,V(13),F(1));s.check(0x06bd,[V(10),V(11),V(13),V(10),V(11),V(12),I(1),I(0),I(0),I(1),I(0)],'BLOCKED')
a(0x0247,I(285));a(0x038b);a(1,I(0));s.check(0x0248,[I(285)],'LOAD_FAILED');s.check(0x056e,[V(1)],'LOAD_FAILED');s.get(19,b.STATE);s.eq(19,3,'LOAD_FAILED');a(0x02e3,V(1),V(8));s.check(0x0023,[F(1.5),V(8)],'LOAD_FAILED')
a(0x0574,V(1),I(1));s.set(b.FROZEN,1)
for i,(var,x,y) in enumerate([(20,-1.5,1.2),(21,1.5,1.2),(22,-1.5,-1.2),(23,1.5,-1.2)]):
 a(0x0407,V(1),F(x),F(y),F(-1),V(10),V(11),V(12));a(0x0503,I(8),I(285),V(10),V(11),V(12),V(var));s.check(0x056d,[V(var)],'CLEANUP');a(0xddc,I(b.GROUND_PUB+i),V(var));a(0x01c5,V(var));a(0x08af,V(var),I(150));a(0x0223,V(var),I(150));a(0x035f,V(var),I(50));a(0x02e2,V(var),I(100))
 for typ in range(32):a(0x077a,V(var),I(2),I(typ))
 a(0x077a,V(var),I(0),I(0));a(0x077a,V(var),I(0),I(8))
a(0x03e5,S('RGDEP'));a(0x01bd,V(27));a(0x000a,V(27),I(1500));a(6,V(25),I(-1));a(6,V(26),I(0));a(6,V(30),I(0));a(6,V(18),I(0))
s.label('ACTIVE');a(1,I(500));s.check(0x0256,[I(0)],'CLEANUP');s.check(0x056e,[V(1)],'CLEANUP');s.check(0x8119,[V(1)],'CLEANUP');s.check(0x056d,[V(0)],'CLEANUP');s.get(19,b.STATE);s.eq(19,3,'CLEANUP');s.get(19,b.ROPE_COMMAND);s.eq(19,1,'CONTINUE');s.set(b.ROPE_COMMAND,0);s.go('CLEANUP')
s.label('CONTINUE');a(0x01bd,V(19))
# Refresh a fifth rope while waiting; the invisible temporary actor only provides the rope visual.
s.check(0x001d,[V(19),V(18)],'PICKUP_GATE')
s.check(0x056d,[V(17)],'FIFTH_NEW');a(0x009b,V(17))
s.label('FIFTH_NEW');a(0x0407,V(1),F(0),F(-3.0),F(-1),V(10),V(11),V(12));a(0x0503,I(8),I(285),V(10),V(11),V(12),V(17));a(0xddc,I(b.GROUND_PUB+4),V(17));s.check(0x056d,[V(17)],'FIFTH_NEXT');a(0x0337,V(17),I(0));a(0x0619,V(17),I(0));a(0x048f,V(17))
s.label('FIFTH_NEXT');a(0x01bd,V(18));a(0x000a,V(18),I(2500))
s.label('PICKUP_GATE');a(0x01bd,V(19));s.check(0x001d,[V(19),V(27)],'ACTIVE')
s.label('PICKUP_CHECK')
# Do not interrupt a descending guard: enter only after all living guards are on the ground.
for var in [20,21,22,23]:
 skip='PICKUP_LANDED_SKIP_'+str(var);s.check(0x056d,[V(var)],skip);s.check(0x8118,[V(var)],skip);a(0x0819,V(var),V(19));s.check(0x0023,[F(2.5),V(19)],'UPDATE_FIRE');s.label(skip)
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
 s.eq(28,1,walk);s.check(0x056d,[V(24)],walk);s.check(0x8118,[V(24)],walk);s.eq(31,1,skip);a(0x074d,V(var),V(24),I(2000));s.go(skip)
 s.label(walk);a(0x04c4,V(0),F(x),F(y),F(0),V(10),V(11),V(12));a(0x00a0,V(var),V(13),V(14),V(15));a(0x050a,V(10),V(11),V(12),V(13),V(14),V(15),V(16));s.check(0x0021,[V(16),F(3)],watch);s.eq(7,1,skip);a(0x04eb,V(var),I(0));a(0x05d3,V(var),V(10),V(11),V(12),I(6),I(1800));s.go(skip);s.label(watch);a(0x04eb,V(var),I(1));s.label(skip)
s.go('ACTIVE')
# The reverse clip is cosmetic; vertical position is moved explicitly.
s.label('CJ_ASCENT');s.check(0x0431,[V(1),I(0)],'NO_SEAT');s.check(0x04ee,[S('PED')],'ANIM_FAIL');s.check(0x056e,[V(1)],'CLEANUP');s.get(19,b.STATE);s.eq(19,3,'CLEANUP')
# Save a ground position for cancellation and disable player control only during ascent.
a(0x0407,V(1),F(0),F(-3),F(-1),V(2),V(3),V(4));a(0x02ce,V(2),V(3),V(4),V(4));a(0x000b,V(4),F(.7));a(0x0087,V(8),V(4));a(0x00aa,V(1),V(10),V(11),V(9));a(0x000b,V(9),F(-1));a(0x0063,V(9),V(8));a(0x0013,V(9),F(1000.0/1800.0));a(0x01b4,I(0),I(0));a(6,V(26),I(1));a(0x00a1,V(0),V(2),V(3),V(8));a(0x0605,V(0),S('ABSEIL'),S('PED'),F(4),I(1),I(1),I(1),I(1),I(-1));a(1,I(100));s.check(0x0611,[V(0),S('ABSEIL')],'CJ_ANIM_NOT_RUNNING');a(0x0614,V(0),S('ABSEIL'),F(.99));a(0x0393,V(0),S('ABSEIL'),F(-1));s.label('CJ_ANIM_NOT_RUNNING');a(0x01bd,V(16));a(0x03e5,S('RGUP'))
s.label('CJ_UP_TICK');a(1,I(0));s.check(0x0256,[I(0)],'ASCENT_ABORT');s.check(0x056d,[V(0)],'ASCENT_ABORT');s.check(0x8118,[V(0)],'ASCENT_ABORT');s.check(0x056e,[V(1)],'ASCENT_ABORT');s.check(0x8119,[V(1)],'ASCENT_ABORT');s.get(19,b.STATE);s.eq(19,3,'ASCENT_ABORT');a(0x01bd,V(15));a(0x0062,V(15),V(16));s.check(0x0019,[V(15),I(1800)],'CJ_TIME_READY');a(6,V(15),I(1800));s.label('CJ_TIME_READY');s.check(0x0611,[V(0),S('ABSEIL')],'CJ_FRAME_ANIM_SKIP');a(0x0093,V(11),V(15));a(0x0013,V(11),F(1.0/1800.0));a(0x0007,V(12),F(1));a(0x0063,V(12),V(11));a(0x0614,V(0),S('ABSEIL'),V(12));s.label('CJ_FRAME_ANIM_SKIP');a(0x083c,V(0),F(0),F(0),V(9));s.check(0x0019,[V(15),I(1799)],'CJ_UP_TICK');a(0x083c,V(0),F(0),F(0),F(0));s.check(0x0431,[V(1),I(0)],'ASCENT_ABORT');a(0x0430,V(0),V(1),I(0));s.check(0x0448,[V(0),V(1)],'ASCENT_ABORT');a(0x01b4,I(0),I(1));a(6,V(26),I(0));a(0x03e5,S('RGABO'))
# After CJ is aboard the extra four run to distinct ropes, ascend, then disappear.
for var,x,y in [(20,-1.5,1.2),(21,1.5,1.2),(22,-1.5,-1.2),(23,1.5,-1.2)]:
 end='GUARD_UP_DONE_'+str(var);approach='GUARD_APPROACH_'+str(var);ready='GUARD_READY_'+str(var);loop='GUARD_ASCEND_'+str(var);newrope='GUARD_ROPE_NEW_'+str(var)
 s.check(0x056d,[V(var)],end);s.check(0x8118,[V(var)],end);a(0x0407,V(1),F(x),F(y),F(-1),V(2),V(3),V(4));a(0x02ce,V(2),V(3),V(4),V(4));a(0x000b,V(4),F(.7));a(0x01bd,V(18));a(0x000a,V(18),I(8000))
 s.label(approach);a(1,I(500));s.check(0x0256,[I(0)],'CLEANUP');s.check(0x056e,[V(1)],'CLEANUP');s.check(0x8119,[V(1)],'CLEANUP');s.get(19,b.STATE);s.eq(19,3,'CLEANUP');s.check(0x056d,[V(var)],end);s.check(0x8118,[V(var)],end);a(0x00a0,V(var),V(10),V(11),V(12));a(0x050a,V(2),V(3),V(4),V(10),V(11),V(12),V(15));s.check(0x0023,[F(2),V(15)],'GUARD_NOT_AT_'+str(var));s.go(ready)
 s.label('GUARD_NOT_AT_'+str(var));a(0x01bd,V(19));s.check(0x001d,[V(19),V(18)],'GUARD_WALK_'+str(var));s.go(end);s.label('GUARD_WALK_'+str(var));a(0x04eb,V(var),I(0));a(0x05d3,V(var),V(2),V(3),V(4),I(6),I(1200));s.go(approach)
 s.label(ready);s.check(0x056d,[V(17)],newrope);a(0x009b,V(17));s.label(newrope);a(0x0407,V(1),F(x),F(y),F(-1),V(10),V(11),V(12));a(0x0503,I(8),I(285),V(10),V(11),V(12),V(17));a(0xddc,I(b.GROUND_PUB+4),V(17));s.check(0x056d,[V(17)],'GUARD_NOROPE_'+str(var));a(0x0337,V(17),I(0));a(0x0619,V(17),I(0));s.label('GUARD_NOROPE_'+str(var));a(0x0087,V(8),V(4));a(0x00aa,V(1),V(10),V(11),V(9));a(0x000b,V(9),F(-1));a(0x0063,V(9),V(8));a(0x0013,V(9),F(1000.0/1800.0));a(0x00a1,V(var),V(2),V(3),V(8));a(0x0605,V(var),S('ABSEIL'),S('PED'),F(4),I(1),I(1),I(1),I(1),I(-1));a(1,I(100));s.check(0x0611,[V(var),S('ABSEIL')],'GUARD_ANIM_NOT_RUNNING_'+str(var));a(0x0614,V(var),S('ABSEIL'),F(.99));a(0x0393,V(var),S('ABSEIL'),F(-1));s.label('GUARD_ANIM_NOT_RUNNING_'+str(var));a(0x01bd,V(16))
 s.label(loop);a(1,I(0));s.check(0x0256,[I(0)],'CLEANUP');s.check(0x056e,[V(1)],'CLEANUP');s.check(0x8119,[V(1)],'CLEANUP');s.get(19,b.STATE);s.eq(19,3,'CLEANUP');s.check(0x056d,[V(var)],end);s.check(0x8118,[V(var)],end);a(0x01bd,V(15));a(0x0062,V(15),V(16));s.check(0x0019,[V(15),I(1800)],'GUARD_TIME_READY_'+str(var));a(6,V(15),I(1800));s.label('GUARD_TIME_READY_'+str(var));s.check(0x0611,[V(var),S('ABSEIL')],'GUARD_FRAME_ANIM_SKIP_'+str(var));a(0x0093,V(11),V(15));a(0x0013,V(11),F(1.0/1800.0));a(0x0007,V(12),F(1));a(0x0063,V(12),V(11));a(0x0614,V(var),S('ABSEIL'),V(12));s.label('GUARD_FRAME_ANIM_SKIP_'+str(var));a(0x083c,V(var),F(0),F(0),V(9));s.check(0x0019,[V(15),I(1799)],loop);a(0x083c,V(var),F(0),F(0),F(0))
 s.label(end);s.set(b.GROUND_PUB+var-20,-1);s.check(0x056d,[V(var)],'GUARD_REMOVED_'+str(var));a(0x009b,V(var));s.label('GUARD_REMOVED_'+str(var))
s.go('CLEANUP')
s.label('ASCENT_ABORT');s.eq(26,1,'CLEANUP');s.check(0x056d,[V(0)],'ASCENT_RESTORE');s.check(0x8118,[V(0)],'ASCENT_RESTORE');a(0x00a1,V(0),V(2),V(3),V(4))
s.label('ASCENT_RESTORE');a(0x01b4,I(0),I(1));a(6,V(26),I(0));s.go('CLEANUP')
s.label('NO_SEAT');a(0x03e5,S('RGSEAT'));s.go('ACTIVE')
s.label('ANIM_FAIL');a(0x03e5,S('RGANIM'));s.go('CLEANUP')
s.label('CLEANUP');s.eq(26,1,'CLEANUP_CONTROL_DONE');a(0x01b4,I(0),I(1));a(6,V(26),I(0));s.label('CLEANUP_CONTROL_DONE');s.check(0x056d,[V(17)],'CLEANUP_ROPE_DONE');a(0x009b,V(17));s.label('CLEANUP_ROPE_DONE');s.set(b.GROUND_PUB+4,-1);s.check(0x056e,[V(1)],'CLEANUP_HELI_DONE');a(0x0574,V(1),I(0));s.set(b.FROZEN,0);s.label('CLEANUP_HELI_DONE')
for i,var in enumerate([20,21,22,23]):
 skip='DELETE_'+str(var);s.set(b.GROUND_PUB+i,-1);s.check(0x056d,[V(var)],skip);a(0x009b,V(var));s.label(skip)
a(0x0249,I(285));a(0x03e5,S('RGDONE'));s.go('WAIT')
s.label('DROP_START');a(6,V(26),I(0));s.get(19,b.STATE);s.eq(19,23,'DROP_FAIL');s.get(1,b.PUB+1);s.get(0,b.PUB);s.check(0x0256,[I(0)],'WAIT');s.check(0x056e,[V(1)],'DROP_FAIL');s.check(0x8119,[V(1)],'DROP_FAIL');s.check(0x056d,[V(0)],'DROP_FAIL');s.check(0x0448,[V(0),V(1)],'DROP_FAIL');a(0x0407,V(1),F(0),F(-3),F(-1),V(2),V(3),V(8));a(0x02ce,V(2),V(3),V(8),V(4));a(0x000b,V(4),F(.7));a(0x0087,V(9),V(8));a(0x0063,V(9),V(4));s.check(0x0021,[V(9),F(8)],'DROP_FAIL');s.check(0x0023,[F(24),V(9)],'DROP_FAIL');a(0x0087,V(10),V(4));a(0x000b,V(10),F(1));s.check(0x06bd,[V(2),V(3),V(10),V(2),V(3),V(8),I(1),I(0),I(0),I(1),I(0)],'DROP_FAIL');a(0x0247,I(285));a(6,V(26),I(1));a(0x038b);a(1,I(0));s.check(0x0248,[I(285)],'DROP_FAIL');s.check(0x056e,[V(1)],'DROP_FAIL');a(0x0574,V(1),I(1));s.set(b.FROZEN,1);a(6,V(17),I(-1));a(0x0503,I(8),I(285),V(2),V(3),V(8),V(17));s.check(0x056d,[V(17)],'DROP_FAIL_UNFREEZE');a(0x0337,V(17),I(0));a(0x0619,V(17),I(0));a(0xddc,I(b.GROUND_PUB+4),V(17));a(0x01b4,I(0),I(0))
# v28: 1 m below the frozen helicopter's centre is inside its hull, which held CJ until the
# final ground warp ("teleport"). Start 3 m lower, below the skids, and recompute the descent speed.
a(0x000b,V(8),F(-2));a(0x0087,V(9),V(8));a(0x0063,V(9),V(4));a(0x0362,V(0),V(2),V(3),V(8));s.check(0x04ee,[S('PED')],'DROP_ANIM_SKIP');a(0x0605,V(0),S('ABSEIL'),S('PED'),F(4),I(1),I(1),I(1),I(1),I(-1));s.label('DROP_ANIM_SKIP');a(0x0013,V(9),F(-1000.0/2200.0));a(0x01bd,V(16))
s.label('DROP_TICK');a(1,I(0));s.check(0x0256,[I(0)],'DROP_ABORT');s.check(0x056d,[V(0)],'DROP_ABORT');s.check(0x8118,[V(0)],'DROP_ABORT');s.check(0x056e,[V(1)],'DROP_ABORT');s.get(19,b.STATE);s.eq(19,23,'DROP_ABORT');a(0x01bd,V(15));a(0x0062,V(15),V(16));s.check(0x0019,[V(15),I(2200)],'DROP_TIME_READY');a(6,V(15),I(2200));s.label('DROP_TIME_READY');a(0x083c,V(0),F(0),F(0),V(9));s.check(0x0019,[V(15),I(2199)],'DROP_TICK');a(0x083c,V(0),F(0),F(0),F(0));a(0x00a1,V(0),V(2),V(3),V(4));a(0x01b4,I(0),I(1));s.check(0x056d,[V(17)],'DROP_NO_DUMMY');a(0x009b,V(17));s.label('DROP_NO_DUMMY');s.set(b.GROUND_PUB+4,-1);a(0x0574,V(1),I(0));s.set(b.FROZEN,0);s.set(b.STATE,3);a(0x0249,I(285));s.go('WAIT')
s.label('DROP_ABORT');s.check(0x056d,[V(0)],'DROP_ABORT_CONTROL');s.check(0x8118,[V(0)],'DROP_ABORT_CONTROL');a(0x00a1,V(0),V(2),V(3),V(4));s.label('DROP_ABORT_CONTROL');a(0x01b4,I(0),I(1));s.check(0x056d,[V(17)],'DROP_FAIL_UNFREEZE');a(0x009b,V(17))
s.label('DROP_FAIL_UNFREEZE');s.set(b.GROUND_PUB+4,-1);s.check(0x056e,[V(1)],'DROP_FAIL');a(0x0574,V(1),I(0));s.set(b.FROZEN,0)
s.label('DROP_FAIL');s.eq(26,1,'DROP_FAIL_NO_MODEL');a(0x0249,I(285));s.label('DROP_FAIL_NO_MODEL');a(0x03e5,S('RPDFAIL'));s.go('WAIT')

s.label('LOAD_FAILED');a(0x0249,I(285));a(0x03e5,S('RGFAIL'));s.go('WAIT')
s.label('NOHOLD');a(0x03e5,S('RGHOLD'));s.go('WAIT')
s.label('ALTITUDE');a(0x03e5,S('RGHIGH'));s.go('WAIT')
s.label('MOVING');a(0x03e5,S('RGMOVE'));s.go('WAIT')
s.label('BLOCKED');a(0x03e5,S('RGBLOCK'));s.go('WAIT')
if __name__=='__main__':
 report=s.build('Helicover_Ground','csa');print(report)
 with (OUT/'validation.txt').open('a') as validation:validation.write(report+'\n')
 with (OUT/'Helicover.fxt').open('a') as f:f.write('RGDEP SWAT: descending. Stay near the helicopter.\nRGDONE SWAT: ground team withdrawn.\nRGFAIL SWAT: model unavailable or heli moving.\nRGHOLD SWAT: use HOLD POSITION first.\nRGHIGH SWAT: heli must hover 12-22m above ground.\nRGMOVE SWAT: wait until the helicopter is nearly still.\nRGBLOCK SWAT: choose a clear open area.\nRGUP EVAC: ascending.\nRGABO EVAC: aboard. Team returning.\nRGSEAT EVAC: passenger seat unavailable.\nRGANIM EVAC: animation unavailable.\nRPDFAIL EVAC: rope descent unavailable here.\n')
