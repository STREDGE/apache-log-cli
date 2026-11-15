"""v40 tactical squad, TEAM ON FOOT escort and overwatch flight, on the mocked VM of test_v25.py.
Mocked script execution only: real GTA pathing, cover use and gunfire are not simulated."""
import math,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;P=HERE/'test_v25.py'
_src=P.read_text();g={'__file__':str(P),'__name__':'v25_harness'}
exec(compile(_src[:_src.index('results=[]')],str(P),'exec'),g)
for _m in re.finditer(r'^def [a-z_0-9]+\(.*?(?=^\S)',_src,re.S|re.M):exec(compile(_m.group(0),str(P),'exec'),g)
World,VM,b,setup,summon,calls=g['World'],g['VM'],g['b'],g['setup'],g['summon'],g['calls']
import build_v25_squad as sqb
results=[]
def passed(t):results.append('PASS: '+t)
def orders(w,op,who):return [x[2] for x in w.calls if x[1]==op and x[2][0]==who]
def last(w,op,who):
 o=orders(w,op,who);assert o,(hex(op),who);return o[-1]

def escort_world(tactics=0,fire=3):
 """Support following CJ, then TEAM ON FOOT: rope hover, four guards down, back to FOLLOW."""
 w,c,_=setup();summon(w,c);ground=VM('Helicover_Ground',w);sq=VM('Helicover_Squad',w)
 w.health[1]=100;w.shared[b.TACTICS]=tactics;w.shared[b.FIRE]=fire;w.step(c,ground,sq,n=3)
 w.shared[b.CMD]=16;w.step(c,ground,sq,n=6)
 assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==1,(w.shared[b.STATE],w.messages)
 w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;w.step(c,ground,sq,n=40)   # 1.2: eased glide (~2.3 s from 18 m)
 team=[w.shared[b.GROUND_PUB+i] for i in range(4)]
 return w,c,ground,sq,team
def steps(w,vms,n):w.step(*vms,n=n)

# ------------------------------------------------------------------ deployment
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
assert len(set(team))==4 and all(t in w.exists for t in team),(team,w.messages)
assert w.shared[b.ESCORT_ON]==1 and w.shared[b.SQ_ROPE]==1 and 'SQIN' in w.messages
assert w.shared[b.GROUND_PUB+4]==-1 and len(calls(w,0x503))==4
assert w.shared[b.STATE]==2 and not w.frozen.get(c.v[5]) and w.shared[b.FROZEN]==0
assert all(last(w,0x1b2,t)[1]==w.shared[b.WPN] for t in team)
passed('TEAM ON FOOT: four armed guards rope down next to CJ, then the helicopter resumes FOLLOW')
# ------------------------------------------------------------------ formation
for t in team:w.pos[t]=[0.,-20.,0.]
steps(w,V,3)
BG=sqb.BG_FORM
for k,t in enumerate(team):
 o=last(w,0x5d3,t);assert abs(o[1]-BG[k][0])<.01 and abs(o[2]-BG[k][1])<.01,(k,o)
 assert o[4]==7,(k,o)
for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1]-5.,0.]
w.calls.clear();w.now+=1000;steps(w,V,2)
assert all(last(w,0x5d3,t)[4]==6 for t in team)
for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1]-2.,0.]
w.calls.clear();w.now+=1000;steps(w,V,2)
assert all(last(w,0x5d3,t)[4]==4 for t in team)
passed('Bodyguard diamond: each guard takes his own slot, sprinting from afar, running, walking when close')
w.calls.clear();steps(w,V,20)
assert all(len(orders(w,0x5d3,t))<=4 for t in team),[len(orders(w,0x5d3,t)) for t in team]
passed('Move orders are refreshed every 0.7 s at most, not every tick')
for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1],0.]
w.calls.clear();w.now+=1500;steps(w,V,3)   # 1.2: the mock walks the guards to their slots, so the order timer must expire first
for k,t in enumerate(team):
 o=last(w,0x667,t);assert (round(o[1],2),round(o[2],2))==sqb.BG_AIM[k] and abs(o[3]-.8)<.01,(k,o)
assert not any(orders(w,0x5d3,t) for t in team)
passed('Standing with CJ: weapons up, each guard covering his own sector')
w.char_speed={1:1.4};w.calls.clear();steps(w,V,3)
o=last(w,0x5d3,team[0]);assert o[4]==4 and abs(o[2]-(BG[0][1]+1.26))<.01,o
w.char_speed={1:5.};w.calls.clear();w.now+=1000;steps(w,V,3)
o=last(w,0x5d3,team[0]);assert o[4]==6 and abs(o[2]-(BG[0][1]+4.5))<.01,o
w.char_speed={1:9.};w.calls.clear();w.now+=1000;steps(w,V,3)
o=last(w,0x5d3,team[0]);assert abs(o[2]-(BG[0][1]+6.))<.01 and o[4]==7,o
w.char_speed={}
passed('Moving with CJ: the formation leads him (capped at 6 m) and matches walking or running')
# ------------------------------------------------------------------ contact (bodyguard)
for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1],0.]
hostile=950;w.exists.add(hostile);w.pos[hostile]=[20.,0.,0.];w.pedtype[hostile]=7;w.weapons[hostile]=30;w.civilians=[hostile];w.damage.add((1,hostile))
w.calls.clear();w.messages.clear();steps(w,V,6)
assert w.shared[b.SQ_T]==hostile and w.shared[b.SQ_THREATS]==1 and 'SQCR' in w.messages,(w.shared[b.SQ_T],w.messages)
o=last(w,0x637,team[1]);assert abs(o[1]-2.)<.01 and abs(o[2]+1.3)<.01 and o[4]==6 and o[7]==hostile,o
assert last(w,0x74d,team[2])[1]==hostile  # already within 1.4 m of his shield point (2, 1.3)
assert last(w,0x634,team[0])[1]==hostile and last(w,0x634,team[3])[1]==hostile
passed('Contact right: shields step between CJ and the threat firing on the move, the other two fight crouched')
w.pos[team[1]]=[2.,-1.3,0.];w.pos[team[2]]=[2.,1.3,0.];steps(w,V,3)
assert last(w,0x74d,team[1])[1]==hostile and last(w,0x74d,team[2])[1]==hostile
w.calls.clear();steps(w,V,8)
assert len(orders(w,0x634,team[0]))<=1 and len(orders(w,0x74d,team[1]))<=1
passed('Shields fire from their spot; combat orders are not restarted every tick')
w.pos[hostile]=[0.,-20.,0.];w.civilians=[hostile];w.pos[team[0]]=[0.,30.,0.];w.calls.clear();steps(w,V,3)
o=last(w,0x5d3,team[0]);assert abs(o[1]-BG[0][0])<.01 and abs(o[2]-BG[0][1])<.01,o
passed('Bodyguard leash: an engager more than 14 m from CJ returns to his slot instead of chasing')
w.pos[team[0]]=[0.,3.2,0.];w.health[1]=30;w.messages.clear();w.calls.clear();steps(w,V,6)
ring=[(0.,-1.5),(-1.2,-.6),(1.2,-.6),(0.,1.2)]  # u = (0,-1): threat behind CJ
for k,t in enumerate(team):
 o=orders(w,0x637,t)
 if o:assert abs(o[-1][1]-ring[k][0])<.01 and abs(o[-1][2]-ring[k][1])<.01,(k,o[-1])
