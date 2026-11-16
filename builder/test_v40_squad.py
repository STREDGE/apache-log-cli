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
import brain_mock
_brain=brain_mock.h.Brain();_cfg=_brain.cfg          # the thresholds are the brain's own now (they used to be constants of the fire script)
class CFG:car_floor=int(_cfg.car_floor);near_m=float(_cfg.near_m);cj_line_m=float(_cfg.cj_line_m);facing_cos=float(_cfg.facing_cos)
FACING_DEG=round(math.degrees(math.acos(CFG.facing_cos)))
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
import build_v25_ground as gb
assert [last(w,0x1b2,t)[1] for t in team]==[wp for wp,_ in gb.TEAM_WEAPONS] and [w.skin.get(t) for t in team]==gb.TEAM_MODELS,([last(w,0x1b2,t) for t in team],[w.skin.get(t) for t in team])
passed('TEAM ON FOOT: four armed guards rope down next to CJ - the commander a soldier (287) with an M4, then agents in black with an MP5, an M4 and an AK (fixed, by role) - then the helicopter resumes FOLLOW')
# ------------------------------------------------------------------ 1.4: the protective detail. The brain gives every guard his post
# (where, how fast, standing or crouched, where to look); the squad worker is the body: it goes there, crouches, aims and fires.
BG=[(0,3.2),(-2.4,.6),(2.4,.6),(0,-2.8)]   # where the team stands after the drop
import hcb_py as H
def posts(w):return w.brain.posts()
def spot(p):return [p.at.x,p.at.y]
FIRING=(0x74d,0x634,0x637,0x7a5,0x668)
def firing(w,who):return [x for x in w.calls if x[1] in FIRING and x[2][0]==who]
def run_order(w,who):
 """His last run order: (point, firing as he runs). With the brain's leave he runs firing (0637), without it he just runs (05D3)."""
 o=[(x[1],x[2]) for x in w.calls if x[1] in (0x637,0x5d3) and x[2][0]==who];assert o,who;op,v=o[-1];return v[1:4],op==0x637
def fights(w,who,man):
 """He is on that man: a firing task at him, or - when the brain holds his fire - his weapon on him."""
 f=[x for x in firing(w,who) if man in x[2][1:8]];return bool(f) or any(math.dist(x[2][1:3],w.coords(man)[:2])<.5 for x in w.calls if x[1]==0x667 and x[2][0]==who)
for t in team:w.pos[t]=[0.,-20.,0.]
w.walk.clear();w.calls.clear();steps(w,V,3)
P_=posts(w);assert set(P_)==set(team),(P_.keys(),team)
for t in team:
 o=last(w,0x5d3,t);assert math.dist(o[1:3],spot(P_[t]))<.6 and o[4] in (6,7),(t,o,spot(P_[t]))   # running or sprinting from afar
