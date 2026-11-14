from asm_v25 import *
from pathlib import Path
import zipfile
# Separate namespace from v2; settings are session-local and survive new calls.
STATE=0x48456A00;CMD=STATE+1;HEART=STATE+2;OPEN=STATE+3;PANELHEART=STATE+4
MODEL=STATE+5;CREW=STATE+6;FIRE=STATE+7;TOUCH=STATE+8;HUD=STATE+9;HP=STATE+10
PUB=STATE+20;PHASE=STATE+27;ACTUAL=STATE+28;BUSY=STATE+29;FIREHEART=STATE+30;WPN=STATE+31;FIRENEXT=STATE+32
ACREW=STATE+33;LSTAGE=STATE+34;LALT=STATE+35;FROZEN=STATE+36;SKINSAVE=STATE+37;CREWNEW=STATE+40;CREWGEN=STATE+45;FIREGEN=STATE+46;FWANTED=STATE+47
GROVE_STREAM=STATE+50;GROVE_WAIT=STATE+51;LAND_STABLE=STATE+53;GROVE_NEXT_SCAN=STATE+54
FIRE_TARGET=STATE+55;FIRE_TASK_TARGET=STATE+56;FIRE_TASK_PHASE=STATE+57;FIRE_TASK_NEXT=STATE+58
FIRE_ACTIVE=STATE+59;TRACKED_TARGET=STATE+60;FIRE_SCAN_NEXT=STATE+61;FIRE_TASK_MODE=STATE+62
LAND_SLOW=STATE+63;LAND_FINAL=STATE+64
WEAPON_SETTING=STATE+65
ROPE_COMMAND=STATE+70;GROUND_PUB=STATE+71;GROUND_MOVE_NEXT=STATE+80;DROP_COMMAND=STATE+81;DEST_X=STATE+82;DEST_Y=STATE+83;DEST_Z=STATE+84;GUARD_TARGET=STATE+90;PATROL_STEP=STATE+97;PATROL_NEXT=STATE+98;FOLLOW_NEXT=STATE+99;AVOID_STAGE=STATE+110;AVOID_NEXT=STATE+111;AVOID_AT=STATE+112;AVOID_X=STATE+113;AVOID_Y=STATE+114;AVOID_Z=STATE+115
GLIDE_C=STATE+116;STUCK_SINCE=STATE+117
# v36 diagnostic breadcrumbs: 'DBG state*100+step' is printed whenever it changes, so a screenshot
# of a frozen screen shows where the core was. Set DEBUG_BREADCRUMBS=False for a quiet build.
DEBUG_BREADCRUMBS=False;DBG_CODE=STATE+130;DBG_LAST=STATE+131
DEST_NATIVE=STATE+133  # v37: 1 once the native pilot owns the final descent
# v39 exit button: EXIT_MODE 0 = land then leave, 1 = rope descent. AUTO_EXIT 1 = get out on
# arrival over the destination, 2 = leave right after the landing. LOCK_HOLD = time until which
# the doors stay unlocked so CJ's own leave-car task can finish.
EXIT_MODE=STATE+134;AUTO_EXIT=STATE+135;LOCK_HOLD=STATE+136
# v39-fire fire control: kill counter, current engaged target, engagement flag, area-clear timer,
# combat-orbit point index and next switch time.
KILLS=STATE+137;LAST_TGT=STATE+138;ENGAGED=STATE+139;CLEAR_AT=STATE+140;ORBIT_I=STATE+141;ORBIT_NEXT=STATE+142
OVERWATCH_DAMAGE=75;OVERWATCH_CADENCE=900;ORBIT_RADIUS=28.0
EXIT_WIDGET=0  # CTouchInterface widget of the on-screen enter/exit vehicle button (CPad::ExitVehicleJustDown)
CRUISE_T=STATE+118;CR_UP=STATE+119;CR_DN=STATE+120
CR_CMDZ=STATE+128  # v33: commanded z, integrated by steps (never rebuilt from the actual z)
CR_DT=STATE+121;CR_V=STATE+122;CR_VT=STATE+123;CR_SLOW=STATE+124;CR_DX=STATE+125;CR_DY=STATE+126;CR_DZ=STATE+127
# v32 scripted cruise for map/Grove flights: per-frame, time-based, with acceleration,
# braking, rate-limited turning and smooth altitude changes (no jerks, no circling).
CRUISE_SPEED=70.0;CRUISE_ACCEL=22.0;CRUISE_BRAKE=35.0;CRUISE_TURN=90.0
CRUISE_CLIMB=30.0;CRUISE_SINK=18.0;CRUISE_CLEAR=35.0;HOVER_SINK=10.0
# 0AB6 GET_TARGET_BLIP_COORDS is a CLEO 4 PC opcode; CLEO Android crashes on it.
# v29 reads the waypoint straight from libGTASA memory with CLEO Android 0DD8 instead.
# Offsets come from the user's arm64 libGTASA.so (DWARF + disassembly of
# CRadar::GetActualBlipArrayIndex and PlaceRedMarker); another game version needs new offsets.
MAP_MARKER=True
# v30: the mobile map does not use FrontEndMenuManager.waypoint_blip. PlaceRedMarker()
# stores the SetCoordBlip handle in gMobileMenu+0x68 and clears it to 0 (0 = none).
WAYPOINT_OFS=0x8BE780+0x68   # gMobileMenu waypoint blip handle (int32, 0 = none)
RADAR_TRACE_OFS=0xC21728     # CRadar::ms_RadarTrace[250], 48 bytes each

GROVE_X=2492.0;GROVE_Y=-1666.0
STATES={25:'MAP CLIMB',24:'PATROLLING',21:'TO MAP POINT',22:'DEST APPROACH',23:'AWAITING EXIT',20:'CLIMB TO GROVE',19:'ROPE APPROACH',17:'CHANGING CREW',18:'LANDING BLOCKED',16:'CHANGING HELI',0:'READY',1:'LOADING',2:'FOLLOWING',3:'HOLDING',4:'DEPARTING',5:'LOAD FAILED',6:'GO OUTDOORS',7:'EVAC INBOUND',8:'TEAM COVERING',9:'CJ ON BOARD',10:'TO GROVE STREET',11:'GROVE LANDING',12:'LANDED',13:'DAMAGED / RTB',14:'TEAM BOARDING',15:'EMERGENCY LAND'}
MESSAGES={
 'HCLOAD':'~b~HELICOVER~w~: support inbound.', 'HCFOLL':'~g~HELICOVER~w~: following CJ.',
 'HCHOLD':'~b~HELICOVER~w~: holding position.', 'HCDEPT':'~b~HELICOVER~w~: departing.',
 'HCFAIL':'~r~HELICOVER~w~: model load failed. Try again.', 'HCOUT':'~y~HELICOVER~w~: move outdoors to call support.',
 'HCRWAIT':'~y~EVAC~w~: unable to reach a safe hover. Move to open ground and retry.',
 'HCGCLMB':'~y~EVAC~w~: cannot climb safely. Clear obstacles and retry.',
 'HCMAPOF':'~y~EVAC~w~: map marker flight is disabled: it crashes CLEO Android.',
 'HCDBG':'DBG ~1~',
 'HCNEED':'~y~HELICOVER~w~: call support first (HELICOVER > CALL SUPPORT).',
 'HCNOMAP':'~y~EVAC~w~: place a destination marker on the map first.',
 'HCCHOS':'~g~EVAC~w~: above destination. Press the exit button to get out.',
 'HCCONT':'~r~CONTACT!~w~ Door gunners engaging.',
 'HCKILL':'~g~TARGET DOWN~w~ - kills: ~1~',
 'HCCLEAR':'~g~AREA CLEAR.~w~ Gunners holding.',
 'HCFM0':'~y~CEASE FIRE~w~: gunners stand down.',
 'HCFM1':'~r~WEAPONS FREE~w~: engage everything except the team.',
 'HCFM2':'~b~FOLLOW YOUR LEAD~w~: gunners fire on your targets.',
 'HCFM3':'~g~PROTECT CJ~w~: engaging threats to CJ.',
 'HCFM4':'~p~OVERWATCH~w~: precision fire on armed hostiles.',
 'HCXHERE':'~g~EVAC~w~: getting out here. Finding a clear spot below.',
 'HCXARR':'~g~EVAC~w~: you will get out on arrival.',
 'HCXWAIT':'~y~EVAC~w~: wait until the helicopter lands or hovers.',
 'HCDWAIT':'~y~EVAC~w~: wait until the helicopter reaches the destination.',
 'HCPAT':'~b~HELICOVER~w~: patrolling around CJ.',
 'HCAVOID':'~y~HELICOVER~w~: path blocked; holding for a clear route.',
 'HCROPE':'~b~EVAC~w~: helicopter approaching for rope pickup.',
 'HCEVAC':'~b~EVAC~w~: landing nearby. Choose open, level ground.',
 'HCTEAM':'~g~EVAC~w~: flank team deployed. Use BOARD CJ when close.',
 'HCBOARD':'~g~EVAC~w~: CJ aboard. GROVE STREET recalls the team, then takes off.',
 'HCGROVE':'~g~EVAC~w~: team aboard. Heading to the Grove Street circle.',
 'HCHOME':'~b~EVAC~w~: approaching Grove Street.', 'HCARRIV':'~g~EVAC~w~: landed. LEAVE HELICOPTER lets CJ out.',
 'HCDAMAG':'~r~HELICOVER~w~: critical damage. Retreating.',
 'HCMUST':'~b~EVAC~w~: team returning. Departure waits for living guards.',
 'HCEMERG':'~r~EVAC~w~: critical damage. Attempting a nearby emergency landing.',
 'HCNOSEA':'~y~EVAC~w~: Hunter has no passenger seat. Use Maverick or Police Maverick.',
 'HCNOSIT':'~y~EVAC~w~: landing site is obstructed or uneven. Move to open ground and retry.',
 'HCFAR':'~y~EVAC~w~: get within 12 metres of the landed helicopter.',
 'HCWAIT':'~y~EVAC~w~: waiting for the flank team. Clear their path or repeat the command.',
 'HCIN':'~y~EVAC~w~: CJ must be sitting in the helicopter before flying to Grove Street.',
 'HCOFF':'~r~HELICOVER~w~: copy all four script files, then restart the game.',
 'HCTAP':'~b~HELICOVER~w~: release, then tap the exact screen centre to open the panel.',
 'HCSWAP':'~b~HELICOVER~w~: helicopter changed. Crew and CJ transferred.',
 'HCSNO':'~y~HELICOVER~w~: Hunter has no passenger seat. CJ must leave first.',
 'HCSFAIL':'~r~HELICOVER~w~: change failed; the current helicopter was kept.',
 'HCCREW':'~g~HELICOVER~w~: crew changed in place.',
 'HCCFAIL':'~r~HELICOVER~w~: crew change failed. Existing crew kept.',
 'HCBLOCK':'~y~EVAC~w~: landing unavailable. Clear the area and retry or choose FOLLOW CJ.',
 'HCLOSE':'~y~EVAC~w~: land first before boarding or leaving.',
 'HCEXIT':'~y~EVAC~w~: exit the helicopter before TAKE OFF / FOLLOW.',
}
# Generate state updates; panel prints messages when the state changes.
def state(s,n):s.set(STATE,n)
def msg(s,key):
 label='MSG_END_'+str(len(s.rows));s.get(19,HUD);s.eq(19,1,label);s.add(0x03e5,S(key));s.label(label)
def alive(s,var,fail):s.check(0x056d,[V(var)],fail);s.check(0x8118,[V(var)],fail)
def healthcheck(s,fail):
 s.check(0x0256,[I(0)],fail);s.check(0x056e,[V(5)],fail);alive(s,4,fail);s.check(0x8119,[V(5)],fail)

c=Script();a=c.add
c.label('INIT');a(0);c.set(AVOID_STAGE,0);c.set(AVOID_NEXT,0);c.set(BUSY,0);c.set(FROZEN,0);c.set(LSTAGE,0);c.set(CREWGEN,0);c.set(FIRE_TARGET,-1);c.set(FIRE_ACTIVE,0);c.set(TRACKED_TARGET,-1);c.set(STUCK_SINCE,0)
for key in range(PUB,PUB+7):c.set(key,-1)
for key in range(GROUND_PUB,GROUND_PUB+5):c.set(key,-1)
c.set(ROPE_COMMAND,0)
for key,val in [(STATE,0),(CMD,0),(OPEN,0),(MODEL,487),(CREW,2),(FIRE,0),(TOUCH,0),(HUD,1),(HP,0),(WEAPON_SETTING,0),(EXIT_MODE,0),(AUTO_EXIT,0),(LOCK_HOLD,0),(KILLS,0),(LAST_TGT,-1),(ENGAGED,0),(CLEAR_AT,0),(ORBIT_I,0),(ORBIT_NEXT,0)]:c.set(key,val)
c.label('IDLE');a(1,I(100));a(0x01bd,V(20));a(0xddc,I(HEART),V(20));c.get(8,CMD);c.set(CMD,0)
c.eq(8,1,'IDLE_EVAC');a(6,V(25),I(0));c.go('LOAD')
# v38: evacuation commands no longer summon support on their own; they ask for CALL SUPPORT first.
c.label('IDLE_EVAC')
for cmd in [5,6,7,8,9,10,11,12,13]:
 nxt='IDLE_NEED_'+str(cmd);c.eq(8,cmd,nxt);msg(c,'HCNEED');c.go('IDLE');c.label(nxt)
c.label('IDLE_PATROL');c.eq(8,14,'IDLE');a(6,V(25),I(12))
c.label('LOAD');c.check(0x0256,[I(0)],'IDLE');a(0x077e,V(17));c.eq(17,0,'OUTDOORS');state(c,1)
a(0x01f5,I(0),V(18));c.get(0,MODEL);c.get(19,CREW)
a(6,V(1),I(105));a(6,V(2),I(106));a(6,V(3),I(107))
c.eq(19,1,'CREW_SWAT');a(6,V(1),I(287));a(6,V(2),I(287));a(6,V(3),I(287));c.go('CREW_READY')
c.label('CREW_SWAT');c.eq(19,2,'CREW_READY');a(6,V(1),I(285));a(6,V(2),I(285));a(6,V(3),I(285))
c.label('CREW_READY');c.eq(25,5,'REQUEST_MODELS');c.eq(0,425,'REQUEST_MODELS');a(6,V(0),I(487));c.set(MODEL,487)
c.label('REQUEST_MODELS')
for v in [0,1,2,3]:a(0x0247,V(v))
for weapon_model in [353,355,356,358]:a(0x0247,I(weapon_model))
a(0x038b);a(1,I(0));a(0xd6,I(7))
for v in [0,1,2,3]:a(0x0248,V(v))
for weapon_model in [353,355,356,358]:a(0x0248,I(weapon_model))
a(0x4d,L('MODEL_FAIL'));c.check(0x0256,[I(0)],'MODEL_FAIL')
for v in [4,5,12,13,14,15,16,31]:a(6,V(v),I(-1))
a(6,V(24),I(0));a(6,V(22),I(0));a(0x04c4,V(18),F(0),F(-45),F(28),V(9),V(10),V(11))
# v28: in downtown CJ+28 m is inside tall buildings; spawn at least 20 m above the highest surface.
a(0x02ce,V(9),V(10),F(1000),V(17));a(0x000b,V(17),F(20));c.check(0x0025,[V(17),V(11)],'SPAWN_Z_OK');a(0x0087,V(11),V(17));c.label('SPAWN_Z_OK')
a(0x00a5,V(0),V(9),V(10),V(11),V(5));a(0x00a0,V(18),V(9),V(10),V(11));a(0x039f,V(5),V(9),V(10));a(0x0129,V(5),I(8),V(1),V(4));a(0x01c5,V(4));a(0x08af,V(4),I(200));a(0x0223,V(4),I(200));a(0x054a,V(4),I(1));a(0x0446,V(4),I(1));a(0x077a,V(4),I(0),I(0))
a(0x0186,V(5),V(12));a(0x0168,V(12),I(2));a(0x0165,V(12),I(2));a(0x07e0,V(12),I(1));a(0x0957,V(5),I(1))
for v,skin in [(13,2),(14,3),(15,2),(16,3)]:
 # Four guards are retained for all models, including four external Hunter positions.
 a(0x009a,I(8),V(skin),V(9),V(10),V(11),V(v));a(0x01c5,V(v));a(0x08af,V(v),I(150));a(0x0223,V(v),I(150));a(0x035f,V(v),I(50));a(0x054a,V(v),I(1));a(0x0446,V(v),I(1));a(0x02e2,V(v),I(100))
 for typ in range(32):a(0x077a,V(v),I(2),I(typ))
 a(0x077a,V(v),I(0),I(0));a(0x077a,V(v),I(0),I(8))
c.label('TEAM_READY');c.call('PUBLISH');a(0x0825,V(5));a(0x07bb,V(5),I(6));a(6,V(23),I(-1));c.call('REATTACH_TEAM');c.call('APPLY_FIRE')
for v in [0,1,2,3]:a(0x0249,V(v))
c.eq(25,5,'TEAM_CHECK_ROPE');c.go('EVAC')
c.label('TEAM_CHECK_ROPE');c.eq(25,11,'TEAM_CHECK_PATROL');c.go('ROPE_PREP')
c.label('TEAM_CHECK_PATROL');c.eq(25,12,'FOLLOW');c.go('PATROL_START')
# v34: per-frame ticks only while the script itself moves the helicopter (cruise, glide, descent);
# long frozen holds (awaiting a choice, rope work) go back to the normal 100 ms tick.
c.label('TICK');c.get(19,FROZEN);c.eq(19,1,'TICK_NORMAL_WAIT');c.get(19,STATE)
for st in [10,19,21,22]:
 nxt='TICK_FAST_NOT_'+str(st);c.eq(19,st,nxt);a(1,I(0));c.go('TICK_AFTER_WAIT');c.label(nxt)
c.label('TICK_NORMAL_WAIT');a(1,I(100))
c.label('TICK_AFTER_WAIT')
if DEBUG_BREADCRUMBS:
 c.get(19,STATE);a(0x0012,V(19),I(100));c.get(17,DBG_CODE);a(0x005a,V(19),V(17));c.get(17,DBG_LAST);c.check(0x803b,[V(19),V(17)],'DBG_SAME');a(0x01e5,S('HCDBG'),V(19),I(600000),I(1));a(0xddc,I(DBG_LAST),V(19));c.label('DBG_SAME')
