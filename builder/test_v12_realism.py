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

def escort_world(tactics=0,fire=3):
 """Support following CJ, then TEAM ON FOOT: rope hover, four guards down, back to FOLLOW."""
 w,c,_=setup();summon(w,c);ground=VM('Helicover_Ground',w);sq=VM('Helicover_Squad',w)
 w.health[1]=100;w.shared[b.TACTICS]=tactics;w.shared[b.FIRE]=fire;w.step(c,ground,sq,n=3)
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
s1=math.dist(moves[1][1:4],moves[0][1:4]);s2=math.dist(moves[2][1:4],moves[1][1:4])
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

text='\n'.join(results)+'\nMocked script execution only: real flight, pathing and animations are not simulated.\n'
(b.OUT/'realism_tests.txt').write_text(text);print(text)
