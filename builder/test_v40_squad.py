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
 w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;w.step(c,ground,sq,n=14)
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
w.calls.clear();steps(w,V,3)
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
w.pos[team[3]]=[0.,-1.,0.];steps(w,V,3)
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
w.pos[team[0]]=[0.,-120.,0.];w.offscreen={team[0]};w.calls.clear();steps(w,V,2)
o=last(w,0xa1,team[0]);assert abs(o[1]-BG[0][0])<.01 and abs(o[2]-BG[0][1])<.01,o
w.pos[team[1]]=[0.,-120.,0.];w.offscreen=set();w.calls.clear();steps(w,V,2)
assert orders(w,0x5f5,team[1]) and not orders(w,0xa1,team[1])
passed('Far behind: teleport only out of sight, otherwise run on the path network')
w.pos[team[2]]=[12.,0.,0.];w.calls.clear();steps(w,V,6);w.now+=3000;steps(w,V,2);w.offscreen={team[2]};w.now+=3000;steps(w,V,3)
assert orders(w,0xa1,team[2]),'stuck guard not recovered'
w.offscreen=set()
passed('A stuck guard (moving, far, not progressing) is recovered out of sight')
w.dead.add(team[1]);w.messages.clear();steps(w,V,4);assert w.messages.count('SQDOWN')==1
steps(w,V,10);assert w.messages.count('SQDOWN')==1
passed('MAN DOWN is called once when a guard dies')
# ------------------------------------------------------------------ recall
w.dead.discard(team[1]);w.car=[0.,-40.,28.];w.shared[b.CMD]=17;steps(w,V,6)
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
assert all(t not in w.exists for t in team) and w.shared[b.ESCORT_ON]==0 and 'SQBACK' in w.messages
passed('CJ boards the helicopter another way: the team withdraws and boards')
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
for t in team:w.dead.add(t)
steps(w,V,12);assert 'SQLOST' in w.messages and w.shared[b.ESCORT_ON]==0 and 'SQBACK' not in w.messages
passed('Losing the whole team is reported and cleaned up')
w,c,ground,sq,team=escort_world();V=(c,ground,sq);spawned=len(calls(w,0x503))
w.car=[0.,-40.,28.];w.shared[b.CMD]=10;steps(w,V,6);assert w.shared[b.STATE]==19
w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;steps(w,V,14)
assert 'SQCOVER' in w.messages and len(calls(w,0x503))<=spawned+1 and all(t in w.exists for t in team) and w.shared[b.SQ_ROPE]==1,(w.messages,len(calls(w,0x503)))
passed('Rope pickup with the team on the ground: the same team covers CJ (only the CJ rope is added)')
# ------------------------------------------------------------------ assault tactics
w,c,ground,sq,team=escort_world(tactics=1);V=(c,ground,sq)
for k,t in enumerate(team):w.pos[t]=list(sqb.AS_FORM[k])+[0.]
hostile=950;w.exists.add(hostile);w.pos[hostile]=[30.,0.,0.];w.pedtype[hostile]=7;w.weapons[hostile]=30;w.civilians=[hostile];w.damage.add((1,hostile))
w.now=(w.now//3000+1)*3000+100;w.calls.clear();w.messages.clear();steps(w,V,6)
mover,cover=(team[0],team[1]) if (w.now//3000)%2==0 else (team[1],team[0])
o=last(w,0x637,mover);g0=w.pos[mover];step=min(math.dist(g0[:2],[30.,0.])-8.,6.)
assert o[7]==hostile and abs(math.dist(o[1:3],g0[:2])-step)<.05 and math.dist(o[1:3],[30.,0.])<math.dist(g0[:2],[30.,0.]),o
assert last(w,0x634,cover)[1]==hostile and not orders(w,0x637,cover)
assert 'SQAR' in w.messages,w.messages
o=last(w,0x637,team[2]);assert abs(o[1]-30.)<.01 and abs(o[2]+9.)<.01 and o[4]==6 and o[7]==hostile,o
o=last(w,0x637,team[3]);assert abs(o[1]-30.)<.01 and abs(o[2]-9.)<.01 and o[7]==hostile,o
passed('Assault contact: one man bounds forward firing while his partner covers crouched; flankers move out firing')
w.now+=3000;w.calls.clear();steps(w,V,4)
assert orders(w,0x637,cover) and last(w,0x634,mover)[1]==hostile
passed('Bounding overwatch: every 3 s the pair swaps who moves and who covers')
w.pos[team[2]]=[29.,-8.,0.];w.calls.clear();steps(w,V,3);assert last(w,0x7a5,team[2])[1]==hostile
passed('A flanker who reached his flank point attacks from there')
w.pos[team[0]]=[0.,60.,0.];w.calls.clear();steps(w,V,3)
o=last(w,0x5d3,team[0]);assert o[4]==7 and abs(o[2]-sqb.AS_FORM[0][1])<.01,o
passed('Assault leash: nobody pushes more than 40 m away from CJ')
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
w.events.append(3);w.step(c,p,n=4);assert w.menu[-2]==b'TEAM ON FOOT >' and w.menu[-1]==b'< BACK'
w.events.append(6);w.step(c,p,n=4);assert w.menu[2:]==[b'DEPLOY TEAM',b'TACTICS: BODYGUARD [ON]',b'TACTICS: ASSAULT',b'< BACK'],w.menu
w.events.append(2);w.step(c,p,n=4);assert w.shared[b.TACTICS]==1 and w.menu[3:5]==[b'TACTICS: BODYGUARD',b'TACTICS: ASSAULT [ON]'],w.menu
w.shared[b.ESCORT_ON]=1;w.step(c,p,n=4);assert w.menu[2]==b'RECALL TEAM',w.menu
w.events.append(0);w.step(c,p,n=2);assert w.shared[b.CMD] in (17,0) and any(x[2]==[b.CMD,17] for x in calls(w,0xddc))
passed('EVAC > TEAM ON FOOT: deploy/recall and BODYGUARD/ASSAULT tactics')
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.shared[b.CMD]=16;w.step(c,n=5);assert 'HCEXIT' in w.messages and w.shared[b.STATE]!=19
w,c,_=setup();summon(w,c);w.shared[b.ESCORT_ON]=1;w.shared[b.CMD]=16;w.step(c,n=5);assert 'SQALR' in w.messages
w,c,_=setup();summon(w,c);w.shared[b.CMD]=17;w.step(c,n=5);assert 'SQNONE' in w.messages
car=777;w.exists.add(car);w.cars[car]={'pos':[0.,0.,0.],'heading':0.};w.model[car]=400;w.incar[1]=car;w.shared[b.CMD]=16;w.step(c,n=5);assert 'SQFOOT' in w.messages
passed('TEAM ON FOOT refuses politely: CJ aboard, team already down, nothing to recall, CJ in a car')
# ------------------------------------------------------------------ overwatch flight
w,c,_=setup();summon(w,c);w.car=[0.,-40.,28.];w.step(c,n=3)
pts=[]
for _ in range(90):
 n=len(calls(w,0x4a2));w.step(c)
 for x in calls(w,0x4a2)[n:]:pts.append(x[2])
assert pts and all(abs(math.dist(m[1:3],[0.,0.])-30.)<.05 and abs(m[3]-24.)<.01 for m in pts),pts[:3]
assert len({(round(m[1]),round(m[2])) for m in pts})>=3
passed('Overwatch: the helicopter circles CJ at 30 m, 24 m above him, instead of hovering on top')
w,c,_=setup();summon(w,c);w.car=[0.,-40.,28.];w.los_fn=lambda a,z:a[0]<=.01;n0=len(calls(w,0x4a2));w.step(c,n=40)
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
w,c,f=gunner_world([(930,-12.,0.),(931,12.,0.),(932,0.,12.),(933,0.,-12.)]);w.messages.clear()
for _ in range(34):w.traces=[{'start':[12.,0.,1.],'end':[1.5,1.,.5],'time':w.now}];w.step(c,f)
assert w.shared[b.TB_SHOOTER]==931 and gs(w)[0][0]==931 and gs(w)[0][1]>=120,(w.shared[b.TB_SHOOTER],gs(w))
assert gtargets(w).count(931)==2 and len(set(gtargets(w)))==3 and 'HCFOCUS' in w.messages,(gtargets(w),w.messages)
passed('A round that lands at CJ names its shooter from the bullet trace: top of the board, two gunners on him, call-out')
w,c,f=gunner_world([(933,-12.,0.)]);w.traces=[{'start':[-12.,0.,1.],'end':[30.,30.,0.],'time':0}]
for _ in range(16):w.traces[0]['time']=w.now;w.step(c,f)
assert w.shared[b.TB_SHOOTER]!=933,'a round that missed CJ by far names nobody'
passed('Rounds that do not come down at CJ do not make anyone the shooter')
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
w.step(c,f,n=50);assert w.shared[b.GT_SUPP]==0,'suppression ends after about 4 s'
passed('Suppression stops after about 4 s instead of wasting rounds on a wall')
# ------------------------------------------------------------------ v41 pilot
w,c,f=gunner_world([]);w.messages.clear()
for _ in range(4):w.traces=[{'start':[70.,0.,0.],'end':list(w.car),'time':w.now},{'start':[70.,5.,0.],'end':[w.car[0]+2,w.car[1],w.car[2]],'time':w.now}];w.step(c,f)
assert w.shared[b.EVADE_UNTIL]>w.now and 'HCSHOT' in w.messages,(w.shared[b.EVADE_UNTIL],w.now,w.messages)
passed('Rounds hitting the helicopter make the pilot break away at once, before the hull is damaged')
w,c,f=gunner_world([]);w.traces=[{'start':list(w.car),'end':[w.car[0]+30,w.car[1],0.],'time':0}]
for _ in range(4):w.traces[0]['time']=w.now;w.step(c,f)
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
w,V,team=squad_scene([(980,20.,0.,30,True),(981,-40.,0.,22,False)]);w.messages.clear();steps(w,V,8)
assert w.shared[b.SQ_T]==980 and 981 not in [w.shared[b.SQ_T+i] for i in range(4)] and 'SQCR' in w.messages,([w.shared[b.SQ_T+i] for i in range(4)],w.messages)
for _ in range(45):w.traces=[{'start':[-40.,0.,1.],'end':[1.5,-1.,.5],'time':w.now}];steps(w,V,1)
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
assert 'SQCVR' in w.messages,w.messages
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
 for _ in range(200):w.traces=[{'start':[20.,0.,1.],'end':w.player.copy(),'time':w.now}];w.step(c,f)
fpeak=peak_of(f,fire_run)
w,V,team=squad_scene([(980+i,x,y,30,True) for i,(x,y) in enumerate([(20,0),(-20,0),(0,20),(0,-20),(14,14),(-14,-14)])])
for n in range(980,986):w.shooting_chars.add(n)
def squad_run():
 for _ in range(200):w.traces=[{'start':[-20.,0.,1.],'end':w.player.copy(),'time':w.now}];steps(w,V,1)
speak=peak_of(V[2],squad_run)
assert fpeak<=3600 and speak<=2000,(fpeak,speak)
passed('Frame cost in a busy fight (8 threats, rounds at CJ): fire worker peak %d, squad worker peak %d script instructions'%(fpeak,speak))

text='\n'.join(results)+'\nMocked script execution only: real pathing, cover and gunfire are not tested.\n'
(b.OUT/'squad_tests.txt').write_text(text);print(text)
