"""v40 tactical squad, TEAM ON FOOT escort and overwatch flight, on the mocked VM of test_v25.py.
Mocked script execution only: real GTA pathing, cover use and gunfire are not simulated."""
import math,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;P=HERE/'test_v25.py'
_src=P.read_text();g={'__file__':str(P),'__name__':'v25_harness'}
exec(compile(_src[:_src.index('results=[]')],str(P),'exec'),g)
for _m in re.finditer(r'^def [a-z_0-9]+\(.*?(?=^\S)',_src,re.S|re.M):exec(compile(_m.group(0),str(P),'exec'),g)
World,VM,b,setup,summon,calls,invariants,command=g['World'],g['VM'],g['b'],g['setup'],g['summon'],g['calls'],g['invariants'],g['command']
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
FIRING=(0x74d,0x634,0x637,0x7a5,0x668)
def firing(w,who):return [x for x in w.calls if x[1] in FIRING and x[2][0]==who]
def run_order(w,who):
 """His last run order: (point, firing as he runs). With the brain's leave he runs firing (0637), without it he just runs (05D3)."""
 o=[(x[1],x[2]) for x in w.calls if x[1] in (0x637,0x5d3) and x[2][0]==who];assert o,who;op,v=o[-1];return v[1:4],op==0x637
def fights(w,who,man):
 """He is on that man: a firing task at him, or - when the brain holds his fire - his weapon on him."""
 f=[x for x in firing(w,who) if man in x[2][1:8]];return bool(f) or any(math.dist(x[2][1:3],w.coords(man)[:2])<.5 for x in w.calls if x[1]==0x667 and x[2][0]==who)
