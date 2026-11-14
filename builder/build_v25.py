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
# v39b robust exit: rope drop retries with repositioning, and a rope fallback when there is
# nowhere to land. DROP_RESULT -1 running / 0 done / 1 failed (set by the ground worker).
ROPE_PENDING=STATE+143;DROP_RESULT=STATE+144;ROPE_TRIES=STATE+145;RETRY_AT=STATE+146;FORCE_ROPE=STATE+147
# v39.2: the hover point is CJ + 9 m along the helicopter's heading, so the tail rope (0,-3)
# hangs 6 m in front of CJ - he is lifted only after walking to it, not while standing still.
ROPE_PICKUP_AHEAD=9.0
# v39.3: the exit widget's release lasts a frame or two, but the core ticks every 100 ms, so it
# missed most presses. The fire worker (WAIT 0, every frame) stamps EXIT_PRESSED with the time;
# the core accepts a stamp younger than 600 ms and debounces commands for 1.5 s (EXIT_LAST).
EXIT_PRESSED=STATE+148;EXIT_LAST=STATE+149
# v39.4 air threat: script searches cannot return helicopters (053E/073E accept only cars and
# bikes) nor peds inside vehicles (0A3E/02DD skip them), and police choppers fire by themselves
# (CHeli::ProcessControl -> FireOneInstantHitRound -> CBulletTraces::AddTrace). So in PROTECT CJ
# at 3+ stars the fire worker reads CBulletTraces::aTraces (16 x 44 bytes, image-relative) with
# 0DD8 and returns fire at the start point of a fresh round that came down at CJ from >=10 m above.
BULLET_TRACES_OFS=0xCFA500;BULLET_TRACE_SIZE=44;BULLET_TRACE_COUNT=16
AIR_X=STATE+150;AIR_Y=STATE+151;AIR_Z=STATE+152;AIR_SEEN=STATE+153;AIR_CALL_NEXT=STATE+154
# v40 tactical squad AI (Helicover_Squad.csa). SQ_HEART = squad worker heartbeat; TACTICS 0 bodyguard /
# 1 assault; SQ_ROPE 1 while the ground worker's rope/escort guards are on the ground under squad control;
# ESCORT_ON 1 while the escort team is deployed; ESCORT_CMD core->ground 1 deploy / 2 recall;
# ESCORT_PENDING tells ROPE_ARRIVE why the core hovered (0 rope pickup, 1 deploy, 2 recall).
SQ_HEART=STATE+155;TACTICS=STATE+156;SQ_ROPE=STATE+157;ESCORT_ON=STATE+158;ESCORT_CMD=STATE+159;ESCORT_PENDING=STATE+160
SQ_THREATS=STATE+161;SQ_T=STATE+162  # SQ_T..SQ_T+3 = current threats (char handles or -1)
SQ_MSG_NEXT=STATE+166;SQ_MEDIC_NEXT=STATE+167;SQ_CONTACT=STATE+168;SQ_CLEAR_AT=STATE+169;SQ_SCAN_NEXT=STATE+170;SQ_GROUP=STATE+171
SQ_SLOT=STATE+172;SQ_SLOT_SIZE=10   # per guard slot: TASK NEXT TX TY LX LY LT DEAD TGT spare
# v40 overwatch flight: station index/time, hull sampling and evasive manoeuvre deadline
# v40.3 gunner brain: each gunner's previous target, last announced heavy-weapon threat
GT_PREV=STATE+225;FOCUS_SEEN=STATE+229;GC_TIME=STATE+250;GC_CAND=STATE+230  # GC_CAND..+18: this round's checked candidates (shooter, primary, 4 squad threats, 13 cells), -1 = none
# v41 threat board (threat_v41.py): shooter found through bullet traces, fire at the helicopter,
# the gunners' sorted list, suppression memory, and the squad's cover / reload / call-out state.
from msg_v42 import say,MSG_UNTIL,MSG_PRIO,LEVEL_ALL
import msg_v42 as _mv;assert _mv.HUD==HUD
from threat_v41 import TB_SHOOTER,TB_SHOOTER_T,HELI_SHOT_T,TRACE_SCAN_T,SHOOTER_FRESH_MS,SCORE_FOCUS,emit_score,emit_trace_scan
import threat_v41 as _tv;assert _tv.STATE==STATE
PREV_HP=STATE+356;PREV_HP_T=STATE+360;GT_YIELD=STATE+364;LS_X=STATE+340;LS_Y=STATE+344;LS_Z=STATE+348;LS_T=STATE+352  # gunner hit tracking / guard last-seen
NOTICE_SKIP=STATE+335;HELLO_AT=STATE+336;KILL_NEXT=STATE+337
GS_H=STATE+256;GS_S=STATE+264            # 8 handles / scores, best first
SUP_X=STATE+272;SUP_Y=STATE+276;SUP_Z=STATE+280;SUP_T=STATE+284;GT_SUPP=STATE+288  # per gunner
CV_X=STATE+292;CV_Y=STATE+296;CV_Z=STATE+300;CV_T=STATE+304;CV_H=STATE+308;CV_OK=STATE+312;ENG_T=STATE+316  # per guard
SQ_CV_TICK=STATE+320;SQ_QUIET_T=STATE+321;SQ_EVAC_NEXT=STATE+322;SQ_CALLED=STATE+323;SQ_SC=STATE+324  # SQ_SC..+3 squad scores
ST_I=STATE+215;ST_NEXT=STATE+216;HP_PREV=STATE+217;HP_T=STATE+218;EVADE_UNTIL=STATE+219
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
# 1.0 public release: the memory reads above (map marker, bullet traces) are only valid for this
# libGTASA build. The core checks two code words of CBulletTraces::AddTrace(CVector*,CVector*,int,
# CEntity*) at start-up; on any other build GAME_OK stays 0 and those features switch off cleanly.
GAME_OK=STATE+330;GAME_SIG=[(0x6E612C,-788364289),(0x6E6130,1828928495)]

GROVE_X=2492.0;GROVE_Y=-1666.0
STATES={25:'MAP CLIMB',24:'PATROLLING',21:'TO MAP POINT',22:'DEST APPROACH',23:'AWAITING EXIT',20:'CLIMB TO GROVE',19:'ROPE APPROACH',17:'CHANGING CREW',18:'LANDING BLOCKED',16:'CHANGING HELI',0:'READY',1:'LOADING',2:'FOLLOWING',3:'HOLDING',4:'DEPARTING',5:'LOAD FAILED',6:'GO OUTDOORS',7:'EVAC INBOUND',8:'TEAM COVERING',9:'CJ ON BOARD',10:'TO GROVE STREET',11:'GROVE LANDING',12:'LANDED',13:'DAMAGED / RTB',14:'TEAM BOARDING',15:'EMERGENCY LAND'}
MESSAGES={'HCLOAD': '~b~PILOT:~w~ inbound to your position.',
 'HCFOLL': '~b~PILOT:~w~ following CJ.',
 'HCHOLD': '~b~PILOT:~w~ holding position.',
 'HCDEPT': '~b~PILOT:~w~ heading home. Call us any time.',
 'HCFAIL': '~r~HELICOVER:~w~ could not load the helicopter. Try again.',
 'HCOUT': '~y~HELICOVER:~w~ go outside to call the helicopter.',
 'HCRWAIT': '~y~PILOT:~w~ no safe hover here. Move to open ground and retry.',
 'HCGCLMB': '~y~PILOT:~w~ cannot climb safely here. Retry from open ground.',
 'HCMAPOF': '~y~HELICOVER:~w~ map marker flight is not available.',
 'HCDBG': 'DBG ~1~',
 'HCNEED': '~y~HELICOVER:~w~ call the helicopter first.',
 'HCVER': '~y~HELICOVER:~w~ map marker is not supported on this game version.',
 'HCNOMAP': '~y~HELICOVER:~w~ put a marker on the map first.',
 'HCCHOS': '~b~PILOT:~w~ over the destination. Press exit to get out.',
 'HCAIR': '~r~POLICE CHOPPER!~w~ Gunners returning fire.',
 'HCCONT': '~r~CONTACT!~w~ Gunners engaging.',
 'HCKILL': '~g~TARGET DOWN~w~ ~1~',
 'HCCLEAR': '~g~GUNNERS:~w~ area clear.',
 'HCFM0': '~y~GUNNERS:~w~ cease fire.',
 'HCFM1': '~r~GUNNERS:~w~ weapons free - anyone but us is a target.',
 'HCFM2': '~b~GUNNERS:~w~ firing on your targets.',
 'HCFM3': '~g~GUNNERS:~w~ protecting CJ.',
 'HCFM4': '~p~GUNNERS:~w~ overwatch - armed hostiles only.',
 'HCXROPE': '~b~PILOT:~w~ no landing spot here - going down by rope.',
 'HCNOPAD': '~b~PILOT:~w~ no flat spot - hovering for a rope exit.',
 'HCXHERE': '~b~PILOT:~w~ finding a clear spot to let you out.',
 'HCXARR': '~b~PILOT:~w~ you will get out on arrival.',
 'HCXWAIT': '~y~PILOT:~w~ wait until we land or hover.',
 'HCDWAIT': '~y~PILOT:~w~ wait until we reach the destination.',
 'HCPAT': '~b~PILOT:~w~ patrolling around CJ.',
 'HCAVOID': '~y~PILOT:~w~ route blocked - holding for a clear path.',
 'HCROPE': '~b~PILOT:~w~ moving in - walk to the rope.',
 'HCRTEAM': '~b~PILOT:~w~ moving in to drop the team.',
 'HCRBACK': '~b~PILOT:~w~ moving in to pick up the team.',
 'HCEVAC': '~b~PILOT:~w~ landing nearby.',
 'HCTEAM': '~g~SQUAD:~w~ guarding the helicopter. Get in when ready.',
 'HCBOARD': '~b~PILOT:~w~ CJ aboard. Open the menu and pick a destination.',
 'HCGROVE': '~b~PILOT:~w~ heading to Grove Street.',
 'HCHOME': '~b~PILOT:~w~ approaching Grove Street.',
 'HCARRIV': '~b~PILOT:~w~ landed. Press exit to get out.',
 'HCDAMAG': '~r~MAYDAY!~w~ Critical damage - pulling out.',
 'HCMUST': '~b~PILOT:~w~ waiting for the crew to get back aboard.',
 'HCEMERG': '~r~MAYDAY!~w~ Critical damage - emergency landing.',
 'HCNOSEA': '~y~HELICOVER:~w~ the Hunter has no passenger seat.',
 'HCNOSIT': '~y~PILOT:~w~ cannot land here. Move to open, level ground.',
 'HCFAR': '~y~PILOT:~w~ come within 12 m of the helicopter.',
 'HCWAIT': '~y~PILOT:~w~ waiting for the crew. Clear their path.',
 'HCIN': '~y~HELICOVER:~w~ get in the helicopter first.',
 'HCOFF': '~r~HELICOVER:~w~ files missing. Copy all 7 files to CLEO and restart.',
 'HCSWAP': '~b~PILOT:~w~ helicopter changed.',
 'HCSNO': '~y~HELICOVER:~w~ the Hunter has no passenger seat - get out first.',
 'HCSFAIL': '~r~HELICOVER:~w~ change failed, kept the current helicopter.',
 'HCCREW': '~g~HELICOVER:~w~ crew changed.',
 'HCCFAIL': '~r~HELICOVER:~w~ crew change failed, kept the current crew.',
 'HCBLOCK': '~y~PILOT:~w~ cannot land here. Choose open ground or FOLLOW CJ.',
 'HCLOSE': '~y~PILOT:~w~ land first.',
 'HCEXIT': '~y~HELICOVER:~w~ get out of the helicopter first.',
 'SQALR': '~y~SQUAD:~w~ the team is already on the ground.',
 'SQNONE': '~y~SQUAD:~w~ no team on the ground.',
 'SQFOOT': '~y~SQUAD:~w~ CJ must be on foot to receive the team.',
 'SQCREW': '~y~SQUAD:~w~ wait until the crew is back aboard.',
 'HCFOCUS': '~r~SHOOTER ON CJ!~w~ Gunners focusing fire.',
 'HCEVADE': '~r~TAKING HITS!~w~ Pilot breaking away.',
 'HCSHOT': '~r~TAKING FIRE!~w~ Pilot breaking away.',
 'HCHELLO': '~b~HELICOVER 1.1~w~ ready. CLEO menu > Helicover.',
 'HCHELLV': '~b~HELICOVER 1.1~w~ ready. Map marker off on this game version.'}
# Generate state updates; panel prints messages when the state changes.
def state(s,n):s.set(STATE,n)
def msg(s,key):say(s,key)
def alive(s,var,fail):s.check(0x056d,[V(var)],fail);s.check(0x8118,[V(var)],fail)
def squad_owns(s,owned,t1,t2):
 # v40: jump to `owned` while the squad worker's heartbeat is fresh (it gives on-foot guards their orders)
 a=s.add;a(0x01bd,V(t1));s.get(t2,SQ_HEART);a(0x0062,V(t1),V(t2));s.check(0x0019,[V(t1),I(1000)],owned)
