"""Helicover 1.2 realism: no teleports, smooth flight, honest escort-team logic, on the mocked VM of test_v25.py.
Mocked script execution only: real flight, pathing and animations are not simulated."""
import math,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;P=HERE/'test_v25.py'
_src=P.read_text();g={'__file__':str(P),'__name__':'v25_harness'}
exec(compile(_src[:_src.index('results=[]')],str(P),'exec'),g)
for _m in re.finditer(r'^def [a-z_0-9]+\(.*?(?=^\S)',_src,re.S|re.M):exec(compile(_m.group(0),str(P),'exec'),g)
World,VM,b,setup,summon,calls,command,invariants=g['World'],g['VM'],g['b'],g['setup'],g['summon'],g['calls'],g['command'],g['invariants']
import build_v25_squad as sqb
results=[]
def passed(t):results.append('PASS: '+t)
def orders(w,op,who):return [x[2] for x in w.calls if x[1]==op and x[2][0]==who]
def last(w,op,who):
 o=orders(w,op,who);assert o,(hex(op),who);return o[-1]
def steps(w,vms,n):w.step(*vms,n=n)
def shoots_cj(w,who):
 """who fires at CJ, every frame from now on (the brain sees the rounds pass him)."""
 w.shot_at=dict(getattr(w,'shot_at',{}));w.shot_at[who]=[w.player[0],w.player[1],w.player[2]+1.];w.shooting_chars.add(who)

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
 dz=[math.dist(zs[i],zs[i-1]) for i in range(4,len(zs))]   # (the first frames include the one-off model height offset of SET_CAR_COORDINATES and the first step after the test's own teleport, which lands in the middle of a core nap)
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
assert team[1] in w.exists and team[1] not in w.released and w.shared[b.GROUND_PUB+1]==-1 and not w.handed,'in view: neither deleted nor handed to the game'
assert team[1] in w.wander and w.weapons[team[1]]==0 and w.shared[b.LEAVE]==team[1] and w.shared[b.LEAVE_N]==1 and not invariants(w),(w.wander,invariants(w))
passed('The same guard in view is never deleted on screen and never handed to the game (beta 4): he puts the gun away and walks off as ours')
w.offscreen={team[1]};steps(w,V,3);assert team[1] not in w.exists and w.shared[b.LEAVE]==-1 and w.shared[b.LEAVE_N]==0;w.offscreen=set()
passed('...and is removed the moment nobody sees him')
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
def car_scene(model=400,driver=True,seats=3,npc_seat=None,cj_seat=0):
 w,c,ground,sq,team=escort_world();V=(c,ground,sq)
 for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1],0.]
 car=777;w.exists.add(car);w.cars[car]={'pos':[0.,0.,0.],'heading':0.};w.model[car]=model;w.seats_count=seats
 w.incar[1]=car
 if not driver:
  w.seats[(car,-1)]=555;w.cj_is_passenger=True                                       # somebody else drives ...
  if cj_seat is not None:w.seats[(car,cj_seat)]=True                                 # ... and CJ sits in a passenger seat the squad could want (None: a seat beyond theirs, e.g. a bus)
 if npc_seat is not None:w.seats[(car,npc_seat)]=True                                # a passenger who stayed in the car CJ drives
 w.calls.clear();steps(w,V,3);return w,V,team,car
w,V,team,car=car_scene()
seatof={t:last(w,0x5ca,t)[3] for t in team if orders(w,0x5ca,t)}
assert seatof=={team[0]:0,team[1]:1,team[2]:2},seatof
passed('CJ drives a 4-door car: guards 0, 1, 2 take passenger seats 0, 1, 2 (guard 3 has no seat)')
w,V,team,car=car_scene(driver=False)
assert not any(orders(w,0x5ca,t) for t in team),'CJ rides as a passenger (taxi, bus, a lift): the team does not board'
passed('CJ is a passenger of somebody else\'s car: the guards do not climb in')
w,V,team,car=car_scene(driver=False,cj_seat=None)     # a lift where the three seats the squad would take all look free (a bus, a back seat)
assert not any(orders(w,0x5ca,t) for t in team),'who drives is asked from the car (its driver is not CJ), not guessed from free seats'
w,V,team,car=car_scene(npc_seat=1)
seatof={t:last(w,0x5ca,t)[3] for t in team if orders(w,0x5ca,t)}
assert seatof=={team[0]:0,team[2]:2},('CJ drives a car that kept a passenger in seat 1: guards 0 and 2 still ride, guard 1 has no seat',seatof)
passed('CJ at the wheel is read from the car\'s driver: a car that kept a passenger is still boarded (free seats only), a lift in the back seat is not')
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
assert all(t not in w.exists for t in team[:3]),'the three at their ropes are aboard'
assert team[3] in w.exists and team[3] not in w.released and not w.handed,'the one who never arrived is left behind - and is NOT handed to the game (beta 4: that was the armed "policeman" the player got a star for)'
assert team[3] in w.wander and w.weapons[team[3]]==0 and team[3] in [w.shared[b.LEAVE+k] for k in range(8)] and not invariants(w),(w.wander,invariants(w))
assert w.shared[b.ESCORT_ON]==0 and not [t for t in w.teleports if t['who']==team[3]]
passed('Recall: the pilot waits up to 25 s for the guards; the one who cannot get there stays behind unarmed as ours (never teleported, never handed to the game)')
# the player's report: deploy -> recall -> deploy again. The straggler of the first team must not be a stray armed ped, and the new team is complete
w.offscreen={team[3]};steps(w,V,30);assert team[3] not in w.exists and w.shared[b.LEAVE_N]==0;w.offscreen=set()
w.shared[b.CMD]=16;steps(w,V,6);assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==1,(w.shared[b.STATE],w.messages)
w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;steps(w,V,60)
team2=[w.shared[b.GROUND_PUB+i] for i in range(4)]
assert w.shared[b.ESCORT_ON]==1 and len(set(team2))==4 and all(t in w.exists for t in team2) and not set(team2)&set(team) and not w.handed and not invariants(w),(w.shared[b.ESCORT_ON],team2,invariants(w))
passed('Deploy - recall - deploy again: the second team is four new men, nobody of the first is left as a stray armed ped')
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
cover=[w.shared[b.GROUND_PUB+i] for i in range(4)];w.now+=91000;w.step(c,ground,n=6)
assert 'RGLATE' in w.messages and w.shared[b.ESCORT_ON]==3 and w.shared[b.ROPE_BUSY]==1 and w.shared[b.ROPE_WAIT]==0 and all(t in w.exists for t in cover),(w.messages,w.shared[b.ESCORT_ON])
for _ in range(400):
 w.step(c,ground)
 if w.shared[b.STATE]==2:break