assert w.messages.count('SQCOV')==1
steps(w,V,40);assert w.messages.count('SQCOV')==1
passed('CJ badly hurt: the whole team closes a ring around him; one COVER CJ call')
w.health[1]=100;w.dead.add(hostile);w.messages.clear();steps(w,V,6)
assert w.shared[b.SQ_THREATS]==0 and 'SQCLR' not in w.messages
w.now+=4000;steps(w,V,6);assert 'SQCLR' in w.messages
passed('AREA SECURE is called 3.5 s after the last threat is gone')
# ------------------------------------------------------------------ medic
w.health[1]=50;w.pos[team[3]]=[0.,-12.,0.];w.messages.clear();w.calls.clear();steps(w,V,3)
o=last(w,0x5d3,team[3]);assert abs(o[1])<.01 and abs(o[2])<.01 and o[4]==6,o
w.pos[team[3]]=[0.,-1.,0.];w.shared[b.MSG_UNTIL]=0;steps(w,V,3)
assert w.health[1]==85 and 'SQMED' in w.messages and last(w,0x4eb,team[3])[1]==1
w.health[1]=50;steps(w,V,30);assert w.health[1]==50
passed('Medic: the rear guard runs to a wounded CJ, kneels and patches him (+35 HP), then cools down')
w.now+=45000;w.health[1]=100;w.health[team[0]]=40;w.pos[team[3]]=[0.,2.5,0.];w.messages.clear();steps(w,V,4)
assert w.health[team[0]]==100 and 'SQMEDG' in w.messages
passed('Medic also treats a wounded teammate (+60 HP, max 150)')
# ------------------------------------------------------------------ vehicles
w.now+=4000  # radio calls are spaced 3.5 s apart
car=777;w.exists.add(car);w.cars[car]={'pos':[0.,0.,0.],'heading':0.};w.model[car]=400;w.incar[1]=car
for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1],0.]
w.calls.clear();w.messages.clear();steps(w,V,3)
seats={t:last(w,0x5ca,t)[3] for t in team[:3]}
assert seats=={team[0]:0,team[1]:1,team[2]:2} and all(w.incar.get(t)==car for t in team[:3]),seats
assert 'SQCAR' in w.messages
passed('Mount up: the guards take CJ\'s passenger seats')
w.incar.pop(1);w.player=[0.,0.,0.];w.calls.clear();steps(w,V,3)
assert all(orders(w,0x633,t) for t in team[:3]) and not any(t in w.incar for t in team)
passed('CJ gets out: the guards get out of the car too')
car2=778;w.exists.add(car2);w.cars[car2]={'pos':[0.,0.,0.],'heading':0.};w.model[car2]=400;w.incar[1]=car2;w.car_speeds={car2:15.}
for t in team:w.pos[t]=[0.,-30.,0.]
w.calls.clear();steps(w,V,3);assert not any(orders(w,0x5ca,t) for t in team)
w.incar.pop(1);w.car_speeds={}
passed('A car driving away is not chased; the guards hold and regroup when CJ stops')
# ------------------------------------------------------------------ catch-up / stuck / casualty
w.pos[team[0]]=[0.,-120.,0.];w.offscreen={team[0]};w.calls.clear();w.teleports.clear();steps(w,V,2)
o=last(w,0x5f5,team[0]);assert o[4]==7 and not orders(w,0xa1,team[0]),o
w.pos[team[1]]=[0.,-120.,0.];w.offscreen=set();w.calls.clear();steps(w,V,2)
assert orders(w,0x5f5,team[1]) and not orders(w,0xa1,team[1])
passed('Far behind (out of sight or not): the guards sprint along the path network, nobody is teleported')
w.pos[team[2]]=[12.,0.,0.];w.blocked={team[2]};w.calls.clear();steps(w,V,6);w.now+=3000;steps(w,V,2);w.offscreen={team[2]};w.now+=3000;steps(w,V,3)
assert orders(w,0x5f5,team[2]) and not orders(w,0xa1,team[2]) and not w.teleports,'stuck guard re-paths, never teleports'
w.offscreen=set();w.blocked=set()
passed('A stuck guard (moving, far, not progressing) is sent along the path network again, never teleported')
w.dead.add(team[1]);w.messages.clear();steps(w,V,4);assert w.messages.count('SQDOWN')==1
steps(w,V,10);assert w.messages.count('SQDOWN')==1
passed('MAN DOWN is called once when a guard dies')
# ------------------------------------------------------------------ recall
for k,t_ in enumerate(team):w.pos[t_]=[BG[k][0],BG[k][1],0.]
w.walk.clear();w.dead.discard(team[1]);w.car=[0.,-40.,28.];w.shared[b.CMD]=17;steps(w,V,6)
assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==2,(w.shared[b.STATE],w.messages)
w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;steps(w,V,14)
assert w.shared[b.ESCORT_ON]==3 and w.shared[b.SQ_ROPE]==0,(w.shared[b.ESCORT_ON],w.messages)
steps(w,V,80)
assert all(t not in w.exists for t in team) and w.shared[b.ESCORT_ON]==0 and 'SQBACK' in w.messages,(w.messages,[t in w.exists for t in team])
steps(w,V,6);assert w.shared[b.STATE]==2 and not w.frozen.get(c.v[5])
passed('RECALL TEAM: hover, the team ropes back up, then FOLLOW resumes')
# ------------------------------------------------------------------ withdrawal, loss, pickup with cover
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
w.incar[1]=c.v[5];w.offscreen=set(team);steps(w,V,12)
assert all(t not in w.exists for t in team) and w.shared[b.ESCORT_ON]==0 and 'SQSTAY' in w.messages and 'SQBACK' not in w.messages
passed('CJ boards the helicopter another way: the team stays on the ground (deleted out of sight, nobody warped aboard)')
w,c,ground,sq,team=escort_world();V=(c,ground,sq);w.teleports.clear()
w.incar[1]=c.v[5];w.offscreen=set();w.onscreen=True;steps(w,V,12)
assert all(t in w.exists and t in w.released for t in team) and w.shared[b.ESCORT_ON]==0 and not w.teleports,(w.messages,w.teleports)
passed('The same in view: the team is handed back to the game, nobody vanishes on screen')
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
for t in team:w.dead.add(t)
steps(w,V,12);assert 'SQLOST' in w.messages and w.shared[b.ESCORT_ON]==0 and 'SQBACK' not in w.messages
passed('Losing the whole team is reported and cleaned up')
w,c,ground,sq,team=escort_world();V=(c,ground,sq);spawned=len(calls(w,0x503))
w.car=[0.,-40.,28.];w.shared[b.CMD]=10;steps(w,V,6);assert w.shared[b.STATE]==19
w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;steps(w,V,40)
assert 'SQCOVER' in w.messages and len(calls(w,0x503))<=spawned+1 and all(t in w.exists for t in team) and w.shared[b.SQ_ROPE]==1,(w.messages,len(calls(w,0x503)))
passed('Rope pickup with the team on the ground: the same team covers CJ (only the CJ rope is added)')
# ------------------------------------------------------------------ assault tactics
w,c,ground,sq,team=escort_world(tactics=1);V=(c,ground,sq)
for k,t in enumerate(team):w.pos[t]=list(sqb.AS_FORM[k])+[0.]
hostile=950;w.exists.add(hostile);w.pos[hostile]=[20.,0.,0.];w.pedtype[hostile]=7;w.weapons[hostile]=30;w.civilians=[hostile];w.damage.add((1,hostile))
w.now=(w.now//3000+1)*3000+100;w.calls.clear();w.messages.clear();steps(w,V,6)
mover,cover=(team[0],team[1]) if (w.now//3000)%2==0 else (team[1],team[0])
o=last(w,0x637,mover);g0=w.pos[mover];step=min(math.dist(g0[:2],[20.,0.])-8.,6.)
assert o[7]==hostile and abs(math.dist(o[1:3],g0[:2])-step)<.05 and math.dist(o[1:3],[20.,0.])<math.dist(g0[:2],[20.,0.]),o
assert last(w,0x634,cover)[1]==hostile and not orders(w,0x637,cover)
assert 'SQAR' in w.messages,w.messages
o=last(w,0x637,team[2]);assert abs(o[1]-20.)<.01 and abs(o[2]+9.)<.01 and o[4]==6 and o[7]==hostile,o
assert not orders(w,0x637,team[3]),'the medic never leaves CJ to flank'
passed('Assault contact: one man bounds forward firing while his partner covers crouched; the flanker moves out firing; the medic stays with CJ')
w.now+=3000;w.calls.clear();steps(w,V,4)
assert orders(w,0x637,cover) and last(w,0x634,mover)[1]==hostile
passed('Bounding overwatch: every 3 s the pair swaps who moves and who covers')
w.pos[team[2]]=[19.,-8.,0.];w.calls.clear();steps(w,V,3);assert last(w,0x7a5,team[2])[1]==hostile
passed('A flanker who reached his flank point attacks from there')
w.pos[team[0]]=[0.,60.,0.];w.calls.clear();steps(w,V,3)
o=last(w,0x5f5,team[0]);assert o[4]==7 and abs(o[2]-sqb.AS_FORM[0][1])<.01 and not orders(w,0xa1,team[0]),o   # 1.2: beyond 40 m he runs back on the path network
passed('Assault leash: nobody pushes more than 40 m away from CJ; beyond it he sprints back (no teleport)')
w.dead.add(hostile);w.now+=5000
for k,t in enumerate(team):w.pos[t]=list(sqb.AS_FORM[k])+[0.]
w.calls.clear();steps(w,V,8)
for k,t in enumerate(team):
 o=last(w,0x667,t);assert (round(o[1],2),round(o[2],2))==sqb.AS_AIM[k] and o[4]==1200,(k,o)
w.now+=1100;steps(w,V,3);assert all(last(w,0x4eb,t)[1]==1 for t in team)
passed('Assault holding: each man faces his sector, then takes a knee')
# ------------------------------------------------------------------ rules of engagement
def roe(fire,typ=7,weapon=30,shooting=False,attacker=False,wanted=0,targeting=False,pos=(15.,0.,0.)):
 w,c,ground,sq,team=escort_world(fire=fire);V=(c,ground,sq);w.wanted=wanted
 npc=960;w.exists.add(npc);w.pos[npc]=list(pos);w.pedtype[npc]=typ;w.weapons[npc]=weapon;w.civilians=[npc]
 if shooting:w.shooting_chars.add(npc)
 if attacker:w.damage.add((1,npc))
 if targeting:w.targeting=npc
 steps(w,V,6);return w.shared[b.SQ_T]==npc
assert not roe(0,shooting=True) and roe(0,attacker=True)
passed('CEASE FIRE: the team only answers someone who hurt CJ or a teammate')
assert roe(3,shooting=True) and not roe(3,weapon=0,shooting=True) and roe(3,pos=(10.,0.,0.)) and not roe(3,typ=14,pos=(10.,0.,0.))
passed('PROTECT CJ: armed shooters, or armed Ballas/Vagos/Rifa close to CJ')
assert not roe(3,typ=8,shooting=True) and not roe(1,typ=8,shooting=True)
passed('Grove Street members are never engaged unless they attack')
assert not roe(3,typ=6,shooting=True,wanted=0) and roe(3,typ=6,wanted=2)
passed('Police are engaged only while CJ is wanted')
assert roe(2,targeting=True,weapon=0,typ=4) and not roe(2,shooting=True)
passed('FOLLOW CJ SHOTS: the team engages what CJ aims at')
assert roe(1,typ=4,weapon=22) and not roe(1,typ=4,weapon=0)
passed('WEAPONS FREE: any armed person, never unarmed civilians')
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
for who in [team[1],c.v[13],c.v[4]]:
 w.civilians=[who];w.damage.add((1,who));steps(w,V,6);assert w.shared[b.SQ_T]!=who
passed('Teammates, the crew and the pilot are never threats')
# ------------------------------------------------------------------ hand-over between workers
w,c,_=setup();summon(w,c);w.wanted=0;f=VM('Helicover_Fire',w);sq=VM('Helicover_Squad',w);w.step(c,f,sq,n=3);w.shared[b.FIRE]=3
guard=c.v[13];w.attach.pop(guard,None);w.incar.pop(guard,None);w.pos[guard]=[3.,0.,0.]
npc=g['target'](w,typ=7,skin=20);w.damage.add((1,npc));w.step(c,f,sq,n=12)
assert w.shared[b.FIRE_TARGET]==npc and not orders(w,0x74d,guard)
passed('Fire worker leaves on-foot guards to the squad while its heartbeat is fresh')
w,c,_=setup();summon(w,c);w.wanted=0;f=VM('Helicover_Fire',w);w.step(c,f,n=3);w.shared[b.FIRE]=3
guard=c.v[13];w.attach.pop(guard,None);w.incar.pop(guard,None);w.pos[guard]=[3.,0.,0.]
npc=g['target'](w,typ=7,skin=20);w.damage.add((1,npc));w.step(c,f,n=12);assert orders(w,0x74d,guard)
passed('Without the squad worker the fire worker still commands on-foot guards (old behaviour)')
w,c,_=setup();summon(w,c);command=g['command'];command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0
ground=VM('Helicover_Ground',w);sq=VM('Helicover_Squad',w);w.health[1]=100;w.step(c,ground,sq,n=3);w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,sq,n=6)
rope=[w.shared[b.GROUND_PUB+i] for i in range(4)];w.now+=8000;w.calls.clear();w.step(c,ground,sq,n=6)
assert w.shared[b.SQ_ROPE]==1 and all(len(orders(w,0x5d3,t))>0 for t in rope)
assert all(o[4] in (4,6,7) for t in rope for o in orders(w,0x5d3,t)) and w.shared[b.SQ_GROUP]==2
passed('Rope evacuation guards are led by the squad while CJ walks to the rope')
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1],0.]
hostile=950;w.exists.add(hostile);w.pos[hostile]=[20.,0.,0.];w.pedtype[hostile]=7;w.weapons[hostile]=30;w.civilians=[hostile];w.damage.add((1,hostile))
steps(w,V,6);assert orders(w,0x634,team[0])
w.dead.add(hostile);w.pos[team[0]]=[0.,-10.,0.];w.calls.clear();steps(w,V,4)
seq=[x[1] for x in w.calls if x[2] and x[2][0]==team[0] and x[1] in (0x4eb,0x5d3)]
assert seq[:2]==[0x4eb,0x5d3] and last(w,0x4eb,team[0])[1]==0,seq
passed('After a crouched fight the guard stands up before moving on')
w.interior=3;w.pos[team[1]]=[0.,-30.,0.];w.calls.clear();steps(w,V,6);assert not any(orders(w,op,t) for t in team for op in (0x5d3,0xa1,0x5f5,0x667))
w.interior=0
passed('CJ inside an interior: the team waits outside instead of teleporting after him')
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
hostile=951;w.exists.add(hostile);w.pos[hostile]=[25.,25.,0.];w.pedtype[hostile]=7;w.weapons[hostile]=30;w.damage.add((1,hostile));w.civilians=[]
w.shared[b.FIRE_TARGET]=hostile;steps(w,V,6);assert w.shared[b.SQ_T]==hostile
passed('The squad also engages whatever the door gunners are firing at')
# fence: knee-high blocked, head-high clear, flat ground behind it -> climb over
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1],1.]
w.pos[team[0]]=[0.,-12.,1.];steps(w,V,3);assert last(w,0x5d3,team[0])
w.los_fn=lambda a,z:not(a[2]<.6 and z[2]<.6)
w.calls.clear();steps(w,V,3)
assert orders(w,0x78f,team[0]) and abs(w.actor_heading[team[0]]-0.)<.5,(orders(w,0x78f,team[0]),w.actor_heading[team[0]])
passed('A fence in the way: the guard turns to it and climbs over')
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
w.pos[team[0]]=[0.,-12.,1.];steps(w,V,3);w.los_fn=lambda a,z:not(a[2]<.6 and z[2]<.6);w.ground_fn=lambda x,y,z:1. if y>-10.5 else 0.
w.calls.clear();steps(w,V,3);assert not orders(w,0x78f,team[0])
passed('Stairs or a slope are walked, not vaulted')
# ------------------------------------------------------------------ menu
w,c,p=setup(True);launch=VM('Helicover',w);summon(w,c);w.step(c,p,launch,n=15)
assert w.menu[5]==b'DEPLOY TEAM ON FOOT',w.menu
w.events.append(4);w.step(c,p,n=4);assert w.menu[5]==b'TEAM TACTICS: BODYGUARD',w.menu
w.events.append(3);w.step(c,p,n=4);assert w.shared[b.TACTICS]==1 and w.menu[5]==b'TEAM TACTICS: ASSAULT',w.menu
w.events.append(6);w.step(c,p,n=4);w.shared[b.ESCORT_ON]=1;w.step(c,p,n=4);assert w.menu[5]==b'RECALL TEAM',w.menu
w.events.append(3);w.step(c,p,n=2);assert w.shared[b.CMD] in (17,0) and any(x[2]==[b.CMD,17] for x in calls(w,0xddc))
passed('Main menu: one row deploys / recalls the team; SETTINGS switches BODYGUARD / ASSAULT')
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.shared[b.CMD]=16;w.step(c,n=5);assert 'HCEXIT' in w.messages and w.shared[b.STATE]!=19
w,c,_=setup();summon(w,c);w.shared[b.ESCORT_ON]=1;w.shared[b.CMD]=16;w.step(c,n=5);assert 'SQALR' in w.messages
w,c,_=setup();summon(w,c);w.shared[b.CMD]=17;w.step(c,n=5);assert 'SQNONE' in w.messages
car=777;w.exists.add(car);w.cars[car]={'pos':[0.,0.,0.],'heading':0.};w.model[car]=400;w.incar[1]=car;w.shared[b.CMD]=16;w.step(c,n=5);assert 'SQFOOT' in w.messages
passed('TEAM ON FOOT refuses politely: CJ aboard, team already down, nothing to recall, CJ in a car')
# ------------------------------------------------------------------ overwatch flight
w,c,_=setup();summon(w,c);w.car=[0.,-40.,28.];w.speed=15.;w.step(c,n=3)   # an orbiting helicopter is moving (not 'wedged')
pts=[]
for _ in range(90):
 n=len(calls(w,0x4a2));w.step(c)
 for x in calls(w,0x4a2)[n:]:pts.append(x[2])
