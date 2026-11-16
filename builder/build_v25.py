from asm_v25 import *
from pathlib import Path
import zipfile
# Separate namespace from v2; settings are session-local and survive new calls.
STATE=0x48456A00;CMD=STATE+1;HEART=STATE+2;OPEN=STATE+3;PANELHEART=STATE+4
MODEL=STATE+5;CREW=STATE+6;FIRE=STATE+7;TOUCH=STATE+8;HUD=STATE+9;HP=STATE+10
PUB=STATE+20;PHASE=STATE+27;ACTUAL=STATE+28;BUSY=STATE+29;FIREHEART=STATE+30;WPN=STATE+31;FIRENEXT=STATE+32
ACREW=STATE+33;LSTAGE=STATE+34;LALT=STATE+35;FROZEN=STATE+36;SKINSAVE=STATE+37;CREWNEW=STATE+40;CREWGEN=STATE+45;FIREGEN=STATE+46
GROVE_STREAM=STATE+50;GROVE_WAIT=STATE+51;LAND_STABLE=STATE+53;GROVE_NEXT_SCAN=STATE+54
FIRE_TARGET=STATE+55
FIRE_ACTIVE=STATE+59;TRACKED_TARGET=STATE+60
LAND_SLOW=STATE+63;LAND_FINAL=STATE+64
WEAPON_SETTING=STATE+65
ROPE_COMMAND=STATE+70;GROUND_PUB=STATE+71;GROUND_MOVE_NEXT=STATE+80;DROP_COMMAND=STATE+81;DEST_X=STATE+82;DEST_Y=STATE+83;DEST_Z=STATE+84;PATROL_STEP=STATE+97;PATROL_NEXT=STATE+98;FOLLOW_NEXT=STATE+99;AVOID_STAGE=STATE+110;AVOID_NEXT=STATE+111;AVOID_AT=STATE+112;AVOID_X=STATE+113;AVOID_Y=STATE+114;AVOID_Z=STATE+115
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
ORBIT_RADIUS=28.0
# beta 4 command gate: orders that must not interrupt somebody on a rope; orders that are dropped when they are already in force
GATE_ROPE_ORDERS=[2,3,4,7,10,11,14,15,16,17];GATE_SAME=[(2,[2]),(3,[3]),(14,[24]),(7,[20,10,11])];MAP_FLIGHT_STATES=[21,25,22]
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
AIR_SEEN=STATE+153;AIR_CALL_NEXT=STATE+154
# v40 tactical squad AI (Helicover_Squad.csa). SQ_HEART = squad worker heartbeat; TACTICS 0 bodyguard /
# 1 assault; SQ_ROPE 1 while the ground worker's rope/escort guards are on the ground under squad control;
# ESCORT_ON 1 while the escort team is deployed; ESCORT_CMD core->ground 1 deploy / 2 recall;
# ESCORT_PENDING tells ROPE_ARRIVE why the core hovered (0 rope pickup, 1 deploy, 2 recall).
SQ_HEART=STATE+155;TACTICS=STATE+156;SQ_ROPE=STATE+157;ESCORT_ON=STATE+158;ESCORT_CMD=STATE+159;ESCORT_PENDING=STATE+160
SQ_THREATS=STATE+161;SQ_T=STATE+162  # SQ_T..SQ_T+3 = current threats (char handles or -1)
SQ_MSG_NEXT=STATE+166;SQ_MEDIC_NEXT=STATE+167;SQ_CONTACT=STATE+168;SQ_CLEAR_AT=STATE+169;SQ_SCAN_NEXT=STATE+170;SQ_GROUP=STATE+171
SQ_SLOT=STATE+172;SQ_SLOT_SIZE=10   # per guard slot: TASK NEXT TX TY LX LY LT DEAD TGT spare
# v40 overwatch flight: station index/time, hull sampling and evasive manoeuvre deadline
# the squad's cover / reload / call-out state
from msg_v42 import say,emit_resolve_lang,emit_banner,LANG,print_key,MSG_UNTIL,MSG_PRIO,MSG_ID,MSG_HOLD,BANNER_ARMED,LEVEL_ALL,GAME_RU_FLAG
import msg_v42 as _mv;assert _mv.HUD==HUD
# What the brain tells the scripts about fire that is not ours (1.3: the threat board, the scores and the reading of bullet traces are gone)
HELI_SHOT_T=STATE+254                                  # when a stranger's round last passed the helicopter (the pilot's evasion)
CJ_AIM_X=STATE+369;CJ_AIM_Y=STATE+370;CJ_AIM_T=STATE+375   # the line of CJ's own last shot and its time (the squad keeps out of it)
BLOCK_T=STATE+390;SQ_CARH=STATE+391;SQ_DRIVES=STATE+392;ESC_LAGGED=STATE+393;ROPE_T0=STATE+394;SQ_LAG=STATE+395   # SQ_LAG..+3: per guard, time since he fell 70 m behind CJ
# 1.3: the brain. BRAIN_HELLO is created with 0 by the core; the mod answers BRAIN_MAGIC in it once its opcode is registered.
# POLICE 0 = fire back at policemen who shoot, 1 = never fire at the police; MISSIONS 0 = defensive in missions, 1 = as usual.
BRAIN_HELLO=STATE+440;POLICE=STATE+441;MISSIONS=STATE+442;BRAIN_MAGIC=0x42520021
G_AIM=STATE+443;G_AIM_T=STATE+447        # per gunner: the man his weapon is on (-1 = resting), when the aiming task is due again
BR_ALERT=STATE+451;BR_TOP=STATE+452;BR_KILLS=STATE+453;BR_THREATS=STATE+454;BR_ATTACKERS=STATE+455
SQ_BR_ST=STATE+456;SQ_BR_TG=STATE+460    # per guard of the squad: the brain's state (0 nothing, 1 cover, 2 fire, 3 cease fire) and man
SQ_TICK=STATE+464
# 1.4.1: the second four of the ground team (guards 5-8) and their own squad worker (Helicover_Squad2) and lifecycle (Helicover_Team2)
GROUND_PUB2=STATE+480;SQ_SLOT2=STATE+500;SQ_BR_ST2=STATE+540;SQ_BR_TG2=STATE+544;SQ_PACE2=STATE+548;SQ_T2=STATE+552
SQ_HEART2=STATE+556;SQ_GROUP2=STATE+557;SQ_TICK2=STATE+558;TEAM2_STATE=STATE+559
AUTO_DEPLOY_T=STATE+567   # 1.5.4: when the helicopter may next send the team down on its own
TEAM2_LAG=STATE+569   # 1.5.4: +0..3 per man of the second four: since when he has been 45 m or more from CJ
CMD_SRC=STATE+568   # 1.5.4: who wrote CMD last: 1 the menu, 2 the commander's "we pull out", 3 the automatic deployment (the log says it)
CR_LAND=STATE+566   # 1.5.3: 1 while the pilot is asked for a landing approach (flag 8: down to 15 m over the pad on the way in)
MODE=STATE+573;RECALL=STATE+574;NATIVE=STATE+575;SQ_TASK_SAID=STATE+576;TEAM2_HEART=STATE+577   # 2.0: the player's mode (0 PROTECT, 1 ASSAULT); "to me" (the brain takes the 1); 1 = the mod walks the guards itself (the squad worker writes it from the brain's answer)
DEPLOY_T0=STATE+565   # 1.5: when the first four went down the ropes (the second four follow them down the same ropes 3 s later)
COMBAT_PILOT=STATE+564   # 1.5: 1 while the brain's own pilot holds the helicopter on its station in a fight (escort, state 2)
HELI_SPOT_X=STATE+561;HELI_SPOT_Y=STATE+562;HELI_SPOT_Z=STATE+563   # 1.4.1: the brain's spot for the helicopter in a fight (floats; x = 0 none)
SQ_PACE=STATE+230   # 1.4, per guard: the pace of his last move order (a new pace renews the order)
G_FIRE=STATE+465;G_FIRE_T=STATE+469;SQ_SAY_SEQ=STATE+473   # SQ_SAY_SEQ: the number of the commander's last words the squad has said (-1 = take the next number without saying it)   # 1.4, per gunner: the man his own weapon is firing at (-1 = not firing), when the firing order is renewed
BURN_NEXT=STATE+433;BURN_SAID=STATE+434;POSE=STATE+435;POSE_DONE=STATE+436   # beta 6: burning-car watch; gunners sit on the skid (2, 1.4) / kneel (1) / stand (0)
# A burning car (health below BURN_HP) within BURN_WARN_M of CJ is called out. Which cars may be fired at is the brain's business (1.3).
BURN_HP=250;BURN_WARN_M=12.0
NAP_UNTIL=STATE+428   # beta 5: end of the core's current 100 ms nap (an order ends the nap at once)
AFTER_ROPE=STATE+425;DISMISS_NEXT=STATE+426;LEAVE_ROT=STATE+427   # beta 4: the order that follows once a cancelled pickup's cover team is back aboard / when the panel may ask for the recall again
ROPE_WAIT=STATE+415;LEAVE=STATE+416;LEAVE_N=STATE+424   # beta 4: the rope hangs waiting for CJ / LEAVE..+7: guards who were let go and walk away / 1 while any is left
ROPE_BUSY=STATE+406;SWAP_MSG=STATE+407;TEAM_CREW=STATE+408;DISMISS_T=STATE+411;PB_AIM=STATE+412   # PB_AIM..+2: the aim point the gunners were called with   # 1.2 decor: a rope motion is under way / swap message shown / crew setting the ground team wears
FORM_UX=STATE+399;FORM_UY=STATE+400;FORM_PX=STATE+401;FORM_PY=STATE+402;FORM_T=STATE+403;FORM_CT=STATE+404;FORM_OK=STATE+405   # formation anchor (unit travel direction)
NOTICE_SKIP=STATE+335;HELLO_AT=STATE+336;KILL_NEXT=STATE+337
CV_X=STATE+292;CV_Y=STATE+296;CV_Z=STATE+300;CV_T=STATE+304;CV_H=STATE+308;CV_OK=STATE+312;ENG_T=STATE+316  # per guard
SQ_CV_TICK=STATE+320;SQ_QUIET_T=STATE+321;SQ_EVAC_NEXT=STATE+322;SQ_CALLED=STATE+323;SQ_SC=STATE+324  # SQ_SC..+3 squad scores
ST_I=STATE+215;ST_NEXT=STATE+216;HP_PREV=STATE+217;HP_T=STATE+218;EVADE_UNTIL=STATE+219
EXIT_WIDGET=0  # CTouchInterface widget of the on-screen enter/exit vehicle button (CPad::ExitVehicleJustDown)
CRUISE_T=STATE+118;CR_UP=STATE+119;CR_DN=STATE+120
CR_CMDZ=STATE+128  # v33: commanded z, integrated by steps (never rebuilt from the actual z)
CR_DT=STATE+121;CR_V=STATE+122;CR_VT=STATE+123;CR_SLOW=STATE+124;CR_BLK=CR_SLOW;CR_DX=STATE+125;CR_DY=STATE+126;CR_DZ=STATE+127
# v32 scripted cruise for map/Grove flights: per-frame, time-based, with acceleration,
# braking, rate-limited turning and smooth altitude changes (no jerks, no circling).
SEAT_DROP=0.45;SEAT_OUT=0.15   # 1.4: a seated gunner sits this much lower and further out than a kneeling one
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
 'HCCONT': '~r~CONTACT!~w~ Gunners engaging.',
 'HCKILL': '~g~TARGET DOWN~w~ ~1~',
 'HCCLEAR': '~g~GUNNERS:~w~ area clear.',
 'HCNOBR': '~r~NO BRAIN MOD.~w~ Put libHelicoverBrain64.so into the mods folder.',
 'HCFM0': '~y~GUNNERS:~w~ cease fire.',
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
 'HCOFF': '~r~HELICOVER:~w~ files missing. Copy all files to CLEO and restart.',
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
 'HCBUSY':'~y~PILOT:~w~ emergency landing - cannot comply.',
 'HCSLATE':'~y~PILOT:~w~ I make the change right after the rope.',
 'HCXBL':'~b~PILOT:~w~ exit button: I land.',
 'HCXBR':'~b~PILOT:~w~ exit button: you go down the rope.',
 'HCRBSY':'~y~PILOT:~w~ wait - rope work in progress.',
 'HCRCAN':'~b~PILOT:~w~ pickup cancelled. Ropes up.',
 'HCRUP':'~b~PILOT:~w~ squad, back up the ropes.',
 'HCDSQ':'~b~PILOT:~w~ picking the squad up first, then we leave.',
 'HCMDP':'~g~ALPHA:~w~ PROTECT. Three by you, four in cover, marksman up high.',
 'HCMDA':'~r~ALPHA:~w~ ASSAULT. Aim or fire at an enemy - we go for him.',
 'HCRCL':'~g~ALPHA:~w~ all back to CJ!',
 'HCBURN': '~r~CAR ON FIRE!~w~ Get away from it.',
 'HCEVADE': '~r~TAKING HITS!~w~ Pilot breaking away.',
 'HCSHOT': '~r~TAKING FIRE!~w~ Pilot breaking away.',
 'HCHELLO': '~b~HELICOVER 2.0 BETA 3~w~ ready. CLEO menu > Helicover.',
 'HCHELLV': '~b~HELICOVER 2.0 BETA 3~w~ ready. Map marker is off here.'}