assert w.shared[b.STATE]==2 and w.shared[b.GROUND_PUB]==-1 and not w.frozen.get(c.v[5]) and w.shared[b.ESCORT_ON]==0 and w.shared[b.ROPE_BUSY]==0,(w.shared[b.STATE],w.messages,w.shared[b.GROUND_PUB])
assert all(t not in w.exists for t in cover) and not w.handed and not set(cover)&w.released and not invariants(w),(w.handed,invariants(w))
passed('Rope pickup nobody takes: after 90 s the cover team climbs back aboard (it used to be let go on the spot), the ropes go up and the helicopter follows again')
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
w.cj_aim=[0.,30.,1.];w.calls.clear();w.now+=1500
for _ in range(3):w.shooting=True;steps(w,V,1)                 # the brain sees his shots and reports the line; nobody writes it by hand
w.shooting=False
assert w.now-w.shared[b.CJ_AIM_T]<=300 and abs(w.shared[b.CJ_AIM_X])<.05 and w.shared[b.CJ_AIM_Y]>.99,('the line of his shots comes from the brain',w.shared[b.CJ_AIM_X],w.shared[b.CJ_AIM_Y])
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
# a guard keeps the man the brain gave him; a new attacker goes to the guard whose hands are free
def attackers_scene(places):
 w,c,ground,sq,team=escort_world();V=(c,ground,sq)
 for k,t_ in enumerate(team):w.pos[t_]=[BG[k][0],BG[k][1],0.]
 hs=[]
 for i,(x,y) in enumerate(places):
  h=960+i;w.exists.add(h);w.pos[h]=[x,y,0.];w.pedtype[h]=7;w.weapons[h]=30;w.health[h]=100000;shoots_cj(w,h);hs.append(h)
 w.civilians=list(hs);return w,c,V,team,hs
def men(w):return [w.shared[b.SQ_T+i] for i in range(4)]
w,c,V,team,hs=attackers_scene([(14.,6.)]);w.now+=3000;steps(w,V,12)
A=hs[0];assert men(w)==[A]*4,men(w)
firing=[k for k in range(4) if w.shared[b.SQ_BR_ST+k]==2];free=[k for k in range(4) if w.shared[b.SQ_BR_ST+k]==3]
assert len(firing)==3 and len(free)==1,('three rifles on one man, the fourth keeps him covered',[w.shared[b.SQ_BR_ST+k] for k in range(4)])
D=963;w.exists.add(D);w.pos[D]=[-12.,-5.,0.];w.pedtype[D]=7;w.weapons[D]=30;w.health[D]=100000;shoots_cj(w,D);w.civilians.append(D)
w.calls.clear();seen=[]
for _ in range(15):steps(w,V,1);seen.append(men(w))
assert all(m[k]==A for m in seen for k in firing),('the men who are firing never leave their man',seen)
assert seen[-1][free[0]]==D and w.shared[b.SQ_BR_ST+free[0]]==2,('the free guard takes the new attacker',seen[-1])
for k in range(4):
 shots=[x[2][1] for x in w.calls if x[1] in (0x634,0x74d,0x637,0x7a5) and x[2][0]==team[k]]
 assert all(t_==(A if k in firing else D) for t_ in shots),(k,shots)
passed('Guards keep the man they are firing at while he lives; a new attacker is taken by the guard whose hands are free (no flipping)')

# the squad takes a man the brain names even when he is far outside anything the squad could look for itself
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
for k,t_ in enumerate(team):w.pos[t_]=[BG[k][0],BG[k][1],0.]
h=980;w.exists.add(h);w.pos[h]=[45.,0.,0.];w.pedtype[h]=7;w.weapons[h]=30;w.health[h]=100000;w.actor_heading[h]=270.;w.civilians=[h]
steps(w,V,6);assert h not in men(w) and not any(x[2][1]==h for x in w.calls if x[1] in (0x634,0x74d,0x637,0x7a5)),'45 m away, armed, back turned and silent: nobody\'s man'
shoots_cj(w,h);steps(w,V,8)
assert men(w).count(h)==4 and [w.shared[b.SQ_BR_ST+k] for k in range(4)].count(2)==3,('a shooter the brain named is taken',men(w))
passed('The squad takes a shooter the brain names, even 45 m away')

