"""Helicover v40 tactical squad AI (Helicover_Squad.csa).

One worker drives whichever team is on foot: the rope / escort team of the ground worker
(GROUND_PUB, while SQ_ROPE = 1) or the helicopter crew after an evacuation landing (PUB+3..6,
while PHASE = 1). The core, ground and fire workers stop tasking those guards while SQ_HEART is
fresh, so exactly one script gives them orders.

1.3 (Helicover Brain, stage 2): who is a threat and which guard fires at whom is decided by the brain
(libHelicoverBrain64.so). Every FRAME each guard asks it (0E48, command 2): nothing / cover / fire / cease
fire, and the man - a guard who is firing when CJ or one of ours comes into his line is taken off the
trigger in that same frame. Every 100 ms: the brain's picture (command 3) for the radio calls, then a
decision for each of the four guards - formation, shields, cover, bounding - with the man the brain gave
him. The squad's own scans, threat list, scoring and rules of engagement are gone. Tasks are only
re-issued when the order changes or its time runs out, so the game AI is never restarted every tick.

Tactics (SETUP > TEAM ON FOOT): 0 BODYGUARD - tight diamond, two shields step between CJ and the
threat, two engage on a short leash; 1 ASSAULT - wide wedge, one pair advances crouched, the other
flanks. When CJ is badly hurt everyone forms a ring around him. The rear guard is the medic.

Registers: 0 CJ, 1 heli, 2-5 guards, 6 CJ car/-1, 7 tactics, 8 attackers (brain), 9-11 CJ xyz, 12 now,
13-16 each guard's man (-1 = none), 17 group, 18 threat count (perception) / CJ speed (guards), 19 message scratch,
20 move speed, 21-23 guard xyz, 24 guard-CJ distance, 25 target, 26-31 scratch.
"""
from asm_v25 import *
import os
import build_v25 as b
# 1.4.1: the same worker is built twice - TEAM 0 (Helicover_Squad: guards 1-4, the commander's words and the radio calls) and
# TEAM 1 (Helicover_Squad2: guards 5-8 of the ground team, with their own shared slots; no speech)
TEAM=int(os.environ.get('HC_SQUAD_TEAM','0'))
if TEAM:
 SLOT,BR_ST,BR_TG,PACE,SQT,HEART,GROUP,TICK=b.SQ_SLOT2,b.SQ_BR_ST2,b.SQ_BR_TG2,b.SQ_PACE2,b.SQ_T2,b.SQ_HEART2,b.SQ_GROUP2,b.SQ_TICK2
else:
 SLOT,BR_ST,BR_TG,PACE,SQT,HEART,GROUP,TICK=b.SQ_SLOT,b.SQ_BR_ST,b.SQ_BR_TG,b.SQ_PACE,b.SQ_T,b.SQ_HEART,b.SQ_GROUP,b.SQ_TICK
from msg_v42 import say
s=Script();a=s.add
FIELDS={'TASK':0,'NEXT':1,'TX':2,'TY':3,'LX':4,'LY':5,'LT':6,'DEAD':7,'TGT':8,'COVER':9}
# (2.0: 20 = the mod walks him, 21 = the mod has his weapon)
# TASK values: -1 not set up, 0 idle, 1 moving, 2 sector watch, 3 shooting, 4 entering car,
# 5 riding, 6 leaving car, 7 path-node move, 8 crouched assault, 9 medic, 10 timed attack,
# 11 climbing an obstacle, 12 moving while shooting, 13 turning to the sector (assault),
# 15 reload drill, 16 relaxed (quiet), 18 weapon on the man but no fire (the brain said cease fire)
def fk(k,f):return SLOT+k*b.SQ_SLOT_SIZE+FIELDS[f]
_n=[0]
def uid(p):_n[0]+=1;return p+'_'+str(_n[0])
def alive(var,fail):s.check(0x056d,[V(var)],fail);s.check(0x8118,[V(var)],fail)
def msg(key,throttle=True):
 """Squad radio call through the shared dispatcher (msg_v42); `throttle` also keeps the squad's
 own calls at least 3.5 s apart."""
 end=uid('MSG_END')
 if throttle:s.get(19,b.SQ_MSG_NEXT);s.check(0x001d,[V(12),V(19)],end)
 say(s,key);a(0x0085,V(19),V(12));a(0x000a,V(19),I(3500));a(0xddc,I(b.SQ_MSG_NEXT),V(19));s.label(end)
def setk(k,f,var):a(0xddc,I(fk(k,f)),V(var))
def setk_lit(k,f,val):s.set(fk(k,f),val)
def later(k,ms):a(0x0085,V(31),V(12));a(0x000a,V(31),I(ms));setk(k,'NEXT',31)
def reset_slots():
 for k in range(4):
  setk_lit(k,'TASK',-1);setk_lit(k,'NEXT',0);setk_lit(k,'DEAD',0);setk_lit(k,'TGT',-1);setk_lit(k,'LT',0);setk_lit(k,'COVER',0)
def reset_threats():
 for i in range(4):s.set(PACE+i,-1);s.set(SQT+i,-1)
 s.set(b.SQ_THREATS,0);s.set(b.SQ_CONTACT,0);s.set(b.SQ_CLEAR_AT,0);s.set(b.SQ_CALLED,-1);a(0xddc,I(b.SQ_QUIET_T),V(12))

BG_AIM=[(0,15),(-15,3),(15,3),(0,-15)]
AS_AIM=[(0,18),(-12,12),(12,12),(0,-15)]
NEAR=[-6.,-3.,0.,3.,6.]
MID=[-27.,-18.,-9.,0.,9.,18.,27.]