# Generate state updates; panel prints messages when the state changes.
# beta 6: our people do not cower. CREATE_CHAR gives a mission ped the built-in "normal" decision maker (m_norm.ped): punched, shot at or
# aimed at, it picks "duck and cover" / "flee" like any passer-by. 65542 is the game's built-in EMPTY decision maker (slot 6 | 1<<16, loaded
# by CDecisionMakerTypesFileLoader::LoadDefaultDecisionMaker): no response to any event, so the ped keeps the task the script gave him and
# can never be turned against CJ by an event. (Not 060A: every call takes one of five script slots and the table is kept in save files.)
EMPTY_DM=65542
def brave(s,var,P):
 s.check(0x09f2,[I(EMPTY_DM)],P+'_NO_DM');s.add(0x060b,V(var),I(EMPTY_DM));s.label(P+'_NO_DM')
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
c.set(GAME_OK,1);c.label('GAME_SIG_BAD');c.set(COMBAT_PILOT,0);c.set(CR_LAND,0);c.set(NOTICE_SKIP,-1);c.set(HELLO_AT,0);c.set(MSG_UNTIL,0);c.set(MSG_PRIO,0);c.set(MSG_HOLD,0);c.set(BANNER_ARMED,0);c.set(AVOID_STAGE,0);c.set(AVOID_NEXT,0);c.set(BUSY,0);c.set(FROZEN,0);c.set(LSTAGE,0);c.set(CREWGEN,0);c.set(FIRE_TARGET,-1);c.set(FIRE_ACTIVE,0);c.set(TRACKED_TARGET,-1);c.set(STUCK_SINCE,0)
for key in range(PUB,PUB+7):c.set(key,-1)
for key in range(GROUND_PUB,GROUND_PUB+5):c.set(key,-1)
c.set(ROPE_COMMAND,0)
for key,val in [(SQ_SAY_SEQ,-1),(BRAIN_HELLO,0),(POLICE,0),(MISSIONS,0),(MODE,0),(RECALL,0),(NATIVE,0),(SQ_TASK_SAID,-1),(TEAM2_HEART,0),(BR_ALERT,0),(BR_TOP,-1),(BR_THREATS,0),(BR_ATTACKERS,0),(POSE,2),(POSE_DONE,2),(LANG,0),(ROPE_WAIT,0),(LEAVE_N,0),(AFTER_ROPE,0),(DISMISS_NEXT,0),(LEAVE_ROT,0),(ROPE_BUSY,0),(SWAP_MSG,0),(TEAM_CREW,0),(STATE,0),(CMD,0),(OPEN,0),(MODEL,487),(CREW,2),(FIRE,3),(TOUCH,0),(HUD,2),(HP,0),(WEAPON_SETTING,0),(EXIT_MODE,0),(AUTO_EXIT,0),(LOCK_HOLD,0),(ROPE_PENDING,0),(DROP_RESULT,0),(ROPE_TRIES,0),(RETRY_AT,0),(FORCE_ROPE,0),(EXIT_PRESSED,0),(EXIT_LAST,0),(AIR_SEEN,0),(AIR_CALL_NEXT,0),(KILLS,0),(LAST_TGT,-1),(ENGAGED,0),(CLEAR_AT,0),(ORBIT_I,0),(ORBIT_NEXT,0),(TACTICS,0),(ESCORT_PENDING,0),(ST_I,0),(ST_NEXT,0),(HP_PREV,0),(HP_T,0),(EVADE_UNTIL,0),(HELI_SHOT_T,-100000)]:c.set(key,val)
c.label('IDLE');c.call('NAP');c.call('RESOLVE_LANG');a(0x01bd,V(20));a(0xddc,I(HEART),V(20));c.get(19,HELLO_AT);c.eq(19,-1,'HELLO_CHECK');c.go('HELLO_DONE')
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
# 1.3: no brain, no Helicover. The mod answers the handshake value one frame after the scripts start; if it has not (it is not
# installed, or it refused this build of the game or of CLEO - its log says which), the helicopter is not called and the player is told why.
c.label('LOAD');c.get(19,BRAIN_HELLO);c.check(0x0039,[V(19),I(BRAIN_MAGIC)],'NO_BRAIN');c.go('LOAD_GO')
c.label('NO_BRAIN');msg(c,'HCNOBR');c.go('IDLE')
c.label('LOAD_GO');c.check(0x0256,[I(0)],'IDLE');a(0x077e,V(17));c.eq(17,0,'OUTDOORS');state(c,1)
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
a(6,V(24),I(0));a(6,V(22),I(0))
# 1.2: the helicopter flies in from far away instead of popping up 45 m from CJ. It is created on a ring 160 m
# out (first behind CJ, then seven more bearings) and, in the same tick, moved to the next bearing while it is
# still on screen, so the player never sees it appear. Altitude: at least 25 m above the highest surface there
# (02CE only knows it where the collision is loaded) and at least 50 m above CJ.
SPAWN_RING=[(0,-160),(-113,-113),(113,-113),(-160,0),(160,0),(-113,113),(113,113),(0,160)]
for k,(ox,oy) in enumerate(SPAWN_RING):
 c.label('SPAWN_TRY_%d'%k)
 if k:c.check(0x02ca,[V(5)],'SPAWN_PLACED')
 a(0x04c4,V(18),F(ox),F(oy),F(0),V(9),V(10),V(11));a(0x04e4,V(9),V(10));a(0x00a0,V(18),V(26),V(27),V(28));a(0x000b,V(28),F(50))
 a(0x02ce,V(9),V(10),F(1000),V(17));a(0x000b,V(17),F(25));a(0x0087,V(11),V(28));c.check(0x0025,[V(17),V(28)],'SPAWN_Z_%d'%k);a(0x0087,V(11),V(17));c.label('SPAWN_Z_%d'%k)
 if k==0:a(0x00a5,V(0),V(9),V(10),V(11),V(5))
 else:a(0x00ab,V(5),V(9),V(10),V(11))
c.label('SPAWN_PLACED')
a(0x00a0,V(18),V(26),V(27),V(28));a(0x039f,V(5),V(26),V(27));a(0x04ba,V(5),F(25));a(0x00aa,V(5),V(9),V(10),V(11));a(0x0129,V(5),I(8),V(1),V(4));a(0x01c5,V(4));a(0x08af,V(4),I(200));a(0x0223,V(4),I(200));a(0x054a,V(4),I(1));a(0x0446,V(4),I(1));a(0x077a,V(4),I(0),I(0));brave(c,4,'BRAVE_PILOT')
a(0x0186,V(5),V(12));a(0x0168,V(12),I(2));a(0x0165,V(12),I(2));a(0x07e0,V(12),I(1));a(0x0957,V(5),I(1))
for v,skin in [(13,2),(14,3),(15,2),(16,3)]:
 # Four guards are retained for all models, including four external Hunter positions.
 a(0x009a,I(8),V(skin),V(9),V(10),V(11),V(v));a(0x01c5,V(v));a(0x08af,V(v),I(150));a(0x0223,V(v),I(150));a(0x035f,V(v),I(50));a(0x054a,V(v),I(1));a(0x0446,V(v),I(1));a(0x02e2,V(v),I(100))
 for typ in range(32):a(0x077a,V(v),I(2),I(typ))
 a(0x077a,V(v),I(0),I(0));a(0x077a,V(v),I(0),I(8));brave(c,v,'BRAVE_CREW_%d'%v)
c.label('TEAM_READY');c.call('PUBLISH');c.call('ARM_CREW');a(0x0825,V(5));a(0x07bb,V(5),I(6));a(6,V(23),I(-1));c.call('REATTACH_TEAM');c.call('APPLY_FIRE')
for v in [0,1,2,3]:a(0x0249,V(v))
c.eq(25,5,'TEAM_CHECK_ROPE');c.go('EVAC')
c.label('TEAM_CHECK_ROPE');c.eq(25,11,'TEAM_CHECK_PATROL');c.go('ROPE_PREP')
c.label('TEAM_CHECK_PATROL');c.eq(25,12,'FOLLOW');c.go('PATROL_START')
# v34: per-frame ticks only while the script itself moves the helicopter (cruise, glide, descent);
# long frozen holds (awaiting a choice, rope work) go back to the normal 100 ms tick.
# beta 5: the core still works every 100 ms, but an order does not wait for the end of the nap: the nap is slept frame by frame and
# ends the moment CMD is set (the menu page then follows the order on the next frame instead of up to 0.1 s later). Uses 17@, 19@.
c.label('NAP');a(0x01bd,V(19));a(0x000a,V(19),I(100));a(0xddc,I(NAP_UNTIL),V(19))
c.label('NAP_LOOP');a(1,I(0));c.get(19,CMD);c.eq(19,0,'NAP_END');a(0x01bd,V(19));c.get(17,NAP_UNTIL);c.check(0x801d,[V(17),V(19)],'NAP_LOOP')
c.label('NAP_END');c.ret()
c.label('TICK');c.get(19,FROZEN);c.eq(19,1,'TICK_NORMAL_WAIT');c.get(19,STATE)
for st in [10,19,21,22]:
 nxt='TICK_FAST_NOT_'+str(st);c.eq(19,st,nxt);a(1,I(0));c.go('TICK_AFTER_WAIT');c.label(nxt)
c.eq(19,2,'TICK_FAST_NOT_CP');c.get(19,COMBAT_PILOT);c.eq(19,1,'TICK_FAST_NOT_CP');a(1,I(0));c.go('TICK_AFTER_WAIT');c.label('TICK_FAST_NOT_CP')
c.label('TICK_NORMAL_WAIT');c.call('NAP')
c.label('TICK_AFTER_WAIT')
if DEBUG_BREADCRUMBS:
 c.get(19,STATE);a(0x0012,V(19),I(100));c.get(17,DBG_CODE);a(0x005a,V(19),V(17));c.get(17,DBG_LAST);c.check(0x803b,[V(19),V(17)],'DBG_SAME');a(0x01e5,S('HCDBG'),V(19),I(600000),I(1));a(0xddc,I(DBG_LAST),V(19));c.label('DBG_SAME')
a(0x01bd,V(20));a(0xddc,I(HEART),V(20));healthcheck(c,'CLEANUP');c.call('RESOLVE_LANG');c.call('CHANGE_MODEL');c.call('CHANGE_CREW');c.call('CHANGE_POSE');c.call('PUBLISH');c.get(7,STATE);a(0x0227,V(5),V(6));a(0xddc,I(HP),V(6));c.call('EVADE_CHECK');c.call('TRACK_COMBAT');c.call('FLIGHT_AVOID');c.call('UNSTICK');c.call('EXIT_BUTTON');c.get(7,STATE)
c.get(19,FIRE);c.check(0x003b,[V(19),V(23)],'UPDATE_FIRE');c.go('HEALTH')
c.label('UPDATE_FIRE');c.call('APPLY_FIRE')
c.label('HEALTH');c.eq(7,15,'HEALTH_LANDED_CHECK');c.go('DISPATCH')
c.label('HEALTH_LANDED_CHECK');c.eq(7,12,'CHECK_HEALTH');c.go('DISPATCH')
c.label('CHECK_HEALTH');c.check(0x0019,[V(6),I(350)],'LOW_HEALTH');c.go('DISPATCH')
c.label('LOW_HEALTH');c.check(0x80db,[V(18),V(5)],'EMERGENCY');a(6,V(25),I(13));c.go('DEPART')   # 1.2: CJ aboard -> emergency landing, CJ on foot -> retreat (not decided by the crew phase)
c.label('DISPATCH');c.get(8,CMD);c.set(CMD,0)
# 1.2: state 18 (landing blocked / no route / climb failed) used to last forever: with CJ on foot the pilot goes back to
# following him after 15 s; in an emergency landing (15) FOLLOW / HOLD / DEPART / PATROL are refused (the health
# check would have flipped the state back the next tick)
c.eq(7,18,'BLOCK_WATCH_CLEAR');c.get(19,BLOCK_T);c.eq(19,0,'BLOCK_WATCH_RUN');a(0xddc,I(BLOCK_T),V(20));c.go('BLOCK_WATCH_DONE')
c.label('BLOCK_WATCH_RUN');a(0x0085,V(17),V(20));a(0x0062,V(17),V(19));c.check(0x0019,[V(17),I(15000)],'BLOCK_WATCH_DONE');c.check(0x80db,[V(18),V(5)],'BLOCK_WATCH_DONE');c.eq(8,0,'BLOCK_WATCH_DONE');c.set(BLOCK_T,0);a(6,V(8),I(2));c.go('BLOCK_WATCH_DONE')   # CJ on foot for 15 s: back to FOLLOW
c.label('BLOCK_WATCH_CLEAR');c.set(BLOCK_T,0)
c.label('BLOCK_WATCH_DONE')
c.eq(7,15,'DISPATCH_NORMAL')
for cmd in [2,3,4,14]:
 nxt='EMERGENCY_REFUSE_'+str(cmd);c.eq(8,cmd,nxt);msg(c,'HCBUSY');c.go('TICK');c.label(nxt)
c.label('DISPATCH_NORMAL')
# ---- beta 4 command gate: an order that is already being carried out is not started again, and nothing interrupts rope work.
# 8@ = the order (0 = none), 7@ = state. A dropped order becomes 0 and the state's own work goes on.
c.eq(8,0,'GATE');c.go('GATE_PASS')
c.label('GATE')
for cmd,states in GATE_SAME:   # the mode that is already on / the flight that is already under way
 nxt='GATE_SAME_NOT_%d'%cmd;c.eq(8,cmd,nxt)
 for st in states:
  n2='GATE_SAME_%d_NOT_%d'%(cmd,st);c.eq(7,st,n2);c.go('GATE_DROP');c.label(n2)
 c.label(nxt)
c.call('SQUAD_MOVING')        # 17@ = 1 while the squad is on its way down or back up: its row shows that, a second order is not taken
for cmd in [16,17]:
 nxt='GATE_SQUAD_NOT_%d'%cmd;c.eq(8,cmd,nxt);c.eq(17,1,nxt);c.go('GATE_DROP');c.label(nxt)
c.eq(8,10,'GATE_SQUAD_NOT_10');c.eq(17,1,'GATE_SQUAD_NOT_10');msg(c,'HCRBSY');c.go('GATE_DROP');c.label('GATE_SQUAD_NOT_10')   # the ropes are taken
# the rope is out for CJ (the rope worker sits in its ACTIVE loop - the cover team is on its way down or the rope hangs waiting - and the
# helicopter hovers frozen): every order is settled with the rope worker here, so the core never starts another approach under it, and
# the worker acts on it once the team has landed. 19@ = ESCORT_ON (1 = the men on the ground are the squad)
c.get(19,ROPE_WAIT);c.eq(19,1,'GATE_NO_WAIT');c.get(19,ESCORT_ON)
c.eq(8,10,'GW_NOT_10');c.set(ROPE_COMMAND,1);c.go('GATE_DROP');c.label('GW_NOT_10')                       # the rope order again = cancel
c.eq(8,17,'GW_NOT_17');c.eq(19,1,'GATE_DROP');c.set(ESCORT_CMD,2);c.go('GATE_DROP');c.label('GW_NOT_17')   # recall: the squad goes up these ropes
c.eq(8,16,'GW_NOT_16');c.eq(19,0,'GATE_DROP');c.set(ESCORT_CMD,1);c.go('GATE_DROP');c.label('GW_NOT_16')   # deploy: the cover team stays down as the squad
for cmd in [2,4,14]:   # the helicopter is sent elsewhere: a cover team climbs back first and the order follows; a squad simply carries on
 nxt='GW_NOT_%d'%cmd;c.eq(8,cmd,nxt);c.eq(19,0,'GATE_NO_WAIT');c.set(AFTER_ROPE,cmd);c.set(ROPE_COMMAND,1);c.go('GATE_DROP');c.label(nxt)
c.label('GATE_NO_WAIT')
# any other rope work (CJ on the rope, a team going down or up): nothing interrupts it, the pilot says so
c.get(19,ROPE_BUSY);c.eq(19,1,'GATE_ROPE_FREE')
for cmd in GATE_ROPE_ORDERS:
 nxt='GATE_ROPE_NOT_%d'%cmd;c.eq(8,cmd,nxt);msg(c,'HCRBSY');c.go('GATE_DROP');c.label(nxt)
c.label('GATE_ROPE_FREE')
# the rope order pressed again on the way in = cancel: the helicopter goes back to following
c.eq(8,10,'GATE_NOT_ROPE');c.eq(7,19,'GATE_NOT_ROPE');msg(c,'HCRCAN');a(6,V(8),I(2));c.label('GATE_NOT_ROPE')
# the exit button pressed again while the exit it asked for is already under way: the rope drop is ordered / is being retried over the spot (23), or
# the helicopter is on its way to the place where CJ gets out (it used to restart: every press pushed the stopping point further on)
c.eq(8,15,'GATE_NOT_EXIT');c.get(19,DROP_COMMAND);c.eq(19,0,'GATE_DROP')
c.eq(7,23,'GATE_EXIT_FLY');c.get(19,ROPE_PENDING);c.eq(19,0,'GATE_DROP');c.go('GATE_NOT_EXIT')
c.label('GATE_EXIT_FLY');c.get(19,AUTO_EXIT);c.eq(19,0,'GATE_EXIT_AUTO');c.go('GATE_NOT_EXIT')
c.label('GATE_EXIT_AUTO')
for st in MAP_FLIGHT_STATES:
 nxt='GATE_EXIT_NOT_%d'%st;c.eq(7,st,nxt);c.go('GATE_DROP');c.label(nxt)