# CJ's line of fire comes from the brain (it reads his shots in the game itself): his own shot gives it in that very frame,
# somebody else's rounds never do - the scripts read no bullet traces any more
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
for k,t_ in enumerate(team):w.pos[t_]=[BG[k][0],BG[k][1],0.]
steps(w,V,3);t0=w.shared[b.CJ_AIM_T]
h=985;w.exists.add(h);w.pos[h]=[-30.,0.,1.];w.pedtype[h]=7;w.weapons[h]=30;w.health[h]=100000;w.civilians=[h]
w.shot_at={h:[30.,0.,1.]};w.shooting_chars={h};steps(w,V,8)                       # a stranger's rounds along a line through CJ
assert w.shared[b.CJ_AIM_T]==t0,'rounds of somebody else are never CJ\'s line, however close they pass'
w.shooting_chars=set();w.cj_aim=[24.,0.,1.];w.shooting=True;steps(w,V,1);w.shooting=False
assert w.now-w.shared[b.CJ_AIM_T]<=150 and w.shared[b.CJ_AIM_X]>.99 and abs(w.shared[b.CJ_AIM_Y])<.05,('his own shot: the line in the frame of the shot',w.now-w.shared[b.CJ_AIM_T],w.shared[b.CJ_AIM_X])
t1=w.shared[b.CJ_AIM_T];steps(w,V,20);assert abs(w.shared[b.CJ_AIM_T]-t1)<=150,'no new shot: the line is not refreshed'
assert not [x for x in w.calls if x[1]==0xdd8 and 0xCFA500<=x[2][1]<0xCFA500+16*44],'no script reads the game\'s bullet traces (the table at G+0xCFA500)'
passed('CJ\'s line of fire comes from the brain: there in the frame of his shot, never from somebody else\'s rounds; the scripts read no bullet traces')

# =================================================================== E4: gunners are not lasers
fire_world,target=g['fire_world'],g['target']
def bullet_ends(dist=40.):
 w,c,f=fire_world();npc=target(w);w.pos[npc]=[dist,0.,0.];w.health[npc]=100000;w.damage.add((1,npc));w.speed=0.;w.step(c,f,n=40)
 return [x[2][3:6] for x in calls(w,0x6bc)],w,npc
def sd(e):
 m=[sum(x[i] for x in e)/len(e) for i in range(3)];return math.sqrt(sum(math.dist(x,m)**2 for x in e)/len(e))
ends,w,npc=bullet_ends()
cx=[sum(e[i] for e in ends)/len(ends) for i in range(3)];spread=[math.dist(e,cx) for e in ends]
rng_=max(math.dist(x[2][0:3],x[2][3:6]) for x in calls(w,0x6bc))                   # the real range, from the door of the helicopter
assert len(ends)>=10 and max(spread)>.15,('the bullets scatter',len(ends),max(spread))
r=.1+.01*rng_;assert max(spread)<=r*math.sqrt(3)+.1,('but stay near the man (+-%.2f m per axis at %d m)'%(r,rng_),max(spread))
assert not invariants(w) and g['hit'](w)=={npc}
passed('Door gunners scatter their bullets (+-%.1f m at %d m) instead of putting every round on one point; the scatter is the brain\'s and every round is still a checked one'%(r,rng_))
near,_,_=bullet_ends(dist=10.);far,_,_=bullet_ends(dist=70.)
assert len(near)>=10 and len(far)>=10 and sd(near)<sd(far),(len(near),len(far),sd(near),sd(far))
passed('The scatter grows with the distance to the target (%.2f m at 10 m, %.2f m at 70 m)'%(sd(near),sd(far)))

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
assert all(abs(w.pos[n_][2])<.01 for n_ in new),('the same height too: CREATE_CHAR adds 1 m to the z it is given, the new guard must not appear in the air and drop',[w.pos[n_][2] for n_ in new])
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

# =================================================================== findings of the independent review
# a crew change waits for a rope motion like the model swap does (the rope workers abort when the state is 17)
def climbing_world():
 w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0.;ground=VM('Helicover_Ground',w);w.step(c,ground,n=3)
 w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=5);rope=[w.shared[b.GROUND_PUB+i] for i in range(4)]
 for ch,(x,y) in zip(rope,[(-1.5,1.2),(1.5,1.2),(-1.5,-1.2),(1.5,-1.2)]):w.pos[ch]=[x,y,.7]
 w.now+=8000;w.player=[0.,-3.,.7];w.step(c,ground,n=8);assert w.control is False;return w,c,ground