assert pts and all(abs(math.dist(m[1:3],[0.,0.])-30.)<.05 and abs(m[3]-24.)<.01 for m in pts),pts[:3]
assert len({(round(m[1]),round(m[2])) for m in pts})>=3
passed('Overwatch: the helicopter circles CJ at 30 m, 24 m above him, instead of hovering on top')
w,c,_=setup();summon(w,c);w.car=[0.,-40.,28.];w.speed=15.;w.los_fn=lambda a,z:a[0]<=.01;n0=len(calls(w,0x4a2));w.step(c,n=40)
pts=[x[2] for x in calls(w,0x4a2)[n0:]];assert pts and all(m[1]<=.01 for m in pts),pts[:4]
passed('Overwatch skips stations from which a building hides CJ')
w,c,_=setup();summon(w,c);w.car=[0.,-40.,28.];w.step(c,n=25);w.health[c.v[5]]=850;w.messages.clear();w.step(c,n=25)
m=calls(w,0x4a2)[-1][2];assert 'HCEVADE' in w.messages and abs(math.dist(m[1:3],[0.,0.])-50.)<.05 and abs(m[3]-45.)<.01,(m,w.messages)
passed('Taking heavy fire: evasive manoeuvre widens the circle to 50 m and climbs to 45 m')
w,c,_=setup();summon(w,c);w.car=[0.,-40.,28.];car=777;w.exists.add(car);w.cars[car]={'pos':[0.,0.,0.],'heading':0.};w.model[car]=400;w.current_car=None
w.incar[1]=car;w.car_speeds={car:20.};w.step(c,n=40)
assert calls(w,0x726)[-1][2][1:]==[1,-1,20.]
passed('CJ driving fast: the helicopter switches to the native chase')
fw=g['fire_world'];w,c,f=fw();npc=g['target'](w,typ=7,skin=20);w.damage.add((1,npc));w.los_fn=lambda a,z:False;w.step(c,f,n=12)
m=[x[2] for x in calls(w,0x4a2) if abs(x[2][5]-70.)<.01][-1];assert abs(m[3]-(w.pos[npc][2]+40.))<.01,m
passed('Combat orbit: a point without a view of the threat is flown 15 m higher and the next one is tried')
pts=[];n=len(calls(w,0x4a2))
for _ in range(30):w.step(c,f)
pts={(round(x[2][1]),round(x[2][2])) for x in calls(w,0x4a2)[n:] if abs(x[2][5]-70.)<.01}
assert len(pts)<=4,pts
passed('Combat orbit with no clear view moves on at most every 1.2 s instead of thrashing every tick')