a(0x01bd,V(20));a(0xddc,I(HEART),V(20));healthcheck(c,'CLEANUP');c.call('CHANGE_MODEL');c.call('CHANGE_CREW');c.call('PUBLISH');c.get(7,STATE);a(0x0227,V(5),V(6));a(0xddc,I(HP),V(6));c.call('TRACK_COMBAT');c.call('FLIGHT_AVOID');c.call('UNSTICK');c.call('EXIT_BUTTON');c.get(7,STATE)
c.get(19,FIRE);c.check(0x003b,[V(19),V(23)],'UPDATE_FIRE');c.go('HEALTH')
c.label('UPDATE_FIRE');c.call('APPLY_FIRE')
c.label('HEALTH');c.eq(7,15,'HEALTH_LANDED_CHECK');c.go('DISPATCH')
c.label('HEALTH_LANDED_CHECK');c.eq(7,12,'CHECK_HEALTH');c.go('DISPATCH')
c.label('CHECK_HEALTH');c.check(0x0019,[V(6),I(350)],'LOW_HEALTH');c.go('DISPATCH')
c.label('LOW_HEALTH');c.check(0x80db,[V(18),V(5)],'EMERGENCY');c.eq(24,0,'EMERGENCY');a(6,V(25),I(13));c.go('DEPART')
c.label('DISPATCH');c.get(8,CMD);c.set(CMD,0)
for command,label in [(15,'REQUEST_EXIT'),(2,'REQUEST_FOLLOW'),(3,'REQUEST_HOLD'),(4,'REQUEST_DEPART'),(5,'EVAC'),(6,'BOARD_CJ'),(7,'REQUEST_GROVE'),(8,'LEAVE_CJ'),(9,'REQUEST_TAKEOFF'),(10,'REQUEST_ROPE'),(11,'REQUEST_MAP'),(12,'REQUEST_DEST_LAND'),(13,'REQUEST_DEST_ROPE'),(14,'REQUEST_PATROL')]:
 nxt='CMD_NEXT_'+str(command);c.eq(8,command,nxt);c.go(label);c.label(nxt)
# Per-state continuous work.
for st,label in [(7,'LANDING_TICK'),(11,'LANDING_TICK'),(15,'LANDING_TICK'),(8,'GROUND_TICK'),(9,'GROUND_TICK'),(12,'GROUND_TICK'),(14,'MUSTER_TICK'),(10,'TRAVEL_TICK'),(19,'ROPE_APPROACH_TICK'),(20,'GROVE_CLIMB_TICK'),(21,'MAP_TRAVEL_TICK'),(22,'DEST_APPROACH_TICK'),(24,'PATROL_TICK'),(25,'MAP_CLIMB_TICK'),(2,'FOLLOW_TICK')]:
 nxt='STATE_NEXT_'+str(st);c.eq(7,st,nxt);c.go(label);c.label(nxt)
c.go('TICK')
for name,pending,target in [('FOLLOW',2,'FOLLOW'),('HOLD',3,'HOLD'),('DEPART',4,'DEPART')]:
 c.label('REQUEST_'+name)
 if name=='DEPART':
  c.check(0x80db,[V(18),V(5)],'REQUEST_GROVE')
 a(6,V(25),I(pending));c.eq(24,0,'START_MUSTER');c.go(target)
c.label('FOLLOW');c.call('UNFREEZE');c.check(0x80db,[V(18),V(5)],'HOLD');c.set(TRACKED_TARGET,-1);c.call('RESTORE_FLIGHT');a(0x0918,V(5),I(1));a(0x0825,V(5));a(0x04df,V(5),I(0));a(0x0726,V(5),V(18),I(-1),F(15));state(c,2);c.go('TICK')
c.label('FOLLOW_TICK');c.check(0x80db,[V(18),V(5)],'TICK');a(0x00a0,V(18),V(9),V(10),V(11));a(0x00aa,V(5),V(26),V(27),V(28));a(0x0509,V(9),V(10),V(26),V(27),V(31));c.check(0x0021,[V(31),F(60)],'TICK');c.get(19,FOLLOW_NEXT);c.check(0x001d,[V(20),V(19)],'TICK');a(0x0085,V(19),V(20));a(0x000a,V(19),I(4000));a(0xddc,I(FOLLOW_NEXT),V(19));a(0x07bb,V(5),I(6));a(0x0726,V(5),V(18),I(-1),F(15));c.go('TICK')

c.label('REQUEST_PATROL');c.check(0x80db,[V(18),V(5)],'PATROL_ABOARD');c.eq(24,0,'PATROL_MUSTER');c.go('PATROL_START')
c.label('PATROL_MUSTER');a(6,V(25),I(12));c.go('START_MUSTER')
c.label('PATROL_ABOARD');msg(c,'HCEXIT');c.go('TICK')
c.label('PATROL_START');c.call('UNFREEZE');c.call('RESTORE_FLIGHT');c.set(PATROL_STEP,0);c.set(PATROL_NEXT,0);c.set(TRACKED_TARGET,-1);state(c,24);c.go('TICK')
c.label('PATROL_TICK');c.check(0x80db,[V(18),V(5)],'PATROL_ABOARD');c.get(29,FIRE_TARGET);alive(c,29,'PATROL_NO_TARGET');c.go('TICK')
c.label('PATROL_NO_TARGET');c.get(19,PATROL_NEXT);c.check(0x001d,[V(20),V(19)],'TICK');a(0x0085,V(19),V(20));a(0x000a,V(19),I(4000));a(0xddc,I(PATROL_NEXT),V(19));c.get(19,PATROL_STEP)
for idx,(x,y) in enumerate([(0,25),(25,0),(0,-25),(-25,0)]):
 nxt='PATROL_NEXT_'+str(idx);c.eq(19,idx,nxt);a(0x04c4,V(18),F(x),F(y),F(25),V(9),V(10),V(11));c.go('PATROL_ISSUE');c.label(nxt)
a(6,V(19),I(0));a(0x04c4,V(18),F(0),F(25),F(25),V(9),V(10),V(11))
c.label('PATROL_ISSUE');a(0x000a,V(19),I(1));c.check(0x0019,[V(19),I(3)],'PATROL_STEP_SAVE');a(6,V(19),I(0));c.label('PATROL_STEP_SAVE');a(0xddc,I(PATROL_STEP),V(19));a(0x04df,V(5),I(0));a(0x04a2,V(5),V(9),V(10),V(11),F(15),V(11));a(0x00ad,V(5),F(25));c.go('TICK')
c.label('HOLD');a(0x0918,V(5),I(1));a(0x0825,V(5));c.call('BLOCK_HOVER');state(c,3);c.go('TICK')

# Flight to a clear hovering point 15m in front of CJ. The rope worker starts
# only after approach, height and speed checks have all passed.
c.label('REQUEST_ROPE');c.check(0x80db,[V(18),V(5)],'ROPE_CJ_ABOARD');c.eq(24,0,'ROPE_MUSTER');c.go('ROPE_PREP')
c.label('ROPE_MUSTER');a(6,V(25),I(11));c.go('START_MUSTER')
c.label('ROPE_CJ_ABOARD');msg(c,'HCEXIT');c.go('TICK')
c.label('ROPE_PREP');c.eq(0,425,'ROPE_SEATS');msg(c,'HCNOSEA');c.go('TICK')
c.label('ROPE_SEATS');a(0x01ea,V(5),V(19));c.check(0x0019,[V(19),I(0)],'NO_SEATS')
# v27: hover point = CJ + 3 m along the helicopter's heading, so the tail rope (0,-3) hangs on CJ.
a(0x00aa,V(5),V(9),V(10),V(11));a(0x0407,V(5),F(0),F(3),F(0),V(26),V(27),V(28));a(0x0063,V(26),V(9));a(0x0063,V(27),V(10))
a(0x00a0,V(18),V(9),V(10),V(28));a(0x005b,V(26),V(9));a(0x005b,V(27),V(10));a(0x000b,V(28),F(100));a(0x02ce,V(26),V(27),V(28),V(28));a(0x00a0,V(18),V(9),V(10),V(11));a(0x000b,V(11),F(26));a(0x02ce,V(9),V(10),V(11),V(31));a(0x0087,V(17),V(28));a(0x0063,V(17),V(31));c.check(0x0023,[F(5),V(17)],'BAD_SITE');c.check(0x0021,[V(17),F(-5)],'BAD_SITE');c.call('CHECK_SITE');c.eq(17,1,'BAD_SITE');c.call('UNFREEZE');c.call('RESTORE_FLIGHT');a(0x04df,V(5),I(0));a(0x0087,V(9),V(28));a(0x000b,V(9),F(15));a(0x0087,V(11),V(28));a(0x000b,V(11),F(15));a(0x0853,V(5),I(10));a(0x04a2,V(5),V(26),V(27),V(9),F(12),V(11));a(0x00ad,V(5),F(45));a(0x01bd,V(21));state(c,19);c.go('TICK')
# v27: the native autopilot circles around a 3-5 m target instead of stopping. Within
# 45 m (clear line of sight) freeze the helicopter and glide it by script at ~25 m/s
# straight to the hover point, then hand over to the rope worker while still frozen.
c.label('ROPE_APPROACH_TICK');a(0x00aa,V(5),V(9),V(10),V(11));c.get(19,FROZEN);c.eq(19,1,'ROPE_FAR');c.go('ROPE_GLIDE')
c.label('ROPE_FAR');a(0x0509,V(9),V(10),V(26),V(27),V(31));c.check(0x0023,[F(45),V(31)],'ROPE_APPROACH_TIMEOUT')
a(0x0087,V(19),V(28));a(0x000b,V(19),F(15));c.check(0x06bd,[V(9),V(10),V(11),V(26),V(27),V(19),I(1),I(0),I(0),I(1),I(0)],'ROPE_APPROACH_TIMEOUT')
# SET_CAR_COORDINATES adds the model's base offset to z; measure it once so the glide does not climb.
a(0x0574,V(5),I(1));c.set(FROZEN,1);a(0x00ab,V(5),V(9),V(10),V(11));a(0xddc,I(CR_CMDZ),V(11));a(0x00aa,V(5),V(17),V(19),V(31));a(0x0063,V(31),V(11));a(0xddc,I(GLIDE_C),V(31))
a(0x0407,V(5),F(0),F(3),F(0),V(17),V(19),V(31));a(0x0063,V(17),V(9));a(0x0063,V(19),V(10));a(0x00a0,V(18),V(26),V(27),V(31));a(0x005b,V(26),V(17));a(0x005b,V(27),V(19))
c.label('ROPE_GLIDE');a(0x00aa,V(5),V(9),V(10),V(11))
a(0x0087,V(17),V(26));a(0x0063,V(17),V(9));a(0x0087,V(29),V(27));a(0x0063,V(29),V(10));a(0x0087,V(30),V(28));a(0x000b,V(30),F(15));a(0x0063,V(30),V(11))
a(0x050a,F(0),F(0),F(0),V(17),V(29),V(30),V(31));c.check(0x0021,[V(31),F(.8)],'ROPE_ARRIVE')
a(0x0007,V(19),F(.8));a(0x0073,V(19),V(31));a(0x006b,V(17),V(19));a(0x006b,V(29),V(19));a(0x006b,V(30),V(19))
a(0x005b,V(9),V(17));a(0x005b,V(10),V(29));c.get(11,CR_CMDZ);a(0x005b,V(11),V(30));a(0xddc,I(CR_CMDZ),V(11));a(0x00ab,V(5),V(9),V(10),V(11));c.go('TICK')
c.label('ROPE_ARRIVE');a(0x0087,V(19),V(28));a(0x000b,V(19),F(15));a(0x0063,V(19),V(11));c.get(11,CR_CMDZ);a(0x005b,V(11),V(19));a(0xddc,I(CR_CMDZ),V(11));a(0x00ab,V(5),V(26),V(27),V(11))
c.call('BLOCK_HOVER');a(0x0574,V(5),I(1));c.set(FROZEN,1);state(c,3);c.set(ROPE_COMMAND,1);c.go('TICK')
c.label('ROPE_APPROACH_TIMEOUT');a(0x0085,V(17),V(20));a(0x0062,V(17),V(21));c.check(0x0019,[V(17),I(35000)],'TICK');c.call('BLOCK_HOVER');state(c,18);msg(c,'HCRWAIT');c.go('TICK')

c.label('EVAC');c.eq(24,1,'EVAC_NOT_GROUND');a(6,V(25),I(5));c.go('START_MUSTER')
c.label('EVAC_NOT_GROUND');c.eq(24,2,'EVAC_MODEL');a(6,V(25),I(5));c.go('START_MUSTER')
c.label('EVAC_MODEL');c.eq(0,425,'EVAC_SEATS');msg(c,'HCNOSEA');c.go('TICK')
c.label('EVAC_SEATS');a(0x01ea,V(5),V(19));c.check(0x0019,[V(19),I(0)],'NO_SEATS');a(0x04c4,V(18),F(0),F(15),F(100),V(26),V(27),V(28));a(0x02ce,V(26),V(27),V(28),V(28))
# A point on a roof or bridge well above/below CJ is not a suitable pickup.
a(0x00a0,V(18),V(9),V(10),V(11));a(0x000b,V(11),F(20));a(0x02ce,V(9),V(10),V(11),V(31));a(0x0087,V(17),V(28));a(0x0063,V(17),V(31));c.check(0x0023,[F(5),V(17)],'BAD_SITE');c.check(0x0021,[V(17),F(-5)],'BAD_SITE')
c.call('CHECK_SITE');c.eq(17,1,'BAD_SITE');state(c,7);c.go('ISSUE_LANDING')
c.label('NO_SEATS');msg(c,'HCNOSEA');c.go('TICK')
c.label('BAD_SITE');msg(c,'HCNOSIT');c.go('TICK')
c.label('EMERGENCY');a(0x00aa,V(5),V(26),V(27),V(28));a(0x000b,V(28),F(100));a(0x02ce,V(26),V(27),V(28),V(28));state(c,15)
c.label('ISSUE_LANDING');c.set(LAND_STABLE,0);c.set(LAND_SLOW,0);c.set(LAND_FINAL,0);c.call('SET_LANDING_MISSION');a(0x01bd,V(21));c.go('TICK')
c.label('LANDING_TICK');a(0x00aa,V(5),V(9),V(10),V(11));a(0x0509,V(9),V(10),V(26),V(27),V(31));c.get(19,LAND_SLOW);c.eq(19,0,'LAND_CHECK_FINAL');c.check(0x0023,[F(45),V(31)],'LAND_CHECK_FINAL');c.set(LAND_SLOW,1);a(0x00ad,V(5),F(8))
c.label('LAND_CHECK_FINAL');c.get(19,LAND_FINAL);c.eq(19,0,'LAND_VERIFY_TOUCHDOWN');c.check(0x0023,[F(10),V(31)],'LAND_VERIFY_TOUCHDOWN');a(0x02e3,V(5),V(19));c.check(0x0023,[F(4),V(19)],'LAND_VERIFY_TOUCHDOWN');c.set(LAND_FINAL,1);c.call('SET_FINAL_LANDING')
c.label('LAND_VERIFY_TOUCHDOWN');c.check(0x0023,[F(18),V(31)],'LAND_TIMEOUT');a(0x0819,V(4),V(19));c.check(0x0023,[F(3),V(19)],'LAND_TIMEOUT');a(0x02e3,V(5),V(19));c.check(0x0023,[F(1.2),V(19)],'LAND_TIMEOUT')
# Require the successful v8 landing conditions to persist for one second before the team gets out.
c.get(17,LAND_STABLE);c.eq(17,0,'LAND_STABILITY_WAIT');a(0xddc,I(LAND_STABLE),V(20));c.go('TICK')
c.label('LAND_STABILITY_WAIT');a(0x0085,V(19),V(20));a(0x0062,V(19),V(17));c.check(0x0019,[V(19),I(1000)],'TICK')
a(0x04df,V(5),I(1));c.eq(7,7,'LANDED_OTHER');state(c,8);c.call('DEPLOY');c.go('TICK')
c.label('LANDED_OTHER');state(c,12);a(6,V(24),I(3));c.call('PUBLISH');c.get(19,AUTO_EXIT);c.eq(19,2,'TICK');c.set(AUTO_EXIT,0);a(6,V(7),I(12));c.go('LEAVE_CJ')
c.label('LAND_TIMEOUT');c.set(LAND_STABLE,0);a(0x0085,V(17),V(20));a(0x0062,V(17),V(21));c.check(0x0019,[V(17),I(90000)],'TICK');c.go('LAND_BLOCKED')
c.label('LAND_BLOCKED');c.set(AUTO_EXIT,0);c.set(DBG_CODE,8);c.call('BLOCK_HOVER');state(c,18);msg(c,'HCBLOCK');c.go('TICK')
c.label('GROUND_TICK');c.check(0x0448,[V(18),V(5)],'GROUND_OUTSIDE');c.eq(7,8,'GROUND_WORK');a(6,V(25),I(9));c.go('START_MUSTER')
c.label('GROUND_OUTSIDE');c.eq(7,9,'GROUND_WORK');state(c,8);c.call('DEPLOY')
c.label('GROUND_WORK');c.eq(24,1,'TICK');c.get(19,FIRE_ACTIVE);c.eq(19,0,'TICK');a(0x0085,V(17),V(20));a(0x0062,V(17),V(22));c.check(0x0019,[V(17),I(800)],'TICK');a(0x0085,V(22),V(20));c.call('GUARD_TEAM');c.go('TICK')
c.label('BOARD_CJ');c.eq(24,3,'BOARD_GROUND_CHECK');c.go('BOARD_DISTANCE_CHECK')
c.label('BOARD_GROUND_CHECK');c.eq(24,1,'NOT_LANDED')
c.label('BOARD_DISTANCE_CHECK');c.check(0x0205,[V(18),V(5),F(12),F(12),F(5),I(0)],'TOO_FAR');a(0x05ca,V(18),V(5),I(12000),I(0));c.go('TICK')
c.label('TOO_FAR');msg(c,'HCFAR');c.go('TICK')
c.label('NOT_LANDED');msg(c,'HCLOSE');c.go('TICK')
c.label('LEAVE_CJ');c.eq(7,12,'LEAVE_CHECK_PHASE');c.go('LEAVE_ALLOWED')
c.label('LEAVE_CHECK_PHASE');c.eq(24,3,'LEAVE_GROUND_CHECK');c.eq(7,9,'NOT_LANDED');c.go('LEAVE_ALLOWED')
c.label('LEAVE_GROUND_CHECK');c.eq(24,1,'NOT_LANDED')
c.label('LEAVE_ALLOWED');c.check(0x00db,[V(18),V(5)],'TICK');a(0x020a,V(5),I(1));a(0x0085,V(19),V(20));a(0x000a,V(19),I(5000));a(0xddc,I(LOCK_HOLD),V(19));a(0x05cd,V(18),V(5));c.go('TICK')
c.label('REQUEST_MAP');c.set(AVOID_STAGE,0);c.set(AUTO_EXIT,0);c.check(0x0448,[V(18),V(5)],'NOT_ABOARD')
if MAP_MARKER:c.call('READ_WAYPOINT');c.eq(29,1,'NO_MAP')
else:msg(c,'HCMAPOF');c.go('TICK')
a(0xddc,I(DEST_X),V(26));a(0xddc,I(DEST_Y),V(27));a(0xddc,I(DEST_Z),V(28));c.set(GROVE_WAIT,0);c.set(GROVE_NEXT_SCAN,0);c.call('UNFREEZE');a(0x01bd,V(21));state(c,21);c.go('TICK')
c.label('MAP_CLIMB_TICK');a(0x0819,V(4),V(19));c.check(0x0021,[V(19),F(40)],'MAP_CLIMB_TIMEOUT');c.get(26,DEST_X);c.get(27,DEST_Y);c.get(28,DEST_Z);c.call('RESTORE_FLIGHT');a(0x0087,V(9),V(28));a(0x000b,V(9),F(80));a(0x04a2,V(5),V(26),V(27),V(9),F(45),V(9));a(0x00ad,V(5),F(30));state(c,21);c.go('TICK')
c.label('MAP_CLIMB_TIMEOUT');a(0x0085,V(17),V(20));a(0x0062,V(17),V(21));c.check(0x0019,[V(17),I(30000)],'TICK');c.call('BLOCK_HOVER');state(c,18);msg(c,'HCGCLMB');c.go('TICK')
c.label('NO_MAP');msg(c,'HCNOMAP');c.go('TICK')
# Waypoint handle = index | counter<<16. Valid when index < 250, the trace's ReferenceIndex
# (+20) equals the counter and bTrackingBlip (bit 1 of byte +41) is set; x/y at +8/+12.
c.label('READ_WAYPOINT');c.set(DBG_CODE,10);a(6,V(29),I(0));a(0x0dd8,V(30),I(WAYPOINT_OFS),I(4),I(1));c.eq(30,-1,'WP_NOT_MINUS');c.ret()
c.label('WP_NOT_MINUS');c.eq(30,0,'WP_HANDLE');c.ret()
c.label('WP_HANDLE');a(0x0dd8,V(30),I(WAYPOINT_OFS),I(2),I(1));c.check(0x0019,[V(30),I(249)],'WP_INDEX');c.ret()
c.label('WP_INDEX');a(0x0dd8,V(31),I(WAYPOINT_OFS+2),I(2),I(1));a(0x0012,V(30),I(48));a(0x000a,V(30),I(RADAR_TRACE_OFS))
a(0x0085,V(28),V(30));a(0x000a,V(28),I(20));a(0x0dd8,V(26),V(28),I(2),I(1));c.check(0x003b,[V(26),V(31)],'WP_STALE')
a(0x0085,V(28),V(30));a(0x000a,V(28),I(41));a(0x0dd8,V(26),V(28),I(1),I(1));a(0x0016,V(26),I(2));a(0x0085,V(31),V(26));a(0x0016,V(31),I(2));a(0x0012,V(31),I(2));c.check(0x003b,[V(26),V(31)],'WP_ACTIVE');c.ret()
c.label('WP_ACTIVE');a(0x0085,V(28),V(30));a(0x000a,V(28),I(8));a(0x0dd8,V(26),V(28),I(4),I(1));a(0x000a,V(28),I(4));a(0x0dd8,V(27),V(28),I(4),I(1))
for v in [26,27]:c.check(0x0021,[V(v),F(-3100)],'WP_STALE');c.check(0x0023,[F(3100),V(v)],'WP_STALE')
a(0x02ce,V(26),V(27),F(1000),V(28));a(6,V(29),I(1));c.ret()
c.label('WP_STALE');c.ret()
c.label('REQUEST_DEST_LAND');c.eq(7,23,'DEST_NOT_READY');c.get(26,DEST_X);c.get(27,DEST_Y);c.get(28,DEST_Z);c.call('CHECK_SITE');c.eq(17,1,'BAD_SITE');state(c,11);c.go('ISSUE_LANDING')
c.label('REQUEST_DEST_ROPE');c.eq(7,23,'DEST_NOT_READY');c.check(0x0448,[V(18),V(5)],'NOT_ABOARD');c.set(DROP_COMMAND,1);c.go('TICK')
c.label('DEST_NOT_READY');msg(c,'HCDWAIT');c.go('TICK')
c.label('REQUEST_GROVE');c.check(0x0448,[V(18),V(5)],'NOT_ABOARD');a(6,V(25),I(7));c.go('START_MUSTER')
c.label('NOT_ABOARD');msg(c,'HCIN');c.go('TICK')
c.label('REQUEST_TAKEOFF');c.check(0x80db,[V(18),V(5)],'TAKEOFF_EXIT_FIRST');a(6,V(25),I(10));c.go('START_MUSTER')
c.label('TAKEOFF_EXIT_FIRST');msg(c,'HCEXIT');c.go('TICK')
c.label('START_MUSTER');c.eq(24,0,'MUSTER_CHECK_SEATED');c.go('AFTER_MUSTER')
c.label('MUSTER_CHECK_SEATED');c.eq(24,3,'MUSTER_CHECK_ACTIVE');c.go('AFTER_MUSTER')
c.label('MUSTER_CHECK_ACTIVE');c.eq(24,2,'MUSTER_BEGIN');c.go('TICK')
c.label('MUSTER_BEGIN');state(c,14);a(0x01bd,V(21));a(6,V(24),I(2));c.call('PUBLISH')
for var in [13,14,15,16]:
 skip='MUSTER_STOP_'+str(var);alive(c,var,skip);a(0x0792,V(var));a(0x04eb,V(var),I(0));c.label(skip)