jobs={H.HCB_ROLE_LEAD:'lead',H.HCB_ROLE_CLOSE:'close',H.HCB_ROLE_POINT:'point',H.HCB_ROLE_REAR:'rear',H.HCB_ROLE_CLOSE2:'close2',H.HCB_ROLE_CLOSE3:'close3',H.HCB_ROLE_POINT2:'point2',H.HCB_ROLE_MARKSMAN:'delta'}
J={jobs[p.job]:p for p in P_.values()}
assert J['lead'].who==team[0] and J['close'].who==team[1] and math.dist(spot(J['lead']),(0.,0.))<1.6 and math.dist(spot(J['point']),(0.,0.))>8 and all(1.5<math.dist(spot(J[k]),(0.,0.))<3.2 for k in ('close','close2')),{k:spot(v) for k,v in J.items()}
passed('Peace: each guard goes to the post the brain gives him - the commander at CJ\'s side, two bodyguards a couple of metres behind him, the fourth man out at 10 m - sprinting from afar')
for t in team:w.pos[t]=[spot(P_[t])[0],spot(P_[t])[1]-6.,0.]
w.walk.clear();w.calls.clear();w.now+=1600;steps(w,V,2)
assert all(last(w,0x5d3,t)[4]==6 for t in team),[last(w,0x5d3,t)[4] for t in team]
for t in team:w.pos[t]=[spot(P_[t])[0],spot(P_[t])[1]-2.,0.]
w.walk.clear();w.calls.clear();w.now+=1600;steps(w,V,2)
assert all(last(w,0x5d3,t)[4]==4 for t in team if not posts(w)[t].stuck or posts(w)[t].job!=H.HCB_ROLE_POINT),[last(w,0x5d3,t)[4] for t in team]   # (the outer man was held back twice by this test: the brain has turned his post, he runs to the new one)
passed('Running to a post 6 m away, walking to one 2 m away (the pace comes with the post)')
w.calls.clear();steps(w,V,20)
assert all(len(orders(w,0x5d3,t))<=4 for t in team),[len(orders(w,0x5d3,t)) for t in team]
passed('Move orders are renewed at most every 1.5 s, or when the post moves more than a metre - not every tick')
w.now+=5000;steps(w,V,3)   # (CJ has stood still a while: the outer men have their posts on the approaches)
for t in team:w.pos[t]=[spot(posts(w)[t])[0],spot(posts(w)[t])[1],0.]
for k in range(4):w.shared[sqb.fk(k,'TASK')]=16   # standing at ease already (no walk order of his own left to keep)
w.walk.clear();w.calls.clear();w.now+=1600;steps(w,V,3)
assert not any(orders(w,0x5d3,t) or orders(w,0x637,t) or orders(w,0x667,t) or firing(w,t) for t in team),'at his post in peace: no move order, no weapon raised'
passed('At his post in peace each guard stands at ease: no needless orders, no weapon raised at nobody')
# ------------------------------------------------------------------ contact: no cover near
for t in team:w.pos[t]=[spot(posts(w)[t])[0],spot(posts(w)[t])[1],0.]
hostile=950;w.exists.add(hostile);w.pos[hostile]=[20.,0.,0.];w.pedtype[hostile]=7;w.weapons[hostile]=30;w.health[hostile]=100000;w.civilians=[hostile];w.damage.add((1,hostile))
w.walk.clear();w.calls.clear();w.messages.clear();steps(w,V,1)
assert not [x for x in w.calls if x[1] in FIRING],'the first look: nobody has leave to fire yet (weapons are coming up)'
steps(w,V,25)
P_=posts(w);J={jobs[p.job]:p for p in P_.values()}
assert J['close'].duty==H.HCB_DUTY_SHIELD and math.dist(spot(J['close']),[1.3,0.])<.4,('the bodyguard: between CJ and the shooter',spot(J['close']))
assert any(fights(w,t,hostile) for t in team) and not invariants(w),invariants(w)
assert any(m.startswith('SQME') for m in w.messages),('no cover near: "stay by your guard, fall back"',w.messages)
assert 'SQXR' in w.messages,'the contact call names the kind of threat and the side'
passed('Contact, no cover near: the bodyguard puts himself between CJ and the shooter, the team fights, the commander tells CJ to stay by his guard; the contact call names the side')
# ------------------------------------------------------------------ contact with cover: the commander sends CJ there and marks it
w2,V2,team2=None,None,None
w2_c=escort_world();w2,c2,ground2,sq2,team2=w2_c;V2=(c2,ground2,sq2)
for t in team2:w2.pos[t]=[0.,-2.,0.]
w2.blockers=[([-3.,0.,1.],1.2)]                       # a pillar 3 m west of CJ: the shade behind it is hidden from a man in the east
h2=951;w2.exists.add(h2);w2.pos[h2]=[20.,0.,0.];w2.pedtype[h2]=7;w2.weapons[h2]=30;w2.health[h2]=100000;w2.civilians=[h2];w2.damage.add((1,h2))
w2.messages.clear();steps(w2,V2,25)
o=w2.brain.out
assert o.cover_ok and o.cover_at.x<-3.5 and abs(o.cover_at.y)<1.5,(o.cover_ok,o.cover_at.x,o.cover_at.y)
assert any(m.startswith('SQGO') for m in w2.messages),('"CJ, into cover - <side>! Go to the mark."',w2.messages)
w2.player=[o.cover_at.x,o.cover_at.y,0.];w2.pos[1]=list(w2.player);w2.messages.clear();steps(w2,V2,25)
P2=posts(w2);J2={jobs[p.job]:p for p in P2.values()}
assert 'SQSAFE' in w2.messages and not w2.brain.out.cover_ok,('"CJ is in cover, we hold"; the mark goes',w2.messages)
assert J2['close'].crouch and any(x[2]==[J2['close'].who,1] for x in calls(w2,0x4eb)),'the bodyguard crouches beside him'
crouched=[x for x in w2.calls if x[1]==0x634]
assert crouched and not invariants(w2),'from cover they fight crouched (the game\'s own duck-and-fire)'
passed('Contact with a pillar 3 m away: the commander tells CJ which way to go ("into cover - left!") and the spot is marked; there: "CJ is in cover, we hold", the bodyguard crouches beside him, the team fights crouched from cover')
# ------------------------------------------------------------------ too hot: a ring and the pickup call
w2.health[1]=20;w2.messages.clear();steps(w2,V2,8)
P2=posts(w2);lead_=w2.brain.out.lead
D2_=sorted(math.dist(spot(p),w2.coords(1)[:2]) for p in P2.values());assert all(x<=5.1 for x in D2_[:-1]) and 7.5<=D2_[-1]<=12.5 and w2.messages.count('SQEVAC')==1,([spot(p) for p in P2.values()],w2.messages)   # (0.9: the commander and the bodyguards come in, the outer man holds 8-12 m off)
steps(w2,V2,60);assert w2.messages.count('SQEVAC')==1
passed('CJ badly hurt under fire: everybody comes in round him (within 5 m) and "too hot - call ROPE PICKUP", once (not again for 20 s)')
w2.health[1]=100;w2.dead.add(h2);w2.messages.clear();w2.now+=30000;steps(w2,V2,6);w2.now+=30000;steps(w2,V2,6);w2.now+=30000;steps(w2,V2,6)
assert w2.messages.count('SQCLR')==1,w2.messages
passed('The shooter down and quiet: "area secure, regrouping on CJ", once')
# ------------------------------------------------------------------ no medic (the user's decision: maybe later)
w.dead.add(hostile);w.health[1]=50;w.messages.clear();w.now+=60000;steps(w,V,30)
assert w.health[1]==50
passed('No medic for now (the user\'s decision): nobody patches CJ up')
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
# the commander's words: only what he says after the scripts have started (the first look takes the number without saying it)
w.messages.clear();w.shared[b.SQ_SAY_SEQ]=-1;w.brain.say=(7,1,0);steps(w,V,4)
assert w.shared[b.SQ_SAY_SEQ]==7 and not [m_ for m_ in w.messages if m_.startswith('SQGO')],('an old word is not said at the start',w.messages)
w.brain.say=(8,1,1);steps(w,V,3);assert w.messages.count('SQGOR')==1,w.messages
steps(w,V,10);assert w.messages.count('SQGOR')==1,'said once'
passed('The commander\'s words are said once each, when new; a word from before the scripts started is not said')
# ------------------------------------------------------------------ 1.4.1: eight on the ground
w8,c8,ground8,sq8,team8=escort_world();t2=VM('Helicover_Team2',w8);sq2=VM('Helicover_Squad2',w8);V8=(c8,ground8,sq8,t2,sq2)
steps(w8,V8,4);assert all(w8.shared[b.GROUND_PUB2+i]==-1 for i in range(4)),'not before the first four are clear of the ropes'
steps(w8,V8,40)
extra=[w8.shared[b.GROUND_PUB2+i] for i in range(4)]
import build_v25_team2 as t2b
assert all(x in w8.exists for x in extra) and len(set(extra))==4 and [w8.skin[x] for x in extra]==t2b.MODELS,(extra,[w8.skin.get(x) for x in extra])
assert [last(w8,0x1b2,x)[1] for x in extra]==[wp for wp,_ in t2b.WEAPONS],[last(w8,0x1b2,x) for x in extra]
ropes=[x for x in w8.calls if x[1]==0x503 and x[2][1] in t2b.MODELS and x[0]>=w8.shared[b.DEPLOY_T0]+3000]
assert len(ropes)>=4 and not [x for x in w8.calls if x[1]==0x9a and x[2][1] in (164,165)],('1.5: the second four come down the helicopter\'s ropes 3 s after the first four (0503), they are not put on the ground',len(ropes))
steps(w8,V8,20)
P8=posts(w8);jobs8={P8[x].job for x in team8+extra if x in P8}
assert set(team8+extra)<=set(P8) and jobs8=={H.HCB_ROLE_LEAD,H.HCB_ROLE_CLOSE,H.HCB_ROLE_POINT,H.HCB_ROLE_REAR,H.HCB_ROLE_CLOSE2,H.HCB_ROLE_POINT2,H.HCB_ROLE_CLOSE3,H.HCB_ROLE_MARKSMAN},jobs8
assert any(orders(w8,0x5d3,x) or orders(w8,0x637,x) for x in extra),'the second squad worker moves the second four to their posts'
passed('Eight on the ground: four more agents in black come down the same ropes 3 s after the first four (MP5, M4, AK, sniper rifle by role) - nobody appears out of nowhere; the brain gives all eight their posts - the commander, three bodyguards, four outer men - and the second squad worker moves them')
# 1.5.4: a man of the second four stuck 45 m+ from CJ for 40 s is replaced where the screen does not show (never in view)
old_=extra[1];w8.pos[old_]=[0.,-60.,0.];w8.offscreen={old_};steps(w8,V8,4)
assert old_ in w8.exists,'not at once'
w8.now+=41000;w8.offscreen={old_};steps(w8,V8,6)
new_=w8.shared[b.GROUND_PUB2+1]
assert new_!=old_ and new_ in w8.exists and old_ not in w8.exists and w8.skin[new_]==t2b.MODELS[1] and not [x for x in w8.teleports if x['who'] in (new_,old_)],(old_,new_)
w8.pos[extra[2]]=[0.,-60.,0.];w8.offscreen=set();steps(w8,V8,4);w8.now+=41000;steps(w8,V8,6)
assert w8.shared[b.GROUND_PUB2+2]==extra[2] and extra[2] in w8.exists,'in view nobody is replaced'
w8.pos[extra[2]]=[1.5,-3.,0.];steps(w8,V8,2)
extra[1]=new_
passed('The second four: a man stuck 45 m or more from CJ for 40 s is deleted out of sight and replaced by a new one that comes in where the screen does not show - never in view, never teleported')
w8.offscreen=set(extra[:2])
for t_ in team8:w8.exists.discard(t_)                     # the first four are gone (fallen / recalled)
steps(w8,V8,8)
assert all(w8.shared[b.GROUND_PUB2+i]==-1 for i in range(4)) and not (set(extra[:2])&w8.exists),'stood down: off screen they are gone at once'
assert all(x in w8.exists and w8.weapons[x]==0 and orders(w8,0x5d3,x) for x in extra[2:]),'in view they put their weapons away and walk off'
w8.offscreen=set(extra);steps(w8,V8,8);assert not (set(extra)&w8.exists),'and are deleted the moment they are out of view'
passed('When the first four go (recalled, stood down) the second four put their weapons away and walk off; nobody is deleted in view')

