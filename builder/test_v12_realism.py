"""Helicover 1.2 realism: no teleports, smooth flight, honest escort-team logic, on the mocked VM of test_v25.py.
Mocked script execution only: real flight, pathing and animations are not simulated."""
import math,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;P=HERE/'test_v25.py'
_src=P.read_text();g={'__file__':str(P),'__name__':'v25_harness'}
exec(compile(_src[:_src.index('results=[]')],str(P),'exec'),g)
for _m in re.finditer(r'^def [a-z_0-9]+\(.*?(?=^\S)',_src,re.S|re.M):exec(compile(_m.group(0),str(P),'exec'),g)
World,VM,b,setup,summon,calls,command=g['World'],g['VM'],g['b'],g['setup'],g['summon'],g['calls'],g['command']
import build_v25_squad as sqb
results=[]
def passed(t):results.append('PASS: '+t)
def orders(w,op,who):return [x[2] for x in w.calls if x[1]==op and x[2][0]==who]
def last(w,op,who):
 o=orders(w,op,who);assert o,(hex(op),who);return o[-1]
def steps(w,vms,n):w.step(*vms,n=n)

def escort_world(tactics=0,fire=3,crew=None):
 """Support following CJ, then TEAM ON FOOT: rope hover, four guards down, back to FOLLOW."""
 w,c,_=setup();summon(w,c);ground=VM('Helicover_Ground',w);sq=VM('Helicover_Squad',w)

 w.health[1]=100;w.shared[b.TACTICS]=tactics;w.shared[b.FIRE]=fire
 if crew is not None:w.shared[b.CREW]=crew
 w.step(c,ground,sq,n=3)
 w.shared[b.CMD]=16;w.step(c,ground,sq,n=6)
 assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==1,(w.shared[b.STATE],w.messages)
 w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;w.step(c,ground,sq,n=40)
 team=[w.shared[b.GROUND_PUB+i] for i in range(4)]
 return w,c,ground,sq,team

# =================================================================== E1: the helicopter
# the glide to the rope point eases out and does not depend on the frame rate (it was a fixed 0.8 m per frame)
def glide_time(frame_ms):
 w,c,_=setup();summon(w,c);ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.frame_ms=frame_ms
 w.shared[b.CMD]=10;w.step(c,ground,n=6);assert w.shared[b.STATE]==19
 w.car=[c.v[26]+40.,c.v[27],c.v[28]+15.];w.speed=0.;t0=w.now;zs=[list(w.car)]
 for _ in range(int(8000/frame_ms)):
  w.step(c,ground);zs.append(list(w.car))
  if w.shared[b.STATE]==3:break
 assert w.shared[b.STATE]==3,(w.shared[b.STATE],frame_ms)
 dz=[math.dist(zs[i],zs[i-1]) for i in range(3,len(zs))]   # (the first frames include the one-off model height offset of SET_CAR_COORDINATES)
 return w.now-t0,max(dz)/(frame_ms/1000.)
t100,v100=glide_time(100);t33,v33=glide_time(33)
assert abs(t100-t33)<=900 and v100<=26 and v33<=26,(t100,t33,v100,v33)
assert 2500<=t100<=4500,t100
passed('Rope glide from 40 m eases out in about 3-4 s, never above 25 m/s, and takes the same time at 30 and 10 fps (%d ms / %d ms)'%(t100,t33))

# leaving by rope from fast flight: the helicopter slows down on the way, not on the spot
def exit_scene(speed,frozen=False,cr_v=0.):
 w,c,_=setup();summon(w,c);car=c.v[5];w.incar[1]=car;w.shared[b.EXIT_MODE]=1;w.speed=speed;w.car=[100.,-50.,60.]
 if frozen:w.frozen[car]=True;w.shared[b.FROZEN]=1;w.shared[b.CR_V]=cr_v
 w.step(c,n=2);w.calls.clear();w.shared[b.CMD]=15;w.step(c,n=4);return w,c,car
