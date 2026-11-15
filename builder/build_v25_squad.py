"""Helicover v40 tactical squad AI (Helicover_Squad.csa).

One worker drives whichever team is on foot: the rope / escort team of the ground worker
(GROUND_PUB, while SQ_ROPE = 1) or the helicopter crew after an evacuation landing (PUB+3..6,
while PHASE = 1). The core, ground and fire workers stop tasking those guards while SQ_HEART is
fresh, so exactly one script gives them orders.

Every 100 ms: perception every 400 ms (threats around CJ, rules of engagement from FIRE CONTROL),
then a decision for each of the four guards. Tasks are only re-issued when the order changes or
its time runs out, so the game AI is never restarted every tick.

Tactics (SETUP > TEAM ON FOOT): 0 BODYGUARD - tight diamond, two shields step between CJ and the
threat, two engage on a short leash; 1 ASSAULT - wide wedge, one pair advances crouched, the other
flanks. When CJ is badly hurt everyone forms a ring around him. The rear guard is the medic.

Registers: 0 CJ, 1 heli, 2-5 guards, 6 CJ car/-1, 7 tactics, 8 fire mode, 9-11 CJ xyz, 12 now,
13-16 threats, 17 group, 18 threat count (perception) / CJ speed (guards), 19 message scratch,
20 move speed, 21-23 guard xyz, 24 guard-CJ distance, 25 target, 26-31 scratch.
"""
from asm_v25 import *
import build_v25 as b
from msg_v42 import say
from threat_v41 import emit_score,SHOOTER_FRESH_MS,SCORE_FOCUS
s=Script();a=s.add
FIELDS={'TASK':0,'NEXT':1,'TX':2,'TY':3,'LX':4,'LY':5,'LT':6,'DEAD':7,'TGT':8,'COVER':9}
# TASK values: -1 not set up, 0 idle, 1 moving, 2 sector watch, 3 shooting, 4 entering car,
# 5 riding, 6 leaving car, 7 path-node move, 8 crouched assault, 9 medic, 10 timed attack,
# 11 climbing an obstacle, 12 moving while shooting, 13 turning to the sector (assault),
# 15 reload drill, 16 relaxed (quiet), 17 suppressive fire at the last seen spot
def fk(k,f):return b.SQ_SLOT+k*b.SQ_SLOT_SIZE+FIELDS[f]
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
 for i in range(4):s.set(b.SQ_T+i,-1);s.set(b.SQ_SC+i,-10000);s.set(b.CV_T+i,0);s.set(b.CV_OK+i,0);s.set(b.ENG_T+i,0)
 s.set(b.SQ_THREATS,0);s.set(b.SQ_CONTACT,0);s.set(b.SQ_CLEAR_AT,0);s.set(b.SQ_CALLED,-1);s.set(b.SQ_EVAC_NEXT,0);s.set(b.SQ_CV_TICK,-1);a(0xddc,I(b.SQ_QUIET_T),V(12))

BG_FORM=[(0,3.2),(-2.4,.6),(2.4,.6),(0,-2.8)]
AS_FORM=[(0,7.0),(-5.0,3.0),(5.0,3.0),(0,-4.5)]
BG_AIM=[(0,15),(-15,3),(15,3),(0,-15)]
AS_AIM=[(0,18),(-12,12),(12,12),(0,-15)]
NEAR=[-6.,-3.,0.,3.,6.]
MID=[-27.,-18.,-9.,0.,9.,18.,27.]

s.label('INIT');a(0)
s.set(b.SQ_GROUP,0);s.set(b.SQ_SCAN_NEXT,0);s.set(b.SQ_MSG_NEXT,0);s.set(b.SQ_MEDIC_NEXT,0);reset_threats();reset_slots()
s.label('LOOP');a(1,I(100));a(0x01bd,V(12));a(0xddc,I(b.SQ_HEART),V(12))
s.check(0x0256,[I(0)],'RELEASE');s.get(19,b.STATE)
for st in [0,1,4,5,6,13]:
 nxt='STATE_OK_'+str(st);s.eq(19,st,nxt);s.go('RELEASE');s.label(nxt)
# 1.2: a model swap (state 16) only takes the helicopter's own crew away from the squad; the rope / escort team on the ground carries on
s.eq(19,16,'STATE_OK_16');s.get(19,b.SQ_ROPE);s.eq(19,1,'RELEASE');s.label('STATE_OK_16')
s.get(0,b.PUB);alive(0,'RELEASE');s.get(1,b.PUB+1)
s.get(19,b.SQ_ROPE);s.eq(19,1,'GROUP_NOT_ROPE');a(6,V(17),I(2))
for i in range(4):s.get(2+i,b.GROUND_PUB+i)
s.go('GROUP_SET')
s.label('GROUP_NOT_ROPE');s.get(19,b.PHASE);s.eq(19,1,'RELEASE');a(6,V(17),I(1))
for i in range(4):s.get(2+i,b.PUB+3+i)
s.go('GROUP_SET')
s.label('RELEASE');a(6,V(17),I(0))
s.label('GROUP_SET');s.get(19,b.SQ_GROUP);s.check(0x803b,[V(17),V(19)],'GROUP_SAME')
a(0xddc,I(b.SQ_GROUP),V(17));reset_slots();reset_threats();s.set(b.FORM_OK,0)
s.label('GROUP_SAME');s.eq(17,0,'GROUP_ACTIVE');s.go('LOOP')
s.label('GROUP_ACTIVE');a(0x00a0,V(0),V(9),V(10),V(11));a(6,V(6),I(-1));s.check(0x00df,[V(0)],'CJ_ON_FOOT');a(0x03c0,V(0),V(6));s.label('CJ_ON_FOOT')
# 1.2: CJ drives when every passenger seat of his car is free at the moment he gets in (decided once per car, before a guard sits down)
s.get(19,b.SQ_CARH);s.check(0x803b,[V(6),V(19)],'DRV_DONE');a(0xddc,I(b.SQ_CARH),V(6));s.set(b.SQ_DRIVES,0);s.check(0x8039,[V(6),I(-1)],'DRV_DONE');s.set(b.SQ_DRIVES,1);a(0x01ea,V(6),V(26))
for seat in range(4):
 skip='DRV_SEAT_%d'%seat;s.check(0x0019,[V(26),I(seat)],skip);s.check(0x0431,[V(6),I(seat)],'DRV_PASSENGER');s.label(skip)