w,c,ground=climbing_world();w.shared[b.CREW]=1;w.messages.clear();w.step(c,ground,n=4)
assert w.control is False and w.shared[b.ACREW]!=1 and 'HCSLATE' in w.messages,(w.control,w.shared[b.ACREW],w.messages)
w.step(c,ground,n=400)
assert w.incar.get(1)==c.v[5] and w.control is True and w.shared[b.ACREW]==1,(w.incar,w.control,w.shared[b.ACREW])
passed('A crew change asked for during CJ\'s climb waits for the end of the rope work: CJ is not left on the ground')
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
for k,t_ in enumerate(team):w.pos[t_]=[BG[k][0],BG[k][1],0.]
w.pos[team[3]]=[0.,-18.,0.];w.car=[0.,-40.,28.];w.shared[b.CMD]=17;steps(w,V,6);w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;steps(w,V,40)
assert w.shared[b.ESCORT_ON]==3,w.shared[b.ESCORT_ON]
w.shared[b.CREW]=1;w.messages.clear();steps(w,V,240)
assert 'SQBACK' in w.messages and 'HCCREW' in w.messages and w.messages.index('SQBACK')<w.messages.index('HCCREW'),('the recall finishes first, then the crew changes',w.messages)
assert w.shared[b.ESCORT_ON]==0 and all(t_ not in w.exists for t_ in team) and w.shared[b.ACREW]==1
passed('A crew change in the middle of a squad recall does not cancel it: the squad climbs aboard first, then the crew changes')
# leaving a script-flown helicopter: the cruise keeps its speed and brakes along the way (no dead stop)
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.speed=0.;command(w,c,7,ticks=2);w.step(c,n=30)
assert w.shared[b.STATE]==10 and w.frozen.get(c.v[5]),(w.shared[b.STATE],);v0=w.shared[b.CR_V];assert v0>8.,v0
w.shared[b.EXIT_MODE]=1;w.shared[b.CMD]=15;w.step(c,n=3)
assert w.frozen.get(c.v[5]) and w.shared[b.STATE] in (21,22) and w.shared[b.CR_V]>=.5*v0,('the cruise is not restarted from a standstill',w.shared[b.CR_V],v0,w.shared[b.STATE])
passed('Exit requested during a scripted flight keeps the helicopter on its cruise and its speed: it slows down smoothly, no dead stop')
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.speed=0.;command(w,c,7,ticks=2);w.step(c,n=30);assert w.shared[b.CR_V]>8.
command(w,c,3,ticks=4);assert not w.frozen.get(c.v[5]) and w.shared[b.CR_V]==0,'a later exit never sees a stale cruise speed'
passed('Releasing the helicopter clears the cruise speed')
# re-skinning the squad never touches the invisible platform handle: later clean-up deletes objects only
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
for k,t_ in enumerate(team):w.pos[t_]=[BG[k][0],BG[k][1],0.]
w.shared[b.CREW]=1;steps(w,V,12);w.calls.clear();command(w,c,4,ticks=6);steps(w,V,30)
assert not [x for x in calls(w,0x108) if x[2][0] in w.pos],'DELETE_OBJECT must never get a ped handle'
passed('After a live re-skin the clean-up deletes only real objects (no ped handle in the platform slot)')
# muster: the guards walk to the side they are mounted on
w,c,_=setup();summon(w,c);g['near_cj_landing'](w,c);w.player=w.car.copy();hx,hy=w.car[:2]
for var,sign in ((13,1),(14,-1),(15,1),(16,-1)):w.pos[c.v[var]]=[hx-sign*20.,hy+2.,0.]
w.attach.clear();[w.incar.pop(c.v[v],None) for v in (13,14,15,16)];w.calls.clear();command(w,c,6,ticks=3)
sides={}
for var in (13,14,15,16):
 o=[x[2] for x in calls(w,0x5d3) if x[2][0]==c.v[var]];assert o,('muster order',var);sides[var]=1 if o[-1][1]>hx else -1
assert sides=={13:1,14:-1,15:1,16:-1},sides
passed('Boarding muster: each guard walks to the side of the helicopter he is mounted on (it was mirrored: a 4 m snap through the fuselage)')

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
alive=[g_ for g_ in team if g_ in [w.shared[b.GROUND_PUB+i] for i in range(4)]]
assert w.shared[b.ESCORT_ON]==0 and not alive and 'SQAWAY' in w.messages and not w.handed and not invariants(w),('the lagging team is stood down',w.shared[b.ESCORT_ON],alive,w.messages,w.handed,invariants(w))
# the helicopter, still following him, is told to leave
command(w,c,4,ticks=6);w.now+=40000;steps(w,V,20)
bad=[x for x in w.teleports if x['who']!=c.v[5] or x['dist']>12.]
bad=[x for x in bad if not (x['who']==c.v[5] and x['op']==0xab)]
assert not bad,[(hex(x['op']),x['who'],round(x['dist'],1)) for x in bad][:6]
passed('A whole day - deploy, fire fight, CJ drives off, the squad cannot keep up, dismiss - without a single teleport of a person')

# =================================================================== beta 4: the same order twice, and orders during rope work
def run_until(w,V,cond,limit=600):
 for _ in range(limit):
  w.step(*V)
  if cond():return True
 return False
def states_seen(w,V,cond,limit=600):
 seen=[]
 for _ in range(limit):
  w.step(*V);seen.append(w.shared[b.STATE])
  if cond():break
 return seen
def cover_world(wait=True):
 """CJ asked for the rope from a hover: the cover team is down and the rope hangs 3 m from him (he has not walked to it)."""
 w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0.;ground=VM('Helicover_Ground',w);V=(c,ground);w.step(*V,n=3)
 w.shared[b.ROPE_COMMAND]=1;w.step(*V,n=8);team=[w.shared[b.GROUND_PUB+i] for i in range(4)];assert all(t_ in w.exists for t_ in team) and w.shared[b.ROPE_WAIT]==1 and w.shared[b.ROPE_BUSY]==1
 if wait:w.now+=6000;w.step(*V,n=8);assert w.shared[b.ROPE_BUSY]==0 and w.shared[b.ROPE_WAIT]==1 and w.shared[b.ESCORT_ON]==0
 return w,c,ground,V,team