# ------------------------------------------------------------------ catch-up / stuck / casualty
w.pos[team[0]]=[0.,-120.,0.];w.offscreen={team[0]};w.calls.clear();w.teleports.clear();w.now+=4100;steps(w,V,2)
o=last(w,0x850,team[0]);assert o[1]==1 and not orders(w,0xa1,team[0]),o
w.pos[team[1]]=[0.,-120.,0.];w.offscreen=set();w.calls.clear();w.now+=4100;steps(w,V,2)
assert orders(w,0x850,team[1]) and not orders(w,0xa1,team[1])
w.pos[team[1]]=[0.,-15.,0.];w.calls.clear();w.now+=4100;steps(w,V,2);assert not orders(w,0x5d3,team[1]),'still following at 15 m (until he is within 10 m)'
w.pos[team[1]]=[0.,-8.,0.];w.calls.clear();steps(w,V,3);assert orders(w,0x5d3,team[1]) or orders(w,0x637,team[1]) or orders(w,0x5f5,team[1]),'within 10 m: back to the post the brain gives him'
w.pos[team[0]]=[1.,-8.,0.];steps(w,V,3)
passed('1.5: left behind (22 m+ from CJ, counting height; out of sight or not): the guard follows CJ\'s own footsteps (the game\'s follower task) until he is within 10 m, then takes his post again; nobody is teleported')
w.pos[team[2]]=[6.,-15.,0.];w.blocked={team[2]};w.calls.clear();steps(w,V,6);w.now+=3000;steps(w,V,2);w.offscreen={team[2]};w.now+=3000;steps(w,V,3)
assert (orders(w,0x5f5,team[2]) or posts(w)[team[2]].move==4) and not orders(w,0xa1,team[2]) and not w.teleports,'stuck guard goes by the path network (the script\'s own re-path, or the brain\'s move 4 he is on already), never teleports'
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
# ------------------------------------------------------------------ a fight: the outer man takes a post out, the inner three stay with CJ
w,c,ground,sq,team=escort_world(tactics=1);V=(c,ground,sq)
for t in team:w.pos[t]=[0.,-2.,0.]
hostile=950;w.exists.add(hostile);w.pos[hostile]=[30.,0.,0.];w.pedtype[hostile]=7;w.weapons[hostile]=30;w.health[hostile]=100000;w.civilians=[hostile];w.damage.add((1,hostile))
w.walk.clear();w.calls.clear();w.messages.clear();steps(w,V,8)
P_=posts(w);J={jobs[p.job]:p for p in P_.values()}
out_=J['point']
assert out_.duty in (H.HCB_DUTY_BOUND,H.HCB_DUTY_COVER) and math.dist(spot(out_),[0.,0.])>8,(out_.duty,spot(out_))
assert [x for x in w.calls if x[1] in (0x637,0x5d3) and x[2][0]==out_.who],'the outer man runs to his post'
assert all(math.dist(spot(J[k]),[0.,0.])<2.1 for k in ('lead','close','close2')) and 'SQXR' in w.messages and not invariants(w),({k:spot(v) for k,v in J.items()},w.messages)
passed('A fight (1.5; the old ASSAULT setting is ignored): the outer man runs to a post of his own 8 m or more out, the commander and the two bodyguards stay at CJ\'s side')
w.pos[team[2]]=[0.,60.,0.];w.calls.clear();steps(w,V,3)
o=last(w,0x850,team[2]);assert o[1]==1 and not orders(w,0xa1,team[2]),o   # 1.5: beyond 22 m he follows CJ's footsteps back
passed('Leash: a guard more than 22 m from CJ follows CJ\'s footsteps back (no teleport)')
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
w.player=[30.,0.,0.];w.calls.clear();steps(w,V,12);assert not calls(w,0xe48) and not [x for x in w.calls if x[1] in FIRING],'still nothing'
passed('The brain mod gone in mid-game: the squad never runs the opcode and never fires (no "dumb" fallback: the posts are the brain\'s)')
w,c,_=setup();summon(w,c);command=g['command'];command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0
ground=VM('Helicover_Ground',w);sq=VM('Helicover_Squad',w);w.health[1]=100;w.step(c,ground,sq,n=3);w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,sq,n=6)
rope=[w.shared[b.GROUND_PUB+i] for i in range(4)];w.now+=8000;w.calls.clear();w.step(c,ground,sq,n=6)
assert w.shared[b.SQ_ROPE]==1 and all(len(orders(w,0x5d3,t))>0 for t in rope)
assert all(o[4] in (4,6,7) for t in rope for o in orders(w,0x5d3,t)) and w.shared[b.SQ_GROUP]==2
passed('Rope evacuation guards are led by the squad while CJ walks to the rope')
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1],0.]
hostile=950;w.exists.add(hostile);w.pos[hostile]=[20.,0.,0.];w.pedtype[hostile]=7;w.weapons[hostile]=30;w.civilians=[hostile];w.damage.add((1,hostile))
w.health[hostile]=100000;steps(w,V,30);ducked=[t for t in team if orders(w,0x634,t)];assert ducked,'somebody fights crouched from his spot'
g_=ducked[0];w.dead.add(hostile);w.pos[g_]=[0.,-12.,0.];w.calls.clear();steps(w,V,6)
seq=[x[1] for x in w.calls if x[2] and x[2][0]==g_ and x[1] in (0x4eb,0x5d3,0x637)]
assert seq[:2]==[0x4eb,0x5d3] and last(w,0x4eb,g_)[1]==0,seq
passed('After a crouched fight the guard stands up before moving on')
door=list(w.coords(1));steps(w,V,3)
w.interior=3;w.player=[2000.,2000.,1000.] if hasattr(w,'player') else None;w.pos[team[1]]=[door[0],door[1]-30.,0.];w.calls.clear();w.teleports.clear();w.now+=4100;steps(w,V,12)
Pd=posts(w)
assert not any(orders(w,op,t) for t in team for op in (0xa1,0x850)) and not w.teleports,'nobody follows CJ into the building or is teleported'
assert Pd and all(math.dist(spot(p_),door[:2])<=13. for p_ in Pd.values()),('the posts are laid out round the door CJ went in by',[spot(p_) for p_ in Pd.values()],door)
assert orders(w,0x5d3,team[1]) or orders(w,0x637,team[1]) or orders(w,0x5f5,team[1]),'the man who was away comes to his post at the door'
w.interior=0;w.player=door
passed('CJ inside a building: the detail holds the door he went in by - posts round it, nobody follows him inside or is teleported; the man who was away comes back to the door')
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
p0=posts(w)[team[0]];hd_=math.degrees(math.atan2(-(p0.at.x-0.),p0.at.y+12.))%360
assert orders(w,0x78f,team[0]) and abs(w.actor_heading[team[0]]-hd_)<.5,(orders(w,0x78f,team[0]),w.actor_heading[team[0]],hd_)
passed('A fence in the way: the guard turns to it and climbs over')
w,c,ground,sq,team=escort_world();V=(c,ground,sq)
w.pos[team[0]]=[0.,-12.,1.];steps(w,V,3);w.los_fn=lambda a,z:not(a[2]<.6 and z[2]<.6);w.ground_fn=lambda x,y,z:1. if y>-10.5 else 0.
w.calls.clear();steps(w,V,3);assert not orders(w,0x78f,team[0])
passed('Stairs or a slope are walked, not vaulted')
# ------------------------------------------------------------------ menu
w,c,p=setup(True);launch=VM('Helicover',w);summon(w,c);w.step(c,p,launch,n=15)
assert w.menu[7]==b'DEPLOY SQUAD',w.menu
w.events.append(6);w.step(c,p,n=4);assert not any(b'TACTICS' in r for r in w.menu) and w.menu[-1]==b'< BACK',w.menu
w.events.append(2);w.step(c,p,n=4);w.shared[b.ESCORT_ON]=1;w.step(c,p,n=4);assert w.menu[7]==b'RECALL SQUAD',w.menu   # (BACK is row 3 now)
w.step(c,p,n=6);w.events.append(5);w.step(c,p,n=2);assert w.shared[b.CMD] in (17,0) and any(x[2]==[b.CMD,17] for x in calls(w,0xddc))
passed('Main menu: one row deploys / recalls the squad; SETTINGS has no tactics row any more (1.5: the brain alone decides how the detail fights)')
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
m=[x[2] for x in calls(w,0x4a2) if abs(x[2][4]-12.)<.01 and abs(x[2][5]-x[2][3])<.01][-1];assert abs(m[3]-(w.pos[npc][2]+40.))<.01,m
passed('Combat orbit: a point without a view of the threat is flown 15 m higher and the next one is tried')
pts=[];n=len(calls(w,0x4a2))
for _ in range(30):w.step(c,f)
pts={(round(x[2][1]),round(x[2][2])) for x in calls(w,0x4a2)[n:] if abs(x[2][4]-12.)<.01 and abs(x[2][5]-x[2][3])<.01}
assert len(pts)<=4,pts
passed('Combat orbit with no clear view moves on at most every 1.2 s instead of thrashing every tick')