s.go('DRV_DONE');s.label('DRV_PASSENGER');s.set(b.SQ_DRIVES,0);s.label('DRV_DONE')
s.get(7,b.TACTICS);s.get(8,b.FIRE)
# CJ inside an interior: the team waits outside (no teleport into interior coordinates)
a(0x077e,V(19));s.eq(19,0,'LOOP')
s.call('ANCHOR');s.call('PERCEIVE')
for i in range(4):s.get(13+i,b.SQ_T+i)
a(0x06ac,V(0),V(18))
for k in range(4):s.call('GUARD_%d'%k)
s.go('LOOP')

# ---------------------------------------------------------------- formation anchor (1.2)
# The formation used to be CJ-relative (04C4 follows his heading), so a guard ran round him every time CJ turned on the spot (aiming,
# looking around). Now it hangs on the unit vector of the direction he is TRAVELLING in (right = (uy, -ux), no trigonometry):
# it starts as his heading, follows his movement only after he has walked more than 60 degrees off it for 1.5 s, and holds while
# he stands or rides.
s.label('ANCHOR');s.get(29,b.FORM_OK);s.eq(29,0,'AN_HAVE')
a(0x04c4,V(0),F(0),F(1),F(0),V(29),V(30),V(31));a(0x0087,V(26),V(29));a(0x0063,V(26),V(9));a(0x0087,V(27),V(30));a(0x0063,V(27),V(10))
a(0xddc,I(b.FORM_UX),V(26));a(0xddc,I(b.FORM_UY),V(27));a(0xddc,I(b.FORM_PX),V(9));a(0xddc,I(b.FORM_PY),V(10));a(0xddc,I(b.FORM_T),V(12));s.set(b.FORM_CT,0);s.set(b.FORM_OK,1);s.ret()
s.label('AN_HAVE');s.get(29,b.FORM_PX);s.get(30,b.FORM_PY);s.get(31,b.FORM_T)
a(0xddc,I(b.FORM_PX),V(9));a(0xddc,I(b.FORM_PY),V(10));a(0xddc,I(b.FORM_T),V(12))
s.eq(6,-1,'AN_RET')
a(0x0087,V(26),V(9));a(0x0063,V(26),V(29));a(0x0087,V(27),V(10));a(0x0063,V(27),V(30));a(0x0509,F(0),F(0),V(26),V(27),V(28))
a(0x0085,V(29),V(12));a(0x0062,V(29),V(31));s.check(0x0019,[V(29),I(400)],'AN_DT_OK');s.ret()
s.label('AN_DT_OK');a(0x0093,V(30),V(29));a(0x0013,V(30),F(.0012));s.check(0x0025,[V(28),V(30)],'AN_IDLE');s.check(0x0023,[F(3),V(28)],'AN_IDLE')
a(0x0073,V(26),V(28));a(0x0073,V(27),V(28));s.get(29,b.FORM_UX);s.get(30,b.FORM_UY)
a(0x0087,V(31),V(26));a(0x006b,V(31),V(29));a(0x0087,V(28),V(27));a(0x006b,V(28),V(30));a(0x005b,V(31),V(28))
s.check(0x0021,[V(31),F(.5)],'AN_OFF');s.set(b.FORM_CT,0);s.ret()
s.label('AN_OFF');s.get(29,b.FORM_CT);s.eq(29,0,'AN_RUN');a(0xddc,I(b.FORM_CT),V(12));s.ret()
s.label('AN_RUN');a(0x0085,V(30),V(12));a(0x0062,V(30),V(29));s.check(0x0019,[V(30),I(1500)],'AN_RET')
a(0xddc,I(b.FORM_UX),V(26));a(0xddc,I(b.FORM_UY),V(27));s.set(b.FORM_CT,0);s.ret()
s.label('AN_IDLE');s.set(b.FORM_CT,0)
s.label('AN_RET');s.ret()

# ---------------------------------------------------------------- perception
# v40.1: the work is spread over four ticks (phase in SQ_SCAN_NEXT) so no single frame carries
# the whole scan: 0 = re-check the list, the fire worker's targets and the fine cells near CJ;
# 1/2 = the two halves of the coarse cells; 3 = drivers of nearby cars, then the radio calls.
s.label('PERCEIVE');s.get(19,b.SQ_SCAN_NEXT)
for i in range(4):s.get(13+i,b.SQ_T+i)
s.get(18,b.SQ_THREATS)
s.eq(19,0,'PH_1');a(6,V(18),I(0))
for i in range(4):
 drop=uid('KEEP_DROP');placed=uid('KEEP_PLACED');a(0x0085,V(29),V(13+i));a(6,V(31),I(1));s.call('CLASSIFY');s.eq(30,1,drop)
 for j in range(i+1):
  nj=uid('KEEP_AT');s.eq(18,j,nj);a(0x0085,V(13+j),V(29));s.go(placed);s.label(nj)
 s.label(placed);a(0x000a,V(18),I(1));s.label(drop)
for j in range(4):
 keep=uid('CLEAR_TAIL');s.check(0x8019,[V(18),I(j)],keep);a(6,V(13+j),I(-1));s.label(keep)
# whatever the door gunners are engaging is a candidate too (still checked against the rules)
for key in [b.TB_SHOOTER,b.FIRE_TARGET]+[b.GUARD_TARGET+i for i in range(4)]:
 s.get(29,key);s.call('CONSIDER');s.check(0x8019,[V(18),I(3)],'PERCEIVE_STORE')
for x in NEAR:
 for y in NEAR:
  a(0x0087,V(26),V(9));a(0x000b,V(26),F(x));a(0x0087,V(27),V(10));a(0x000b,V(27),F(y));a(0x0a3e,V(26),V(27),V(11),F(1.6),F(1.6),F(4),V(29));s.call('CONSIDER');s.check(0x8019,[V(18),I(3)],'PERCEIVE_STORE')