def squad_cover_world():
 """The squad is on the ground, CJ asked for the rope: the helicopter hovers with the rope out and the squad covers him."""
 w,c,ground,sq,team=escort_world();V=(c,ground,sq)
 for k,t_ in enumerate(team):w.pos[t_]=[BG[k][0],BG[k][1],0.]
 command(w,c,10,ticks=4);assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==0,(w.shared[b.STATE],w.messages)
 w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;w.player=[w.player[0]+6.,w.player[1],w.player[2]]   # CJ steps away from the rope: it waits for him
 assert run_until(w,V,lambda:w.shared[b.ROPE_WAIT]==1 and w.shared[b.ROPE_BUSY]==0,120),(w.shared[b.STATE],w.shared[b.ROPE_WAIT],w.messages)
 w.now+=4000;w.step(*V,n=6);assert w.shared[b.STATE]==3 and w.shared[b.ESCORT_ON]==1 and w.shared[b.ROPE_WAIT]==1,(w.shared[b.STATE],w.shared[b.ESCORT_ON])
 return w,c,ground,V,team
FLIGHT=(0x726,0x4a2,0x825,0x918,0x4d2,0x743,0x4a1)
def flight_orders(w):return [x for x in w.calls if x[1] in FLIGHT]
# --- the mode that is already on
w,c,_=setup();summon(w,c);w.step(c,n=3);w.calls.clear();command(w,c,2,ticks=4);assert w.shared[b.STATE]==2 and not flight_orders(w),flight_orders(w)
command(w,c,3,ticks=4);assert w.shared[b.STATE]==3;w.calls.clear();command(w,c,3,ticks=4);assert not flight_orders(w)
command(w,c,14,ticks=4);assert w.shared[b.STATE]==24;step_=w.shared[b.PATROL_STEP];nxt_=w.shared[b.PATROL_NEXT];w.calls.clear();command(w,c,14,ticks=1)
assert w.shared[b.STATE]==24 and w.shared[b.PATROL_STEP]==step_ and w.shared[b.PATROL_NEXT]==nxt_,'the patrol round is not started again'
passed('FOLLOW / HOLD / PATROL given again while already on: nothing is restarted (no new flight task, the patrol round goes on)')
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.step(c,n=3);command(w,c,7,ticks=4);st=w.shared[b.STATE];assert st in (20,10,11),st
t0=c.v[21];w.now+=3000;command(w,c,7,ticks=3);assert c.v[21]==t0 and w.shared[b.STATE] in (20,10,11),'the flight to Grove Street is not restarted (its clock stays)'
passed('FLY TO GROVE STREET again during the flight: ignored')
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.marker=[300.,200.,0.];w.step(c,n=3);command(w,c,11,ticks=4);assert w.shared[b.STATE] in (21,25),w.shared[b.STATE]
t0=c.v[21];dx=w.shared[b.DEST_X];w.now+=3000;w.calls.clear();command(w,c,11,ticks=3);assert c.v[21]==t0 and w.shared[b.DEST_X]==dx,'same marker: the flight goes on'
w.marker=[-400.,100.,0.];command(w,c,11,ticks=3);assert w.shared[b.DEST_X]!=dx and c.v[21]!=t0,'a marker moved somewhere else is a new destination'
passed('FLY TO MAP MARKER again with the same marker: ignored; with the marker moved: the new destination is taken')
# --- the squad: one deployment, one recall
w,c,_=setup();summon(w,c);ground=VM('Helicover_Ground',w);sq=VM('Helicover_Squad',w);V=(c,ground,sq);w.step(*V,n=3)
command(w,c,16,ticks=4);assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==1
t0=c.v[21];w.messages.clear();w.now+=1500
for cmd in (16,17,16):command(w,c,cmd,ticks=2)
assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==1 and c.v[21]==t0 and not {'SQALR','SQNONE'}&set(w.messages),(w.shared[b.ESCORT_PENDING],w.messages)
command(w,c,10,ticks=2);assert w.shared[b.ESCORT_PENDING]==1 and 'HCRBSY' in w.messages,'the rope for CJ is not taken while the squad is using the ropes'
w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;assert run_until(w,V,lambda:w.shared[b.ESCORT_ON]==2,80)
assert w.shared[b.ROPE_BUSY]==1,'busy from the moment the rope worker takes the order'
assert run_until(w,V,lambda:w.shared[b.GROUND_PUB+3]>0,10);team=[w.shared[b.GROUND_PUB+i] for i in range(4)];made=len(calls(w,0x503));assert all(t_ in w.exists for t_ in team)
w.ped_heights={t_:9. for t_ in team}   # still high on the ropes
w.step(*V,n=3);assert w.shared[b.ESCORT_ON]==2;w.messages.clear();w.shared[b.MSG_UNTIL]=0
for cmd in (16,17,16,17):command(w,c,cmd,ticks=1)
assert len(calls(w,0x503))==made and [w.shared[b.GROUND_PUB+i] for i in range(4)]==team and not {'SQALR','SQNONE'}&set(w.messages)
command(w,c,2,ticks=2);assert w.shared[b.STATE]==3 and 'HCRBSY' in w.messages and w.shared[b.ESCORT_ON]==2,'FOLLOW does not pull the helicopter away from men on the ropes'
w.ped_heights={}
assert run_until(w,V,lambda:w.shared[b.ESCORT_ON]==1,120) and all(t_ in w.exists for t_ in team) and not invariants(w)
passed('DEPLOY SQUAD given again (and RECALL, and the rope) while the helicopter comes in or the men are on the ropes: one team of four, nothing restarted, FOLLOW waits')
w.step(*V,n=6);w.car=[0.,-45.,28.];w.speed=12.;w.step(*V,n=3)   # the helicopter is back to following, away from the squad
command(w,c,17,ticks=4);assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==2
t0=c.v[21];w.now+=1500;w.messages.clear()
for cmd in (17,16,17):command(w,c,cmd,ticks=2)
assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==2 and c.v[21]==t0 and w.shared[b.ESCORT_ON]==1 and not {'SQALR','SQNONE'}&set(w.messages)
w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;assert run_until(w,V,lambda:w.shared[b.ESCORT_ON]==3,80)
for cmd in (16,17,16):command(w,c,cmd,ticks=1)
assert w.shared[b.ESCORT_ON]==3 and len(calls(w,0x503))==made,'no second team is created while the first climbs back'
assert run_until(w,V,lambda:w.shared[b.ESCORT_ON]==0 and w.shared[b.STATE]==2,600),(w.shared[b.ESCORT_ON],w.shared[b.STATE])
assert all(t_ not in w.exists for t_ in team) and not w.handed and not invariants(w),(w.handed,invariants(w))
passed('RECALL SQUAD given again (and DEPLOY) during the recall: one recall, no second team, everybody back aboard, nobody handed to the game')
# --- the rope for CJ: order again = cancel
w,c,_=setup();summon(w,c);w.step(c,n=3);command(w,c,10,ticks=4);assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==0
w.messages.clear();command(w,c,10,ticks=4);assert w.shared[b.STATE]==2 and 'HCRCAN' in w.messages and w.shared[b.ROPE_COMMAND]==0,(w.shared[b.STATE],w.messages)
passed('The rope order again on the way in cancels the pickup: the helicopter goes back to following')
w,c,ground,V,team=cover_world(wait=False)   # the cover team is still on its way down
w.messages.clear();command(w,c,10,ticks=3);assert w.shared[b.ROPE_COMMAND]==1 and w.shared[b.STATE]==3 and 'HCRBSY' not in w.messages,'the cancel is noted, the men are not disturbed on the ropes'
w.calls.clear();w.step(*V,n=12);assert w.shared[b.ROPE_COMMAND]==1 and w.shared[b.ESCORT_ON]==0 and 'HCRCAN' not in w.messages and not [x for x in calls(w,0x5d3) if x[2][0] in team],'still on the ropes 1.2 s later: the cancel waits for the landing'
w.player=[0.,-3.,.7]   # CJ even stands at the rope: the cancel still wins over the automatic pull-up
w.now+=6000;seen=states_seen(w,V,lambda:w.shared[b.STATE]==2)
assert w.shared[b.STATE]==2 and 19 not in seen and 'HCRCAN' in w.messages and w.incar.get(1)!=c.v[5] and w.control,(seen[-5:],w.messages,w.incar)
assert all(t_ not in w.exists for t_ in team) and not w.handed and not invariants(w)
passed('CANCEL ROPE PICKUP while the cover team is still roping down: taken when the men have landed - they climb back, CJ is not pulled up')
w,c,ground,V,team=cover_world(wait=False);command(w,c,10,ticks=3);assert w.shared[b.ROPE_COMMAND]==1
w.health[c.v[5]]=300;w.messages.clear();made=len(calls(w,0x503));w.step(*V,n=20)   # the helicopter is driven off before the men have even landed
assert w.shared[b.STATE]==13 and w.shared[b.ROPE_COMMAND]==0 and len(calls(w,0x503))==made and 'RGHOLD' not in w.messages and not w.handed,(w.shared[b.STATE],w.shared[b.ROPE_COMMAND],w.messages)
passed('A cancel that was still waiting for the landing ends with the pickup when the helicopter is driven off (it is not read as a new rope order)')
w,c,ground,V,team=cover_world();w.messages.clear();command(w,c,10,ticks=3);seen=states_seen(w,V,lambda:w.shared[b.STATE]==2)
assert w.shared[b.STATE]==2 and 19 not in seen and 'HCRCAN' in w.messages and all(t_ not in w.exists for t_ in team) and not w.handed and not w.frozen.get(c.v[5]) and not invariants(w),(seen[-5:],w.messages,w.handed)
passed('CANCEL ROPE PICKUP with the rope hanging: the cover team climbs back up, the helicopter follows again (no new approach, nobody left behind)')
w,c,ground,V,team=squad_cover_world();w.messages.clear();command(w,c,10,ticks=3);assert run_until(w,V,lambda:w.shared[b.STATE]==2,80)
assert w.shared[b.ESCORT_ON]==1 and [w.shared[b.GROUND_PUB+i] for i in range(4)]==team and all(t_ in w.exists for t_ in team) and w.shared[b.ROPE_WAIT]==0 and not w.frozen.get(c.v[5]) and 'HCRCAN' in w.messages,(w.shared[b.ESCORT_ON],w.messages)
assert w.shared[b.GROUND_PUB+4]==-1 and not w.handed and not invariants(w)
passed('CANCEL ROPE PICKUP with the squad on the ground: the squad simply stays with CJ, the rope goes up, the helicopter follows')
# --- other orders while the rope hangs
w,c,ground,V,team=cover_world();made=len(calls(w,0x503));w.messages.clear();command(w,c,16,ticks=3);assert run_until(w,V,lambda:w.shared[b.ESCORT_ON]==1 and w.shared[b.STATE]==2,80),(w.shared[b.ESCORT_ON],w.shared[b.STATE])
assert [w.shared[b.GROUND_PUB+i] for i in range(4)]==team and all(t_ in w.exists for t_ in team) and len(calls(w,0x503))==made and 'SQIN' in w.messages and w.shared[b.ROPE_WAIT]==0 and not invariants(w),(w.messages,invariants(w))
passed('DEPLOY SQUAD while a cover team waits by the rope: the same four men stay down as the squad (no second team)')
w,c,ground,V,team=squad_cover_world();w.messages.clear();command(w,c,17,ticks=3);seen=states_seen(w,V,lambda:w.shared[b.ESCORT_ON]==0 and w.shared[b.STATE]==2)
assert w.shared[b.ESCORT_ON]==0 and w.shared[b.STATE]==2 and 19 not in seen and 'HCRUP' in w.messages and all(t_ not in w.exists for t_ in team) and not w.handed and not invariants(w),(seen[-5:],w.messages,w.handed)
passed('RECALL SQUAD while the squad covers the rope: it goes up the ropes that already hang (no second approach)')
for cmd,final in ((14,24),(4,4)):
 w,c,ground,V,team=cover_world();command(w,c,cmd,ticks=3);assert w.shared[b.STATE]==3 and w.shared[b.AFTER_ROPE]==cmd,(cmd,w.shared[b.STATE])
 seen=states_seen(w,V,lambda:w.shared[b.STATE]==final);assert w.shared[b.STATE]==final and all(t_ not in w.exists for t_ in team) and not w.handed and w.shared[b.AFTER_ROPE]==0 and not invariants(w),(cmd,seen[-5:],w.handed)