# ------------------------------------------------------------------ door gunners (1.3: every decision is the brain's)
fw=g['fire_world'];threaten=g['threaten'];attacks=g['attacks'];hit=g['hit'];aims=g['aims']
def gunner_world(npcs,attack=True,typ=7):
 w,c,f=fw();w.civilians=[];w.brain.hold_still=True   # (door-gunner drills: the helicopter hangs where it is put - its own pilot is tried in test_v25)
 for npc,x,y in npcs:
  w.exists.add(npc);w.pos[npc]=[x,y,0.];w.skin[npc]=102;w.pedtype[npc]=typ;w.weapons[npc]=30;w.health[npc]=100000;w.civilians.append(npc)
  if attack:w.damage.add((1,npc))
 return w,c,f
def rounds_by(w):
 """Who of the gunners fired his own weapon at whom (the rounds of the game the world saw)."""
 crew={w.shared[b.PUB+i] for i in range(3,7)};d={}
 for t_,who,man,_s,_e in w.game_rounds:
  if who in crew:d.setdefault(who,set()).add(man)
 return d
# The helicopter hangs south of CJ, nose to the north-west: its right door looks north (towards CJ), its left door south.
def heli_frame():
 w,c,f=gunner_world([]);w.step(c,f,n=2);h=w.shared[b.PUB+1];hd=math.radians(w.cars[h].get('heading',0.));return w.cars[h]['pos'],(-math.sin(hd),math.cos(hd))