s.label('INIT');a(0)
s.set(GROUP,0);s.set(TICK,0);s.set(b.SQ_MSG_NEXT,0);reset_threats();reset_slots()
s.label('LOOP');a(1,I(0));a(0x01bd,V(12));a(0xddc,I(HEART),V(12))
s.call('BRAIN_FRAME')                                    # every frame: the brain's word for each guard
s.get(19,TICK);s.check(0x801d,[V(19),V(12)],'LOOP')   # everything else ten times a second (due when the time HAS come: at 10 fps that is every frame)
a(0x0085,V(19),V(12));a(0x000a,V(19),I(100));a(0xddc,I(TICK),V(19))
s.check(0x0256,[I(0)],'RELEASE');s.get(19,b.STATE)
for st in [0,1,4,5,6,13]:
 nxt='STATE_OK_'+str(st);s.eq(19,st,nxt);s.go('RELEASE');s.label(nxt)
# 1.2: a model swap (state 16) only takes the helicopter's own crew away from the squad; the rope / escort team on the ground carries on
s.eq(19,16,'STATE_OK_16');s.get(19,b.SQ_ROPE);s.eq(19,1,'RELEASE');s.label('STATE_OK_16')
s.get(0,b.PUB);alive(0,'RELEASE');s.get(1,b.PUB+1)
s.get(19,b.SQ_ROPE);s.eq(19,1,'GROUP_NOT_ROPE');a(6,V(17),I(2))
for i in range(4):s.get(2+i,(b.GROUND_PUB2 if TEAM else b.GROUND_PUB)+i)
s.go('GROUP_SET')
s.label('GROUP_NOT_ROPE')
if TEAM:s.go('RELEASE')   # (the landed crew is four men: the first worker has them)
s.get(19,b.PHASE);s.eq(19,1,'RELEASE');a(6,V(17),I(1))
for i in range(4):s.get(2+i,b.PUB+3+i)
s.go('GROUP_SET')
s.label('RELEASE');a(6,V(17),I(0))
s.label('GROUP_SET');s.get(19,GROUP);s.check(0x803b,[V(17),V(19)],'GROUP_SAME')
a(0xddc,I(GROUP),V(17));reset_slots();reset_threats()
s.label('GROUP_SAME');s.eq(17,0,'GROUP_ACTIVE');s.go('LOOP')
s.label('GROUP_ACTIVE');a(0x00a0,V(0),V(9),V(10),V(11));a(6,V(6),I(-1));s.check(0x00df,[V(0)],'CJ_ON_FOOT');a(0x03c0,V(0),V(6));s.label('CJ_ON_FOOT')
# 1.2: CJ drives when the driver of his car (046C: the vehicle's driver pointer as a ped handle, the player included) is CJ himself.
# Asked every pass. (The first 1.2 beta guessed it from "every passenger seat is free when he gets in", which was wrong for a car
# that keeps a passenger: a jacked car, a mission companion.)
a(0xddc,I(b.SQ_CARH),V(6));s.set(b.SQ_DRIVES,0);s.eq(6,-1,'DRV_CHECK');s.go('DRV_DONE')
s.label('DRV_CHECK');a(0x046c,V(6),V(26));s.check(0x003b,[V(26),V(0)],'DRV_DONE');s.set(b.SQ_DRIVES,1)
s.label('DRV_DONE')
s.get(7,b.TACTICS)
# 1.5.3: CJ inside a building - the brain lays the detail out round the door he went in by (it never follows him into interior
# coordinates); the guards take those posts like any others. Only the catch-up by his footsteps is left out (see ON_FOOT).
(s.call('PERCEIVE') if not TEAM else a(6,V(18),I(0)))   # (the second four: no speech, no radio calls)
if not TEAM:s.call('PLAN')   # 2.0: the squad's task (said when it changes) and who walks the guards - the mod or these scripts (NATIVE, for both fours)
# each guard's man: the one the brain has him firing at (or holding fire on). A suspect he is only told to cover does not take him out
# of the formation.
for k in range(4):
 nx=uid('MAN');a(6,V(13+k),I(-1));s.get(19,BR_ST+k);s.check(0x0019,[V(19),I(1)],nx);s.get(13+k,BR_TG+k);s.label(nx);a(0xddc,I(SQT+k),V(13+k))
a(0x06ac,V(0),V(18))
for k in range(4):s.call('GUARD_%d'%k)
s.go('LOOP')

# ---------------------------------------------------------------- the brain, every frame
# 27@ = what this guard is to do (0 nothing, 1 cover the man, 2 fire, 3 cease fire now), 28@ = the man. A guard who is on a firing task
# and is told to cease fire gets an aiming task at once: the game's own weapon handling stops with the task that drove it.
s.label('BRAIN_FRAME');s.eq(17,0,'BF_GO');s.ret()
s.label('BF_GO');s.get(26,b.BRAIN_HELLO);s.check(0x0039,[V(26),I(b.BRAIN_MAGIC)],'BF_NONE')
for k in range(4):
 G=2+k;nxt=uid('BF_NEXT');hold=uid('BF_HOLD')
 a(0x0085,V(26),V(G));a(0x0e48,V(26),I(3),I(2));a(0xddc,I(BR_ST+k),V(27));a(0xddc,I(BR_TG+k),V(28))
 s.eq(27,3,nxt);s.get(29,fk(k,'TASK'))
 for task in (3,8,10,12):s.check(0x8039,[V(29),I(task)],hold)
 s.go(nxt)
 s.label(hold);alive(G,nxt);alive(28,nxt);a(0x00a0,V(28),V(29),V(30),V(31));a(0x0667,V(G),V(29),V(30),V(31),I(1000));setk_lit(k,'TASK',18);setk(k,'TGT',28);later(k,600)
 s.label(nxt)
s.ret()
s.label('BF_NONE')
for k in range(4):s.set(BR_ST+k,0);s.set(BR_TG+k,-1)
s.ret()