c.label('GATE_NOT_EXIT')
for cmd in [2,3,4,14]:        # another order ends an approach for the squad
 nxt='GATE_KEEP_PENDING_%d'%cmd;c.eq(8,cmd,nxt);c.set(ESCORT_PENDING,0);c.label(nxt)
c.go('GATE_PASS')
c.label('GATE_DROP');a(6,V(8),I(0))
c.label('GATE_PASS')
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
c.get(19,FOLLOW_NEXT);c.check(0x001d,[V(20),V(19)],'TICK');a(0x0085,V(19),V(20));a(0x000a,V(19),I(4000));a(0xddc,I(FOLLOW_NEXT),V(19));a(0x07bb,V(5),I(6));a(0x0726,V(5),V(18),I(-1),F(15));a(0x00ad,V(5),F(40));c.go('TICK')
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
a(0x0574,V(5),I(1));c.set(FROZEN,1);a(0x00ab,V(5),V(9),V(10),V(11));a(0xddc,I(CR_CMDZ),V(11));a(0x00aa,V(5),V(17),V(19),V(31));a(0x0063,V(31),V(11));a(0xddc,I(GLIDE_C),V(31));a(0xddc,I(CRUISE_T),V(20))   # 1.2: the glide clock starts now (a stale one made the first step 3x too long)
a(0x0407,V(5),F(0),F(ROPE_PICKUP_AHEAD),F(0),V(17),V(19),V(31));a(0x0063,V(17),V(9));a(0x0063,V(19),V(10));a(0x00a0,V(18),V(26),V(27),V(31));a(0x005b,V(26),V(17));a(0x005b,V(27),V(19))
c.label('ROPE_GLIDE');c.call('CR_TIME');a(0x00aa,V(5),V(9),V(10),V(11))
a(0x0087,V(17),V(26));a(0x0063,V(17),V(9));a(0x0087,V(29),V(27));a(0x0063,V(29),V(10));a(0x0087,V(30),V(28));a(0x000b,V(30),F(15));a(0x0063,V(30),V(11))
a(0x050a,F(0),F(0),F(0),V(17),V(29),V(30),V(31));c.check(0x0021,[V(31),F(.4)],'ROPE_ARRIVE')
# 1.2: time-based with easing (it was a fixed 0.8 m per frame: 24 m/s at 30 fps, 48 m/s at 60 fps, and a hard stop):
# speed = 1.2 * distance + 1 m/s, at most 25 m/s, step = speed * frame time
a(0x0087,V(19),V(31));a(0x0013,V(19),F(1.2));a(0x000b,V(19),F(1.0));c.check(0x0021,[V(19),F(25)],'GL_SP_OK');a(0x0007,V(19),F(25));c.label('GL_SP_OK')
c.get(8,CR_DT);a(0x006b,V(19),V(8));a(0x0073,V(19),V(31));c.check(0x0021,[V(19),F(1.0)],'GL_SC_OK');a(0x0007,V(19),F(1.0));c.label('GL_SC_OK')
a(0x006b,V(17),V(19));a(0x006b,V(29),V(19));a(0x006b,V(30),V(19))
a(0x005b,V(9),V(17));a(0x005b,V(10),V(29));c.get(11,CR_CMDZ);a(0x005b,V(11),V(30));a(0xddc,I(CR_CMDZ),V(11));a(0x00ab,V(5),V(9),V(10),V(11));c.go('TICK')
c.label('ROPE_ARRIVE');a(0x0087,V(19),V(28));a(0x000b,V(19),F(15));a(0x0063,V(19),V(11));c.get(11,CR_CMDZ);a(0x005b,V(11),V(19));a(0xddc,I(CR_CMDZ),V(11));a(0x00ab,V(5),V(26),V(27),V(11))
c.call('BLOCK_HOVER');a(0x0574,V(5),I(1));c.set(FROZEN,1);c.set(NOTICE_SKIP,3);state(c,3);c.get(19,ESCORT_PENDING);c.eq(19,0,'ARRIVE_ESCORT');c.set(ROPE_COMMAND,1);c.go('TICK')
c.label('ARRIVE_ESCORT')
# 1.2: a recall for a team that died or was stood down on the way is dropped (the helicopter must not hover frozen waiting for it)
c.eq(19,2,'ARRIVE_GO');c.get(17,ESCORT_ON);c.eq(17,1,'ARRIVE_TEAM_GONE')
c.label('ARRIVE_GO');a(0xddc,I(ESCORT_CMD),V(19));c.set(ESCORT_PENDING,0);c.go('TICK')
c.label('ARRIVE_TEAM_GONE');c.set(ESCORT_PENDING,0);c.set(CMD,2);c.go('TICK')
# v40 TEAM ON FOOT: deploy the four-man escort by rope next to CJ, or recall it the same way.
c.label('REQUEST_TEAM_DEPLOY');c.get(19,ESCORT_ON);c.eq(19,0,'TEAM_BUSY');c.check(0x80db,[V(18),V(5)],'ROPE_CJ_ABOARD');c.check(0x80df,[V(18)],'TEAM_CJ_IN_CAR');c.eq(24,1,'TEAM_DEPLOY_CREW');msg(c,'SQCREW');c.go('TICK')
c.label('TEAM_DEPLOY_CREW');c.set(ESCORT_PENDING,1);c.eq(24,0,'TEAM_MUSTER');c.go('ROPE_HOVER')
c.label('TEAM_MUSTER');a(6,V(25),I(18));c.go('START_MUSTER')
c.label('TEAM_BUSY');msg(c,'SQALR');c.go('TICK')
# 17@ = 1 while a squad deployment or recall is under way (approach for it, hand-over to the rope worker, the ropes themselves). Uses 19@.
c.label('SQUAD_MOVING');a(6,V(17),I(1));c.get(19,ESCORT_ON);c.eq(19,2,'SM_NOT_DOWN');c.ret();c.label('SM_NOT_DOWN');c.eq(19,3,'SM_NOT_UP');c.ret();c.label('SM_NOT_UP')
c.get(19,ESCORT_CMD);c.eq(19,0,'SM_RET');c.eq(7,19,'SM_NO');c.get(19,ESCORT_PENDING);c.eq(19,0,'SM_RET')
c.label('SM_NO');a(6,V(17),I(0));c.label('SM_RET');c.ret()
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
c.label('EMERGENCY')
# 1.2: look for a flat, clear spot (CHECK_SITE) first below the helicopter, then 25 m around; the first one that fits wins
for k,(ox,oy) in enumerate([(0,0),(25,0),(-25,0),(0,25),(0,-25)]):
 a(0x00aa,V(5),V(9),V(10),V(11));a(0x0087,V(26),V(9));a(0x000b,V(26),F(ox));a(0x0087,V(27),V(10));a(0x000b,V(27),F(oy));a(0x0087,V(28),V(11));a(0x000b,V(28),F(100));a(0x02ce,V(26),V(27),V(28),V(28))
 c.call('CHECK_SITE');c.eq(17,1,'EMERGENCY_NEXT_%d'%k);c.go('EMERGENCY_GO');c.label('EMERGENCY_NEXT_%d'%k)
a(0x00aa,V(5),V(26),V(27),V(28));a(0x000b,V(28),F(100));a(0x02ce,V(26),V(27),V(28),V(28))
c.label('EMERGENCY_GO');state(c,15)
c.label('ISSUE_LANDING');c.set(LAND_STABLE,0);c.set(LAND_SLOW,0);c.set(LAND_FINAL,0);c.call('SET_LANDING_MISSION');a(0x01bd,V(21));c.go('TICK')
c.label('LANDING_TICK');a(0x00aa,V(5),V(9),V(10),V(11));a(0x0509,V(9),V(10),V(26),V(27),V(31));c.get(19,LAND_SLOW);c.eq(19,0,'LAND_CHECK_FINAL');c.check(0x0023,[F(45),V(31)],'LAND_CHECK_FINAL');c.set(LAND_SLOW,1);a(0x00ad,V(5),F(14))
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
c.label('REQUEST_MAP');c.check(0x0448,[V(18),V(5)],'NOT_ABOARD');c.get(19,GAME_OK);c.eq(19,1,'MAP_UNSUPPORTED')
if MAP_MARKER:c.call('READ_WAYPOINT');c.eq(29,1,'NO_MAP')
else:msg(c,'HCMAPOF');c.go('TICK')
# beta 4: the same marker while the flight to it is already under way: nothing to restart
c.get(19,AUTO_EXIT);c.eq(19,0,'MAP_NEW');a(6,V(19),I(0))
for st in MAP_FLIGHT_STATES:
 nxt='MAP_FLIGHT_NOT_%d'%st;c.eq(7,st,nxt);a(6,V(19),I(1));c.label(nxt)
c.eq(19,1,'MAP_NEW');c.get(9,DEST_X);c.get(10,DEST_Y);a(0x0509,V(9),V(10),V(26),V(27),V(31));c.check(0x0021,[V(31),F(10)],'TICK')
c.label('MAP_NEW');c.set(AVOID_STAGE,0);c.set(AUTO_EXIT,0);c.set(ROPE_PENDING,0)   # a new destination ends a rope drop that was still being retried
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
for var,x,y,seat in [(13,4,2,1),(14,-4,2,2),(15,4,-2,-1),(16,-4,-2,-1)]:   # 1.2: the side each guard is mounted on
 skip='MUSTER_DONE_'+str(var);alive(c,var,skip)
 c.check(0x8a32,[V(var)],skip)
 a(0x00a0,V(var),V(9),V(10),V(11));a(0x0407,V(5),F(x),F(y),F(0),V(17),V(19),V(31));a(0x050a,V(9),V(10),V(11),V(17),V(19),V(31),V(29))   # 1.2: distance to HIS muster point (the door side), not to the helicopter's centre
 c.check(0x0023,[F(3),V(29)],'MUSTER_WALK_'+str(var));c.go('MUSTER_BOARD_'+str(var))   # 1.2: attach only within 3 m (was 9 m: a visible snap)
 c.label('MUSTER_WALK_'+str(var));a(0x0085,V(17),V(20));a(0x0062,V(17),V(21));c.check(0x0019,[V(17),I(8000)],'MUSTER_WALK_TASK_'+str(var));c.check(0x0023,[F(25),V(29)],'MUSTER_FAR_'+str(var));c.check(0x82cb,[V(var)],'MUSTER_WALK_TASK_'+str(var));c.go('MUSTER_RECOVER_'+str(var))   # 1.2: warp only out of sight
 c.label('MUSTER_FAR_'+str(var));c.check(0x0019,[V(17),I(30000)],'MUSTER_OFFSCREEN_'+str(var));c.check(0x82cb,[V(var)],'MUSTER_WALK_TASK_'+str(var));c.go('MUSTER_RECOVER_'+str(var))
 c.label('MUSTER_OFFSCREEN_'+str(var));c.check(0x0019,[V(17),I(15000)],'MUSTER_WALK_TASK_'+str(var));c.check(0x82cb,[V(var)],'MUSTER_WALK_TASK_'+str(var))
 c.label('MUSTER_RECOVER_'+str(var));a(0x0407,V(5),F(x),F(y),F(5),V(9),V(10),V(11));a(0x02ce,V(9),V(10),V(11),V(11));a(0x000b,V(11),F(.7));a(0x0362,V(var),V(9),V(10),V(11));c.go('MUSTER_BOARD_'+str(var))
 c.label('MUSTER_WALK_TASK_'+str(var));a(6,V(30),I(0));a(0x0407,V(5),F(x),F(y),F(0),V(9),V(10),V(11));a(0x05d3,V(var),V(9),V(10),V(11),I(6),I(1000));c.go(skip)
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
c.label('GROVE');c.set(AUTO_EXIT,0);c.set(ROPE_PENDING,0);c.call('UNFREEZE');c.check(0x0448,[V(18),V(5)],'NOT_ABOARD');c.set(AVOID_STAGE,0);c.set(GROVE_STREAM,0);c.set(GROVE_WAIT,0);c.set(GROVE_NEXT_SCAN,0);a(0x01bd,V(21));state(c,10);c.go('TICK')
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
c.label('DEST_APPROACH_TICK');c.get(26,DEST_X);c.get(27,DEST_Y);c.get(28,DEST_Z);c.get(19,DEST_NATIVE);c.eq(19,0,'DEST_DESCEND');a(0x00aa,V(5),V(9),V(10),V(11));a(0x0509,V(9),V(10),V(26),V(27),V(31));c.check(0x0021,[V(31),F(4)],'DEST_DESCEND');c.set(CR_LAND,1);c.call('CRUISE_STEP');c.set(CR_LAND,0);c.go('TICK')   # 1.5.3: the brain's pilot comes down on the way in
# v37: the in-game freezes happened during the frozen, teleported descent next to roofs
# (DBG 2205). Now the scripted cruise only brings the helicopter exactly overhead at its safe
# altitude; then it is unfrozen, its residual speed zeroed, and the native pilot descends to
# 18 m with a 10 m reached distance (already overhead, so it does not circle).
c.label('DEST_DESCEND');c.set(DBG_CODE,5);c.get(19,DEST_NATIVE);c.eq(19,0,'DEST_NATIVE_WAIT')
c.call('UNFREEZE');a(0x04ba,V(5),F(0));a(0x07bb,V(5),I(0));a(0x0853,V(5),I(10));a(0x0087,V(9),V(28));a(0x000b,V(9),F(18));a(0x04df,V(5),I(0));a(0x04a2,V(5),V(26),V(27),V(9),F(10),V(9));a(0x00ad,V(5),F(22));c.set(DEST_NATIVE,1);a(0x01bd,V(21));c.go('TICK')
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
c.label('DEPART_START');c.call('UNFREEZE');c.call('RESTORE_FLIGHT');a(0x0918,V(5),I(1));a(0x0825,V(5));a(0x04df,V(5),I(0))
# 1.2: it flies off AWAY from CJ (the old target was 1500 m along its own heading, which could lead over his head),
# fast, and is only removed once it is out of sight and 200 m away
a(0x00aa,V(5),V(26),V(27),V(28));a(0x00a0,V(18),V(9),V(10),V(11));a(0x0509,V(9),V(10),V(26),V(27),V(31));c.check(0x0021,[V(31),F(3)],'DEPART_AHEAD')
a(0x0087,V(29),V(26));a(0x0063,V(29),V(9));a(0x0073,V(29),V(31));a(0x0013,V(29),F(1500));a(0x0087,V(30),V(27));a(0x0063,V(30),V(10));a(0x0073,V(30),V(31));a(0x0013,V(30),F(1500));a(0x005b,V(9),V(29));a(0x005b,V(10),V(30));a(0x0087,V(11),V(28));a(0x000b,V(11),F(40));c.go('DEPART_FLY')
c.label('DEPART_AHEAD');a(0x0407,V(5),F(0),F(1500),F(60),V(9),V(10),V(11))
c.label('DEPART_FLY');a(0x04a2,V(5),V(9),V(10),V(11),F(30),F(120));a(0x00ad,V(5),F(40));a(0x01bd,V(21))
c.label('DEPART_TICK');a(1,I(100));a(0x01bd,V(20));a(0xddc,I(HEART),V(20));c.set(CMD,0);healthcheck(c,'CLEANUP');c.call('RESOLVE_LANG');c.call('CHANGE_MODEL');c.call('CHANGE_CREW');c.call('PUBLISH');a(0x0227,V(5),V(6));a(0xddc,I(HP),V(6));c.get(19,FIRE);c.check(0x003b,[V(19),V(23)],'DEPART_FIRE_CHANGE');c.go('DEPART_HEALTH_DONE')
c.label('DEPART_FIRE_CHANGE');c.call('APPLY_FIRE')
c.label('DEPART_HEALTH_DONE');a(0x0085,V(17),V(20));a(0x0062,V(17),V(21));c.check(0x0019,[V(17),I(60000)],'DEPART_DISTANCE');c.go('DEPART_RELEASE')
c.label('DEPART_DISTANCE');c.check(0x0019,[V(17),I(3000)],'DEPART_TICK');c.check(0x80db,[V(18),V(5)],'DEPART_TICK')
# 1.2: never removed in view (v28 deleted it after 12 s even on screen): only out of sight AND 200 m away;
# a helicopter that cannot get away in 60 s is released instead of deleted
c.check(0x82ca,[V(5)],'DEPART_TICK');a(0x00a0,V(18),V(9),V(10),V(11));a(0x00aa,V(5),V(26),V(27),V(28));a(0x050a,V(9),V(10),V(11),V(26),V(27),V(28),V(19));c.check(0x0021,[V(19),F(200)],'DEPART_TICK')
c.label('DEPART_DELETE');a(0x0164,V(12))
for var in [13,14,15,16,4]:
 skip='DELETE_SKIP_'+str(var);c.check(0x056d,[V(var)],skip);a(0x009b,V(var));c.label(skip)