HPOS,HFW=heli_frame();HRT=(HFW[1],-HFW[0])
def around(ahead,right):
 """A point on the ground in the helicopter's own frame: metres ahead of it and to its right."""
 return HPOS[0]+HFW[0]*ahead+HRT[0]*right,HPOS[1]+HFW[1]*ahead+HRT[1]*right
w,c,f=gunner_world([(910,20.,10.),(911,-10.,-95.)]);w.step(c,f,n=25)
R,L=[w.shared[b.PUB+3],w.shared[b.PUB+5]],[w.shared[b.PUB+4],w.shared[b.PUB+6]];by=rounds_by(w)
assert all(by[x]=={910} for x in R if x in by) and all(by[x]=={911} for x in L if x in by) and set(R)&set(by) and set(L)&set(by) and hit(w)=={910,911} and not invariants(w),(by,invariants(w))
sides={x[2][0]:x[2][8] for x in calls(w,0x713)}
assert sides and all(v_==(1 if who in R else 0) for who,v_ in sides.items()),('the drive-by is fired out of his own door',sides)
passed('Door gunners take a man on their own side - right door right, left door left - and never fire across the cabin (1.4: his own weapon; the second man of a door holds while his mate is in his line)')
w,c,f=gunner_world([]);w.step(c,f,n=2);g3=w.coords(w.shared[b.PUB+3]);g5=w.coords(w.shared[b.PUB+5])
hd=math.radians(w.cars[w.shared[b.PUB+1]].get('heading',0.));fw_=(-math.sin(hd),math.cos(hd));rt=(fw_[1],-fw_[0])
man=[g5[0]+(rt[0]*.87-fw_[0]*.5)*25.,g5[1]+(rt[1]*.87-fw_[1]*.5)*25.]   # out of the right door, a little aft (the helicopter's own right)
w.exists.add(910);w.pos[910]=[man[0],man[1],0.];w.skin[910]=102;w.pedtype[910]=7;w.weapons[910]=30;w.health[910]=100000;w.civilians=[910];w.damage.add((1,910))
w.los_fn=lambda a,z:math.dist(a,w.coords(w.shared[b.PUB+3]))>1.6;w.step(c,f,n=25);by=rounds_by(w)   # something hides the man from the front seat of the right door (wherever the brain has him sit or kneel)
assert w.shared[b.PUB+3] not in by and by.get(w.shared[b.PUB+5])=={910} and not invariants(w),by
assert [x for x in w.game_rounds if x[1]==w.shared[b.PUB+3]]==[],'no round is even asked for: the brain knows he cannot see the man'
passed('A gunner without a clear line from his seat does not fire; the other gunner in that door does')
w,c,f=gunner_world([(900,*around(14,25)),(901,*around(0,30)),(902,*around(-14,25))]);w.step(c,f,n=30);by=rounds_by(w)   # all three off the right door: ahead, abeam, aft
assert set(by)==set(R) and all(len(v)==1 for v in by.values()) and by[R[0]]!=by[R[1]],by
passed('Three attackers and two gunners who can see them: each gunner stays on a man of his own (no hopping from man to man, no doubling up while there is a man nobody is on)')
n0={who:len([x for x in w.game_rounds if x[1]==who]) for who in R};w.exists.add(903);w.pos[903]=[25.,20.,0.];w.pedtype[903]=7;w.weapons[903]=30;w.health[903]=100000;w.damage.add((1,903));w.step(c,f,n=15)
later={who:{x[2] for x in w.game_rounds[-200:] if x[1]==who and x[0]>w.now-800} for who in R}
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
assert {x[2] for x in w.game_rounds}=={940} and not invariants(w),'the man at the wheel'
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
 w,c,f=fire_world();w.brain.hold_still=True;npc=target(w,typ=7,skin=20);w.damage.add((1,npc));w.step(c,f,n=10)   # (no spot from the brain: the old orbit of the game's pilot, kept as the fallback)
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
m=calls(w,0x4a2)[-1][2];spot_z=w.shared[b.HELI_SPOT_Z]
assert abs(m[3]-(10.+25.+15.))<.01 or (spot_z>1 and abs(m[3]-spot_z)<.01 and spot_z>=10.+12.),(m,spot_z)
passed('A shooter on a roof: the helicopter stays well above him (the brain\'s spot where the gunners see him, or the old orbit 15 m higher)')
# CJ steps into a guard's line of fire between two looks of the squad (it thinks ten times a second): the guard is told in that very frame
for offset in range(7):
 w,c,ground,sq,team=escort_world();V=(c,ground,sq);w.frame_ms=16
 for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1],0.]
 foe=960;w.exists.add(foe);w.pos[foe]=[25.,0.,0.];w.pedtype[foe]=7;w.weapons[foe]=30;w.health[foe]=100000;w.civilians=[foe];w.damage.add((1,foe))
 steps(w,V,80+offset)
 shooters=[k for k in range(4) if w.shared[b.SQ_BR_ST+k]==2 and firing(w,team[k])];assert shooters,[w.shared[b.SQ_BR_ST+k] for k in range(4)]
 k=shooters[0];gp=w.coords(team[k]);d=[w.pos[foe][i]-gp[i] for i in range(2)];L=math.hypot(*d)
 w.player=[gp[0]+d[0]/L*4.,gp[1]+d[1]/L*4.,0.];w.pos[1]=list(w.player);n0=len(w.calls);steps(w,V,1)
 frame=w.calls[n0:]
 assert w.shared[b.SQ_BR_ST+k]==3 and [x for x in frame if x[1]==0x667 and x[2][0]==team[k]] and not [x for x in frame if x[1] in FIRING and x[2][0]==team[k]],(offset,k,w.shared[b.SQ_BR_ST+k],[hex(x[1]) for x in frame if x[2] and x[2][0]==team[k]])