def healthcheck(s,fail):
 s.check(0x0256,[I(0)],fail);s.check(0x056e,[V(5)],fail);alive(s,4,fail);s.check(0x8119,[V(5)],fail)

c=Script();a=c.add
c.label('INIT');a(0);c.set(GAME_OK,0)
for _ofs,_val in GAME_SIG:a(0x0dd8,V(19),I(_ofs),I(4),I(1));c.check(0x0039,[V(19),I(_val)],'GAME_SIG_BAD')
c.set(GAME_OK,1);c.label('GAME_SIG_BAD');c.set(NOTICE_SKIP,-1);c.set(HELLO_AT,0);c.set(MSG_UNTIL,0);c.set(MSG_PRIO,0);c.set(AVOID_STAGE,0);c.set(AVOID_NEXT,0);c.set(BUSY,0);c.set(FROZEN,0);c.set(LSTAGE,0);c.set(CREWGEN,0);c.set(FIRE_TARGET,-1);c.set(FIRE_ACTIVE,0);c.set(TRACKED_TARGET,-1);c.set(STUCK_SINCE,0)
for key in range(PUB,PUB+7):c.set(key,-1)
for key in range(GROUND_PUB,GROUND_PUB+5):c.set(key,-1)
c.set(ROPE_COMMAND,0)
for key,val in [(STATE,0),(CMD,0),(OPEN,0),(MODEL,487),(CREW,2),(FIRE,3),(TOUCH,0),(HUD,2),(HP,0),(WEAPON_SETTING,0),(EXIT_MODE,0),(AUTO_EXIT,0),(LOCK_HOLD,0),(ROPE_PENDING,0),(DROP_RESULT,0),(ROPE_TRIES,0),(RETRY_AT,0),(FORCE_ROPE,0),(EXIT_PRESSED,0),(EXIT_LAST,0),(AIR_SEEN,0),(AIR_CALL_NEXT,0),(KILLS,0),(LAST_TGT,-1),(ENGAGED,0),(CLEAR_AT,0),(ORBIT_I,0),(ORBIT_NEXT,0),(TACTICS,0),(ESCORT_PENDING,0),(ST_I,0),(ST_NEXT,0),(HP_PREV,0),(HP_T,0),(EVADE_UNTIL,0),(HELI_SHOT_T,-100000)]:c.set(key,val)
c.label('IDLE');a(1,I(100));a(0x01bd,V(20));a(0xddc,I(HEART),V(20));c.get(19,HELLO_AT);c.eq(19,-1,'HELLO_CHECK');c.go('HELLO_DONE')
c.label('HELLO_CHECK');c.eq(19,0,'HELLO_DUE');a(0x0085,V(19),V(20));a(0x000a,V(19),I(5000));a(0xddc,I(HELLO_AT),V(19));c.go('HELLO_DONE')
c.label('HELLO_DUE');c.check(0x001d,[V(20),V(19)],'HELLO_DONE');c.check(0x0256,[I(0)],'HELLO_DONE');c.set(HELLO_AT,-1);c.get(19,GAME_OK);c.eq(19,1,'HELLO_OLD');msg(c,'HCHELLO');c.go('HELLO_DONE')
c.label('HELLO_OLD');msg(c,'HCHELLV')
c.label('HELLO_DONE');c.get(8,CMD);c.set(CMD,0)
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
a(0x01bd,V(20));a(0xddc,I(HEART),V(20));healthcheck(c,'CLEANUP');c.call('CHANGE_MODEL');c.call('CHANGE_CREW');c.call('PUBLISH');c.get(7,STATE);a(0x0227,V(5),V(6));a(0xddc,I(HP),V(6));c.call('EVADE_CHECK');c.call('TRACK_COMBAT');c.call('FLIGHT_AVOID');c.call('UNSTICK');c.call('EXIT_BUTTON');c.get(7,STATE)
c.get(19,FIRE);c.check(0x003b,[V(19),V(23)],'UPDATE_FIRE');c.go('HEALTH')
c.label('UPDATE_FIRE');c.call('APPLY_FIRE')
c.label('HEALTH');c.eq(7,15,'HEALTH_LANDED_CHECK');c.go('DISPATCH')
c.label('HEALTH_LANDED_CHECK');c.eq(7,12,'CHECK_HEALTH');c.go('DISPATCH')
c.label('CHECK_HEALTH');c.check(0x0019,[V(6),I(350)],'LOW_HEALTH');c.go('DISPATCH')
c.label('LOW_HEALTH');c.check(0x80db,[V(18),V(5)],'EMERGENCY');c.eq(24,0,'EMERGENCY');a(6,V(25),I(13));c.go('DEPART')
c.label('DISPATCH');c.get(8,CMD);c.set(CMD,0)
for command,label in [(15,'REQUEST_EXIT'),(2,'REQUEST_FOLLOW'),(3,'REQUEST_HOLD'),(4,'REQUEST_DEPART'),(5,'EVAC'),(6,'BOARD_CJ'),(7,'REQUEST_GROVE'),(8,'LEAVE_CJ'),(9,'REQUEST_TAKEOFF'),(10,'REQUEST_ROPE'),(11,'REQUEST_MAP'),(12,'REQUEST_DEST_LAND'),(13,'REQUEST_DEST_ROPE'),(14,'REQUEST_PATROL'),(16,'REQUEST_TEAM_DEPLOY'),(17,'REQUEST_TEAM_RECALL')]:
 nxt='CMD_NEXT_'+str(command);c.eq(8,command,nxt);c.go(label);c.label(nxt)
# Per-state continuous work.
for st,label in [(7,'LANDING_TICK'),(11,'LANDING_TICK'),(15,'LANDING_TICK'),(8,'GROUND_TICK'),(9,'GROUND_TICK'),(12,'GROUND_TICK'),(14,'MUSTER_TICK'),(10,'TRAVEL_TICK'),(19,'ROPE_APPROACH_TICK'),(20,'GROVE_CLIMB_TICK'),(21,'MAP_TRAVEL_TICK'),(22,'DEST_APPROACH_TICK'),(24,'PATROL_TICK'),(25,'MAP_CLIMB_TICK'),(2,'FOLLOW_TICK'),(23,'AWAIT_TICK')]:
 nxt='STATE_NEXT_'+str(st);c.eq(7,st,nxt);c.go(label);c.label(nxt)
c.go('TICK')
for name,pending,target in [('FOLLOW',2,'FOLLOW'),('HOLD',3,'HOLD'),('DEPART',4,'DEPART')]:
 c.label('REQUEST_'+name)
 if name=='DEPART':
  c.check(0x80db,[V(18),V(5)],'REQUEST_GROVE')
 a(6,V(25),I(pending));c.eq(24,0,'START_MUSTER');c.go(target)
c.label('FOLLOW');c.call('UNFREEZE');c.check(0x80db,[V(18),V(5)],'HOLD');c.set(TRACKED_TARGET,-1);c.call('RESTORE_FLIGHT');a(0x0918,V(5),I(1));a(0x0825,V(5));a(0x04df,V(5),I(0));a(0x0726,V(5),V(18),I(-1),F(15));state(c,2);c.go('TICK')
# v40 overwatch: far away (>60 m) the native follow catches up; when CJ drives fast the native chase
# follows the car; otherwise the helicopter holds a station 30 m from CJ and 24 m above the higher of
# CJ and the ground below it, slowly circling (30 deg every 3 s) and skipping stations from which a
# building blocks the view of CJ. Rapid hull damage widens the circle to 50 m / 45 m for 7 s.
c.label('FOLLOW_TICK');c.check(0x80db,[V(18),V(5)],'TICK');c.get(19,TRACKED_TARGET);c.eq(19,-1,'TICK');a(0x077e,V(17));c.eq(17,0,'TICK')
# a live threat within 65 m of CJ belongs to the combat orbit (TRACK_COMBAT re-acquires it next tick)
c.get(29,FIRE_TARGET);alive(c,29,'FOLLOW_NO_THREAT');a(0x00a0,V(18),V(9),V(10),V(11));a(0x00a0,V(29),V(17),V(19),V(31));a(0x050a,V(9),V(10),V(11),V(17),V(19),V(31),V(30));c.check(0x0023,[F(65),V(30)],'FOLLOW_NO_THREAT');c.go('TICK')
c.label('FOLLOW_NO_THREAT')
a(0x00a0,V(18),V(9),V(10),V(11));a(0x00aa,V(5),V(26),V(27),V(28));a(0x0509,V(9),V(10),V(26),V(27),V(31));c.check(0x0021,[V(31),F(60)],'FOLLOW_NEAR')
c.get(19,FOLLOW_NEXT);c.check(0x001d,[V(20),V(19)],'TICK');a(0x0085,V(19),V(20));a(0x000a,V(19),I(4000));a(0xddc,I(FOLLOW_NEXT),V(19));a(0x07bb,V(5),I(6));a(0x0726,V(5),V(18),I(-1),F(15));c.go('TICK')
c.label('FOLLOW_NEAR');c.check(0x00df,[V(18)],'FOLLOW_STATION');a(0x03c0,V(18),V(17));a(0x02e3,V(17),V(19));c.check(0x0021,[V(19),F(12)],'FOLLOW_STATION')
c.get(19,FOLLOW_NEXT);c.check(0x001d,[V(20),V(19)],'TICK');a(0x0085,V(19),V(20));a(0x000a,V(19),I(3000));a(0xddc,I(FOLLOW_NEXT),V(19));c.call('RESTORE_FLIGHT');a(0x0726,V(5),V(18),I(-1),F(20));c.go('TICK')
c.label('FOLLOW_STATION');c.get(19,FOLLOW_NEXT);c.check(0x001d,[V(20),V(19)],'TICK');a(0x0085,V(19),V(20));a(0x000a,V(19),I(1500));a(0xddc,I(FOLLOW_NEXT),V(19))
c.get(19,ST_NEXT);c.check(0x001d,[V(20),V(19)],'ST_KEEP');a(0x0085,V(19),V(20));a(0x000a,V(19),I(3000));a(0xddc,I(ST_NEXT),V(19));c.get(19,ST_I);a(0x000a,V(19),I(1));c.check(0x0019,[V(19),I(11)],'ST_STORE');a(6,V(19),I(0));c.label('ST_STORE');a(0xddc,I(ST_I),V(19))
c.label('ST_KEEP');a(6,V(29),I(0));c.get(19,EVADE_UNTIL);c.check(0x001d,[V(19),V(20)],'ST_MODE_SET');a(6,V(29),I(1));c.label('ST_MODE_SET');c.get(19,ST_I)
for t in range(6):
 if t:a(0x000a,V(19),I(2));wrap='ST_WRAP_%d'%t;c.check(0x0019,[V(19),I(11)],wrap);a(0x000a,V(19),I(-12));c.label(wrap)
 c.call('ST_POINT');c.eq(30,1,'ST_TRY_NEXT_%d'%t);c.go('ST_ISSUE');c.label('ST_TRY_NEXT_%d'%t)
