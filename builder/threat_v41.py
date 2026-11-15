"""v41 threat board: shared code emitters for the fire worker (door gunners) and the squad worker.

THREAT_SCORE rates how dangerous one character is right now from what the game actually reports:
a shot at CJ found through the bullet traces (+100), damage done to CJ or the team (+80), shooting (+40)
and turned towards CJ (+60),
CJ aiming at him (+30), the weapon he holds, a car racing at CJ (+50), a roof position (+15),
being close (+20); minus 30 without a line of sight to CJ, minus 40 for a passive police officer
(no extra wanted stars for nothing) and minus 20 for someone nearly dead.

TRACE_SCAN reads the game's bullet traces (CBulletTraces::aTraces) as LINES (see emit_trace_scan): a
shot at CJ names its shooter (TB_SHOOTER, found on the back-ray), CJ's own shot gives his aim line
(CJ_AIM_*), two or more fresh hits on the helicopter mark HELI_SHOT_T (the pilot breaks away).
"""
from asm_v25 import *
# Shared variables (0DDC/0DDD keys) of the v41 threat board; build_v25 re-exports them.
STATE=0x48456A00
BULLET_TRACES_OFS=0xCFA500;BULLET_TRACE_SIZE=44;BULLET_TRACE_COUNT=16
TB_SHOOTER=STATE+252;TB_SHOOTER_T=STATE+253;HELI_SHOT_T=STATE+254;TRACE_SCAN_T=STATE+255
# 1.2: CJ's own shot line (unit direction + a point on it + the trace's creation time / the time it was seen),
# the time CJ last fired, the time of the last shooter search, and the ground escort handles (friends)
CJ_SHOT_T=STATE+368;CJ_AIM_X=STATE+369;CJ_AIM_Y=STATE+370;CJ_AIM_Z=STATE+371;CJ_AIM_PX=STATE+372;CJ_AIM_PY=STATE+373;CJ_AIM_PZ=STATE+374
CJ_AIM_T=STATE+375;CJ_AIM_E=STATE+376;TB_SEARCH_T=STATE+377;GROUND_PUB=STATE+71
class _B:pass
b=_B()
for _k in ('TB_SHOOTER','TB_SHOOTER_T','HELI_SHOT_T','TRACE_SCAN_T','BULLET_TRACES_OFS','BULLET_TRACE_SIZE','BULLET_TRACE_COUNT','CJ_SHOT_T','CJ_AIM_X','CJ_AIM_Y','CJ_AIM_Z','CJ_AIM_PX','CJ_AIM_PY','CJ_AIM_PZ','CJ_AIM_T','CJ_AIM_E','TB_SEARCH_T','GROUND_PUB'):setattr(b,_k,globals()[_k])

SHOOTER_FRESH_MS=3000
SCORE_FOCUS=120

def _alive(s,var,fail):s.check(0x056d,[V(var)],fail);s.check(0x8118,[V(var)],fail)

def emit_score(s,label,h,out,friends,R,cj=0):
 """Subroutine `label`: out@ = threat score of h@. R = scratch registers cx cy cz (CJ), tx ty tz
 (target), d (distance), t1 t2 t3."""
 a=s.add;P=label+'_';cx,cy,cz,tx,ty,tz,d,t1,t2,t3=[R[k] for k in ('cx','cy','cz','tx','ty','tz','d','t1','t2','t3')]
 _emit_body(s,label,h,out,friends,R,cj)
 s.check(0x00df,[V(h)],P+'RET');a(0x03c0,V(h),V(t1));a(0x02e3,V(t1),V(t2));s.check(0x0021,[V(t2),F(10)],P+'RET');s.check(0x0023,[F(60),V(d)],P+'RET')
 a(0x0174,V(t1),V(t2))
 # bearing from the car to CJ, minus the car heading, folded into -180..180
 a(0x0087,V(t1),V(cx));a(0x0063,V(t1),V(tx));a(0x0087,V(t3),V(cy));a(0x0063,V(t3),V(ty));a(0x0604,V(t1),V(t3),V(t1));a(0x0063,V(t1),V(t2))
 s.check(0x0023,[F(-180),V(t1)],P+'ANG_LO');a(0x000b,V(t1),F(360));s.label(P+'ANG_LO')
 s.check(0x0021,[V(t1),F(180)],P+'ANG_HI');a(0x000b,V(t1),F(-360));s.label(P+'ANG_HI')
 s.check(0x0023,[F(30),V(t1)],P+'RET');s.check(0x0021,[V(t1),F(-30)],P+'RET');a(0x000a,V(out),I(50))
 s.label(P+'RET');s.ret()