a(0x00a6,V(5));c.go('RESET')
c.label('DEPART_RELEASE');c.call('UNFREEZE');a(0x0164,V(12))
for var in [4,13,14,15,16]:
 skip='DEPART_RELEASE_SKIP_'+str(var);c.check(0x056d,[V(var)],skip);a(0x01c2,V(var));c.label(skip)
c.check(0x056e,[V(5)],'RESET');a(0x01c3,V(5));c.go('RESET')
c.label('CLEANUP');c.call('UNFREEZE');a(0x0164,V(12))
for var in [4,13,14,15,16]:
 skip='RELEASE_SKIP_'+str(var);c.check(0x056d,[V(var)],skip)
 # 1.2: a living pilot who is still in his helicopter is not thrown out of it (that dropped a pilotless helicopter)
 if var==4:c.check(0x056e,[V(5)],'CLEANUP_EJECT');c.check(0x00db,[V(4),V(5)],'CLEANUP_EJECT');c.go('CLEANUP_KEEP');c.label('CLEANUP_EJECT')
 a(0x0792,V(var))
 if var==4:c.label('CLEANUP_KEEP')
 a(0x048f,V(var));a(0x01c2,V(var));c.label(skip)
c.check(0x056e,[V(5)],'RESET');a(0x01c3,V(5))
c.label('RESET');c.set(FROZEN,0);c.set(COMBAT_PILOT,0);c.set(CR_LAND,0);c.set(LSTAGE,0);c.set(BUSY,0);state(c,0)
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
emit_resolve_lang(c,GAME_OK)
# 1.2: every gunner holds the chosen weapon the moment he exists (it used to be the next Fire pass, 0.15-0.9 s of unarmed gunners)
c.label('ARM_CREW');c.get(19,WPN);c.check(0x0019,[V(19),I(0)],'ARM_CREW_RET')
for var in [13,14,15,16]:
 skip='ARM_CREW_SKIP_'+str(var);alive(c,var,skip);a(0x0470,V(var),V(17));c.check(0x803b,[V(17),V(19)],skip);a(0x01b2,V(var),V(19),I(30000));a(0x01b9,V(var),V(19));a(0x02e2,V(var),I(100));a(0x07dd,V(var),I(100));c.label(skip)
c.label('ARM_CREW_RET');c.ret()
c.label('CHANGE_POSE');c.get(19,POSE);c.get(17,POSE_DONE);c.check(0x003b,[V(19),V(17)],'CHANGE_POSE_GO');c.ret()
c.label('CHANGE_POSE_GO');a(0xddc,I(POSE_DONE),V(19));c.call('RESEAT_MOUNTED');c.call('ARM_CREW');c.ret()   # (the attach strips the weapons)
# 1.4.1: the brain changes the gunners' pose in flight: only the men who are in their doors are re-seated (a crewman who has got
# out after a landing stays on his feet)
c.label('RESEAT_MOUNTED')
for var in (13,14,15,16):
 skip='RESEAT_SKIP_'+str(var);alive(c,var,skip);c.check(0x0a32,[V(var)],skip);c.call('ATTACH_'+str(var));c.label(skip)
c.ret()
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
 # 1.4: SITTING on the skid - lower and a little further out, crouched: his seat on the skid, his legs down past it, the weapon
 # out of the door (SETTINGS: GUNNERS SITTING / KNEELING / STANDING)
 c.label('ATTACH_POS_'+str(var));c.get(17,POSE);c.eq(17,2,'ATTACH_PLACE_'+str(var));a(0x000b,V(11),F(-SEAT_DROP));a(0x000b,V(9),F(SEAT_OUT if x>0 else -SEAT_OUT))
 c.label('ATTACH_PLACE_'+str(var));a(0x0792,V(var));a(0x048f,V(var));a(0x04eb,V(var),I(0));a(0x0464,V(var),V(5),V(9),V(10),V(11),I(direction),F(190),I(0))
 # beta 6: a door gunner kneels on the skid instead of standing bolt upright (sitting is a crouch too)
 c.get(11,POSE);c.eq(11,0,'ATTACH_CROUCH_'+str(var));c.go('ATTACH_END_'+str(var));c.label('ATTACH_CROUCH_'+str(var));a(0x04eb,V(var),I(1));c.label('ATTACH_END_'+str(var));c.ret()
c.label('CHECK_SITE');a(6,V(17),I(0))
for dx,dy in [(0,0),(4,0),(-4,0),(0,4),(0,-4)]:
 # Sample local ground and reject steep edges; check low vehicles plus fixed overhead obstacles.
 a(0x0087,V(9),V(26));a(0x000b,V(9),F(dx));a(0x0087,V(10),V(27));a(0x000b,V(10),F(dy));a(0x0087,V(11),V(28));a(0x000b,V(11),F(20));a(0x02ce,V(9),V(10),V(11),V(31));a(0x0063,V(31),V(28));c.check(0x0023,[F(2),V(31)],'SITE_END');c.check(0x0021,[V(31),F(-2)],'SITE_END')
 a(0x0087,V(11),V(28));a(0x000b,V(11),F(.7));a(0x0087,V(29),V(28));a(0x000b,V(29),F(4));c.check(0x06bd,[V(9),V(10),V(11),V(9),V(10),V(29),I(1),I(1),I(0),I(1),I(0)],'SITE_END')
 a(0x0087,V(11),V(28));a(0x000b,V(11),F(4));a(0x0087,V(29),V(28));a(0x000b,V(29),F(22));c.check(0x06bd,[V(9),V(10),V(11),V(9),V(10),V(29),I(1),I(0),I(0),I(1),I(0)],'SITE_END')
a(6,V(17),I(1));c.label('SITE_END');c.ret()
c.label('DEPLOY');c.set(BUSY,1);a(6,V(24),I(1))
for var,x,y in [(13,3.5,2),(14,-3.5,2),(15,3.5,-2),(16,-3.5,-2)]:   # 1.2: the side they are mounted on (was mirrored: ~5 m through the fuselage)
 skip='DEPLOY_SKIP_'+str(var);alive(c,var,skip);a(0x0792,V(var));a(0x0465,V(var));a(0x0407,V(5),F(x),F(y),F(6),V(9),V(10),V(11));a(0x02ce,V(9),V(10),V(11),V(11));a(0x000b,V(11),F(1));a(0x0362,V(var),V(9),V(10),V(11));a(0x0619,V(var),I(1));a(0x083c,V(var),F(0),F(0),F(-.5));a(0x04eb,V(var),I(1));c.label(skip)
c.call('PUBLISH');c.set(BUSY,0);c.ret()
c.label('GUARD_TEAM')
for var,x,y in [(13,-5,4),(14,5,4),(15,-5,-4),(16,5,-4)]:
 skip='GUARD_SKIP_'+str(var);alive(c,var,skip);c.check(0x80df,[V(var)],skip);a(0x04c4,V(18),F(x),F(y),F(0),V(9),V(10),V(11));a(0x00a0,V(var),V(17),V(19),V(30));a(0x050a,V(9),V(10),V(11),V(17),V(19),V(30),V(30));c.check(0x0021,[V(30),F(2.5)],'GUARD_WATCH_'+str(var));a(0x05d3,V(var),V(9),V(10),V(11),I(4),I(1000));c.go(skip)
 c.label('GUARD_WATCH_'+str(var));a(0x04eb,V(var),I(1));c.label(skip)
c.ret()

# Only while FOLLOW CJ is active: if a selected nearby threat is too far from the
# helicopter, keep it in view. Never change landing, hold, muster or Grove missions.
# 1.5: the brain's OWN pilot in a fight. While the helicopter escorts CJ (state 2), CJ is not aboard and the brain gives a spot
# (HELI_SPOT: 20 m from CJ, 16 m up, abeam of the line to the threat) within 120 m, the helicopter is flown to it and held there
# by the brain's pilot, frame by frame (CRUISE_STEP with flag 4: the spot's height, short hops, side-on to the threat) - not by the
# game's pilot (04A2), who hung far and high and never turned a door to the target. When the spot is gone the helicopter is
# given back to the game's follow; when another state has taken over, only the flag is dropped (that state flies it).
c.label('TRACK_COMBAT');c.eq(7,2,'CP_OFF');c.get(30,BRAIN_HELLO);c.eq(30,BRAIN_MAGIC,'CP_OFF');c.get(30,HELI_SPOT_Z);c.check(0x0021,[V(30),F(1)],'CP_OFF');c.check(0x80db,[V(18),V(5)],'CP_OFF')
c.get(30,FIREHEART);a(0x0085,V(31),V(20));a(0x0062,V(31),V(30));c.check(0x8019,[V(31),I(2000)],'CP_OFF')   # (the spot is fresh: the Fire worker, which publishes it, is alive)
a(0x00aa,V(5),V(9),V(10),V(11));c.get(26,HELI_SPOT_X);c.get(27,HELI_SPOT_Y);a(0x0509,V(9),V(10),V(26),V(27),V(31));c.check(0x0023,[F(120),V(31)],'CP_OFF')
c.set(COMBAT_PILOT,1);c.set(TRACKED_TARGET,-2);c.call('CRUISE_STEP');c.ret()
c.label('CP_OFF');c.get(30,COMBAT_PILOT);c.eq(30,1,'TRACK_OLD');c.set(COMBAT_PILOT,0);c.eq(7,2,'TRACK_OLD')
c.call('UNFREEZE');c.set(TRACKED_TARGET,-1);c.call('RESTORE_FLIGHT');a(0x0726,V(5),V(18),I(-1),F(15))
c.label('TRACK_OLD');c.eq(7,2,'TRACK_PATROL');c.go('TRACK_ACTIVE');c.label('TRACK_PATROL');c.eq(7,24,'TRACK_INACTIVE');c.label('TRACK_ACTIVE');c.get(29,FIRE_TARGET);alive(c,29,'TRACK_STOP')
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
c.label('TRACK_GOTO');c.get(30,EVADE_UNTIL);c.check(0x001d,[V(30),V(20)],'TRACK_BRAIN')
a(0x0013,V(9),F(1.6));a(0x0013,V(10),F(1.6));a(0x0087,V(11),V(31));a(0x000b,V(11),F(40));c.go('TRACK_POS')   # (evading: wider and higher)
# 1.4.1: the brain's spot - 28 m from CJ on the far side from the threat, 24 m up, where the threat is seen from (the game's own
# line of sight, asked by the brain): the pilot goes there instead of round the orbit while it is given (z 0 = none)
c.label('TRACK_BRAIN');c.get(30,HELI_SPOT_Z);c.check(0x0021,[V(30),F(1)],'TRACK_NORMAL');c.get(9,HELI_SPOT_X);c.get(10,HELI_SPOT_Y);a(0x0087,V(11),V(30));c.go('TRACK_ISSUE')
c.label('TRACK_NORMAL');a(0x0087,V(11),V(31));a(0x000b,V(11),F(25));a(0x0087,V(8),V(31));a(0x0063,V(8),V(28));c.check(0x0021,[V(8),F(6)],'TRACK_POS');a(0x000b,V(11),F(15))
c.label('TRACK_POS');a(0x005b,V(9),V(26));a(0x005b,V(10),V(27))
# v40: an orbit point without a clear view of the threat is flown 15 m higher, and the next tick
# moves on to the following point (ORBIT_NEXT <= now + 1.2 s) until the gunners can see it.
a(0x0087,V(30),V(31));a(0x000b,V(30),F(1));c.check(0x06bd,[V(9),V(10),V(11),V(17),V(19),V(30),I(1),I(0),I(0),I(0),I(0)],'TRACK_BLOCKED');c.go('TRACK_ISSUE')
# v40.1: move on to the next point after 1.2 s at the earliest (v40 re-picked every 100 ms and the
# helicopter thrashed between points); only buildings count, not trees and other objects.
c.label('TRACK_BLOCKED');a(0x000b,V(11),F(15));c.get(30,ORBIT_NEXT);a(0x0085,V(8),V(20));a(0x000a,V(8),I(1200));c.check(0x001d,[V(30),V(8)],'TRACK_ISSUE');a(0xddc,I(ORBIT_NEXT),V(8))
# 1.4.3: the ceiling of the flight is the spot's own height (with 20 / 70 the game's pilot climbed to 70 m above the sea and
# hung there, far from the fight: the second whole-game log), and it goes there at speed
c.label('TRACK_ISSUE');a(0x07bb,V(5),I(0));a(0x04a2,V(5),V(9),V(10),V(11),F(12),V(11));a(0x00ad,V(5),F(32));a(0xddc,I(TRACKED_TARGET),V(29));c.ret()
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
# 1.2: the model is a decor choice and changes at once; the only wait is a rope motion in progress (the swap would drop CJ)
c.get(17,ROPE_BUSY);c.eq(17,0,'SWAP_DEFER');c.set(SWAP_MSG,0)
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
c.label('SWAP_DEFER');c.get(17,SWAP_MSG);c.eq(17,0,'SWAP_RETURN');c.set(SWAP_MSG,1);msg(c,'HCSLATE');c.ret()
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
c.label('RESUME_HOLD');c.get(19,FROZEN);c.eq(19,1,'RESUME_HOLD_FREE');a(0x0574,V(5),I(1));c.ret()   # 1.2: ropes out: the new helicopter hangs frozen on the old one's spot
c.label('RESUME_HOLD_FREE');c.call('BLOCK_HOVER');c.ret()
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
# 1.2: the native pilot climbs out (the old code teleported the helicopter 10-20 m up); the follow / patrol / orbit
# orders wait 6 s so they do not override the climb
a(0x04df,V(5),I(0));a(0x04a2,V(5),V(9),V(10),V(11),F(15),V(11));a(0x00ad,V(5),F(20));a(0x0085,V(19),V(20));a(0x000a,V(19),I(6000));a(0xddc,I(FOLLOW_NEXT),V(19));a(0xddc,I(ORBIT_NEXT),V(19));a(0xddc,I(PATROL_NEXT),V(19));c.set(STUCK_SINCE,0);c.ret()
c.label('UNSTICK_RESET');c.set(STUCK_SINCE,0)
c.label('UNSTICK_WAIT');c.ret()
# 1.4: the brain's pilot flies the helicopter to (26@,27@) (command 6 of 0E48, brain/core/hcb_pilot.c): nose down to speed up,
# banked into turns, a safe height over the roofs ahead, braking in good time with the nose up, stopping over the point.
# The script measures the roofs (02CE) under the helicopter and 30/80/150/250 m on the way, moves it to the point the
# pilot gives (00AB, never through anything solid: a blocked step is refused and the pilot stops and climbs) and the
# brain turns it (pitch, bank and heading, written after the scripts have run). Returns 19@ = metres left (flat);
# 26@/27@ are kept.
c.label('GLIDE_BEGIN');a(0x00aa,V(5),V(9),V(10),V(11));a(0x02e3,V(5),V(30));a(0x0574,V(5),I(1));c.set(FROZEN,1);a(0x00ab,V(5),V(9),V(10),V(11));a(0xddc,I(CR_CMDZ),V(11));a(0x00aa,V(5),V(17),V(29),V(31));a(0x0063,V(31),V(11));a(0xddc,I(GLIDE_C),V(31));a(0xddc,I(CRUISE_T),V(20));c.check(0x0021,[V(30),F(CRUISE_SPEED)],'GB_SPEED_OK');a(0x0007,V(30),F(CRUISE_SPEED));c.label('GB_SPEED_OK');c.set(CR_BLK,0);a(0xddc,I(CR_V),V(30));c.ret()   # 1.2: continues at the real speed (was restarted from 0 = a dead stop)
c.label('CR_TIME');c.get(29,CRUISE_T);a(0x0085,V(30),V(20));a(0x0062,V(30),V(29));a(0xddc,I(CRUISE_T),V(20))
c.check(0x0019,[V(30),I(100)],'CRT_HI');a(6,V(30),I(100));c.label('CRT_HI');c.check(0x0019,[V(30),I(0)],'CRT_LOW');c.go('CRT_OK');c.label('CRT_LOW');a(6,V(30),I(16));c.label('CRT_OK')
a(0x0093,V(31),V(30));a(0x0013,V(31),F(.001));a(0xddc,I(CR_DT),V(31));c.ret()
c.label('CRUISE_STEP');c.get(19,FROZEN);c.eq(19,1,'CR_BEGIN');c.go('CR_RUN');c.label('CR_BEGIN');c.call('GLIDE_BEGIN')
c.label('CR_RUN');c.set(DBG_CODE,1);a(0x00aa,V(5),V(9),V(10),V(11));a(0xddc,I(CR_DX),V(26));a(0xddc,I(CR_DY),V(27))
# the roofs: the highest surface under the helicopter and on the way to the point (29@)
a(0x02ce,V(9),V(10),F(1000),V(29));a(0x0087,V(17),V(26));a(0x0063,V(17),V(9));a(0x0087,V(30),V(27));a(0x0063,V(30),V(10));a(0x0509,F(0),F(0),V(17),V(30),V(19))
c.check(0x0021,[V(19),F(1)],'CR_ROOFS_DONE');a(0x0073,V(17),V(19));a(0x0073,V(30),V(19))
for ahead in [30,80,150,250]:
 nxt='CR_ROOF_'+str(ahead);c.check(0x0021,[V(19),F(ahead-12)],'CR_ROOFS_DONE')   # 1.5.2: not beyond the point (a tower 250 m on, behind a spot 30 m away, sent it up to 90 m: the fourth log)
 a(0x0087,V(28),V(17));a(0x0013,V(28),F(ahead));a(0x005b,V(28),V(9));a(0x0087,V(31),V(30));a(0x0013,V(31),F(ahead));a(0x005b,V(31),V(10))
 a(0x02ce,V(28),V(31),F(1000),V(28));c.check(0x0025,[V(28),V(29)],nxt);a(0x0087,V(29),V(28));c.label(nxt)