a(0x000b,V(28),F(20))
c.label('ST_ISSUE');c.call('RESTORE_FLIGHT');a(0x04df,V(5),I(0));a(0x04a2,V(5),V(26),V(27),V(28),F(15),V(28));a(0x00ad,V(5),F(28));c.go('TICK')
# 26-28 = station for index 19@ (29@ = 1 evading); 30@ = 1 when CJ is in view from it
c.label('ST_POINT')
c.eq(19,0,'ST_OFS_0');c.eq(29,1,'ST_OFS_N_0');a(0x0007,V(26),F(0.0));a(0x0007,V(27),F(50.0));c.go('ST_OFS_DONE');c.label('ST_OFS_N_0');a(0x0007,V(26),F(0.0));a(0x0007,V(27),F(30.0));c.go('ST_OFS_DONE');c.label('ST_OFS_0')
c.eq(19,1,'ST_OFS_1');c.eq(29,1,'ST_OFS_N_1');a(0x0007,V(26),F(25.0));a(0x0007,V(27),F(43.3));c.go('ST_OFS_DONE');c.label('ST_OFS_N_1');a(0x0007,V(26),F(15.0));a(0x0007,V(27),F(25.98));c.go('ST_OFS_DONE');c.label('ST_OFS_1')
c.eq(19,2,'ST_OFS_2');c.eq(29,1,'ST_OFS_N_2');a(0x0007,V(26),F(43.3));a(0x0007,V(27),F(25.0));c.go('ST_OFS_DONE');c.label('ST_OFS_N_2');a(0x0007,V(26),F(25.98));a(0x0007,V(27),F(15.0));c.go('ST_OFS_DONE');c.label('ST_OFS_2')
c.eq(19,3,'ST_OFS_3');c.eq(29,1,'ST_OFS_N_3');a(0x0007,V(26),F(50.0));a(0x0007,V(27),F(0.0));c.go('ST_OFS_DONE');c.label('ST_OFS_N_3');a(0x0007,V(26),F(30.0));a(0x0007,V(27),F(0.0));c.go('ST_OFS_DONE');c.label('ST_OFS_3')
c.eq(19,4,'ST_OFS_4');c.eq(29,1,'ST_OFS_N_4');a(0x0007,V(26),F(43.3));a(0x0007,V(27),F(-25.0));c.go('ST_OFS_DONE');c.label('ST_OFS_N_4');a(0x0007,V(26),F(25.98));a(0x0007,V(27),F(-15.0));c.go('ST_OFS_DONE');c.label('ST_OFS_4')
c.eq(19,5,'ST_OFS_5');c.eq(29,1,'ST_OFS_N_5');a(0x0007,V(26),F(25.0));a(0x0007,V(27),F(-43.3));c.go('ST_OFS_DONE');c.label('ST_OFS_N_5');a(0x0007,V(26),F(15.0));a(0x0007,V(27),F(-25.98));c.go('ST_OFS_DONE');c.label('ST_OFS_5')
c.eq(19,6,'ST_OFS_6');c.eq(29,1,'ST_OFS_N_6');a(0x0007,V(26),F(0.0));a(0x0007,V(27),F(-50.0));c.go('ST_OFS_DONE');c.label('ST_OFS_N_6');a(0x0007,V(26),F(0.0));a(0x0007,V(27),F(-30.0));c.go('ST_OFS_DONE');c.label('ST_OFS_6')
c.eq(19,7,'ST_OFS_7');c.eq(29,1,'ST_OFS_N_7');a(0x0007,V(26),F(-25.0));a(0x0007,V(27),F(-43.3));c.go('ST_OFS_DONE');c.label('ST_OFS_N_7');a(0x0007,V(26),F(-15.0));a(0x0007,V(27),F(-25.98));c.go('ST_OFS_DONE');c.label('ST_OFS_7')
c.eq(19,8,'ST_OFS_8');c.eq(29,1,'ST_OFS_N_8');a(0x0007,V(26),F(-43.3));a(0x0007,V(27),F(-25.0));c.go('ST_OFS_DONE');c.label('ST_OFS_N_8');a(0x0007,V(26),F(-25.98));a(0x0007,V(27),F(-15.0));c.go('ST_OFS_DONE');c.label('ST_OFS_8')
c.eq(19,9,'ST_OFS_9');c.eq(29,1,'ST_OFS_N_9');a(0x0007,V(26),F(-50.0));a(0x0007,V(27),F(-0.0));c.go('ST_OFS_DONE');c.label('ST_OFS_N_9');a(0x0007,V(26),F(-30.0));a(0x0007,V(27),F(-0.0));c.go('ST_OFS_DONE');c.label('ST_OFS_9')
c.eq(19,10,'ST_OFS_10');c.eq(29,1,'ST_OFS_N_10');a(0x0007,V(26),F(-43.3));a(0x0007,V(27),F(25.0));c.go('ST_OFS_DONE');c.label('ST_OFS_N_10');a(0x0007,V(26),F(-25.98));a(0x0007,V(27),F(15.0));c.go('ST_OFS_DONE');c.label('ST_OFS_10')
c.eq(19,11,'ST_OFS_11');c.eq(29,1,'ST_OFS_N_11');a(0x0007,V(26),F(-25.0));a(0x0007,V(27),F(43.3));c.go('ST_OFS_DONE');c.label('ST_OFS_N_11');a(0x0007,V(26),F(-15.0));a(0x0007,V(27),F(25.98));c.go('ST_OFS_DONE');c.label('ST_OFS_11')
a(0x0007,V(26),F(0));a(0x0007,V(27),F(30))
c.label('ST_OFS_DONE');a(0x005b,V(26),V(9));a(0x005b,V(27),V(10));a(0x0087,V(28),V(11));a(0x000b,V(28),F(80));a(0x02ce,V(26),V(27),V(28),V(28));c.check(0x8025,[V(28),V(11)],'ST_GROUND_HIGH');a(0x0087,V(28),V(11));c.label('ST_GROUND_HIGH')
c.eq(29,1,'ST_ALT_NORMAL');a(0x000b,V(28),F(45));c.go('ST_ALT_DONE');c.label('ST_ALT_NORMAL');a(0x000b,V(28),F(24));c.label('ST_ALT_DONE')
a(6,V(30),I(0));a(0x0087,V(31),V(11));a(0x000b,V(31),F(1));c.check(0x06bd,[V(26),V(27),V(28),V(9),V(10),V(31),I(1),I(0),I(0),I(0),I(0)],'ST_POINT_RET');a(6,V(30),I(1))
c.label('ST_POINT_RET');c.ret()
# Hull sampled every 2 s; a loss of more than 120 within 2 s starts a 7 s evasive manoeuvre.
c.label('EVADE_CHECK');c.get(19,HELI_SHOT_T);a(0x0085,V(17),V(20));a(0x0062,V(17),V(19));c.check(0x8019,[V(17),I(600)],'EVADE_HULL')
c.eq(7,2,'EVADE_SHOT_PATROL');c.go('EVADE_SHOT_OK');c.label('EVADE_SHOT_PATROL');c.eq(7,24,'EVADE_HULL');c.label('EVADE_SHOT_OK')
c.get(19,EVADE_UNTIL);c.check(0x001d,[V(20),V(19)],'EVADE_HULL');a(0x0085,V(19),V(20));a(0x000a,V(19),I(6000));a(0xddc,I(EVADE_UNTIL),V(19));c.set(FOLLOW_NEXT,0);c.set(ORBIT_NEXT,0);msg(c,'HCSHOT')
c.label('EVADE_HULL');c.get(19,HP_T);c.check(0x001d,[V(20),V(19)],'EVADE_RET');a(0x0085,V(19),V(20));a(0x000a,V(19),I(2000));a(0xddc,I(HP_T),V(19));c.get(17,HP_PREV);a(0xddc,I(HP_PREV),V(6));c.eq(17,0,'EVADE_DROP');c.ret()
c.label('EVADE_DROP');c.eq(7,2,'EVADE_PATROL');c.go('EVADE_STATE_OK');c.label('EVADE_PATROL');c.eq(7,24,'EVADE_RET');c.label('EVADE_STATE_OK')
a(0x0062,V(17),V(6));c.check(0x0019,[V(17),I(120)],'EVADE_RET');a(0x0085,V(19),V(20));a(0x000a,V(19),I(7000));a(0xddc,I(EVADE_UNTIL),V(19));c.set(FOLLOW_NEXT,0);c.set(ORBIT_NEXT,0);msg(c,'HCEVADE')
c.label('EVADE_RET');c.ret()

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
c.label('REQUEST_ROPE');c.set(ESCORT_PENDING,0);c.check(0x80db,[V(18),V(5)],'ROPE_CJ_ABOARD');c.eq(24,0,'ROPE_MUSTER');c.go('ROPE_PREP')
c.label('ROPE_MUSTER');a(6,V(25),I(11));c.go('START_MUSTER')
c.label('ROPE_CJ_ABOARD');msg(c,'HCEXIT');c.go('TICK')
c.label('ROPE_PREP');c.eq(0,425,'ROPE_SEATS');msg(c,'HCNOSEA');c.go('TICK')
c.label('ROPE_SEATS');a(0x01ea,V(5),V(19));c.check(0x0019,[V(19),I(0)],'NO_SEATS')
# v40: the escort team deploys / is recalled through the same clear-hover approach (no seat needed)
c.label('ROPE_HOVER')
# v27: hover point = CJ + 3 m along the helicopter's heading, so the tail rope (0,-3) hangs on CJ.
a(0x00aa,V(5),V(9),V(10),V(11));a(0x0407,V(5),F(0),F(ROPE_PICKUP_AHEAD),F(0),V(26),V(27),V(28));a(0x0063,V(26),V(9));a(0x0063,V(27),V(10))
a(0x00a0,V(18),V(9),V(10),V(28));a(0x005b,V(26),V(9));a(0x005b,V(27),V(10));a(0x000b,V(28),F(100));a(0x02ce,V(26),V(27),V(28),V(28));a(0x00a0,V(18),V(9),V(10),V(11));a(0x000b,V(11),F(26));a(0x02ce,V(9),V(10),V(11),V(31));a(0x0087,V(17),V(28));a(0x0063,V(17),V(31));c.check(0x0023,[F(5),V(17)],'BAD_SITE');c.check(0x0021,[V(17),F(-5)],'BAD_SITE');c.call('CHECK_SITE');c.eq(17,1,'BAD_SITE');c.call('UNFREEZE');c.call('RESTORE_FLIGHT');a(0x04df,V(5),I(0));a(0x0087,V(9),V(28));a(0x000b,V(9),F(15));a(0x0087,V(11),V(28));a(0x000b,V(11),F(15));a(0x0853,V(5),I(10));a(0x04a2,V(5),V(26),V(27),V(9),F(12),V(11));a(0x00ad,V(5),F(45));a(0x01bd,V(21));state(c,19);c.go('TICK')
# v27: the native autopilot circles around a 3-5 m target instead of stopping. Within
# 45 m (clear line of sight) freeze the helicopter and glide it by script at ~25 m/s
# straight to the hover point, then hand over to the rope worker while still frozen.
c.label('ROPE_APPROACH_TICK');a(0x00aa,V(5),V(9),V(10),V(11));c.get(19,FROZEN);c.eq(19,1,'ROPE_FAR');c.go('ROPE_GLIDE')
c.label('ROPE_FAR');a(0x0509,V(9),V(10),V(26),V(27),V(31));c.check(0x0023,[F(45),V(31)],'ROPE_APPROACH_TIMEOUT')
a(0x0087,V(19),V(28));a(0x000b,V(19),F(15));c.check(0x06bd,[V(9),V(10),V(11),V(26),V(27),V(19),I(1),I(0),I(0),I(1),I(0)],'ROPE_APPROACH_TIMEOUT')
# SET_CAR_COORDINATES adds the model's base offset to z; measure it once so the glide does not climb.
a(0x0574,V(5),I(1));c.set(FROZEN,1);a(0x00ab,V(5),V(9),V(10),V(11));a(0xddc,I(CR_CMDZ),V(11));a(0x00aa,V(5),V(17),V(19),V(31));a(0x0063,V(31),V(11));a(0xddc,I(GLIDE_C),V(31))
a(0x0407,V(5),F(0),F(ROPE_PICKUP_AHEAD),F(0),V(17),V(19),V(31));a(0x0063,V(17),V(9));a(0x0063,V(19),V(10));a(0x00a0,V(18),V(26),V(27),V(31));a(0x005b,V(26),V(17));a(0x005b,V(27),V(19))
c.label('ROPE_GLIDE');a(0x00aa,V(5),V(9),V(10),V(11))
a(0x0087,V(17),V(26));a(0x0063,V(17),V(9));a(0x0087,V(29),V(27));a(0x0063,V(29),V(10));a(0x0087,V(30),V(28));a(0x000b,V(30),F(15));a(0x0063,V(30),V(11))
a(0x050a,F(0),F(0),F(0),V(17),V(29),V(30),V(31));c.check(0x0021,[V(31),F(.8)],'ROPE_ARRIVE')
a(0x0007,V(19),F(.8));a(0x0073,V(19),V(31));a(0x006b,V(17),V(19));a(0x006b,V(29),V(19));a(0x006b,V(30),V(19))
a(0x005b,V(9),V(17));a(0x005b,V(10),V(29));c.get(11,CR_CMDZ);a(0x005b,V(11),V(30));a(0xddc,I(CR_CMDZ),V(11));a(0x00ab,V(5),V(9),V(10),V(11));c.go('TICK')
c.label('ROPE_ARRIVE');a(0x0087,V(19),V(28));a(0x000b,V(19),F(15));a(0x0063,V(19),V(11));c.get(11,CR_CMDZ);a(0x005b,V(11),V(19));a(0xddc,I(CR_CMDZ),V(11));a(0x00ab,V(5),V(26),V(27),V(11))
c.call('BLOCK_HOVER');a(0x0574,V(5),I(1));c.set(FROZEN,1);c.set(NOTICE_SKIP,3);state(c,3);c.get(19,ESCORT_PENDING);c.eq(19,0,'ARRIVE_ESCORT');c.set(ROPE_COMMAND,1);c.go('TICK')
c.label('ARRIVE_ESCORT');a(0xddc,I(ESCORT_CMD),V(19));c.set(ESCORT_PENDING,0);c.go('TICK')
# v40 TEAM ON FOOT: deploy the four-man escort by rope next to CJ, or recall it the same way.
c.label('REQUEST_TEAM_DEPLOY');c.get(19,ESCORT_ON);c.eq(19,0,'TEAM_BUSY');c.check(0x80db,[V(18),V(5)],'ROPE_CJ_ABOARD');c.check(0x80df,[V(18)],'TEAM_CJ_IN_CAR');c.eq(24,1,'TEAM_DEPLOY_CREW');msg(c,'SQCREW');c.go('TICK')
c.label('TEAM_DEPLOY_CREW');c.set(ESCORT_PENDING,1);c.eq(24,0,'TEAM_MUSTER');c.go('ROPE_HOVER')
c.label('TEAM_MUSTER');a(6,V(25),I(18));c.go('START_MUSTER')
c.label('TEAM_BUSY');msg(c,'SQALR');c.go('TICK')
c.label('TEAM_CJ_IN_CAR');msg(c,'SQFOOT');c.go('TICK')
c.label('REQUEST_TEAM_RECALL');c.get(19,ESCORT_ON);c.eq(19,1,'TEAM_NONE');c.check(0x80db,[V(18),V(5)],'TEAM_EXTRACT');c.set(ESCORT_PENDING,2);c.go('ROPE_HOVER')
c.label('TEAM_EXTRACT');c.set(ESCORT_CMD,3);c.go('TICK')
c.label('TEAM_NONE');msg(c,'SQNONE');c.go('TICK')
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
c.label('GROUND_WORK');c.eq(24,1,'TICK');c.get(19,SQ_HEART);a(0x0085,V(17),V(20));a(0x0062,V(17),V(19));c.check(0x0019,[V(17),I(1000)],'TICK');c.get(19,FIRE_ACTIVE);c.eq(19,0,'TICK');a(0x0085,V(17),V(20));a(0x0062,V(17),V(22));c.check(0x0019,[V(17),I(800)],'TICK');a(0x0085,V(22),V(20));c.call('GUARD_TEAM');c.go('TICK')
c.label('BOARD_CJ');c.eq(24,3,'BOARD_GROUND_CHECK');c.go('BOARD_DISTANCE_CHECK')
c.label('BOARD_GROUND_CHECK');c.eq(24,1,'NOT_LANDED')
c.label('BOARD_DISTANCE_CHECK');c.check(0x0205,[V(18),V(5),F(12),F(12),F(5),I(0)],'TOO_FAR');a(0x05ca,V(18),V(5),I(12000),I(0));c.go('TICK')
c.label('TOO_FAR');msg(c,'HCFAR');c.go('TICK')
c.label('NOT_LANDED');msg(c,'HCLOSE');c.go('TICK')
c.label('LEAVE_CJ');c.eq(7,12,'LEAVE_CHECK_PHASE');c.go('LEAVE_ALLOWED')
c.label('LEAVE_CHECK_PHASE');c.eq(24,3,'LEAVE_GROUND_CHECK');c.eq(7,9,'NOT_LANDED');c.go('LEAVE_ALLOWED')
c.label('LEAVE_GROUND_CHECK');c.eq(24,1,'NOT_LANDED')
c.label('LEAVE_ALLOWED');c.check(0x00db,[V(18),V(5)],'TICK');a(0x020a,V(5),I(1));a(0x0085,V(19),V(20));a(0x000a,V(19),I(5000));a(0xddc,I(LOCK_HOLD),V(19));a(0x05cd,V(18),V(5));c.go('TICK')
c.label('REQUEST_MAP');c.set(AVOID_STAGE,0);c.set(AUTO_EXIT,0);c.check(0x0448,[V(18),V(5)],'NOT_ABOARD');c.get(19,GAME_OK);c.eq(19,1,'MAP_UNSUPPORTED')
if MAP_MARKER:c.call('READ_WAYPOINT');c.eq(29,1,'NO_MAP')
else:msg(c,'HCMAPOF');c.go('TICK')
a(0xddc,I(DEST_X),V(26));a(0xddc,I(DEST_Y),V(27));a(0xddc,I(DEST_Z),V(28));c.set(GROVE_WAIT,0);c.set(GROVE_NEXT_SCAN,0);c.call('UNFREEZE');a(0x01bd,V(21));state(c,21);c.go('TICK')
c.label('MAP_CLIMB_TICK');a(0x0819,V(4),V(19));c.check(0x0021,[V(19),F(40)],'MAP_CLIMB_TIMEOUT');c.get(26,DEST_X);c.get(27,DEST_Y);c.get(28,DEST_Z);c.call('RESTORE_FLIGHT');a(0x0087,V(9),V(28));a(0x000b,V(9),F(80));a(0x04a2,V(5),V(26),V(27),V(9),F(45),V(9));a(0x00ad,V(5),F(30));state(c,21);c.go('TICK')
c.label('MAP_CLIMB_TIMEOUT');a(0x0085,V(17),V(20));a(0x0062,V(17),V(21));c.check(0x0019,[V(17),I(30000)],'TICK');c.call('BLOCK_HOVER');state(c,18);msg(c,'HCGCLMB');c.go('TICK')
c.label('NO_MAP');msg(c,'HCNOMAP');c.go('TICK')
c.label('MAP_UNSUPPORTED');msg(c,'HCVER');c.go('TICK')
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
c.label('REQUEST_DEST_LAND');c.eq(7,23,'DEST_NOT_READY');c.get(26,DEST_X);c.get(27,DEST_Y);c.get(28,DEST_Z);c.call('CHECK_SITE');c.eq(17,1,'DEST_LAND_BAD');state(c,11);c.go('ISSUE_LANDING')
c.label('DEST_LAND_BAD');c.get(19,AUTO_EXIT);c.eq(19,2,'BAD_SITE');c.set(AUTO_EXIT,0);msg(c,'HCXROPE');c.go('REQUEST_DEST_ROPE')
c.label('REQUEST_DEST_ROPE');c.eq(7,23,'DEST_NOT_READY');c.check(0x0448,[V(18),V(5)],'NOT_ABOARD');c.set(DROP_COMMAND,1);c.set(ROPE_PENDING,1);c.set(DROP_RESULT,-1);c.set(ROPE_TRIES,0);c.set(RETRY_AT,0);c.go('TICK')
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
for action,label in [(2,'FOLLOW'),(3,'HOLD'),(4,'DEPART'),(13,'DEPART'),(7,'GROVE'),(5,'EVAC'),(9,'WAIT_ABOARD'),(10,'TAKEOFF'),(11,'ROPE_PREP'),(12,'PATROL_START'),(18,'ROPE_HOVER')]:
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
MAP_PADS=[(0,0)]+[(round(r*dx/((dx*dx+dy*dy)**.5),1),round(r*dy/((dx*dx+dy*dy)**.5),1)) for r in [8,16,24] for dx,dy in [(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1)]]+[(32,0),(0,32),(-32,0),(0,-32)]
for index,(dx,dy) in enumerate(MAP_PADS):
 nxt='MAP_PAD_NEXT_'+str(index);c.get(26,DEST_X);c.get(27,DEST_Y);a(0x000b,V(26),F(dx));a(0x000b,V(27),F(dy));a(0x02ce,V(26),V(27),F(1000),V(28));c.check(0x0021,[V(28),F(-50)],nxt);c.check(0x0023,[F(800),V(28)],nxt);c.call('CHECK_SITE');c.eq(17,1,nxt);a(0xddc,I(DEST_X),V(26));a(0xddc,I(DEST_Y),V(27));a(0xddc,I(DEST_Z),V(28));c.go('DEST_HOVER_GO');c.label(nxt)