passed('PATROL / DISMISS while a cover team waits by the rope: the team climbs back first, then the order is carried out (it used to be left on the ground)')
w,c,ground,V,team=squad_cover_world();command(w,c,14,ticks=3);w.step(*V,n=8);assert w.shared[b.STATE]==24 and w.shared[b.ESCORT_ON]==1 and all(t_ in w.exists for t_ in team) and w.shared[b.ROPE_WAIT]==0 and not invariants(w),(w.shared[b.STATE],w.shared[b.ESCORT_ON])
passed('PATROL while the squad covers the rope: the rope goes up, the squad stays with CJ, the helicopter patrols')
# --- rope work is never interrupted
w,c,ground,V,team=cover_world();w.player=[0.,-3.,.7];assert run_until(w,V,lambda:not w.control,40),'CJ is on the rope'
w.messages.clear()
for cmd in (2,3,4,14,10,16,17):command(w,c,cmd,ticks=1)
assert w.shared[b.STATE]==3 and 'HCRBSY' in w.messages and not w.control
assert run_until(w,V,lambda:w.incar.get(1)==c.v[5],200) and w.control,'he arrives aboard'
w.messages.clear();w.shared[b.MSG_UNTIL]=0
for cmd in (7,11,15):command(w,c,cmd,ticks=1)
assert w.shared[b.STATE]==3 and 'HCRBSY' in w.messages,'aboard, with the team still climbing: destinations and the exit wait too'
assert run_until(w,V,lambda:w.shared[b.ROPE_BUSY]==0 and all(t_ not in w.exists for t_ in team),400) and not w.handed and not invariants(w)
passed('Nothing interrupts rope work: while CJ or the team is on the ropes every order is answered "wait - rope work in progress" and the work is finished')
# --- the exit button
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.shared[b.EXIT_MODE]=1;w.speed=20.;w.step(c,n=3);w.messages.clear();command(w,c,15,ticks=1)
assert w.shared[b.STATE] in (21,22,25) and w.shared[b.AUTO_EXIT]==1 and w.messages.count('HCXHERE')==1,(w.shared[b.STATE],w.shared[b.AUTO_EXIT],w.messages)
dest=(w.shared[b.DEST_X],w.shared[b.DEST_Y]);w.car=[w.car[0]+15.,w.car[1],w.car[2]];w.shared[b.MSG_UNTIL]=0
for _ in range(3):command(w,c,15,ticks=1)
assert (w.shared[b.DEST_X],w.shared[b.DEST_Y])==dest and w.shared[b.AUTO_EXIT]==1 and w.messages.count('HCXHERE')==1,('the stopping point is not pushed further on by every press',dest,w.shared[b.DEST_X],w.messages)
passed('The exit button pressed again while the helicopter slows down for the exit: one exit, the stopping point stays')
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.shared[b.EXIT_MODE]=1;w.speed=0.;w.step(c,n=3);command(w,c,15,ticks=3)
assert w.shared[b.STATE]==23 and w.shared[b.DROP_COMMAND]==1 and w.shared[b.ROPE_PENDING]==1,(w.shared[b.STATE],w.shared[b.DROP_COMMAND])
w.shared[b.ROPE_TRIES]=3;w.shared[b.DROP_COMMAND]=0;w.shared[b.DROP_RESULT]=-1   # the rope worker took the order and is at it
for _ in range(3):command(w,c,15,ticks=2)
assert w.shared[b.ROPE_TRIES]==3 and w.shared[b.DROP_COMMAND]==0,'the drop is not ordered a second time (the retry count used to start again)'
passed('The exit button pressed again while the rope drop is under way: the drop is not ordered twice')
# --- a new destination ends a rope drop that was being retried
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.shared[b.EXIT_MODE]=1;w.speed=0.;w.marker=[300.,200.,0.];w.step(c,n=3);command(w,c,15,ticks=3)
assert w.shared[b.STATE]==23 and w.shared[b.ROPE_PENDING]==1;w.shared[b.DROP_COMMAND]=0
command(w,c,11,ticks=3);assert w.shared[b.STATE] in (21,25) and w.shared[b.ROPE_PENDING]==0,(w.shared[b.STATE],w.shared[b.ROPE_PENDING])
passed('FLY TO MAP MARKER while a rope drop was still being retried: the retries end with the new destination (the exit button is not left blocked)')
# --- guards who were let go: at most eight are kept as ours, the gunners never shoot at them
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
assert not any(x[1]==0x1c2 and x[2][0] in team for x in w.calls)
w.shared[b.ESCORT_CMD]=1;w.step(*V,n=6);assert w.shared[b.ESCORT_CMD]==0 and w.shared[b.ESCORT_ON]==1,'an order that is not for the team on the ground does not stay pending'
command(w,c,17,ticks=4);assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==2,'...so the recall still works'
passed('A stale squad order cannot block the squad row: it is cleared by the team\'s own loop')
w,c,ground,sq,team=escort_world();f=VM('Helicover_Fire',w);V=(c,ground,sq,f)
for k,t_ in enumerate(team):w.pos[t_]=[BG[k][0],BG[k][1],0.]
w.incar[1]=c.v[5];w.step(*V,n=12);assert w.shared[b.LEAVE_N]==1 and all(t_ in w.exists for t_ in team),'CJ flew off: the team is let go in view'
w.incar.pop(1);left=[w.shared[b.LEAVE+i] for i in range(4)];assert sorted(left)==sorted(team),left
w.calls.clear();w.step(*V,n=6)
assert all(w.brain.marks().get(t_,(0,0))[0]==0 for t_ in team) and {o for o,_ in w.brain.ours(w)}>=set(team),'for the brain they are still ours'
# an attacker stands right behind one of them as the gunners see it: the man walking away is in the line
gun=w.coords(w.shared[b.PUB+3]);m=w.coords(team[0]);d=[m[i]-gun[i] for i in range(3)];L=math.sqrt(sum(x*x for x in d))
foe=990;w.exists.add(foe);w.pos[foe]=[m[i]+d[i]/L*3. for i in range(2)]+[0.];w.pedtype[foe]=7;w.weapons[foe]=30;w.health[foe]=100000;w.civilians=[foe];shoots_cj(w,foe)
w.step(*V,n=30)
assert not w.bullet_violations and not invariants(w),('no round passes a man who was let go',w.bullet_violations[:3])
assert not [x for x in w.calls if x[1] in (0x6bc,0x74d,0x634,0x637) and x[2][0] in team]+[x for x in w.calls if x[1] in (0x74d,0x634,0x637) and x[2][1] in team],'and they are nobody\'s target'
w.pos[foe]=[25.,-10.,0.];shoots_cj(w,foe);n0=len(w.bullets);w.step(*V,n=20)
assert len(w.bullets)>n0 and g['hit'](w)=={foe} and not w.bullet_violations,'(control: in the open the same attacker is engaged)'
passed('Guards who were let go stay ours for the brain until they are gone: never a target, and no round is fired past them')