# ---------------------------------------------------------------- the brain's picture, ten times a second
# 24@ alert, 25@ threats, 26@ attackers, 27@ kills, 28@ the most dangerous man, 29@ ms since CJ fired (-1 = long ago), 30@/31@ the
# direction of that shot. Leaves 18@ = threats, 8@ = attackers, 13@ = the most dangerous man (-1 = none) for the radio calls.
s.label('PERCEIVE');s.get(19,b.BRAIN_HELLO);s.check(0x0039,[V(19),I(b.BRAIN_MAGIC)],'PV_NONE')
a(0x0e48,V(24),I(8),I(3))
a(0x0085,V(18),V(25));a(0x0085,V(8),V(26));a(6,V(13),I(-1));s.check(0x0019,[V(28),I(0)],'PV_STORE');a(0x0085,V(13),V(28));s.go('PV_STORE')
s.label('PV_NONE');a(6,V(18),I(0));a(6,V(8),I(0));a(6,V(13),I(-1))
s.label('PV_STORE');a(0xddc,I(b.SQ_THREATS),V(18));s.eq(18,0,'PS_BUSY');s.go('PS_STORE');s.label('PS_BUSY');a(0xddc,I(b.SQ_QUIET_T),V(12));s.label('PS_STORE')
# 1.4: the commander's words (the brain's protective detail): said once, when their number changes. The first look after a start only
# takes the number (a word said before the scripts started is not said again).
s.get(19,b.BRAIN_HELLO);s.check(0x0039,[V(19),I(b.BRAIN_MAGIC)],'SAY_DONE')
a(0x0e48,V(23),I(9),I(5))   # 23@ number, 24@ what (HCB_SAY_*), 25@ direction from CJ (0 ahead, 1 right, 2 behind, 3 left), 26@ duty, 27@ cover ok, 28-30@ CJ's cover, 31@ commander
s.get(19,b.SQ_SAY_SEQ);s.check(0x003b,[V(19),V(23)],'SAY_NEW');s.go('SAY_DONE')
s.label('SAY_NEW');a(0xddc,I(b.SQ_SAY_SEQ),V(23));s.eq(19,-1,'SAY_WHAT');s.go('SAY_DONE')
s.label('SAY_WHAT')
for what,keys in [(1,['SQGO'+d for d in 'FRBL']),(2,['SQSAFE']),(3,['SQME'+d for d in 'FRBL']),(4,['SQEVAC']),(5,['SQCMD']),(6,['SQCLR']),(7,['SQS'+d for d in 'FRBL']),(8,['SQMEM']),(9,['SQG'+d for d in 'FRBL']),(10,['SQWATER']),(11,['SQAHEAD']),(12,['SQK'+d for d in 'FRBL'])]:   # 1.5.4: 12 a car on a collision course   # 1.5.3: 9 grenade, 10 CJ in the water, 11 armed men ahead   # 1.5.2: 7 sniper, 8 a place where the detail was attacked before
 nw=uid('SAY_W');s.eq(24,what,nw)
 if len(keys)==1:
  msg(keys[0],False)
  if what==4 and not TEAM:
   # 1.5.3, the hot pickup: "we pull out" is also the order to the pilot - while the helicopter escorts CJ (state 2) and CJ is on
   # foot, the rope pickup is asked for at once (the same command as CLIMB ABOARD BY ROPE on the menu); CJ only has to take the rope
   s.get(19,b.STATE);s.eq(19,2,'SAY_DONE');s.check(0x80df,[V(0)],'SAY_DONE');s.get(19,b.CMD);s.eq(19,0,'SAY_DONE');s.set(b.CMD_SRC,2);s.set(b.CMD,10)
  s.go('SAY_DONE')
 else:
  for d,key in enumerate(keys):
   nd=uid('SAY_D');s.eq(25,d,nd);msg(key,False);s.go('SAY_DONE');s.label(nd)
  s.go('SAY_DONE')
 s.label(nw)
s.label('SAY_DONE')
# radio calls: kind and direction of the first contact, of every new most dangerous man who is attacking (throttled),
# and "area secure" 3.5 s after the last threat
s.eq(18,0,'CALL_CONTACT')
s.get(19,b.SQ_CONTACT);s.eq(19,1,'CALL_RET');s.get(19,b.SQ_CLEAR_AT);s.eq(19,0,'CALL_CLEAR_CHECK');a(0x0085,V(19),V(12));a(0x000a,V(19),I(3500));a(0xddc,I(b.SQ_CLEAR_AT),V(19));s.ret()
s.label('CALL_CLEAR_CHECK');s.check(0x001d,[V(12),V(19)],'CALL_RET');s.set(b.SQ_CONTACT,0);s.set(b.SQ_CLEAR_AT,0);s.set(b.SQ_CALLED,-1);s.ret()   # (1.4: "clear" is the commander's word)
s.label('CALL_CONTACT');s.set(b.SQ_CLEAR_AT,0);s.get(19,b.SQ_CONTACT);s.eq(19,0,'CALL_NEW_TOP');s.set(b.SQ_CONTACT,1);a(6,V(26),I(0));s.go('CALL_ANNOUNCE')
s.label('CALL_NEW_TOP');s.get(19,b.SQ_CALLED);s.check(0x803b,[V(13),V(19)],'CALL_RET');s.check(0x0019,[V(8),I(0)],'CALL_RET');s.get(19,b.SQ_MSG_NEXT);s.check(0x001d,[V(12),V(19)],'CALL_RET');a(6,V(26),I(1))
s.label('CALL_ANNOUNCE');alive(13,'CALL_RET');a(0xddc,I(b.SQ_CALLED),V(13))
# kind (27@): 0 plain, 1 shooting at CJ, 2 sniper, 3 vehicle, 4 roof
a(6,V(27),I(0));a(0x0470,V(13),V(19));s.check(0x0019,[V(19),I(32)],'KIND_NOT_S');s.check(0x0019,[V(19),I(34)],'KIND_S');s.go('KIND_NOT_S');s.label('KIND_S');a(6,V(27),I(2));s.go('KIND_DONE')
s.label('KIND_NOT_S');s.check(0x00df,[V(13)],'KIND_NOT_V');a(6,V(27),I(3));s.go('KIND_DONE')
s.label('KIND_NOT_V');a(0x00a0,V(13),V(20),V(21),V(22));a(0x0063,V(22),V(11));s.check(0x0021,[V(22),F(6)],'KIND_NOT_R');a(6,V(27),I(4));s.go('KIND_DONE')
s.label('KIND_NOT_R');s.check(0x0019,[V(8),I(0)],'KIND_DONE');a(6,V(27),I(1))   # somebody is attacking: "shots at CJ"
s.label('KIND_DONE')
# direction (28@) of the threat relative to CJ's heading: 0 front, 1 left, 2 rear, 3 right
a(0x00a0,V(13),V(20),V(21),V(22));a(0x0063,V(20),V(9));a(0x0063,V(21),V(10));a(0x0604,V(20),V(21),V(29));a(0x0172,V(0),V(30));a(0x0063,V(29),V(30))
s.check(0x0023,[F(0),V(29)],'DIR_POS');a(0x000b,V(29),F(360))
s.label('DIR_POS');s.check(0x0023,[F(360),V(29)],'DIR_WRAP');s.go('DIR_READY')
s.label('DIR_WRAP');a(0x000b,V(29),F(-360))
s.label('DIR_READY');a(6,V(28),I(0))
for lim,d in [(45,0),(135,1),(225,2),(315,3)]:
 nxt=uid('DIR_NEXT');s.check(0x0023,[F(lim),V(29)],nxt);a(6,V(28),I(d));s.go('DIR_SET');s.label(nxt)