c.label('CR_ROOFS_DONE')
# ask the pilot: 26@ helicopter, 27/28@ the point, 29@ the roofs, 30@ 1 = stop there (+2: the last step was refused) ->
# 27-29@ where to be now, 30@ metres left, 31@ speed (-1: the brain has no pilot for this helicopter)
a(0x0087,V(28),V(27));a(0x0087,V(27),V(26));a(0x0085,V(26),V(5));c.get(30,CR_BLK);a(0x0012,V(30),I(2));a(0x000a,V(30),I(1));c.get(31,COMBAT_PILOT);a(0x0012,V(31),I(4));a(0x005a,V(30),V(31));c.get(31,CR_LAND);a(0x0012,V(31),I(8));a(0x005a,V(30),V(31))   # (+4: on station in a fight, +8: a landing approach)
c.get(31,BRAIN_HELLO);c.check(0x0039,[V(31),I(BRAIN_MAGIC)],'CR_NO_PILOT');a(6,V(31),I(-1));a(0x0e48,V(26),I(6),I(6))   # (31@ stays -1 when the brain does not answer)
c.check(0x0039,[V(31),I(-1)],'CR_FLY')
c.label('CR_NO_PILOT');c.get(26,CR_DX);c.get(27,CR_DY);a(0x0509,V(9),V(10),V(26),V(27),V(19));c.ret()   # (no brain: the helicopter hangs where it is)
c.label('CR_FLY');a(0xddc,I(CR_V),V(31));a(0x0087,V(19),V(30))
c.check(0x06bd,[V(9),V(10),V(11),V(27),V(28),V(29),I(1),I(0),I(0),I(1),I(0)],'CR_BLOCKED');c.go('CR_MOVE')
c.label('CR_BLOCKED');c.set(CR_BLK,1);c.get(17,CR_CMDZ);c.check(0x0025,[V(17),V(29)],'CR_UP');a(0x0087,V(29),V(17));c.label('CR_UP')   # only straight up (the pilot climbs from the next frame on)
c.check(0x0023,[F(2000),V(29)],'CR_BAD_POS');a(0xddc,I(CR_CMDZ),V(29));a(0x00ab,V(5),V(9),V(10),V(29));c.get(26,CR_DX);c.get(27,CR_DY);c.ret()
c.label('CR_MOVE');c.set(CR_BLK,0);c.set(DBG_CODE,2)
for v,lo,hi in [(27,-3500,3500),(28,-3500,3500),(29,-200,2000)]:c.check(0x0021,[V(v),F(lo)],'CR_BAD_POS');c.check(0x0023,[F(hi),V(v)],'CR_BAD_POS')
a(0xddc,I(CR_CMDZ),V(29));a(0x00ab,V(5),V(27),V(28),V(29));c.get(26,CR_DX);c.get(27,CR_DY);c.ret()
c.label('CR_BAD_POS');c.set(DBG_CODE,99);c.get(26,CR_DX);c.get(27,CR_DY);c.ret()
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
c.label('EXIT_ROPE_NOW');a(0x02e3,V(5),V(19));c.get(17,FROZEN);c.eq(17,1,'EXR_SPD');c.get(17,CR_V);c.check(0x8025,[V(19),V(17)],'EXR_SPD');a(0x0087,V(19),V(17));c.label('EXR_SPD')
c.check(0x0021,[V(19),F(8)],'EXIT_ROPE_SLOW');c.go('EXIT_HERE')   # 1.2: faster than 8 m/s: slow down along the way first (no dead stop), the rope follows on arrival
c.label('EXIT_ROPE_SLOW');a(0x00aa,V(5),V(9),V(10),V(11));a(0x0574,V(5),I(1));c.set(FROZEN,1);a(0x04ba,V(5),F(0));a(0x02ce,V(9),V(10),V(11),V(28))
a(0xddc,I(DEST_X),V(9));a(0xddc,I(DEST_Y),V(10));a(0xddc,I(DEST_Z),V(28));c.set(AUTO_EXIT,0);c.set(DEST_NATIVE,0);state(c,23);a(6,V(7),I(23));c.go('REQUEST_DEST_ROPE')
c.label('EXIT_NOT_ROPE_NOW')
c.eq(7,22,'EXIT_HERE');c.set(AUTO_EXIT,1);msg(c,'HCXARR');c.go('TICK')
c.label('EXIT_HERE');a(0x00aa,V(5),V(9),V(10),V(11))
# 1.2: a moving helicopter is not stopped dead on the spot: its destination is a point ahead (speed + 10 m, at most 100 m) where the
# scripted cruise slows it down smoothly; the exit follows on arrival (AUTO_EXIT). A frozen, script-flown helicopter reports no speed, so CR_V counts.
a(0x02e3,V(5),V(19));c.get(17,FROZEN);c.eq(17,1,'EXH_SPD');c.get(17,CR_V);c.check(0x8025,[V(19),V(17)],'EXH_SPD');a(0x0087,V(19),V(17));c.label('EXH_SPD')
c.check(0x0021,[V(19),F(8)],'EXH_AT');a(0x000b,V(19),F(10));c.check(0x0021,[V(19),F(100)],'EXH_D');a(0x0007,V(19),F(100));c.label('EXH_D');a(0x0407,V(5),F(0),V(19),F(0),V(9),V(10),V(17))
c.label('EXH_AT');a(0x02ce,V(9),V(10),F(1000),V(28));a(0xddc,I(DEST_X),V(9));a(0xddc,I(DEST_Y),V(10));a(0xddc,I(DEST_Z),V(28));c.set(GROVE_WAIT,0);c.set(GROVE_NEXT_SCAN,0);c.set(AVOID_STAGE,0);c.set(AUTO_EXIT,1);c.call('EXIT_UNFREEZE');a(0x01bd,V(21));state(c,21);msg(c,'HCXHERE');c.go('TICK')
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
c.label('LAND_APPROACH_MISSION');a(0x0087,V(17),V(28));a(0x000b,V(17),F(6));a(0x0743,V(5),V(26),V(27),V(28),F(6),V(17));c.get(19,LAND_SLOW);c.eq(19,1,'LAND_SPEED_FAST');a(0x00ad,V(5),F(14));c.ret()
c.label('LAND_SPEED_FAST');a(0x00ad,V(5),F(25));c.ret()
c.label('SET_FINAL_LANDING');a(0x0743,V(5),V(26),V(27),V(28),F(0),F(0));a(0x00ad,V(5),F(14));c.ret()

c.label('UNFREEZE');c.check(0x056e,[V(5)],'UNFREEZE_DONE');a(0x0574,V(5),I(0))
c.label('UNFREEZE_DONE');c.set(FROZEN,0);c.set(CR_V,0);c.ret()   # 1.2: no stale cruise speed for the next exit
# 1.2: a helicopter the script is flying (frozen, cruising to Grove / the map point) must not be released for an exit request: the cruise
# gets its new destination and brakes smoothly (releasing it restarted the cruise from a standstill = a dead stop)
c.label('EXIT_UNFREEZE');c.get(17,FROZEN);c.eq(17,1,'EXU_DO');c.eq(7,10,'EXU_N21');c.ret()
c.label('EXU_N21');c.eq(7,21,'EXU_DO');c.ret()
c.label('EXU_DO');c.call('UNFREEZE');c.ret()
c.label('CHANGE_CREW');c.get(29,CREW);c.get(30,ACREW);c.check(0x803b,[V(29),V(30)],'CREW_RETURN')
# 1.2: same rule as the model: only a rope motion in progress makes the change wait (the rope workers abort when the state is 17)
c.get(17,ROPE_BUSY);c.eq(17,0,'SWAP_DEFER')
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
 a(0x077a,V(29),I(0),I(0));a(0x077a,V(29),I(0),I(8));brave(c,29,'BRAVE_NEW_%d'%var);c.label(skip)
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
a(0xddc,I(STATE),V(7));c.call('PUBLISH');c.call('ARM_CREW');c.get(19,CREWGEN);a(0x000a,V(19),I(1));a(0xddc,I(CREWGEN),V(19));c.call('RESUME_FLIGHT');c.set(BUSY,0);msg(c,'HCCREW');c.ret()
c.label('CREW_ROLLBACK')
for index in range(5):
 skip='CREW_ROLLBACK_SKIP_'+str(index);c.get(29,CREWNEW+index);c.check(0x056d,[V(29)],skip);a(0x009b,V(29));c.label(skip)
for var in [1,2,3]:a(0x0249,V(var))
for index,var in enumerate([1,2,3]):c.get(var,SKINSAVE+index)
a(0xddc,I(STATE),V(7));c.set(BUSY,0);msg(c,'HCCFAIL')
c.label('CREW_REJECT');c.get(19,ACREW);a(0xddc,I(CREW),V(19))
c.label('CREW_RETURN');c.ret()