passed('CJ steps into a guard\'s line of fire: in that very frame (not on the squad\'s next look) his firing task is replaced by an aiming one')
# ------------------------------------------------------------------ v41 threat board: squad
def squad_scene(npcs):
 w,c,ground,sq,team=escort_world();V=(c,ground,sq)
 for k,t in enumerate(team):w.pos[t]=[BG[k][0],BG[k][1],0.]
 steps(w,V,3);w.civilians=[]
 for n,x,y,wpn,hostile in npcs:
  w.exists.add(n);w.pos[n]=[x,y,0.];w.pedtype[n]=7;w.skin[n]=20;w.weapons[n]=wpn;w.civilians.append(n)
  if hostile:w.damage.add((1,n))
 return w,V,team
w,V,team=squad_scene([(980,20.,0.,30,True),(981,-40.,0.,22,False)]);w.weapons[981]=30;w.health[980]=100000;w.health[981]=100000;V=V+(VM('Helicover_Fire',w),);w.messages.clear();steps(w,V,8)
assert w.shared[b.SQ_T]==980 and 981 not in [w.shared[b.SQ_T+i] for i in range(4)] and 'SQXR' in w.messages,([w.shared[b.SQ_T+i] for i in range(4)],w.messages)
w.shot_at={981:[1.5,-1.,.5]};w.shooting_chars={981};w.calls.clear();steps(w,V,45);w.shooting_chars=set()
men=[w.shared[b.SQ_T+i] for i in range(4)];on=w.brain.orders()
assert men.count(980)>=3 and set(men)<={980,981} and any(fights(w,t,980) for t in team),('the guards who are firing keep their man (a free fourth may take the second)',men)
assert [k for k,o in on.items() if o[0]==981 and o[1]] and 981 in {x[1] for x in getattr(w,'hits',[])} and not invariants(w),('the second man is taken by the door gunners who have him in their arc',on,invariants(w))
passed('A second man opens fire on CJ from 40 m on the other side: the brain gives him to the door gunners who can reach him, the guards keep the man they are firing at - both are fought, nobody flips')
w,V,team=squad_scene([(982,0.,-25.,34,True)]);w.messages.clear();steps(w,V,8)
assert 'SQSB' in w.messages,w.messages
w,V,team=squad_scene([(983,22.,0.,30,True)]);w.pos[983][2]=9.;w.messages.clear();steps(w,V,8)
assert 'SQRR' in w.messages,w.messages
passed('Squad call-outs name the kind of threat and where: "Sniper - rear!", "Shooter on the roof - right!"')
# 1.4: cover, crouching, shielding and 'at ease' are the brain's posts now - see the protective-detail drills above

# ------------------------------------------------------------------ 1.1: v41 details completed
def car_attack(hp,x=24.):
 w,c,f=gunner_world([]);drv,car=962,963;w.exists.update({drv,car});w.cars[car]={'pos':[x,6.,0.],'heading':90.};w.model[car]=400;w.incar[drv]=car
 w.traffic=[car];w.seats[(car,-1)]=drv;w.pedtype[drv]=7;w.skin[drv]=102;w.weapons[drv]=30;w.health[drv]=100000;w.damage.add((1,drv));w.health[car]=hp;w.calls.clear();w.step(c,f,n=30);return w,c,f,car,drv