s.label('DIR_SET')
s.eq(26,0,'CALL_THROTTLED')
def call_table(prefix,throttle):
 for kind in range(5):
  nk=uid(prefix+'K');s.eq(27,kind,nk)
  for d,letter in enumerate('FLBR'):
   nd=uid(prefix+'D');s.eq(28,d,nd)
   if kind==0:
    bg=uid(prefix+'BG');s.eq(7,1,bg);msg('SQA'+letter,throttle);s.ret();s.label(bg);msg('SQC'+letter,throttle);s.ret()
   else:msg('SQ'+'XSVR'[kind-1]+letter,throttle);s.ret()
   s.label(nd)
  s.ret();s.label(nk)
 s.ret()
call_table('CT0_',False)
s.label('CALL_THROTTLED');call_table('CT1_',True)
s.label('CALL_RET');s.ret()
# ---------------------------------------------------------------- 2.0: the squad's plan (0E48, command 7)
# 21@ mode (0 PROTECT, 1 ASSAULT), 22@ task (HCB_TASK_*), 23@ a roof for the marksman, 24@ the helicopter is over it, 25-27@ the roof,
# 28@ metres to the target, 29@ men on the move, 30@ 1 = the mod walks the guards itself. Keeps 8@, 13@, 18@.
if not TEAM:
 s.label('PLAN');s.get(19,b.BRAIN_HELLO);s.check(0x0039,[V(19),I(b.BRAIN_MAGIC)],'PLAN_NONE')
 a(0x0e48,V(21),I(10),I(7));a(0xddc,I(b.NATIVE),V(30))
 s.get(19,b.SQ_TASK_SAID);s.check(0x003b,[V(19),V(22)],'PLAN_NEW');s.ret()
 s.label('PLAN_NEW');a(0xddc,I(b.SQ_TASK_SAID),V(22))
 for task,key in [(3,'SQTAP'),(5,'SQTBD'),(6,'SQTSR'),(7,'SQTCN'),(9,'SQTWD')]:
  nx=uid('PLAN_T');s.eq(22,task,nx);msg(key,False);s.ret();s.label(nx)
 # "back to CJ" only after an assault task (3-7, 9), not at the first look
 s.eq(22,8,'PLAN_RET');s.check(0x0019,[V(19),I(2)],'PLAN_RET');s.eq(19,8,'PLAN_BACK');s.ret()
 s.label('PLAN_BACK');msg('SQTRG',False)
 s.label('PLAN_RET');s.ret()
 s.label('PLAN_NONE');s.set(b.NATIVE,0);s.ret()
# ---------------------------------------------------------------- one guard
def post_spot(G,fail):
 """26-28@ = this guard's post from the brain (cmd 4); `fail` when the brain has none for him (or no handshake)."""
 s.get(31,b.BRAIN_HELLO);s.check(0x0039,[V(31),I(b.BRAIN_MAGIC)],fail)
 a(0x0085,V(21),V(G));a(0x0e48,V(21),I(10),I(4));s.check(0x8039,[V(22),I(-1)],fail)
 a(0x0087,V(26),V(23));a(0x0087,V(27),V(24));a(0x0087,V(28),V(25))
import build_v25_ground as _gr
import build_v25_team2 as _t2
GUNS=[w_ for w_,_m in (_t2.WEAPONS if TEAM else _gr.TEAM_WEAPONS)]   # each guard's own gun, to put back in his hands after a fist fight
def same_order(k,task,target_var,issue):
 """Return from the guard routine while the guard already runs `task` on target_var and the order
 has not expired; otherwise continue at `issue` (placed right after this call)."""
 s.get(31,fk(k,'TASK'));s.eq(31,task,issue);s.get(31,fk(k,'TGT'));s.check(0x003b,[V(31),V(target_var)],issue);s.get(31,fk(k,'NEXT'));s.check(0x001d,[V(12),V(31)],'G%d_RET'%k)