PANEL_FRESH_MS=1000;CORE_FRESH_MS=1500;PANEL_PROOF_MS=650;CORE_PROOF_MS=250   # beta 5: a heartbeat (game time stamp) younger than FRESH = the script is running, no waiting; otherwise it has to change within PROOF ms
p=Script();a=p.add
MENU_GUARD_MS=350;MENU_REPEAT_MS=1000   # beta 4 tap guard: after a tap or a page change / the same main-page row again
import i18n_v12 as i18n
p.label('INIT');a(0);a(6,V(10),I(0));a(6,V(16),I(0));a(6,V(25),I(-1));a(6,V(26),I(0));a(6,V(17),I(-999));p.set(DISMISS_T,0)
p.label('WATCH');a(1,I(0));a(0x01bd,V(20));a(0xddc,I(PANELHEART),V(20));p.call('DISMISS_TICK');p.get(0,0);p.eq(0,0,'WATCH');p.check(0x0256,[I(0)],'WATCH')
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
p.label('ACQUIRE');p.get(0,0);p.eq(0,0,'WATCH');p.set(OPEN,0);p.set(0,1);a(6,V(10),I(0));a(6,V(25),I(-1));p.get(13,HEART);p.eq(13,0,'CORE_SEEN');p.go('CORE_SLOW')
p.label('CORE_SEEN');a(0x01bd,V(14));a(0x0062,V(14),V(13));p.check(0x8019,[V(14),I(CORE_FRESH_MS)],'CORE_SLOW');p.check(0x0019,[V(14),I(-1)],'CORE_SLOW')   # beta 5: no 250 ms pause - the core's heartbeat is a time stamp
p.label('CORE_OK');a(6,V(2),I(0));a(6,V(3),I(-999));p.go('REFRESH')
# a stale stamp (or one from 'the future' after a loaded save): the old proof of life - it has to change within 250 ms
p.label('CORE_SLOW');a(0x01bd,V(29));a(0x000a,V(29),I(CORE_PROOF_MS))
p.label('CORE_SLOW_LOOP');a(1,I(0));p.get(14,HEART);p.check(0x003b,[V(14),V(13)],'CORE_OK');a(0x01bd,V(14));p.check(0x001d,[V(14),V(29)],'CORE_SLOW_LOOP');p.go('CORE_MISSING')
p.label('MENU_POLL');a(1,I(0));a(0x01bd,V(20));a(0xddc,I(PANELHEART),V(20));p.call('DISMISS_TICK');p.check(0x0256,[I(0)],'CLOSE');a(0x0df4,V(1),I(250));p.eq(1,-2,'PICK');p.go('CLOSE')
p.label('PICK');p.eq(1,-1,'HAS_PICK');p.go('CHECK_MENU_STATUS')
# beta 4, every page: nothing is accepted for 0.35 s after a tap was taken or the page changed (16@). A double tap on "CREW >" used to
# open the page AND pick its first row; a tap already on its way when the squad landed used to hit the row that replaced the old one.
# Main page only: a row that is being hammered (25@ = the row tapped last, 26@ = when, counted for every tap - taken or not) is taken
# once; the next tap on it counts after a second's pause. So CANCEL does not turn back into the order it cancelled, and a squad that
# has just landed is not sent back up by the same burst of taps on "SQUAD ROPING DOWN...". 28@ = 1: this tap is such a repeat.
p.label('HAS_PICK');a(0x01bd,V(18));a(6,V(28),I(0));p.eq(2,0,'HP_GUARD')
p.check(0x003b,[V(1),V(25)],'HP_NEW_ROW');a(0x0085,V(27),V(18));a(0x0062,V(27),V(26));a(0x0085,V(26),V(18));p.check(0x8019,[V(27),I(MENU_REPEAT_MS)],'HP_GUARD');a(6,V(28),I(1));p.go('HP_GUARD')
p.label('HP_NEW_ROW');a(0x0085,V(25),V(1));a(0x0085,V(26),V(18))
p.label('HP_GUARD');a(0x0085,V(27),V(18));a(0x0062,V(27),V(16));p.check(0x0019,[V(27),I(MENU_GUARD_MS)],'CHECK_MENU_STATUS');p.eq(28,0,'CHECK_MENU_STATUS');a(0x0085,V(16),V(18));p.get(8,STATE)
# 1.2 menu: every row is ONE action and a mode is marked [X] instead of "cycling blind". The main page follows the situation - no
# helicopter, busy, CJ on foot or CJ aboard - and its title shows what the helicopter is doing. The CLEO menu has its own CLOSE.
# Pages (local 2): 0 main, 1 gunner fire, 2 settings, 3 crew, 4 helicopter model, 5 crew weapon, 6 dismiss confirm.
# Local 3 = key of the drawn page (redrawn when it changes), 7 = situation of the drawn main page, 9 = language scratch.
# Beta 4: an operation that is under way is shown instead of the button that started it (SQUAD ROPING DOWN..., CANCEL ROPE PICKUP),
# so nothing can be started twice; the two EXIT BUTTON rows only switch what the game's exit button does.
NONE_STATES=[0,5,6];BUSY_STATES=[1,4,13,16,17]
GROUND_STATES=[st for st in STATES if st not in NONE_STATES+BUSY_STATES]
PROFILES=('en','game');SUFFIX=('','_U')
FIRE_VALUES=[3,4,2,0];CREW_VALUES=[0,1,2];MODEL_VALUES=[487,497,425];WEAPON_VALUES=[0,29,30,31,34]
MAP_STATES=(25,21,22);GROVE_STATES=(20,10,11)
def Tx(key,prof,mark=False):return i18n.menu_text(key,prof)+(i18n.MARK.encode('ascii') if mark else b'')
def main_rows(st,sit,x,prof='en'):
 """sit 0 no helicopter, 1 busy, 2 CJ on foot (x = team phase * 2 + rope phase), 3 CJ aboard (x = exit mode + 2 * exit under way)."""
 if sit==0:return [Tx('CALL',prof),Tx('SETTINGS',prof)]
 if sit==1:return [Tx({1:'WAIT_IN',4:'WAIT_OUT',13:'WAIT_OUT'}.get(st,'WAIT_SWAP'),prof),Tx('GUNFIRE',prof),Tx('SETTINGS',prof)]
 if sit==2:
  team,rope=divmod(x,2)
  return [Tx('FOLLOW',prof,st==2),Tx('HOLD',prof,st==3 and not rope),Tx('PATROL',prof,st==24),Tx('GUNFIRE',prof),Tx('ROPE_CANCEL' if rope else 'ROPE',prof),
          Tx(('TEAM_ON','TEAM_OFF','TEAM_DOWN','TEAM_UP')[team],prof),Tx('SETTINGS',prof),Tx('DISMISS',prof)]
 mode,exiting=x%2,x//2
 return [Tx('MAP',prof,st in MAP_STATES and not exiting),Tx('GROVE',prof,st in GROVE_STATES),Tx('EXIT_LAND',prof,mode==0),Tx('EXIT_ROPE',prof,mode==1),Tx('GUNFIRE',prof),Tx('SETTINGS',prof)]
MAIN_VARIANTS=[(st,0,0) for st in NONE_STATES]+[(st,1,0) for st in BUSY_STATES]+[(st,2,x) for st in GROUND_STATES for x in range(8)]+[(st,3,x) for st in GROUND_STATES for x in range(4)]
def main_key(st,sit,x):return st*1000+sit*100+x
def setup_rows(mis,hud,prof):
 """1.4.1: the crews are fixed (SWAT in the helicopter; on the ground a soldier in command and seven agents in black) and the
 gunners' pose is the brain's - the settings keep the helicopter, the squad's tactics (AUTO = the brain picks) and the messages."""
 # 1.5: no SQUAD TACTICS row - how the detail fights is the brain's business alone (the player: "what are ASSAULT and GUARD for if it is all the same")
 # 2.0: the missions switch moved here from the fire page (that page got the mode and "to me" and must stay within eight rows)
 return [Tx('SET_MODEL',prof),Tx(('MSG_OFF','MSG_IMP','MSG_ALL')[hud],prof),Tx('MIS_FREE' if mis else 'MIS_DEF',prof),Tx('BACK',prof)]
def fire_rows(val,pol,mode,prof):
 """FIRE AND MODE: 2.0 - the detail's mode (a switch: PROTECT / ASSAULT) and "to me" first; then the four fire rules (the one in force is
 marked) and a switch: what to do about policemen."""
 return [Tx('MODE_ASSAULT' if mode else 'MODE_PROTECT',prof),Tx('RECALL',prof)]+[Tx('FIRE%d'%v,prof,v==val) for v in FIRE_VALUES]+[Tx('POL_NEVER' if pol else 'POL_ANSWER',prof),Tx('BACK',prof)]
PREF_PAGES=[(4,MODEL,MODEL_VALUES,'MODEL_TITLE','MODEL%d')]   # 1.4.1: no crew / weapon pages (fixed)
for page,label in [(0,'PICK_MAIN'),(1,'PICK_FIRE'),(2,'PICK_SETUP'),(4,'PICK_MODEL'),(6,'PICK_DISMISS')]:
 nxt='PAGE_PICK_NEXT_'+str(page);p.eq(2,page,nxt);p.go(label);p.label(nxt)
p.go('MENU_POLL')
def page(n):
 a(6,V(2),I(n));a(6,V(3),I(-999));a(6,V(25),I(-1));p.go('REFRESH')
def pick(index,label):
 nxt='PICK_NOT_'+label+'_'+str(len(p.rows));p.eq(1,index,nxt);p.go(label);p.label(nxt)
p.label('FORCE_REFRESH');a(6,V(3),I(-999));p.go('REFRESH')
p.label('PICK_MAIN')
# beta 4: nothing is taken while what is drawn is out of date (the page is redrawn first)
p.call('MAIN_KEY');p.check(0x003b,[V(6),V(3)],'CHECK_MENU_STATUS')
for sit,actions in [(0,['DO_CALL','OPEN_SETUP']),(1,['FORCE_REFRESH','OPEN_FIRE','OPEN_SETUP']),(2,['DO_FOLLOW','DO_HOLD','DO_PATROL','OPEN_FIRE','DO_ROPE','DO_TEAM_TOGGLE','OPEN_SETUP','OPEN_DISMISS']),(3,['DO_MAP','DO_GROVE','DO_EXIT_LAND','DO_EXIT_ROPE','OPEN_FIRE','OPEN_SETUP'])]:
 nxt='PICK_MAIN_SIT_'+str(sit);p.eq(7,sit,nxt)
 for index,label in enumerate(actions):pick(index,label)
 p.go('MENU_POLL');p.label(nxt)
p.go('MENU_POLL')
# models of the CREW / HELICOPTER pages are requested while the page is open (no waiting at the moment of the choice) and released after
p.label('OPEN_CREW');p.call('PRELOAD_SKINS');page(3)
p.label('OPEN_MODEL');p.call('PRELOAD_MODELS');page(4)
for label,n in [('OPEN_MAIN',0),('OPEN_FIRE',1),('OPEN_SETUP',2),('OPEN_WEAPON',5),('OPEN_DISMISS',6)]:p.label(label);page(n)
p.label('PRELOAD_SKINS')
for model in [105,106,107,285,287]:a(0x0247,I(model))
p.ret()
p.label('PRELOAD_MODELS')
for model in [487,497,425]:a(0x0247,I(model))
p.ret()
p.label('UNLOAD')
for model in [105,106,107,285,287,487,497,425]:a(0x0249,I(model))
p.ret()
# the squad row acts by what is true right now (not by what was drawn): deploy, recall, or nothing while the squad is on the ropes
p.label('DO_TEAM_TOGGLE');p.call('TEAM_PHASE');p.eq(12,0,'TT_NOT_DEPLOY');p.go('DO_TEAM_DEPLOY');p.label('TT_NOT_DEPLOY');p.eq(12,1,'FORCE_REFRESH');p.go('DO_TEAM_RECALL')
# DISMISS: with the team on the ground the squad is recalled by rope first and the helicopter leaves when it is back (DISMISS_TICK)
p.label('PICK_DISMISS');pick(0,'DO_DISMISS_ASK');p.go('OPEN_MAIN')
p.label('DO_DISMISS_ASK')
for st in [1,4,13]:
 nxt='ALLOW_DISMISS_'+str(st);p.eq(8,st,nxt);p.go('FORCE_REFRESH');p.label(nxt)
# beta 4: the order is carried out by DISMISS_TICK - at once with everybody aboard, after the squad is back otherwise
a(0x01bd,V(20));a(0xddc,I(DISMISS_T),V(20));p.set(DISMISS_NEXT,0);p.call('DT_PHASE');p.eq(22,0,'DDA_SQUAD');p.go('DDA_GO')
p.label('DDA_SQUAD');say(p,'HCDSQ')
p.label('DDA_GO');p.call('DISMISS_TICK');a(6,V(2),I(0));p.go('CHECK_MENU_STATUS')
# DISMISS_TICK (every pass of the panel, menu open or not) while a dismissal is pending: nothing while ropes move or the squad is on its
# way; squad on the ground - the recall is asked for (again every 6 s: a first try may meet a bad site) and after 45 s the helicopter
# leaves without it; everybody aboard - the helicopter is sent home. Uses 19@, 21@ - 24@.
p.label('DISMISS_TICK');p.get(19,DISMISS_T);p.eq(19,0,'DT_ACTIVE');p.ret()
p.label('DT_ACTIVE');p.get(21,STATE)
for st in [0,1,4,5,6,13]:   # no helicopter (any more), or it is leaving already
 nxt='DT_ST_%d'%st;p.eq(21,st,nxt);p.set(DISMISS_T,0);p.ret();p.label(nxt)
p.get(21,ROPE_BUSY);p.eq(21,1,'DT_FREE');p.ret()
p.label('DT_FREE');p.call('DT_PHASE');p.eq(22,0,'DT_SQUAD');p.go('DT_GO')
p.label('DT_SQUAD');p.eq(22,1,'DT_RET')
a(0x0085,V(21),V(20));a(0x0062,V(21),V(19));p.check(0x0019,[V(21),I(45000)],'DT_ASK');p.go('DT_GO')
p.label('DT_ASK');p.get(21,DISMISS_NEXT);p.check(0x001d,[V(20),V(21)],'DT_RET');a(0x0085,V(21),V(20));a(0x000a,V(21),I(6000));a(0xddc,I(DISMISS_NEXT),V(21));p.set(CMD,17);p.ret()
p.label('DT_GO');p.set(DISMISS_T,0);p.set(CMD,4)
p.label('DT_RET');p.ret()
# settings: three sub-pages and two one-tap switches
p.label('PICK_SETUP')
for index,label in [(0,'OPEN_MODEL'),(1,'TOGGLE_HUD'),(2,'TOGGLE_MIS'),(3,'LEAVE_SETUP')]:pick(index,label)
p.go('MENU_POLL')
p.label('LEAVE_SETUP');p.call('UNLOAD');p.go('OPEN_MAIN')
# 1.4.1: tactics AUTO (0, the brain picks) -> ASSAULT (1) -> GUARD (2) -> AUTO
p.label('TOGGLE_HUD');p.get(9,HUD);a(0x000a,V(9),I(-1));p.check(0x0019,[V(9),I(-1)],'TOGGLE_HUD_WRAP');a(0xddc,I(HUD),V(9));p.go('FORCE_REFRESH')
p.label('TOGGLE_HUD_WRAP');p.set(HUD,2);p.go('FORCE_REFRESH')
p.label('TOGGLE_MIS');p.get(9,MISSIONS);p.eq(9,0,'TOGGLE_MIS_OFF');p.set(MISSIONS,1);p.go('FORCE_REFRESH')
p.label('TOGGLE_MIS_OFF');p.set(MISSIONS,0);p.go('FORCE_REFRESH')
p.label('PICK_FIRE')
# 2.0: row 0 switches the mode (and says what it means), row 1 is "to me" (the brain drops the assault and brings everybody back)
p.eq(1,0,'FIRE_NOT_MODE');p.get(9,MODE);p.eq(9,0,'MODE_TO_PROTECT');p.set(MODE,1);say(p,'HCMDA');p.go('FORCE_REFRESH')
p.label('MODE_TO_PROTECT');p.set(MODE,0);say(p,'HCMDP');p.go('FORCE_REFRESH')
p.label('FIRE_NOT_MODE');p.eq(1,1,'FIRE_NOT_RECALL');p.set(RECALL,1);say(p,'HCRCL');p.go('FORCE_REFRESH')
p.label('FIRE_NOT_RECALL')
for idx,val in enumerate(FIRE_VALUES):
 nxt='FIRE_OPTION_NEXT_'+str(idx);p.eq(1,idx+2,nxt);p.set(FIRE,val);p.go('FORCE_REFRESH');p.label(nxt)
for idx,key in [(len(FIRE_VALUES)+2,POLICE)]:
 nxt='FIRE_SWITCH_NEXT_'+str(idx);off='FIRE_SWITCH_OFF_'+str(idx);p.eq(1,idx,nxt);p.get(9,key);p.eq(9,0,off);p.set(key,1);p.go('FORCE_REFRESH');p.label(off);p.set(key,0);p.go('FORCE_REFRESH');p.label(nxt)
p.go('OPEN_MAIN')
p.label('FIRE_KEY');p.get(6,FIRE);a(0x0012,V(6),I(10));p.get(11,POLICE);a(0x005a,V(6),V(11));a(0x0012,V(6),I(10));p.get(11,MODE);a(0x005a,V(6),V(11));p.ret()
for key,pag,choices,back in [(MODEL,4,[(0,487),(1,497),(2,425)],'OPEN_SETUP')]:
 label={4:'PICK_MODEL'}[pag];p.label(label)
 for idx,val in choices:
  nxt='OPTION_NEXT_'+str(pag)+'_'+str(idx);p.eq(1,idx,nxt);p.set(key,val);p.go('FORCE_REFRESH');p.label(nxt)
 p.go(back)
