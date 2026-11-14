"""v41 threat board: shared code emitters for the fire worker (door gunners) and the squad worker.

THREAT_SCORE rates how dangerous one character is right now from what the game actually reports:
a fresh bullet trace that ends at CJ (+100), damage done to CJ or the team (+80), shooting (+40),
CJ aiming at him (+30), the weapon he holds, a car racing at CJ (+50), a roof position (+15),
being close (+20); minus 30 without a line of sight to CJ, minus 40 for a passive police officer
(no extra wanted stars for nothing) and minus 20 for someone nearly dead.

TRACE_SCAN reads the game's bullet traces (CBulletTraces::aTraces): a fresh round that ends at CJ
names its shooter (TB_SHOOTER, the ped or the driver at the start of the trace); two or more fresh
rounds ending at the helicopter mark HELI_SHOT_T, which makes the pilot break away.
"""
from asm_v25 import *
# Shared variables (0DDC/0DDD keys) of the v41 threat board; build_v25 re-exports them.
STATE=0x48456A00
BULLET_TRACES_OFS=0xCFA500;BULLET_TRACE_SIZE=44;BULLET_TRACE_COUNT=16
TB_SHOOTER=STATE+252;TB_SHOOTER_T=STATE+253;HELI_SHOT_T=STATE+254;TRACE_SCAN_T=STATE+255
class _B:pass
b=_B()
for _k in ('TB_SHOOTER','TB_SHOOTER_T','HELI_SHOT_T','TRACE_SCAN_T','BULLET_TRACES_OFS','BULLET_TRACE_SIZE','BULLET_TRACE_COUNT'):setattr(b,_k,globals()[_k])

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
 s.check(0x02e0,[V(h)],P+'NOT_FIRING');a(0x000a,V(out),I(40));a(6,V(t3),I(1));s.label(P+'NOT_FIRING')
 s.check(0x0457,[I(0),V(h)],P+'NOT_AIMED');a(0x000a,V(out),I(30));s.label(P+'NOT_AIMED')
 a(0x0470,V(h),V(t1));W=P+'W_DONE'
 s.check(0x0019,[V(t1),I(21)],P+'W_LOW')
 s.check(0x0019,[V(t1),I(24)],P+'W_PISTOL');s.go(P+'W_25');s.label(P+'W_PISTOL');a(0x000a,V(out),I(10));s.go(W)
 s.label(P+'W_25');s.check(0x0019,[V(t1),I(27)],P+'W_SHOTGUN');s.go(P+'W_28')
 s.label(P+'W_SHOTGUN');a(0x000a,V(out),I(10));s.check(0x0023,[F(15),V(d)],W);a(0x000a,V(out),I(15));s.go(W)
 s.label(P+'W_28');s.check(0x0019,[V(t1),I(32)],P+'W_AUTO');s.go(P+'W_33');s.label(P+'W_AUTO');a(0x000a,V(out),I(25));s.go(W)
 s.label(P+'W_33');s.check(0x0019,[V(t1),I(34)],P+'W_SNIPER');s.go(P+'W_35');s.label(P+'W_SNIPER');a(0x000a,V(out),I(35));s.go(W)
 s.label(P+'W_35');s.eq(t1,37,P+'W_HEAVY');s.check(0x0023,[F(15),V(d)],W);a(0x000a,V(out),I(30));s.go(W)
 s.label(P+'W_HEAVY');s.check(0x0019,[V(t1),I(38)],W);a(0x000a,V(out),I(60));s.go(W)
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
 """Subroutine `label`: reads the 16 bullet traces. R = registers cx cy cz hx hy hz x y z d n now bx by,
 plus 29/30 for the candidate and notfriend's verdict (notfriend: subroutine, 30@ = 1 when 29@ is not ours)."""
 a=s.add;P=label+'_';cx,cy,cz,hx,hy,hz,x,y,z,d,n,now,bx,by=[R[k] for k in ('cx','cy','cz','hx','hy','hz','x','y','z','d','n','now','bx','by')]
 s.label(label);a(0x01bd,V(now));a(0xddc,I(b.TRACE_SCAN_T),V(now));a(6,V(n),I(0))
 a(0x00a0,V(cj),V(cx),V(cy),V(cz));a(0x0007,V(hx),F(-9999));a(0x0007,V(hy),F(-9999));a(0x0007,V(hz),F(-9999))
 s.check(0x056e,[V(heli)],P+'NO_HELI');a(0x00aa,V(heli),V(hx),V(hy),V(hz));s.label(P+'NO_HELI')
 for k in range(b.BULLET_TRACE_COUNT):
  base=b.BULLET_TRACES_OFS+k*b.BULLET_TRACE_SIZE;nxt=P+'NEXT_%d'%k;heli_k=P+'HELI_%d'%k;car_k=P+'CAR_%d'%k
  a(0x0dd8,V(x),I(base+24),I(1),I(1));s.eq(x,1,nxt)
  a(0x0dd8,V(x),I(base+28),I(4),I(1));a(0x0085,V(y),V(now));a(0x0062,V(y),V(x));s.check(0x8019,[V(y),I(1000)],nxt)
  a(0x0dd8,V(x),I(base+12),I(4),I(1));a(0x0dd8,V(y),I(base+16),I(4),I(1));a(0x0dd8,V(z),I(base+20),I(4),I(1))
  a(0x050a,V(cx),V(cy),V(cz),V(x),V(y),V(z),V(d));s.check(0x0023,[F(4),V(d)],heli_k)
  # the round ended at CJ: who fired it? (start more than 4 m from CJ, so not his own)
  a(0x0dd8,V(x),I(base),I(4),I(1));a(0x0dd8,V(y),I(base+4),I(4),I(1));a(0x0dd8,V(z),I(base+8),I(4),I(1))
  for v,lo,hi in [(x,-3100,3100),(y,-3100,3100),(z,-100,1500)]:s.check(0x0021,[V(v),F(lo)],nxt);s.check(0x0023,[F(hi),V(v)],nxt)
  a(0x050a,V(cx),V(cy),V(cz),V(x),V(y),V(z),V(d));s.check(0x0021,[V(d),F(4)],nxt);s.check(0x0023,[F(200),V(d)],nxt)
  a(0x0a3e,V(x),V(y),V(z),F(2),F(2),F(3),V(29));_alive(s,29,car_k);s.call(notfriend);s.eq(30,1,car_k);a(0xddc,I(b.TB_SHOOTER),V(29));a(0xddc,I(b.TB_SHOOTER_T),V(now));s.go(nxt)
  s.label(car_k);a(0x0087,V(bx),V(x));a(0x000b,V(bx),F(-3));a(0x0087,V(by),V(y));a(0x000b,V(by),F(-3));a(0x000b,V(x),F(3));a(0x000b,V(y),F(3))
  a(0x053e,V(bx),V(by),V(x),V(y),I(-1),V(29));s.check(0x056e,[V(29)],nxt);s.check(0x803b,[V(29),V(heli)],nxt);a(0x046c,V(29),V(29));_alive(s,29,nxt);s.call(notfriend);s.eq(30,1,nxt);a(0xddc,I(b.TB_SHOOTER),V(29));a(0xddc,I(b.TB_SHOOTER_T),V(now));s.go(nxt)
  # the round ended at the helicopter and came from more than 10 m away (not our own gunners)
  s.label(heli_k);a(0x050a,V(hx),V(hy),V(hz),V(x),V(y),V(z),V(d));s.check(0x0023,[F(7),V(d)],nxt)
  a(0x0dd8,V(x),I(base),I(4),I(1));a(0x0dd8,V(y),I(base+4),I(4),I(1));a(0x0dd8,V(z),I(base+8),I(4),I(1))
  a(0x050a,V(hx),V(hy),V(hz),V(x),V(y),V(z),V(d));s.check(0x0021,[V(d),F(10)],nxt);a(0x000a,V(n),I(1))
  s.label(nxt)
 s.check(0x0019,[V(n),I(1)],P+'RET');a(0xddc,I(b.HELI_SHOT_T),V(now))
 s.label(P+'RET');s.ret()