def order(k,task,target_var,ms):setk_lit(k,'TASK',task);setk(k,'TGT',target_var);later(k,ms);s.ret()
def same_post(k,task,issue):
 """1.4: return from the guard routine while he already runs `task` at the man in 21@ towards the spot 23/24@ (within a metre) and
 the order has not run out; otherwise continue at `issue` (placed right after this call)."""
 drift=uid('POST_DRIFT')
 s.get(31,fk(k,'TASK'));s.eq(31,task,issue);s.get(31,fk(k,'TGT'));s.check(0x003b,[V(31),V(21)],issue);s.get(31,PACE+k);s.check(0x003b,[V(31),V(22)],issue)
 s.get(31,fk(k,'NEXT'));s.check(0x001d,[V(12),V(31)],drift);s.go(issue)
 s.label(drift);s.get(19,fk(k,'TX'));s.get(31,fk(k,'TY'));a(0x0509,V(23),V(24),V(19),V(31),V(19));s.check(0x0021,[V(19),F(1.0)],'G%d_RET'%k)
 s.label(issue)
def pace(var):
 """The game's move state for the post's pace in 22@ (1 walk -> 4, 2 run -> 6, 3 sprint -> 7) into `var`."""
 a(6,V(var),I(4));n2=uid('PACE');s.eq(22,2,n2);a(6,V(var),I(6));s.label(n2);n3=uid('PACE');s.eq(22,3,n3);a(6,V(var),I(7));s.label(n3)