c.go('TICK')
c.label('MUSTER_TICK');a(6,V(30),I(1))
for var,x,y,seat in [(13,-4,2,1),(14,4,2,2),(15,-4,-2,-1),(16,4,-2,-1)]:
 skip='MUSTER_DONE_'+str(var);alive(c,var,skip)
 c.check(0x8a32,[V(var)],skip)
 a(0x00a0,V(var),V(9),V(10),V(11));a(0x00aa,V(5),V(17),V(19),V(31));a(0x050a,V(9),V(10),V(11),V(17),V(19),V(31),V(29))
 c.check(0x0023,[F(9),V(29)],'MUSTER_WALK_'+str(var));c.go('MUSTER_BOARD_'+str(var))
 c.label('MUSTER_WALK_'+str(var));a(0x0085,V(17),V(20));a(0x0062,V(17),V(21));c.check(0x0019,[V(17),I(8000)],'MUSTER_WALK_TASK_'+str(var));c.check(0x0023,[F(25),V(29)],'MUSTER_FAR_'+str(var));c.go('MUSTER_RECOVER_'+str(var))
 c.label('MUSTER_FAR_'+str(var));c.check(0x0019,[V(17),I(30000)],'MUSTER_OFFSCREEN_'+str(var));c.go('MUSTER_RECOVER_'+str(var))
 c.label('MUSTER_OFFSCREEN_'+str(var));c.check(0x0019,[V(17),I(15000)],'MUSTER_WALK_TASK_'+str(var));c.check(0x82cb,[V(var)],'MUSTER_WALK_TASK_'+str(var))
 c.label('MUSTER_RECOVER_'+str(var));a(0x0407,V(5),F(x),F(y),F(5),V(9),V(10),V(11));a(0x02ce,V(9),V(10),V(11),V(11));a(0x000b,V(11),F(.7));a(0x0362,V(var),V(9),V(10),V(11));c.go('MUSTER_BOARD_'+str(var))
 c.label('MUSTER_WALK_TASK_'+str(var));a(6,V(30),I(0));a(0x0407,V(5),F(x),F(y),F(0),V(9),V(10),V(11));a(0x05d3,V(var),V(9),V(10),V(11),I(4),I(1000));c.go(skip)
 c.label('MUSTER_BOARD_'+str(var));a(0x0792,V(var));a(0x04eb,V(var),I(0))
 c.call('ATTACH_'+str(var))
 c.label(skip)
c.eq(30,1,'MUSTER_WAIT');a(6,V(24),I(3));c.call('PUBLISH');c.go('AFTER_MUSTER')
c.label('MUSTER_WAIT');a(0x0085,V(17),V(20));a(0x0062,V(17),V(21));c.check(0x0019,[V(17),I(20000)],'TICK');msg(c,'HCWAIT');c.go('TICK')
c.label('AFTER_MUSTER')
for action,label in [(2,'FOLLOW'),(3,'HOLD'),(4,'DEPART'),(13,'DEPART'),(7,'GROVE'),(5,'EVAC'),(9,'WAIT_ABOARD'),(10,'TAKEOFF'),(11,'ROPE_PREP'),(12,'PATROL_START')]:
 nxt='MUSTER_NEXT_'+str(action);c.eq(25,action,nxt);c.go(label);c.label(nxt)
c.go('HOLD')
c.label('WAIT_ABOARD');state(c,9);c.go('TICK')
c.label('TAKEOFF');c.check(0x80db,[V(18),V(5)],'TAKEOFF_EXIT_FIRST');c.go('FOLLOW')
c.label('GROVE');c.set(AUTO_EXIT,0);c.call('UNFREEZE');c.check(0x0448,[V(18),V(5)],'NOT_ABOARD');c.set(AVOID_STAGE,0);c.set(GROVE_STREAM,0);c.set(GROVE_WAIT,0);c.set(GROVE_NEXT_SCAN,0);a(0x01bd,V(21));state(c,10);c.go('TICK')
c.label('GROVE_CLIMB_TICK');a(0x0819,V(4),V(19));c.check(0x0021,[V(19),F(40)],'GROVE_CLIMB_TIMEOUT');c.go('GROVE_CRUISE')
c.label('GROVE_CLIMB_TIMEOUT');a(0x0085,V(17),V(20));a(0x0062,V(17),V(21));c.check(0x0019,[V(17),I(30000)],'TICK');c.call('BLOCK_HOVER');state(c,18);msg(c,'HCGCLMB');c.go('TICK')
c.label('GROVE_CRUISE');c.set(AVOID_STAGE,0);c.set(GROVE_STREAM,0);c.set(GROVE_WAIT,0);c.set(GROVE_NEXT_SCAN,0);c.call('RESTORE_FLIGHT');a(0x0918,V(5),I(1));a(0x0825,V(5));a(0x04df,V(5),I(0));a(0x04a2,V(5),F(GROVE_X),F(GROVE_Y),F(75),F(45),F(90));a(0x00ad,V(5),F(30));state(c,10);c.go('TICK')
c.label('MAP_TRAVEL_TICK');c.get(26,DEST_X);c.get(27,DEST_Y);c.call('CRUISE_STEP');c.check(0x0023,[F(150),V(19)],'TICK');a(0x04e4,V(26),V(27));c.get(17,GROVE_WAIT);c.eq(17,0,'MAP_SCAN_TIMER');a(0xddc,I(GROVE_WAIT),V(20))
c.label('MAP_SCAN_TIMER');c.set(DBG_CODE,3);c.get(17,GROVE_NEXT_SCAN);c.check(0x001d,[V(20),V(17)],'TICK');a(0x0085,V(17),V(20));a(0x000a,V(17),I(500));a(0xddc,I(GROVE_NEXT_SCAN),V(17))
# Try the exact marker first, then neighbouring points. Each candidate requires a clear landing footprint.
for index,(dx,dy) in enumerate([(0,0),(8,0),(-8,0),(0,8),(0,-8),(16,0),(-16,0),(0,16),(0,-16),(16,16),(-16,16),(16,-16),(-16,-16)]):
 nxt='MAP_PAD_NEXT_'+str(index);c.get(26,DEST_X);c.get(27,DEST_Y);a(0x000b,V(26),F(dx));a(0x000b,V(27),F(dy));a(0x02ce,V(26),V(27),F(1000),V(28));c.check(0x0021,[V(28),F(-50)],nxt);c.check(0x0023,[F(800),V(28)],nxt);c.call('CHECK_SITE');c.eq(17,1,nxt);a(0xddc,I(DEST_X),V(26));a(0xddc,I(DEST_Y),V(27));a(0xddc,I(DEST_Z),V(28));c.go('DEST_HOVER_GO');c.label(nxt)
c.get(17,GROVE_WAIT);a(0x0085,V(31),V(20));a(0x0062,V(31),V(17));c.check(0x0019,[V(31),I(8000)],'TICK');c.go('LAND_BLOCKED')
c.label('DEST_HOVER_GO');c.set(DBG_CODE,4);c.set(DEST_NATIVE,0);a(0x01bd,V(21));state(c,22);c.go('TICK')
# v31: cruise to the pad at altitude, then sink vertically to 18 m above it (no native circling).
c.label('DEST_APPROACH_TICK');c.get(26,DEST_X);c.get(27,DEST_Y);c.get(28,DEST_Z);c.get(19,DEST_NATIVE);c.eq(19,0,'DEST_DESCEND');a(0x00aa,V(5),V(9),V(10),V(11));a(0x0509,V(9),V(10),V(26),V(27),V(31));c.check(0x0021,[V(31),F(1)],'DEST_DESCEND');c.call('CRUISE_STEP');c.go('TICK')
# v37: the in-game freezes happened during the frozen, teleported descent next to roofs
# (DBG 2205). Now the scripted cruise only brings the helicopter exactly overhead at its safe
# altitude; then it is unfrozen, its residual speed zeroed, and the native pilot descends to
# 18 m with a 10 m reached distance (already overhead, so it does not circle).
c.label('DEST_DESCEND');c.set(DBG_CODE,5);c.get(19,DEST_NATIVE);c.eq(19,0,'DEST_NATIVE_WAIT')
c.call('UNFREEZE');a(0x04ba,V(5),F(0));a(0x07bb,V(5),I(0));a(0x0853,V(5),I(10));a(0x0087,V(9),V(28));a(0x000b,V(9),F(18));a(0x04df,V(5),I(0));a(0x04a2,V(5),V(26),V(27),V(9),F(10),V(9));a(0x00ad,V(5),F(12));c.set(DEST_NATIVE,1);a(0x01bd,V(21));c.go('TICK')
c.label('DEST_NATIVE_WAIT');c.set(DBG_CODE,6);a(0x00aa,V(5),V(9),V(10),V(11));a(0x0509,V(9),V(10),V(26),V(27),V(31));c.check(0x0023,[F(8),V(31)],'DEST_NATIVE_TIMEOUT');a(0x0087,V(19),V(11));a(0x0063,V(19),V(28));c.check(0x0021,[V(19),F(12)],'DEST_NATIVE_TIMEOUT');c.check(0x0023,[F(23),V(19)],'DEST_NATIVE_TIMEOUT');a(0x02e3,V(5),V(19));c.check(0x0023,[F(4),V(19)],'DEST_NATIVE_TIMEOUT')
c.label('DEST_NATIVE_ARRIVE');c.call('BLOCK_HOVER');c.set(DBG_CODE,7);state(c,23);a(6,V(7),I(23));c.get(19,AUTO_EXIT);c.eq(19,1,'DEST_ARRIVE_ASK');c.set(AUTO_EXIT,0);c.go('EXIT_BY_MODE')
c.label('DEST_ARRIVE_ASK');msg(c,'HCCHOS');c.go('TICK')
c.label('DEST_NATIVE_TIMEOUT');a(0x0085,V(17),V(20));a(0x0062,V(17),V(21));c.check(0x0019,[V(17),I(25000)],'TICK');c.check(0x0023,[F(20),V(31)],'LAND_BLOCKED');c.go('DEST_NATIVE_ARRIVE')
c.label('DEST_WAIT_TIMEOUT');a(0x0085,V(17),V(20));a(0x0062,V(17),V(21));c.check(0x0019,[V(17),I(60000)],'TICK');c.go('LAND_BLOCKED')
c.label('TRAVEL_TICK');a(0x0007,V(26),F(GROVE_X));a(0x0007,V(27),F(GROVE_Y));c.call('CRUISE_STEP');c.check(0x0023,[F(180),V(19)],'TICK')
c.get(17,GROVE_STREAM);c.eq(17,0,'GROVE_NEAR');c.set(GROVE_STREAM,1);a(0x04e4,F(GROVE_X),F(GROVE_Y));a(0x07bb,V(5),I(0));a(0x00ad,V(5),F(21))
c.label('GROVE_NEAR');c.check(0x0023,[F(90),V(19)],'TICK');c.get(17,GROVE_WAIT);c.eq(17,0,'GROVE_SEARCH');a(0xddc,I(GROVE_WAIT),V(20))
c.label('GROVE_SEARCH');c.set(DBG_CODE,9);c.get(17,GROVE_NEXT_SCAN);c.check(0x001d,[V(20),V(17)],'TICK');a(0x0085,V(17),V(20));a(0x000a,V(17),I(500));a(0xddc,I(GROVE_NEXT_SCAN),V(17))
# Search only within the Grove Street circle. Check loading/ground and clearance before landing.
for index,(dx,dy) in enumerate([(0,0),(6,0),(-6,0),(0,6),(0,-6)]):
 nxt='GROVE_PAD_NEXT_'+str(index);a(0x0007,V(26),F(GROVE_X+dx));a(0x0007,V(27),F(GROVE_Y+dy));a(0x02ce,V(26),V(27),F(60),V(28));c.check(0x0021,[V(28),F(5)],nxt);c.check(0x0023,[F(30),V(28)],nxt);c.call('CHECK_SITE');c.eq(17,1,nxt);a(0xddc,I(DEST_X),V(26));a(0xddc,I(DEST_Y),V(27));a(0xddc,I(DEST_Z),V(28));c.go('DEST_HOVER_GO');c.label(nxt)
c.get(17,GROVE_WAIT);a(0x0085,V(31),V(20));a(0x0062,V(31),V(17));c.check(0x0019,[V(31),I(8000)],'TICK');c.go('LAND_BLOCKED')

c.label('DEPART');c.eq(25,13,'NORMAL_DEPART');state(c,13);c.go('DEPART_START')
c.label('NORMAL_DEPART');state(c,4)
c.label('DEPART_START');c.call('UNFREEZE');c.call('RESTORE_FLIGHT');a(0x0918,V(5),I(1));a(0x0825,V(5));a(0x04df,V(5),I(0));a(0x0407,V(5),F(0),F(1500),F(60),V(9),V(10),V(11));a(0x04a2,V(5),V(9),V(10),V(11),F(30),F(120));a(0x01bd,V(21))
c.label('DEPART_TICK');a(1,I(100));a(0x01bd,V(20));a(0xddc,I(HEART),V(20));c.set(CMD,0);healthcheck(c,'CLEANUP');c.call('CHANGE_MODEL');c.call('CHANGE_CREW');c.call('PUBLISH');a(0x0227,V(5),V(6));a(0xddc,I(HP),V(6));c.get(19,FIRE);c.check(0x003b,[V(19),V(23)],'DEPART_FIRE_CHANGE');c.go('DEPART_HEALTH_DONE')
c.label('DEPART_FIRE_CHANGE');c.call('APPLY_FIRE')
c.label('DEPART_HEALTH_DONE');a(0x0085,V(17),V(20));a(0x0062,V(17),V(21));c.check(0x0019,[V(17),I(45000)],'DEPART_DISTANCE');c.go('CLEANUP')
c.label('DEPART_DISTANCE');c.check(0x0019,[V(17),I(3000)],'DEPART_TICK');c.check(0x80db,[V(18),V(5)],'DEPART_TICK')
# v28: a stuck or slow departing helicopter is removed after 12 s even if it is still on screen.
c.check(0x0019,[V(17),I(12000)],'DEPART_VISIBLE');c.go('DEPART_DELETE')
c.label('DEPART_VISIBLE');c.check(0x82ca,[V(5)],'DEPART_TICK');a(0x00a0,V(18),V(9),V(10),V(11));a(0x00aa,V(5),V(26),V(27),V(28));a(0x050a,V(9),V(10),V(11),V(26),V(27),V(28),V(19));c.check(0x0021,[V(19),F(250)],'DEPART_TICK')
c.label('DEPART_DELETE');a(0x0164,V(12))
for var in [13,14,15,16,4]:
 skip='DELETE_SKIP_'+str(var);c.check(0x056d,[V(var)],skip);a(0x009b,V(var));c.label(skip)