# ------------------------------------------------------------------ door gunners (v40.2)
fw=g['fire_world']
def gunner_world(npcs):
 w,c,f=fw();w.civilians=[]
 for npc,x,y in npcs:
  w.exists.add(npc);w.pos[npc]=[x,y,0.];w.skin[npc]=20;w.pedtype[npc]=7;w.civilians.append(npc)
 return w,c,f
w,c,f=gunner_world([(910,24.,0.),(911,-24.,0.)]);w.step(c,f,n=16)
gt=[w.shared[b.GUARD_TARGET+i] for i in range(4)]
assert gt[0]==910 and gt[1]==911,gt
passed('Door gunners take a target on their own side: right door right, left door left')
w,c,f=gunner_world([(911,-2.,0.),(910,12.,0.),(912,24.,0.)])  # 911 left = primary; 910 right, scanned first, but blocked
g3=None
def los(a,z):
 return not(g3 and abs(a[0]-g3[0])<.01 and abs(a[1]-g3[1])<.01 and abs(z[0]-12.)<.1 and abs(z[1])<.1)
w.los_fn=los;g3=w.coords(c.v[13]);w.step(c,f,n=16)
assert w.shared[b.GUARD_TARGET]==912,[w.shared[b.GUARD_TARGET+i] for i in range(4)]
passed('A gunner without a clear line from his seat leaves that target to someone else')
w,c,f=gunner_world([(911,-24.,0.)]);w.exists.add(920);w.pos[920]=[30.,-45.,0.];w.pedtype[920]=7;w.skin[920]=20;w.damage.add((1,920))
w.shared[b.SQ_T]=920;w.step(c,f,n=16)
assert w.shared[b.GUARD_TARGET]==920,[w.shared[b.GUARD_TARGET+i] for i in range(4)]
passed('Gunners also use the threats the ground squad has found')
w,c,f=gunner_world([(900,0.,0.),(901,-12.,0.),(902,12.,0.),(903,0.,12.)]);w.step(c,f,n=16)
gt=[w.shared[b.GUARD_TARGET+i] for i in range(4)];assert len(set(gt))==4,gt
passed('With four threats around, the four gunners never double up')