c.get(17,GROVE_WAIT);a(0x0085,V(31),V(20));a(0x0062,V(31),V(17));c.check(0x0019,[V(31),I(12000)],'TICK');c.go('MAP_NO_PAD')
c.label('MAP_NO_PAD');c.get(19,AUTO_EXIT);c.eq(19,1,'MAP_NO_PAD_PLAIN');c.get(19,EXIT_MODE);c.eq(19,0,'DEST_HOVER_GO');c.set(FORCE_ROPE,1);msg(c,'HCXROPE');c.go('DEST_HOVER_GO')
c.label('MAP_NO_PAD_PLAIN');msg(c,'HCNOPAD')
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
c.label('TRACK_DIST');a(0x00a0,V(29),V(17),V(19),V(31));a(0x00a0,V(18),V(26),V(27),V(28));a(0x0509,V(17),V(19),V(26),V(27),V(8));c.check(0x0021,[V(8),F(20)],'TRACK_CENTER_TARGET')
a(0x0063,V(26),V(17));a(0x0013,V(26),F(.3));a(0x005b,V(26),V(17));a(0x0063,V(27),V(19));a(0x0013,V(27),F(.3));a(0x005b,V(27),V(19));c.go('TRACK_CENTER_DONE')
c.label('TRACK_CENTER_TARGET');a(0x0087,V(26),V(17));a(0x0087,V(27),V(19))
c.label('TRACK_CENTER_DONE')
c.get(30,ORBIT_NEXT);c.check(0x001d,[V(20),V(30)],'ORBIT_KEEP');a(0x0085,V(30),V(20));a(0x000a,V(30),I(2500));a(0xddc,I(ORBIT_NEXT),V(30))
a(6,V(8),I(0))
for i,sgn in [(3,1),(5,1),(4,-1),(6,-1)]:
 skip='ORBIT_DOOR_%d'%i;c.get(30,PUB+i);alive(c,30,skip);a(0x000a,V(8),I(sgn));c.label(skip)
c.get(30,ORBIT_I);a(0x000a,V(30),I(1));c.check(0x0019,[V(8),I(0)],'ORBIT_DIR_SET');a(0x000a,V(30),I(-2));c.label('ORBIT_DIR_SET')
c.check(0x0019,[V(30),I(7)],'ORBIT_WRAP_LO');a(6,V(30),I(0));c.label('ORBIT_WRAP_LO');c.check(0x0019,[V(30),I(-1)],'ORBIT_WRAP_HI');c.go('ORBIT_STORE');c.label('ORBIT_WRAP_HI');a(6,V(30),I(7))
c.label('ORBIT_STORE');a(0xddc,I(ORBIT_I),V(30))
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
c.label('TRACK_GOTO');c.get(30,EVADE_UNTIL);c.check(0x001d,[V(30),V(20)],'TRACK_NORMAL');a(0x0013,V(9),F(1.6));a(0x0013,V(10),F(1.6));a(0x0087,V(11),V(31));a(0x000b,V(11),F(40));c.go('TRACK_POS')
c.label('TRACK_NORMAL');a(0x0087,V(11),V(31));a(0x000b,V(11),F(25));a(0x0087,V(8),V(31));a(0x0063,V(8),V(28));c.check(0x0021,[V(8),F(6)],'TRACK_POS');a(0x000b,V(11),F(15))
c.label('TRACK_POS');a(0x005b,V(9),V(26));a(0x005b,V(10),V(27))
# v40: an orbit point without a clear view of the threat is flown 15 m higher, and the next tick
# moves on to the following point (ORBIT_NEXT <= now + 1.2 s) until the gunners can see it.
a(0x0087,V(30),V(31));a(0x000b,V(30),F(1));c.check(0x06bd,[V(9),V(10),V(11),V(17),V(19),V(30),I(1),I(0),I(0),I(0),I(0)],'TRACK_BLOCKED');c.go('TRACK_ISSUE')
# v40.1: move on to the next point after 1.2 s at the earliest (v40 re-picked every 100 ms and the
# helicopter thrashed between points); only buildings count, not trees and other objects.
c.label('TRACK_BLOCKED');a(0x000b,V(11),F(15));c.get(30,ORBIT_NEXT);a(0x0085,V(8),V(20));a(0x000a,V(8),I(1200));c.check(0x001d,[V(30),V(8)],'TRACK_ISSUE');a(0xddc,I(ORBIT_NEXT),V(8))
c.label('TRACK_ISSUE');a(0x07bb,V(5),I(0));a(0x04a2,V(5),V(9),V(10),V(11),F(20),F(70));a(0xddc,I(TRACKED_TARGET),V(29));c.ret()
c.label('TRACK_STOP');c.get(19,TRACKED_TARGET);c.eq(19,-1,'TRACK_RESUME');c.ret()
c.label('TRACK_RESUME');c.set(TRACKED_TARGET,-1);c.call('RESTORE_FLIGHT');a(0x0726,V(5),V(18),I(-1),F(15));c.ret()
c.label('TRACK_INACTIVE');c.set(TRACKED_TARGET,-1)
c.label('TRACK_DONE');c.ret()