w,c,car=exit_scene(20.)
assert w.shared[b.STATE] in (21,22),(w.shared[b.STATE],w.messages)
assert abs(w.shared[b.DEST_X]-100.)<.01 and abs(w.shared[b.DEST_Y]-(-50.+30.))<.01,(w.shared[b.DEST_X],w.shared[b.DEST_Y])
passed('Exit by rope at 20 m/s: the destination is 30 m ahead (speed + 10 m), so the helicopter slows down on the way')
w,c,car=exit_scene(0.,frozen=True,cr_v=40.)
assert w.shared[b.STATE] in (21,22) and abs(w.shared[b.DEST_Y]-(-50.+50.))<.01,(w.shared[b.STATE],w.shared[b.DEST_Y])
passed('A script-flown helicopter (frozen, no real speed) is slowed by its cruise speed: 40 m/s means a point 50 m ahead')
w,c,car=exit_scene(2.)
assert w.shared[b.STATE]==23 and w.frozen.get(car),(w.shared[b.STATE],)
passed('Exit by rope at walking pace: freeze right here and drop')
# the scripted cruise carries on with the real speed (it used to restart from 0 = a dead stop)
w,c,car=exit_scene(20.)
moves=[x[2] for x in calls(w,0xab)];assert len(moves)>=3,'the cruise moves the helicopter'
s1=math.dist(moves[1][1:3],moves[0][1:3]);s2=math.dist(moves[2][1:3],moves[1][1:3])   # horizontal: the vertical easing is separate
assert .25<=s1<=.45 and s2>=1.5,('cruise steps',s1,s2)
passed('Scripted cruise starts at the real speed (0.3 m in the first 16 ms frame, then %.1f m per 100 ms), not from a standstill'%s2)

# state 18 (landing blocked / no route): with CJ on foot the pilot goes back to following after 15 s
w,c,_=setup();summon(w,c);w.shared[b.STATE]=18;w.step(c,n=2)
w.now+=14000;w.step(c,n=3);assert w.shared[b.STATE]==18
w.now+=2000;w.step(c,n=4);assert w.shared[b.STATE]==2,(w.shared[b.STATE],w.messages)
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.shared[b.STATE]=18;w.step(c,n=2);w.now+=30000;w.step(c,n=4);assert w.shared[b.STATE]==18
passed('Blocked-landing state ends by itself: back to FOLLOW after 15 s with CJ on foot, kept while CJ is aboard')

# emergency landing: finds a clear spot, and refuses orders that would flip the state back
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.step(c,n=2);w.health[c.v[5]]=300;w.step(c,n=4)
assert w.shared[b.STATE]==15,(w.shared[b.STATE],w.messages)
land=calls(w,0x743)[-1][2];assert abs(land[1])<.01 and abs(land[2]-(-45.))<.01,land    # a clear spot right below
w.messages.clear();command(w,c,2,ticks=3);assert w.shared[b.STATE]==15 and 'HCBUSY' in w.messages,(w.shared[b.STATE],w.messages)
passed('Emergency landing (CJ aboard, hull below 350): lands below at once and refuses FOLLOW while it is down')
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.clear_fn=lambda x,y:not(abs(x)<10 and abs(y+45)<10);w.step(c,n=2);w.health[c.v[5]]=300;w.step(c,n=4)
assert w.shared[b.STATE]==15
land=calls(w,0x743)[-1][2];assert w.clear_fn(land[1],land[2]) and 20<=math.dist(land[1:3],[0.,-45.])<=30,land
passed('Emergency landing skips a blocked spot and takes the first clear one 25 m around')
w,c,_=setup();summon(w,c);w.health[c.v[5]]=300;w.step(c,n=4)
assert w.shared[b.STATE]==13,(w.shared[b.STATE],w.messages)   # 13 = going home
passed('Hull below 350 with CJ on foot: the pilot retreats (it no longer depends on the crew phase)')