def _emit_body(s,label,h,out,friends,R,cj):
 """Everything of the score except the vehicle tail (no return)."""
 a=s.add;P=label+'_';cx,cy,cz,tx,ty,tz,d,t1,t2,t3=[R[k] for k in ('cx','cy','cz','tx','ty','tz','d','t1','t2','t3')]
 s.label(label);a(6,V(out),I(10));a(6,V(t3),I(0))
 a(0x00a0,V(cj),V(cx),V(cy),V(cz));a(0x00a0,V(h),V(tx),V(ty),V(tz));a(0x050a,V(cx),V(cy),V(cz),V(tx),V(ty),V(tz),V(d))
 s.get(t1,b.TB_SHOOTER);s.check(0x003b,[V(h),V(t1)],P+'NOT_SHOOTER');s.get(t1,b.TB_SHOOTER_T);a(0x01bd,V(t2));a(0x0062,V(t2),V(t1))
 s.check(0x8019,[V(t2),I(SHOOTER_FRESH_MS)],P+'NOT_SHOOTER');a(0x000a,V(out),I(100));a(6,V(t3),I(1))
 s.label(P+'NOT_SHOOTER')
 for fr in friends:
  nxt=P+'ATK_%d'%fr;_alive(s,fr,nxt);s.check(0x051a,[V(fr),V(h)],nxt);a(0x000a,V(out),I(80));a(6,V(t3),I(1));s.go(P+'ATK_DONE');s.label(nxt)
 s.label(P+'ATK_DONE')
 s.check(0x02e0,[V(h)],P+'NOT_FIRING');a(0x000a,V(out),I(40));a(6,V(t3),I(1))
 # shooting AND turned towards CJ (heading within 25 degrees of the bearing to him): +60. Works without any trace.
 a(0x0087,V(t1),V(cx));a(0x0063,V(t1),V(tx));a(0x0087,V(t2),V(cy));a(0x0063,V(t2),V(ty));a(0x0604,V(t1),V(t2),V(t1));a(0x0172,V(h),V(t2));a(0x0063,V(t1),V(t2))
 s.check(0x0023,[F(-180),V(t1)],P+'F_LO');a(0x000b,V(t1),F(360));s.label(P+'F_LO')
 s.check(0x0021,[V(t1),F(180)],P+'F_HI');a(0x000b,V(t1),F(-360));s.label(P+'F_HI')
 s.check(0x0021,[V(t1),F(25)],P+'F_OK1');s.go(P+'NOT_FIRING');s.label(P+'F_OK1')
 s.check(0x0023,[F(-25),V(t1)],P+'F_OK2');s.go(P+'NOT_FIRING');s.label(P+'F_OK2');a(0x000a,V(out),I(60))
 s.label(P+'NOT_FIRING')
 s.check(0x0457,[I(0),V(h)],P+'NOT_AIMED');a(0x000a,V(out),I(30));s.label(P+'NOT_AIMED')
 a(0x0470,V(h),V(t1));W=P+'W_DONE'
 s.check(0x0019,[V(t1),I(21)],P+'W_LOW')
 s.check(0x0019,[V(t1),I(24)],P+'W_PISTOL');s.go(P+'W_25');s.label(P+'W_PISTOL');a(0x000a,V(out),I(10));s.go(W)
 s.label(P+'W_25');s.check(0x0019,[V(t1),I(27)],P+'W_SHOTGUN');s.go(P+'W_28')
 s.label(P+'W_SHOTGUN');a(0x000a,V(out),I(10));s.check(0x0023,[F(15),V(d)],W);a(0x000a,V(out),I(15));s.go(W)
 s.label(P+'W_28');s.check(0x0019,[V(t1),I(32)],P+'W_AUTO');s.go(P+'W_33');s.label(P+'W_AUTO');a(0x000a,V(out),I(25));s.go(W)
 s.label(P+'W_33');s.check(0x0019,[V(t1),I(34)],P+'W_SNIPER');s.go(P+'W_35');s.label(P+'W_SNIPER');a(0x000a,V(out),I(35));s.go(W)
 s.label(P+'W_35');s.eq(t1,37,P+'W_HEAVY');s.check(0x0023,[F(15),V(d)],W);a(0x000a,V(out),I(30));s.go(W)
 s.label(P+'W_HEAVY');s.check(0x8019,[V(t1),I(38)],W);a(0x000a,V(out),I(60));s.go(W)   # rocket launchers (35, 36) and the minigun (38): +60; 39 and up (satchel, spray, camera...) nothing
 s.label(P+'W_LOW');s.check(0x0019,[V(t1),I(15)],W);s.check(0x0019,[V(t1),I(18)],P+'W_THROWN');s.go(W)
 s.label(P+'W_THROWN');a(0x000a,V(out),I(30))
 s.label(W)
 a(0x0087,V(t1),V(tz));a(0x0063,V(t1),V(cz));s.check(0x0021,[V(t1),F(6)],P+'NOT_ROOF');a(0x000a,V(out),I(15));s.label(P+'NOT_ROOF')
 s.check(0x0023,[F(15),V(d)],P+'NOT_CLOSE');a(0x000a,V(out),I(20));s.label(P+'NOT_CLOSE')
 a(0x0087,V(t1),V(tz));a(0x000b,V(t1),F(.7));a(0x0087,V(t2),V(cz));a(0x000b,V(t2),F(.7))
 s.check(0x06bd,[V(tx),V(ty),V(t1),V(cx),V(cy),V(t2),I(1),I(0),I(0),I(0),I(0)],P+'NO_LOS');s.go(P+'LOS_DONE')
 s.label(P+'NO_LOS');a(0x000a,V(out),I(-30));s.label(P+'LOS_DONE')
 a(0x089f,V(h),V(t1));s.eq(t1,6,P+'NOT_COP');s.eq(t3,0,P+'NOT_COP');a(0x000a,V(out),I(-40));s.label(P+'NOT_COP')
 for model in (285,286,287):
  nxt=P+'MDL_%d'%model;s.check(0x02f2,[V(h),I(model)],nxt);a(0x000a,V(out),I(20));s.go(P+'MDL_DONE');s.label(nxt)
 s.label(P+'MDL_DONE')
 a(0x0226,V(h),V(t1));s.check(0x8019,[V(t1),I(15)],P+'NOT_DYING');a(0x000a,V(out),I(-20));s.label(P+'NOT_DYING')