# Short detours during the two long-range cruise modes. Collision rays only guide the
# pilot; they cannot guarantee safe clearance from all moving or unstreamed objects.
# v39b: the scripted cruise owns obstacle handling for Grove/map flights; the old native detours
# could still fire on the first unfrozen tick and give up with HCAVOID, so they are disabled.
c.label('FLIGHT_AVOID');c.go('AVOID_NOT_CRUISE');c.label('AVOID_UNFROZEN');c.eq(7,10,'AVOID_CHECK_MAP');c.go('AVOID_ACTIVE_STATE');c.label('AVOID_CHECK_MAP');c.eq(7,21,'AVOID_NOT_CRUISE');c.label('AVOID_ACTIVE_STATE');c.get(19,AVOID_STAGE);c.eq(19,1,'AVOID_PROBE_TIMER');c.get(17,AVOID_AT);a(0x0085,V(19),V(20));a(0x0062,V(19),V(17));c.check(0x0019,[V(19),I(6000)],'AVOID_CHECK_REACHED');c.go('AVOID_RESUME')
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
a(0x020a,V(5),I(4))
c.get(19,EXIT_PRESSED);c.eq(19,0,'EXIT_STAMP');c.go('EXIT_DIRECT')
c.label('EXIT_STAMP');c.set(EXIT_PRESSED,0);a(0x0085,V(17),V(20));a(0x0062,V(17),V(19));c.check(0x0019,[V(17),I(600)],'EXIT_FIRE')
c.label('EXIT_DIRECT');c.check(0x0a52,[I(EXIT_WIDGET)],'EXIT_RET')
c.label('EXIT_FIRE');c.get(19,EXIT_LAST);a(0x0085,V(17),V(20));a(0x0062,V(17),V(19));c.check(0x0019,[V(17),I(1500)],'EXIT_RET');a(0xddc,I(EXIT_LAST),V(20));c.set(CMD,15);c.ret()
c.label('EXIT_UNLOCK');a(0x020a,V(5),I(1));c.set(EXIT_PRESSED,0)
c.label('EXIT_RET');c.ret()
c.label('REQUEST_EXIT');c.check(0x0448,[V(18),V(5)],'NOT_ABOARD')
for st in [12,9]:
 nxt='EXIT_NOT_GROUND_'+str(st);c.eq(7,st,nxt);c.go('LEAVE_CJ');c.label(nxt)
c.eq(7,23,'EXIT_NOT_HOVER')
c.label('EXIT_BY_MODE');c.get(19,FORCE_ROPE);c.eq(19,1,'EXIT_BY_SETTING');c.set(FORCE_ROPE,0);c.go('REQUEST_DEST_ROPE')
c.label('EXIT_BY_SETTING');c.get(19,EXIT_MODE);c.eq(19,1,'EXIT_LAND_NOW');c.go('REQUEST_DEST_ROPE')
c.label('EXIT_LAND_NOW');c.set(AUTO_EXIT,2);c.go('REQUEST_DEST_LAND')
c.label('EXIT_NOT_HOVER')
for st in [1,4,7,11,13,15,16,17]:
 nxt='EXIT_NOT_BUSY_'+str(st);c.eq(7,st,nxt);msg(c,'HCXWAIT');c.go('TICK');c.label(nxt)
# v39.2 ROPE mode: freeze right where the helicopter is and drop immediately (retries with a
# small shift only if the shaft is blocked or the height is outside 4-60 m).
c.get(19,EXIT_MODE);c.eq(19,1,'EXIT_NOT_ROPE_NOW')
c.label('EXIT_ROPE_NOW');a(0x00aa,V(5),V(9),V(10),V(11));a(0x0574,V(5),I(1));c.set(FROZEN,1);a(0x04ba,V(5),F(0));a(0x02ce,V(9),V(10),V(11),V(28))
a(0xddc,I(DEST_X),V(9));a(0xddc,I(DEST_Y),V(10));a(0xddc,I(DEST_Z),V(28));c.set(AUTO_EXIT,0);c.set(DEST_NATIVE,0);state(c,23);a(6,V(7),I(23));c.go('REQUEST_DEST_ROPE')
c.label('EXIT_NOT_ROPE_NOW')
c.eq(7,22,'EXIT_HERE');c.set(AUTO_EXIT,1);msg(c,'HCXARR');c.go('TICK')
c.label('EXIT_HERE');a(0x00aa,V(5),V(9),V(10),V(11));a(0x02ce,V(9),V(10),F(1000),V(28));a(0xddc,I(DEST_X),V(9));a(0xddc,I(DEST_Y),V(10));a(0xddc,I(DEST_Z),V(28));c.set(GROVE_WAIT,0);c.set(GROVE_NEXT_SCAN,0);c.set(AVOID_STAGE,0);c.set(AUTO_EXIT,1);c.call('UNFREEZE');a(0x01bd,V(21));state(c,21);msg(c,'HCXHERE');c.go('TICK')
# v39b: while hovering over the destination, a failed rope drop (slope, height window, shaft)
# moves the helicopter 6-8 m to another spot, re-hovers 16 m above the ground there and retries
# after 3.5 s - up to 5 times - before reporting RPDFAIL.
c.label('AWAIT_TICK');c.get(19,ROPE_PENDING);c.eq(19,1,'TICK')
c.get(19,RETRY_AT);c.eq(19,0,'AWAIT_RETRY_WAIT')
c.get(19,DROP_RESULT);c.eq(19,1,'TICK')
c.get(19,ROPE_TRIES);a(0x000a,V(19),I(1));a(0xddc,I(ROPE_TRIES),V(19));c.check(0x0019,[V(19),I(5)],'AWAIT_REPOSITION')
c.set(ROPE_PENDING,0);msg(c,'RPDFAIL');c.go('TICK')
c.label('AWAIT_REPOSITION');c.call('UNFREEZE');c.get(26,DEST_X);c.get(27,DEST_Y)
for k,(ox,oy) in enumerate([(0,6),(6,0),(0,-6),(-6,0),(8,8)],1):
 nxt='AWAIT_OFFSET_'+str(k);c.eq(19,k,nxt);a(0x000b,V(26),F(ox));a(0x000b,V(27),F(oy));c.go('AWAIT_MOVE');c.label(nxt)
c.label('AWAIT_MOVE');a(0x02ce,V(26),V(27),F(1000),V(28));a(0x000b,V(28),F(16));a(0x07bb,V(5),I(0));a(0x0853,V(5),I(3));a(0x04df,V(5),I(0));a(0x04a2,V(5),V(26),V(27),V(28),F(10),V(28));a(0x00ad,V(5),F(8))
a(0x0085,V(19),V(20));a(0x000a,V(19),I(3500));a(0xddc,I(RETRY_AT),V(19));c.set(DROP_RESULT,-1);c.go('TICK')
c.label('AWAIT_RETRY_WAIT');c.get(19,RETRY_AT);c.check(0x001d,[V(20),V(19)],'TICK');c.set(RETRY_AT,0);c.set(DROP_COMMAND,1);c.go('TICK')
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
p.get(8,STATE);p.check(0x803b,[V(8),V(17)],'AFTER_NOTICE');a(0x0085,V(17),V(8))
# 1.1: a state the core entered on its own way (rope hover = 3, follow after the team landed = 2)
# is not announced as if the player had asked for it
p.get(19,NOTICE_SKIP);p.check(0x003b,[V(8),V(19)],'NOTICE_SAY');p.set(NOTICE_SKIP,-1);p.go('AFTER_NOTICE')
p.label('NOTICE_SAY');p.eq(8,19,'NOTICE_NOT_ROPE');p.get(19,ESCORT_PENDING)
for pend,key in [(1,'HCRTEAM'),(2,'HCRBACK')]:
 nxt='NOTICE_ROPE_'+str(pend);p.eq(19,pend,nxt);say(p,key);p.go('AFTER_NOTICE');p.label(nxt)
say(p,'HCROPE');p.go('AFTER_NOTICE')
p.label('NOTICE_NOT_ROPE')
notice={24:'HCPAT',1:'HCLOAD',2:'HCFOLL',3:'HCHOLD',4:'HCDEPT',5:'HCFAIL',6:'HCOUT',7:'HCEVAC',8:'HCTEAM',9:'HCBOARD',10:'HCGROVE',11:'HCHOME',12:'HCARRIV',13:'HCDAMAG',14:'HCMUST',15:'HCEMERG'}
for st,key in notice.items():
 nxt='NOTICE_NEXT_'+str(st);p.eq(8,st,nxt);say(p,key);p.go('AFTER_NOTICE');p.label(nxt)
p.label('AFTER_NOTICE');p.get(1,OPEN);p.eq(1,1,'WATCH');p.go('ACQUIRE')
p.label('ACQUIRE');p.get(0,0);p.eq(0,0,'WATCH');p.set(OPEN,0);p.set(0,1);a(6,V(10),I(0));p.get(13,HEART);a(1,I(250));p.get(14,HEART);p.check(0x803b,[V(13),V(14)],'CORE_MISSING');a(6,V(2),I(0));a(6,V(3),I(-999));p.go('REFRESH')
p.label('MENU_POLL');a(1,I(50));a(0x01bd,V(20));a(0xddc,I(PANELHEART),V(20));p.check(0x0256,[I(0)],'CLOSE');a(0x0df4,V(1),I(250));p.eq(1,-2,'PICK');p.go('CLOSE')
p.label('PICK');p.eq(1,-1,'HAS_PICK');p.go('CHECK_MENU_STATUS')
p.label('HAS_PICK');p.get(8,STATE)
# v42 (public 1.0) menu: the main page follows the situation - no helicopter, busy, CJ on foot or CJ
# aboard - so only the actions that make sense right now are shown. The CLEO menu has its own CLOSE.
# Pages (local 2): 0 main, 1 gunners, 2 settings, 3 crew, 4 helicopter, 5 gun type, 6 dismiss confirm.
# Local 3 = key of the drawn page (redrawn when it changes), 7 = situation of the drawn main page.
NONE_STATES=[0,5,6];BUSY_STATES=[1,4,13,16,17]
GROUND_STATES=[st for st in STATES if st not in NONE_STATES+BUSY_STATES]
MODE_ROW={2:'MODE: FOLLOW CJ',3:'MODE: HOLD POSITION',24:'MODE: PATROL AROUND CJ'}
FIRE_PAGE=[(3,'PROTECT CJ'),(4,'OVERWATCH (ARMED ONLY)'),(2,'FOLLOW MY SHOTS'),(1,'WEAPONS FREE'),(0,'CEASE FIRE')]
def main_rows(st,sit,extra):
 if sit==0:return ['CALL HELICOPTER','SETTINGS >']
 if sit==1:return ['PLEASE WAIT...','GUNNERS >','SETTINGS >']
 if sit==2:return [MODE_ROW.get(st,'FOLLOW CJ'),'GUNNERS >','ROPE PICKUP',('RECALL TEAM' if extra else 'DEPLOY TEAM ON FOOT'),'SETTINGS >','DISMISS HELICOPTER']
 return ['FLY TO MAP MARKER','FLY TO GROVE STREET','GET OUT HERE','EXIT BY: '+('ROPE' if extra else 'LANDING'),'GUNNERS >','SETTINGS >']
MAIN_VARIANTS=[(st,0,0) for st in NONE_STATES]+[(st,1,0) for st in BUSY_STATES]+[(st,sit,x) for st in GROUND_STATES for sit in (2,3) for x in (0,1)]
for page,label in [(0,'PICK_MAIN'),(1,'PICK_FIRE'),(2,'PICK_SETUP'),(3,'PICK_CREW'),(4,'PICK_MODEL'),(5,'PICK_WEAPON'),(6,'PICK_DISMISS')]:
 nxt='PAGE_PICK_NEXT_'+str(page);p.eq(2,page,nxt);p.go(label);p.label(nxt)
p.go('MENU_POLL')
def page(n):
 a(6,V(2),I(n));a(6,V(3),I(-999));p.go('REFRESH')
def pick(index,label):
 nxt='PICK_NOT_'+label+'_'+str(len(p.rows));p.eq(1,index,nxt);p.go(label);p.label(nxt)
p.label('FORCE_REFRESH');a(6,V(3),I(-999));p.go('REFRESH')
p.label('PICK_MAIN')
for sit,actions in [(0,['DO_CALL','OPEN_SETUP']),(1,['FORCE_REFRESH','OPEN_FIRE','OPEN_SETUP']),(2,['DO_MODE_CYCLE','OPEN_FIRE','DO_ROPE','DO_TEAM_TOGGLE','OPEN_SETUP','OPEN_DISMISS']),(3,['DO_MAP','DO_GROVE','DO_EXIT_NOW','TOGGLE_EXIT','OPEN_FIRE','OPEN_SETUP'])]:
 nxt='PICK_MAIN_SIT_'+str(sit);p.eq(7,sit,nxt)
 for index,label in enumerate(actions):pick(index,label)
 p.go('MENU_POLL');p.label(nxt)