# a wedged helicopter climbs out under its own power (see test_v25) and a following one is not mistaken for wedged
# =================================================================== E2: the team on the ground
w,c,ground,sq,team=escort_world();V=(c,ground,sq);BG=sqb.BG_FORM
w.teleports.clear()
for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1],0.]
# lag ladder: more than 70 m from CJ for 60 s = let go; in view the game gets him back, out of sight he is deleted
w.pos[team[0]]=[0.,-150.,0.];w.offscreen={team[0]};steps(w,V,3)
assert w.shared[b.SQ_LAG]!=0 and team[0] in w.exists
w.now+=59000;steps(w,V,3);assert team[0] in w.exists,'not yet at 59 s'
w.now+=2000;steps(w,V,3)
assert team[0] not in w.exists and w.shared[b.GROUND_PUB]==-1 and w.shared[b.ESC_LAGGED]==1,(w.exists,w.shared[b.GROUND_PUB])
assert all(x in w.exists for x in team[1:]) and w.shared[b.ESCORT_ON]==1
passed('A guard 150 m behind for 60 s is let go (deleted out of sight); the rest of the team carries on')
w.pos[team[1]]=[0.,-150.,0.];w.offscreen=set();w.onscreen=True;steps(w,V,3);w.now+=61000;steps(w,V,3)
assert team[1] in w.exists and team[1] in w.released and w.shared[b.GROUND_PUB+1]==-1,'in view: handed back, not deleted'
passed('The same guard in view is handed back to the game (01C2), never deleted on screen')
w.pos[team[2]]=[0.,-150.,0.];w.pos[team[3]]=[0.,-160.,0.];steps(w,V,3);w.now+=61000;steps(w,V,6)
assert w.shared[b.ESCORT_ON]==0 and 'SQAWAY' in w.messages and 'SQLOST' not in w.messages,(w.shared[b.ESCORT_ON],w.messages)
assert not w.teleports,w.teleports
passed('Everybody lagging for 60 s: "lost you, team stands down", ESCORT_ON cleared, not a single teleport')
# a guard who catches up resets the clock
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
w.pos[team[0]]=[0.,-100.,0.];steps(w,V,3);w.now+=40000;steps(w,V,2);w.pos[team[0]]=[0.,-30.,0.];steps(w,V,3)
assert w.shared[b.SQ_LAG]==0
w.pos[team[0]]=[0.,-100.,0.];steps(w,V,3);w.now+=40000;steps(w,V,3);assert team[0] in w.exists
passed('Catching up within 70 m clears the lag clock')

# riding along: only a car CJ drives, one seat per guard, nobody boards a taxi or somebody else's car
def car_scene(model=400,driver=True,seats=3):
 w,c,ground,sq,team=escort_world();V=(c,ground,sq)
 for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1],0.]
 car=777;w.exists.add(car);w.cars[car]={'pos':[0.,0.,0.],'heading':0.};w.model[car]=model;w.seats_count=seats
 w.incar[1]=car
 if not driver:w.seats[(car,0)]=True   # CJ sits in a passenger seat: it is not free
 w.calls.clear();steps(w,V,3);return w,V,team,car
w,V,team,car=car_scene()
seatof={t:last(w,0x5ca,t)[3] for t in team if orders(w,0x5ca,t)}
assert seatof=={team[0]:0,team[1]:1,team[2]:2},seatof
passed('CJ drives a 4-door car: guards 0, 1, 2 take passenger seats 0, 1, 2 (guard 3 has no seat)')
w,V,team,car=car_scene(driver=False)
assert not any(orders(w,0x5ca,t) for t in team),'CJ rides as a passenger (taxi, bus, a lift): the team does not board'
passed('CJ is a passenger of somebody else\'s car: the guards do not climb in')
w,V,team,car=car_scene(seats=1)
assert [t for t in team if orders(w,0x5ca,t)]==[team[0]],[t for t in team if orders(w,0x5ca,t)]
passed('A bike / two-seater has one passenger seat: only guard 0 rides')
# a recall: the guards walk to the ropes, the pilot waits for them (no warp), whoever is not there after 25 s stays
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1],0.]
w.pos[team[3]]=[0.,-40.,0.];w.blocked={team[3]};w.teleports.clear();w.calls.clear()
w.car=[0.,-40.,28.];w.shared[b.CMD]=17;steps(w,V,6);assert w.shared[b.STATE]==19
w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;steps(w,V,40)
assert w.shared[b.ESCORT_ON]==3 and team[3] in w.exists,(w.shared[b.ESCORT_ON],w.messages)
steps(w,V,60);assert all(t in w.exists for t in team),'the three at their ropes wait for the fourth'
w.now+=26000;steps(w,V,70)
assert team[3] in w.released or team[3] not in w.exists,'the one who never arrived is left behind'
assert w.shared[b.ESCORT_ON]==0 and not [t for t in w.teleports if t['who']==team[3]]
passed('Recall: the pilot waits up to 25 s for the guards; the one who cannot get there stays behind and is never teleported')
# a guard sitting in a car gets out (0633), he is not teleported out
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1],0.]
car=778;w.exists.add(car);w.cars[car]={'pos':[2.,2.,0.],'heading':0.};w.model[car]=400;w.incar[team[0]]=car;w.teleports.clear();w.calls.clear()
V=(c,ground)   # the squad worker is left out: it would also tell a rider to leave the car, and this test is about the rope worker
w.car=[0.,-40.,28.];w.shared[b.CMD]=17;steps(w,V,6);w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;steps(w,V,40)
assert orders(w,0x633,team[0]) and not orders(w,0x362,team[0]),(orders(w,0x633,team[0]),orders(w,0x362,team[0]))
passed('A guard in a car gets out first (task) and then runs to his rope; no teleport out of the car')
# nobody on the ropes: the pilot gives up after 90 s instead of hovering for ever; an abandoned request leaves no stale team flag
w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0.;ground=VM('Helicover_Ground',w);w.step(c,ground,n=3)
w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=10);assert w.shared[b.GROUND_PUB]!=-1 and w.frozen.get(c.v[5])
w.now+=91000;w.step(c,ground,n=6)
assert w.shared[b.GROUND_PUB]==-1 and not w.frozen.get(c.v[5]) and 'RGLATE' in w.messages,(w.messages,w.shared[b.GROUND_PUB])
passed('Rope pickup nobody takes: after 90 s the ropes go up and the helicopter is free again')
w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);ground=VM('Helicover_Ground',w);w.step(c,ground,n=3)
w.shared[b.ESCORT_ON]=2;w.shared[b.ESCORT_CMD]=1;w.playing=False;w.step(ground,n=4)
assert w.shared[b.ESCORT_ON]==0,w.shared[b.ESCORT_ON]
passed('CJ dies / is arrested while a team deployment starts: ESCORT_ON is reset, support is not stuck on a team that never came')