# ------------------------------------------------------------------ v41 threat board: door gunners
def gs(w):return [(w.shared[b.GS_H+i],w.shared[b.GS_S+i]) for i in range(8) if w.shared[b.GS_H+i]!=-1]
def gtargets(w):return [w.shared[b.GUARD_TARGET+i] for i in range(4)]
w,c,f=gunner_world([(930,-12.,0.),(931,12.,0.),(932,0.,12.),(933,0.,-12.)]);w.weapons.update({930:30,931:30,932:30,933:30});w.messages.clear()
for _ in range(34):w.ped_bullet([12.,0.,1.],[1.5,1.,.5]);w.step(c,f)
assert w.shared[b.TB_SHOOTER]==931 and gs(w)[0][0]==931 and gs(w)[0][1]>=120,(w.shared[b.TB_SHOOTER],gs(w))
assert gtargets(w).count(931)==2 and len(set(gtargets(w)))==3 and 'HCFOCUS' in w.messages,(gtargets(w),w.messages)
passed('A shot at CJ names its shooter from the bullet trace (the engine stores a random 2-5 m piece of the path, not its ends): top of the board, two gunners on him, call-out')
for dist in (6.,20.,60.,85.):
 hits=0
 for seed in range(6):
  w,c,f=gunner_world([(931,dist,0.)]);w.weapons[931]=30;w.rng.seed(seed)
  for _ in range(40):w.ped_bullet([dist,0.,1.],[0.4,0.3,.5]);w.step(c,f)
  hits+=w.shared[b.TB_SHOOTER]==931
 assert hits>=5,(dist,hits)
passed('The shooter is found at 6, 20, 60 and 85 m, whatever random piece of the path the engine recorded')
w,c,f=gunner_world([(933,-12.,0.)]);w.weapons[933]=30
for _ in range(16):w.ped_bullet([-12.,0.,1.],[30.,30.,0.]);w.step(c,f)
assert w.shared[b.TB_SHOOTER]!=933,'a round that missed CJ by far names nobody'
passed('Rounds that do not come down at CJ do not make anyone the shooter')
w,c,f=gunner_world([(934,25.,0.)]);w.weapons[934]=0
for _ in range(30):w.ped_bullet([25.,0.,1.],[0.4,0.3,.5]);w.step(c,f)
assert w.shared[b.TB_SHOOTER]!=934,'an unarmed bystander on the line is not the shooter'
passed('An unarmed bystander standing on the back-ray is not mistaken for the shooter')
w,c,f=gunner_world([(931,12.,0.)]);w.weapons[931]=30;w.shared[b.GAME_OK]=0;w.calls.clear()
for _ in range(20):w.shared[b.GAME_OK]=0;w.ped_bullet([12.,0.,1.],[1.5,1.,.5]);w.step(c,f)
assert w.shared[b.TB_SHOOTER]!=931 and not [x for x in calls(w,0xdd8) if x[2][1]>=b.BULLET_TRACES_OFS],'unknown game build: bullet traces are not read'
passed('On another game build the bullet traces are not read at all')
w,c,f=gunner_world([(934,-20.,0.),(935,20.,0.),(936,0.,-20.)]);w.weapons.update({934:22,935:30,936:34})
for n in (934,935,936):w.damage.add((1,n))
w.step(c,f,n=16);order=[h for h,_ in gs(w)]
assert order==[936,935,934],gs(w)
w,c,f=gunner_world([(938,-20.,0.),(939,20.,0.)]);w.weapons.update({938:30,939:30});w.pos[939][2]=10.
for n in (938,939):w.damage.add((1,n))
w.step(c,f,n=16);assert [h for h,_ in gs(w)]==[939,938],gs(w)
passed('Threats are ranked by weapon (sniper, then rifle, then pistol) and position (a rifleman on a roof above one on the street)')
w,c,f=gunner_world([]);w.shared[b.FIRE]=1
for n,typ in [(937,6),(938,7)]:w.exists.add(n);w.pos[n]=[20.,0.,0.] if n==937 else [0.,24.,0.];w.pedtype[n]=typ;w.skin[n]=280 if typ==6 else 20;w.civilians.append(n)
w.step(c,f,n=16);order=[h for h,_ in gs(w)]
assert order[0]==938 and dict(gs(w))[937]<dict(gs(w))[938]-30,gs(w)
passed('A passive police officer ranks below a gang member (no wanted stars for nothing)')
for heading,expect in [(90.,140),(270.,90)]:
 w,c,f=gunner_world([]);drv,car=960,961;w.exists.update({drv,car});w.cars[car]={'pos':[30.,0.,0.],'heading':heading};w.model[car]=400;w.incar[drv]=car;w.traffic=[car];w.seats[(car,-1)]=drv
 w.pedtype[drv]=7;w.skin[drv]=20;w.damage.add((1,drv));w.car_speeds={car:20.};w.shared[b.SQ_T]=drv;w.step(c,f,n=16)
 assert dict(gs(w)).get(drv)==expect,(heading,gs(w))
passed('A car racing at CJ scores +50 for its driver; one driving away does not')
w,c,f=gunner_world([(970,24.,0.)]);w.step(c,f,n=16);assert gtargets(w)[0]==970,gtargets(w)
seat=None
def hide(a,z):return not(abs(z[0]-24.)<.6 and abs(z[1]-6.)<.6)
w.pos[970]=[24.,6.,0.];w.los_fn=hide;w.calls.clear();w.step(c,f,n=22)
assert w.shared[b.GT_SUPP]==1 and gtargets(w)[0]==970,(w.shared[b.GT_SUPP],gtargets(w))
shots=[x[2] for x in w.calls if x[1]==0x6bc and x[0]>w.now-1000]
assert any(abs(s[4])<1. and abs(s[3]-24.)<1.5 for s in shots),shots[-3:]
passed('A target that ducks behind cover gets suppressive fire at his last seen position')
for _ in range(30):w.step(c,f)  # 4 s after he was last seen, before the 5 s hand-over
assert w.shared[b.GT_SUPP]==0,'suppression ends after about 4 s'
passed('Suppression stops after about 4 s instead of wasting rounds on a wall')
w,c,f=gunner_world([(950,20.,0.),(951,-20.,0.)]);w.weapons.update({950:30,951:30});w.shooting_chars={950,951};w.actor_heading[950]=90.;w.actor_heading[951]=90.
for n in (950,951):w.damage.add((1,n))
w.step(c,f,n=16);sc=dict(gs(w));assert sc[950]-sc[951]==60,sc
passed('A gunman who is shooting AND turned towards CJ outranks one shooting the other way (+60), with no bullet trace needed')
# ------------------------------------------------------------------ 1.2 FOLLOW MY SHOTS (gunners fire where CJ fires)
def cj_fire(w,c,f,frames,every=6,target=(24.,0.,1.),muzzle=(.5,0.,.7),sample=None,after=12):
 """CJ fires every `every` frames (IS_CHAR_SHOOTING is a one-frame pulse); each shot leaves an engine-style trace."""
 out=[]
 for i in range(frames):
  shot=i%every==0;w.shooting=shot
  if shot:w.ped_bullet(list(muzzle),list(target))
  w.step(c,f)
  if sample and i>=after:out.append(sample(w))
 w.shooting=False;return out
def follow_world(npcs):
 w,c,f=gunner_world(npcs);w.shared[b.FIRE]=2;w.frame_ms=33;w.step(c,f,n=3)
 for n,*_ in npcs:w.weapons[n]=30
 return w,c,f