for label,cmd in [('DO_CALL',1),('DO_FOLLOW',2),('DO_HOLD',3),('DO_GROVE',7),('DO_ROPE',10),('DO_MAP',11),('DO_PATROL',14),('DO_TEAM_DEPLOY',16),('DO_TEAM_RECALL',17)]:
 p.label(label)
 # No commands while spawning/departing/retreating: the page is redrawn instead.
 for st in [1,4,13]:
  nxt='ALLOW_'+label+'_'+str(st);p.eq(8,st,nxt);p.go('FORCE_REFRESH');p.label(nxt)
 if cmd!=17:p.set(DISMISS_T,0)   # another order withdraws a dismissal that still waits for the squad
 p.set(CMD_SRC,1);p.set(CMD,cmd)   # beta 5: no fixed 200 ms pause - the page follows the state on the very next pass (the menu is polled every frame)
 p.go('CHECK_MENU_STATUS')
# the two EXIT BUTTON rows are switches: they choose what the game's own exit button does and start nothing themselves
p.label('DO_EXIT_LAND');p.set(EXIT_MODE,0);say(p,'HCXBL');p.go('FORCE_REFRESH')
p.label('DO_EXIT_ROPE');p.set(EXIT_MODE,1);say(p,'HCXBR');p.go('FORCE_REFRESH')
# 6@ = key of the main page now (state*1000 + situation*100 + x), 5@ = situation; x: on foot = squad phase*2 + rope phase, aboard = exit mode (+2 while an exit is under way)
p.label('MAIN_KEY');p.get(8,STATE);a(6,V(5),I(2));a(6,V(12),I(0))
for sit,group in [(0,NONE_STATES),(1,BUSY_STATES)]:
 for st in group:nxt='MK_%d_%d'%(sit,st);p.eq(8,st,nxt);a(6,V(5),I(sit));p.go('MK_DONE');p.label(nxt)
a(0x01f5,I(0),V(11));p.get(12,PUB+1);p.check(0x056e,[V(12)],'MK_GROUND');p.check(0x0448,[V(11),V(12)],'MK_GROUND');a(6,V(5),I(3));p.get(12,EXIT_MODE);p.get(15,AUTO_EXIT);p.eq(15,0,'MK_EXITING');p.go('MK_DONE')
p.label('MK_EXITING');a(0x000a,V(12),I(2));p.go('MK_DONE')
p.label('MK_GROUND');p.call('TEAM_PHASE');a(0x0012,V(12),I(2));p.call('ROPE_PHASE');a(0x005a,V(12),V(15))
p.label('MK_DONE');a(0x0085,V(6),V(8));a(0x0012,V(6),I(1000));a(0x0085,V(11),V(5));a(0x0012,V(11),I(100));a(0x005a,V(6),V(11));a(0x005a,V(6),V(12));p.ret()
# 12@ = squad phase: 0 aboard (DEPLOY), 1 on the ground (RECALL), 2 roping down, 3 coming back. Uses 11@, 15@.
def emit_team_phase(name,out,on,tmp):
 L=lambda x:name+'_'+x
 p.label(name);a(6,V(out),I(0));p.get(on,ESCORT_ON)
 p.eq(on,2,L('ON_N2'));a(6,V(out),I(2));p.ret();p.label(L('ON_N2'));p.eq(on,3,L('ON_N3'));a(6,V(out),I(3));p.ret();p.label(L('ON_N3'))
 p.get(tmp,ESCORT_CMD);p.eq(tmp,1,L('CMD_N1'));a(6,V(out),I(2));p.ret();p.label(L('CMD_N1'));p.eq(tmp,2,L('CMD_N2'));a(6,V(out),I(3));p.ret();p.label(L('CMD_N2'))
 p.get(tmp,STATE);p.eq(tmp,19,L('STEADY'));p.get(tmp,ESCORT_PENDING);p.eq(tmp,1,L('PEND_N1'));a(6,V(out),I(2));p.ret();p.label(L('PEND_N1'));p.eq(tmp,2,L('STEADY'));a(6,V(out),I(3));p.ret()
 p.label(L('STEADY'));p.eq(on,1,L('RET'));a(6,V(out),I(1));p.label(L('RET'));p.ret()
emit_team_phase('TEAM_PHASE',12,11,15)
emit_team_phase('DT_PHASE',22,23,24)   # the same for DISMISS_TICK, which runs between the menu's own steps and must not touch its registers
# 15@ = 1 while a rope pickup of CJ is under way: the helicopter is coming in for it, or the rope hangs waiting for him. Uses 11@.
p.label('ROPE_PHASE');p.get(15,ROPE_WAIT);p.eq(15,1,'RP_APPROACH');p.ret()
p.label('RP_APPROACH');a(6,V(15),I(0));p.get(11,STATE);p.eq(11,19,'RP_RET');p.get(11,ESCORT_PENDING);p.eq(11,0,'RP_RET');a(6,V(15),I(1));p.label('RP_RET');p.ret()
p.label('SETUP_KEY');p.get(6,MISSIONS);a(0x0012,V(6),I(10));p.get(11,HUD);a(0x005a,V(6),V(11));p.ret()
p.label('CHECK_MENU_STATUS');p.eq(2,0,'CMS_FIRE');p.call('MAIN_KEY');p.go('CMS_COMPARE')
p.label('CMS_FIRE');p.eq(2,1,'CMS_SETUP');p.call('FIRE_KEY');p.go('CMS_COMPARE')
p.label('CMS_SETUP');p.eq(2,2,'CMS_CREW');p.call('SETUP_KEY');p.go('CMS_COMPARE')
p.label('CMS_CREW');p.eq(2,3,'CMS_MODEL');p.get(6,CREW);p.go('CMS_COMPARE')
p.label('CMS_MODEL');p.eq(2,4,'CMS_WEAPON');p.get(6,MODEL);p.go('CMS_COMPARE')
p.label('CMS_WEAPON');p.eq(2,5,'MENU_POLL');p.get(6,WEAPON_SETTING)
p.label('CMS_COMPARE');p.check(0x803b,[V(6),V(3)],'MENU_POLL');a(0x01bd,V(16));p.go('REFRESH')   # 16@ = when the page last changed under the player's finger
p.label('REFRESH');a(0x0df3)
for pageid in (0,1,2,4,6):   # (1.4.1: pages 3 and 5 - crew and crew weapon - are gone)
 nxt='DRAW_NEXT_'+str(pageid);p.eq(2,pageid,nxt);p.go('DRAW_'+str(pageid));p.label(nxt)
p.go('CLOSE')
_draw=[0]
def draw(base,count):
 """Point V4 at the blob of the language in force (V9 = LANG) and show it with `count` rows."""
 _draw[0]+=1;k='DRW%d'%_draw[0]
 p.get(9,LANG);p.eq(9,0,k+'_RU');a(0xdd0,V(4),L(base));p.go('SHOW_%d'%count)
 p.label(k+'_RU');a(0xdd0,V(4),L(base+'_U'));p.go('SHOW_%d'%count)
p.label('DRAW_0');p.call('MAIN_KEY');a(0x0085,V(3),V(6));a(0x0085,V(7),V(5))
for st,sit,x in MAIN_VARIANTS:
 nxt='DRAW_MAIN_NEXT_%d_%d_%d'%(st,sit,x);p.eq(6,main_key(st,sit,x),nxt);draw('MAIN_%d_%d_%d'%(st,sit,x),len(main_rows(st,sit,x)));p.label(nxt)
a(6,V(7),I(0));draw('MAIN_0_0_0',2)
p.label('DRAW_2');p.call('SETUP_KEY');a(0x0085,V(3),V(6))
for tac in (0,1):
 for hud in (0,1,2):
  nxt='DRAW_SETUP_NEXT_%d%d'%(tac,hud);p.eq(6,tac*10+hud,nxt);draw('SETUP_%d%d'%(tac,hud),4);p.label(nxt)
draw('SETUP_02',4)
p.label('DRAW_1');p.call('FIRE_KEY');a(0x0085,V(3),V(6))
for val in FIRE_VALUES:
 for pol in (0,1):
  for mode in (0,1):
   nxt='DRAW_FIRE_NEXT_%d%d%d'%(val,pol,mode);p.eq(6,val*100+pol*10+mode,nxt);draw('FIRE_%d%d%d'%(val,pol,mode),len(FIRE_VALUES)+4);p.label(nxt)
draw('FIRE_300',len(FIRE_VALUES)+4)
for pageid,key,values,_,_ in PREF_PAGES:
 p.label('DRAW_'+str(pageid));p.get(8,key);a(0x0085,V(3),V(8))
 for val in values:
  nxt='DRAW_PREF_NEXT_'+str(pageid)+'_'+str(val);p.eq(8,val,nxt);draw('PREF_'+str(pageid)+'_'+str(val),len(values)+1);p.label(nxt)
 draw('PREF_'+str(pageid)+'_'+str(values[0]),len(values)+1)
p.label('DRAW_6');a(6,V(3),I(-1));p.call('DT_PHASE');p.eq(22,0,'DRAW_6_TEAM');draw('DISMISS_MENU',2);p.label('DRAW_6_TEAM');draw('DISMISS_MENU_T',2)   # squad down or on the ropes: "recall squad first"
for count in range(1,9):p.label('SHOW_'+str(count));a(0xdf2,V(4),I(count));p.go('MENU_POLL')
p.label('CORE_MISSING');a(0xdd0,V(4),L('OFFLINE_MENU'));a(0xdf2,V(4),I(1))
p.label('OFFLINE_POLL');a(1,I(50));a(0x01bd,V(20));a(0xddc,I(PANELHEART),V(20));p.check(0x0256,[I(0)],'CLOSE');a(0xdf4,V(1),I(250));p.eq(1,-1,'CLOSE');p.go('OFFLINE_POLL')
p.label('CLOSE');p.call('UNLOAD');a(0xdf3);p.set(OPEN,0);p.set(0,0);a(6,V(10),I(0));p.go('WATCH')
# All menus fit on one page (<=8 rows); metadata is appended beyond terminating branches.
VERSION='1.4'
for st,sit,x in MAIN_VARIANTS:
 for prof,suf in zip(PROFILES,SUFFIX):
  title=(i18n.encode('HELICOVER 2.0 BETA 3','en') if prof=='en' else i18n.menu_text('TITLE_READY',prof)) if st==0 else i18n.state_title(st,STATES[st],prof)
  p.blob('MAIN_%d_%d_%d'%(st,sit,x)+suf,title,main_rows(st,sit,x,prof))
for prof,suf in zip(PROFILES,SUFFIX):
 if prof=='en':p.blob('OFFLINE_MENU',i18n.menu_text('OFFLINE_TITLE',prof),[i18n.menu_text('OFFLINE_ROW',prof)])   # the core is missing, so the language is unknown: English only
 p.blob('DISMISS_MENU'+suf,i18n.menu_text('DISMISS_TITLE',prof),[Tx('DISMISS_YES',prof),Tx('DISMISS_NO',prof)])
 p.blob('DISMISS_MENU_T'+suf,i18n.menu_text('DISMISS_TITLE',prof),[Tx('DISMISS_YES_TEAM',prof),Tx('DISMISS_NO',prof)])
 for tac in (0,1):
  for hud in (0,1,2):p.blob('SETUP_%d%d'%(tac,hud)+suf,i18n.menu_text('SET_TITLE',prof),setup_rows(tac,hud,prof))
 for val in FIRE_VALUES:
  for pol in (0,1):
   for mode in (0,1):p.blob('FIRE_%d%d%d'%(val,pol,mode)+suf,i18n.menu_text('FIRE_TITLE',prof),fire_rows(val,pol,mode,prof))
 for pg,_,values,title,fmt in PREF_PAGES:
  for val in values:
   p.blob('PREF_'+str(pg)+'_'+str(val)+suf,i18n.menu_text(title,prof),[Tx(fmt%v,prof,v==val) for v in values]+[Tx('BACK',prof)])

launch=Script();a=launch.add
# beta 5: the menu opens at once. The panel writes the game time into PANELHEART on every pass, so "is it alive" is a comparison
# with the time now (it used to be two reads 250 ms apart after a 400 ms pause: 0.65 s before the panel was even asked).
# A stale stamp (or one from 'the future' after a loaded save) falls back to the old proof of life: the stamp has to change
# within 650 ms - so a stale stamp alone never means "files missing".
launch.label('ENTRY');a(0);launch.get(1,PANELHEART);launch.eq(1,0,'PANEL_SEEN');launch.go('PANEL_SLOW')
launch.label('PANEL_SEEN');a(0x01bd,V(2));a(0x0062,V(2),V(1));launch.check(0x8019,[V(2),I(PANEL_FRESH_MS)],'PANEL_SLOW');launch.check(0x0019,[V(2),I(-1)],'PANEL_SLOW')
launch.label('PANEL_OK');launch.set(OPEN,1);a(0x004e)
launch.label('PANEL_SLOW');a(0x01bd,V(3));a(0x000a,V(3),I(PANEL_PROOF_MS))
launch.label('PANEL_SLOW_LOOP');a(1,I(0));launch.get(2,PANELHEART);launch.check(0x003b,[V(2),V(1)],'PANEL_OK');a(0x01bd,V(2));launch.check(0x001d,[V(2),V(3)],'PANEL_SLOW_LOOP')
launch.label('MISSING')
for _ofs,_val in GAME_SIG:a(0x0dd8,V(1),I(_ofs),I(4),I(1));launch.check(0x0039,[V(1),I(_val)],'MISSING_EN')   # only on the known build is the game's language flag read
a(0x0dd8,V(1),I(GAME_RU_FLAG),I(1),I(1));launch.eq(1,1,'MISSING_EN');a(0x03e5,S('UCOFF'));a(0x004e)
launch.label('MISSING_EN');a(0x03e5,S('HCOFF'));a(0x004e)

# ---------------------------------------------------------------------------------------------------------------------
# 1.3 (Helicover Brain, stage 2): the fire worker is the gunners' BODY. Who is a threat, who fires at whom, when, and
# along which line is decided by the brain (the AML mod libHelicoverBrain64.so); this script asks it every frame through
# the private CLEO opcode 0E48 and does what it is told: point the weapon, let one round go, bring the weapon down.
# Everything that used to choose targets here (cell scans, bullet-trace reading, the threat board, friend lists by
# model, the per-mode checks, the script's own line-of-fire test) is gone.
#   0E48 first_variable count command      (the brain writes its answer into `count` local variables from `first`)
#   command 1 (9 variables): in gunner handle; out state (0 rest, 1 weapon on the man, 2 = 1 + fire this round), the man,
#             round start x y z, round end x y z
#   command 3 (5, 8 or 9): out alert level (0 calm .. 4 evacuate), threats, attackers, kills so far, the most dangerous man;
#             then ms since CJ fired and the direction of that shot x, y; then ms since a stranger fired at our helicopter
# The opcode exists only while the mod is loaded: it is never run before the handshake value says so (an unregistered
# opcode would have its parameters executed as code).
f=Script();a=f.add
def rest(var,P):
 """Weapons down. CLEAR_CHAR_TASKS also ends the kneeling of a mounted gunner, so it is asked for again (beta 6). Uses 30@."""
 a(0x0687,V(var));f.get(30,POSE);f.check(0x0019,[V(30),I(0)],P);f.check(0x0a32,[V(var)],P);a(0x04eb,V(var),I(1));f.label(P)