# a recall for a team that is gone by the time the helicopter arrives does not leave it hovering frozen
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
w.car=[0.,-40.,28.];w.shared[b.CMD]=17;steps(w,V,6);assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==2
for t_ in team:w.dead.add(t_)
steps(w,V,12);w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;steps(w,V,60)
assert w.shared[b.ESCORT_ON]==0 and w.shared[b.STATE]==2 and not w.frozen.get(c.v[5]),(w.shared[b.ESCORT_ON],w.shared[b.STATE],w.messages)
passed('Recall for a team that no longer exists: the pilot does not hang frozen, he goes back to FOLLOW')

# =================================================================== E3: squad tactics
def anchor_scene():
 w,c,ground,sq,team=escort_world();V=(c,ground,sq)
 for k,t_ in enumerate(team):w.pos[t_]=[BG[k][0],BG[k][1],0.]
 w.walk.clear();w.calls.clear();w.now+=1000;steps(w,V,3);return w,c,V,team
# the formation hangs on the direction CJ travels in, not on the way he faces
w,c,V,team=anchor_scene()
assert (round(w.shared[b.FORM_UX],2),round(w.shared[b.FORM_UY],2))==(0.,1.),(w.shared[b.FORM_UX],w.shared[b.FORM_UY])
w.velocity[1]=[3.,0.,0.];w.char_speed={1:3.};steps(w,V,8)
assert w.shared[b.FORM_UY]>.99,'a sidestep of 0.8 s does not turn the formation'
steps(w,V,10);assert w.shared[b.FORM_UX]>.99 and abs(w.shared[b.FORM_UY])<.05,(w.shared[b.FORM_UX],w.shared[b.FORM_UY])
passed('Formation anchor: walking 60+ degrees off the old direction for 1.5 s re-anchors it, a short sidestep does not')
w.velocity.pop(1);w.char_speed={};ux,uy=w.shared[b.FORM_UX],w.shared[b.FORM_UY];w.now+=5000;steps(w,V,20)
assert (w.shared[b.FORM_UX],w.shared[b.FORM_UY])==(ux,uy)
passed('Standing still (turning, aiming) never rotates the formation: the guards do not run round CJ')
# the point guard ahead of CJ is the one at (0, 3.2) east of CJ once the anchor points east
w.pos[1]=w.player=[0.,0.,0.]
for k,t_ in enumerate(team):w.pos[t_]=[0.,0.,0.]
w.calls.clear();w.now+=1500;steps(w,V,4)
o=last(w,0x5d3,team[0]);assert abs(o[1]-BG[0][1])<.01 and abs(o[2]+BG[0][0])<.01,o     # ahead (y of the table) is now +x, right is -y
o=last(w,0x5d3,team[1]);assert abs(o[1]-BG[1][1])<.01 and abs(o[2]+BG[1][0])<.01,o     # left rear guard of the diamond
passed('Slots are placed in the anchored frame: ahead = travel direction, right = (uy, -ux)')
# CJ shooting ahead: nobody stands in his line of fire
w,c,V,team=anchor_scene()
def aim_north(w):
 for key,val in ((b.CJ_AIM_X,0.),(b.CJ_AIM_Y,1.),(b.CJ_AIM_Z,0.),(b.CJ_AIM_PX,0.),(b.CJ_AIM_PY,0.),(b.CJ_AIM_PZ,1.)):w.shared[key]=val
 w.shared[b.CJ_AIM_T]=w.now;w.shared[b.CJ_SHOT_T]=w.now