w,c,f,car,drv=car_attack(1000)
assert attacks(w) and {x[2] for x in w.game_rounds}=={drv} and all(x[2][1]==drv for x in calls(w,0x713)) and not invariants(w),(len(attacks(w)),{x[2] for x in w.game_rounds})
passed('A man in a car: the gunners\' fire is at him (the drive-by task names the man, never the car), never at the engine or the tank - the gunners do not blow cars up')
# a damaged car within 18 m of CJ is left alone: it could blow up beside him
w,c,f,car,drv=car_attack(1000,x=12.);assert attacks(w)
n0=len(attacks(w));w.calls.clear();w.health[car]=CFG.car_floor-1;w.step(c,f,n=3);n=len(attacks(w));w.step(c,f,n=30)
assert len(attacks(w))==n and n-n0<=3 and aims(w,drv),('no round later than 0.3 s after the car dropped below the floor; the weapons stay on the man',n-n0)
w,c,f,car,drv=car_attack(CFG.car_floor-1,x=12.);assert not attacks(w)
w.incar.pop(drv);w.pos[drv]=[12.,6.,0.];w.calls.clear();w.step(c,f,n=30);assert attacks(w) and hit(w)=={drv},'the same man on foot is a target again'
w,c,f,car,drv=car_attack(CFG.car_floor-1,x=40.);assert attacks(w),'40 m from CJ the same damaged car may be stopped by fire'
passed('A car below %d health within 18 m of CJ is not fired at (it burns below 250): no rounds, weapons on the man only - he is engaged again once he is out of it; far from CJ the same car may be fired at'%int(CFG.car_floor))
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
assert protect(turn=FACING_DEG-10)[0] and protect(turn=10-FACING_DEG)[0] and not protect(turn=FACING_DEG+15)[0] and not protect(turn=-FACING_DEG-15)[0],'turned to CJ = within 40 degrees either way'
assert not protect(x=CFG.near_m+15.)[0],'armed and looking this way from 55 m: too far to call it imminent'
assert not protect(in_car=True)[0],'gang members driving past are left alone (this is what blew cars up beside CJ)'
assert protect(in_car=True,hurt=True)[0],'... until they attack'
assert not protect(typ=4)[0] and not protect(typ=4,wanted=3)[0],'an armed civilian is not a hostile type, wanted level or not'
assert protect(typ=4,hurt=True)[0],'... but anybody who has hurt CJ is a target'
assert not protect(typ=6,weapon=22,wanted=0)[0],'police without a wanted level'
assert not protect(typ=6,weapon=22,wanted=1)[0] and protect(typ=6,weapon=22,wanted=1,shoots=True)[0],'an armed policeman turned to a wanted CJ is covered; he is fired at once he fires (POLICE: FIRE BACK)'
assert not protect(typ=6,weapon=3,wanted=2)[0],'a policeman with a nightstick is left to CJ (until he hits him)'
assert not protect(typ=6,weapon=22,wanted=3,in_car=True)[0],'police cars are not fired at just because CJ is wanted'
assert not protect(typ=8)[0] and not protect(typ=8,skin=105)[0],'Grove never'
passed('PROTECT ME engages threats only: whoever hurt CJ, or an armed gang member on foot within %d m and turned to CJ (40 degrees either way) - not passers-by, not armed civilians, not cars driving past, not policemen who have not fired'%CFG.near_m)
for mode in (0,2,3,4):
 w,c,f=fw();w.shared[b.FIRE]=mode;w.wanted=3;w.calls.clear();w.step(c,f,n=20)
 assert not [x for x in calls(w,0x77a) if x[2][1]==4],(mode,[x[2] for x in calls(w,0x77a) if x[2][1]==4][:3])
passed('No fire mode makes the gunners hate a ped type any more: the game\'s own AI cannot open fire on a car by itself, every target comes from the rules')
# an attacker at CJ's elbow: not one round from the helicopter; the moment CJ is clear of him the gunners fire
w,c,f=fw();w.civilians=[];npc=900;w.exists.add(npc);w.pos[npc]=[0.,1.5,0.];w.skin[npc]=102;w.pedtype[npc]=7;w.health[npc]=100000;w.civilians.append(npc);w.damage.add((1,npc));w.calls.clear();w.step(c,f,n=50)
assert not attacks(w) and aims(w,npc) and not invariants(w),(len(attacks(w)),invariants(w))
w.player=[0.,-25.,0.];w.calls.clear();w.step(c,f,n=40);assert attacks(w) and hit(w)=={npc} and not invariants(w),'CJ has stepped away from him: fire'
passed('An attacker 1.5 m from CJ: no round from the helicopter, the weapons stay on him; they fire once CJ is %.0f m clear of the line'%CFG.cj_line_m)
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
 w.step(c,f);m=calls(w,0x4a2)[-1][2];cj=w.coords(1)
 assert abs(math.dist(m[1:3],[28.,0.])-b.ORBIT_RADIUS)<.5 or (w.shared[b.HELI_SPOT_Z]>1 and 9.<=math.dist(m[1:3],cj[:2])<=34.),m
passed('Threat 40 m from CJ: the helicopter covers both - the brain\'s spot 28 m from CJ on the far side (or the old orbit centre 30% towards CJ)')
w,V,team=squad_scene([(997,0.,20.,30,True)]);steps(w,V,10)
assert sum(1 for t in team if firing(w,t))>=2
w.los_fn=lambda a,z:False;w.calls.clear();steps(w,V,30)        # he slips out of everybody's sight
assert not [x for x in w.calls if x[1] in FIRING and x[0]>w.now-2800] and not calls(w,0x668) and any(orders(w,0x667,t) for t in team) and not invariants(w)
w.los_fn=lambda a,z:True;w.calls.clear();steps(w,V,12);assert any(firing(w,t) for t in team) and not invariants(w),'the fight goes on as soon as he shows himself (whoever has a clear line)'
passed('A man who slips out of sight: within 0.2 s nobody fires at him or at the place he was (nobody checks a line to a place) - weapons stay up - and the fight goes on when he shows himself')
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
 for _ in range(secs*10):steps(w,V,1)
 return w,V,team