# a ninth man let go while eight are still walking away in view: the one who left first makes room - nobody is handed to the game
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
for k,t_ in enumerate(team):w.pos[t_]=[BG[k][0],BG[k][1],0.]
old=[]
for k in range(8):
 h=2000+k;w.exists.add(h);w.pos[h]=[40.+k,40.,0.];w.creator[h]='Helicover_Ground';w.kind[h]='ped';w.shared[b.LEAVE+k]=h;old.append(h)
w.shared[b.LEAVE_N]=1;w.shared[b.LEAVE_ROT]=0
w.pos[team[0]]=[0.,-150.,0.];steps(w,V,3);w.now+=61000;steps(w,V,4)
assert w.shared[b.LEAVE]==team[0] and old[0] not in w.exists and all(h in w.exists for h in old[1:]) and w.shared[b.LEAVE_ROT]==1 and not w.handed and not invariants(w),(w.shared[b.LEAVE],w.handed,invariants(w))
w.pos[team[1]]=[0.,-150.,0.];steps(w,V,3);w.now+=61000;steps(w,V,4)
assert w.shared[b.LEAVE+1]==team[1] and old[1] not in w.exists and w.shared[b.LEAVE_ROT]==2 and not w.handed and not invariants(w)
passed('More than eight guards walking away at once: the one who left first is removed to make room - even then nobody is handed to the game')

text='\n'.join(results)+'\nMocked script execution only: real flight, pathing and animations are not simulated.\n'
(b.OUT/'realism_tests.txt').write_text(text);print(text)