a(0x00a6,V(5));c.go('RESET')
c.label('CLEANUP');c.call('UNFREEZE');a(0x0164,V(12))
for var in [4,13,14,15,16]:
 skip='RELEASE_SKIP_'+str(var);c.check(0x056d,[V(var)],skip);a(0x0792,V(var));a(0x048f,V(var));a(0x01c2,V(var));c.label(skip)
c.check(0x056e,[V(5)],'RESET');a(0x01c3,V(5))
c.label('RESET');c.set(FROZEN,0);c.set(LSTAGE,0);c.set(BUSY,0);state(c,0)
for weapon_model in [353,355,356,358]:a(0x0249,I(weapon_model))
for key in range(PUB,PUB+7):c.set(key,-1)
c.set(CMD,0);c.set(HP,0);c.go('IDLE')
c.label('OUTDOORS');state(c,6);c.go('IDLE')
c.label('MODEL_FAIL')
for v in [0,1,2,3]:a(0x0249,V(v))
for weapon_model in [353,355,356,358]:a(0x0249,I(weapon_model))
state(c,5);c.go('IDLE')

# No mission/global relationships are changed: only the created NPCs are configured.
c.label('APPLY_FIRE');c.get(23,FIRE);c.ret()
c.label('REATTACH_TEAM')
for var,x,y,direction in [(13,1.4,1.3,3),(14,-1.4,1.3,1),(15,1.4,-.8,3),(16,-1.4,-.8,1)]:
 skip='ATTACH_SKIP_'+str(var);alive(c,var,skip)
 c.eq(24,0,'ATTACH_PHASE_'+str(var));c.go('ATTACH_ALLOWED_'+str(var))
 c.label('ATTACH_PHASE_'+str(var));c.eq(24,3,skip)
 c.label('ATTACH_ALLOWED_'+str(var));c.call('ATTACH_'+str(var));c.label(skip)
c.ret()
for var,x,y,direction in [(13,1.4,1.3,3),(14,-1.4,1.3,1),(15,1.4,-.8,3),(16,-1.4,-.8,1)]:
 c.label('ATTACH_'+str(var));c.eq(0,425,'ATTACH_NORMAL_'+str(var));a(0x0007,V(9),F(1.9 if x>0 else -1.9));a(0x0007,V(10),F(1.2 if var in [13,14] else -1.2));a(0x0007,V(11),F(-.4));c.go('ATTACH_POS_'+str(var))
 c.label('ATTACH_NORMAL_'+str(var));a(0x0007,V(9),F(x));a(0x0007,V(10),F(y));a(0x0007,V(11),F(-.1))
 c.label('ATTACH_POS_'+str(var));a(0x0792,V(var));a(0x048f,V(var));a(0x04eb,V(var),I(0));a(0x0464,V(var),V(5),V(9),V(10),V(11),I(direction),F(190),I(0));c.ret()
c.label('CHECK_SITE');a(6,V(17),I(0))
for dx,dy in [(0,0),(4,0),(-4,0),(0,4),(0,-4)]:
 # Sample local ground and reject steep edges; check low vehicles plus fixed overhead obstacles.
 a(0x0087,V(9),V(26));a(0x000b,V(9),F(dx));a(0x0087,V(10),V(27));a(0x000b,V(10),F(dy));a(0x0087,V(11),V(28));a(0x000b,V(11),F(20));a(0x02ce,V(9),V(10),V(11),V(31));a(0x0063,V(31),V(28));c.check(0x0023,[F(2),V(31)],'SITE_END');c.check(0x0021,[V(31),F(-2)],'SITE_END')
 a(0x0087,V(11),V(28));a(0x000b,V(11),F(.7));a(0x0087,V(29),V(28));a(0x000b,V(29),F(4));c.check(0x06bd,[V(9),V(10),V(11),V(9),V(10),V(29),I(1),I(1),I(0),I(1),I(0)],'SITE_END')
 a(0x0087,V(11),V(28));a(0x000b,V(11),F(4));a(0x0087,V(29),V(28));a(0x000b,V(29),F(22));c.check(0x06bd,[V(9),V(10),V(11),V(9),V(10),V(29),I(1),I(0),I(0),I(1),I(0)],'SITE_END')
a(6,V(17),I(1));c.label('SITE_END');c.ret()
c.label('DEPLOY');c.set(BUSY,1);a(6,V(24),I(1))
for var,x,y in [(13,-3.5,2),(14,3.5,2),(15,-3.5,-2),(16,3.5,-2)]:
 skip='DEPLOY_SKIP_'+str(var);alive(c,var,skip);a(0x0792,V(var));a(0x0465,V(var));a(0x0407,V(5),F(x),F(y),F(6),V(9),V(10),V(11));a(0x02ce,V(9),V(10),V(11),V(11));a(0x000b,V(11),F(1));a(0x0362,V(var),V(9),V(10),V(11));a(0x0619,V(var),I(1));a(0x083c,V(var),F(0),F(0),F(-.5));a(0x04eb,V(var),I(1));c.label(skip)
c.call('PUBLISH');c.set(BUSY,0);c.ret()
c.label('GUARD_TEAM')
for var,x,y in [(13,-5,4),(14,5,4),(15,-5,-4),(16,5,-4)]:
 skip='GUARD_SKIP_'+str(var);alive(c,var,skip);c.check(0x80df,[V(var)],skip);a(0x04c4,V(18),F(x),F(y),F(0),V(9),V(10),V(11));a(0x00a0,V(var),V(17),V(19),V(30));a(0x050a,V(9),V(10),V(11),V(17),V(19),V(30),V(30));c.check(0x0021,[V(30),F(2.5)],'GUARD_WATCH_'+str(var));a(0x05d3,V(var),V(9),V(10),V(11),I(4),I(1000));c.go(skip)
 c.label('GUARD_WATCH_'+str(var));a(0x04eb,V(var),I(1));c.label(skip)
c.ret()

# Only while FOLLOW CJ is active: if a selected nearby threat is too far from the
# helicopter, keep it in view. Never change landing, hold, muster or Grove missions.
c.label('TRACK_COMBAT');c.eq(7,2,'TRACK_PATROL');c.go('TRACK_ACTIVE');c.label('TRACK_PATROL');c.eq(7,24,'TRACK_INACTIVE');c.label('TRACK_ACTIVE');c.get(29,FIRE_TARGET);alive(c,29,'TRACK_STOP')
a(0x00a0,V(18),V(9),V(10),V(11));a(0x00a0,V(29),V(17),V(19),V(31));a(0x050a,V(9),V(10),V(11),V(17),V(19),V(31),V(30));c.check(0x0023,[F(65),V(30)],'TRACK_STOP')
c.get(19,TRACKED_TARGET);c.check(0x003b,[V(19),V(29)],'TRACK_CHANGED');c.go('TRACK_DIST')
c.label('TRACK_CHANGED');c.eq(19,-1,'TRACK_REPLACE');c.go('TRACK_DIST')
c.label('TRACK_REPLACE');c.call('RESTORE_FLIGHT');a(0x0726,V(5),V(18),I(-1),F(15));c.set(TRACKED_TARGET,-1)
# v39-fire combat orbit: circle the threat at ORBIT_RADIUS m, 25 m above it, moving to the next of 8
# points every 2.5 s so both door gunners get angles. Still coordinates only (no entity pointer:
# see the v26 crash in CCarCtrl::SteerAIHeliToKeepEntityInView).
c.label('TRACK_DIST');a(0x00a0,V(29),V(17),V(19),V(31))
c.get(30,ORBIT_NEXT);c.check(0x001d,[V(20),V(30)],'ORBIT_KEEP');a(0x0085,V(30),V(20));a(0x000a,V(30),I(2500));a(0xddc,I(ORBIT_NEXT),V(30))
c.get(30,ORBIT_I);a(0x000a,V(30),I(1));c.check(0x0019,[V(30),I(7)],'ORBIT_STORE');a(6,V(30),I(0));c.label('ORBIT_STORE');a(0xddc,I(ORBIT_I),V(30))
c.label('ORBIT_KEEP');c.get(30,ORBIT_I)
c.eq(30,0,'ORBIT_PT_0');a(0x0007,V(9),F(28.0));a(0x0007,V(10),F(0.0));c.go('TRACK_GOTO');c.label('ORBIT_PT_0')
c.eq(30,1,'ORBIT_PT_1');a(0x0007,V(9),F(19.8));a(0x0007,V(10),F(19.8));c.go('TRACK_GOTO');c.label('ORBIT_PT_1')
c.eq(30,2,'ORBIT_PT_2');a(0x0007,V(9),F(0.0));a(0x0007,V(10),F(28.0));c.go('TRACK_GOTO');c.label('ORBIT_PT_2')
c.eq(30,3,'ORBIT_PT_3');a(0x0007,V(9),F(-19.8));a(0x0007,V(10),F(19.8));c.go('TRACK_GOTO');c.label('ORBIT_PT_3')
c.eq(30,4,'ORBIT_PT_4');a(0x0007,V(9),F(-28.0));a(0x0007,V(10),F(0.0));c.go('TRACK_GOTO');c.label('ORBIT_PT_4')
c.eq(30,5,'ORBIT_PT_5');a(0x0007,V(9),F(-19.8));a(0x0007,V(10),F(-19.8));c.go('TRACK_GOTO');c.label('ORBIT_PT_5')
c.eq(30,6,'ORBIT_PT_6');a(0x0007,V(9),F(0.0));a(0x0007,V(10),F(-28.0));c.go('TRACK_GOTO');c.label('ORBIT_PT_6')
c.eq(30,7,'ORBIT_PT_7');a(0x0007,V(9),F(19.8));a(0x0007,V(10),F(-19.8));c.go('TRACK_GOTO');c.label('ORBIT_PT_7')
a(0x0007,V(9),F(ORBIT_RADIUS));a(0x0007,V(10),F(0))
c.label('TRACK_GOTO');a(0x005b,V(9),V(17));a(0x005b,V(10),V(19));a(0x0087,V(11),V(31));a(0x000b,V(11),F(25))
a(0x07bb,V(5),I(0));a(0x04a2,V(5),V(9),V(10),V(11),F(20),F(45));a(0xddc,I(TRACKED_TARGET),V(29));c.ret()
c.label('TRACK_STOP');c.get(19,TRACKED_TARGET);c.eq(19,-1,'TRACK_RESUME');c.ret()
c.label('TRACK_RESUME');c.set(TRACKED_TARGET,-1);c.call('RESTORE_FLIGHT');a(0x0726,V(5),V(18),I(-1),F(15));c.ret()
c.label('TRACK_INACTIVE');c.set(TRACKED_TARGET,-1)
c.label('TRACK_DONE');c.ret()

# Short detours during the two long-range cruise modes. Collision rays only guide the
# pilot; they cannot guarantee safe clearance from all moving or unstreamed objects.
c.label('FLIGHT_AVOID');c.get(19,FROZEN);c.eq(19,1,'AVOID_UNFROZEN');c.go('AVOID_NOT_CRUISE');c.label('AVOID_UNFROZEN');c.eq(7,10,'AVOID_CHECK_MAP');c.go('AVOID_ACTIVE_STATE');c.label('AVOID_CHECK_MAP');c.eq(7,21,'AVOID_NOT_CRUISE');c.label('AVOID_ACTIVE_STATE');c.get(19,AVOID_STAGE);c.eq(19,1,'AVOID_PROBE_TIMER');c.get(17,AVOID_AT);a(0x0085,V(19),V(20));a(0x0062,V(19),V(17));c.check(0x0019,[V(19),I(6000)],'AVOID_CHECK_REACHED');c.go('AVOID_RESUME')
c.label('AVOID_CHECK_REACHED');a(0x00aa,V(5),V(9),V(10),V(11));c.get(17,AVOID_X);c.get(19,AVOID_Y);a(0x0509,V(9),V(10),V(17),V(19),V(31));c.check(0x0023,[F(10),V(31)],'AVOID_RETURN');c.go('AVOID_RESUME')
c.label('AVOID_PROBE_TIMER');c.get(19,AVOID_NEXT);c.check(0x001d,[V(20),V(19)],'AVOID_RETURN');a(0x0085,V(19),V(20));a(0x000a,V(19),I(1000));a(0xddc,I(AVOID_NEXT),V(19));a(0x0407,V(5),F(0),F(2),F(2),V(9),V(10),V(11));a(0x0407,V(5),F(0),F(35),F(2),V(17),V(19),V(31));c.check(0x06bd,[V(9),V(10),V(11),V(17),V(19),V(31),I(1),I(0),I(0),I(1),I(0)],'AVOID_TRY_LEFT');c.ret()
c.label('AVOID_TRY_LEFT');a(0x0407,V(5),F(-15),F(25),F(12),V(17),V(19),V(31));c.check(0x06bd,[V(9),V(10),V(11),V(17),V(19),V(31),I(1),I(0),I(0),I(1),I(0)],'AVOID_TRY_RIGHT');c.go('AVOID_ISSUE')
c.label('AVOID_TRY_RIGHT');a(0x0407,V(5),F(15),F(25),F(12),V(17),V(19),V(31));c.check(0x06bd,[V(9),V(10),V(11),V(17),V(19),V(31),I(1),I(0),I(0),I(1),I(0)],'AVOID_NO_ROUTE')
c.label('AVOID_ISSUE');a(0xddc,I(AVOID_X),V(17));a(0xddc,I(AVOID_Y),V(19));a(0xddc,I(AVOID_Z),V(31));a(0xddc,I(AVOID_AT),V(20));c.set(AVOID_STAGE,1);a(0x04df,V(5),I(0));a(0x04a2,V(5),V(17),V(19),V(31),F(15),V(31));a(0x00ad,V(5),F(18));c.ret()
c.label('AVOID_NO_ROUTE');c.call('BLOCK_HOVER');state(c,18);msg(c,'HCAVOID');c.ret()
c.label('AVOID_RESUME');c.set(AVOID_STAGE,0);c.eq(7,10,'AVOID_RESUME_MAP');a(0x04a2,V(5),F(GROVE_X),F(GROVE_Y),F(75),F(45),F(90));a(0x00ad,V(5),F(30));c.ret()
c.label('AVOID_RESUME_MAP');c.get(26,DEST_X);c.get(27,DEST_Y);c.get(28,DEST_Z);a(0x0087,V(9),V(28));a(0x000b,V(9),F(80));a(0x04a2,V(5),V(26),V(27),V(9),F(45),V(9));a(0x00ad,V(5),F(30));c.ret()
c.label('AVOID_NOT_CRUISE');c.set(AVOID_STAGE,0)
c.label('AVOID_RETURN');c.ret()

# Shared handles isolate the fire worker from the flight controller's locals.
c.label('PUBLISH')
for index,var in enumerate([18,5,4,13,14,15,16]):a(0xddc,I(PUB+index),V(var))
a(0xddc,I(PHASE),V(24));a(0xddc,I(ACTUAL),V(0));a(6,V(19),I(30));c.eq(1,105,'PUBLISH_M4');c.go('PUBLISH_WEAPON')
c.label('PUBLISH_M4');a(6,V(19),I(31))
c.label('PUBLISH_WEAPON');c.get(30,WEAPON_SETTING);c.eq(30,0,'PUBLISH_WEAPON_OVERRIDE');c.go('PUBLISH_WEAPON_CHOSEN')
c.label('PUBLISH_WEAPON_OVERRIDE');a(0x0085,V(19),V(30))
c.label('PUBLISH_WEAPON_CHOSEN');a(0xddc,I(WPN),V(19));a(6,V(19),I(0));c.eq(1,105,'PUBLISH_CREW_ARMY');c.go('PUBLISH_CREW_DONE')
c.label('PUBLISH_CREW_ARMY');a(6,V(19),I(1));c.eq(1,287,'PUBLISH_CREW_SWAT');c.go('PUBLISH_CREW_DONE')
c.label('PUBLISH_CREW_SWAT');a(6,V(19),I(2))
c.label('PUBLISH_CREW_DONE');a(0xddc,I(ACREW),V(19));c.ret()
c.label('CHANGE_MODEL');c.get(29,MODEL);c.check(0x803b,[V(29),V(0)],'SWAP_RETURN')
# Validate the supported set before loading anything.
for model in [487,497,425]:
 nxt='SWAP_VALIDATE_'+str(model);c.eq(29,model,nxt);c.go('SWAP_VALID');c.label(nxt)
c.go('SWAP_REJECT')
c.label('SWAP_VALID');c.eq(29,425,'SWAP_LOAD');c.check(0x80db,[V(18),V(5)],'SWAP_NO_PASSENGER')
c.label('SWAP_LOAD');c.set(BUSY,1);c.get(7,STATE);c.set(STATE,16);a(0x0247,V(29));a(0x038b);a(1,I(0));c.check(0x0248,[V(29)],'SWAP_FAILED');c.check(0x0256,[I(0)],'SWAP_FAILED')
a(0x0085,V(30),V(5));a(0x00aa,V(5),V(9),V(10),V(11));a(0x0174,V(5),V(17));a(0x02e3,V(5),V(22));a(0x0227,V(5),V(6));a(6,V(8),I(0));c.check(0x00db,[V(18),V(5)],'SWAP_CJ_FLAG_READY');a(6,V(8),I(1));c.label('SWAP_CJ_FLAG_READY')
a(0x00a5,V(29),V(9),V(10),V(11),V(31));c.check(0x056e,[V(31)],'SWAP_FAILED');a(0x099a,V(31),I(0));a(0x099a,V(30),I(0));a(0x0175,V(31),V(17));a(0x0224,V(31),V(6));a(0x0825,V(31));a(0x07bb,V(31),I(6));a(0x0957,V(31),I(1))
a(0x0792,V(4));a(0x036a,V(4),V(31));c.eq(8,1,'SWAP_CJ_READY');a(0x0430,V(18),V(31),I(0));c.label('SWAP_CJ_READY')
a(0x0085,V(5),V(31));a(0x0085,V(0),V(29))
for var,seat in [(13,1),(14,2),(15,-1),(16,-1)]:
 skip='SWAP_GUARD_DONE_'+str(var);alive(c,var,skip);c.check(0x0a32,[V(var)],'SWAP_GUARD_SEAT_'+str(var));a(0x0465,V(var));c.call('ATTACH_'+str(var));c.go(skip)
 c.label('SWAP_GUARD_SEAT_'+str(var));c.check(0x00db,[V(var),V(30)],skip)
 if seat>=0:
  c.eq(0,425,'SWAP_GUARD_CABIN_'+str(var));a(0x00aa,V(5),V(9),V(10),V(11));a(0x0362,V(var),V(9),V(10),V(11));c.call('ATTACH_'+str(var));c.go(skip);c.label('SWAP_GUARD_CABIN_'+str(var));a(0x0430,V(var),V(5),I(seat))
 else:a(0x00aa,V(5),V(9),V(10),V(11));a(0x0362,V(var),V(9),V(10),V(11));c.call('ATTACH_'+str(var))
 c.label(skip)