w,V,team=noisy_fight(2)
assert 2<=len(w.messages)<=6,w.messages
passed('A 12 s fight with four shooters gives %d clear radio calls, not a stream (%s)'%(len(w.messages),', '.join(w.messages)))
w,V,team=squad_scene([(985,20.,0.,30,False)]);w.actor_heading[985]=90.;w.health[985]=100000;w.shared[b.MSG_PRIO]=3;w.shared[b.MSG_UNTIL]=w.now+8000;w.shared[b.MSG_HOLD]=w.now+1200;w.messages.clear();steps(w,V,10)
assert not w.messages,('nothing lesser for the first 1.2 s of an alarm',w.messages)
w,V,team=squad_scene([(985,20.,0.,30,False)]);w.actor_heading[985]=90.;w.health[985]=100000;w.shared[b.MSG_PRIO]=3;w.shared[b.MSG_UNTIL]=w.now+8000;w.shared[b.MSG_HOLD]=0;w.messages.clear();steps(w,V,10)
assert w.messages and all(b._mv.PRIO.get(k_,2)>=2 for k_ in w.messages),w.messages
w.shared[b.MSG_PRIO]=3;w.shared[b.MSG_UNTIL]=w.now+20000;w.messages.clear();steps(w,V,120);assert w.messages and all(b._mv.PRIO.get(k_,2)>=2 for k_ in w.messages),w.messages
passed('An alarm on screen: nothing lesser for 1.2 s, then a tactical call or an order of the commander may take its place but never chatter')
w,V,team=noisy_fight(1)
assert w.messages and not {'SQCAR'}&set(w.messages),w.messages
passed('MESSAGES: IMPORTANT keeps danger and tactical calls, drops the chatter')
w,V,team=noisy_fight(0,6)
assert not w.messages,w.messages
assert w.shared[b.STATE] in (3,19),'1.5.3: "we pull out" has called the rope pickup by itself'
w.health[1]=100;w.shared[b.CMD]=2;steps(w,V,8);w.messages.clear()   # (FOLLOW ME again: the pickup is called off)
w.shared[b.CMD]=16;steps(w,V,4);assert w.messages==['SQALR'],w.messages
passed('MESSAGES: OFF is silent in a fight but still explains why a command was refused')
w,c,ground,sq,team=escort_world();f=VM('Helicover_Fire',w);V=(c,ground,sq,f)
for k,tm in enumerate(team):w.pos[tm]=[BG[k][0],BG[k][1],0.]
hostile=996;w.exists.add(hostile);w.pos[hostile]=[20.,0.,0.];w.pedtype[hostile]=7;w.weapons[hostile]=30;w.civilians=[hostile];w.damage.add((1,hostile))
w.messages.clear();w.shared[b.MSG_UNTIL]=0;steps(w,V,30)
assert 'SQXR' in w.messages and 'HCCONT' not in w.messages,w.messages
passed('With the team on the ground only the squad calls the contact (no double "CONTACT!")')
# ------------------------------------------------------------------ 1.5.3: the rest of the plan, in the scripts
# an unarmed brawler at CJ: the brain says "by hand" - the guard puts his gun away and goes for him; an armed man - the gun is back
w,V,team=squad_scene([(985,7.,0.,0,True)]);w.health[985]=100000;w.calls.clear();steps(w,V,25)
fist=[x for x in w.calls if x[1]==0x5e2 and x[2][1]==985]
assert fist and not hit_men(w,985) if 'hit_men' in globals() else fist,'a guard goes for him with his hands'
gman=fist[0][2][0]
assert any(x[1]==0x1b9 and x[2]==[gman,0] for x in w.calls) and not [x for x in firing(w,gman) if 985 in x[2][1:8]],'his gun is put away first, and he does not shoot the man'
w.weapons[985]=30;w.calls.clear();steps(w,V,20)
import build_v25_ground as _g
assert any(x[1]==0x1b9 and x[2][0]==gman and x[2][1] in [wp for wp,_m in _g.TEAM_WEAPONS] for x in w.calls),'the man has drawn a gun: the guard\'s own gun is back in his hands'
passed('An unarmed brawler at CJ is taken down by hand (the guard puts his gun away, no shot is fired at the man); when the man draws a weapon the guard has his gun in his hands again')
# the commander's new words reach the screen
w,c,ground,sq,team=escort_world();V=(c,ground,sq);steps(w,V,3)
for seq_,(what,dir_,key) in enumerate([(9,3,'SQGL'),(10,0,'SQWATER'),(11,0,'SQAHEAD'),(12,3,'SQKL'),(7,1,'SQSR'),(8,0,'SQMEM')]):
 w.messages.clear();w.now+=4000;w.brain.say=(100+seq_,what,dir_);steps(w,V,4);assert key in w.messages,(key,w.messages)
passed('The commander\'s words reach the screen: "grenade - left", "CJ is in the water", "armed men ahead", "sniper - right", "we were attacked here before"')
# "we pull out" also orders the rope pickup for the player (the hot pickup) - only while the helicopter escorts and CJ is on foot
w,c,ground,sq,team=escort_world();V=(c,ground,sq);steps(w,V,3)
assert w.shared[b.STATE]==2
w.now+=4000;w.brain.say=(200,4,0);steps(w,V,6)
assert w.shared[b.STATE]==19 or any(x[2]==[b.CMD,10] for x in calls(w,0xddc)),(w.shared[b.STATE],'the rope pickup is ordered')
passed('"We pull out" is also the order to the pilot: the rope pickup starts by itself (the hot pickup); CJ only has to take the rope')
w,c,p=setup(True);launch=VM('Helicover',w);w.step(c,p,launch,n=15);w.events.append(1);w.step(c,p,n=4)
rows=[]
for _ in range(4):rows.append(w.menu[3]);w.events.append(1);w.step(c,p,n=4)   # (1.5: MESSAGES is row 1 of the settings)
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