p.go('MENU_POLL')
for label,n in [('OPEN_MAIN',0),('OPEN_FIRE',1),('OPEN_SETUP',2),('OPEN_CREW',3),('OPEN_MODEL',4),('OPEN_WEAPON',5),('OPEN_DISMISS',6)]:p.label(label);page(n)
# FOLLOW -> HOLD -> PATROL -> FOLLOW; from any other state (landed, rope hover...) FOLLOW CJ
p.label('DO_MODE_CYCLE');p.eq(8,2,'MODE_NOT_FOLLOW');p.go('DO_HOLD')
p.label('MODE_NOT_FOLLOW');p.eq(8,3,'MODE_NOT_HOLD');p.go('DO_PATROL')
p.label('MODE_NOT_HOLD');p.go('DO_FOLLOW')
p.label('DO_TEAM_TOGGLE');p.get(9,ESCORT_ON);p.eq(9,1,'DO_TEAM_DEPLOY');p.go('DO_TEAM_RECALL')
p.label('PICK_DISMISS');pick(0,'DO_DISMISS');p.go('OPEN_MAIN')
# settings: three sub-pages and three one-tap switches
p.label('PICK_SETUP')
for index,label in [(0,'OPEN_CREW'),(1,'OPEN_MODEL'),(2,'OPEN_WEAPON'),(3,'TOGGLE_TACTICS'),(4,'TOGGLE_EXIT'),(5,'TOGGLE_HUD'),(6,'OPEN_MAIN')]:pick(index,label)
p.go('MENU_POLL')
for label,key in [('TOGGLE_TACTICS',TACTICS),('TOGGLE_EXIT',EXIT_MODE)]:
 p.label(label);p.get(9,key);p.eq(9,0,label+'_OFF');p.set(key,1);p.go('FORCE_REFRESH');p.label(label+'_OFF');p.set(key,0);p.go('FORCE_REFRESH')
p.label('TOGGLE_HUD');p.get(9,HUD);a(0x000a,V(9),I(-1));p.check(0x0019,[V(9),I(-1)],'TOGGLE_HUD_WRAP');a(0xddc,I(HUD),V(9));p.go('FORCE_REFRESH')
p.label('TOGGLE_HUD_WRAP');p.set(HUD,2);p.go('FORCE_REFRESH')
for key,pag,choices,back in [(FIRE,1,[(i,v) for i,(v,_) in enumerate(FIRE_PAGE)],'OPEN_MAIN'),(CREW,3,[(0,0),(1,1),(2,2)],'OPEN_SETUP'),(MODEL,4,[(0,487),(1,497),(2,425)],'OPEN_SETUP'),(WEAPON_SETTING,5,[(0,0),(1,29),(2,30),(3,31),(4,34)],'OPEN_SETUP')]:
 label={1:'PICK_FIRE',3:'PICK_CREW',4:'PICK_MODEL',5:'PICK_WEAPON'}[pag];p.label(label)
 for idx,val in choices:
  nxt='OPTION_NEXT_'+str(pag)+'_'+str(idx);p.eq(1,idx,nxt);p.set(key,val);p.go('FORCE_REFRESH');p.label(nxt)
 p.go(back)
for label,cmd in [('DO_EXIT_NOW',15),('DO_CALL',1),('DO_FOLLOW',2),('DO_HOLD',3),('DO_DISMISS',4),('DO_GROVE',7),('DO_ROPE',10),('DO_MAP',11),('DO_PATROL',14),('DO_TEAM_DEPLOY',16),('DO_TEAM_RECALL',17)]:
 p.label(label)
 # No commands while spawning/departing/retreating: the page is redrawn instead.
 for st in [1,4,13]:
  nxt='ALLOW_'+label+'_'+str(st);p.eq(8,st,nxt);p.go('FORCE_REFRESH');p.label(nxt)
 p.set(CMD,cmd);a(1,I(200))
 if label=='DO_DISMISS':a(6,V(2),I(0))
 p.go('CHECK_MENU_STATUS')
# 6@ = key of the main page now (state*100 + situation*10 + team / exit method), 5@ = situation
p.label('MAIN_KEY');p.get(8,STATE);a(6,V(5),I(2));a(6,V(12),I(0))
for sit,group in [(0,NONE_STATES),(1,BUSY_STATES)]:
 for st in group:nxt='MK_%d_%d'%(sit,st);p.eq(8,st,nxt);a(6,V(5),I(sit));p.go('MK_DONE');p.label(nxt)
a(0x01f5,I(0),V(11));p.get(12,PUB+1);p.check(0x056e,[V(12)],'MK_GROUND');p.check(0x0448,[V(11),V(12)],'MK_GROUND');a(6,V(5),I(3));p.get(12,EXIT_MODE);p.go('MK_DONE')
p.label('MK_GROUND');p.get(12,ESCORT_ON)
p.label('MK_DONE');a(0x0085,V(6),V(8));a(0x0012,V(6),I(100));a(0x0085,V(11),V(5));a(0x0012,V(11),I(10));a(0x005a,V(6),V(11));a(0x005a,V(6),V(12));p.ret()
p.label('SETUP_KEY');p.get(6,TACTICS);a(0x0012,V(6),I(100));p.get(11,EXIT_MODE);a(0x0012,V(11),I(10));a(0x005a,V(6),V(11));p.get(11,HUD);a(0x005a,V(6),V(11));p.ret()
p.label('CHECK_MENU_STATUS');p.eq(2,0,'CMS_FIRE');p.call('MAIN_KEY');p.go('CMS_COMPARE')
p.label('CMS_FIRE');p.eq(2,1,'CMS_SETUP');p.get(6,FIRE);p.go('CMS_COMPARE')
p.label('CMS_SETUP');p.eq(2,2,'CMS_CREW');p.call('SETUP_KEY');p.go('CMS_COMPARE')
p.label('CMS_CREW');p.eq(2,3,'CMS_MODEL');p.get(6,CREW);p.go('CMS_COMPARE')
p.label('CMS_MODEL');p.eq(2,4,'CMS_WEAPON');p.get(6,MODEL);p.go('CMS_COMPARE')
p.label('CMS_WEAPON');p.eq(2,5,'MENU_POLL');p.get(6,WEAPON_SETTING)
p.label('CMS_COMPARE');p.check(0x803b,[V(6),V(3)],'MENU_POLL');p.go('REFRESH')
p.label('REFRESH');a(0x0df3)
for pageid in range(7):
 nxt='DRAW_NEXT_'+str(pageid);p.eq(2,pageid,nxt);p.go('DRAW_'+str(pageid));p.label(nxt)
p.go('CLOSE')
p.label('DRAW_0');p.call('MAIN_KEY');a(0x0085,V(3),V(6));a(0x0085,V(7),V(5))
for st,sit,x in MAIN_VARIANTS:
 nxt='DRAW_MAIN_NEXT_%d_%d_%d'%(st,sit,x);p.eq(6,st*100+sit*10+x,nxt);a(0xdd0,V(4),L('MAIN_%d_%d_%d'%(st,sit,x)));p.go('SHOW_'+str(len(main_rows(st,sit,x))));p.label(nxt)
a(6,V(7),I(0));a(0xdd0,V(4),L('MAIN_0_0_0'));p.go('SHOW_2')
p.label('DRAW_2');p.call('SETUP_KEY');a(0x0085,V(3),V(6))
for tac in (0,1):
 for ex in (0,1):
  for hud in (0,1,2):
   nxt='DRAW_SETUP_NEXT_%d%d%d'%(tac,ex,hud);p.eq(6,tac*100+ex*10+hud,nxt);a(0xdd0,V(4),L('SETUP_%d%d%d'%(tac,ex,hud)));p.go('SHOW_7');p.label(nxt)
a(0xdd0,V(4),L('SETUP_002'));p.go('SHOW_7')
PREF_PAGES=[(1,FIRE,[v for v,_ in FIRE_PAGE],'GUNNERS / FIRE MODE',[n for _,n in FIRE_PAGE]),(3,CREW,[0,1,2],'SETTINGS / CREW',['GROVE STREET','ARMY','SWAT']),(4,MODEL,[487,497,425],'SETTINGS / HELICOPTER',['MAVERICK','POLICE MAVERICK','HUNTER (NO PASSENGERS)']),(5,WEAPON_SETTING,[0,29,30,31,34],'SETTINGS / GUN TYPE',['AUTO (BY CREW)','MP5','AK-47','M4','SNIPER RIFLE'])]
for pageid,key,values,_,_ in PREF_PAGES:
 p.label('DRAW_'+str(pageid));p.get(8,key);a(0x0085,V(3),V(8))
 for val in values:
  nxt='DRAW_PREF_NEXT_'+str(pageid)+'_'+str(val);p.eq(8,val,nxt);a(0xdd0,V(4),L('PREF_'+str(pageid)+'_'+str(val)));p.go('SHOW_'+str(len(values)+1));p.label(nxt)
 a(0xdd0,V(4),L('PREF_'+str(pageid)+'_'+str(values[0])));p.go('SHOW_'+str(len(values)+1))
p.label('DRAW_6');a(6,V(3),I(-1));a(0xdd0,V(4),L('DISMISS_MENU'));p.go('SHOW_2')
for count in range(1,9):p.label('SHOW_'+str(count));a(0xdf2,V(4),I(count));p.go('MENU_POLL')
p.label('CORE_MISSING');a(0xdd0,V(4),L('OFFLINE_MENU'));a(0xdf2,V(4),I(1))
p.label('OFFLINE_POLL');a(1,I(50));a(0x01bd,V(20));a(0xddc,I(PANELHEART),V(20));p.check(0x0256,[I(0)],'CLOSE');a(0xdf4,V(1),I(250));p.eq(1,-1,'CLOSE');p.go('OFFLINE_POLL')
p.label('CLOSE');a(0xdf3);p.set(OPEN,0);p.set(0,0);a(6,V(10),I(0));p.go('WATCH')
# All menus fit on one page (<=8 rows); metadata is appended beyond terminating branches.
VERSION='1.1'
for st,sit,x in MAIN_VARIANTS:p.blob('MAIN_%d_%d_%d'%(st,sit,x),('HELICOVER '+VERSION) if st==0 else 'HELICOVER / '+STATES[st],main_rows(st,sit,x))
p.blob('OFFLINE_MENU','HELICOVER / OFFLINE',['COPY ALL FILES, RESTART GAME'])
p.blob('DISMISS_MENU','SEND THE HELICOPTER AWAY?',['YES, DISMISS IT','NO, KEEP IT'])
for tac in (0,1):
 for ex in (0,1):
  for hud in (0,1,2):p.blob('SETUP_%d%d%d'%(tac,ex,hud),'HELICOVER / SETTINGS',['CREW >','HELICOPTER >','GUN TYPE >','TEAM TACTICS: '+('ASSAULT' if tac else 'BODYGUARD'),'EXIT BY: '+('ROPE' if ex else 'LANDING'),'MESSAGES: '+['OFF','IMPORTANT','ALL'][hud],'< BACK'])
for pg,_,values,title,labels in PREF_PAGES:
 for val in values:
  rows=[text+(' [ON]' if values[i]==val else '') for i,text in enumerate(labels)]+['< BACK']
  p.blob('PREF_'+str(pg)+'_'+str(val),title,rows)

launch=Script();a=launch.add
launch.label('ENTRY');a(0);a(1,I(400));launch.get(1,PANELHEART);a(1,I(250));launch.get(2,PANELHEART);launch.check(0x803b,[V(1),V(2)],'MISSING');launch.set(OPEN,1);a(0x004e)
launch.label('MISSING');a(0x03e5,S('HCOFF'));a(0x004e)

# Dedicated fire worker: no global faction hatred and no automatic armed turrets.
f=Script();a=f.add
f.label('INIT');a(0);f.set(FOCUS_SEEN,-1);f.set(GC_TIME,-100000);f.set(TB_SHOOTER,-1);f.set(TB_SHOOTER_T,-100000);f.set(TRACE_SCAN_T,-100000)
for i in range(4):f.set(GT_PREV+i,-1);f.set(GT_SUPP+i,0);f.set(SUP_T+i,-100000)
f.set(FIRENEXT,0);f.set(FIREGEN,-1);f.set(FWANTED,-1);f.set(FIRE_ACTIVE,0);f.set(FIRE_TARGET,-1);f.set(FIRE_TASK_TARGET,-1);f.set(FIRE_TASK_PHASE,-1);f.set(FIRE_TASK_MODE,-1);f.set(FIRE_TASK_NEXT,0);f.set(FIRE_SCAN_NEXT,0);a(6,V(26),I(-1));a(6,V(27),I(0));a(6,V(29),I(-1))
f.label('WAIT');a(1,I(0));a(0x01bd,V(30));a(0xddc,I(FIREHEART),V(30));f.check(0x0a52,[I(EXIT_WIDGET)],'EXIT_POLL_DONE');a(0xddc,I(EXIT_PRESSED),V(30));f.label('EXIT_POLL_DONE');f.get(30,BUSY);f.eq(30,0,'WAIT');f.get(30,STATE)
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
f.label('MODE_READY');f.call('KILL_CHECK');f.call('TRACE_TICK');f.label('ARM_GUARDS');f.get(30,FIRENEXT);a(0x01bd,V(31));f.check(0x001d,[V(31),V(30)],'WAIT');f.eq(25,4,'ARM_FAST');a(0x000a,V(31),I(OVERWATCH_CADENCE));f.go('ARM_NEXT_SET');f.label('ARM_FAST');a(0x000a,V(31),I(150));f.label('ARM_NEXT_SET');a(0xddc,I(FIRENEXT),V(31))
for var in [3,4,5,6]:
 skip='ARM_SKIP_'+str(var);alive(f,var,skip);a(0x0470,V(var),V(30));f.check(0x803b,[V(30),V(7)],skip);a(0x01b2,V(var),V(7),I(30000));a(0x01b9,V(var),V(7));a(0x02e2,V(var),I(100));a(0x07dd,V(var),I(100));f.label(skip)