a(0x0164,V(12));a(0x00a6,V(30));a(0x0186,V(5),V(12));a(0x0168,V(12),I(2));a(0x0165,V(12),I(1));a(0x07e0,V(12),I(1));a(0x099a,V(5),I(1));a(0x04ba,V(5),V(22));a(0x0249,V(29));a(0xddc,I(STATE),V(7));c.call('PUBLISH');c.call('RESUME_FLIGHT');c.set(BUSY,0);msg(c,'HCSWAP');c.ret()
c.label('SWAP_NO_PASSENGER');msg(c,'HCSNO');c.go('SWAP_REJECT')
c.label('SWAP_FAILED');a(0x0249,V(29));a(0xddc,I(STATE),V(7));c.set(BUSY,0);msg(c,'HCSFAIL')
c.label('SWAP_REJECT');a(0xddc,I(MODEL),V(0))
c.label('SWAP_RETURN');c.ret()
c.label('RESUME_FLIGHT')
for st,label in [(2,'RESUME_FOLLOW'),(3,'RESUME_HOLD'),(18,'RESUME_HOLD'),(7,'RESUME_LAND'),(11,'RESUME_LAND'),(15,'RESUME_LAND'),(10,'RESUME_GROVE'),(4,'RESUME_DEPART'),(13,'RESUME_DEPART'),(19,'RESUME_ROPE'),(20,'RESUME_GROVE_CLIMB'),(24,'RESUME_PATROL'),(25,'RESUME_GROVE_CLIMB')]:
 nxt='RESUME_NEXT_'+str(st);c.eq(7,st,nxt);c.go(label);c.label(nxt)
a(0x04df,V(5),I(1));c.get(19,FROZEN);c.eq(19,1,'RESUME_GROUND_DONE');a(0x0574,V(5),I(1))
c.label('RESUME_GROUND_DONE');c.ret()
c.label('RESUME_PATROL');c.set(PATROL_NEXT,0);c.call('UNFREEZE');c.ret()
c.label('RESUME_FOLLOW');c.call('UNFREEZE');c.set(TRACKED_TARGET,-1);c.call('RESTORE_FLIGHT');a(0x0726,V(5),V(18),I(-1),F(15));c.ret()
c.label('RESUME_HOLD');c.call('BLOCK_HOVER');c.ret()
c.label('RESUME_LAND');c.set(LAND_STABLE,0);c.call('SET_LANDING_MISSION');c.ret()
c.label('RESUME_GROVE_CLIMB');c.call('UNFREEZE');c.call('RESTORE_FLIGHT');a(0x00aa,V(5),V(9),V(10),V(11));a(0x000b,V(11),F(55));a(0x04a2,V(5),V(9),V(10),V(11),F(45),V(11));c.ret()
c.label('RESUME_GROVE');c.call('UNFREEZE');c.set(GROVE_STREAM,0);c.call('RESTORE_FLIGHT');a(0x04a2,V(5),F(GROVE_X),F(GROVE_Y),F(75),F(30),F(90));c.ret()
c.label('RESUME_ROPE');c.call('UNFREEZE');c.call('RESTORE_FLIGHT');a(0x0087,V(9),V(28));a(0x000b,V(9),F(15));a(0x0087,V(11),V(28));a(0x000b,V(11),F(15));a(0x0853,V(5),I(3));a(0x07bb,V(5),I(0));a(0x04a2,V(5),V(26),V(27),V(9),F(12),V(11));c.ret()
c.label('RESUME_DEPART');c.call('UNFREEZE');c.call('RESTORE_FLIGHT');a(0x0407,V(5),F(0),F(1500),F(60),V(9),V(10),V(11));a(0x04a2,V(5),V(9),V(10),V(11),F(30),F(120));c.ret()

# v28: a helicopter wedged in a building barely moves. After 5 s of < 1 m/s while it should be
# flying (following/patrolling far from CJ, cruising, climbing) lift it 20 m above the roofs.
c.label('UNSTICK');c.get(19,FROZEN);c.eq(19,0,'UNSTICK_RESET')
for st in [2,24]:
 nxt='UNSTICK_NOT_'+str(st);c.eq(7,st,nxt);a(0x00a0,V(18),V(9),V(10),V(11));a(0x00aa,V(5),V(29),V(30),V(31));a(0x050a,V(9),V(10),V(11),V(29),V(30),V(31),V(19));c.check(0x0021,[V(19),F(30)],'UNSTICK_RESET');c.go('UNSTICK_SPEED');c.label(nxt)
for st in [10,20,25]:
 nxt='UNSTICK_NOT_'+str(st);c.eq(7,st,nxt);c.go('UNSTICK_SPEED');c.label(nxt)
c.go('UNSTICK_RESET')
c.label('UNSTICK_SPEED');a(0x02e3,V(5),V(19));c.check(0x0023,[F(1),V(19)],'UNSTICK_RESET');c.get(19,STUCK_SINCE);c.eq(19,0,'UNSTICK_TIMER');a(0xddc,I(STUCK_SINCE),V(20));c.ret()
c.label('UNSTICK_TIMER');a(0x0085,V(29),V(20));a(0x0062,V(29),V(19));c.check(0x0019,[V(29),I(5000)],'UNSTICK_WAIT')
a(0x00aa,V(5),V(9),V(10),V(11));a(0x02ce,V(9),V(10),F(1000),V(17));a(0x000b,V(17),F(20));a(0x000b,V(11),F(10));c.check(0x0025,[V(17),V(11)],'UNSTICK_Z_OK');a(0x0087,V(11),V(17));c.label('UNSTICK_Z_OK')
a(0x00ab,V(5),V(9),V(10),V(11));c.set(STUCK_SINCE,0);c.call('RESUME_FLIGHT');c.ret()
c.label('UNSTICK_RESET');c.set(STUCK_SINCE,0)
c.label('UNSTICK_WAIT');c.ret()
# v32 scripted cruise toward (26@,27@). The helicopter is frozen and moved every frame by
# SET_CAR_COORDINATES. Speed ramps up/down (target = 0.6*distance+3, capped), heading turns at
# most CRUISE_TURN deg/s (slow while turning > 45 deg), altitude eases toward CRUISE_CLEAR m above
# the highest surface below and 30/70/120 m ahead (stop and climb if > 8 m too low or blocked).
# Returns 19@ = remaining 2D distance.
c.label('GLIDE_BEGIN');a(0x00aa,V(5),V(9),V(10),V(11));a(0x0574,V(5),I(1));c.set(FROZEN,1);a(0x00ab,V(5),V(9),V(10),V(11));a(0xddc,I(CR_CMDZ),V(11));a(0x00aa,V(5),V(17),V(29),V(31));a(0x0063,V(31),V(11));a(0xddc,I(GLIDE_C),V(31));a(0xddc,I(CRUISE_T),V(20));a(0x0007,V(31),F(0));a(0xddc,I(CR_V),V(31));c.ret()
c.label('CR_TIME');c.get(29,CRUISE_T);a(0x0085,V(30),V(20));a(0x0062,V(30),V(29));a(0xddc,I(CRUISE_T),V(20))
c.check(0x0019,[V(30),I(100)],'CRT_HI');a(6,V(30),I(100));c.label('CRT_HI');c.check(0x0019,[V(30),I(0)],'CRT_LOW');c.go('CRT_OK');c.label('CRT_LOW');a(6,V(30),I(16));c.label('CRT_OK')
a(0x0093,V(31),V(30));a(0x0013,V(31),F(.001));a(0xddc,I(CR_DT),V(31));c.ret()
c.label('CRUISE_STEP');c.get(19,FROZEN);c.eq(19,1,'CR_BEGIN');c.go('CR_RUN');c.label('CR_BEGIN');c.call('GLIDE_BEGIN')
c.label('CR_RUN');c.set(DBG_CODE,1);c.call('CR_TIME');a(0x00aa,V(5),V(9),V(10),V(11))
a(0x0087,V(17),V(26));a(0x0063,V(17),V(9));a(0x0087,V(29),V(27));a(0x0063,V(29),V(10));a(0x0509,F(0),F(0),V(17),V(29),V(19))
a(0xddc,I(CR_DX),V(17));a(0xddc,I(CR_DY),V(29));c.set(CR_SLOW,0)
c.check(0x0021,[V(19),F(2)],'CR_HEAD_DONE')
a(0x0604,V(17),V(29),V(30));a(0x0174,V(5),V(31));a(0x0063,V(30),V(31))
c.check(0x0021,[V(30),F(180)],'CR_W1');a(0x000b,V(30),F(-360));c.label('CR_W1')
c.check(0x0023,[F(-180),V(30)],'CR_W2');a(0x000b,V(30),F(360));c.label('CR_W2')
c.check(0x0021,[V(30),F(45)],'CR_T1');c.set(CR_SLOW,1);c.label('CR_T1')
c.check(0x0023,[F(-45),V(30)],'CR_T2');c.set(CR_SLOW,1);c.label('CR_T2')
c.get(17,CR_DT);a(0x0013,V(17),F(CRUISE_TURN))
c.check(0x0025,[V(30),V(17)],'CR_T3');a(0x0087,V(30),V(17));c.label('CR_T3')
a(0x0013,V(17),F(-1));c.check(0x0025,[V(17),V(30)],'CR_T4');a(0x0087,V(30),V(17));c.label('CR_T4')
a(0x005b,V(31),V(30));a(0x0175,V(5),V(31))
c.label('CR_HEAD_DONE')
a(0x0087,V(30),V(19));a(0x0013,V(30),F(.6));a(0x000b,V(30),F(3));c.check(0x0021,[V(30),F(CRUISE_SPEED)],'CR_VT1');a(0x0007,V(30),F(CRUISE_SPEED));c.label('CR_VT1')
c.get(17,CR_SLOW);c.eq(17,1,'CR_VT2');c.check(0x0021,[V(30),F(8)],'CR_VT2');a(0x0007,V(30),F(8));c.label('CR_VT2')
a(0xddc,I(CR_VT),V(30))
a(0x02ce,V(9),V(10),F(1000),V(31))
for ahead in [30,70,120]:
 nxt='CR_ROOF_'+str(ahead);a(0x0407,V(5),F(0),F(ahead),F(0),V(17),V(29),V(30));a(0x02ce,V(17),V(29),F(1000),V(30));c.check(0x0025,[V(30),V(31)],nxt);a(0x0087,V(31),V(30));c.label(nxt)
a(0x000b,V(31),F(CRUISE_CLEAR));a(0x0063,V(31),V(11))
c.check(0x0021,[V(31),F(8)],'CR_LOW_OK');a(0x0007,V(30),F(0));a(0xddc,I(CR_VT),V(30));c.label('CR_LOW_OK')
# v33: no sinking during the long leg (it caused bobbing over uneven roofs); only within 200 m
c.check(0x0021,[V(19),F(200)],'CR_MAY_SINK');c.check(0x0023,[F(0),V(31)],'CR_MAY_SINK');a(0x0007,V(31),F(0));c.label('CR_MAY_SINK')
a(0x0013,V(31),F(1.5))
c.check(0x0021,[V(31),F(CRUISE_CLIMB)],'CR_Z1');a(0x0007,V(31),F(CRUISE_CLIMB));c.label('CR_Z1')
c.check(0x0023,[F(-CRUISE_SINK),V(31)],'CR_Z2');a(0x0007,V(31),F(-CRUISE_SINK));c.label('CR_Z2')
c.get(30,CR_DT);a(0x006b,V(31),V(30));a(0xddc,I(CR_DZ),V(31))
c.get(17,CR_V);c.get(29,CR_VT)
c.check(0x0025,[V(29),V(17)],'CR_DECEL')
a(0x0087,V(31),V(30));a(0x0013,V(31),F(CRUISE_ACCEL));a(0x005b,V(17),V(31));c.check(0x0025,[V(17),V(29)],'CR_V_OK');a(0x0087,V(17),V(29));c.go('CR_V_OK')
c.label('CR_DECEL');a(0x0087,V(31),V(30));a(0x0013,V(31),F(CRUISE_BRAKE));a(0x0063,V(17),V(31));c.check(0x0025,[V(29),V(17)],'CR_V_OK');a(0x0087,V(17),V(29))
c.label('CR_V_OK');a(0xddc,I(CR_V),V(17))
a(0x006b,V(17),V(30));c.check(0x0025,[V(17),V(19)],'CR_S1');a(0x0087,V(17),V(19));c.label('CR_S1')
c.get(30,CR_DX);c.get(29,CR_DY)
c.check(0x0021,[V(19),F(.01)],'CR_NODIR');a(0x0073,V(17),V(19));a(0x006b,V(30),V(17));a(0x006b,V(29),V(17));c.go('CR_DIR')
c.label('CR_NODIR');a(0x0007,V(30),F(0));a(0x0007,V(29),F(0));c.label('CR_DIR')
a(0x0087,V(17),V(9));a(0x005b,V(17),V(30));a(0x005b,V(29),V(10))
c.get(30,CR_DZ);a(0x0087,V(31),V(11));a(0x005b,V(31),V(30))
c.check(0x06bd,[V(9),V(10),V(11),V(17),V(29),V(31),I(1),I(0),I(0),I(1),I(0)],'CR_BLOCKED');c.go('CR_MOVE')
c.label('CR_BLOCKED');a(0x0087,V(17),V(9));a(0x0087,V(29),V(10));a(0x0007,V(30),F(0));a(0xddc,I(CR_V),V(30));c.get(30,CR_DT);a(0x0013,V(30),F(CRUISE_CLIMB));a(0x0087,V(31),V(11));a(0x005b,V(31),V(30))
c.label('CR_MOVE');c.set(DBG_CODE,2);a(0x0063,V(31),V(11));c.get(30,CR_CMDZ);a(0x005b,V(31),V(30))
for v,lo,hi in [(17,-3500,3500),(29,-3500,3500),(31,-200,2000)]:c.check(0x0021,[V(v),F(lo)],'CR_BAD_POS');c.check(0x0023,[F(hi),V(v)],'CR_BAD_POS')
a(0xddc,I(CR_CMDZ),V(31));a(0x00ab,V(5),V(17),V(29),V(31));c.ret()
c.label('CR_BAD_POS');c.set(DBG_CODE,99);c.ret()
# v39: while CJ sits in the helicopter the doors are locked against the player (020A 4), so the
# on-screen exit button no longer makes CJ jump out; the script reads that button (0A52 0) and
# runs the selected exit method instead (command 15). Doors unlock when CJ is outside, and for
# LOCK_HOLD ms after the script itself starts CJ's leave-car task.
c.label('EXIT_BUTTON');c.check(0x0448,[V(18),V(5)],'EXIT_UNLOCK');c.get(19,LOCK_HOLD);c.check(0x001d,[V(20),V(19)],'EXIT_RET')
a(0x020a,V(5),I(4));c.check(0x0a52,[I(EXIT_WIDGET)],'EXIT_RET');c.set(CMD,15);c.ret()
c.label('EXIT_UNLOCK');a(0x020a,V(5),I(1))
c.label('EXIT_RET');c.ret()
c.label('REQUEST_EXIT');c.check(0x0448,[V(18),V(5)],'NOT_ABOARD')
for st in [12,9]:
 nxt='EXIT_NOT_GROUND_'+str(st);c.eq(7,st,nxt);c.go('LEAVE_CJ');c.label(nxt)
c.eq(7,23,'EXIT_NOT_HOVER')
c.label('EXIT_BY_MODE');c.get(19,EXIT_MODE);c.eq(19,1,'EXIT_LAND_NOW');c.go('REQUEST_DEST_ROPE')
c.label('EXIT_LAND_NOW');c.set(AUTO_EXIT,2);c.go('REQUEST_DEST_LAND')
c.label('EXIT_NOT_HOVER')
for st in [1,4,7,11,13,15,16,17]:
 nxt='EXIT_NOT_BUSY_'+str(st);c.eq(7,st,nxt);msg(c,'HCXWAIT');c.go('TICK');c.label(nxt)
c.eq(7,22,'EXIT_HERE');c.set(AUTO_EXIT,1);msg(c,'HCXARR');c.go('TICK')
c.label('EXIT_HERE');a(0x00aa,V(5),V(9),V(10),V(11));a(0x02ce,V(9),V(10),F(1000),V(28));a(0xddc,I(DEST_X),V(9));a(0xddc,I(DEST_Y),V(10));a(0xddc,I(DEST_Z),V(28));c.set(GROVE_WAIT,0);c.set(GROVE_NEXT_SCAN,0);c.set(AVOID_STAGE,0);c.set(AUTO_EXIT,1);c.call('UNFREEZE');a(0x01bd,V(21));state(c,21);msg(c,'HCXHERE');c.go('TICK')
c.label('RESTORE_FLIGHT');a(0x0853,V(5),I(10));a(0x07bb,V(5),I(6));c.ret()
c.label('BLOCK_HOVER');c.call('UNFREEZE');a(0x07bb,V(5),I(0));a(0x0853,V(5),I(10));a(0x00aa,V(5),V(9),V(10),V(11));a(0x04df,V(5),I(0));a(0x04a2,V(5),V(9),V(10),V(11),F(10),V(11));a(0x00ad,V(5),F(21));a(0x04df,V(5),I(1));c.ret()
c.label('SET_LANDING_MISSION');c.call('UNFREEZE');a(0x04df,V(5),I(0));a(0x07bb,V(5),I(0));a(0x0853,V(5),I(3));c.get(19,LAND_FINAL);c.eq(19,1,'LAND_APPROACH_MISSION');c.call('SET_FINAL_LANDING');c.ret()
# Faster long approach; still use native AI and slow before the pad.
c.label('LAND_APPROACH_MISSION');a(0x0087,V(17),V(28));a(0x000b,V(17),F(6));a(0x0743,V(5),V(26),V(27),V(28),F(6),V(17));c.get(19,LAND_SLOW);c.eq(19,1,'LAND_SPEED_FAST');a(0x00ad,V(5),F(8));c.ret()
c.label('LAND_SPEED_FAST');a(0x00ad,V(5),F(25));c.ret()
c.label('SET_FINAL_LANDING');a(0x0743,V(5),V(26),V(27),V(28),F(0),F(0));a(0x00ad,V(5),F(8));c.ret()

c.label('UNFREEZE');c.check(0x056e,[V(5)],'UNFREEZE_DONE');a(0x0574,V(5),I(0))
c.label('UNFREEZE_DONE');c.set(FROZEN,0);c.ret()
c.label('CHANGE_CREW');c.get(29,CREW);c.get(30,ACREW);c.check(0x803b,[V(29),V(30)],'CREW_RETURN')
for value in [0,1,2]:
 nxt='CREW_VALIDATE_'+str(value);c.eq(29,value,nxt);c.go('CREW_LOAD');c.label(nxt)