f.label('INIT');a(0);f.set(AUTO_DEPLOY_T,0);f.set(BURN_NEXT,0);f.set(BURN_SAID,0);f.set(BR_KILLS,-1);f.set(BR_ALERT,0);f.set(BR_TOP,-1)
for i in range(4):f.set(G_AIM+i,-1);f.set(G_AIM_T+i,0);f.set(G_FIRE+i,-1);f.set(G_FIRE_T+i,0)
f.set(FIRENEXT,0);f.set(FIREGEN,-1);f.set(FIRE_ACTIVE,0);f.set(FIRE_TARGET,-1);a(6,V(26),I(-1))
f.label('WAIT');a(1,I(0));f.call('BANNER');a(0x01bd,V(30));a(0xddc,I(FIREHEART),V(30));f.check(0x0a52,[I(EXIT_WIDGET)],'EXIT_POLL_DONE');a(0xddc,I(EXIT_PRESSED),V(30));f.label('EXIT_POLL_DONE');f.get(30,BUSY);f.eq(30,0,'WAIT');f.get(30,STATE)
for stateid in [0,1,5,6,16]:
 nxt='FSTATE_NEXT_'+str(stateid);f.eq(30,stateid,nxt);f.go('NO_HELI');f.label(nxt)
for index in range(7):f.get(index,PUB+index)
f.get(30,CREWGEN);f.get(31,FIREGEN);f.check(0x003b,[V(30),V(31)],'FIRE_CREW_CHANGED');f.go('FIRE_CREW_READY')
f.label('FIRE_CREW_CHANGED');a(0xddc,I(FIREGEN),V(30));a(6,V(26),I(-1))
for i in range(4):f.set(G_AIM+i,-1);f.set(G_FIRE+i,-1)
f.label('FIRE_CREW_READY');f.get(7,WPN);f.get(28,PHASE);f.eq(28,2,'FIRE_MODE');f.call('ALL_REST');f.go('WAIT')
f.label('FIRE_MODE');f.get(25,FIRE);f.check(0x003b,[V(25),V(26)],'MODE_CHANGED');f.go('MODE_READY')
f.label('MODE_CHANGED');f.eq(26,-1,'MODE_REPORT')
f.go('MODE_REPORT_DONE');f.label('MODE_REPORT')
for m in (0,2,3,4):
 nxt='MODE_REPORT_NOT_'+str(m);f.eq(25,m,nxt);msg(f,'HCFM'+str(m));f.go('MODE_REPORT_DONE');f.label(nxt)
f.label('MODE_REPORT_DONE');a(0x0085,V(26),V(25))
for var in [3,4,5,6]:
 # (no hatred is set or cleared here any more: the core gives every crewman none when he is created, and no fire rule adds any)
 skip='MODE_CLEAR_'+str(var);alive(f,var,skip);rest(var,'REST1_'+str(var));f.set(G_AIM+var-3,-1);f.set(G_FIRE+var-3,-1);f.label(skip)
f.label('MODE_READY');f.call('BURN_WATCH');f.get(30,FIRENEXT);a(0x01bd,V(31));f.check(0x001d,[V(31),V(30)],'BRAIN')
a(0x000a,V(31),I(500));a(0xddc,I(FIRENEXT),V(31))
for var in [3,4,5,6]:
 skip='ARM_SKIP_'+str(var);alive(f,var,skip);a(0x0470,V(var),V(30));f.check(0x803b,[V(30),V(7)],skip);a(0x01b2,V(var),V(7),I(30000));a(0x01b9,V(var),V(7));a(0x02e2,V(var),I(100));a(0x07dd,V(var),I(100));f.label(skip)
# ---- the brain
f.label('BRAIN');f.get(30,BRAIN_HELLO);f.check(0x0039,[V(30),I(BRAIN_MAGIC)],'NO_BRAIN')
a(0x0e48,V(8),I(13),I(3))   # 8@ alert, 9@ threats, 10@ attackers, 11@ kills, 12@ the most dangerous man, 13-15@ CJ's own fire (the squad's business), 16@ ms since a stranger fired at the helicopter
# 1.4.1: 17@ the gunners' pose (the brain's: seated on the skid, kneeling at the door over a fight) - the core re-seats them when it
# changes; 18-20@ the spot where the helicopter's gunners see the threat (0 0 0 = none), for the pilot
f.get(30,POSE);f.check(0x803b,[V(30),V(17)],'POSE_SAME');f.check(0x8019,[V(17),I(2)],'POSE_SAME');f.check(0x0019,[V(17),I(-1)],'POSE_SAME');a(0xddc,I(POSE),V(17));f.label('POSE_SAME')   # (check jumps when false: same, above 2 or negative -> unchanged)
a(0xddc,I(HELI_SPOT_X),V(18));a(0xddc,I(HELI_SPOT_Y),V(19));a(0xddc,I(HELI_SPOT_Z),V(20))
a(0xddc,I(BR_ALERT),V(8));a(0xddc,I(BR_THREATS),V(9));a(0xddc,I(BR_ATTACKERS),V(10))
# 1.5.4 (fifth log: no ground team for the first 218 s of the fight and for the last 34): the helicopter that escorts CJ (state 2) sends the
# team down the ropes by itself when the alert is COMBAT or worse, CJ is on foot, no team is out, nothing else is ordered, and 45 s have
# passed since it last did so
f.check(0x0019,[V(8),I(2)],'AD_DONE');f.get(30,ESCORT_ON);f.eq(30,0,'AD_DONE');f.get(30,STATE);f.eq(30,2,'AD_DONE');f.get(30,CMD);f.eq(30,0,'AD_DONE')
f.get(30,PUB);f.check(0x80df,[V(30)],'AD_DONE');f.get(30,AUTO_DEPLOY_T);a(0x01bd,V(31));f.check(0x001d,[V(31),V(30)],'AD_DONE')
a(0x000a,V(31),I(45000));a(0xddc,I(AUTO_DEPLOY_T),V(31));f.set(CMD_SRC,3);f.set(CMD,16)
f.label('AD_DONE')
# fire at the helicopter: the stamp the pilot's evasion looks at (it used to come from the bullet traces)
f.check(0x0019,[V(16),I(-1)],'HELI_SHOT_DONE');f.check(0x8019,[V(16),I(600)],'HELI_SHOT_DONE');a(0x01bd,V(31));a(0x0062,V(31),V(16));a(0xddc,I(HELI_SHOT_T),V(31));f.label('HELI_SHOT_DONE')
# the pilot still flies by the old rules (stage 6): he is told whom the fight is about - the most dangerous man, while there is a threat and
# the gunners are allowed to fire
a(6,V(30),I(-1));f.eq(25,0,'TOP_FIRE_ALLOWED');f.go('TOP_SET');f.label('TOP_FIRE_ALLOWED');f.check(0x0019,[V(8),I(1)],'TOP_SET');f.check(0x0019,[V(12),I(0)],'TOP_SET');a(0x0085,V(30),V(12))
f.label('TOP_SET');a(0xddc,I(FIRE_TARGET),V(30));a(0xddc,I(BR_TOP),V(30))
# kills: the brain counts the men who died under our fire; the script keeps the player's counter and says so
f.get(30,BR_KILLS);f.eq(30,-1,'KILL_KNOWN');a(0xddc,I(BR_KILLS),V(11));f.go('KILL_DONE')
f.label('KILL_KNOWN');f.check(0x803b,[V(30),V(11)],'KILL_DONE');a(0xddc,I(BR_KILLS),V(11));f.get(31,KILLS);a(0x000a,V(31),I(1));a(0xddc,I(KILLS),V(31))
f.get(30,HUD);f.eq(30,LEVEL_ALL,'KILL_DONE');f.get(30,KILL_NEXT);a(0x01bd,V(14));f.check(0x001d,[V(14),V(30)],'KILL_DONE');a(0x000a,V(14),I(2000));a(0xddc,I(KILL_NEXT),V(14));print_key(f,'HCKILL','KILLP_',number=(V(31),I(2000),I(1)))
f.label('KILL_DONE')
# "contact" when somebody attacks; "area clear" once nobody dangerous has been left (seen or remembered) for 3 s.
# While the squad is on the ground it makes these calls itself.
f.check(0x0019,[V(10),I(0)],'CONTACT_NO');f.set(CLEAR_AT,0);f.get(30,ENGAGED);f.eq(30,0,'CONTACT_DONE');f.set(ENGAGED,1);f.get(30,SQ_GROUP);f.eq(30,0,'CONTACT_DONE');msg(f,'HCCONT');f.go('CONTACT_DONE')
f.label('CONTACT_NO');f.check(0x8019,[V(9),I(0)],'CONTACT_DONE');f.get(30,ENGAGED);f.eq(30,1,'CONTACT_DONE');f.get(30,CLEAR_AT);a(0x01bd,V(31));f.eq(30,0,'CLEAR_TIMED');a(0x000a,V(31),I(3000));a(0xddc,I(CLEAR_AT),V(31));f.go('CONTACT_DONE')
f.label('CLEAR_TIMED');f.check(0x001d,[V(31),V(30)],'CONTACT_DONE');f.set(ENGAGED,0);f.set(CLEAR_AT,0);f.get(30,SQ_GROUP);f.eq(30,0,'CONTACT_DONE');msg(f,'HCCLEAR')
f.label('CONTACT_DONE')
# ---- one question per gunner per frame (1.4: he fires his own weapon - the game's drive-by task - in the bursts the brain allows;
# in a pause, or the moment CJ or one of ours comes into his line, the brain says "no fire" and his weapon only stays on the man:
# the aiming task takes the place of the firing one in that very frame)
a(6,V(27),I(0))
for var in [3,4,5,6]:
 g=var-3;skip='G%d_SKIP'%var;hold='G%d_HOLD'%var;fire='G%d_FIRE'%var;issue='G%d_AIM'%var;check_aim='G%d_AIMCHK'%var;resting='G%d_REST'%var
 # a crewman who has left the helicopter (after a landing) is a guard on foot: the squad worker asks the brain for him
 alive(f,var,skip);f.check(0x0a32,[V(var)],skip);a(0x0085,V(8),V(var));a(0x0e48,V(8),I(3),I(2))   # 9@ 0 rest / 1 cover / 2 fire / 3 his man, no fire; 10@ the man
 f.check(0x0019,[V(9),I(0)],resting);a(6,V(27),I(1));f.eq(9,2,hold)
 # fire: the drive-by task at the man for a new man, and renewed every 1.5 s
 f.get(30,G_FIRE+g);f.check(0x003b,[V(30),V(10)],fire);f.get(30,G_FIRE_T+g);a(0x01bd,V(31));f.check(0x001d,[V(31),V(30)],skip)
 f.label(fire);alive(f,10,skip);a(0x0713,V(var),V(10),I(-1),F(0),F(0),F(0),F(150),I(0),I(1 if var in [3,5] else 0),I(100))
 a(0xddc,I(G_FIRE+g),V(10));a(0x01bd,V(31));a(0x000a,V(31),I(1500));a(0xddc,I(G_FIRE_T+g),V(31));a(0xddc,I(G_AIM+g),V(10));f.go(skip)
 # no fire: a gunner who was firing stops at once (the aiming task replaces the drive-by); his weapon stays on the man, renewed every 0.7 s
 f.label(hold);f.get(30,G_FIRE+g);f.check(0x8039,[V(30),I(-1)],check_aim);f.set(G_FIRE+g,-1);f.go(issue)
 f.label(check_aim);f.get(30,G_AIM+g);f.check(0x003b,[V(30),V(10)],issue);f.get(30,G_AIM_T+g);a(0x01bd,V(31));f.check(0x001d,[V(31),V(30)],skip)
 f.label(issue);alive(f,10,skip);a(0x00a0,V(10),V(17),V(18),V(19));a(0x0667,V(var),V(17),V(18),V(19),I(1500));a(0xddc,I(G_AIM+g),V(10));a(0x01bd,V(31));a(0x000a,V(31),I(700));a(0xddc,I(G_AIM_T+g),V(31));f.go(skip)
 f.label(resting);f.get(30,G_AIM+g);f.check(0x8039,[V(30),I(-1)],skip);rest(var,'REST2_'+str(var));f.set(G_AIM+g,-1);f.set(G_FIRE+g,-1)
 f.label(skip)
a(0xddc,I(FIRE_ACTIVE),V(27));f.go('WAIT')
# no brain (the mod is not loaded, or it refused this game): nobody fires. The core does not call the helicopter in the first place.
f.label('NO_BRAIN');f.call('ALL_REST');f.go('WAIT')
# no helicopter (dismissed, lost, on its way in or out): a fight that was going on is over for the gunners - nothing of it is left behind
# for the next call ("contact" is said again, the pilot has no old target)
f.label('NO_HELI');f.set(FIRE_ACTIVE,0);f.set(FIRE_TARGET,-1);f.set(ENGAGED,0);f.set(CLEAR_AT,0);f.go('WAIT')
f.label('ALL_REST');f.set(FIRE_ACTIVE,0);f.set(FIRE_TARGET,-1)
for var in [3,4,5,6]:
 g=var-3;skip='AR_SKIP_%d'%var;f.get(30,G_AIM+g);f.check(0x8039,[V(30),I(-1)],skip);f.set(G_AIM+g,-1);f.set(G_FIRE+g,-1);alive(f,var,skip);rest(var,'REST3_'+str(var));f.label(skip)
f.ret()
emit_banner(f)
# beta 6: a burning car close to CJ is called out, whoever set it on fire (four 12 m squares around him, twice a second)
f.label('BURN_WATCH');f.get(30,BURN_NEXT);a(0x01bd,V(31));f.check(0x001d,[V(31),V(30)],'BURN_RET');a(0x000a,V(31),I(500));a(0xddc,I(BURN_NEXT),V(31));a(0x00a0,V(0),V(8),V(9),V(10))
for q,(qx,qy) in enumerate([(-1,-1),(1,-1),(-1,1),(1,1)]):
 nxt='BURN_NEXT_%d'%q;h=BURN_WARN_M/2
 a(0x0087,V(11),V(8));a(0x000b,V(11),F(qx*h-h));a(0x0087,V(12),V(9));a(0x000b,V(12),F(qy*h-h));a(0x0087,V(13),V(8));a(0x000b,V(13),F(qx*h+h));a(0x0087,V(14),V(9));a(0x000b,V(14),F(qy*h+h));a(0x053e,V(11),V(12),V(13),V(14),I(-1),V(15))
 f.check(0x056e,[V(15)],nxt);f.check(0x803b,[V(15),V(1)],nxt);f.check(0x8119,[V(15)],nxt);a(0x0227,V(15),V(30));f.check(0x8019,[V(30),I(BURN_HP-1)],nxt);f.go('BURN_SAY');f.label(nxt)
f.label('BURN_RET');f.ret()
f.label('BURN_SAY');f.get(30,BURN_SAID);a(0x01bd,V(31));f.check(0x001d,[V(31),V(30)],'BURN_RET');a(0x000a,V(31),I(4000));a(0xddc,I(BURN_SAID),V(31));msg(f,'HCBURN');f.ret()

def main():
 reports=[c.build('Helicover_Core','csa'),p.build('Helicover_Panel','csa'),launch.build('Helicover','csi'),f.build('Helicover_Fire','csa')]
 (OUT/'Helicover.fxt').write_text('\n'.join(k+' '+v for k,v in MESSAGES.items())+'\n')
 (OUT/'validation.txt').write_text('\n'.join(reports)+'\nAndroid runtime: NOT TESTED.\n')
 print('\n'.join(reports))
if __name__=='__main__':main()