def fired_at(w,since):return [x[2][3:6] for x in calls(w,0x6bc) if x[0]>=since]
w,c,f=follow_world([(940,24.,0.)]);w.blockers=[((24.,0.,1.),.6)]   # the ped is solid for line-of-sight checks that include peds
ok=cj_fire(w,c,f,90,sample=lambda w:940 in gtargets(w) and w.shared[b.FIRE_ACTIVE]==1)
assert sum(ok)>=.9*len(ok),(sum(ok),len(ok))
ends=fired_at(w,0);assert ends and all(22.<e[0]<27. and abs(e[1])<1.5 for e in ends[-5:]),ends[-5:]
passed('FOLLOW MY SHOTS: single shots (one-frame IS_CHAR_SHOOTING pulses) keep the gunners on his target without flicker')
t0=w.now;w.step(c,f,n=60)
assert w.shared[b.FIRE_ACTIVE]==0 and not fired_at(w,t0+1000),(w.shared[b.FIRE_ACTIVE],len(fired_at(w,t0+1000)))
passed('FOLLOW MY SHOTS: about a second after CJ stops, the gunners stop too')
w,c,f=follow_world([])
w.los_fn=lambda a,z:not((a[0]<15.<=z[0]) or (z[0]<15.<=a[0]))
cj_fire(w,c,f,60,target=(14.9,0.,.9));ends=fired_at(w,0)
assert ends and all(13.5<e[0]<16.5 and abs(e[1])<1.5 for e in ends),ends[:5]
passed('FOLLOW MY SHOTS, free aim at a wall: the gunners fire at the point where his line meets the wall')
w,c,f=follow_world([]);cj_fire(w,c,f,60,target=(120.,0.,40.))
assert not calls(w,0x6bc),'shots at the sky / far scenery do not draw gunner fire'
passed('FOLLOW MY SHOTS: nothing on his line within 170 m (the sky) - no rounds wasted')
w,c,f=follow_world([(940,24.,0.)]);w.targeting=940;w.blockers=[((24.,0.,1.),.6)]
for i in range(60):
 w.shooting=i%6==0;w.step(c,f)
assert 940 in gtargets(w) or w.shared[b.FIRE_ACTIVE]==1,(gtargets(w),w.shared[b.FIRE_ACTIVE])
passed('FOLLOW MY SHOTS without any bullet trace (grenade, flamethrower): the game\'s lock-on target still draws fire')
w,c,f=follow_world([]);w.shared[b.GROUND_PUB]=941;w.exists.add(941);w.pos[941]=[1.5,1.,0.]
for i in range(60):w.ped_bullet([1.6,1.2,1.],[30.,5.,1.]);w.step(c,f)
assert w.shared[b.FIRE_ACTIVE]==0 and not calls(w,0x6bc),'a guard shooting next to CJ is not CJ shooting'
passed('FOLLOW MY SHOTS: a guard firing next to CJ (CJ not shooting) does not start the gunners')
w,c,f=follow_world([(940,24.,0.)]);w.blockers=[((24.,0.,1.),.6)];w.shared[b.GROUND_PUB]=941;w.exists.add(941);w.pos[941]=[-.8,1.,0.]
for i in range(90):
 w.shooting=i%6==0
 if w.shooting:w.ped_bullet([.5,0.,.7],[24.,0.,1.])
 w.ped_bullet([-.9,1.,1.],[-30.,2.,1.]);w.step(c,f)
ends=fired_at(w,0);assert ends and all(e[0]>10. for e in ends),ends[:6]
passed('FOLLOW MY SHOTS: with a guard firing the other way next to him, the gunners still follow CJ\'s own line')
# ------------------------------------------------------------------ 1.2 helicopter lifecycle
def spawn_world(visible):
 w,c,_=setup();w.visible_fn=visible;command=g['command'];command(w,c,1,ticks=8)
 car=c.v[5];return w,c,car,w.cars[car]['pos']
front=lambda p:p[1]>3 and abs(p[0])<2.*p[1] and math.dist(p[:2],[0.,0.])<400.      # the camera looks along +y
w,c,car,pos=spawn_world(front)
assert 140.<math.dist(pos[:2],[0.,0.])<200. and pos[2]>=50. and not w.visible(car),(pos,w.visible(car))
assert w.shared[b.STATE]==2
passed('CALL HELICOPTER: it is created 160 m out, 50 m up and behind CJ, out of the camera\'s view, and flies in')
w,c,car,pos=spawn_world(lambda p:p[1]<-3 and abs(p[0])<2.*(-p[1]))              # the camera looks along -y: behind is in view
assert abs(pos[0]+160.)<2. and abs(pos[1])<2. and not w.visible(car),pos
passed('When the first bearing is in view it is moved, in the same tick, to the next bearing where it is not')
w,c,car,pos=spawn_world(lambda p:True)
assert abs(pos[0])<2. and abs(pos[1]-160.)<2.,pos
passed('When every bearing is in view (e.g. a tall tower) the last one is used instead of looping')
w,c,car,pos=spawn_world(front);made=[x for x in calls(w,0xa5)][-1][0]
assert all(x['time']==made or not x['visible'] for x in w.teleports if x['who']==car),w.teleports
passed('The relocation to a hidden bearing happens in the creation tick: no visible teleport')
w,c,_=setup();w.ground_fn=lambda x,y,z:80.;w.visible_fn=front;g['command'](w,c,1,ticks=8);pos=w.cars[c.v[5]]['pos']
assert pos[2]>=105.,pos
passed('Spawn altitude clears the highest surface by 25 m')
w,c,car,pos=spawn_world(front)
crew=[x[2] for x in calls(w,0x9a)];assert crew and all(math.dist(x[2:5],pos)<3. for x in crew[:4]),(pos,crew[:4])
passed('The gunners are created at the helicopter (not at CJ) and attached at once')
w,c,_=setup();summon(w,c);w.car=[30.,40.,28.];g['command'](w,c,4,ticks=3);m=calls(w,0x4a2)[-1][2]
assert abs(m[1]-900.)<3. and abs(m[2]-1200.)<3. and calls(w,0xad)[-1][2][1]==40.,(m,calls(w,0xad)[-1])
passed('DISMISS: the helicopter flies off AWAY from CJ (through its own position), at cruise speed 40')
w,c,_=setup();summon(w,c);w.visible_fn=lambda p:False;g['command'](w,c,4,ticks=3);old=c.v[5]
w.car=[0.,-120.,60.];w.now+=4000;w.step(c,n=3);assert old in w.exists,'out of sight but only 120 m away: not removed yet'
w.car=[0.,-260.,60.];w.now+=500;w.step(c,n=3);assert old not in w.exists and w.shared[b.STATE]==0,(w.shared[b.STATE],)
passed('DISMISS: removed only when out of sight AND at least 200 m away')
w,c,_=setup();summon(w,c);pilot=c.v[4];w.playing=False;w.step(c,n=4)
assert not [x for x in calls(w,0x792) if x[2][0]==pilot],'a living pilot is not thrown out of his helicopter by the clean-up'
passed('Clean-up (CJ dead or arrested) does not eject a living pilot from his helicopter')
# ------------------------------------------------------------------ v41 pilot
w,c,f=gunner_world([]);w.messages.clear()
for _ in range(6):w.ped_bullet([70.,0.,0.],list(w.car));w.ped_bullet([70.,5.,0.],[w.car[0]+2,w.car[1],w.car[2]]);w.step(c,f)
assert w.shared[b.EVADE_UNTIL]>w.now and 'HCSHOT' in w.messages,(w.shared[b.EVADE_UNTIL],w.now,w.messages)
passed('Rounds hitting the helicopter make the pilot break away at once, before the hull is damaged')
w,c,f=gunner_world([])
for _ in range(6):w.exact_bullet(list(w.car),[w.car[0]+30,w.car[1],0.]);w.ped_bullet(list(w.car),[w.car[0]+30,w.car[1]+3,0.]);w.step(c,f)
assert w.shared[b.EVADE_UNTIL]<=w.now,'our own gunners firing from the helicopter are not "taking fire"'
passed('The gunners\' own rounds leaving the helicopter do not trigger evasion')
fire_world,target=g['fire_world'],g['target']
def orbit_steps(dead_left):
 w,c,f=fire_world();npc=target(w,typ=7,skin=20);w.damage.add((1,npc));w.step(c,f,n=10)
 if dead_left:
  for i in (4,6):w.dead.add(w.shared[b.PUB+i])
 seq=[]
 for _ in range(60):
  w.step(c,f);v=w.shared[b.ORBIT_I]
  if not seq or seq[-1]!=v:seq.append(v)
 return seq