c.go('CREW_REJECT')
c.label('CREW_LOAD');c.set(BUSY,1);c.get(7,STATE);c.set(STATE,17)
for index,var in enumerate([1,2,3]):a(0xddc,I(SKINSAVE+index),V(var))
for index in range(5):c.set(CREWNEW+index,-1)
a(6,V(1),I(105));a(6,V(2),I(106));a(6,V(3),I(107));c.eq(29,1,'LIVE_CREW_SWAT');a(6,V(1),I(287));a(6,V(2),I(287));a(6,V(3),I(287));c.go('LIVE_CREW_MODELS')
c.label('LIVE_CREW_SWAT');c.eq(29,2,'LIVE_CREW_MODELS');a(6,V(1),I(285));a(6,V(2),I(285));a(6,V(3),I(285))
c.label('LIVE_CREW_MODELS')
for var in [1,2,3]:a(0x0247,V(var))
a(0x038b);a(1,I(0));a(0xd6,I(2))
for var in [1,2,3]:a(0x0248,V(var))
a(0x004d,L('CREW_ROLLBACK'));c.check(0x0256,[I(0)],'CREW_ROLLBACK')
# Stage every living replacement before deleting any old actor.
for index,var,skin in [(0,4,1),(1,13,2),(2,14,3),(3,15,2),(4,16,3)]:
 skip='CREW_STAGE_SKIP_'+str(var);alive(c,var,skip);a(0x00a0,V(var),V(9),V(10),V(11));a(0x0172,V(var),V(17));a(0x0226,V(var),V(6));a(0x04dd,V(var),V(19));a(0x009a,I(8),V(skin),V(9),V(10),V(11),V(29));c.check(0x056d,[V(29)],'CREW_ROLLBACK');a(0xddc,I(CREWNEW+index),V(29));a(0x0619,V(29),I(0));a(0x0173,V(29),V(17));a(0x01c5,V(29));a(0x08af,V(29),I(200 if var==4 else 150));a(0x0223,V(29),V(6));a(0x035f,V(29),V(19));a(0x054a,V(29),I(1));a(0x0446,V(29),I(1));a(0x02e2,V(29),I(100))
 for typ in range(32):a(0x077a,V(29),I(2),I(typ))
 a(0x077a,V(29),I(0),I(0));a(0x077a,V(29),I(0),I(8));c.label(skip)
for index,var,seat in [(0,4,-2),(1,13,1),(2,14,2),(3,15,-1),(4,16,-1)]:
 skip='CREW_COMMIT_SKIP_'+str(var);c.get(29,CREWNEW+index);c.check(0x056d,[V(29)],skip);a(0x0085,V(30),V(var));a(6,V(31),I(0))
 if var!=4:
  c.check(0x0a32,[V(var)],'CREW_COMMIT_SEAT_'+str(var));a(6,V(31),I(1));c.go('CREW_COMMIT_ROLE_'+str(var));c.label('CREW_COMMIT_SEAT_'+str(var));c.check(0x00db,[V(var),V(5)],'CREW_COMMIT_ROLE_'+str(var));a(6,V(31),I(2));c.label('CREW_COMMIT_ROLE_'+str(var))
 a(0x009b,V(30));a(0x0085,V(var),V(29));a(0x0619,V(var),I(1))
 if var==4:
  a(0x036a,V(var),V(5))
 else:
  c.eq(31,1,'CREW_COMMIT_WAS_SEATED_'+str(var));c.call('ATTACH_'+str(var));c.go(skip);c.label('CREW_COMMIT_WAS_SEATED_'+str(var));c.eq(31,2,'CREW_COMMIT_FOOT_'+str(var))
  if seat>=0:a(0x0430,V(var),V(5),I(seat))
  else:c.call('ATTACH_'+str(var))
  c.go(skip);c.label('CREW_COMMIT_FOOT_'+str(var));a(0x04eb,V(var),I(1))
 c.label(skip)
for var in [1,2,3]:a(0x0249,V(var))
a(0xddc,I(STATE),V(7));c.call('PUBLISH');c.get(19,CREWGEN);a(0x000a,V(19),I(1));a(0xddc,I(CREWGEN),V(19));c.call('RESUME_FLIGHT');c.set(BUSY,0);msg(c,'HCCREW');c.ret()
c.label('CREW_ROLLBACK')
for index in range(5):
 skip='CREW_ROLLBACK_SKIP_'+str(index);c.get(29,CREWNEW+index);c.check(0x056d,[V(29)],skip);a(0x009b,V(29));c.label(skip)
for var in [1,2,3]:a(0x0249,V(var))
for index,var in enumerate([1,2,3]):c.get(var,SKINSAVE+index)
a(0xddc,I(STATE),V(7));c.set(BUSY,0);msg(c,'HCCFAIL')
c.label('CREW_REJECT');c.get(19,ACREW);a(0xddc,I(CREW),V(19))
c.label('CREW_RETURN');c.ret()

p=Script();a=p.add
p.label('INIT');a(0);a(6,V(10),I(0));a(6,V(17),I(-999))
p.label('WATCH');a(1,I(50));a(0x01bd,V(20));a(0xddc,I(PANELHEART),V(20));p.get(0,0);p.eq(0,0,'WATCH');p.check(0x0256,[I(0)],'WATCH')
p.get(8,STATE);p.check(0x803b,[V(8),V(17)],'AFTER_NOTICE');a(0x0085,V(17),V(8));p.get(19,HUD);p.eq(19,1,'AFTER_NOTICE')
notice={24:'HCPAT',19:'HCROPE',1:'HCLOAD',2:'HCFOLL',3:'HCHOLD',4:'HCDEPT',5:'HCFAIL',6:'HCOUT',7:'HCEVAC',8:'HCTEAM',9:'HCBOARD',10:'HCGROVE',11:'HCHOME',12:'HCARRIV',13:'HCDAMAG',14:'HCMUST',15:'HCEMERG'}
for st,key in notice.items():
 nxt='NOTICE_NEXT_'+str(st);p.eq(8,st,nxt);a(0x03e5,S(key));p.go('AFTER_NOTICE');p.label(nxt)
p.label('AFTER_NOTICE');p.get(1,OPEN);p.eq(1,1,'WATCH');p.go('ACQUIRE')
p.label('ACQUIRE');p.get(0,0);p.eq(0,0,'WATCH');p.set(OPEN,0);p.set(0,1);a(6,V(10),I(0));p.get(13,HEART);a(1,I(250));p.get(14,HEART);p.check(0x803b,[V(13),V(14)],'CORE_MISSING');a(6,V(2),I(0));a(6,V(3),I(-999));p.go('REFRESH')
p.label('MENU_POLL');a(1,I(50));a(0x01bd,V(20));a(0xddc,I(PANELHEART),V(20));p.check(0x0256,[I(0)],'CLOSE');a(0x0df4,V(1),I(250));p.eq(1,-2,'PICK');p.go('CLOSE')
p.label('PICK');p.eq(1,-1,'HAS_PICK');p.go('CHECK_MENU_STATUS')
p.label('HAS_PICK');p.get(8,STATE)
# Submenu dispatch; local 2 holds page index.
for page,label in [(0,'PICK_MAIN'),(1,'PICK_EVAC'),(2,'PICK_SETUP'),(3,'PICK_CREW'),(4,'PICK_MODEL'),(5,'PICK_FIRE'),(6,'PICK_WEAPON'),(7,'PICK_HUD'),(8,'PICK_INFO')]:
 nxt='PAGE_PICK_NEXT_'+str(page);p.eq(2,page,nxt);p.go(label);p.label(nxt)
p.go('MENU_POLL')
def page(n):
 a(6,V(2),I(n));a(6,V(3),I(-999));p.go('REFRESH')
def pick(index,label):
 nxt='PICK_NOT_'+label+'_'+str(len(p.rows));p.eq(1,index,nxt);p.go(label);p.label(nxt)
p.label('PICK_MAIN')
for index,label in [(0,'DO_CALL'),(1,'DO_FOLLOW'),(2,'DO_HOLD'),(3,'OPEN_EVAC'),(4,'DO_DISMISS'),(5,'OPEN_SETUP'),(6,'OPEN_FIRE'),(7,'CLOSE')]:pick(index,label)
p.go('MENU_POLL')
p.label('OPEN_EVAC');page(1)
p.label('OPEN_SETUP');page(2)
p.label('OPEN_INFO');page(8)
p.label('PICK_EVAC')
for index,label in [(0,'DO_ROPE'),(1,'DO_GROVE'),(2,'DO_MAP'),(3,'TOGGLE_EXIT'),(4,'DO_EXIT_NOW'),(5,'DO_TAKEOFF'),(6,'OPEN_MAIN')]:pick(index,label)
p.go('MENU_POLL')
p.label('DO_ROPE');p.set(CMD,10);a(1,I(200));p.go('CHECK_MENU_STATUS')
p.label('OPEN_MAIN');page(0)
# v39: one item switches the exit method used by the exit button and EXIT NOW
p.label('TOGGLE_EXIT');p.get(9,EXIT_MODE);p.eq(9,0,'TOGGLE_TO_LAND');p.set(EXIT_MODE,1);a(6,V(3),I(-999));p.go('REFRESH')
p.label('TOGGLE_TO_LAND');p.set(EXIT_MODE,0);a(6,V(3),I(-999));p.go('REFRESH')
p.label('PICK_SETUP')
for index,label in [(0,'OPEN_CREW'),(1,'OPEN_MODEL'),(2,'OPEN_FIRE'),(3,'OPEN_WEAPON'),(4,'OPEN_HUD'),(5,'DO_PATROL'),(6,'OPEN_MAIN')]:pick(index,label)
p.go('MENU_POLL')
for label,n in [('OPEN_CREW',3),('OPEN_MODEL',4),('OPEN_FIRE',5),('OPEN_WEAPON',6),('OPEN_HUD',7)]:p.label(label);page(n)
for key,pag,choices in [(CREW,3,[(0,0),(1,1),(2,2)]),(MODEL,4,[(0,487),(1,497),(2,425)]),(FIRE,5,[(0,0),(1,3),(2,2),(3,1),(4,4)]),(WEAPON_SETTING,6,[(0,0),(1,29),(2,30),(3,31),(4,34)]),(HUD,7,[(0,1),(1,0)])]:
 label={3:'PICK_CREW',4:'PICK_MODEL',5:'PICK_FIRE',6:'PICK_WEAPON',7:'PICK_HUD'}[pag];p.label(label)
 for idx,val in choices:
  nxt='OPTION_NEXT_'+str(pag)+'_'+str(idx);p.eq(1,idx,nxt);p.set(key,val);a(6,V(3),I(-999));p.go('REFRESH');p.label(nxt)
 p.go('OPEN_SETUP')
p.label('PICK_INFO');p.go('OPEN_MAIN')
for label,cmd in [('DO_EXIT_NOW',15),('DO_CALL',1),('DO_FOLLOW',2),('DO_HOLD',3),('DO_DISMISS',4),('DO_EVAC',5),('DO_BOARD',6),('DO_GROVE',7),('DO_LEAVE',8),('DO_TAKEOFF',9),('DO_MAP',11),('DO_DEST_LAND',12),('DO_DEST_ROPE',13),('DO_PATROL',14)]:
 p.label(label)
 # No commands while spawning/departing. Ground muster can still be changed through EVAC.
 for st in [1,4,13]:
  nxt='ALLOW_'+label+'_'+str(st);p.eq(8,st,nxt);p.go('MENU_POLL');p.label(nxt)
 p.set(CMD,cmd);a(1,I(200));p.go('CHECK_MENU_STATUS')
p.label('CHECK_MENU_STATUS');p.eq(2,0,'INFO_STATUS_CHECK');p.get(8,STATE);p.check(0x803b,[V(8),V(3)],'MENU_POLL');p.go('REFRESH')
p.label('INFO_STATUS_CHECK');p.eq(2,1,'CREW_STATUS_CHECK');p.get(8,STATE);p.check(0x803b,[V(8),V(3)],'MENU_POLL');p.go('REFRESH')
p.label('CREW_STATUS_CHECK');p.eq(2,3,'HELI_STATUS_CHECK');p.get(19,CREW);p.check(0x803b,[V(19),V(3)],'MENU_POLL');p.go('REFRESH')
p.label('HELI_STATUS_CHECK');p.eq(2,4,'INFO_STATUS_PAGE');p.get(19,MODEL);p.check(0x803b,[V(19),V(3)],'MENU_POLL');p.go('REFRESH')
p.label('INFO_STATUS_PAGE');p.eq(2,8,'MENU_POLL');p.get(8,STATE);p.get(9,HP);a(0x0085,V(19),V(8));a(0x0012,V(19),I(10));p.check(0x0019,[V(9),I(350)],'INFO_CRITICAL');p.check(0x0019,[V(9),I(700)],'INFO_DAMAGED');a(0x000a,V(19),I(2));p.go('INFO_CHECK_KEY')
p.label('INFO_DAMAGED');a(0x000a,V(19),I(1));p.go('INFO_CHECK_KEY')
p.label('INFO_CRITICAL')
p.label('INFO_CHECK_KEY');p.check(0x803b,[V(19),V(3)],'MENU_POLL');p.go('REFRESH')
p.label('REFRESH');a(0x0df3)
for pageid in range(9):
 nxt='DRAW_NEXT_'+str(pageid);p.eq(2,pageid,nxt);p.go('DRAW_'+str(pageid));p.label(nxt)
p.go('CLOSE')
p.label('DRAW_0');p.get(8,STATE);a(0x0085,V(3),V(8))
for st in STATES:
 nxt='DRAW_MAIN_NEXT_'+str(st);p.eq(8,st,nxt);a(0xdd0,V(4),L('MAIN_'+str(st)));p.go('SHOW_8');p.label(nxt)
a(0xdd0,V(4),L('MAIN_0'));p.go('SHOW_8')
p.label('DRAW_1');p.get(8,STATE);a(0x0085,V(3),V(8));p.get(9,EXIT_MODE)
for st in STATES:
 nxt='DRAW_EVAC_NEXT_'+str(st);land='DRAW_EVAC_LAND_'+str(st);p.eq(8,st,nxt);p.eq(9,1,land);a(0xdd0,V(4),L('EVAC_%d_1'%st));p.go('SHOW_7');p.label(land);a(0xdd0,V(4),L('EVAC_%d_0'%st));p.go('SHOW_7');p.label(nxt)
a(0xdd0,V(4),L('EVAC_0_0'));p.go('SHOW_7')
p.label('DRAW_2');a(0xdd0,V(4),L('SETUP_MENU'));p.go('SHOW_7')
for pageid,key,values in [(3,CREW,[0,1,2]),(4,MODEL,[487,497,425]),(5,FIRE,[0,3,2,1,4]),(6,WEAPON_SETTING,[0,29,30,31,34]),(7,HUD,[1,0])]:
 p.label('DRAW_'+str(pageid));p.get(8,key);a(0x0085,V(3),V(8))
 for val in values:
  nxt='DRAW_PREF_NEXT_'+str(pageid)+'_'+str(val);p.eq(8,val,nxt);a(0xdd0,V(4),L('PREF_'+str(pageid)+'_'+str(val)));p.go('SHOW_'+str(len(values)+1));p.label(nxt)
 a(0xdd0,V(4),L('PREF_'+str(pageid)+'_'+str(values[0])));p.go('SHOW_'+str(len(values)+1))
p.label('DRAW_8');p.get(8,STATE);p.get(9,HP);a(0x0085,V(3),V(8));a(0x0012,V(3),I(10));a(6,V(19),I(0));p.check(0x0019,[V(9),I(350)],'INFO_BUILD');a(6,V(19),I(1));p.check(0x0019,[V(9),I(700)],'INFO_BUILD');a(6,V(19),I(2))
p.label('INFO_BUILD');a(0x005a,V(3),V(19))
for st in STATES:
 for hull in range(3):
  nxt='INFO_NEXT_'+str(st)+'_'+str(hull);p.eq(3,st*10+hull,nxt);a(0xdd0,V(4),L('INFO_'+str(st)+'_'+str(hull)));p.go('SHOW_3');p.label(nxt)
a(0xdd0,V(4),L('INFO_0_0'));p.go('SHOW_3')
for count in [3,4,5,6,7,8]:p.label('SHOW_'+str(count));a(0xdf2,V(4),I(count));p.go('MENU_POLL')
p.label('CORE_MISSING');a(0xdd0,V(4),L('OFFLINE_MENU'));a(0xdf2,V(4),I(1))
p.label('OFFLINE_POLL');a(1,I(50));a(0x01bd,V(20));a(0xddc,I(PANELHEART),V(20));p.check(0x0256,[I(0)],'CLOSE');a(0xdf4,V(1),I(250));p.eq(1,-1,'CLOSE');p.go('OFFLINE_POLL')
p.label('CLOSE');a(0xdf3);p.set(OPEN,0);p.set(0,0);a(6,V(10),I(0));p.go('WATCH')
# All menus fit on one page (<=8 rows); metadata is appended beyond terminating branches.
for st,title in STATES.items():
 rows=['CALL SUPPORT','FOLLOW CJ','HOLD POSITION','EVACUATION >','DISMISS SUPPORT','SETUP >','FIRE CONTROL >','CLOSE']
 if st in [1,4,13]:rows[0]='PLEASE WAIT'
 if st==2:rows[1]='FOLLOW CJ [ON]'
 if st==3:rows[2]='HOLD POSITION [ON]'
 p.blob('MAIN_'+str(st),'HELICOVER / '+title,rows)
p.blob('OFFLINE_MENU','HELICOVER / OFFLINE',['INSTALL CORE + RESTART'])
for st,title in STATES.items():
 for mode in [0,1]:p.blob('EVAC_%d_%d'%(st,mode),'EVAC / '+title,['ROPE EVACUATION','FLY TO GROVE','FLY TO MAP MARKER','EXIT MODE: '+('ROPE' if mode else 'LAND'),'EXIT NOW','TAKE OFF / FOLLOW','< BACK'])
p.blob('SETUP_MENU','HELICOVER / SETUP',['CREW >','HELICOPTER >','FIRE MODE >','WEAPONS >','STATUS MESSAGES >','PATROL AROUND CJ','< BACK'])
for pg,title,values,labels in [(3,'CREW / LIVE',[0,1,2],['GROVE','ARMY','SWAT']), (4,'HELICOPTER / LIVE',[487,497,425],['MAVERICK','POLICE MAVERICK','HUNTER / NO EVAC']), (5,'FIRE CONTROL',[0,3,2,1,4],['CEASE FIRE','PROTECT CJ','FOLLOW CJ SHOTS','WEAPONS FREE','OVERWATCH']), (6,'WEAPONS / LIVE',[0,29,30,31,34],['AUTO BY CREW','MP5','AK-47','M4','SNIPER RIFLE']), (7,'STATUS MESSAGES',[1,0],['ENABLED','DISABLED'])]:
 for val in values:
  rows=[text+(' [ON]' if values[i]==val else '') for i,text in enumerate(labels)]+['< BACK']
  p.blob('PREF_'+str(pg)+'_'+str(val),title,rows)
for st,title in STATES.items():
 for hull,hullname in [(0,'CRITICAL'),(1,'DAMAGED'),(2,'HEALTHY')]:
  info='NO ACTIVE SUPPORT' if st in [0,1,5,6] else 'HULL: '+hullname
  p.blob('INFO_'+str(st)+'_'+str(hull),'STATUS / '+title,[info,'EVAC: GROVE STREET','< BACK'])