f.eq(25,0,'ACTIVE_MODE');f.go('WAIT')
f.label('ACTIVE_MODE');f.eq(25,3,'CHECK_ALL_MODE');f.call('REFRESH_PROTECT_POLICE');f.call('AIR_SCAN');f.eq(30,1,'PROTECT_GROUND');f.call('AIR_CALLOUT');f.call('SHOOT_COORD');f.go('WAIT')
f.label('PROTECT_GROUND');f.call('FIND_PROTECT_NPC');alive(f,29,'NO_TARGET');f.call('SHOOT_CHAR');f.go('WAIT')
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
f.label('SC_NEW_TARGET');a(0xddc,I(LAST_TGT),V(29));f.get(30,ENGAGED);f.eq(30,0,'SC_KNOWN');f.set(ENGAGED,1);f.get(30,SQ_GROUP);f.eq(30,0,'SOLO_HCCONT_SQ');msg(f,'HCCONT');f.go('SOLO_HCCONT');f.label('SOLO_HCCONT_SQ');squad_owns(f,'SOLO_HCCONT',30,31);msg(f,'HCCONT');f.label('SOLO_HCCONT')
f.label('SC_KNOWN');f.set(FIRE_ACTIVE,1);a(0xddc,I(FIRE_TARGET),V(29));f.get(30,FIRE_TASK_MODE);f.eq(30,1,'CHAR_ISSUE_TASKS');f.get(30,FIRE_TASK_TARGET);f.check(0x003b,[V(30),V(29)],'CHAR_ISSUE_TASKS');f.get(30,FIRE_TASK_PHASE);f.check(0x003b,[V(30),V(28)],'CHAR_ISSUE_TASKS');f.get(30,FIRE_TASK_NEXT);a(0x01bd,V(31));f.check(0x001d,[V(31),V(30)],'CHAR_PRECISE')
# v40.3: the candidate check runs in its own frame (at most every 1.5 s); the gunners are assigned
# on the next frame, so the two heavy parts never land on the same frame.
f.label('CHAR_ISSUE_TASKS');f.get(30,GC_TIME);a(0x01bd,V(31));a(0x0062,V(31),V(30));f.check(0x0019,[V(31),I(1500)],'CIT_GO');a(0x01bd,V(31));a(0xddc,I(GC_TIME),V(31));a(0xddc,I(GC_TIME+1),V(29));f.call('GUNNER_ROUND');f.get(29,GC_TIME+1);f.ret()
f.label('CIT_GO');f.set(FIRE_TASK_MODE,1);a(0xddc,I(FIRE_TASK_TARGET),V(29));a(0xddc,I(FIRE_TASK_PHASE),V(28));a(0x01bd,V(31));a(0x000a,V(31),I(1800));a(0xddc,I(FIRE_TASK_NEXT),V(31))
for i in range(4):f.get(31,GUARD_TARGET+i);a(0xddc,I(GT_PREV+i),V(31));f.set(GUARD_TARGET+i,-1)
for var in [3,4,5,6]:
 f.call('SELECT_GUARD_TARGET_'+str(var));a(0xddc,I(GUARD_TARGET+var-3),V(29))
 skip='SHOOT_CHAR_SKIP_'+str(var);alive(f,var,skip);f.check(0x00db,[V(var),V(1)],'SHOOT_CHAR_ONFOOT_'+str(var));f.check(0x8a32,[V(var)],'SHOOT_CHAR_ONFOOT_'+str(var));a(0x0713,V(var),V(29),I(-1),F(0),F(0),F(0),F(150),I(0),I(1 if var in [3,5] else 0),I(100));f.go(skip)
 f.label('SHOOT_CHAR_ONFOOT_'+str(var));squad_owns(f,skip,30,31);a(0x074d,V(var),V(29),I(2500));f.label(skip)
f.label('CHAR_PRECISE');f.get(29,FIRE_TASK_TARGET);alive(f,29,'CHAR_DONE');a(0x00a0,V(29),V(11),V(12),V(13));a(0x000b,V(13),F(.25));a(6,V(7),I(0));f.check(0x80df,[V(29)],'CHAR_TARGET_IN_CAR');f.go('CHAR_TARGET_READY')
f.label('CHAR_TARGET_IN_CAR');f.call('TARGET_CAR_SAFE');f.eq(30,1,'CHAR_DONE');a(6,V(7),I(1))
f.label('CHAR_TARGET_READY');f.call('PRECISE_BULLETS')
f.label('CHAR_DONE');f.ret()

f.label('SHOOT_COORD');f.set(FIRE_ACTIVE,1);f.set(FIRE_TARGET,-1);f.get(30,FIRE_TASK_MODE);f.eq(30,2,'COORD_ISSUE_TASKS');f.get(30,FIRE_TASK_NEXT);a(0x01bd,V(31));f.check(0x001d,[V(31),V(30)],'COORD_PRECISE')
f.label('COORD_ISSUE_TASKS');f.set(FIRE_TASK_MODE,2);f.set(FIRE_TASK_TARGET,-1);a(0x01bd,V(31));a(0x000a,V(31),I(400));a(0xddc,I(FIRE_TASK_NEXT),V(31))
for var in [3,4,5,6]:
 skip='SHOOT_COORD_SKIP_'+str(var);alive(f,var,skip);f.check(0x00db,[V(var),V(1)],'SHOOT_COORD_ONFOOT_'+str(var));f.check(0x8a32,[V(var)],'SHOOT_COORD_ONFOOT_'+str(var));a(0x0713,V(var),I(-1),I(-1),V(22),V(23),V(24),F(150),I(0),I(1 if var in [3,5] else 0),I(100));f.go(skip)
 f.label('SHOOT_COORD_ONFOOT_'+str(var));squad_owns(f,skip,30,31);a(0x0668,V(var),V(22),V(23),V(24),I(600));f.label(skip)
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
 f.get(30,FIRE_TASK_MODE);f.eq(30,1,'PRECISE_MODE_DONE_'+str(var));f.get(29,GUARD_TARGET+var-3);alive(f,29,skip);a(6,V(7),I(0));f.check(0x80df,[V(29)],'PRECISE_CAR_'+str(var));f.go('PRECISE_TARGET_DONE_'+str(var));f.label('PRECISE_CAR_'+str(var));f.call('TARGET_CAR_SAFE');f.eq(30,1,skip);a(6,V(7),I(1));f.label('PRECISE_TARGET_DONE_'+str(var));a(0x00a0,V(29),V(11),V(12),V(13));a(0x000b,V(13),F(.25));f.eq(7,1,'PRECISE_ENGINE_DONE_'+str(var))
 if var in (3,5):a(0x0407,V(22),F(0),F(1.8),F(.3),V(11),V(12),V(13))
 f.label('PRECISE_ENGINE_DONE_'+str(var));f.get(30,GT_SUPP+var-3);f.eq(30,1,'PRECISE_MODE_DONE_'+str(var));f.get(11,SUP_X+var-3);f.get(12,SUP_Y+var-3);f.get(13,SUP_Z+var-3);f.label('PRECISE_MODE_DONE_'+str(var))
 alive(f,var,skip);a(0x00a0,V(var),V(8),V(9),V(10));a(0x000b,V(10),F(.25));a(0x050a,V(8),V(9),V(10),V(11),V(12),V(13),V(17));f.check(0x0023,[F(150),V(17)],skip)
 a(0x0007,V(31),F(.8));f.check(0x00db,[V(var),V(1)],onfoot);a(0x0007,V(31),F(5.5));f.go(origin)
 f.label(onfoot);f.check(0x0a32,[V(var)],'PRECISE_FOOT_'+str(var));a(0x0007,V(31),F(5.5));f.go(origin)
 f.label('PRECISE_FOOT_'+str(var));squad_owns(f,skip,30,21);f.label(origin)
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

# v41 gunner brain on the threat board. Once per round (GUNNER_ROUND, at most every 1.5 s, in a frame of
# its own) every candidate - the shooter found through bullet traces, the primary target, the ground
# squad's four threats and 13 scan cells - is de-duplicated, checked against the fire mode and range,
# rated by THREAT_SCORE and kept in a list sorted by score (GS_H/GS_S, top 8). Each gunner then:
# (1) the top threat when it scores 120+ (firing at CJ, or hurt us and still shooting): up to two
# gunners on it, with a call-out; (2) his own previous target while it is still on the list and in
# view; (3) the best free target on HIS side (right door 3/5, left door 4/6) with a clear line from his
# seat; (4) the best free target anywhere; (5) suppressive fire on the last seen position of his
# previous target for up to 4 s after it went behind cover; (6) the shared primary.
SCAN_CELLS=[(0,0),(-12,0),(12,0),(0,-12),(0,12),(-24,0),(24,0),(0,-24),(0,24),(-40,-40),(40,-40),(-40,40),(40,40)]
GC_N=2+4+len(SCAN_CELLS)
GS_N=8
def gunner_mode_check(P):
 f.eq(25,3,P+'NOT_PROTECT');f.call('CHECK_PROTECT_NPC');f.go(P+'MODE_DONE')
 f.label(P+'NOT_PROTECT');f.eq(25,4,P+'NOT_OVERWATCH');f.call('CHECK_ARMED_HOSTILE');f.go(P+'MODE_DONE')
 f.label(P+'NOT_OVERWATCH');f.call('NOT_FRIEND')
 f.label(P+'MODE_DONE')
emit_score(f,'THREAT_SCORE',29,30,[0,2,3,4,5,6],dict(cx=8,cy=9,cz=10,tx=11,ty=12,tz=13,d=14,t1=15,t2=16,t3=17))
emit_trace_scan(f,'TRACE_SCAN',dict(cx=8,cy=9,cz=10,hx=11,hy=12,hz=13,x=14,y=15,z=16,d=17,n=18,now=19,bx=20,by=21),'NOT_FRIEND',cj=0,heli=1)
f.label('TRACE_TICK');f.get(30,GAME_OK);f.eq(30,1,'TRACE_TICK_RET');f.get(30,TRACE_SCAN_T);a(0x01bd,V(31));a(0x0062,V(31),V(30));f.check(0x0019,[V(31),I(249)],'TRACE_TICK_RET');f.call('TRACE_SCAN')
f.label('TRACE_TICK_RET');f.ret()
# 29@ handle, 30@ score: insert into the sorted list (higher first); uses 31@
f.label('GS_INSERT')
for gp in range(GS_N):
 f.get(31,GS_S+gp);f.check(0x001d,[V(30),V(31)],'GSI_NEXT_%d'%gp);f.go('GSI_AT_%d'%gp);f.label('GSI_NEXT_%d'%gp)
f.ret()
for gp in range(GS_N):
 f.label('GSI_AT_%d'%gp)
 for q in range(GS_N-1,gp,-1):f.get(31,GS_H+q-1);a(0xddc,I(GS_H+q),V(31));f.get(31,GS_S+q-1);a(0xddc,I(GS_S+q),V(31))
 a(0xddc,I(GS_H+gp),V(29));a(0xddc,I(GS_S+gp),V(30));f.ret()
f.label('GUNNER_ROUND')
for gp in range(GS_N):f.set(GS_H+gp,-1);f.set(GS_S+gp,-10000)
for e in range(GC_N):
 P='GCR_%d_'%e;bad=P+'BAD';nxt=P+'NEXT'
 if e==0:
  f.get(29,TB_SHOOTER);f.get(30,TB_SHOOTER_T);a(0x01bd,V(31));a(0x0062,V(31),V(30));f.check(0x8019,[V(31),I(SHOOTER_FRESH_MS)],bad)
 elif e==1:f.get(29,FIRE_TASK_TARGET)
 elif e<6:f.get(29,SQ_T+e-2)
 else:
  x,y=SCAN_CELLS[e-6];a(0x00a0,V(0),V(8),V(9),V(10));a(0x000b,V(8),F(x));a(0x000b,V(9),F(y));a(0x0a3e,V(8),V(9),V(10),F(8),F(8),F(40),V(29))
 alive(f,29,bad)
 for j in range(e):f.get(31,GC_CAND+j);f.check(0x803b,[V(29),V(31)],bad)
 if e==0:f.call('NOT_FRIEND')
 else:gunner_mode_check(P)
 f.eq(30,1,bad);f.call('TARGET_IN_RANGE');f.eq(30,1,bad);a(0xddc,I(GC_CAND+e),V(29));f.call('THREAT_SCORE');f.call('GS_INSERT');f.go(nxt)
 f.label(bad);f.set(GC_CAND+e,-1);f.label(nxt)