aim_north(w);w.calls.clear();w.now+=1500;aim_north(w);steps(w,V,3)
o=last(w,0x5d3,team[0]);assert abs(o[1])>=1.9,('the point guard stepped out of the line',o)
for k in (1,2):
 o=last(w,0x5d3,team[k]) if orders(w,0x5d3,team[k]) else None
 assert o is None or abs(math.dist(o[1:3],[0.,0.])-math.dist(BG[k],[0.,0.]))<.05,(k,o)    # slots beside the line stay where they are
passed('CJ shooting ahead: the guard in front of him steps 2 m out of his line of fire, the others stay in place')
w.calls.clear();w.now+=3000;steps(w,V,3)
o=last(w,0x5d3,team[0]) if orders(w,0x5d3,team[0]) else None
assert o is None or abs(o[1])<.05,('after the shooting stops (aim line older than 1.2 s) he returns to his slot',o)
passed('When CJ stops shooting the guard returns to his slot')
# assault leash is 25 m, the medic stays
w,c,ground,sq,team=escort_world(tactics=1);V=(c,ground,sq)
AS=sqb.AS_FORM
for k,t_ in enumerate(team):w.pos[t_]=list(AS[k])+[0.]
hostile=950;w.exists.add(hostile);w.pos[hostile]=[20.,0.,0.];w.pedtype[hostile]=7;w.weapons[hostile]=30;w.civilians=[hostile];w.damage.add((1,hostile))
w.pos[team[0]]=[0.,27.,0.];w.calls.clear();w.now=(w.now//6000+1)*6000+100;beyond=[]
for _ in range(6):
 n0=len(w.calls);d=math.dist(w.pos[team[0]][:2],[0.,0.]);steps(w,V,1)
 if d>25.2:beyond+=[x for x in w.calls[n0:] if x[1] in (0x5d3,0x637) and x[2][0]==team[0]]
assert w.shared[b.SQ_T]==hostile,'the hostile is a threat'   # guard 0 is the one who bounds forward in this 3 s slot
assert beyond and all(x[1]==0x5d3 and abs(x[2][2]-AS[0][1])<.5 for x in beyond),('beyond 25 m he only turns back',beyond)
passed('Assault: a guard 27 m from CJ turns back to his slot (25 m cap, was 40 m)')
assert not orders(w,0x637,team[3]),'the medic never joins the advance'
passed('Assault: the medic stays with CJ')
# a guard keeps his target while it is alive and still a threat
def two_hostiles():
 w,c,ground,sq,team=escort_world();V=(c,ground,sq)
 for k,t_ in enumerate(team):w.pos[t_]=[BG[k][0],BG[k][1],0.]
 hs=[]
 for i,(x,y) in enumerate([(14.,6.),(16.,-6.),(12.,0.)]):
  h=960+i;w.exists.add(h);w.pos[h]=[x,y,0.];w.pedtype[h]=7;w.weapons[h]=30;w.shooting_chars.add(h);hs.append(h)
 w.civilians=list(hs);w.damage.add((1,hs[0]));return w,c,V,team,hs
w,c,V,team,hs=two_hostiles();w.now+=3000;steps(w,V,12)
mine=last(w,0x634,team[3])[1];assert mine in hs,mine
D=963;w.exists.add(D);w.pos[D]=[7.,3.,0.];w.pedtype[D]=7;w.weapons[D]=30;w.shooting_chars.add(D);w.civilians.append(D);w.damage.add((1,D))
w.calls.clear();w.now+=1000;steps(w,V,10)
lst=[w.shared[b.SQ_T+i] for i in range(4)];assert lst[0]==D,('a closer attacker takes the top of the list',lst)
o3=orders(w,0x634,team[3]);assert not o3 or all(o[1]==mine for o in o3),(mine,o3,lst)
o0=orders(w,0x634,team[0]);assert o0 and o0[-1][1]==D,('guard 0 always takes the top threat',o0)
passed('Guards keep the target they are on while it lives (no flipping when the threat list is reshuffled)')

# =================================================================== E4: gunners are not lasers
fire_world,target=g['fire_world'],g['target']
def bullet_ends(jitter,dist=40.):
 w,c,f=fire_world();w.jitter=jitter;npc=target(w);w.pos[npc]=[dist,0.,0.];w.damage.add((1,npc));w.speed=0.;w.step(c,f,n=40)
 return [x[2][3:6] for x in calls(w,0x6bc)],w,npc
ends,w,npc=bullet_ends(False)
assert len(ends)>=10 and max(math.dist(e,ends[0]) for e in ends)<.05,('no jitter in the mock: every bullet lands on the same point',len(ends))
ends,w,npc=bullet_ends(True)
cx=[sum(e[i] for e in ends)/len(ends) for i in range(3)];spread=[math.dist(e,cx) for e in ends]
assert len(ends)>=10 and max(spread)>.15,('the bullets scatter',max(spread))
r=.1+.01*40.+.02*0.;assert max(spread)<=2*r*math.sqrt(3)+.7,('but stay near the target (+-%.2f m per axis at 40 m)'%r,max(spread))
passed('Door gunners scatter their bullets (about +-0.5 m at 40 m) instead of putting every round on one point')
near,_,_=bullet_ends(True,dist=8.);far,_,_=bullet_ends(True,dist=70.)
def sd(e):
 m=[sum(x[i] for x in e)/len(e) for i in range(3)];return math.sqrt(sum(math.dist(x,m)**2 for x in e)/len(e))
assert sd(near)<sd(far),(sd(near),sd(far))
passed('The scatter grows with the distance to the target (%.2f m at 8 m, %.2f m at 70 m)'%(sd(near),sd(far)))

# =================================================================== E5: decor (model, clothes, weapon) changes at once
for crew,expect in ((0,[106,107,106,107]),(1,[287]*4),(2,[285]*4)):
 w,c,ground,sq,team=escort_world(crew=crew)
 assert [w.skin[t_] for t_ in team]==expect,(crew,[w.skin[t_] for t_ in team])
passed('The team that ropes down wears the crew setting: Grove 106/107, Army 287, SWAT 285 (it was always SWAT)')
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
for k,t_ in enumerate(team):w.pos[t_]=[BG[k][0],BG[k][1],0.];w.health[t_]=130;w.armor[t_]=40;w.actor_heading[t_]=33.
w.teleports.clear();old=list(team);w.shared[b.CREW]=1;steps(w,V,12)
new=[w.shared[b.GROUND_PUB+i] for i in range(4)]
assert all(n_ not in old and w.skin[n_]==287 for n_ in new) and all(o_ not in w.exists for o_ in old),(old,new,[w.skin.get(n_) for n_ in new])
assert all(w.pos[n_][:2]==[BG[i][0],BG[i][1]] and w.health[n_]==130 and w.armor[n_]==40 and w.actor_heading[n_]==33. for i,n_ in enumerate(new)),[(w.pos[n_],w.health[n_],w.armor[n_]) for n_ in new]
assert w.shared[b.TEAM_CREW]==1 and w.shared[b.ESCORT_ON]==1 and not w.teleports,(w.shared[b.TEAM_CREW],w.shared[b.ESCORT_ON],w.teleports)
passed('Changing the crew on the menu re-dresses the team on the ground at once: same spot, heading, health and armour, nobody teleports')
w.shared[b.CREW]=0;steps(w,V,12);new2=[w.shared[b.GROUND_PUB+i] for i in range(4)]
assert [w.skin[n_] for n_ in new2]==[106,107,106,107] and w.shared[b.TEAM_CREW]==0
passed('Grove clothes alternate between the two Families skins')
# a guard riding in a car is re-dressed as soon as he gets out
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
car=777;w.exists.add(car);w.cars[car]={'pos':[0.,0.,0.],'heading':0.};w.model[car]=400;w.incar[1]=car;w.incar[team[1]]=car;w.shared[b.CREW]=1;steps(w,V,10)   # CJ drives, one guard rides with him
assert w.skin[team[1]]==285 and team[1] in w.exists and w.shared[b.TEAM_CREW]==2,'the passenger keeps his clothes while he rides'
hs=[w.shared[b.GROUND_PUB+i] for i in range(4)];riders=[h for h in hs if h in w.incar];walkers=[h for h in hs if h not in w.incar]
assert team[1] in riders and walkers and all(w.skin[h]==285 for h in riders) and all(w.skin[h]==287 for h in walkers),(hs,riders,[w.skin[h] for h in hs])
w.incar.pop(1);[w.incar.pop(h,None) for h in riders];steps(w,V,8);assert all(w.skin[w.shared[b.GROUND_PUB+i]]==287 for i in range(4)) and w.shared[b.TEAM_CREW]==1,[w.skin[w.shared[b.GROUND_PUB+i]] for i in range(4)]
passed('A guard in a car keeps the old clothes until he steps out, then changes in place')
# the weapon is live as well
w,c,ground,sq,team=escort_world();V=(c,ground,sq);w.calls.clear();w.shared[b.WEAPON_SETTING]=29;steps(w,V,8)
assert all(any(x[1]==0x1b2 and x[2][0]==t_ and x[2][1]==29 for x in w.calls) for t_ in team),'every guard gets the new weapon at once'
passed('Changing the crew weapon arms the team on the ground at once')
# new heli crew members are armed the moment they are created (not at the next Fire pass)
w,c,_=setup();summon(w,c);w.calls.clear();w.shared[b.CREW]=1;w.step(c,n=10)
fresh=[c.v[v] for v in (13,14,15,16)]
assert all(any(x[1]==0x1b2 and x[2][0]==g_ for x in w.calls) for g_ in fresh),'gunners hold a weapon right after the swap'
passed('Door gunners created by a crew change are armed immediately')
# the model swap waits only for a rope motion
w,c,_=setup();summon(w,c);old=c.v[5];w.shared[b.ROPE_BUSY]=1;w.shared[b.MODEL]=497;w.messages.clear();w.step(c,n=6)
assert c.v[5]==old and 'HCSLATE' in w.messages and w.messages.count('HCSLATE')==1,(c.v[5],old,w.messages)
w.shared[b.ROPE_BUSY]=0;w.step(c,n=6);assert c.v[5]!=old and w.model[c.v[5]]==497 and 'HCSWAP' in w.messages,(c.v[5],w.messages)
passed('Model swap: instant, except while somebody hangs on a rope (then right after it ends, one message)')
# swapping the helicopter while the ropes hang out and CJ has not climbed yet: the rope worker follows, the new one stays frozen
w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0.;ground=VM('Helicover_Ground',w);w.step(c,ground,n=3)
w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=10);w.now+=8000;w.step(c,ground,n=10)
assert w.shared[b.GROUND_PUB]!=-1 and w.shared[b.ROPE_BUSY]==0,(w.shared[b.GROUND_PUB],w.shared[b.ROPE_BUSY])
old=c.v[5];ropes=[w.shared[b.GROUND_PUB+i] for i in range(4)];w.shared[b.MODEL]=497;w.step(c,ground,n=12)
assert c.v[5]!=old and w.frozen.get(c.v[5]) and all(r_ in w.exists for r_ in ropes) and w.shared[b.GROUND_PUB]==ropes[0],('rope session survives the swap',c.v[5],old,w.shared[b.GROUND_PUB],ropes)
passed('Helicopter swapped while the ropes are out: the rope session carries on with the new helicopter, still frozen on the spot')