launch=Script();a=launch.add
launch.label('ENTRY');a(0);a(1,I(400));launch.get(1,PANELHEART);a(1,I(250));launch.get(2,PANELHEART);launch.check(0x803b,[V(1),V(2)],'MISSING');launch.set(OPEN,1);a(0x004e)
launch.label('MISSING');a(0x03e5,S('HCOFF'));a(0x004e)

# Dedicated fire worker: no global faction hatred and no automatic armed turrets.
f=Script();a=f.add
f.label('INIT');a(0);f.set(FIRENEXT,0);f.set(FIREGEN,-1);f.set(FWANTED,-1);f.set(FIRE_ACTIVE,0);f.set(FIRE_TARGET,-1);f.set(FIRE_TASK_TARGET,-1);f.set(FIRE_TASK_PHASE,-1);f.set(FIRE_TASK_MODE,-1);f.set(FIRE_TASK_NEXT,0);f.set(FIRE_SCAN_NEXT,0);a(6,V(26),I(-1));a(6,V(27),I(0));a(6,V(29),I(-1))
f.label('WAIT');a(1,I(0));a(0x01bd,V(30));a(0xddc,I(FIREHEART),V(30));f.get(30,BUSY);f.eq(30,0,'WAIT');f.get(30,STATE)
for stateid in [0,1,5,6,16]:
 nxt='FSTATE_NEXT_'+str(stateid);f.eq(30,stateid,nxt);f.go('WAIT');f.label(nxt)
for index in range(7):f.get(index,PUB+index)
f.get(30,CREWGEN);f.get(31,FIREGEN);f.check(0x003b,[V(30),V(31)],'FIRE_CREW_CHANGED');f.go('FIRE_CREW_READY')
f.label('FIRE_CREW_CHANGED');a(0xddc,I(FIREGEN),V(30));a(6,V(26),I(-1))
f.label('FIRE_CREW_READY');f.get(7,WPN);f.get(28,PHASE);f.eq(28,2,'FIRE_MODE');f.set(FIRE_ACTIVE,0);f.set(FIRE_TARGET,-1);f.set(FIRE_TASK_TARGET,-1);f.go('WAIT')
f.label('FIRE_MODE');f.get(25,FIRE);f.check(0x003b,[V(25),V(26)],'MODE_CHANGED');f.go('MODE_READY')
f.label('MODE_CHANGED');f.eq(26,-1,'MODE_REPORT')
f.go('MODE_REPORT_DONE');f.label('MODE_REPORT')
for m in range(5):
 nxt='MODE_REPORT_NOT_'+str(m);f.eq(25,m,nxt);msg(f,'HCFM'+str(m));f.go('MODE_REPORT_DONE');f.label(nxt)
f.label('MODE_REPORT_DONE');f.set(FWANTED,-1);f.set(FIRE_ACTIVE,0);f.set(FIRE_TARGET,-1);f.set(FIRE_TASK_TARGET,-1);f.set(FIRE_TASK_MODE,-1);f.set(FIRE_SCAN_NEXT,0);a(0x0085,V(26),V(25));a(6,V(29),I(-1));a(6,V(27),I(0))
for var in [3,4,5,6]:
 skip='MODE_CLEAR_'+str(var);alive(f,var,skip);a(0x0687,V(var))
 for typ in range(32):a(0x077a,V(var),I(2),I(typ))
 f.eq(25,1,'MODE_PROTECT_GANG_'+str(var))
 for typ in range(4,32):
  if typ!=8:a(0x077a,V(var),I(4),I(typ))
 f.go('MODE_RESPECT_'+str(var));f.label('MODE_PROTECT_GANG_'+str(var));f.eq(25,3,'MODE_RESPECT_'+str(var))
 for typ in range(7,17):
  if typ!=8:a(0x077a,V(var),I(4),I(typ))
 f.label('MODE_RESPECT_'+str(var));a(0x077a,V(var),I(0),I(0));a(0x077a,V(var),I(0),I(8));f.label(skip)
f.label('MODE_READY');f.call('KILL_CHECK');f.label('ARM_GUARDS');f.get(30,FIRENEXT);a(0x01bd,V(31));f.check(0x001d,[V(31),V(30)],'WAIT');f.eq(25,4,'ARM_FAST');a(0x000a,V(31),I(OVERWATCH_CADENCE));f.go('ARM_NEXT_SET');f.label('ARM_FAST');a(0x000a,V(31),I(150));f.label('ARM_NEXT_SET');a(0xddc,I(FIRENEXT),V(31))
for var in [3,4,5,6]:
 skip='ARM_SKIP_'+str(var);alive(f,var,skip);a(0x0470,V(var),V(30));f.check(0x803b,[V(30),V(7)],skip);a(0x01b2,V(var),V(7),I(30000));a(0x01b9,V(var),V(7));a(0x02e2,V(var),I(100));a(0x07dd,V(var),I(100));f.label(skip)
f.eq(25,0,'ACTIVE_MODE');f.go('WAIT')
f.label('ACTIVE_MODE');f.eq(25,3,'CHECK_ALL_MODE');f.call('REFRESH_PROTECT_POLICE');f.call('FIND_PROTECT_NPC');alive(f,29,'NO_TARGET');f.call('SHOOT_CHAR');f.go('WAIT')
f.label('CHECK_ALL_MODE');f.eq(25,1,'FOLLOW_SHOTS');f.call('FIND_ANY_NPC');alive(f,29,'NO_TARGET');f.call('SHOOT_CHAR');f.go('WAIT')
f.label('NO_TARGET');f.call('STOP_COMBAT');f.call('CLEAR_CHECK');f.go('WAIT')
# v39-fire OVERWATCH: precision fire on armed hostiles only (guns/grenades; police only when wanted)
f.label('OVERWATCH_MODE');f.eq(25,4,'WAIT');f.call('FIND_ARMED_HOSTILE');alive(f,29,'NO_TARGET');f.call('SHOOT_CHAR');f.go('WAIT')
f.label('FOLLOW_SHOTS');f.eq(25,2,'OVERWATCH_MODE');f.check(0x02e0,[V(0)],'SILENCE');a(6,V(27),I(1))
# Aiming at a friendly suppresses assistance even before the camera ray is evaluated.
for var in [2,3,4,5,6]:
 skip='AIM_FRIEND_SKIP_'+str(var);alive(f,var,skip);f.check(0x8457,[I(0),V(var)],'SILENCE');f.label(skip)
# Check the game's actual auto-aim target across nearby cells before estimating a free-aim ray.
f.call('FIND_CJ_AIMED');alive(f,29,'AIM_RAY');f.call('SHOOT_CHAR');f.go('WAIT')
f.label('AIM_RAY');a(0x068d,V(8),V(9),V(10));a(0x068e,V(11),V(12),V(13))
for dest,point,origin in [(14,11,8),(15,12,9),(16,13,10)]:a(0x0087,V(dest),V(point));a(0x0063,V(dest),V(origin))
a(0x050a,V(8),V(9),V(10),V(11),V(12),V(13),V(17));f.check(0x0021,[V(17),F(.01)],'SILENCE')
for var in [14,15,16]:a(0x0073,V(var),V(17))
# Start the ray just ahead of CJ so a third-person camera does not hit CJ's back.
a(0x00a0,V(0),V(22),V(23),V(24));a(0x050a,V(8),V(9),V(10),V(22),V(23),V(24),V(18));a(0x000b,V(18),F(1.5))
for origin,direction in [(8,14),(9,15),(10,16)]:a(0x0087,V(21),V(direction));a(0x006b,V(21),V(18));a(0x005b,V(origin),V(21))
a(0x0007,V(18),F(0));a(0x0007,V(19),F(180));a(6,V(20),I(0))
f.label('RAY_STEP');a(0x0087,V(21),V(18));a(0x005b,V(21),V(19));a(0x0013,V(21),F(.5))
for point,origin,direction in [(22,8,14),(23,9,15),(24,10,16)]:a(0x0087,V(point),V(direction));a(0x006b,V(point),V(21));a(0x005b,V(point),V(origin))
f.check(0x06bd,[V(8),V(9),V(10),V(22),V(23),V(24),I(1),I(1),I(1),I(1),I(0)],'RAY_BLOCKED');a(0x0087,V(18),V(21));f.go('RAY_NEXT')
f.label('RAY_BLOCKED');a(0x0087,V(19),V(21))
f.label('RAY_NEXT');a(0x000a,V(20),I(1));f.check(0x0019,[V(20),I(11)],'RAY_STEP')
for point,origin,direction in [(22,8,14),(23,9,15),(24,10,16)]:a(0x0087,V(point),V(direction));a(0x006b,V(point),V(19));a(0x005b,V(point),V(origin))
# Reject a coordinate at or immediately beside CJ or our team.
for var in [0,2,3,4,5,6]:
 skip='COORD_FRIEND_SKIP_'+str(var);alive(f,var,skip);a(0x00a0,V(var),V(11),V(12),V(13));a(0x050a,V(11),V(12),V(13),V(22),V(23),V(24),V(30));f.check(0x0021,[V(30),F(3)],'SILENCE');f.label(skip)
f.call('SHOOT_COORD');f.go('WAIT')
f.label('SILENCE');f.eq(27,1,'WAIT');a(6,V(27),I(0));f.set(FIRE_ACTIVE,0);f.set(FIRE_TARGET,-1);f.set(FIRE_TASK_TARGET,-1);f.set(FIRE_TASK_MODE,-1)
for var in [3,4,5,6]:
 skip='SILENCE_SKIP_'+str(var);alive(f,var,skip);a(0x0687,V(var));f.label(skip)
f.go('WAIT')
f.label('NOT_FRIEND');a(6,V(30),I(0))
for var in [0,2,3,4,5,6]:
 f.check(0x803b,[V(29),V(var)],'FRIEND_FOUND')
for i in range(5):
 f.get(31,GROUND_PUB+i);f.check(0x803b,[V(29),V(31)],'FRIEND_FOUND')
a(6,V(30),I(1));f.ret()
f.label('FRIEND_FOUND');f.ret()
f.label('STOP_COMBAT');f.get(30,FIRE_ACTIVE);f.eq(30,1,'STOP_COMBAT_END');f.set(FIRE_ACTIVE,0);f.set(FIRE_TASK_TARGET,-1);f.set(FIRE_TASK_MODE,-1)
for var in [3,4,5,6]:
 skip='STOP_COMBAT_GUARD_'+str(var);alive(f,var,skip);a(0x0687,V(var));f.label(skip)
f.label('STOP_COMBAT_END');f.set(FIRE_TARGET,-1);f.ret()

# Do not restart a 2.5-second aiming/firing task every 150 ms; reissue on a new
# target, new seating phase, or after 1.8 seconds. Keep emitting checked rounds.
f.label('SHOOT_CHAR');f.set(CLEAR_AT,0);f.get(30,LAST_TGT);f.check(0x003b,[V(30),V(29)],'SC_NEW_TARGET');f.go('SC_KNOWN')
f.label('SC_NEW_TARGET');a(0xddc,I(LAST_TGT),V(29));f.get(30,ENGAGED);f.eq(30,0,'SC_KNOWN');f.set(ENGAGED,1);msg(f,'HCCONT')
f.label('SC_KNOWN');f.set(FIRE_ACTIVE,1);a(0xddc,I(FIRE_TARGET),V(29));f.get(30,FIRE_TASK_MODE);f.eq(30,1,'CHAR_ISSUE_TASKS');f.get(30,FIRE_TASK_TARGET);f.check(0x003b,[V(30),V(29)],'CHAR_ISSUE_TASKS');f.get(30,FIRE_TASK_PHASE);f.check(0x003b,[V(30),V(28)],'CHAR_ISSUE_TASKS');f.get(30,FIRE_TASK_NEXT);a(0x01bd,V(31));f.check(0x001d,[V(31),V(30)],'CHAR_PRECISE')
f.label('CHAR_ISSUE_TASKS');f.set(FIRE_TASK_MODE,1);a(0xddc,I(FIRE_TASK_TARGET),V(29));a(0xddc,I(FIRE_TASK_PHASE),V(28));a(0x01bd,V(31));a(0x000a,V(31),I(1800));a(0xddc,I(FIRE_TASK_NEXT),V(31))
for i in range(4):f.set(GUARD_TARGET+i,-1)
for var in [3,4,5,6]:
 f.call('SELECT_GUARD_TARGET_'+str(var));a(0xddc,I(GUARD_TARGET+var-3),V(29))
 skip='SHOOT_CHAR_SKIP_'+str(var);alive(f,var,skip);f.check(0x00db,[V(var),V(1)],'SHOOT_CHAR_ONFOOT_'+str(var));f.check(0x8a32,[V(var)],'SHOOT_CHAR_ONFOOT_'+str(var));a(0x0713,V(var),V(29),I(-1),F(0),F(0),F(0),F(150),I(0),I(1 if var in [3,5] else 0),I(100));f.go(skip)
 f.label('SHOOT_CHAR_ONFOOT_'+str(var));a(0x074d,V(var),V(29),I(2500));f.label(skip)
f.label('CHAR_PRECISE');f.get(29,FIRE_TASK_TARGET);alive(f,29,'CHAR_DONE');a(0x00a0,V(29),V(11),V(12),V(13));a(0x000b,V(13),F(.25));a(6,V(7),I(0));f.check(0x80df,[V(29)],'CHAR_TARGET_IN_CAR');f.go('CHAR_TARGET_READY')
f.label('CHAR_TARGET_IN_CAR');f.call('TARGET_CAR_SAFE');f.eq(30,1,'CHAR_DONE');a(6,V(7),I(1))
f.label('CHAR_TARGET_READY');f.call('PRECISE_BULLETS')
f.label('CHAR_DONE');f.ret()

f.label('SHOOT_COORD');f.set(FIRE_ACTIVE,1);f.set(FIRE_TARGET,-1);f.get(30,FIRE_TASK_MODE);f.eq(30,2,'COORD_ISSUE_TASKS');f.get(30,FIRE_TASK_NEXT);a(0x01bd,V(31));f.check(0x001d,[V(31),V(30)],'COORD_PRECISE')
f.label('COORD_ISSUE_TASKS');f.set(FIRE_TASK_MODE,2);f.set(FIRE_TASK_TARGET,-1);a(0x01bd,V(31));a(0x000a,V(31),I(400));a(0xddc,I(FIRE_TASK_NEXT),V(31))
for var in [3,4,5,6]:
 skip='SHOOT_COORD_SKIP_'+str(var);alive(f,var,skip);f.check(0x00db,[V(var),V(1)],'SHOOT_COORD_ONFOOT_'+str(var));f.check(0x8a32,[V(var)],'SHOOT_COORD_ONFOOT_'+str(var));a(0x0713,V(var),I(-1),I(-1),V(22),V(23),V(24),F(150),I(0),I(1 if var in [3,5] else 0),I(100));f.go(skip)
 f.label('SHOOT_COORD_ONFOOT_'+str(var));a(0x0668,V(var),V(22),V(23),V(24),I(600));f.label(skip)
f.label('COORD_PRECISE')
for dst,src in [(11,22),(12,23),(13,24)]:a(0x0087,V(dst),V(src))
a(6,V(7),I(0));f.call('PRECISE_BULLETS');f.ret()

# Do not damage the helicopter, CJ's current vehicle, squad occupants or Grove
# occupants in president mode when the chosen hostile is inside a vehicle.
f.label('TARGET_CAR_SAFE');a(0x03c0,V(29),V(22));f.check(0x056e,[V(22)],'TARGET_CAR_UNSAFE');f.check(0x803b,[V(22),V(1)],'TARGET_CAR_UNSAFE');f.check(0x80db,[V(0),V(22)],'TARGET_CAR_UNSAFE');a(0x01ea,V(22),V(8))
# Passenger getter 0432 is implicated in an AML crash log. Avoid it entirely.
# Suppress precision shots at vehicles with any occupied passenger seat.
for seat in [0,1,2]:
 nxt='CAR_PASSENGER_CLEAR_'+str(seat);f.check(0x0019,[V(8),I(seat)],nxt);f.check(0x0431,[V(22),I(seat)],'TARGET_CAR_UNSAFE');f.label(nxt)
for seat in [-1]:
 nxt='SAFE_CAR_OCCUPANT_'+str(seat).replace('-','M')
 if seat<0:a(0x046c,V(22),V(31))
 else:f.check(0x0019,[V(8),I(seat)],nxt);f.check(0x8431,[V(22),I(seat)],nxt);a(0x0432,V(22),I(seat),V(31))
 alive(f,31,nxt)
 for friend in [0,2,3,4,5,6]:f.check(0x803b,[V(31),V(friend)],'TARGET_CAR_UNSAFE')
 for i in range(5):
  f.get(30,GROUND_PUB+i);f.check(0x803b,[V(31),V(30)],'TARGET_CAR_UNSAFE')
 f.eq(25,3,nxt)
 for model in [105,106,107]:f.check(0x82f2,[V(31),I(model)],'TARGET_CAR_UNSAFE')
 a(0x089f,V(31),V(30));f.check(0x8039,[V(30),I(8)],'TARGET_CAR_UNSAFE');f.label(nxt)
a(6,V(30),I(1));f.ret()
f.label('TARGET_CAR_UNSAFE');a(6,V(30),I(0));f.ret()