def guard(k):
 G=2+k;P='G%d_'%k;R=P+'RET'
 s.label('GUARD_%d'%k);s.check(0x056d,[V(G)],R);s.check(0x8118,[V(G)],P+'DEAD')
 s.check(0x8a32,[V(G)],R);a(0x0819,V(G),V(21));s.check(0x0023,[F(2.5),V(21)],R)
 s.get(21,fk(k,'TASK'));s.eq(21,-1,P+'READY')
 a(0x081a,V(G),I(2));a(0x02e2,V(G),I(80));a(0x07dd,V(G),I(80));a(0x0856,V(G),I(1));setk_lit(k,'TASK',0);setk_lit(k,'NEXT',0);setk_lit(k,'DEAD',0);setk(k,'LT',12)
 a(0x00a0,V(G),V(21),V(22),V(23));setk(k,'LX',21);setk(k,'LY',22)
 s.label(P+'READY');a(0x00a0,V(G),V(21),V(22),V(23));a(0x050a,V(21),V(22),V(23),V(9),V(10),V(11),V(24))
 # ---- CJ in a vehicle: ride along when there is a free seat, never chase a car that drives away
 s.eq(6,-1,P+'VEH');s.go(P+'FOOT')
 s.label(P+'VEH');s.check(0x803b,[V(6),V(1)],R);s.check(0x80db,[V(G),V(6)],P+'RIDING')
 s.get(25,b.SQ_DRIVES);s.eq(25,1,R)   # 1.2: only a car CJ drives himself (a taxi / bus / somebody else's car is not boarded)
 a(0x02e3,V(6),V(25));s.check(0x0021,[V(25),F(6)],P+'VEH_SLOW');s.check(0x0021,[V(24),F(10)],P+'VEH_SLOW');s.ret()
 s.label(P+'VEH_SLOW');s.get(25,fk(k,'TASK'));s.eq(25,4,P+'VEH_ISSUE');s.get(25,fk(k,'NEXT'));s.check(0x001d,[V(12),V(25)],R)
 s.label(P+'VEH_ISSUE');a(0x01ea,V(6),V(26))
 # 1.2: guard k takes passenger seat k (the old rotation sent guards 0 and 3 to the same seat); no seat, no ride
 nxt=uid(P+'SEAT');s.check(0x0019,[V(26),I(k)],nxt);s.check(0x0431,[V(6),I(k)],nxt);a(0x05ca,V(G),V(6),I(8000),I(k));setk_lit(k,'TASK',4);later(k,3000)
 if k==0:msg('SQCAR')
 s.ret();s.label(nxt)
 s.ret()
 s.label(P+'RIDING');setk_lit(k,'TASK',5);s.ret()
 # ---- CJ on foot: get out of any car first
 s.label(P+'FOOT');s.check(0x00df,[V(G)],P+'ON_FOOT');s.get(25,fk(k,'TASK'));s.eq(25,6,P+'LEAVE');s.get(25,fk(k,'NEXT'));s.check(0x001d,[V(12),V(25)],R)
 s.label(P+'LEAVE');a(0x0633,V(G));setk_lit(k,'TASK',6);later(k,2500);s.ret()
 # ---- 1.2: far behind (40 m+): run to the slot on the path network. Never a teleport: a guard who cannot catch up
 # lags, and the ground worker stands the team down after 60 s (SQ_LAG).
 # ---- 1.5: left behind (22 m+ from CJ, counting the height - he went up a stair, onto a bridge, round a block): the man
 # follows CJ's own footsteps (the game's follower task, the one mission companions use), the way CJ really went, until he is
 # within 10 m again; then the brain's posts apply as before. (1.2 sent him by the path network at 40 m: in the canal under
 # the bridge the whole detail stood 60-80 m away for half a minute - the third whole-game log.) Never a teleport.
 s.label(P+'ON_FOOT');a(0x077e,V(25));s.eq(25,0,P+'NEAR')   # (CJ is inside a building: no following him - the post at the door)
 s.get(25,b.NATIVE);s.eq(25,0,P+'NEAR')   # 2.0: the mod walks him - from any distance, by the brain's way (in ASSAULT his place is far from CJ on purpose)
 s.check(0x0021,[V(24),F(22)],P+'FS_NEAR');s.get(25,fk(k,'TASK'));s.eq(25,13,P+'FS_ISSUE');s.get(25,fk(k,'NEXT'));s.check(0x001d,[V(12),V(25)],R)
 s.label(P+'FS_ISSUE');a(0x0850,V(G),V(0));setk_lit(k,'TASK',13);later(k,4000);s.ret()
 s.label(P+'FS_NEAR');s.get(25,fk(k,'TASK'));s.eq(25,13,P+'NEAR');s.check(0x0021,[V(24),F(10)],P+'FS_DONE');s.ret()
 s.label(P+'FS_DONE');setk_lit(k,'TASK',0)
 # ---- stuck check every 2.5 s: moving, far, and barely moved
 # 2.0: while the mod walks the guards (NATIVE) the scripts' own stuck check, path-network detour and vault are not used: the brain's map
 # finds the way and the mod's task takes him there
 s.label(P+'NEAR');s.get(25,b.NATIVE);s.eq(25,0,P+'VAULT_DONE');s.get(25,fk(k,'LT'));a(0x0085,V(26),V(12));a(0x0062,V(26),V(25));s.check(0x0019,[V(26),I(2500)],P+'STUCK_DONE')
 s.get(26,fk(k,'LX'));s.get(27,fk(k,'LY'));a(0x0509,V(21),V(22),V(26),V(27),V(28));setk(k,'LX',21);setk(k,'LY',22);setk(k,'LT',12)
 s.check(0x0021,[V(24),F(9)],P+'STUCK_DONE');s.check(0x0023,[F(.7),V(28)],P+'STUCK_DONE');s.get(25,fk(k,'TASK'));s.eq(25,1,P+'STUCK_T12');s.go(P+'STUCK_YES');s.label(P+'STUCK_T12');s.eq(25,12,P+'STUCK_DONE');s.label(P+'STUCK_YES')
 post_spot(G,R);a(0x05f5,V(G),V(26),V(27),V(28),I(6),I(15000));setk_lit(k,'TASK',7);later(k,3000);s.ret()   # 1.2: re-path, no teleport
 s.label(P+'STUCK_DONE');s.get(25,fk(k,'TASK'));s.eq(25,7,P+'NOT_PATHING');s.get(25,fk(k,'NEXT'));s.check(0x001d,[V(12),V(25)],R)
 s.label(P+'NOT_PATHING');s.get(25,fk(k,'TASK'));s.eq(25,11,P+'NOT_CLIMBING');s.get(25,fk(k,'NEXT'));s.check(0x001d,[V(12),V(25)],R)
 s.label(P+'NOT_CLIMBING');s.get(25,fk(k,'TASK'));s.eq(25,1,P+'VAULT_T12');s.go(P+'VAULT_PROBE');s.label(P+'VAULT_T12');s.eq(25,12,P+'VAULT_DONE')
 s.label(P+'VAULT_PROBE');s.get(26,fk(k,'TX'));s.get(27,fk(k,'TY'));a(0x0087,V(29),V(26));a(0x0063,V(29),V(21));a(0x0087,V(30),V(27));a(0x0063,V(30),V(22));a(0x0509,V(21),V(22),V(26),V(27),V(31));s.check(0x0021,[V(31),F(2)],P+'VAULT_DONE')
 a(0x0073,V(29),V(31));a(0x0073,V(30),V(31))
 for dist,height,ok in [(1.3,-.55,None),(1.3,1.0,P+'VAULT_DONE'),(2.6,1.0,P+'VAULT_DONE')]:
  a(0x0087,V(26),V(29));a(0x0013,V(26),F(dist));a(0x005b,V(26),V(21));a(0x0087,V(27),V(30));a(0x0013,V(27),F(dist));a(0x005b,V(27),V(22));a(0x0087,V(31),V(23));a(0x000b,V(31),F(height))
  if ok is None:s.check(0x06bd,[V(21),V(22),V(31),V(26),V(27),V(31),I(1),I(0),I(0),I(1),I(0)],P+'VAULT_LOW');s.go(P+'VAULT_DONE');s.label(P+'VAULT_LOW')
  else:s.check(0x06bd,[V(21),V(22),V(31),V(26),V(27),V(31),I(1),I(0),I(0),I(1),I(0)],ok)
 # stairs or a slope (ground 2.6 m ahead more than 0.6 m above his feet) are walked, not vaulted
 a(0x0087,V(28),V(23));a(0x000b,V(28),F(2));a(0x02ce,V(26),V(27),V(28),V(28));a(0x0087,V(31),V(23));a(0x000b,V(31),F(-.4));s.check(0x8025,[V(28),V(31)],P+'VAULT_DONE')
 a(0x0604,V(29),V(30),V(31));a(0x0173,V(G),V(31));a(0x04eb,V(G),I(0));a(0x078f,V(G),I(1));setk_lit(k,'TASK',11);later(k,1800);s.ret()
 s.label(P+'VAULT_DONE')
 # ---- 1.4: the protective detail. The brain gives each guard his post - where to be, how fast to get there, standing or crouched,
 # where to look - and the fire order (BRAIN_FRAME: SQ_BR_ST, the man). This is only the body: go, crouch, aim, fire.
 s.get(31,b.BRAIN_HELLO);s.check(0x0039,[V(31),I(b.BRAIN_MAGIC)],R)   # never the opcode before the handshake (CLEO would run its parameters as code)
 a(0x0085,V(21),V(G));a(0x0e48,V(21),I(10),I(4))   # 22@ move (-1 no post, 0 stay, 1 walk, 2 run, 3 sprint), 23-25@ the spot, 26@ crouch, 27-29@ look, 30@ duty
 s.check(0x8039,[V(22),I(-1)],R)                     # no post (the brain does not have him): nothing new
 a(0x00a0,V(G),V(19),V(20),V(31));a(0x0509,V(19),V(20),V(23),V(24),V(19))   # 19@ how far he is from his spot
 s.get(20,BR_ST+k);s.get(21,BR_TG+k)       # 20@ 0 nothing / 1 cover / 2 fire / 3 his man, no fire / 5 by hand; 21@ the man (-1 none)
 # 1.5.3, proportionate force: an unarmed man on foot - the brain says "by hand" (5). The guard puts his gun away (fists in his
 # hands, the gun stays his) and goes for the man; when it is over (any other state) the gun is back in his hands.
 nofist=uid(P+'NOFIST');rearmed=uid(P+'REARMED');s.eq(20,5,nofist);alive(21,nofist)
 issue=uid(P+'FIST');same_order(k,19,21,issue);s.label(issue);a(0x04eb,V(G),I(0));a(0x01b9,V(G),I(0));a(0x05e2,V(G),V(21));setk_lit(k,'COVER',0);order(k,19,21,3000)
 s.label(nofist);s.get(31,fk(k,'TASK'));s.eq(31,19,rearmed);a(0x01b9,V(G),I(GUNS[k]));setk_lit(k,'TASK',0)
 s.label(rearmed)
 s.eq(22,0,P+'GO');s.go(P+'AT')
 s.label(P+'GO');s.check(0x0021,[V(19),F(.9)],P+'AT')
 # 2.0: move 5 = the mod has his legs (its own go-to task, given once). The script only stands him up once and keeps its hands off
 nat=uid(P+'NAT');natn=uid(P+'NATN');s.eq(22,5,nat);s.get(31,fk(k,'TASK'));s.eq(31,20,natn);s.ret()
 s.label(natn);a(0x04eb,V(G),I(0));setk_lit(k,'TASK',20);setk_lit(k,'COVER',0);s.ret()
 s.label(nat)
 # 1.4.1: the brain says he has not got nearer for a while (move 4): the game's path network takes him round
 nopath=uid(P+'NOPATH');s.eq(22,4,nopath);issue=uid(P+'PATH');same_post(k,7,issue)   # (same_post places the label)
 a(0x05f5,V(G),V(23),V(24),V(25),I(6),I(15000));setk(k,'TX',23);setk(k,'TY',24);setk_lit(k,'COVER',0);a(0xddc,I(PACE+k),V(22));order(k,7,21,3000)
 s.label(nopath)
 # ---- on his way: run (walk, sprint) to the spot; with the brain's leave he fires as he goes
 run=P+'RUN';walk=P+'WALK'
 s.check(0x0039,[V(20),I(2)],walk);alive(21,walk)
 same_post(k,12,run);a(0x04eb,V(G),I(0));pace(31)
 a(0x0637,V(G),V(23),V(24),V(25),V(31),F(.5),F(1.0),V(21));setk(k,'TX',23);setk(k,'TY',24);setk_lit(k,'COVER',0);a(0xddc,I(PACE+k),V(22));order(k,12,21,1200)
 s.label(walk);same_post(k,1,P+'WALK_GO');a(0x04eb,V(G),I(0));pace(31)
 a(0x05d3,V(G),V(23),V(24),V(25),V(31),I(20000));setk(k,'TX',23);setk(k,'TY',24);setk_lit(k,'COVER',0);a(0xddc,I(PACE+k),V(22));order(k,1,21,1500)
 # ---- at his spot: crouched or standing as the post says (crouched in cover the game's own duck-and-fire takes over)
 s.label(P+'AT');s.get(31,fk(k,'COVER'));s.check(0x003b,[V(31),V(26)],P+'CR_SET');s.go(P+'CR_OK')
 s.label(P+'CR_SET');a(0x04eb,V(G),V(26));setk(k,'COVER',26)
 # 2.0 beta 2: state 6 = his weapon is the mod's (one gun task of the game's, commanded every look): the script gives him no aim or fire task
 s.label(P+'CR_OK');mine=uid(P+'GUN');s.eq(20,6,mine);setk_lit(k,'TASK',21);s.ret();s.label(mine)
 s.check(0x0039,[V(20),I(2)],P+'NO_FIRE');alive(21,P+'NO_FIRE')
 s.eq(26,1,P+'FIRE_STAND')
 issue=uid(P+'DUCK');same_order(k,8,21,issue);s.label(issue);a(0x0634,V(G),V(21),I(1),I(1000),I(60));order(k,8,21,2500)
 s.label(P+'FIRE_STAND');issue=uid(P+'SHOOT');same_order(k,3,21,issue);s.label(issue);a(0x074d,V(G),V(21),I(1500));order(k,3,21,1200)
 # his man, no fire (or a suspect to cover): the weapon on him
 s.label(P+'NO_FIRE');s.check(0x0019,[V(20),I(0)],P+'LOOK');alive(21,P+'LOOK')
 issue=uid(P+'HOLD');same_order(k,18,21,issue);s.label(issue);a(0x00a0,V(21),V(27),V(28),V(29));a(0x0667,V(G),V(27),V(28),V(29),I(1000));order(k,18,21,600)
 # nobody to fire at or cover: on alert his weapon on his sector (renewed every 2.4 s), in peace at ease
 s.label(P+'LOOK');s.eq(30,0,P+'SECTOR')
 s.get(31,fk(k,'TASK'));s.eq(31,16,P+'EASE');s.ret()
 s.label(P+'EASE');setk_lit(k,'TASK',16);later(k,5000);s.ret()
 s.label(P+'SECTOR');s.get(31,fk(k,'TASK'));s.eq(31,2,P+'SECTOR_GO');s.get(31,fk(k,'NEXT'));s.check(0x001d,[V(12),V(31)],R)
 s.label(P+'SECTOR_GO');a(0x0667,V(G),V(27),V(28),V(29),I(2600));setk_lit(k,'TASK',2);later(k,2400);s.ret()
 # ---- casualty report (once per guard)
 s.label(P+'DEAD');s.get(25,fk(k,'DEAD'));s.eq(25,0,R);s.get(25,fk(k,'TASK'));s.eq(25,-1,P+'DEAD_NEW');s.ret()
 s.label(P+'DEAD_NEW');setk_lit(k,'DEAD',1);msg('SQDOWN',False)
 s.label(R);s.ret()