def emit_trace_scan(s,label,R,notfriend,cj=0,heli=1):
 """Subroutine `label`: reads the 16 bullet traces once (a loop over the table, not unrolled).

 What the engine really stores (libGTASA: CWeapon::DoBulletImpact -> CBulletTraces::AddTrace(start,end,
 weaponType,victim)) is NOT the bullet's start and end but a random 2-5 m piece somewhere on its path
 (a visual tracer, ~300 ms). Only FIRE_SINGLE_BULLET / police helicopters store exact ends. So every
 trace is used as a LINE: P1 = start field, u = unit(P2 - P1), and the target's position along the line
 t = (X - P1).u, its squared distance from the line perp2 = |X - P1|^2 - t^2 (no square root needed):
  - CJ behind the piece (t <= 1) and within 1.5 m of the line while CJ is shooting, and the piece points the way
    he faces (within 100 degrees; in a car any direction): his own shot -> CJ_AIM_* (line + time) for FOLLOW MY
    SHOTS; a close friend with a smaller perp2 takes the credit. (An enemy round that missed him and flew on
    lies behind him too, but points back past the man he faces: not his.)
  - CJ ahead of the piece (1 < t <= 220) and within 2 m of the line: a shot at CJ -> the shooter is
    searched on the back-ray P1 - u*s (s = 0..88 m, 12 steps of 8 m with a 4.5 m box, on foot and in cars; he must
    hold a gun, 22-38) -> TB_SHOOTER.
  - the helicopter ahead of the piece (3 < t <= 250) and within 6 m: a hit on it; two fresh hits ->
    HELI_SHOT_T (the pilot breaks away). Our own gunners' lines start at the helicopter (t <= 0).
 R: cx cy cz (CJ) hx hy hz (heli) px py pz (P1) ux uy uz (direction) ad (address) n (hits)
 t1 t2 t3 t4 t5 t6 (scratch; t4 = 29 and t5/t6 = 30/31 are also what `notfriend` uses: 29 = the candidate,
 30 = verdict, 31 = scratch)."""
 a=s.add;P=label+'_'
 cx,cy,cz,hx,hy,hz,px,py,pz,ux,uy,uz,ad,n,t1,t2,t3,t4,t5,t6=[R[k] for k in ('cx','cy','cz','hx','hy','hz','px','py','pz','ux','uy','uz','ad','n','t1','t2','t3','t4','t5','t6')]
 def jgt(r,v,l):s.check(0x8021,[V(r),F(v)],l)    # jump when r > v
 def jlt(r,v,l):s.check(0x8023,[F(v),V(r)],l)    # jump when r < v
 def jle(r,v,l):s.check(0x0021,[V(r),F(v)],l)    # jump when r <= v
 def rd(off,reg,size=4):a(0x0085,V(t6),V(ad));a(0x000a,V(t6),I(off));a(0x0dd8,V(reg),V(t6),I(size),I(1))
 def dot(x,y,z,out,tmp):
  """out = (X - P1) . u  for X = (x,y,z) registers (X is not modified; tmp is scratch)."""
  a(0x0087,V(out),V(x));a(0x0063,V(out),V(px));a(0x006b,V(out),V(ux))
  a(0x0087,V(tmp),V(y));a(0x0063,V(tmp),V(py));a(0x006b,V(tmp),V(uy));a(0x005b,V(out),V(tmp))
  a(0x0087,V(tmp),V(z));a(0x0063,V(tmp),V(pz));a(0x006b,V(tmp),V(uz));a(0x005b,V(out),V(tmp))
 def perp2(x,y,z,t,out,tmp):
  """out = |X - P1|^2 - t^2 (squared distance of X from the line)."""
  a(0x050a,V(x),V(y),V(z),V(px),V(py),V(pz),V(out));a(0x006b,V(out),V(out));a(0x0087,V(tmp),V(t));a(0x006b,V(tmp),V(tmp));a(0x0063,V(out),V(tmp))
 s.label(label);a(0x01bd,V(t6));a(0xddc,I(b.TRACE_SCAN_T),V(t6));a(6,V(n),I(0))
 a(0x00a0,V(cj),V(cx),V(cy),V(cz));a(0x0007,V(hx),F(-9999));a(0x0007,V(hy),F(-9999));a(0x0007,V(hz),F(-9999))
 s.check(0x056e,[V(heli)],P+'NO_HELI');a(0x00aa,V(heli),V(hx),V(hy),V(hz));s.label(P+'NO_HELI')
 a(6,V(ad),I(b.BULLET_TRACES_OFS))
 s.label(P+'LOOP')
 rd(24,t1,1);s.eq(t1,1,P+'NEXT')
 rd(28,t1);a(0x01bd,V(t2));a(0x0062,V(t2),V(t1));s.check(0x8019,[V(t2),I(450)],P+'NEXT')
 rd(0,px);rd(4,py);rd(8,pz);rd(12,ux);rd(16,uy);rd(20,uz)
 for v in (px,py):jlt(v,-3100.0,P+'NEXT');jgt(v,3100.0,P+'NEXT')
 a(0x050a,V(px),V(py),V(pz),V(ux),V(uy),V(uz),V(t1));jle(t1,.4,P+'NEXT')
 a(0x0063,V(ux),V(px));a(0x0063,V(uy),V(py));a(0x0063,V(uz),V(pz));a(0x0073,V(ux),V(t1));a(0x0073,V(uy),V(t1));a(0x0073,V(uz),V(t1))
 dot(cx,cy,cz,t4,t5);perp2(cx,cy,cz,t4,t3,t5)
 # ---- CJ behind the piece: his own shot? (only while he is shooting; a closer friend takes the credit)
 jgt(t4,1.0,P+'INCOMING');jlt(t4,-160.0,P+'HELI');jgt(t3,2.25,P+'HELI')
 s.get(t5,b.CJ_SHOT_T);a(0x01bd,V(t6));a(0x0062,V(t6),V(t5));s.check(0x8019,[V(t6),I(350)],P+'HELI')
 # the piece must point the way CJ faces (within 100 degrees): an enemy round that missed him and flew on lies behind him and
 # points back past the man he is facing, which is not his aim. In a car (drive-by) any direction is possible: no check
 s.check(0x80df,[V(cj)],P+'DIR_OK')
 a(0x0604,V(ux),V(uy),V(t1));a(0x0172,V(cj),V(t2));a(0x0063,V(t1),V(t2))
 s.check(0x0023,[F(-180),V(t1)],P+'D_LO');a(0x000b,V(t1),F(360));s.label(P+'D_LO')
 s.check(0x0021,[V(t1),F(180)],P+'D_HI');a(0x000b,V(t1),F(-360));s.label(P+'D_HI')
 jgt(t1,100.0,P+'HELI');jlt(t1,-100.0,P+'HELI')
 s.label(P+'DIR_OK')
 for i in range(4):
  skip=P+'FR_%d'%i;s.get(t6,b.GROUND_PUB+i);_alive(s,t6,skip)
  a(0x00a0,V(t6),V(t1),V(t2),V(t5));a(0x050a,V(t1),V(t2),V(t5),V(px),V(py),V(pz),V(t6));a(0x006b,V(t6),V(t6))
  a(0x0063,V(t1),V(px));a(0x0063,V(t2),V(py));a(0x0063,V(t5),V(pz));a(0x006b,V(t1),V(ux));a(0x006b,V(t2),V(uy));a(0x006b,V(t5),V(uz));a(0x005b,V(t1),V(t2));a(0x005b,V(t1),V(t5))
  jgt(t1,1.0,skip);a(0x006b,V(t1),V(t1));a(0x0063,V(t6),V(t1));a(0x000b,V(t6),F(.3));s.check(0x8025,[V(t3),V(t6)],P+'HELI')
  s.label(skip)
 rd(28,t1);s.get(t5,b.CJ_AIM_E);s.check(0x001d,[V(t1),V(t5)],P+'NEXT')
 a(0xddc,I(b.CJ_AIM_E),V(t1));a(0x01bd,V(t6));a(0xddc,I(b.CJ_AIM_T),V(t6))
 for key,reg in ((b.CJ_AIM_X,ux),(b.CJ_AIM_Y,uy),(b.CJ_AIM_Z,uz),(b.CJ_AIM_PX,px),(b.CJ_AIM_PY,py),(b.CJ_AIM_PZ,pz)):a(0xddc,I(key),V(reg))
 s.go(P+'NEXT')
 # ---- CJ ahead of the piece and close to the line: somebody shot at him
 s.label(P+'INCOMING');jgt(t4,220.0,P+'HELI');jgt(t3,4.0,P+'HELI')
 s.get(t5,b.TB_SEARCH_T);a(0x01bd,V(t6));a(0x0062,V(t6),V(t5));s.check(0x0019,[V(t6),I(250)],P+'HELI')
 s.get(t5,b.TB_SHOOTER_T);a(0x01bd,V(t6));a(0x0062,V(t6),V(t5));s.check(0x8019,[V(t6),I(1500)],P+'SEARCH');s.go(P+'HELI')
 s.label(P+'SEARCH');a(0x01bd,V(t6));a(0xddc,I(b.TB_SEARCH_T),V(t6))
 for step in range(12):
  dist=8*step;car=P+'CAR_%d'%step;nxt=P+'STEP_%d'%step
  for q,u,p in ((t1,ux,px),(t2,uy,py),(t3,uz,pz)):a(0x0087,V(q),V(u));a(0x0013,V(q),F(-dist));a(0x005b,V(q),V(p))
  a(0x0a3e,V(t1),V(t2),V(t3),F(4.5),F(4.5),F(3.5),V(t4));_alive(s,t4,car);a(0x0470,V(t4),V(t5));s.check(0x0019,[V(t5),I(21)],car);s.check(0x8019,[V(t5),I(38)],car);s.call(notfriend);s.eq(t5,1,car)
  a(0x01bd,V(t6));a(0xddc,I(b.TB_SHOOTER),V(t4));a(0xddc,I(b.TB_SHOOTER_T),V(t6));s.go(P+'HELI')
  s.label(car)
  a(0x0087,V(t5),V(t1));a(0x000b,V(t5),F(4.5));a(0x0087,V(t6),V(t2));a(0x000b,V(t6),F(4.5));a(0x000b,V(t1),F(-4.5));a(0x000b,V(t2),F(-4.5))
  a(0x053e,V(t1),V(t2),V(t5),V(t6),I(-1),V(t4));s.check(0x056e,[V(t4)],nxt);s.check(0x803b,[V(t4),V(heli)],nxt);a(0x046c,V(t4),V(t4));_alive(s,t4,nxt);a(0x0470,V(t4),V(t5));s.check(0x0019,[V(t5),I(21)],nxt);s.check(0x8019,[V(t5),I(38)],nxt);s.call(notfriend);s.eq(t5,1,nxt)
  a(0x01bd,V(t6));a(0xddc,I(b.TB_SHOOTER),V(t4));a(0xddc,I(b.TB_SHOOTER_T),V(t6));s.go(P+'HELI')
  s.label(nxt)
 # ---- the helicopter ahead of the piece (our own gunners' lines start at the helicopter: t <= 0)
 s.label(P+'HELI');jlt(hx,-9000.0,P+'NEXT')
 dot(hx,hy,hz,t4,t5);jlt(t4,3.0,P+'NEXT');jgt(t4,250.0,P+'NEXT');perp2(hx,hy,hz,t4,t3,t5);jgt(t3,36.0,P+'NEXT');a(0x000a,V(n),I(1))
 s.label(P+'NEXT');a(0x000a,V(ad),I(b.BULLET_TRACE_SIZE));s.check(0x0019,[V(ad),I(b.BULLET_TRACES_OFS+b.BULLET_TRACE_SIZE*b.BULLET_TRACE_COUNT-1)],P+'LOOP')
 s.label(P+'DONE');s.check(0x0019,[V(n),I(1)],P+'RET');a(0x01bd,V(t6));a(0xddc,I(b.HELI_SHOT_T),V(t6))
 s.label(P+'RET');s.ret()