# the same swap with a team on the ground, and a crew change while the ropes are out
w,c,ground,sq,team=escort_world();V=(c,ground,sq);old=c.v[5];w.calls.clear();w.shared[b.MODEL]=497;steps(w,V,14)
assert not any(x[2]==[b.SQ_GROUP,0] for x in calls(w,0xddc)),'the squad never lets go of the team on the ground during the swap'
assert c.v[5]!=old and w.shared[b.ESCORT_ON]==1 and all(t_ in w.exists for t_ in team) and w.shared[b.GROUND_PUB]==team[0],(w.shared[b.ESCORT_ON],w.messages)
passed('Helicopter model changed while the escort team is on the ground: the team is not recalled or lost')
w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0.;ground=VM('Helicover_Ground',w);w.step(c,ground,n=3)
w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=10);w.now+=8000;w.step(c,ground,n=10);ropes=[w.shared[b.GROUND_PUB+i] for i in range(4)]
w.shared[b.CREW]=1;w.step(c,ground,n=14)
assert w.shared[b.GROUND_PUB]==ropes[0] or all(r_ in w.exists or w.skin.get(w.shared[b.GROUND_PUB+i])==287 for i,r_ in enumerate(ropes)),(ropes,)
assert w.shared[b.GROUND_PUB]!=-1 and w.frozen.get(c.v[5]) and w.shared[b.ACREW]==1,(w.shared[b.GROUND_PUB],w.shared[b.ACREW])
passed('Crew changed while the ropes are out: the rope session carries on, the helicopter stays frozen on its spot')
# a swap asked for during CJ\'s climb waits until the rope work is over, then CJ is moved into the new helicopter
w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0.;ground=VM('Helicover_Ground',w);w.step(c,ground,n=3)
w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=5);rope=[w.shared[b.GROUND_PUB+i] for i in range(4)]
for ch,(x,y) in zip(rope,[(-1.5,1.2),(1.5,1.2),(-1.5,-1.2),(1.5,-1.2)]):w.pos[ch]=[x,y,.7]
w.now+=8000;w.player=[0.,-3.,.7];w.step(c,ground,n=8);assert w.control is False
old=c.v[5];w.shared[b.MODEL]=497;w.messages.clear();w.step(c,ground,n=4)
assert c.v[5]==old and w.control is False and 'HCSLATE' in w.messages,(c.v[5],old,w.messages)
w.step(c,ground,n=400)
assert c.v[5]!=old and w.model[c.v[5]]==497 and w.incar.get(1)==c.v[5] and w.control is True and not w.frozen.get(old),(c.v[5],old,w.incar.get(1),w.control)
passed('Model swap asked for during the climb waits for the end of the rope work, then CJ sits in the new helicopter')