for k in range(4):guard(k)

TEXTS={'SQXF': '~r~SHOTS AT CJ - FRONT!~w~ Covering him.',
 'SQSF': '~r~SNIPER - FRONT!~w~ Keep CJ in cover.',
 'SQVF': '~r~CAR INCOMING - FRONT!~w~ Hitting the driver.',
 'SQRF': '~r~ROOF - FRONT!~w~ Shooter up high.',
 'SQCF': '~r~CONTACT FRONT!~w~ Squad engaging.',
 'SQAF': '~r~CONTACT FRONT!~w~ Assault - moving up.',
 'SQXL': '~r~SHOTS AT CJ - LEFT!~w~ Covering him.',
 'SQSL': '~r~SNIPER - LEFT!~w~ Keep CJ in cover.',
 'SQVL': '~r~CAR INCOMING - LEFT!~w~ Hitting the driver.',
 'SQRL': '~r~ROOF - LEFT!~w~ Shooter up high.',
 'SQCL': '~r~CONTACT LEFT!~w~ Squad engaging.',
 'SQAL': '~r~CONTACT LEFT!~w~ Assault - moving up.',
 'SQXB': '~r~SHOTS AT CJ - REAR!~w~ Covering him.',
 'SQSB': '~r~SNIPER - REAR!~w~ Keep CJ in cover.',
 'SQVB': '~r~CAR INCOMING - REAR!~w~ Hitting the driver.',
 'SQRB': '~r~ROOF - REAR!~w~ Shooter up high.',
 'SQCB': '~r~CONTACT REAR!~w~ Squad engaging.',
 'SQAB': '~r~CONTACT REAR!~w~ Assault - moving up.',
 'SQXR': '~r~SHOTS AT CJ - RIGHT!~w~ Covering him.',
 'SQSR': '~r~SNIPER - RIGHT!~w~ Keep CJ in cover.',
 'SQVR': '~r~CAR INCOMING - RIGHT!~w~ Hitting the driver.',
 'SQRR': '~r~ROOF - RIGHT!~w~ Shooter up high.',
 'SQCR': '~r~CONTACT RIGHT!~w~ Squad engaging.',
 'SQAR': '~r~CONTACT RIGHT!~w~ Assault - moving up.',
 'SQCLR': '~g~SQUAD:~w~ area secure, regrouping on CJ.',
 'SQDOWN': '~r~MAN DOWN!~w~ We lost one.',
 'SQCAR': '~g~SQUAD:~w~ mounting up.',
 'SQEVAC': '~r~TOO HOT!~w~ We pull out - the helicopter is coming with the rope.',
 'SQGOF': '~g~ALPHA:~w~ CJ, follow me! Cover straight ahead - run to me.',
 'SQGOR': '~g~ALPHA:~w~ CJ, follow me! Cover on your right - run to me.',
 'SQGOB': '~g~ALPHA:~w~ CJ, follow me! Cover behind you - run to me.',
 'SQGOL': '~g~ALPHA:~w~ CJ, follow me! Cover on your left - run to me.',
 'SQMEF': '~g~ALPHA:~w~ no cover here - stay by your guard, move ahead!',
 'SQMER': '~g~ALPHA:~w~ no cover here - stay by your guard, move right!',
 'SQMEB': '~g~ALPHA:~w~ no cover here - stay by your guard, fall back!',
 'SQMEL': '~g~ALPHA:~w~ no cover here - stay by your guard, move left!',
 'SQSAFE': '~g~ALPHA:~w~ CJ is in cover. Stay there, we work.',
 'SQMEM': '~y~ALPHA:~w~ we were attacked here before. Eyes open.',
 'SQGF': '~r~GRENADE - FRONT!~w~ Get away from it!', 'SQGR': '~r~GRENADE - RIGHT!~w~ Get away from it!', 'SQGB': '~r~GRENADE - BEHIND!~w~ Get away from it!', 'SQGL': '~r~GRENADE - LEFT!~w~ Get away from it!',
 'SQWATER': '~y~ALPHA:~w~ CJ in the water - helicopter over you, take the rope.',
 'SQAHEAD': '~y~PILOT:~w~ armed men ahead on your way.',
 'SQKF': '~r~CAR - FRONT!~w~ Get out of its way!', 'SQKR': '~r~CAR - RIGHT!~w~ Get out of its way!', 'SQKB': '~r~CAR - BEHIND!~w~ Get out of its way!', 'SQKL': '~r~CAR - LEFT!~w~ Get out of its way!',
 'SQCMD': '~r~ALPHA DOWN!~w~ BRAVO: I have command.',
 'SQTAP': '~r~ALPHA:~w~ target marked. Moving up - stay behind us.',
 'SQTBD': '~r~ALPHA:~w~ fire team, cover! Pairs - bound!',
 'SQTSR': '~y~ALPHA:~w~ lost him. Searching where he was.',
 'SQTCN': '~g~ALPHA:~w~ target down. All-round watch.',
 'SQTRG': '~g~ALPHA:~w~ done here. Back to CJ.',
 'SQTWD': '~r~ALPHA:~w~ too many down - falling back!'}
if __name__=='__main__':
 report=s.build('Helicover_Squad2' if TEAM else 'Helicover_Squad','csa');print(report)
 with (OUT/'validation.txt').open('a') as validation:validation.write(report+'\n')
 if not TEAM:
  with (OUT/'Helicover.fxt').open('a') as f:f.write(''.join(k+' '+v+'\n' for k,v in TEXTS.items()))