w.walk.clear();w.calls.clear();w.messages.clear();steps(w,V,1)
assert [w.shared[b.SQ_BR_ST+i] for i in range(4)]==[3,3,3,3] and not [x for x in w.calls if x[1] in FIRING],'the first look: every guard has his man, nobody has leave to fire yet (weapons are coming up)'
assert all(math.dist(last(w,0x667,team[k])[1:3],[20.,0.])<.1 for k in (0,2,3)),'weapons on the man'
steps(w,V,6)
assert [w.shared[b.SQ_T+i] for i in range(4)]==[hostile]*4 and w.shared[b.SQ_THREATS]==1 and 'SQXR' in w.messages,([w.shared[b.SQ_T+i] for i in range(4)],w.messages)
# guard 1 stands on the far side of CJ: CJ is in his line. He runs to his shield point WITHOUT firing; the other three fire.
o=last(w,0x5d3,team[1]);assert abs(o[1]-2.)<.01 and abs(o[2]+1.3)<.01 and o[4]==6 and not firing(w,team[1]),(o,firing(w,team[1]))
assert last(w,0x74d,team[2])[1]==hostile  # already within 1.4 m of his shield point (2, 1.3)
assert last(w,0x634,team[0])[1]==hostile and last(w,0x634,team[3])[1]==hostile
passed('Contact right: on the first look every guard turns his weapon on the man, 0.2-0.4 s later the brain lets three of them fire - the two who fight crouched and the shield already in place; the guard with CJ in his line runs to his shield point without firing')
w.pos[team[1]]=[2.,-1.3,0.];w.pos[team[2]]=[2.,1.3,0.];w.walk.clear();w.calls.clear();steps(w,V,14)
assert last(w,0x74d,team[1])[1]==hostile and last(w,0x74d,team[2])[1]==hostile,'both shields have a clear line from their spots now'
held=[k for k in range(4) if w.shared[b.SQ_BR_ST+k]==3]
assert held==[3] and not firing(w,team[3]) and math.dist(last(w,0x667,team[3])[1:3],[20.,0.])<.1,'the rear guard now has a shield in his line (and three rifles are on the man): weapon on him, no fire'
w.calls.clear();steps(w,V,8)
assert len(orders(w,0x634,team[0]))<=1 and len(orders(w,0x74d,team[1]))<=1 and len(orders(w,0x667,team[3]))<=2
assert not invariants(w)
passed('Shields fire from their spot; the guard who now has a mate in his line keeps his weapon on the man and holds his fire; orders are not restarted every tick')
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
assert all(t in w.exists and t not in w.released and t in w.wander and w.weapons[t]==0 for t in team) and w.shared[b.ESCORT_ON]==0 and not w.teleports and not w.handed,(w.messages,w.teleports,w.handed)
assert sorted(w.shared[b.LEAVE+k] for k in range(4))==sorted(team) and not invariants(w),invariants(w)
passed('The same in view: nobody vanishes on screen and nobody is handed to the game - the men put the guns away and walk off as ours (beta 4)')
w.onscreen=False;steps(w,V,4);assert all(t not in w.exists for t in team) and w.shared[b.LEAVE_N]==0
passed('...and they are removed once out of sight')
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
w.now=(w.now//3000+1)*3000+100;w.walk.clear();w.calls.clear();w.messages.clear();steps(w,V,8)
mover,cover=(team[0],team[1]) if (w.now//3000)%2==0 else (team[1],team[0])
(pt,shooting),g0=run_order(w,mover),w.pos[mover];step=min(math.dist(g0[:2],[20.,0.])-8.,6.)
assert math.dist(pt[:2],[20.,0.])<math.dist(g0[:2],[20.,0.]) and math.dist(pt[:2],g0[:2])<=6.05,(pt,g0)
assert fights(w,cover,hostile) and not [x for x in w.calls if x[1] in (0x637,0x5d3) and x[2][0]==cover],'his partner covers from where he is'
assert 'SQXR' in w.messages,w.messages
pt,shooting=run_order(w,team[2]);assert abs(pt[0]-20.)<.01 and abs(pt[1]+9.)<.01,pt
assert not [x for x in w.calls if x[1] in (0x637,0x5d3) and x[2][0]==team[3] and math.dist(x[2][1:3],[0.,0.])>8.],'the medic never leaves CJ to flank'
on=[k for k in range(4) if w.shared[b.SQ_BR_ST+k]==2];assert 2<=len(on)<=3 and not invariants(w),(on,invariants(w))
passed('Assault contact: one man bounds forward while his partner covers crouched, the flanker moves out, the medic stays with CJ - and of the four only those the brain lets (three rifles on one man at most) fire as they go')
w.now+=3000;w.calls.clear();steps(w,V,4)
assert [x for x in w.calls if x[1] in (0x637,0x5d3) and x[2][0]==cover] and fights(w,mover,hostile)
passed('Bounding overwatch: every 3 s the pair swaps who moves and who covers')
w.pos[team[2]]=[19.,-8.,0.];w.walk.clear();w.calls.clear();steps(w,V,8);assert fights(w,team[2],hostile) and not [x for x in w.calls if x[1] in (0x637,0x5d3) and x[2][0]==team[2]] and not invariants(w)
passed('A flanker who reached his flank point fights from there')
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
# The rules themselves are the brain's (brain/tests/test_fire.py tries each of them on its own). Here: the player's settings reach it, and
# the squad does what it says - a guard gets a firing task only with the brain's leave.
def roe(fire,typ=7,weapon=30,shooting=False,attacker=False,wanted=0,targeting=False,pos=(15.,0.,0.),facing=True,police=0,cj_fires=False):
 w,c,ground,sq,team=escort_world(fire=fire);V=(c,ground,sq);w.wanted=wanted;w.shared[b.POLICE]=police
 npc=960;w.exists.add(npc);w.pos[npc]=list(pos);w.pedtype[npc]=typ;w.weapons[npc]=weapon;w.civilians=[npc]
 w.actor_heading[npc]=(math.degrees(math.atan2(-(w.player[0]-pos[0]),w.player[1]-pos[1]))+(0. if facing else 180.))%360
 if shooting:w.shooting_chars.add(npc)
 if attacker:w.damage.add((1,npc))
 if targeting:w.targeting=npc
 if cj_fires:w.shooting=True
 steps(w,V,10);assert not invariants(w),invariants(w)
 return any(w.shared[b.SQ_T+k]==npc and w.shared[b.SQ_BR_ST+k]==2 and firing(w,team[k]) for k in range(4))
assert not roe(0,shooting=True) and not roe(0,attacker=True)
passed('HOLD FIRE: nobody of the squad fires, not even at a man who is shooting at CJ or has hurt him')
assert roe(3,shooting=True) and roe(3,attacker=True,weapon=0,typ=4) and roe(3) and not roe(3,facing=False) and not roe(3,weapon=0) and not roe(3,pos=(60.,0.,0.))
passed('PROTECT ME: whoever fires at CJ or has hurt him, and an armed gang member within 40 m who is turned to him; not one looking away, unarmed, or far off')
assert not roe(3,typ=8) and not roe(4,typ=8)
passed('Grove Street members are not engaged, armed and looking at CJ or not')
assert not roe(3,typ=6,wanted=0) and not roe(3,typ=6,wanted=2) and roe(3,typ=6,wanted=2,shooting=True) and not roe(3,typ=6,wanted=2,shooting=True,police=1)
passed('Police: nobody without stars; with stars only a policeman who has fired (POLICE: FIRE BACK), and none at all with POLICE: NEVER FIRE')
assert roe(2,targeting=True,cj_fires=True,weapon=0,typ=4) and not roe(2,attacker=True) and not roe(2,shooting=True)
passed('WHERE I SHOOT: the squad engages the man CJ is firing at, and nobody else - not even somebody shooting at him')
assert roe(4,facing=False) and not roe(4,typ=4,weapon=22,facing=False) and not roe(4,weapon=0,facing=False)
passed('ARMED ONLY: an armed gang member even with his back to CJ; never an armed civilian, never an unarmed man')
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
for who in [team[1],c.v[13],c.v[4]]:
 w.civilians=[who];w.damage.add((1,who));steps(w,V,6);assert who not in [w.shared[b.SQ_T+k] for k in range(4)] and not [x for x in w.calls if x[1] in FIRING] and not invariants(w)
passed('Teammates, the crew and the pilot are never threats')
# ------------------------------------------------------------------ the brain mod missing
w,c,ground,sq,team=escort_world();V=(c,ground,sq);asked=len(calls(w,0xe48));assert asked
w.brain=None;w.shared[b.BRAIN_HELLO]=0;hostile=950;w.exists.add(hostile);w.pos[hostile]=[20.,0.,0.];w.pedtype[hostile]=7;w.weapons[hostile]=30;w.damage.add((1,hostile));w.calls.clear();steps(w,V,12)
assert not calls(w,0xe48) and not [x for x in w.calls if x[1] in FIRING] and all(w.shared[b.SQ_T+k]==-1 for k in range(4))
w.player=[30.,0.,0.];w.calls.clear();steps(w,V,12);assert any(x[2][0] in team for x in calls(w,0x5d3)) and not calls(w,0xe48),'the squad still follows CJ in formation'
passed('The brain mod gone in mid-game: the squad never runs the opcode and never fires; it keeps its formation round CJ')
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
assert w.menu[7]==b'DEPLOY SQUAD',w.menu
w.events.append(6);w.step(c,p,n=4);assert w.menu[5]==b'SQUAD TACTICS: GUARD',w.menu
w.events.append(3);w.step(c,p,n=4);assert w.shared[b.TACTICS]==1 and w.menu[5]==b'SQUAD TACTICS: ASSAULT',w.menu
w.events.append(6);w.step(c,p,n=4);w.shared[b.ESCORT_ON]=1;w.step(c,p,n=4);assert w.menu[7]==b'RECALL SQUAD',w.menu
w.step(c,p,n=6);w.events.append(5);w.step(c,p,n=2);assert w.shared[b.CMD] in (17,0) and any(x[2]==[b.CMD,17] for x in calls(w,0xddc))
passed('Main menu: one row deploys / recalls the squad; SETTINGS switches GUARD / ASSAULT')
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

# ------------------------------------------------------------------ door gunners (1.3: every decision is the brain's)
fw=g['fire_world'];threaten=g['threaten'];attacks=g['attacks'];hit=g['hit'];aims=g['aims']
def gunner_world(npcs,attack=True,typ=7):
 w,c,f=fw();w.civilians=[]
 for npc,x,y in npcs:
  w.exists.add(npc);w.pos[npc]=[x,y,0.];w.skin[npc]=102;w.pedtype[npc]=typ;w.weapons[npc]=30;w.health[npc]=100000;w.civilians.append(npc)
  if attack:w.damage.add((1,npc))
 return w,c,f
def rounds_by(w):
 """Who of the gunners let rounds go at whom."""
 d={}
 for r in w.brain.rounds:
  if r.verdict==0 and r.ray:d.setdefault(r.who,set()).add(r.target)
 return d
# The helicopter hangs south of CJ, nose to the north-west: its right door looks north (towards CJ), its left door south.
w,c,f=gunner_world([(910,20.,10.),(911,-10.,-95.)]);w.step(c,f,n=25)
R,L=[w.shared[b.PUB+3],w.shared[b.PUB+5]],[w.shared[b.PUB+4],w.shared[b.PUB+6]];by=rounds_by(w)
assert all(by.get(x)=={910} for x in R) and all(by.get(x)=={911} for x in L) and hit(w)=={910,911} and not invariants(w),(by,invariants(w))
passed('Door gunners take a man on their own side - right door right, left door left - and never fire across the cabin')
w,c,f=gunner_world([(910,20.,10.)]);g3=w.coords(w.shared[b.PUB+3]);w.los_fn=lambda a,z:math.dist(a,g3)>1.;w.step(c,f,n=25);by=rounds_by(w)   # something hides the man from the front seat of the right door
assert w.shared[b.PUB+3] not in by and by.get(w.shared[b.PUB+5])=={910} and not by.keys()&set([w.shared[b.PUB+4],w.shared[b.PUB+6]]),by
assert [r for r in w.brain.rounds if r.who==w.shared[b.PUB+3]]==[],'no round is even asked for: the brain knows he cannot see the man'
passed('A gunner without a clear line from his seat does not fire; the other gunner in that door does')
w,c,f=gunner_world([(900,15.,12.),(901,-12.,14.),(902,12.,30.)]);w.step(c,f,n=30);by=rounds_by(w)
assert set(by)==set(R) and all(len(v)==1 for v in by.values()) and by[R[0]]!=by[R[1]],by
passed('Three attackers and two gunners who can see them: each gunner stays on a man of his own (no hopping from man to man, no doubling up while there is a man nobody is on)')
n0={who:len([r for r in w.brain.rounds if r.who==who and r.verdict==0 and r.ray]) for who in R};w.exists.add(903);w.pos[903]=[25.,20.,0.];w.pedtype[903]=7;w.weapons[903]=30;w.health[903]=100000;w.damage.add((1,903));w.step(c,f,n=15)
later={who:{r.target for r in w.brain.rounds[-200:] if r.who==who and r.verdict==0 and r.ray and r.time>w.now-800} for who in R}
assert all(later[who]==by[who] for who in R),(later,by)
passed('A gunner finishes the man he started on instead of hopping to a newer one')
# every round against the hard rules, by the world itself: nothing within 2 m of CJ, nothing within 1 m of ours
w,c,f=gunner_world([(900,1.2,.5),(901,-1.,1.)]);w.step(c,f,n=30)
assert not attacks(w) and not invariants(w) and (aims(w,900) or aims(w,901)),('attackers at arm\'s length of CJ: weapons on them, not one round',len(attacks(w)),invariants(w))
w.pos[900]=[3.4,1.,0.];w.step(c,f,n=30);near=len(attacks(w));assert not invariants(w),invariants(w)     # 3.5 m from CJ: a round may go only when its scattered line still keeps 2 m from him
w.pos[900]=[14.,8.,0.];w.step(c,f,n=15);assert hit(w)=={900} and len(attacks(w))>near and not invariants(w),(hit(w),invariants(w))
passed('Attackers at arm\'s length of CJ are not fired at from the helicopter (no round may pass within 2 m of him): weapons on them only; 3.5 m from him only the rounds whose line keeps the 2 m go; clear of CJ the man is engaged fully (%d rounds in 3 s at 3.5 m, every one checked by the world itself)'%near)
w,c,f=gunner_world([(900,20.,10.)]);w.step(c,f,n=12);n=len(attacks(w));assert n
w.player=[19.,9.,0.];w.step(c,f,n=10);assert len(attacks(w))==n and not invariants(w),'CJ walks up to the man: fire stops with the next round'
w.player=[0.,0.,0.];w.step(c,f,n=10);assert len(attacks(w))>n
passed('CJ walks into the line of fire: the gunners stop with the very next round, and go on when he is clear again')
# ------------------------------------------------------------------ WHERE I SHOOT
def follow_world(npcs,typ=4):
 w,c,f=fw();w.shared[b.FIRE]=2;w.civilians=[]
 for npc,x,y in npcs:w.exists.add(npc);w.pos[npc]=[x,y,0.];w.skin[npc]=20;w.pedtype[npc]=typ;w.health[npc]=100000;w.civilians.append(npc)
 w.step(c,f,n=3);return w,c,f
w,c,f=follow_world([(940,30.,10.),(941,-25.,15.)]);w.damage.add((1,941));w.weapons[941]=30;w.step(c,f,n=12)
assert not attacks(w) and aims(w,941) and not aims(w,940),'nobody is fired at until CJ fires at him - the man who has hurt CJ is covered (weapons on him), no more'
pulses=0
for k in range(40):                       # single shots: the firing flag is up for one frame in five
 w.shooting=(k%5==0);w.cj_aim=[30.,10.,0.];w.step(c,f)
w.shooting=False;first=[x[0] for x in attacks(w)]
assert hit(w)=={940} and first and max(b_-a_ for a_,b_ in zip(first,first[1:]))<1500 and not invariants(w),(hit(w),first[:5])
passed('WHERE I SHOOT: single shots of CJ keep the gunners on the man he is firing at (free aim, no lock-on needed), without long gaps; the man who hurt CJ is left to him')
n=len(attacks(w));w.step(c,f,n=45);n2=len(attacks(w));w.step(c,f,n=10);assert len(attacks(w))==n2 and n2-n<25,(n,n2)
passed('WHERE I SHOOT: about three seconds after CJ\'s last shot the gunners stop too')
w,c,f=follow_world([(940,30.,10.)]);w.shooting=True;w.cj_aim=[0.,200.,40.];w.step(c,f,n=20);assert not attacks(w)
passed('WHERE I SHOOT: CJ fires into the sky or at a wall - there is no man on his line, so no rounds are wasted')
w,c,f=follow_world([(940,30.,10.)]);guard=941;w.exists.add(guard);w.pos[guard]=[1.,1.,0.];w.pedtype[guard]=8;w.weapons[guard]=31;w.shared[b.GROUND_PUB]=guard
w.shot_at={guard:[30.,10.,0.]};w.shooting_chars={guard};w.step(c,f,n=20);assert not attacks(w),'the guard beside CJ fires at the man: that is not CJ\'s fire'
passed('WHERE I SHOOT: a guard firing next to CJ (CJ not shooting) does not start the gunners')
car=777;w,c,f=follow_world([(940,40.,0.)]);w.exists.add(car);w.cars[car]={'pos':[40.,0.,0.],'heading':0.};w.model[car]=400;w.incar[940]=car;w.seats[(car,-1)]=940;w.health[car]=1000
w.shooting=True;w.cj_aim=[40.,2.,0.];w.step(c,f,n=20);w.shooting=False
assert {r.target for r in w.brain.rounds if r.verdict==0}=={940} and not invariants(w),'the man at the wheel'
passed('WHERE I SHOOT: CJ fires at a car - the gunners fire at the man in it')
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
w,c,f=gunner_world([(970,70.,0.)],attack=False);w.actor_heading[970]=0.;w.messages.clear();w.shot_at={970:list(w.car)};w.shooting_chars={970}
w.step(c,f,n=6);w.shooting_chars=set()
assert w.shared[b.EVADE_UNTIL]>w.now and 'HCSHOT' in w.messages,(w.shared[b.EVADE_UNTIL],w.now,w.messages)
passed('Rounds fired at the helicopter make the pilot break away at once, before the hull is damaged (the brain reports them; the bullet traces are no longer read)')
w,c,f=gunner_world([(970,60.,-45.)]);w.step(c,f,n=20);assert attacks(w),'the gunners are firing'
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
assert w.shared[b.SQ_T]==980 and 981 not in [w.shared[b.SQ_T+i] for i in range(4)] and 'SQXR' in w.messages,([w.shared[b.SQ_T+i] for i in range(4)],w.messages)
w.shot_at={981:[1.5,-1.,.5]};w.shooting_chars={981};w.calls.clear();steps(w,V,45);w.shooting_chars=set()
men=[w.shared[b.SQ_T+i] for i in range(4)];assert {980,981}<=set(men) and any(fights(w,t,981) for t in team) and any(fights(w,t,980) for t in team) and not invariants(w),(men,w.messages,invariants(w))
passed('Squad: a second man opens fire on CJ from 40 m on the other side - the brain puts a guard on him as well, and both men are fought')
w,V,team=squad_scene([(982,0.,-25.,34,True)]);w.messages.clear();steps(w,V,8)
assert 'SQSB' in w.messages,w.messages
w,V,team=squad_scene([(983,22.,0.,30,True)]);w.pos[983][2]=9.;w.messages.clear();steps(w,V,8)
assert 'SQRR' in w.messages,w.messages
passed('Squad call-outs name the kind of threat and where: "Sniper - rear!", "Shooter on the roof - right!"')
w,V,team=squad_scene([(990,0.,20.,30,True)]);w.shooting_chars.add(990)
def low_wall(a,z):return not(abs(z[0]-3.5)<.1 and abs(z[1]-3.2)<.1 and z[2]<1.)
w.los_fn=low_wall;w.messages.clear();steps(w,V,10)
pt,shooting=run_order(w,team[0]);assert abs(pt[0]-3.5)<.01 and abs(pt[1]-3.2)<.01,pt
assert w.shared[b.CV_OK]==1  # the 'taking cover' chatter itself is dropped while 'CONTACT' is on screen
w.pos[team[0]]=[3.5,3.2,0.];w.walk.clear();steps(w,V,8)
assert last(w,0x634,team[0])[1]==990 and w.shared[sqb.fk(0,'TASK')]==8 and not invariants(w)
passed('Under fire an engager moves to low cover (blocks the chest, not the head) and fights crouched from there')
w,V,team=squad_scene([(991,0.,20.,30,True)]);w.shooting_chars.add(991);w.messages.clear();steps(w,V,10)
assert fights(w,team[0],991) and not [x for x in w.calls if x[1] in (0x637,0x5d3) and x[2][0]==team[0] and x[0]>w.now-500] and 'SQCVR' not in w.messages,'no cover nearby: fight crouched where he stands'
passed('Without cover nearby the engager fights crouched where he stands')
w.calls.clear();steps(w,V,130)
ducks=[x for x in w.calls if x[1]==0x4eb and x[2][1]==1 and x[2][0] in team];who={x[2][0] for x in ducks}
assert ducks and 'SQRLD' in w.messages and len(who)>=2,(len(ducks),who)
assert not calls(w,0x5c5),'beta 6: never TASK_DUCK - it plays the scared "cower" pose; the drill uses the weapon crouch (04EB)'
steps(w,V,25)
for g_ in who:   # ... and every guard who went down for the drill is told to get up again
 ups=[x[0] for x in w.calls if x[1]==0x4eb and x[2]==[g_,0]];downs=[x[0] for x in ducks if x[2][0]==g_];assert ups and max(ups)>min(downs),(g_,downs,ups)
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
assert fights(w,team[0],995) and sum(1 for t in team if firing(w,t))>=2 and not invariants(w)
passed('After 20 s of quiet the team lowers its weapons; the first threat puts them back on alert')

# ------------------------------------------------------------------ 1.1: v41 details completed
def car_attack(hp,x=24.):
 w,c,f=gunner_world([]);drv,car=962,963;w.exists.update({drv,car});w.cars[car]={'pos':[x,6.,0.],'heading':90.};w.model[car]=400;w.incar[drv]=car
 w.traffic=[car];w.seats[(car,-1)]=drv;w.pedtype[drv]=7;w.skin[drv]=102;w.weapons[drv]=30;w.health[drv]=100000;w.damage.add((1,drv));w.health[car]=hp;w.calls.clear();w.step(c,f,n=30);return w,c,f,car,drv
w,c,f,car,drv=car_attack(1000)
aimed=[(r.to.x,r.to.y,r.to.z) for r in w.brain.rounds if r.verdict==0 and r.ray];assert calls(w,0x6bc) and aimed and all(abs(t[0]-24.)<1.05 and abs(t[1]-6.)<1.05 and abs(t[2]-.2)<1.05 for t in aimed) and {r.target for r in w.brain.rounds}=={drv} and not invariants(w),aimed[-4:]
passed('A man in a car: every round is aimed at him (scattered by up to a metre at 60 m from a moving helicopter), never at the engine or the tank - the gunners do not blow cars up')
# a damaged car within 18 m of CJ is left alone: it could blow up beside him
w,c,f,car,drv=car_attack(1000,x=12.);assert calls(w,0x6bc)
w.calls.clear();w.health[car]=b.CAR_HOLD_HP-1;w.step(c,f,n=3);n=len(calls(w,0x6bc));w.step(c,f,n=30)
assert len(calls(w,0x6bc))==n and n<=2 and aims(w,drv),'no round within 0.3 s of the car dropping below the floor; the weapons stay on the man'
w,c,f,car,drv=car_attack(b.CAR_HOLD_HP-1,x=12.);assert not calls(w,0x6bc)
w.incar.pop(drv);w.pos[drv]=[12.,6.,0.];w.calls.clear();w.step(c,f,n=30);assert calls(w,0x6bc) and hit(w)=={drv},'the same man on foot is a target again'
w,c,f,car,drv=car_attack(b.CAR_HOLD_HP-1,x=40.);assert calls(w,0x6bc),'40 m from CJ the same damaged car may be stopped by fire'
passed('A car below %d health within 18 m of CJ is not fired at (it burns below 250): no rounds, weapons on the man only - he is engaged again once he is out of it; far from CJ the same car may be fired at'%b.CAR_HOLD_HP)
# ------------------------------------------------------------------ beta 6: PROTECT CJ is close protection, not a gang war
def protect(typ=7,weapon=30,x=20.,facing=True,wanted=0,in_car=False,skin=20,hurt=False,frames=30,turn=0.,shoots=False):
 w,c,f=fw();w.civilians=[];npc=900;w.exists.add(npc);w.pos[npc]=[x,0.,0.];w.skin[npc]=skin;w.pedtype[npc]=typ;w.civilians.append(npc);w.wanted=wanted
 w.weapons[npc]=weapon;threaten(w,npc,weapon=weapon)
 if not facing:turn=120.
 w.actor_heading[npc]=(w.actor_heading[npc]+turn)%360
 if in_car:car=963;w.exists.add(car);w.cars[car]={'pos':[x,0.,0.],'heading':90.};w.model[car]=400;w.incar[npc]=car;w.traffic=[car];w.seats[(car,-1)]=npc
 if hurt:w.damage.add((1,npc))
 if shoots:w.shooting_chars.add(npc)
 w.calls.clear();w.step(c,f,n=frames);assert not invariants(w),invariants(w);return bool(attacks(w)),w
assert protect()[0],'control: an armed gang member on foot, 20 m away, turned to CJ'
assert not protect(weapon=0)[0],'a gang member with empty hands is nobody\'s target'
assert not protect(weapon=5)[0],'nor one with a bat: no firearm, no pre-emptive fire'
assert not protect(facing=False)[0],'armed but walking away: not a threat yet'
assert protect(turn=b.THREAT_FACING_DEG-10)[0] and protect(turn=10-b.THREAT_FACING_DEG)[0] and not protect(turn=b.THREAT_FACING_DEG+15)[0] and not protect(turn=-b.THREAT_FACING_DEG-15)[0],'turned to CJ = within 40 degrees either way'
assert not protect(x=b.THREAT_NEAR_M+15.)[0],'armed and looking this way from 55 m: too far to call it imminent'
assert not protect(in_car=True)[0],'gang members driving past are left alone (this is what blew cars up beside CJ)'
assert protect(in_car=True,hurt=True)[0],'... until they attack'
assert not protect(typ=4)[0] and not protect(typ=4,wanted=3)[0],'an armed civilian is not a hostile type, wanted level or not'
assert protect(typ=4,hurt=True)[0],'... but anybody who has hurt CJ is a target'
assert not protect(typ=6,weapon=22,wanted=0)[0],'police without a wanted level'
assert not protect(typ=6,weapon=22,wanted=1)[0] and protect(typ=6,weapon=22,wanted=1,shoots=True)[0],'an armed policeman turned to a wanted CJ is covered; he is fired at once he fires (POLICE: FIRE BACK)'
assert not protect(typ=6,weapon=3,wanted=2)[0],'a policeman with a nightstick is left to CJ (until he hits him)'
assert not protect(typ=6,weapon=22,wanted=3,in_car=True)[0],'police cars are not fired at just because CJ is wanted'
assert not protect(typ=8)[0] and not protect(typ=8,skin=105)[0],'Grove never'
passed('PROTECT ME engages threats only: whoever hurt CJ, or an armed gang member on foot within %d m and turned to CJ (40 degrees either way) - not passers-by, not armed civilians, not cars driving past, not policemen who have not fired'%b.THREAT_NEAR_M)
for mode in (0,2,3,4):
 w,c,f=fw();w.shared[b.FIRE]=mode;w.wanted=3;w.calls.clear();w.step(c,f,n=20)
 assert not [x for x in calls(w,0x77a) if x[2][1]==4],(mode,[x[2] for x in calls(w,0x77a) if x[2][1]==4][:3])
passed('No fire mode makes the gunners hate a ped type any more: the game\'s own AI cannot open fire on a car by itself, every target comes from the rules')
# an attacker at CJ's elbow: not one round from the helicopter; the moment CJ is clear of him the gunners fire
w,c,f=fw();w.civilians=[];npc=900;w.exists.add(npc);w.pos[npc]=[0.,1.5,0.];w.skin[npc]=102;w.pedtype[npc]=7;w.health[npc]=100000;w.civilians.append(npc);w.damage.add((1,npc));w.calls.clear();w.step(c,f,n=50)
assert not calls(w,0x6bc) and aims(w,npc) and not invariants(w),(len(calls(w,0x6bc)),invariants(w))
w.player=[0.,-25.,0.];w.calls.clear();w.step(c,f,n=40);assert calls(w,0x6bc) and hit(w)=={npc} and not invariants(w),'CJ has stepped away from him: fire'
passed('An attacker 1.5 m from CJ: no round from the helicopter, the weapons stay on him; they fire once CJ is %.0f m clear of the line'%b.CJ_LINE_CLEAR_M)
# WHERE I SHOOT at an empty car: there is no man to fire at
w,c,f=gunner_world([]);w.shared[b.FIRE]=2;car=963;w.exists.add(car);w.cars[car]={'pos':[24.,0.,0.],'heading':90.};w.model[car]=400;w.traffic=[car]
w.shooting=True;w.cj_aim=[24.,0.,1.];w.step(c,f,n=30);assert not attacks(w)
passed('WHERE I SHOOT: CJ shooting up an empty car gets no help - the gunners never shoot cars, only the men in them')
# a burning car beside CJ is called out
def burning(hp,x,dead=False):
 w,c,f=fw();car=963;w.exists.add(car);w.cars[car]={'pos':[x,3.,0.],'heading':90.};w.model[car]=400;w.traffic=[car];w.health[car]=hp
 if dead:w.dead.add(car)
 w.messages.clear();w.step(c,f,n=20);return w.messages.count('HCBURN'),w,c,f
assert burning(b.BURN_HP-50,5.)[0]==1,'a car on fire 6 m from CJ: said once'
assert burning(b.BURN_HP+50,5.)[0]==0 and burning(b.BURN_HP-50,30.)[0]==0 and burning(0,5.,dead=True)[0]==0,'not for a healthy car, a far one or a wreck'
n,w,c,f=burning(b.BURN_HP-50,-5.);w.step(c,f,n=30);assert w.messages.count('HCBURN')==2,'repeated every 4 s while it burns'
passed('A burning car within %d m of CJ is called out ("CAR ON FIRE! Get away from it."), whoever set it on fire; repeated every 4 s, not for wrecks'%b.BURN_WARN_M)
w,c,f=fire_world();npc=target(w,typ=7,skin=20);w.pos[npc]=[40.,0.,0.];w.damage.add((1,npc));w.step(c,f,n=12)
for _ in range(20):
 w.step(c,f);m=calls(w,0x4a2)[-1][2];assert abs(math.dist(m[1:3],[28.,0.])-b.ORBIT_RADIUS)<.5,m
passed('Threat 40 m from CJ: the orbit centre moves 30% towards CJ so the gunners cover both')
w,V,team=squad_scene([(997,0.,20.,30,True)]);steps(w,V,10)
assert sum(1 for t in team if firing(w,t))>=2
w.los_fn=lambda a,z:False;w.calls.clear();steps(w,V,30)        # he slips out of everybody's sight
assert not [x for x in w.calls if x[1] in FIRING and x[0]>w.now-2800] and not calls(w,0x668) and any(orders(w,0x667,t) for t in team) and not invariants(w)
w.los_fn=lambda a,z:True;w.calls.clear();steps(w,V,12);assert firing(w,team[0]) and not invariants(w),'the front guard has a clear line again (the shields behind him and the rear guard have a mate or CJ in theirs: they hold)'
passed('A man who slips out of sight: within 0.2 s nobody fires at him or at the place he was (nobody checks a line to a place) - weapons stay up - and the fight goes on when he shows himself')
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
w,V,team=squad_scene([(985,20.,0.,30,False)]);w.actor_heading[985]=90.;w.health[985]=100000;w.shared[b.MSG_PRIO]=3;w.shared[b.MSG_UNTIL]=w.now+8000;w.shared[b.MSG_HOLD]=w.now+1200;w.messages.clear();steps(w,V,10)
assert not w.messages,('nothing lesser for the first 1.2 s of an alarm',w.messages)
w,V,team=squad_scene([(985,20.,0.,30,False)]);w.actor_heading[985]=90.;w.health[985]=100000;w.shared[b.MSG_PRIO]=3;w.shared[b.MSG_UNTIL]=w.now+8000;w.shared[b.MSG_HOLD]=0;w.messages.clear();steps(w,V,10)
assert w.messages and all(b._mv.PRIO.get(k_,2)>=2 for k_ in w.messages),w.messages
w.shared[b.MSG_PRIO]=3;w.shared[b.MSG_UNTIL]=w.now+20000;w.messages.clear();steps(w,V,120);assert 'SQRLD' not in w.messages,w.messages
w.shared[b.MSG_PRIO]=1;w.shared[b.MSG_UNTIL]=0;steps(w,V,100);assert 'SQRLD' in w.messages,w.messages
passed('An alarm on screen: nothing lesser for 1.2 s, then a tactical call may take its place but never chatter; chatter comes back once the line is free')
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
assert 'SQXR' in w.messages and 'HCCONT' not in w.messages,w.messages
passed('With the team on the ground only the squad calls the contact (no double "CONTACT!")')
w,c,p=setup(True);launch=VM('Helicover',w);w.step(c,p,launch,n=15);w.events.append(1);w.step(c,p,n=4)
rows=[]
for _ in range(4):rows.append(w.menu[6]);w.events.append(4);w.step(c,p,n=4)
assert rows==[b'MESSAGES: ALL',b'MESSAGES: IMPORTANT',b'MESSAGES: OFF',b'MESSAGES: ALL'],rows
passed('SETTINGS: one row cycles MESSAGES: ALL / IMPORTANT / OFF')
# ------------------------------------------------------------------ v41 frame cost
def cost_of(vm,fn):
 """(peak, average) script instructions per frame of one worker while fn runs."""
 orig=vm.run;costs=[]
 def run():
  n0=len(vm.w.calls);orig();costs.append(len(vm.w.calls)-n0)
 vm.run=run;fn();vm.run=orig;return max(costs),sum(costs)//len(costs)
w,c,f=gunner_world([(900+i,x,y) for i,(x,y) in enumerate([(20,8),(-20,8),(8,20),(-8,-70),(12,14),(-12,14),(4,22),(4,-80)])])
w.frame_ms=33
def fire_run():
 for k in range(300):
  w.shooting_chars={900+k%8};w.step(c,f)
fpeak,favg=cost_of(f,fire_run);assert len(attacks(w))>=40 and not invariants(w),(len(attacks(w)),invariants(w))
w,V,team=squad_scene([(980+i,x,y,30,True) for i,(x,y) in enumerate([(20,0),(-20,0),(0,20),(0,-20),(14,14),(-14,-14)])])
for n in range(980,986):w.shooting_chars.add(n)
w.frame_ms=33
def squad_run():steps(w,V,300)
speak,savg=cost_of(V[2],squad_run);assert not invariants(w)
assert fpeak<=700 and favg<=350 and speak<=2000 and savg<=500,(fpeak,favg,speak,savg)
passed('Frame cost in a busy fight at 30 fps (8 attackers, 10 s): fire worker peak %d / average %d script instructions a frame (it was up to 3600 when it searched for targets itself), squad worker peak %d / average %d'%(fpeak,favg,speak,savg))

text='\n'.join(results)+'\nMocked script execution only: real pathing, cover and gunfire are not tested.\n'
(b.OUT/'squad_tests.txt').write_text(text);print(text)