# =================================================================== one long day: no teleports anywhere
w,c,ground,sq,team=escort_world();V=(c,ground,sq,VM('Helicover_Fire',w))
for k,t_ in enumerate(team):w.pos[t_]=[BG[k][0],BG[k][1],0.]
w.teleports.clear();w.calls.clear()
# a fire fight: two hostiles come at CJ and die
for i,(x,y) in enumerate([(18.,6.),(18.,-6.)]):
 h=970+i;w.exists.add(h);w.pos[h]=[x,y,0.];w.pedtype[h]=7;w.weapons[h]=30;w.shooting_chars.add(h);w.damage.add((1,h));w.civilians.append(h)
steps(w,V,40)
for h in (970,971):w.dead.add(h);w.shooting_chars.discard(h)
steps(w,V,20)
# CJ takes a car and drives 600 m away at 15 m/s, the squad cannot follow
car=777;w.exists.add(car);w.cars[car]={'pos':[0.,0.,0.],'heading':0.};w.model[car]=400;w.incar[1]=car;w.seats_count=0   # a car with no free seat for the squad
for _ in range(400):
 w.cars[car]['pos'][0]+=1.5;w.player=list(w.cars[car]['pos']);w.speed=15.;w.car_speeds={car:15.};w.step(*V)
w.car_speeds={};w.incar.pop(1);w.player=[w.cars[car]['pos'][0],w.cars[car]['pos'][1],0.];w.speed=12.
steps(w,V,100);w.now+=65000;steps(w,V,20)
alive=[g_ for g_ in team if g_ in w.exists and g_ not in w.released]
assert w.shared[b.ESCORT_ON]==0 and not alive and 'SQAWAY' in w.messages,('the lagging team is stood down',w.shared[b.ESCORT_ON],alive,w.messages)
# the helicopter, still following him, is told to leave
command(w,c,4,ticks=6);w.now+=40000;steps(w,V,20)
bad=[x for x in w.teleports if x['who']!=c.v[5] or x['dist']>12.]
bad=[x for x in bad if not (x['who']==c.v[5] and x['op']==0xab)]
assert not bad,[(hex(x['op']),x['who'],round(x['dist'],1)) for x in bad][:6]
passed('A whole day - deploy, fire fight, CJ drives off, the squad cannot keep up, dismiss - without a single teleport of a person')

text='\n'.join(results)+'\nMocked script execution only: real flight, pathing and animations are not simulated.\n'
(b.OUT/'realism_tests.txt').write_text(text);print(text)