up=orbit_steps(False);down=orbit_steps(True)
assert all((y-x)%8==1 for x,y in zip(up,up[1:])) and all((x-y)%8==1 for x,y in zip(down,down[1:])) and len(down)>=3,(up,down)
passed('Combat orbit direction keeps the door with more living gunners towards the threat (left door by default, right when the left gunners are down)')
w,c,f=fire_world();npc=target(w,typ=7,skin=20);w.pos[npc][2]=10.;w.damage.add((1,npc));w.step(c,f,n=12)
m=calls(w,0x4a2)[-1][2];assert abs(m[3]-(10.+25.+15.))<.01,m
passed('A shooter on a roof is circled 15 m higher')
w,c,f=gunner_world([(911,-2.,0.),(940,12.,0.)]);w.step(c,f,n=16);first=w.shared[b.GUARD_TARGET]
w.exists.add(941);w.pos[941]=[30.,-45.,0.];w.skin[941]=20;w.pedtype[941]=7;w.damage.add((1,941));w.shared[b.SQ_T]=941;w.step(c,f,n=30)
assert first==940 and w.shared[b.GUARD_TARGET]==940,(first,[w.shared[b.GUARD_TARGET+i] for i in range(4)])
passed('A gunner finishes the target he started instead of hopping to a newer one')
# ------------------------------------------------------------------ v41 threat board: squad
def squad_scene(npcs):
 w,c,ground,sq,team=escort_world();V=(c,ground,sq)
 for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1],0.]
 steps(w,V,3);w.civilians=[]
 for n,x,y,wpn,hostile in npcs:
  w.exists.add(n);w.pos[n]=[x,y,0.];w.pedtype[n]=7;w.skin[n]=20;w.weapons[n]=wpn;w.civilians.append(n)
  if hostile:w.damage.add((1,n))
 return w,V,team
w,V,team=squad_scene([(980,20.,0.,30,True),(981,-40.,0.,22,False)]);w.weapons[981]=30;V=V+(VM('Helicover_Fire',w),);w.messages.clear();steps(w,V,8)
assert w.shared[b.SQ_T]==980 and 981 not in [w.shared[b.SQ_T+i] for i in range(4)] and 'SQCR' in w.messages,([w.shared[b.SQ_T+i] for i in range(4)],w.messages)
for _ in range(45):w.ped_bullet([-40.,0.,1.],[1.5,-1.,.5]);steps(w,V,1)
assert w.shared[b.TB_SHOOTER]==981 and w.shared[b.SQ_T]==981 and w.shared[b.SQ_T+1]==980,([w.shared[b.SQ_T+i] for i in range(4)],[w.shared[b.SQ_SC+i] for i in range(4)])
assert 'SQXL' in w.messages and last(w,0x634,team[0])[1]==981,(w.messages,orders(w,0x634,team[0])[-2:])
passed('Squad: the man firing at CJ from 40 m (found only through his bullet traces) jumps to the top of the list, guard 0 takes him, "Shots at CJ - left!"')
w,V,team=squad_scene([(982,0.,-25.,34,True)]);w.messages.clear();steps(w,V,8)
assert 'SQSB' in w.messages,w.messages
w,V,team=squad_scene([(983,22.,0.,30,True)]);w.pos[983][2]=9.;w.messages.clear();steps(w,V,8)
assert 'SQRR' in w.messages,w.messages
passed('Squad call-outs name the kind of threat and where: "Sniper - rear!", "Shooter on the roof - right!"')
w,V,team=squad_scene([(990,0.,20.,30,True)]);w.shooting_chars.add(990)
def low_wall(a,z):return not(abs(z[0]-3.5)<.1 and abs(z[1]-3.2)<.1 and z[2]<1.)
w.los_fn=low_wall;w.messages.clear();steps(w,V,10)
o=last(w,0x637,team[0]);assert abs(o[1]-3.5)<.01 and abs(o[2]-3.2)<.01 and o[7]==990,o
assert w.shared[b.CV_OK]==1  # the 'taking cover' chatter itself is dropped while 'CONTACT' is on screen
w.pos[team[0]]=[3.5,3.2,0.];w.calls.clear();steps(w,V,4)
assert last(w,0x634,team[0])[1]==990
passed('Under fire an engager moves to low cover (blocks the chest, not the head) and fights crouched from there')
w,V,team=squad_scene([(991,0.,20.,30,True)]);w.shooting_chars.add(991);w.messages.clear();steps(w,V,10)
assert last(w,0x634,team[0])[1]==991 and 'SQCVR' not in w.messages,'no cover nearby: fight crouched where he stands'
passed('Without cover nearby the engager fights crouched where he stands')
w.calls.clear();steps(w,V,130)
ducks=[x for x in w.calls if x[1]==0x5c5];who={x[2][0] for x in ducks}
assert ducks and 'SQRLD' in w.messages and len(who)>=2,(len(ducks),who)
times=sorted((x[0],x[2][0]) for x in ducks);assert all(b2[0]-a2[0]>=1000 or a2[1]==b2[1] for a2,b2 in zip(times,times[1:])),times
passed('Reload drill: after 10 s of fighting guards crouch 1.5 s to reload, staggered so the others keep firing')
w,V,team=squad_scene([(992,20.,0.,30,True),(993,-20.,0.,30,True),(994,0.,-20.,30,True)]);w.health[1]=30;w.messages.clear();steps(w,V,30)
assert 'SQCOV' in w.messages and 'SQEVAC' in w.messages and w.messages.index('SQCOV')<w.messages.index('SQEVAC'),w.messages
passed('CJ badly hurt with three or more threats: shields up, then "EVAC recommended"')
w,V,team=squad_scene([]);w.calls.clear();steps(w,V,30)
assert any(orders(w,0x667,t) for t in team)
w.now+=21000;w.calls.clear();steps(w,V,30)
assert not any(orders(w,0x667,t) for t in team) and all(w.shared[sqb.fk(k,'TASK')]==16 for k in range(4)),[w.shared[sqb.fk(k,'TASK')] for k in range(4)]
w.exists.add(995);w.pos[995]=[20.,0.,0.];w.pedtype[995]=7;w.weapons[995]=30;w.civilians=[995];w.damage.add((1,995));w.calls.clear();steps(w,V,8)
assert orders(w,0x634,team[0]) and orders(w,0x634,team[0])[-1][1]==995
passed('After 20 s of quiet the team lowers its weapons; the first threat puts them back on alert')

# ------------------------------------------------------------------ 1.1: v41 details completed
w,c,f=gunner_world([]);drv,car=962,963;w.exists.update({drv,car});w.cars[car]={'pos':[24.,0.,0.],'heading':90.};w.model[car]=400;w.incar[drv]=car
w.traffic=[car];w.seats[(car,-1)]=drv;w.pedtype[drv]=7;w.skin[drv]=20;w.damage.add((1,drv));w.car_speeds={car:20.};w.shared[b.SQ_T]=drv;w.calls.clear();w.step(c,f,n=30)
ends=[x[2][3:5] for x in calls(w,0x6bc)]
engine=[e for e in ends if math.dist(e,[24.,1.8])<.9];cabin=[e for e in ends if math.dist(e,[24.,0.])<.9]
assert engine and cabin,ends[-6:]
passed('A car target: right-door gunners hit the engine, left-door gunners the driver')
w,c,f=gunner_world([(940,-24.,0.),(941,24.,0.),(942,0.,24.),(943,0.,-24.)]);w.damage.add((1,941));w.targeting=940;w.step(c,f,n=30)
assert gtargets(w).count(940)==2,(gtargets(w),gs(w))
passed('CJ aiming at someone: two gunners join him on that target at once')
for hit in (True,False):
 w,c,f=gunner_world([(950,24.,0.),(952,-24.,0.)]);w.step(c,f,n=16);first=gtargets(w)[0]
 for _ in range(80):
  if hit:w.health[950]-=2
  w.step(c,f)
 assert first==950 and (gtargets(w)[0]==950)==hit,(hit,first,gtargets(w))