s.go('PERCEIVE_STORE')
MID_CELLS=[(x,y) for x in MID for y in MID if not (x==0 and y==0)]  # the fine grid covers the centre
for ph,cells in [(1,MID_CELLS[:len(MID_CELLS)//2]),(2,MID_CELLS[len(MID_CELLS)//2:])]:
 s.label('PH_%d'%ph);s.eq(19,ph,'PH_%d'%(ph+1))
 for x,y in cells:
  a(0x0087,V(26),V(9));a(0x000b,V(26),F(x));a(0x0087,V(27),V(10));a(0x000b,V(27),F(y));a(0x0a3e,V(26),V(27),V(11),F(4.6),F(4.6),F(10),V(29));s.call('CONSIDER');s.check(0x8019,[V(18),I(3)],'PERCEIVE_STORE')
 s.go('PERCEIVE_STORE')
s.label('PH_3')
for dx,dy in [(-30,-30),(0,-30),(-30,0),(0,0)]:
 nxt=uid('CAR_NEXT');a(0x0087,V(26),V(9));a(0x000b,V(26),F(dx));a(0x0087,V(27),V(10));a(0x000b,V(27),F(dy));a(0x0087,V(28),V(26));a(0x000b,V(28),F(30));a(0x0087,V(31),V(27));a(0x000b,V(31),F(30))
 a(0x053e,V(26),V(27),V(28),V(31),I(-1),V(23));s.check(0x056e,[V(23)],nxt);s.check(0x803b,[V(23),V(1)],nxt);s.check(0x803b,[V(23),V(6)],nxt);a(0x046c,V(23),V(29));s.call('CONSIDER');s.check(0x8019,[V(18),I(3)],'PERCEIVE_STORE');s.label(nxt)
s.label('PERCEIVE_STORE');s.eq(18,0,'PS_BUSY');s.go('PS_STORE');s.label('PS_BUSY');a(0xddc,I(b.SQ_QUIET_T),V(12));s.label('PS_STORE')
for i in range(4):a(0xddc,I(b.SQ_T+i),V(13+i))
a(0xddc,I(b.SQ_THREATS),V(18));s.get(19,b.SQ_SCAN_NEXT);a(0x000a,V(19),I(1));s.check(0x8019,[V(19),I(3)],'PH_WRAP');a(0xddc,I(b.SQ_SCAN_NEXT),V(19));s.ret()
s.label('PH_WRAP');s.set(b.SQ_SCAN_NEXT,0)
# v41: rate the threats (threat_v41.THREAT_SCORE) and sort them, most dangerous first: guard 0 and
# every guard without a threat of his own take the top one.
for i in range(4):
 none=uid('SC_NONE');done=uid('SC_DONE');a(0x0085,V(29),V(13+i));alive(29,none);s.call('SQ_SCORE');a(0xddc,I(b.SQ_SC+i),V(30));s.go(done)
 s.label(none);s.set(b.SQ_SC+i,-10000);s.label(done)
SREG=[27,28,31,19]
for i in range(4):s.get(SREG[i],b.SQ_SC+i)
for i,j in [(0,1),(2,3),(0,2),(1,3),(1,2)]:
 keep=uid('SORT_KEEP');s.check(0x001d,[V(SREG[j]),V(SREG[i])],keep)
 a(0x0085,V(29),V(SREG[i]));a(0x0085,V(SREG[i]),V(SREG[j]));a(0x0085,V(SREG[j]),V(29))
 a(0x0085,V(29),V(13+i));a(0x0085,V(13+i),V(13+j));a(0x0085,V(13+j),V(29));s.label(keep)
for i in range(4):a(0xddc,I(b.SQ_SC+i),V(SREG[i]));a(0xddc,I(b.SQ_T+i),V(13+i))
# radio calls: kind and direction of the first contact, of every new top threat scoring 120+ (throttled),
# and "area secure" 3.5 s after the last threat
s.eq(18,0,'CALL_CONTACT')
s.get(19,b.SQ_CONTACT);s.eq(19,1,'CALL_RET');s.get(19,b.SQ_CLEAR_AT);s.eq(19,0,'CALL_CLEAR_CHECK');a(0x0085,V(19),V(12));a(0x000a,V(19),I(3500));a(0xddc,I(b.SQ_CLEAR_AT),V(19));s.ret()
s.label('CALL_CLEAR_CHECK');s.check(0x001d,[V(12),V(19)],'CALL_RET');s.set(b.SQ_CONTACT,0);s.set(b.SQ_CLEAR_AT,0);s.set(b.SQ_CALLED,-1);msg('SQCLR',False);s.ret()
s.label('CALL_CONTACT');s.set(b.SQ_CLEAR_AT,0);s.get(19,b.SQ_CONTACT);s.eq(19,0,'CALL_NEW_TOP');s.set(b.SQ_CONTACT,1);a(6,V(26),I(0));s.go('CALL_ANNOUNCE')
s.label('CALL_NEW_TOP');s.get(19,b.SQ_CALLED);s.check(0x803b,[V(13),V(19)],'CALL_RET');s.get(19,b.SQ_SC);s.check(0x0019,[V(19),I(SCORE_FOCUS-1)],'CALL_RET');s.get(19,b.SQ_MSG_NEXT);s.check(0x001d,[V(12),V(19)],'CALL_RET');a(6,V(26),I(1))
s.label('CALL_ANNOUNCE');a(0xddc,I(b.SQ_CALLED),V(13))
# kind (27@): 0 plain, 1 shooting at CJ, 2 sniper, 3 vehicle, 4 roof
a(6,V(27),I(0));s.get(19,b.TB_SHOOTER);s.check(0x003b,[V(13),V(19)],'KIND_NOT_X');s.get(19,b.TB_SHOOTER_T);a(0x0085,V(20),V(12));a(0x0062,V(20),V(19));s.check(0x8019,[V(20),I(SHOOTER_FRESH_MS)],'KIND_NOT_X');a(6,V(27),I(1));s.go('KIND_DONE')
s.label('KIND_NOT_X');a(0x0470,V(13),V(19));s.check(0x0019,[V(19),I(32)],'KIND_NOT_S');s.check(0x0019,[V(19),I(34)],'KIND_S');s.go('KIND_NOT_S');s.label('KIND_S');a(6,V(27),I(2));s.go('KIND_DONE')
s.label('KIND_NOT_S');s.check(0x00df,[V(13)],'KIND_NOT_V');a(6,V(27),I(3));s.go('KIND_DONE')
s.label('KIND_NOT_V');a(0x00a0,V(13),V(20),V(21),V(22));a(0x0063,V(22),V(11));s.check(0x0021,[V(22),F(6)],'KIND_DONE');a(6,V(27),I(4))
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
emit_score(s,'SQ_SCORE',29,30,[0,2,3,4,5],dict(cx=9,cy=10,cz=11,tx=20,ty=21,tz=22,d=23,t1=24,t2=25,t3=26))
# 29@ candidate: append to the threat list when it is new, there is room and CLASSIFY accepts it.
s.label('CONSIDER');s.check(0x0019,[V(18),I(3)],'CON_ROOM');s.ret()
s.label('CON_ROOM')
for j in range(4):s.check(0x803b,[V(29),V(13+j)],'CON_RET')
a(6,V(31),I(0));s.call('CLASSIFY');s.eq(30,1,'CON_RET')
for j in range(4):
 nj=uid('CON_AT');s.eq(18,j,nj);a(0x0085,V(13+j),V(29));s.go('CON_COUNT');s.label(nj)
s.label('CON_COUNT');a(0x000a,V(18),I(1))
s.label('CON_RET');s.ret()

# 30@ = 1 when 29@ is a threat under the current rules of engagement. 31@ = 1: an existing threat,
# kept while it stays in range (no need to keep shooting); police still drop out at wanted level 0.
# Uses 19-25.
s.label('CLASSIFY');a(6,V(30),I(0));alive(29,'CL_RET')
s.check(0x803b,[V(29),V(0)],'CL_RET');s.check(0x8448,[V(29),V(1)],'CL_RET')
a(0x00a0,V(29),V(20),V(21),V(22));a(0x050a,V(20),V(21),V(22),V(9),V(10),V(11),V(22));s.check(0x0023,[F(55),V(22)],'CL_RET')
# The team, the crew and the pilot are all Grove-type (8): only for those run the friend checks.
a(0x089f,V(29),V(23));s.eq(23,8,'CL_STRANGER')
for i in range(2,7):s.get(19,b.PUB+i);s.check(0x803b,[V(29),V(19)],'CL_RET')
for i in range(5):s.get(19,b.GROUND_PUB+i);s.check(0x803b,[V(29),V(19)],'CL_RET')
s.label('CL_STRANGER')
s.get(19,b.TB_SHOOTER);s.check(0x003b,[V(29),V(19)],'CL_NOT_SHOOTER');s.get(19,b.TB_SHOOTER_T);a(0x0085,V(25),V(12));a(0x0062,V(25),V(19));s.check(0x8019,[V(25),I(SHOOTER_FRESH_MS)],'CL_NOT_SHOOTER');s.go('CL_ACCEPT');s.label('CL_NOT_SHOOTER')
# Anyone who hurt CJ or one of the team is hostile under every mode (self-defence).
s.check(0x051a,[V(0),V(29)],'CL_NOT_ATTACKER_CJ');s.go('CL_ACCEPT');s.label('CL_NOT_ATTACKER_CJ')
for k in range(4):
 nxt=uid('CL_NOT_ATTACKER');alive(2+k,nxt);s.check(0x051a,[V(2+k),V(29)],nxt);s.go('CL_ACCEPT');s.label(nxt)
s.eq(8,0,'CL_ROE');s.ret()
s.label('CL_ROE');a(0x0470,V(29),V(24))
s.eq(8,2,'CL_NOT_FOLLOW');s.eq(31,1,'CL_FOLLOW_AIM');s.go('CL_ACCEPT');s.label('CL_FOLLOW_AIM');s.check(0x0457,[I(0),V(29)],'CL_RET');s.go('CL_ACCEPT')
s.label('CL_NOT_FOLLOW');s.eq(23,8,'CL_NOT_GROVE');s.ret()
s.label('CL_NOT_GROVE');s.eq(23,6,'CL_NOT_COP');a(0x01c0,I(0),V(25));s.check(0x0019,[V(25),I(0)],'CL_RET');s.go('CL_ACCEPT')
s.label('CL_NOT_COP');s.eq(31,1,'CL_FRESH');s.go('CL_ACCEPT');s.label('CL_FRESH')
# armed = pistols .. minigun (22-38) or thrown explosives (16-18)
s.check(0x0019,[V(24),I(21)],'CL_THROWN');s.check(0x0019,[V(24),I(38)],'CL_ARMED');s.ret()
s.label('CL_THROWN');s.check(0x0019,[V(24),I(15)],'CL_RET');s.check(0x0019,[V(24),I(18)],'CL_ARMED');s.ret()
s.label('CL_ARMED');s.eq(8,1,'CL_CAREFUL');s.go('CL_ACCEPT')
s.label('CL_CAREFUL');s.check(0x02e0,[V(29)],'CL_GANG');s.go('CL_ACCEPT')
s.label('CL_GANG');s.check(0x0023,[F(20),V(22)],'CL_RET')
for gang in [7,9,10]:
 nxt=uid('CL_GANG_NEXT');s.eq(23,gang,nxt);s.go('CL_ACCEPT');s.label(nxt)
s.ret()
s.label('CL_ACCEPT');a(6,V(30),I(1))
s.label('CL_RET');s.ret()

# ---------------------------------------------------------------- one guard
def formation(k,table,lead=True):
  """26-28 = point `ox` to the right and `oy` ahead of CJ in the formation frame (unit travel direction u = FORM_UX/UY, right = (uy, -ux));
  `oy` is pushed ahead while CJ moves. Slots (lead=True) step out of CJ's line of fire while he shoots."""
  ox,oy=table[k]
  a(0x0007,V(31),F(oy))
  if lead:
   a(0x0087,V(30),V(18));a(0x0013,V(30),F(.9))
   cap=uid('LEAD_CAP');s.check(0x0021,[V(30),F(6)],cap);a(0x0007,V(30),F(6));s.label(cap)
   a(0x005b,V(31),V(30))
  s.get(29,b.FORM_UX);s.get(30,b.FORM_UY)
  a(0x0087,V(26),V(30));a(0x0013,V(26),F(ox));a(0x0087,V(27),V(29));a(0x0013,V(27),F(-ox))
  a(0x0087,V(28),V(29));a(0x006b,V(28),V(31));a(0x006b,V(30),V(31))
  a(0x005b,V(26),V(28));a(0x005b,V(27),V(30));a(0x005b,V(26),V(9));a(0x005b,V(27),V(10));a(0x0087,V(28),V(11))
  if lead:fire_line_clear()
def fire_line_clear():s.call('FIRE_LINE')
def emit_fire_line():
  """Subroutine: V26/V27 = slot. While CJ shoots (aim line younger than 1.2 s) a slot within 2 m of his line of fire, ahead of him,
  is pushed sideways (right = (dy, -dx) of the unit aim direction); returns V28 = CJ z."""
  skip='FL_SKIP';left='FL_LEFT';go='FL_GO'
  s.label('FIRE_LINE')
  s.get(29,b.CJ_AIM_T);a(0x0085,V(30),V(12));a(0x0062,V(30),V(29));s.check(0x8019,[V(30),I(1200)],skip)
  s.get(29,b.CJ_AIM_X);s.get(30,b.CJ_AIM_Y);a(0x0509,F(0),F(0),V(29),V(30),V(31));s.check(0x0021,[V(31),F(.2)],skip)
  a(0x0073,V(29),V(31));a(0x0073,V(30),V(31))
  a(0x0087,V(31),V(26));a(0x0063,V(31),V(9));a(0x0087,V(28),V(27));a(0x0063,V(28),V(10))
  a(0x0087,V(19),V(31));a(0x006b,V(19),V(29));a(0x0087,V(20),V(28));a(0x006b,V(20),V(30));a(0x005b,V(19),V(20));s.check(0x0021,[V(19),F(.5)],skip)
  a(0x006b,V(31),V(30));a(0x006b,V(28),V(29));a(0x0063,V(31),V(28))
  a(0x0087,V(19),V(31));s.check(0x0021,[V(19),F(0)],left);a(0x0007,V(20),F(1));s.go(go)
  s.label(left);a(0x0013,V(19),F(-1));a(0x0007,V(20),F(-1));s.label(go)
  s.check(0x0023,[F(2),V(19)],skip);a(0x0087,V(31),V(19));a(0x0013,V(31),F(-1));a(0x000b,V(31),F(2))
  a(0x006b,V(31),V(20));a(0x0087,V(28),V(30));a(0x006b,V(28),V(31));a(0x005b,V(26),V(28))
  a(0x0087,V(28),V(29));a(0x006b,V(28),V(31));a(0x0063,V(27),V(28))
  s.label(skip);a(0x0087,V(28),V(11));s.ret()
def form_point(k):
 """26-28 = this guard's formation point for the current tactics."""
 bg=uid('FP_BG');done=uid('FP_DONE');s.eq(7,1,bg);formation(k,AS_FORM);s.go(done);s.label(bg);formation(k,BG_FORM);s.label(done)
def move_to(k,G,speed,ms=2500,every=800):
 """Go straight to 26-28 at move state `speed` (literal or V). Re-issued only for a new order,
 a target that moved more than a metre, or after `every` ms. Returns from the guard routine."""
 issue=uid('MOVE_ISSUE');drift=uid('MOVE_DRIFT')
 s.get(31,fk(k,'TASK'));s.eq(31,1,issue);s.get(31,fk(k,'NEXT'));s.check(0x001d,[V(12),V(31)],drift);s.go(issue)
 s.label(drift);s.get(29,fk(k,'TX'));s.get(30,fk(k,'TY'));a(0x0509,V(26),V(27),V(29),V(30),V(31));s.check(0x0021,[V(31),F(1.0)],'G%d_RET'%k)
 s.label(issue);a(0x04eb,V(G),I(0))
 a(0x05d3,V(G),V(26),V(27),V(28),speed,I(ms));setk(k,'TX',26);setk(k,'TY',27);setk_lit(k,'TASK',1);later(k,every);s.ret()
def shoot_move(k,G,every=1200):
 """Run to 26-28 while firing at 25@ (TASK 12); re-issued for a new target or after `every` ms."""
 issue=uid('SHOOTMOVE_ISSUE');same_order(k,12,25,issue);s.label(issue);a(0x04eb,V(G),I(0))
 a(0x0637,V(G),V(26),V(27),V(28),I(6),F(.5),F(1.0),V(25));setk(k,'TX',26);setk(k,'TY',27);order(k,12,25,every)
def same_order(k,task,target_var,issue):
 """Return from the guard routine while the guard already runs `task` on target_var and the order
 has not expired; otherwise continue at `issue` (placed right after this call)."""
 s.get(31,fk(k,'TASK'));s.eq(31,task,issue);s.get(31,fk(k,'TGT'));s.check(0x003b,[V(31),V(target_var)],issue);s.get(31,fk(k,'NEXT'));s.check(0x001d,[V(12),V(31)],'G%d_RET'%k)
def order(k,task,target_var,ms):setk_lit(k,'TASK',task);setk(k,'TGT',target_var);later(k,ms);s.ret()
def shield(k,G,front,lateral):
 """Step to CJ + front*u + lateral*perp (u = unit vector CJ->threat in 29/30), then fire from there."""
 a(0x0087,V(26),V(29));a(0x0013,V(26),F(front));a(0x005b,V(26),V(9));a(0x0087,V(28),V(30));a(0x0013,V(28),F(-lateral));a(0x005b,V(26),V(28))
 a(0x0087,V(27),V(30));a(0x0013,V(27),F(front));a(0x005b,V(27),V(10));a(0x0087,V(28),V(29));a(0x0013,V(28),F(lateral));a(0x005b,V(27),V(28))
 a(0x0087,V(28),V(11));a(0x0509,V(21),V(22),V(26),V(27),V(31));fire=uid('SHIELD_FIRE');s.check(0x0021,[V(31),F(1.4)],fire);shoot_move(k,G,1200)
 s.label(fire);issue=uid('SHIELD_ISSUE');same_order(k,3,25,issue);s.label(issue);a(0x074d,V(G),V(25),I(1500));order(k,3,25,1200)
COVER_DIRS=[(3.5,0),(2.5,2.5),(0,3.5),(-2.5,2.5),(-3.5,0),(-2.5,-2.5),(0,-3.5),(2.5,-2.5)]
def take_cover(k,G,limit,duck):
 """v41: under fire (the threat is shooting, or this guard is below 50 HP) look once for low cover
 within 3.5 m - a spot where the threat's line to a crouching chest hits a wall or a car but a standing
 head sees over it - and fight from there. One search per tick for the whole team; a spot (or the lack
 of one) is kept 6 s for the same threat. Falls through to `duck` (crouched fire where he stands)."""
 P=uid('CV%d'%k)+'_'
 s.check(0x02e0,[V(25)],P+'HP');s.go(P+'NEED')
 s.label(P+'HP');a(0x0226,V(G),V(31));s.check(0x0019,[V(31),I(49)],P+'NEED');s.go(duck)
 s.label(P+'NEED');s.get(31,b.CV_T+k);s.check(0x001d,[V(31),V(12)],P+'SEARCH');s.get(31,b.CV_H+k);s.check(0x003b,[V(31),V(25)],P+'SEARCH');s.get(31,b.CV_OK+k);s.eq(31,1,duck);s.go(P+'GO')
 s.label(P+'SEARCH');s.get(31,b.SQ_CV_TICK);s.check(0x803b,[V(31),V(12)],duck)
 a(0xddc,I(b.SQ_CV_TICK),V(12));a(0xddc,I(b.CV_H+k),V(25));a(0x0085,V(31),V(12));a(0x000a,V(31),I(6000));a(0xddc,I(b.CV_T+k),V(31));s.set(b.CV_OK+k,0)
 a(0x00a0,V(25),V(19),V(20),V(29));a(0x000b,V(29),F(.5))
 for n,(dx,dy) in enumerate(COVER_DIRS):
  nxt=P+'DIR%d'%n;blk=P+'BLK%d'%n
  a(0x0087,V(26),V(21));a(0x000b,V(26),F(dx));a(0x0087,V(27),V(22));a(0x000b,V(27),F(dy))
  a(0x0087,V(28),V(23));a(0x000b,V(28),F(2));a(0x02ce,V(26),V(27),V(28),V(28))
  # walkable: the ground there is within 1.2 m of his feet (ped z is about 1 m above the feet)
  a(0x0087,V(31),V(28));a(0x0063,V(31),V(23));a(0x000b,V(31),F(1));s.check(0x0021,[V(31),F(-1.2)],nxt);s.check(0x0023,[F(1.2),V(31)],nxt)
  a(0x0509,V(26),V(27),V(9),V(10),V(31));s.check(0x0023,[F(limit),V(31)],nxt)
  a(0x0087,V(30),V(28));a(0x000b,V(30),F(.6));s.check(0x06bd,[V(19),V(20),V(29),V(26),V(27),V(30),I(1),I(1),I(0),I(1),I(0)],blk);s.go(nxt)
  s.label(blk);a(0x0087,V(30),V(28));a(0x000b,V(30),F(1.7));s.check(0x06bd,[V(19),V(20),V(29),V(26),V(27),V(30),I(1),I(1),I(0),I(1),I(0)],nxt)
  a(0xddc,I(b.CV_X+k),V(26));a(0xddc,I(b.CV_Y+k),V(27));a(0x000b,V(28),F(1));a(0xddc,I(b.CV_Z+k),V(28));s.set(b.CV_OK+k,1);msg('SQCVR');s.go(P+'GO')
  s.label(nxt)
 s.go(duck)
 s.label(P+'GO');s.get(26,b.CV_X+k);s.get(27,b.CV_Y+k);s.get(28,b.CV_Z+k);a(0x0509,V(21),V(22),V(26),V(27),V(31));s.check(0x0021,[V(31),F(1.0)],duck);shoot_move(k,G,2500)
def engage_duck(k,G,limit=None):
 if limit is None:
  issue=uid('DUCK_ISSUE');same_order(k,8,25,issue);s.label(issue);a(0x0634,V(G),V(25),I(1),I(1000),I(60));order(k,8,25,3000);return
 duck=uid('DUCK_HERE');take_cover(k,G,limit,duck);s.label(duck)
 # v1.1: a threat that slipped out of sight gets 4 s of suppressive fire at the spot where this
 # guard last saw him (TASK 17), while the flankers work around
 sup=uid('SUP_KEEP');s.get(31,fk(k,'TASK'));s.eq(31,17,sup);s.get(31,fk(k,'TGT'));s.check(0x003b,[V(31),V(25)],sup);s.get(31,fk(k,'NEXT'));s.check(0x001d,[V(12),V(31)],'G%d_RET'%k);s.label(sup)
 issue=uid('DUCK_ISSUE');same_order(k,8,25,issue);s.label(issue)
 hidden=uid('SUP_HIDDEN');shoot=uid('SUP_DUCK')
 a(0x00a0,V(25),V(26),V(27),V(28));a(0x000b,V(28),F(.5));a(0x0087,V(30),V(23));a(0x000b,V(30),F(.6))
 s.check(0x06bd,[V(21),V(22),V(30),V(26),V(27),V(28),I(1),I(0),I(0),I(0),I(0)],hidden)
 a(0xddc,I(b.LS_X+k),V(26));a(0xddc,I(b.LS_Y+k),V(27));a(0xddc,I(b.LS_Z+k),V(28));a(0xddc,I(b.LS_T+k),V(12));s.go(shoot)
 s.label(hidden);s.get(31,b.LS_T+k);a(0x0085,V(30),V(12));a(0x0062,V(30),V(31));s.check(0x8019,[V(30),I(4000)],shoot)
 s.get(26,b.LS_X+k);s.get(27,b.LS_Y+k);s.get(28,b.LS_Z+k);a(0x0668,V(G),V(26),V(27),V(28),I(1500));order(k,17,25,1500)
 s.label(shoot);a(0x0634,V(G),V(25),I(1),I(1000),I(60));order(k,8,25,3000)
def engage_timed(k,G):
 issue=uid('TIMED_ISSUE');same_order(k,10,25,issue);s.label(issue);a(0x07a5,V(G),V(25),I(3000));order(k,10,25,2500)
def leash(k,G,limit,speed):
 """Further than `limit` from CJ (70% of it when this guard is below 50 HP): go back to the
 formation point instead of fighting."""
 ok=uid('LEASH_OK');back=uid('LEASH_BACK');hurt=uid('LEASH_HURT')
 a(0x0226,V(G),V(31));s.check(0x0019,[V(31),I(49)],hurt);s.check(0x0021,[V(24),F(limit)],ok);s.go(back)
 s.label(hurt);s.check(0x0021,[V(24),F(limit*.7)],ok)
 s.label(back);form_point(k);move_to(k,G,I(speed),2500,900);s.label(ok)

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
 s.label(P+'ON_FOOT');s.check(0x0021,[V(24),F(40)],P+'NEAR');form_point(k);s.get(25,fk(k,'TASK'));s.eq(25,7,P+'FAR_PATH');s.get(25,fk(k,'NEXT'));s.check(0x001d,[V(12),V(25)],R)
 s.label(P+'FAR_PATH');a(0x05f5,V(G),V(26),V(27),V(28),I(7),I(20000));setk_lit(k,'TASK',7);later(k,3000);s.ret()
 # ---- stuck check every 2.5 s: moving, far, and barely moved
 s.label(P+'NEAR');s.get(25,fk(k,'LT'));a(0x0085,V(26),V(12));a(0x0062,V(26),V(25));s.check(0x0019,[V(26),I(2500)],P+'STUCK_DONE')
 s.get(26,fk(k,'LX'));s.get(27,fk(k,'LY'));a(0x0509,V(21),V(22),V(26),V(27),V(28));setk(k,'LX',21);setk(k,'LY',22);setk(k,'LT',12)
 s.check(0x0021,[V(24),F(9)],P+'STUCK_DONE');s.check(0x0023,[F(.7),V(28)],P+'STUCK_DONE');s.get(25,fk(k,'TASK'));s.eq(25,1,P+'STUCK_T12');s.go(P+'STUCK_YES');s.label(P+'STUCK_T12');s.eq(25,12,P+'STUCK_DONE');s.label(P+'STUCK_YES')
 form_point(k);a(0x05f5,V(G),V(26),V(27),V(28),I(6),I(15000));setk_lit(k,'TASK',7);later(k,3000);s.ret()   # 1.2: re-path, no teleport
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
 # ---- combat: 1.2: a guard stays on the target he is already engaging while it lives and is still a threat (no flipping at every
 # perception pass); guard 0 always takes the top threat, so the team never ignores a new danger. Otherwise: own threat (spread
 # over the list), else the first one
 if k>0:
  s.get(25,fk(k,'TGT'));alive(25,P+'PICK')
  for j in range(4):s.check(0x803b,[V(25),V(13+j)],P+'COMBAT')
 s.label(P+'PICK');a(0x0085,V(25),V(13+k));alive(25,P+'T0');s.go(P+'COMBAT')
 s.label(P+'T0');a(0x0085,V(25),V(13));alive(25,P+'PEACE')
 s.label(P+'COMBAT');a(0x00a0,V(25),V(26),V(27),V(28));a(0x0087,V(29),V(26));a(0x0063,V(29),V(9));a(0x0087,V(30),V(27));a(0x0063,V(30),V(10))
 a(0x0509,V(9),V(10),V(26),V(27),V(31));s.check(0x0023,[F(.5),V(31)],P+'D_OK');a(0x0007,V(31),F(.5));s.label(P+'D_OK');a(0x0073,V(29),V(31));a(0x0073,V(30),V(31))
 a(0x0226,V(0),V(31));s.check(0x0019,[V(31),I(35)],P+'CRIT')
 # v41 reload drill: after 10 s of fighting a guard drops into a crouch for 1.5 s (the others keep
 # firing; the clocks are staggered 2.5 s per guard so they never all reload together)
 s.get(31,b.ENG_T+k);a(0x0085,V(19),V(12));a(0x0062,V(19),V(31));s.check(0x0019,[V(19),I(10000)],P+'NO_RELOAD')
 s.check(0x0019,[V(19),I(11500)],P+'RELOADING');a(0xddc,I(b.ENG_T+k),V(12));s.go(P+'NO_RELOAD')
 s.label(P+'RELOADING');s.get(31,fk(k,'TASK'));s.eq(31,15,P+'RELOAD_ISSUE');s.ret()
 s.label(P+'RELOAD_ISSUE');a(0x05c5,V(G),I(1500));setk_lit(k,'TASK',15);later(k,1500);msg('SQRLD');s.ret()
 s.label(P+'NO_RELOAD')
 s.eq(7,1,P+'BODYGUARD')
 # ASSAULT: pair 0/1 advances crouched, guard 2 flanks 9 m to the side of the threat, never further than 25 m from CJ (1.2: was 40 m);
 # guard 3 is the medic and never leaves CJ (he fights from his place like in BODYGUARD)
 if k==3:s.go(P+'BODYGUARD')
 elif k in (0,1):
  # bounding overwatch: every 3 s the pair swaps roles - one runs up to 6 m closer while firing
  # (never closer than 8 m), the other covers him crouched
  leash(k,G,25,7);cover=uid(P+'BOUND_COVER');step_ok=uid(P+'BOUND_STEP')
  a(0x0509,V(21),V(22),V(26),V(27),V(31));s.check(0x0021,[V(31),F(10)],cover)
  a(0x0085,V(19),V(12));a(0x0016,V(19),I(3000));a(0x0085,V(20),V(19));a(0x0016,V(20),I(2));a(0x0012,V(20),I(2));a(0x0062,V(19),V(20));s.eq(19,k,cover)
  a(0x0087,V(28),V(31));a(0x000b,V(28),F(-8));s.check(0x0021,[V(28),F(6)],step_ok);a(0x0007,V(28),F(6));s.label(step_ok)
  a(0x0087,V(29),V(26));a(0x0063,V(29),V(21));a(0x0073,V(29),V(31));a(0x006b,V(29),V(28));a(0x005b,V(29),V(21))
  a(0x0087,V(30),V(27));a(0x0063,V(30),V(22));a(0x0073,V(30),V(31));a(0x006b,V(30),V(28));a(0x005b,V(30),V(22))
  a(0x0087,V(26),V(29));a(0x0087,V(27),V(30));a(0x0087,V(28),V(23));shoot_move(k,G,2500)
  s.label(cover);engage_duck(k,G,25)
 else:
  side=-1;leash(k,G,25,7)
  a(0x0509,V(21),V(22),V(26),V(27),V(31));close=uid(P+'FLANK_CLOSE');s.check(0x0021,[V(31),F(10)],close)
  a(0x0087,V(31),V(30));a(0x0013,V(31),F(-9*side));a(0x005b,V(26),V(31));a(0x0087,V(31),V(29));a(0x0013,V(31),F(9*side));a(0x005b,V(27),V(31))
  a(0x0509,V(21),V(22),V(26),V(27),V(31));s.check(0x0021,[V(31),F(3)],close);shoot_move(k,G,1500)
  s.label(close);engage_timed(k,G)
 # BODYGUARD: 1 and 2 are shields between CJ and the threat, 0 and 3 engage within 14 m of CJ
 s.label(P+'BODYGUARD')
 if k in (1,2):shield(k,G,2.0,-1.3 if k==1 else 1.3)
 else:leash(k,G,14,6);engage_duck(k,G,14)
 # CJ below 35 HP: everyone closes a ring around him and fires
 s.label(P+'CRIT')
 if k==0:
  said=uid(P+'COVER_SAID');done=uid(P+'COVER_DONE');s.get(31,fk(k,'COVER'));s.eq(31,0,said);msg('SQCOV',False);setk_lit(k,'COVER',1);s.go(done)
  # still under fire from three or more: recommend the evacuation (every 30 s)
  s.label(said);s.get(31,b.SQ_THREATS);s.check(0x0019,[V(31),I(2)],done);s.get(31,b.SQ_EVAC_NEXT);s.check(0x001d,[V(12),V(31)],done)
  a(0x0085,V(31),V(12));a(0x000a,V(31),I(30000));a(0xddc,I(b.SQ_EVAC_NEXT),V(31));msg('SQEVAC',False);s.label(done)
 shield(k,G,*[(1.5,0),(.6,-1.2),(.6,1.2),(-1.2,0)][k])
 # ---- no threat: medic first (rear guard), then formation / sector watch
 s.label(P+'PEACE');a(0x0085,V(31),V(12));a(0x000a,V(31),I(k*2500));a(0xddc,I(b.ENG_T+k),V(31))
 if k==0:setk_lit(k,'COVER',0)
 if k==3:
  s.get(25,fk(k,'TASK'));s.eq(25,9,P+'MEDIC_IDLE');s.get(25,fk(k,'NEXT'));s.check(0x001d,[V(12),V(25)],R)
  s.label(P+'MEDIC_IDLE');s.get(25,b.SQ_MEDIC_NEXT);s.check(0x001d,[V(12),V(25)],P+'NO_MEDIC')
  a(0x0226,V(0),V(31));s.check(0x8019,[V(31),I(59)],P+'MED_GUARDS');a(0x0085,V(25),V(0));s.go(P+'MED_GO')
  s.label(P+'MED_GUARDS')
  for j in range(3):
   nxt=uid(P+'MED_NEXT');alive(2+j,nxt);a(0x0226,V(2+j),V(31));s.check(0x0019,[V(31),I(59)],P+'MED_G%d'%j);s.go(nxt)
   s.label(P+'MED_G%d'%j);a(0x0085,V(25),V(2+j));s.go(P+'MED_GO');s.label(nxt)
  s.go(P+'NO_MEDIC')
  s.label(P+'MED_GO');a(0x00a0,V(25),V(26),V(27),V(28));a(0x0509,V(21),V(22),V(26),V(27),V(31));s.check(0x0021,[V(31),F(1.6)],P+'MED_TREAT');move_to(k,G,I(6),2000,700)
  s.label(P+'MED_TREAT');a(0x04eb,V(G),I(1));a(0x0226,V(25),V(31));s.check(0x803b,[V(25),V(0)],P+'MED_CJ')
  a(0x000a,V(31),I(60));s.check(0x0019,[V(31),I(150)],P+'MED_G_SET');a(6,V(31),I(150));s.label(P+'MED_G_SET');a(0x0223,V(25),V(31))
  a(0x0085,V(31),V(12));a(0x000a,V(31),I(20000));a(0xddc,I(b.SQ_MEDIC_NEXT),V(31));msg('SQMEDG',False);setk_lit(k,'TASK',9);later(k,2500);s.ret()
  s.label(P+'MED_CJ');a(0x000a,V(31),I(35));s.check(0x0019,[V(31),I(100)],P+'MED_CJ_SET');a(6,V(31),I(100));s.label(P+'MED_CJ_SET');a(0x0223,V(25),V(31))
  a(0x0085,V(31),V(12));a(0x000a,V(31),I(40000));a(0xddc,I(b.SQ_MEDIC_NEXT),V(31));msg('SQMED',False);setk_lit(k,'TASK',9);later(k,2500);s.ret()
  s.label(P+'NO_MEDIC')
 form_point(k);a(0x0509,V(21),V(22),V(26),V(27),V(31))
 s.check(0x0021,[V(31),F(1.2)],P+'CLOSE');s.go(P+'MOVE')
 s.label(P+'CLOSE');s.check(0x0021,[V(18),F(.5)],P+'WATCH')
 s.label(P+'MOVE');a(6,V(20),I(4));s.check(0x0021,[V(18),F(3)],P+'SPD_DIST');a(6,V(20),I(6))
 s.label(P+'SPD_DIST');s.check(0x0021,[V(31),F(3.5)],P+'SPD_SET');a(6,V(20),I(6));s.check(0x0021,[V(31),F(9)],P+'SPD_SET');a(6,V(20),I(7))
 s.label(P+'SPD_SET');s.check(0x0021,[V(18),F(6)],P+'SPD_GO');a(6,V(20),I(7));s.label(P+'SPD_GO');move_to(k,G,V(20),2500,700)
 # standing with CJ: weapons up on this guard's sector
 s.label(P+'WATCH');s.get(31,b.SQ_QUIET_T);a(0x0085,V(30),V(12));a(0x0062,V(30),V(31));s.check(0x0019,[V(30),I(20000)],P+'ALERT')
 s.get(25,fk(k,'TASK'));s.eq(25,16,P+'RELAX');s.ret()
 s.label(P+'RELAX');a(0x04eb,V(G),I(0));setk_lit(k,'TASK',16);later(k,5000);s.ret()
 s.label(P+'ALERT');s.get(25,fk(k,'TASK'));s.eq(7,1,P+'WATCH_BG')
 s.eq(25,13,P+'AS_NOT_TURNING');s.get(25,fk(k,'NEXT'));s.check(0x001d,[V(12),V(25)],R);a(0x04eb,V(G),I(1));setk_lit(k,'TASK',2);later(k,6000);s.ret()
 s.label(P+'AS_NOT_TURNING');s.eq(25,2,P+'AS_AIM');s.get(25,fk(k,'NEXT'));s.check(0x001d,[V(12),V(25)],R)
 s.label(P+'AS_AIM');formation(k,AS_AIM,False);a(0x000b,V(28),F(.8));a(0x0667,V(G),V(26),V(27),V(28),I(1200));setk_lit(k,'TASK',13);later(k,1000);s.ret()
 s.label(P+'WATCH_BG');s.eq(25,2,P+'WATCH_ISSUE');s.get(25,fk(k,'NEXT'));s.check(0x001d,[V(12),V(25)],R)
 s.label(P+'WATCH_ISSUE');formation(k,BG_AIM,False)
 a(0x000b,V(28),F(.8));a(0x0667,V(G),V(26),V(27),V(28),I(2600));setk_lit(k,'TASK',2);later(k,2400);s.ret()
 # ---- casualty report (once per guard)
 s.label(P+'DEAD');s.get(25,fk(k,'DEAD'));s.eq(25,0,R);s.get(25,fk(k,'TASK'));s.eq(25,-1,P+'DEAD_NEW');s.ret()
 s.label(P+'DEAD_NEW');setk_lit(k,'DEAD',1);msg('SQDOWN',False)
 s.label(R);s.ret()
emit_fire_line()
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
 'SQCOV': '~r~CJ IS HIT!~w~ Shields up.',
 'SQMED': '~g~MEDIC:~w~ CJ patched up.',
 'SQMEDG': '~g~MEDIC:~w~ teammate patched up.',
 'SQCAR': '~g~SQUAD:~w~ mounting up.',
 'SQRLD': '~g~SQUAD:~w~ reloading!',
 'SQCVR': '~g~SQUAD:~w~ taking cover.',
 'SQEVAC': '~r~TOO HOT!~w~ CJ is hurt - call ROPE PICKUP.'}
if __name__=='__main__':
 report=s.build('Helicover_Squad','csa');print(report)
 with (OUT/'validation.txt').open('a') as validation:validation.write(report+'\n')
 with (OUT/'Helicover.fxt').open('a') as f:f.write(''.join(k+' '+v+'\n' for k,v in TEXTS.items()))