# One checked shot per living guard every 150 ms, toward the current target point.
# The game's bullet operation handles collision and the visual trace; reject a line
# containing any protected actor, building, object or intervening vehicle.
f.label('PRECISE_BULLETS')
for var in [3,4,5,6]:
 skip='PRECISE_SKIP_'+str(var);onfoot='PRECISE_CHECK_ATTACH_'+str(var);origin='PRECISE_ORIGIN_'+str(var);pedmin='PRECISE_PED_MIN_'+str(var);minready='PRECISE_MIN_READY_'+str(var);pedcut='PRECISE_PED_CUT_'+str(var);cutready='PRECISE_CUT_READY_'+str(var)
 f.get(30,FIRE_TASK_MODE);f.eq(30,1,'PRECISE_MODE_DONE_'+str(var));f.get(29,GUARD_TARGET+var-3);alive(f,29,skip);a(6,V(7),I(0));f.check(0x80df,[V(29)],'PRECISE_CAR_'+str(var));f.go('PRECISE_TARGET_DONE_'+str(var));f.label('PRECISE_CAR_'+str(var));f.call('TARGET_CAR_SAFE');f.eq(30,1,skip);a(6,V(7),I(1));f.label('PRECISE_TARGET_DONE_'+str(var));a(0x00a0,V(29),V(11),V(12),V(13));a(0x000b,V(13),F(.25));f.label('PRECISE_MODE_DONE_'+str(var))
 alive(f,var,skip);a(0x00a0,V(var),V(8),V(9),V(10));a(0x000b,V(10),F(.25));a(0x050a,V(8),V(9),V(10),V(11),V(12),V(13),V(17));f.check(0x0023,[F(150),V(17)],skip)
 a(0x0007,V(31),F(.8));f.check(0x00db,[V(var),V(1)],onfoot);a(0x0007,V(31),F(5.5));f.go(origin)
 f.label(onfoot);f.check(0x0a32,[V(var)],origin);a(0x0007,V(31),F(5.5));f.label(origin)
 a(0x0087,V(30),V(31));f.eq(7,1,pedmin);a(0x000b,V(30),F(6));f.go(minready);f.label(pedmin);a(0x000b,V(30),F(2));f.label(minready);f.check(0x0025,[V(17),V(30)],skip)
 for dst,aim,start in [(14,11,8),(15,12,9),(16,13,10)]:a(0x0087,V(dst),V(aim));a(0x0063,V(dst),V(start));a(0x0073,V(dst),V(17))
 for dst,start,direction in [(18,8,14),(19,9,15),(20,10,16)]:a(0x0087,V(dst),V(direction));a(0x006b,V(dst),V(31));a(0x005b,V(dst),V(start))
 f.eq(7,1,pedcut);a(0x0007,V(31),F(5.5));f.go(cutready);f.label(pedcut);a(0x0007,V(31),F(1.4));f.label(cutready)
 for dst,aim,direction in [(22,11,14),(23,12,15),(24,13,16)]:a(0x0087,V(dst),V(direction));a(0x006b,V(dst),V(31));a(0x0087,V(21),V(aim));a(0x0063,V(21),V(dst));a(0x0087,V(dst),V(21))
 f.check(0x06bd,[V(18),V(19),V(20),V(22),V(23),V(24),I(1),I(1),I(1),I(1),I(0)],skip)
 # Check the entire bullet segment against CJ, the pilot and all other guards.
 for friend in [0,2,3,4,5,6,100,101,102,103,104]:
  if friend==var:continue
  if friend>=100:f.get(31,GROUND_PUB+friend-100);friend_var=31
  else:friend_var=friend
  friend_done='PRECISE_FRIEND_DONE_'+str(var)+'_'+str(friend);alive(f,friend_var,friend_done);a(0x00a0,V(friend_var),V(8),V(9),V(10));a(0x000b,V(10),F(.25))
  for coord,offset in [(8,18),(9,19),(10,20)]:a(0x0063,V(coord),V(offset))
  a(0x0087,V(21),V(8));a(0x006b,V(21),V(14));a(0x0087,V(30),V(9));a(0x006b,V(30),V(15));a(0x005b,V(21),V(30));a(0x0087,V(30),V(10));a(0x006b,V(30),V(16));a(0x005b,V(21),V(30));f.check(0x0021,[V(21),F(0)],friend_done);f.check(0x0025,[V(17),V(21)],friend_done)
  for coord,direction in [(8,14),(9,15),(10,16)]:a(0x0087,V(30),V(direction));a(0x006b,V(30),V(21));a(0x0063,V(coord),V(30))
  a(0x050a,V(8),V(9),V(10),F(0),F(0),F(0),V(30));f.check(0x0021,[V(30),F(1.25)],skip);f.label(friend_done)
 for dst,aim,direction in [(22,11,14),(23,12,15),(24,13,16)]:a(0x0087,V(dst),V(direction));a(0x0013,V(dst),F(.6));a(0x005b,V(dst),V(aim))
 f.eq(25,4,'PB_STD_'+str(var));a(0x06bc,V(18),V(19),V(20),V(22),V(23),V(24),I(OVERWATCH_DAMAGE));f.go(skip);f.label('PB_STD_'+str(var));a(0x06bc,V(18),V(19),V(20),V(22),V(23),V(24),I(18));f.label(skip)
f.ret()

f.label('REFRESH_PROTECT_POLICE');a(0x01c0,I(0),V(30));f.get(31,FWANTED);f.check(0x803b,[V(30),V(31)],'PROTECT_POLICE_DONE');a(0xddc,I(FWANTED),V(30))
for var in [3,4,5,6]:
 skip='POLICE_REL_SKIP_'+str(var);alive(f,var,skip);f.check(0x0019,[V(30),I(0)],'POLICE_REL_NEUTRAL_'+str(var));a(0x077a,V(var),I(4),I(6));f.go(skip);f.label('POLICE_REL_NEUTRAL_'+str(var));a(0x077a,V(var),I(2),I(6));f.label(skip)
f.label('PROTECT_POLICE_DONE');f.ret()
# No-save searches do not convert ordinary pedestrians or vehicles into mission entities.
# Fine cells near CJ find a melee attacker even among other pedestrians; larger cells
# cover nearby streets. Broader scanning runs at most once per 600 ms.
near_cells=[(x,y) for x in [0,-3,3] for y in [0,-3,3]]
wide_cells=[(x,y) for x in [0,-40,40,-80,80] for y in [0,-40,40,-80,80]]
def scan_foot(cells,half,zhalf,check,prefix):
 for index,(x,y) in enumerate(cells):
  nxt=prefix+'_FOOT_NEXT_'+str(index);a(0x00a0,V(0),V(8),V(9),V(10));a(0x000b,V(8),F(x));a(0x000b,V(9),F(y));a(0x0a3e,V(8),V(9),V(10),F(half),F(half),F(zhalf),V(29));alive(f,29,nxt);f.call(check);f.eq(30,1,nxt);f.ret();f.label(nxt)
def scan_vehicles(cells,half,check,prefix):
 for index,(x,y) in enumerate(cells):
  nxt=prefix+'_CAR_NEXT_'+str(index);a(0x00a0,V(0),V(8),V(9),V(10));a(0x0087,V(11),V(8));a(0x0087,V(12),V(9));a(0x000b,V(8),F(x-half));a(0x000b,V(9),F(y-half));a(0x000b,V(11),F(x+half));a(0x000b,V(12),F(y+half));a(0x053e,V(8),V(9),V(11),V(12),I(-1),V(23));f.call(check);f.eq(30,1,nxt);f.ret();f.label(nxt)

# Assign different eligible visible pedestrians when available; otherwise share the primary threat.
for guard in [3,4,5,6]:
 f.label('SELECT_GUARD_TARGET_'+str(guard))
 if guard==3:f.get(29,FIRE_TASK_TARGET);f.ret()
 else:
  f.eq(25,2,'SELECT_SCAN_'+str(guard));f.get(29,FIRE_TASK_TARGET);f.ret();f.label('SELECT_SCAN_'+str(guard))
  for index,(x,y) in enumerate([(0,0),(-12,0),(12,0),(0,-12),(0,12),(-24,0),(24,0),(0,-24),(0,24),(-40,-40),(40,-40),(-40,40),(40,40)]):
   nxt='SELECT_NEXT_'+str(guard)+'_'+str(index);a(0x00a0,V(0),V(8),V(9),V(10));a(0x000b,V(8),F(x));a(0x000b,V(9),F(y));a(0x0a3e,V(8),V(9),V(10),F(8),F(8),F(40),V(29));alive(f,29,nxt)
   for prior in range(guard-3):f.get(31,GUARD_TARGET+prior);f.check(0x803b,[V(29),V(31)],nxt)
   f.eq(25,3,'SELECT_ANY_'+str(guard)+'_'+str(index));f.call('CHECK_PROTECT_NPC');f.go('SELECT_VALID_'+str(guard)+'_'+str(index));f.label('SELECT_ANY_'+str(guard)+'_'+str(index));f.eq(25,4,'SELECT_ANY2_'+str(guard)+'_'+str(index));f.call('CHECK_ARMED_HOSTILE');f.go('SELECT_VALID_'+str(guard)+'_'+str(index));f.label('SELECT_ANY2_'+str(guard)+'_'+str(index));f.call('NOT_FRIEND');f.label('SELECT_VALID_'+str(guard)+'_'+str(index));f.eq(30,1,nxt);f.call('TARGET_IN_RANGE');f.eq(30,1,nxt);f.ret();f.label(nxt)
  f.get(29,FIRE_TASK_TARGET);f.ret()

f.label('FIND_PROTECT_NPC');a(0x0085,V(24),V(29))
scan_foot(near_cells,2.0,12,'CHECK_ATTACKER_NPC','NEAR_ATTACK')
f.get(30,FIRE_SCAN_NEXT);a(0x01bd,V(31));f.check(0x001d,[V(31),V(30)],'PROTECT_KEEP_OLD');a(0x000a,V(31),I(600));a(0xddc,I(FIRE_SCAN_NEXT),V(31))
scan_foot(wide_cells,20.2,120,'CHECK_ATTACKER_NPC','WIDE_ATTACK')
scan_vehicles(wide_cells,20.2,'CAR_ATTACKER','WIDE_ATTACK')
a(0x0085,V(29),V(24));alive(f,29,'PROTECT_FIND_NEW');f.call('CHECK_PROTECT_NPC');f.eq(30,1,'PROTECT_FIND_NEW');f.call('TARGET_IN_RANGE');f.eq(30,1,'PROTECT_FIND_NEW');f.ret()
f.label('PROTECT_FIND_NEW')
scan_foot(wide_cells,20.2,120,'CHECK_PROTECT_NPC','WIDE_PROTECT')
scan_vehicles(wide_cells,20.2,'CAR_PROTECT','WIDE_PROTECT')
f.go('PROTECT_NO_TARGET')
f.label('PROTECT_KEEP_OLD');a(0x0085,V(29),V(24));alive(f,29,'PROTECT_NO_TARGET');f.call('CHECK_PROTECT_NPC');f.eq(30,1,'PROTECT_NO_TARGET');f.call('TARGET_IN_RANGE');f.eq(30,1,'PROTECT_NO_TARGET');f.ret()
f.label('PROTECT_NO_TARGET');a(6,V(29),I(-1));f.ret()

f.label('FIND_ARMED_HOSTILE');alive(f,29,'ARMED_SCAN');f.call('CHECK_ARMED_HOSTILE');f.eq(30,1,'ARMED_SCAN');f.call('TARGET_IN_RANGE');f.eq(30,1,'ARMED_SCAN');f.ret()
f.label('ARMED_SCAN')
scan_foot(wide_cells,20.2,120,'CHECK_ARMED_HOSTILE','OVW')
scan_vehicles(wide_cells,20.2,'CAR_ARMED','OVW')
a(6,V(29),I(-1));f.ret()
f.label('CHECK_ARMED_HOSTILE');f.call('NOT_FRIEND');f.eq(30,1,'ARMED_REJECT')
for grove_model in [105,106,107]:f.check(0x82f2,[V(29),I(grove_model)],'ARMED_REJECT')
a(0x089f,V(29),V(30));f.check(0x8039,[V(30),I(8)],'ARMED_REJECT');f.eq(30,6,'ARMED_WEAPON');f.check(0x010f,[I(0),I(0)],'ARMED_REJECT')
f.label('ARMED_WEAPON');a(0x0470,V(29),V(30));f.check(0x0019,[V(30),I(15)],'ARMED_REJECT');f.check(0x0019,[V(30),I(39)],'ARMED_ACCEPT');f.go('ARMED_REJECT')
f.label('ARMED_ACCEPT');a(6,V(30),I(1));f.ret()
f.label('ARMED_REJECT');a(6,V(30),I(0));f.ret()
# v39-fire callouts: TARGET DOWN with a kill counter, AREA CLEAR 3 s after the last target.
f.label('KILL_CHECK');f.get(30,LAST_TGT);f.eq(30,-1,'KILL_HAVE');f.ret()
f.label('KILL_HAVE');f.check(0x056d,[V(30)],'KILL_GONE');f.check(0x0118,[V(30)],'KILL_RET');f.get(31,KILLS);a(0x000a,V(31),I(1));a(0xddc,I(KILLS),V(31))
f.get(30,HUD);f.eq(30,1,'KILL_GONE');a(0x01e5,S('HCKILL'),V(31),I(2500),I(1))
f.label('KILL_GONE');f.set(LAST_TGT,-1)
f.label('KILL_RET');f.ret()
f.label('CLEAR_CHECK');f.get(30,ENGAGED);f.eq(30,1,'CLEAR_RET');f.get(30,CLEAR_AT);a(0x01bd,V(31));f.eq(30,0,'CLEAR_TIMED');a(0x000a,V(31),I(3000));a(0xddc,I(CLEAR_AT),V(31));f.ret()
f.label('CLEAR_TIMED');f.check(0x001d,[V(31),V(30)],'CLEAR_RET');f.set(ENGAGED,0);f.set(CLEAR_AT,0);msg(f,'HCCLEAR')
f.label('CLEAR_RET');f.ret()
f.label('FIND_ANY_NPC');alive(f,29,'ANY_SCAN');f.call('NOT_FRIEND');f.eq(30,1,'ANY_SCAN');f.call('TARGET_IN_RANGE');f.eq(30,1,'ANY_SCAN');f.ret()
f.label('ANY_SCAN')
scan_foot(wide_cells,20.2,120,'NOT_FRIEND','ANY')
scan_vehicles(wide_cells,20.2,'CAR_ANY','ANY')
a(6,V(29),I(-1));f.ret()
f.label('TARGET_IN_RANGE');a(0x00a0,V(0),V(8),V(9),V(10));a(0x00a0,V(29),V(11),V(12),V(13));a(0x050a,V(8),V(9),V(10),V(11),V(12),V(13),V(30));f.check(0x0023,[F(160),V(30)],'TARGET_TOO_FAR');a(6,V(30),I(1));f.ret()
f.label('TARGET_TOO_FAR');a(6,V(30),I(0));f.ret()

# Inspect the driver and occupied passenger seats of a no-save traffic vehicle.
for label,check in [('CAR_ARMED','CHECK_ARMED_HOSTILE'),('CAR_ATTACKER','CHECK_ATTACKER_NPC'),('CAR_PROTECT','CHECK_PROTECT_NPC'),('CAR_ANY','NOT_FRIEND'),('CAR_AIM','CHECK_CJ_AIMED')]:
 f.label(label);f.check(0x056e,[V(23)],label+'_NONE');f.check(0x803b,[V(23),V(1)],label+'_NONE');a(0x01ea,V(23),V(22))
 for seat in [-1]:
  nxt=label+'_SEAT_'+str(seat).replace('-','M')
  if seat<0:a(0x046c,V(23),V(29))
  else:f.check(0x0019,[V(22),I(seat)],nxt);f.check(0x8431,[V(23),I(seat)],nxt);a(0x0432,V(23),I(seat),V(29))
  alive(f,29,nxt);f.call(check);f.eq(30,1,nxt);f.ret();f.label(nxt)
 f.label(label+'_NONE');a(6,V(30),I(0));f.ret()

f.label('CHECK_PROTECT_NPC');f.call('NOT_FRIEND');f.eq(30,1,'PROTECT_REJECT')
for grove_model in [105,106,107]:f.check(0x82f2,[V(29),I(grove_model)],'PROTECT_REJECT')
a(0x089f,V(29),V(30));f.check(0x8039,[V(30),I(8)],'PROTECT_REJECT');f.check(0x0019,[V(30),I(6)],'PROTECT_POLICE_CHECK');f.check(0x8019,[V(30),I(16)],'PROTECT_POLICE_CHECK');f.go('PROTECT_ACCEPT')
f.label('PROTECT_POLICE_CHECK');f.check(0x010f,[I(0),I(0)],'PROTECT_DAMAGE_CHECK');a(0x089f,V(29),V(30));f.eq(30,6,'PROTECT_ARMED_SERVICES');f.go('PROTECT_ACCEPT')
f.label('PROTECT_ARMED_SERVICES')
for model in [285,286,287]:
 nxt='PROTECT_MODEL_NEXT_'+str(model);f.check(0x02f2,[V(29),I(model)],nxt);f.go('PROTECT_ACCEPT');f.label(nxt)
f.label('PROTECT_DAMAGE_CHECK');f.call('CHECK_ATTACKER_NPC');f.ret()
f.label('CHECK_ATTACKER_NPC');f.call('NOT_FRIEND');f.eq(30,1,'PROTECT_REJECT')
for grove_model in [105,106,107]:f.check(0x82f2,[V(29),I(grove_model)],'PROTECT_REJECT')
a(0x089f,V(29),V(30));f.check(0x8039,[V(30),I(8)],'PROTECT_REJECT')
for var in [0,2,3,4,5,6]:
 skip='PROTECT_DAMAGE_NEXT_'+str(var);alive(f,var,skip);f.check(0x051a,[V(var),V(29)],skip);f.go('PROTECT_ACCEPT');f.label(skip)
f.check(0x051c,[V(1),V(29)],'PROTECT_INCOMING');f.go('PROTECT_ACCEPT')
f.label('PROTECT_INCOMING');f.check(0x02e0,[V(29)],'PROTECT_REJECT');a(0x00a0,V(0),V(8),V(9),V(10));a(0x00a0,V(29),V(11),V(12),V(13));a(0x0087,V(14),V(8));a(0x0063,V(14),V(11));a(0x0087,V(15),V(9));a(0x0063,V(15),V(12));a(0x0604,V(14),V(15),V(16));a(0x0172,V(29),V(17));a(0x0063,V(16),V(17));f.check(0x0023,[F(0),V(16)],'PROTECT_ANGLE_POSITIVE');a(0x000b,V(16),F(360))
f.label('PROTECT_ANGLE_POSITIVE');f.check(0x0023,[F(20),V(16)],'PROTECT_ANGLE_WRAP');f.go('PROTECT_INCOMING_LOS')
f.label('PROTECT_ANGLE_WRAP');f.check(0x0021,[V(16),F(340)],'PROTECT_REJECT')
f.label('PROTECT_INCOMING_LOS');a(0x000b,V(10),F(.7));a(0x000b,V(13),F(.7));f.check(0x06bd,[V(11),V(12),V(13),V(8),V(9),V(10),I(1),I(1),I(0),I(1),I(0)],'PROTECT_REJECT')
f.label('PROTECT_ACCEPT');a(6,V(30),I(1));f.ret()
f.label('PROTECT_REJECT');a(6,V(30),I(0));f.ret()

f.label('CHECK_CJ_AIMED');f.call('NOT_FRIEND');f.eq(30,1,'CJ_AIM_NO');f.check(0x0457,[I(0),V(29)],'CJ_AIM_NO');a(6,V(30),I(1));f.ret()
f.label('CJ_AIM_NO');a(6,V(30),I(0));f.ret()
f.label('FIND_CJ_AIMED');alive(f,29,'CJ_AIM_SCAN');f.call('CHECK_CJ_AIMED');f.eq(30,1,'CJ_AIM_SCAN');f.ret()
f.label('CJ_AIM_SCAN')
scan_foot(near_cells,2.0,12,'CHECK_CJ_AIMED','CJ_AIM_NEAR')
scan_foot(wide_cells,20.2,120,'CHECK_CJ_AIMED','CJ_AIM_WIDE')
scan_vehicles(wide_cells,20.2,'CAR_AIM','CJ_AIM_CAR')
a(6,V(29),I(-1));f.ret()

def main():
 reports=[c.build('Helicover_Core','csa'),p.build('Helicover_Panel','csa'),launch.build('Helicover','csi'),f.build('Helicover_Fire','csa')]
 (OUT/'Helicover.fxt').write_text('\n'.join(k+' '+v for k,v in MESSAGES.items())+'\n')
 (OUT/'validation.txt').write_text('\n'.join(reports)+'\nAndroid runtime: NOT TESTED.\n')
 print('\n'.join(reports))
if __name__=='__main__':main()