passed('A gunner keeps a target he is hurting, and hands it over after 5 s without a hit')
w,c,f=fire_world();npc=target(w,typ=7,skin=20);w.pos[npc]=[40.,0.,0.];w.damage.add((1,npc));w.step(c,f,n=12)
for _ in range(20):
 w.step(c,f);m=calls(w,0x4a2)[-1][2];assert abs(math.dist(m[1:3],[28.,0.])-b.ORBIT_RADIUS)<.5,m
passed('Threat 40 m from CJ: the orbit centre moves 30% towards CJ so the gunners cover both')
w,V,team=squad_scene([(997,0.,20.,30,True)]);steps(w,V,10)
assert last(w,0x634,team[0])[1]==997
def wall(a,z):return not(abs(z[0]-3.)<.6 and abs(z[1]-22.)<.6 and abs(a[0])<.1 and abs(a[1]-3.2)<.1)
w.los_fn=wall;w.pos[997]=[3.,22.,0.];w.calls.clear();steps(w,V,40)
o=orders(w,0x668,team[0]);assert o and abs(o[-1][1])<.01 and abs(o[-1][2]-20.)<.01,o
w.calls.clear();steps(w,V,60);assert not orders(w,0x668,team[0]) and orders(w,0x634,team[0])
passed('A threat that slips out of a guard\'s sight gets 4 s of suppressive fire at his last seen spot, then normal fighting')
for hp,expect_back in [(100,False),(40,True)]:
 w,V,team=squad_scene([(998,0.,25.,30,True)]);steps(w,V,8);w.pos[team[0]]=[0.,12.,0.];w.health[team[0]]=hp;w.calls.clear();steps(w,V,4)
 back=bool(orders(w,0x5d3,team[0]));assert back==expect_back,(hp,back)
passed('A wounded guard (below 50 HP) stays closer to CJ: 10 m leash instead of 14 m')
# ------------------------------------------------------------------ 1.1 messages
w,c,_=setup();w.step(c,n=80)
assert w.messages.count('HCHELLO')==1,w.messages
w.step(c,n=100);assert w.messages.count('HCHELLO')==1
passed('Welcome message once, a few seconds after the game starts')
w,c,p=setup(True);summon(w,c);ground=VM('Helicover_Ground',w);sq=VM('Helicover_Squad',w);w.health[1]=100;w.step(c,p,ground,sq,n=3)
w.messages.clear();w.shared[b.CMD]=16;w.step(c,p,ground,sq,n=6)
w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;w.step(c,p,ground,sq,n=30)
assert 'HCRTEAM' in w.messages and 'SQIN' in w.messages and not {'HCROPE','HCHOLD','HCFOLL'}&set(w.messages),w.messages
passed('Team drop notices say what really happens: "moving in to drop the team", "on the ground" - no false "rope pickup" / "holding"')
def noisy_fight(level,secs=12):
 w,V,team=squad_scene([(980+i,x,y,30,True) for i,(x,y) in enumerate([(20,0),(-20,0),(0,20),(0,-20)])])
 for n in range(980,984):w.shooting_chars.add(n)
 w.shared[b.HUD]=level;w.health[1]=60;w.messages.clear();n0=len(w.messages)
 for _ in range(secs*10):w.ped_bullet([-20.,0.,1.],[1.,1.,.5]);steps(w,V,1)
 return w,V,team
w,V,team=noisy_fight(2)
assert 2<=len(w.messages)<=6,w.messages
passed('A 12 s fight with four shooters gives %d clear radio calls, not a stream (%s)'%(len(w.messages),', '.join(w.messages)))
w,V,team=squad_scene([(985,20.,0.,30,True)]);w.shooting_chars.add(985);w.shared[b.MSG_PRIO]=3;w.shared[b.MSG_UNTIL]=w.now+8000;w.messages.clear();steps(w,V,70)
assert not w.messages,w.messages
w.shared[b.MSG_PRIO]=1;steps(w,V,100);assert 'SQRLD' in w.messages,w.messages
passed('An alarm on screen is not covered by lesser calls; once it expires the chatter comes back')
w,V,team=noisy_fight(1)
assert w.messages and not {'SQRLD','SQCVR','SQMED','SQMEDG','SQCAR'}&set(w.messages),w.messages
passed('MESSAGES: IMPORTANT keeps danger and tactical calls, drops the chatter')
w,V,team=noisy_fight(0,6)
assert not w.messages,w.messages
w.shared[b.CMD]=16;steps(w,V,4);assert w.messages==['SQALR'],w.messages
passed('MESSAGES: OFF is silent in a fight but still explains why a command was refused')
w,c,ground,sq,team=escort_world();f=VM('Helicover_Fire',w);V=(c,ground,sq,f)
for k,tm in enumerate(team):w.pos[tm]=[BG[k][0],BG[k][1],0.]
hostile=996;w.exists.add(hostile);w.pos[hostile]=[20.,0.,0.];w.pedtype[hostile]=7;w.weapons[hostile]=30;w.civilians=[hostile];w.damage.add((1,hostile))
w.messages.clear();w.shared[b.MSG_UNTIL]=0;steps(w,V,30)
assert 'SQCR' in w.messages and 'HCCONT' not in w.messages,w.messages
passed('With the team on the ground only the squad calls the contact (no double "CONTACT!")')
w,c,p=setup(True);launch=VM('Helicover',w);w.step(c,p,launch,n=15);w.events.append(1);w.step(c,p,n=4)
rows=[]
for _ in range(4):rows.append(w.menu[7]);w.events.append(5);w.step(c,p,n=4)
assert rows==[b'MESSAGES: ALL',b'MESSAGES: IMPORTANT',b'MESSAGES: OFF',b'MESSAGES: ALL'],rows
passed('SETTINGS: one row cycles MESSAGES: ALL / IMPORTANT / OFF')
# ------------------------------------------------------------------ v41 frame cost
def peak_of(vm,fn):
 orig=vm.run;box=[0]
 def run():
  n0=len(vm.w.calls);orig();box[0]=max(box[0],len(vm.w.calls)-n0)
 vm.run=run;fn();vm.run=orig;return box[0]
w,c,f=gunner_world([(900+i,x,y) for i,(x,y) in enumerate([(20,0),(-20,0),(0,20),(0,-20),(12,4),(-12,4),(4,12),(4,-12)])])
for n in range(900,908):w.weapons[n]=30;w.damage.add((1,n))
for i in range(4):w.shared[b.SQ_T+i]=904+i
def fire_run():
 for _ in range(200):w.ped_bullet([20.,0.,1.],w.player.copy());w.step(c,f)
fpeak=peak_of(f,fire_run)
w,V,team=squad_scene([(980+i,x,y,30,True) for i,(x,y) in enumerate([(20,0),(-20,0),(0,20),(0,-20),(14,14),(-14,-14)])])
for n in range(980,986):w.shooting_chars.add(n)
def squad_run():
 for _ in range(200):w.ped_bullet([-20.,0.,1.],w.player.copy());steps(w,V,1)
speak=peak_of(V[2],squad_run)
assert fpeak<=3600 and speak<=2000,(fpeak,speak)
passed('Frame cost in a busy fight (8 threats, rounds at CJ): fire worker peak %d, squad worker peak %d script instructions'%(fpeak,speak))

text='\n'.join(results)+'\nMocked script execution only: real pathing, cover and gunfire are not tested.\n'
(b.OUT/'squad_tests.txt').write_text(text);print(text)