f.ret()
for guard in [3,4,5,6]:
 g=guard-3;T='SG_TAKE_%d'%guard
 f.label('SELECT_GUARD_TARGET_'+str(guard))
 f.eq(25,2,'SG_SCAN_'+str(guard));f.get(29,FIRE_TASK_TARGET);f.ret();f.label('SG_SCAN_'+str(guard));f.set(GT_YIELD+g,-1)
 for n in range(GS_N):
  nxt='SG_CJAIM_%d_%d'%(guard,n);f.get(29,GS_H+n);alive(f,29,nxt);f.check(0x0457,[I(0),V(29)],nxt);f.call('GUNNER_FOCUS_%d'%guard);f.eq(30,1,nxt);f.go(T);f.label(nxt)
 f.get(29,GS_H);f.get(30,GS_S);f.check(0x0019,[V(30),I(SCORE_FOCUS-1)],'SG_PREV_%d'%guard);f.call('GUNNER_FOCUS_%d'%guard);f.eq(30,1,'SG_PREV_%d'%guard);f.go(T)
 f.label('SG_PREV_%d'%guard);f.get(29,GT_PREV+g);f.call('GUNNER_PREV_%d'%guard);f.eq(30,1,'SG_PREV_LOST_%d'%guard);f.go(T);f.label('SG_PREV_LOST_%d'%guard)
 for side in [1,0]:
  for n in range(GS_N):
   nxt='SG_NEXT_%d_%d_%d'%(guard,side,n);f.get(29,GS_H+n);f.call('GUNNER_OK_%d_%d'%(guard,side));f.eq(30,1,nxt);f.go(T);f.label(nxt)
 f.get(29,GT_PREV+g);f.call('GUNNER_SUPP_%d'%guard);f.eq(30,1,'SG_PRIMARY_%d'%guard);f.set(GT_SUPP+g,1);f.ret()
 f.label('SG_PRIMARY_%d'%guard);f.set(GT_SUPP+g,0);f.get(29,FIRE_TASK_TARGET);f.ret()
 # a target seen with a clear line: remember where, for suppressive fire once he hides
 f.label(T);f.set(GT_SUPP+g,0)
 # hit tracking: the clock restarts on a new target or whenever the target loses health
 a(0x0226,V(29),V(14));f.get(15,GT_PREV+g);f.check(0x003b,[V(29),V(15)],'SG_HP_RESET_%d'%guard);f.get(15,PREV_HP+g);f.check(0x001d,[V(15),V(14)],'SG_HP_KEEP_%d'%guard)
 f.label('SG_HP_RESET_%d'%guard);a(0x01bd,V(15));a(0xddc,I(PREV_HP_T+g),V(15))
 f.label('SG_HP_KEEP_%d'%guard);a(0xddc,I(PREV_HP+g),V(14))
 a(0x00a0,V(29),V(11),V(12),V(13));a(0xddc,I(SUP_X+g),V(11));a(0xddc,I(SUP_Y+g),V(12));a(0xddc,I(SUP_Z+g),V(13));a(0x01bd,V(31));a(0xddc,I(SUP_T+g),V(31));f.ret()
 # light checks for an already validated candidate: alive, not taken, (side), clear line from his seat
 for side in [1,0]:
  P='GOK_%d_%d_'%(guard,side);fail=P+'FAIL'
  f.label('GUNNER_OK_%d_%d'%(guard,side));a(6,V(30),I(0));alive(f,29,fail);f.get(31,GT_YIELD+guard-3);f.check(0x803b,[V(29),V(31)],fail)
  for prior in range(guard-3):f.get(31,GUARD_TARGET+prior);f.check(0x803b,[V(29),V(31)],fail)
  a(0x00a0,V(29),V(11),V(12),V(13))
  if side:
   a(0x0407,V(1),F(6),F(0),F(0),V(14),V(15),V(16));a(0x0407,V(1),F(-6),F(0),F(0),V(17),V(18),V(19))
   a(0x050a,V(11),V(12),V(13),V(14),V(15),V(16),V(20));a(0x050a,V(11),V(12),V(13),V(17),V(18),V(19),V(21))
   f.check(0x0025,[V(21),V(20)] if guard in (3,5) else [V(20),V(21)],fail)
  a(0x00a0,V(guard),V(14),V(15),V(16));a(0x0087,V(17),V(13));a(0x000b,V(17),F(.5))
  f.check(0x06bd,[V(14),V(15),V(16),V(11),V(12),V(17),I(1),I(0),I(0),I(0),I(0)],fail)
  a(6,V(30),I(1));f.ret()
  f.label(fail);a(6,V(30),I(0));f.ret()
 # 30@ = 1 when 29@ is on this round's list
 P='GLS_%d_'%guard
 f.label('GUNNER_LISTED_%d'%guard);a(6,V(30),I(0))
 for n in range(GS_N):f.get(31,GS_H+n);f.check(0x003b,[V(29),V(31)],P+'N%d'%n);a(6,V(30),I(1));f.ret();f.label(P+'N%d'%n)
 f.ret()
 # previous target: still on the list (so still a threat under the rules), then the light checks
 P='GPV_%d_'%guard;fail=P+'FAIL'
 f.label('GUNNER_PREV_%d'%guard);alive(f,29,fail);f.call('GUNNER_LISTED_%d'%guard);f.eq(30,1,fail)
 f.get(30,PREV_HP_T+g);a(0x01bd,V(31));a(0x0062,V(31),V(30));f.check(0x8019,[V(31),I(5000)],P+'YIELD');f.call('GUNNER_OK_%d_0'%guard);f.ret()
 f.label(P+'YIELD');a(0xddc,I(GT_YIELD+g),V(29))
 f.label(fail);a(6,V(30),I(0));f.ret()
 # suppression: the previous target is still listed and was last seen less than 4 s ago
 P='GSP_%d_'%guard;fail=P+'FAIL'
 f.label('GUNNER_SUPP_%d'%guard);alive(f,29,fail);f.get(31,GT_YIELD+g);f.check(0x803b,[V(29),V(31)],fail);f.call('GUNNER_LISTED_%d'%guard);f.eq(30,1,fail)
 f.get(30,SUP_T+g);a(0x01bd,V(31));a(0x0062,V(31),V(30));f.check(0x8019,[V(31),I(4000)],fail);a(6,V(30),I(1));f.ret()
 f.label(fail);a(6,V(30),I(0));f.ret()
 # focus: at most two gunners on the top threat, each with a clear line; call it out once
 P='GFC_%d_'%guard;fail=P+'FAIL'
 f.label('GUNNER_FOCUS_%d'%guard);a(6,V(30),I(0));alive(f,29,fail);a(6,V(22),I(0))
 for prior in range(guard-3):
  nx=P+'PRIOR_%d'%prior;f.get(31,GUARD_TARGET+prior);f.check(0x003b,[V(29),V(31)],nx);a(0x000a,V(22),I(1));f.label(nx)
 f.check(0x0019,[V(22),I(1)],P+'ROOM');f.go(fail);f.label(P+'ROOM')
 a(0x00a0,V(29),V(11),V(12),V(13));a(0x00a0,V(guard),V(14),V(15),V(16));a(0x0087,V(17),V(13));a(0x000b,V(17),F(.5))
 f.check(0x06bd,[V(14),V(15),V(16),V(11),V(12),V(17),I(1),I(0),I(0),I(0),I(0)],fail)
 f.get(31,FOCUS_SEEN);f.check(0x803b,[V(29),V(31)],P+'SAID');a(0xddc,I(FOCUS_SEEN),V(29));msg(f,'HCFOCUS')
 f.label(P+'SAID');a(6,V(30),I(1));f.ret()
 f.label(fail);a(6,V(30),I(0));f.ret()

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

# v39.4: 30@ = 1 and 22@..24@ = the shooter position when a fresh hostile round came down at CJ.
f.label('AIR_SCAN');a(6,V(30),I(0));f.get(14,GAME_OK);f.eq(14,1,'AIR_RET');f.check(0x010f,[I(0),I(2)],'AIR_RET')
a(0x00a0,V(0),V(8),V(9),V(10));a(0x00aa,V(1),V(11),V(12),V(13));a(0x01bd,V(31))
for k in range(BULLET_TRACE_COUNT):
 base=BULLET_TRACES_OFS+k*BULLET_TRACE_SIZE;nxt='AIR_TRACE_NEXT_'+str(k)
 a(0x0dd8,V(14),I(base+24),I(1),I(1));f.eq(14,1,nxt)
 a(0x0dd8,V(14),I(base+28),I(4),I(1));a(0x0085,V(15),V(31));a(0x0062,V(15),V(14));f.check(0x8019,[V(15),I(1500)],nxt)
 a(0x0dd8,V(16),I(base+12),I(4),I(1));a(0x0dd8,V(17),I(base+16),I(4),I(1));a(0x0dd8,V(18),I(base+20),I(4),I(1))
 a(0x050a,V(8),V(9),V(10),V(16),V(17),V(18),V(19));f.check(0x0023,[F(12),V(19)],nxt)
 a(0x0dd8,V(16),I(base),I(4),I(1));a(0x0dd8,V(17),I(base+4),I(4),I(1));a(0x0dd8,V(18),I(base+8),I(4),I(1))
 for v,lo,hi in [(16,-3100,3100),(17,-3100,3100),(18,-100,1500)]:f.check(0x0021,[V(v),F(lo)],nxt);f.check(0x0023,[F(hi),V(v)],nxt)
 a(0x0087,V(19),V(18));a(0x0063,V(19),V(10));f.check(0x0021,[V(19),F(10)],nxt)
 a(0x050a,V(11),V(12),V(13),V(16),V(17),V(18),V(19));f.check(0x0021,[V(19),F(15)],nxt)
 a(0x050a,V(8),V(9),V(10),V(16),V(17),V(18),V(19));f.check(0x0023,[F(220),V(19)],nxt)
 a(0xddc,I(AIR_X),V(16));a(0xddc,I(AIR_Y),V(17));a(0xddc,I(AIR_Z),V(18));a(0xddc,I(AIR_SEEN),V(31));f.go('AIR_USE');f.label(nxt)
f.get(14,AIR_SEEN);f.eq(14,0,'AIR_RECENT');f.ret()
f.label('AIR_RECENT');a(0x0085,V(15),V(31));a(0x0062,V(15),V(14));f.check(0x8019,[V(15),I(3000)],'AIR_RET')
f.label('AIR_USE');f.get(22,AIR_X);f.get(23,AIR_Y);f.get(24,AIR_Z);a(6,V(30),I(1))
f.label('AIR_RET');f.ret()
f.label('AIR_CALLOUT');f.set(ENGAGED,1);f.set(CLEAR_AT,0);f.get(30,AIR_CALL_NEXT);a(0x01bd,V(31));f.check(0x001d,[V(31),V(30)],'AIR_CALL_RET');a(0x000a,V(31),I(10000));a(0xddc,I(AIR_CALL_NEXT),V(31));msg(f,'HCAIR')
f.label('AIR_CALL_RET');a(6,V(30),I(1));f.ret()
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
f.get(30,HUD);f.eq(30,LEVEL_ALL,'KILL_GONE');f.get(30,KILL_NEXT);a(0x01bd,V(14));f.check(0x001d,[V(14),V(30)],'KILL_GONE');a(0x000a,V(14),I(2000));a(0xddc,I(KILL_NEXT),V(14));a(0x01e5,S('HCKILL'),V(31),I(2000),I(1))
f.label('KILL_GONE');f.set(LAST_TGT,-1)
f.label('KILL_RET');f.ret()
f.label('CLEAR_CHECK');f.get(30,ENGAGED);f.eq(30,1,'CLEAR_RET');f.get(30,CLEAR_AT);a(0x01bd,V(31));f.eq(30,0,'CLEAR_TIMED');a(0x000a,V(31),I(3000));a(0xddc,I(CLEAR_AT),V(31));f.ret()
f.label('CLEAR_TIMED');f.check(0x001d,[V(31),V(30)],'CLEAR_RET');f.set(ENGAGED,0);f.set(CLEAR_AT,0);f.get(30,SQ_GROUP);f.eq(30,0,'SOLO_HCCLEAR_SQ');msg(f,'HCCLEAR');f.go('SOLO_HCCLEAR');f.label('SOLO_HCCLEAR_SQ');squad_owns(f,'SOLO_HCCLEAR',30,31);msg(f,'HCCLEAR');f.label('SOLO_HCCLEAR')
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
