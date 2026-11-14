"""Tests final CLEO bytecode with mocked game opcodes, not an Android/GTA emulator."""
import struct,json,math,sys
from collections import defaultdict,deque
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import build_v25 as b
class World:
 def __init__(self):
  self.shared=defaultdict(int);self.now=0;self.models=True;self.playing=True;self.control=True;self.interior=0
  self.exists={1};self.dead=set();self.next=100;self.player=[0.,0.,0.];self.car=[0.,-45.,28.]
  self.onscreen=True;self.calls=[];self.events=deque();self.menu=None;self.touches={}
  self.incar={};self.attach={};self.pos={};self.model={};self.skin={};self.health=defaultdict(lambda:1000)
  self.weapons=defaultdict(int);self.velocity={};self.speed=0;self.altitude=25;self.siteclear=True;self.auto_board=True;self.ground_fn=lambda x,y,z: 13.35 if 2400<x<2600 and -1750<y< -1600 else 0.;self.clear_fn=lambda x,y: True
  self.random_char=-1;self.civilians=[];self.traffic=[];self.seats={};self.damage=set();self.messages=[];self.cars={};self.current_car=None;self.fallback_car=self.car.copy();self.heading=72.;self.attached_reports_incar=True;self.shooting=False;self.targeting=-1;self.camera=[0.,-5.,2.];self.lookat=[100.,-5.,2.];self.ray_block_distance=None;self.pedtype={};self.armor=defaultdict(int);self.wanted=0;self.shooting_chars=set();self.actor_heading=defaultdict(float);self.frozen={};self.accuracy={};self.attack_rate={};self.create_calls=0;self.fail_create_after=None
 @property
 def car(self):
  return self.cars[self.current_car]['pos'] if getattr(self,'current_car',None) in getattr(self,'cars',{}) else getattr(self,'fallback_car',[0.,-45.,28.])
 @car.setter
 def car(self,value):
  if getattr(self,'current_car',None) in getattr(self,'cars',{}):self.cars[self.current_car]['pos']=value
  else:self.fallback_car=value
 def step(self,*vms,n=1):
  for _ in range(n):
   delta=getattr(self,'frame_ms',100);self.now+=delta
   for actor,velocity in self.velocity.items():
    if actor in self.incar:continue
    if actor==1:self.player=[self.player[i]+velocity[i]*delta/1000. for i in range(3)]
    elif actor in self.pos:self.pos[actor]=[self.pos[actor][i]+velocity[i]*delta/1000. for i in range(3)]
   for vm in vms:vm.run()
 def coords(self,char):
  if char in self.incar:return self.cars[self.incar[char]]['pos'].copy()
  if char in self.attach:return [self.cars[self.attach[char][0]]['pos'][i]+self.attach[char][1][i] for i in range(3)]
  return self.player.copy() if char==1 else self.pos.get(char,[0.,0.,0.]).copy()
class VM:
 def __init__(self,name,w):
  self.w=w;self.ip=0;self.v=defaultdict(int);self.wake=0;self.done=False;self.stack=[]
  meta=json.loads((b.OUT/(name+'.meta.json')).read_text());raw=(b.OUT/(name+('.csi' if name=='Helicover' else '.csa'))).read_bytes();self.raw=raw
  self.code={};p=0
  while p<meta['code_size']:
   start=p;op=struct.unpack_from('<H',raw,p)[0];p+=2;args=[]
   for _ in range(b.LIB[op&0x7fff]['num_params']):
    t=raw[p];p+=1
    if t==9:v=raw[p:p+8].split(b'\0')[0].decode();p+=8
    else:fmt={1:'<i',2:'<h',3:'<h',4:'<b',5:'<h',6:'<f'}[t];v=struct.unpack_from(fmt,raw,p)[0];p+=struct.calcsize(fmt)
    args.append((t,v))
   self.code[start]=(op,args,p)
 def run(self):
  if self.done or self.w.now<self.wake:return
  w=self.w
  for _ in range(5000):
   op,aa,nxt=self.code[self.ip];self.ip=nxt;vals=[self.v[v] if t==3 else v for t,v in aa]
   def put(i,v):assert aa[i][0]==3;self.v[aa[i][1]]=v
   def cond(val):self.cond=self.cond and (not val if op&0x8000 else val)
   base=op&0x7fff;w.calls.append((w.now,op,vals.copy()))
   if op==0:pass
   elif op==1:self.wake=w.now+max(vals[0],1);return
   elif op==2:self.ip=-vals[0]
   elif op==0x50:self.stack.append(self.ip);self.ip=-vals[0]
   elif op==0x51:self.ip=self.stack.pop()
   elif op==0x4d:
    if not self.cond:self.ip=-vals[0]
   elif op==0x4e:self.done=True;return
   elif op==0xd6:self.cond=True
   elif base in [0x39,0x3b]:cond(vals[0]==vals[1])
   elif base in [0x19,0x1d,0x21,0x23,0x25]:cond(vals[0]>vals[1])
   elif base==0x256:cond(w.playing)
   elif base==0xab6:
    marker=getattr(w,'marker',None)
    for i in range(3):put(i,marker[i] if marker else 0.)
    cond(marker is not None)
   elif base==0x9e7:cond(w.control)
   elif base==0x248:cond(w.models)
   elif base==0x4ee:cond(getattr(w,'animation_loaded',True))
   elif base==0x611:cond(getattr(w,'animation_available',True))
   elif base in [0x56d,0x56e]:cond(vals[0] in w.exists)
   elif base in [0x118,0x119]:cond(vals[0] in w.dead)
   elif base in [0x2ca,0x2cb]:cond(w.onscreen)
   elif base in [0xdb,0x448]:cond(w.incar.get(vals[0])==vals[1] or (base==0xdb and w.attached_reports_incar and vals[0] in w.attach and w.attach[vals[0]][0]==vals[1]))
   elif base==0xdf:cond(vals[0] in w.incar or (w.attached_reports_incar and vals[0] in w.attach))
   elif base==0xa32:cond(vals[0] in w.attach)
   elif base==0x2e0:cond(w.shooting if vals[0]==1 else vals[0] in w.shooting_chars)
   elif base==0x10f:cond(w.wanted>vals[1])
   elif base==0x2f2:cond(w.skin.get(vals[0])==vals[1])
   elif base==0x457:cond(w.targeting==vals[1])
   elif base==0x431:cond((vals[0],vals[1]) not in w.seats)
   elif base==0x205:cond(all(abs(w.coords(vals[0])[i]-w.car[i])<=vals[2+i] for i in range(3)))
   elif base==0x6bd:cond(w.siteclear and w.clear_fn(vals[0],vals[1]) and getattr(w,'los_fn',lambda a,b:True)(vals[:3],vals[3:6]) and (w.ray_block_distance is None or math.dist(vals[:3],vals[3:6])<w.ray_block_distance))
   elif base in [0x51a,0x51c]:cond((vals[0],vals[1]) in w.damage)
   elif op==0xddd:put(0,w.shared[vals[1]])
   elif op==0xddc:w.shared[vals[0]]=vals[1]
   elif op in [6,7,0x85,0x87]:put(0,vals[1])
   elif op==0x93:put(0,float(vals[1]))
   elif op==0x62:put(0,vals[0]-vals[1])
   elif op in [0xa,0xb,0x5a,0x5b]:put(0,vals[0]+vals[1])
   elif op in [0x12,0x13,0x6b]:put(0,vals[0]*vals[1])
   elif op==0x63:put(0,vals[0]-vals[1])
   elif op==0x73:put(0,vals[0]/vals[1])
   elif op==0x1bd:put(0,w.now)
   elif op==0x1f5:put(1,1)
   elif op==0x1b4:w.control=bool(vals[1])
   elif op==0x83c:w.velocity[vals[0]]=vals[1:4]
   elif op==0xa1:
    w.velocity.pop(vals[0],None)
    if vals[0]==1:w.player=vals[1:4].copy()
    else:w.pos[vals[0]]=vals[1:4].copy()
   elif op==0x77e:put(0,w.interior)
   elif op in [0x4c4,0x407]:
    xyz=w.coords(vals[0]) if op==0x4c4 else w.cars[vals[0]]['pos']
    for i in range(3):put(4+i,xyz[i]+vals[1+i])
   elif op in [0xa0,0xaa]:
    for i,v in enumerate(w.coords(vals[0]) if op==0xa0 else w.cars[vals[0]]['pos']):put(1+i,v)
   elif op==0x50a:put(6,math.dist(vals[:3],vals[3:6]))
   elif op==0x509:put(4,math.dist(vals[:2],vals[2:4]))
   elif op==0x2ce:put(3,w.ground_fn(*vals[:3]))
   elif op==0x174:put(1,w.cars[vals[0]]['heading'])
   elif op==0x175:w.cars[vals[0]]['heading']=vals[1]
   elif op==0x224:w.health[vals[0]]=vals[1]
   elif op==0x470:put(1,w.weapons[vals[0]])
   elif op==0x68d:
    for i,v in enumerate(w.camera):put(i,v)
   elif op==0x68e:
    for i,v in enumerate(w.lookat):put(i,v)
   elif op==0x81a:pass
   elif op==0x819:put(1,getattr(w,'ped_heights',{}).get(vals[0],0.) if vals[0] in w.pos else w.altitude)
   elif op==0x2e3:put(1,w.speed)
   elif op in [0x227,0x226]:put(1,w.health[vals[0]])
   elif op==0x4dd:put(1,w.armor[vals[0]])
   elif op==0x35f:w.armor[vals[0]]=min(100,w.armor[vals[0]]+vals[1])
   elif op==0x172:put(1,w.actor_heading[vals[0]])
   elif op==0x173:w.actor_heading[vals[0]]=vals[1]
   elif op==0x89f:put(1,w.pedtype.get(vals[0],4))
   elif op==0x1c0:put(1,w.wanted)
   elif op==0x604:put(2,math.degrees(math.atan2(-vals[0],vals[1]))%360)
   elif op==0x7e4:
    for i,v in enumerate([-2.,-5.,-1.,2.,5.,2.]):put(i+1,v)
   elif op==0x574:w.frozen[vals[0]]=bool(vals[1])
   elif op==0x88c:w.cars[vals[0]]['pos']=vals[1:4].copy()
   elif op==0x1ea:put(1,0 if w.model.get(vals[0])==425 else 3)
   elif op==0x73f:put(7,w.random_char)
   elif op==0x503:
    w.next+=1;new=w.next;put(5,new);w.exists.add(new);w.pos[new]=vals[2:5].copy();w.skin[new]=vals[1];w.pedtype[new]=vals[0]
   elif op==0xa3e:
    candidates=w.civilians or ([w.random_char] if w.random_char in w.exists else [])
    found=next((ch for ch in candidates if ch in w.exists and ch not in w.dead and ch not in w.incar and ch not in w.attach and all(abs(w.coords(ch)[i]-vals[i])<=vals[i+3] for i in range(3))),-1)
    put(6,found)
   elif op==0x53e:
    found=next((car for car in w.traffic if car in w.exists and vals[0]<=w.cars[car]['pos'][0]<=vals[2] and vals[1]<=w.cars[car]['pos'][1]<=vals[3] and (vals[4]<0 or w.model[car]==vals[4])),-1)
    put(5,found)
   elif op==0x46c:put(1,w.seats.get((vals[0],-1),-1))
   elif op==0x432:
    assert (vals[0],vals[1]) in w.seats, 'empty passenger seat dereference'
    put(2,w.seats[(vals[0],vals[1])])
   elif op==0x3c0:put(1,w.incar.get(vals[0],-1))
   elif op==0x2e2:w.accuracy[vals[0]]=vals[1]
   elif op==0x7dd:w.attack_rate[vals[0]]=vals[1]
   elif op in [0xa5,0x129,0x9a,0x186,0x187]:
    w.create_calls+=1
    if op==0x9a and w.fail_create_after is not None and w.create_calls>=w.fail_create_after:put(len(aa)-1,-1);continue
    w.next+=1;new=w.next;put(len(aa)-1,new);w.exists.add(new)
    if op==0xa5:w.model[new]=vals[0];w.cars[new]={'pos':vals[1:4].copy(),'heading':w.heading};w.current_car=new
    elif op==0x129:w.incar[new]=vals[0];w.skin[new]=vals[2]
    elif op==0x9a:w.pos[new]=vals[2:5].copy();w.skin[new]=vals[1];w.pedtype[new]=vals[0]
   elif op in [0x9b,0xa6]:w.exists.discard(vals[0]);w.incar.pop(vals[0],None);w.attach.pop(vals[0],None);w.cars.pop(vals[0],None)
   elif op==0x464:
    w.incar.pop(vals[0],None);w.attach[vals[0]]=(vals[1],vals[2:5].copy());w.weapons[vals[0]]=vals[-1]
   elif op==0x465:w.pos[vals[0]]=w.coords(vals[0]);w.attach.pop(vals[0],None)
   elif op in [0x36a,0x430]:w.attach.pop(vals[0],None);w.incar[vals[0]]=vals[1]
   elif op==0x362:w.pos[vals[0]]=vals[1:4].copy();w.incar.pop(vals[0],None);w.attach.pop(vals[0],None)
   elif op==0x5ca:
    if w.auto_board:w.attach.pop(vals[0],None);w.incar[vals[0]]=vals[1]
   elif op==0x5cd:
    if vals[0]==1:w.player=w.car.copy()
    else:w.pos[vals[0]]=w.car.copy()
    w.incar.pop(vals[0],None)
   elif op==0x223:w.health[vals[0]]=vals[1]
   elif op==0x48f:w.weapons[vals[0]]=0
   elif op==0x1b2:w.weapons[vals[0]]=vals[1]
   elif op==0x3e5:w.messages.append(vals[0])
   elif op==0xdd0:put(0,-vals[1])
   elif op==0xdf2:
    fields=self.raw[vals[0]+4:].split(b'\0');w.menu=fields[:2+vals[1]]
   elif op==0xdf3:w.menu=None
   elif op==0xdf4:put(0,w.events.popleft() if w.events else -1)
   elif op==0xde0:put(0,int(vals[1] in w.touches and w.now-w.touches[vals[1]]>=vals[2]))
   else:
    assert op in [0x247,0x38b,0x39f,0x1c5,0x8af,0x54a,0x446,0x77a,0x168,0x165,0x7e0,0x957,0x35f,0x825,0x918,0x7bb,0x249,0x4df,0x726,0x780,0x4a2,0x743,0x164,0x1c2,0x1c3,0x1b9,0x687,0x74d,0x5d3,0x4eb,0x637,0x667,0x792,0x619,0x83c,0x99a,0x4ba,0x668,0x713,0x6bc,0xaf,0x7db,0x4e4,0xad,0x853,0x337,0x4ed,0x605,0x614,0x393],hex(op)
  raise AssertionError('loop without WAIT')
def setup(panel=False):
 w=World();c=VM('Helicover_Core',w);p=VM('Helicover_Panel',w) if panel else None;v=[c]+([p] if p else []);w.step(*v,n=3);return w,c,p
def command(w,c,n,extra=None,ticks=5):w.shared[b.CMD]=n;w.step(c,*([extra] if extra else []),n=ticks)
def summon(w,c):command(w,c,1,ticks=8);assert w.shared[b.STATE]==2
results=[]
def passed(t):results.append('PASS: '+t)
def calls(w,op):return [x for x in w.calls if x[1]==op]

def near_cj_landing(w,c):
 command(w,c,5,ticks=8)
 assert w.shared[b.STATE]==7
 w.car=[c.v[26],c.v[27],1.5];w.altitude=1.5;w.speed=0
 w.step(c,n=14)
 assert w.shared[b.STATE]==8

def start_grove(w,c):
 near_cj_landing(w,c)
 w.player=w.car.copy()
 command(w,c,6,ticks=24)
 assert w.incar.get(1)==c.v[5] and w.shared[b.STATE]==9,(w.incar,w.shared[b.STATE],c.v[24])
 command(w,c,7,ticks=15)
 assert w.shared[b.STATE]==20
 w.altitude=50;w.step(c,n=8)
 assert w.shared[b.STATE]==10,(w.shared[b.STATE],c.v[24])

w,c,_=setup();summon(w,c);pilot=c.v[4];car=c.v[5];command(w,c,5,ticks=8)
assert w.shared[b.STATE]==7
mission=calls(w,0x743)[-1][2]
assert mission[:5]==[car,0.,15.,0.,6.] and abs(mission[5]-6.)<1e-5,mission
assert calls(w,0x7bb)[-1][2]==[car,0] and calls(w,0x853)[-1][2]==[car,3]
assert calls(w,0xad)[-1][2]==[car,25.]
assert w.calls.index(calls(w,0xad)[-1])>w.calls.index(calls(w,0x743)[-1])
assert not any(x[2][0]==pilot for x in calls(w,0x792))
assert calls(w,0x186) and not calls(w,0x187) and not calls(w,0x88c)
passed('Pickup requests native landing with reduced approach altitude/thrust/speed and vehicle marker')

# Do not deploy guards while moving or while the altitude test briefly flickers.
w.car=[c.v[26],c.v[27],1.5];w.altitude=1.5;w.speed=4.;w.step(c,n=14)
assert w.shared[b.STATE]==7 and all(v in w.attach for v in [c.v[13],c.v[14],c.v[15],c.v[16]])
w.speed=0;w.step(c,n=5);w.altitude=8;w.step(c,n=2);w.altitude=1.5;w.step(c,n=8)
assert w.shared[b.STATE]==7
w.step(c,n=6)
assert w.shared[b.STATE]==8 and w.incar[pilot]==car and all(c.v[v] not in w.attach for v in [13,14,15,16])
passed('Guard deployment waits for stable pickup; pilot stays in helicopter')

w,c,_=setup();summon(w,c);w.siteclear=False;command(w,c,5,ticks=8)
assert w.shared[b.STATE]==2 and not calls(w,0x743) and 'HCNOSIT' in w.messages
passed('Obstructed pickup does not issue a landing order')

w,c,_=setup();summon(w,c);w.ground_fn=lambda x,y,z: 4. if x>2. else 0.;command(w,c,5,ticks=8)
assert w.shared[b.STATE]==2 and not calls(w,0x743) and 'HCNOSIT' in w.messages
passed('Uneven pickup is rejected')

w,c,_=setup();summon(w,c);start_grove(w,c);car=c.v[5]
route=calls(w,0x4a2)[-1][2]
assert route[1:3]==[b.GROVE_X,b.GROVE_Y]
w.car=[b.GROVE_X+150,b.GROVE_Y,75];w.step(c,n=3)
assert calls(w,0x4e4)[-1][2]==[b.GROVE_X,b.GROVE_Y]
assert calls(w,0x7bb)[-1][2]==[car,0] and calls(w,0xad)[-1][2]==[car,21.]
w.car=[b.GROVE_X+60,b.GROVE_Y,75];w.step(c,n=8)
assert w.shared[b.STATE]==22
w.car=[w.shared[b.DEST_X],w.shared[b.DEST_Y],w.shared[b.DEST_Z]+18.];w.speed=0;w.step(c,n=6);assert w.shared[b.STATE]==23
command(w,c,12,ticks=6);assert w.shared[b.STATE]==11
mission=calls(w,0x743)[-1][2]
assert mission[0:3]==[car,b.GROVE_X,b.GROVE_Y]
assert abs(mission[3]-13.35)<.001 and mission[4]==0. and mission[5]==0.,mission
assert w.incar[1]==car
w.car=[c.v[26],c.v[27],14.85];w.altitude=1.5;w.step(c,n=14)
assert w.shared[b.STATE]==12 and w.incar[1]==car
command(w,c,8,ticks=5);assert 1 not in w.incar
command(w,c,6,ticks=5);assert w.incar[1]==car
command(w,c,2,ticks=20);assert w.shared[b.STATE]==3 and c.v[24]==3
passed('Full pickup -> team muster -> Grove flight -> detected landing -> CJ leaves')

w,c,_=setup();summon(w,c);start_grove(w,c)
w.clear_fn=lambda x,y:not (abs(x-b.GROVE_X)<.2 and abs(y-b.GROVE_Y)<.2)
w.car=[b.GROVE_X+60,b.GROVE_Y,75];w.step(c,n=8)
assert w.shared[b.STATE]==22 and w.shared[b.DEST_X]==b.GROVE_X+6
w.car=[w.shared[b.DEST_X],w.shared[b.DEST_Y],w.shared[b.DEST_Z]+18.];w.speed=0;w.step(c,n=6);command(w,c,12,ticks=6)
assert w.shared[b.STATE]==11 and calls(w,0x743)[-1][2][1:3]==[b.GROVE_X+6,b.GROVE_Y]
passed('Grove chooses a nearby point in the circle when the centre is obstructed')

w,c,_=setup();summon(w,c);start_grove(w,c);w.ground_fn=lambda x,y,z: 0.
w.car=[b.GROVE_X+60,b.GROVE_Y,75];before=len(calls(w,0x743));w.step(c,n=90)
assert w.shared[b.STATE]==18 and len(calls(w,0x743))==before and w.incar[1]==c.v[5]
assert 'HCBLOCK' in w.messages and not calls(w,0x88c)
passed('Unloaded/invalid Grove ground times out with status; CJ remains safely aboard')

w,c,_=setup();summon(w,c);command(w,c,5,ticks=8);initial=len(calls(w,0x743))
w.now+=26000;w.step(c,n=4)
assert len(calls(w,0x743))==initial and w.shared[b.STATE]==7
w.step(c,n=12);assert len(calls(w,0x743))==initial
w.now+=65000;w.step(c,n=5)
assert w.shared[b.STATE]==18 and 'HCBLOCK' in w.messages and not calls(w,0x88c)
w.shared[b.MODEL]=497;w.step(c,n=8)
assert w.shared[b.STATE]==18 and calls(w,0x4a2)[-1][2][0]==c.v[5]
passed('Stalled approach reports blocked without restarting the mission or teleporting')

w,c,_=setup();summon(w,c);command(w,c,5,ticks=8)
w.car=[c.v[26]+8,c.v[27],15.];w.now+=26000;w.step(c,n=4)
assert len(calls(w,0x743))==2 and calls(w,0x743)[-1][2][4:]==[0.,0.]
w.step(c,n=15);assert len(calls(w,0x743))==2
passed('Final descent is ordered once after coming close and slow')

w,c,_=setup();summon(w,c);command(w,c,5,ticks=8);target=[c.v[x] for x in [26,27,28]]
w.shared[b.MODEL]=497;w.step(c,n=12)
assert w.model[c.v[5]]==497 and calls(w,0x743)[-1][2][1:4]==target
assert calls(w,0x7bb)[-1][2]==[c.v[5],0] and calls(w,0x853)[-1][2]==[c.v[5],3]
w.shared[b.CREW]=0;w.step(c,n=12);assert w.shared[b.ACREW]==0 and calls(w,0x743)[-1][2][1:4]==target
passed('Changing helicopter or crew resumes the same native landing')

w,c,p=setup(True);summon(w,c);launch=VM('Helicover',w);w.step(c,p,launch,n=15);w.events.append(3);w.step(c,p,n=4)
assert w.menu[0]==b'EVAC / FOLLOWING'
w.shared[b.CMD]=5;w.step(c,p,n=8);assert w.menu[0]==b'EVAC / EVAC INBOUND'
passed('Evacuation menu updates status while it is open')

def fire_world():
 w,c,_=setup();summon(w,c);f=VM('Helicover_Fire',w);w.step(c,f,n=3);w.shared[b.FIRE]=3;return w,c,f
def target(w,typ=4,skin=20):
 npc=900;w.exists.add(npc);w.pos[npc]=[20.,0.,0.];w.skin[npc]=skin;w.pedtype[npc]=typ;w.random_char=npc;return npc
def attacks(w):return [x for x in w.calls if x[1] in [0x74d,0x713,0x668]]
w,c,f=fire_world();npc=target(w);w.step(c,f,n=7);assert not attacks(w)
w.damage.add((1,npc));w.step(c,f,n=7);assert calls(w,0x74d) and all(x[2][1]==npc for x in calls(w,0x74d))
passed('Existing protection worker still issues target tasks for a simulated attacker')
for typ,skin in [(8,105),(8,270),(4,105),(4,106),(4,107)]:
 w,c,f=fire_world();npc=target(w,typ=typ,skin=skin);w.damage.add((1,npc));w.wanted=6;w.step(c,f,n=7);assert not attacks(w)
passed('Existing protection worker still excludes Grove actors in the mock')
w,c,f=fire_world();w.shared[b.FIRE]=0;npc=target(w,typ=7);w.wanted=6;w.damage.add((1,npc));w.step(c,f,n=7);assert not attacks(w)
w.shared[b.FIRE]=1;w.step(c,f,n=7);assert attacks(w)
w.shared[b.FIRE]=0;w.step(c,f,n=3);count=len(attacks(w));w.step(c,f,n=5);assert len(attacks(w))==count
passed('Fire mode selection still enables and stops issuing tasks in the mock')

w,c,_=setup();summon(w,c);start_grove(w,c);w.car=[b.GROVE_X+60,b.GROVE_Y,75];w.step(c,n=8);assert w.shared[b.STATE]==22;w.car=[w.shared[b.DEST_X],w.shared[b.DEST_Y],w.shared[b.DEST_Z]+18.];w.speed=0;w.step(c,n=6);command(w,c,12,ticks=6);w.car=[c.v[26],c.v[27],14.85];w.altitude=1.5;w.step(c,n=14)
assert w.shared[b.STATE]==12;command(w,c,8,ticks=5);assert 1 not in w.incar
w.player=[2400.,-1600.,13.]
for v in [13,14,15,16]:w.pos[c.v[v]]=w.player.copy()
w.onscreen=False;command(w,c,9,ticks=10)
assert w.shared[b.STATE]==2 and c.v[24]==3 and 1 not in w.incar
assert all(c.v[v] in w.attach for v in [13,14,15,16])
assert calls(w,0x918)[-1][2]==[c.v[5],1] and calls(w,0x726)[-1][2][1]==1
passed('All four onboard guards remain attached after Grove and follow takeoff')

w,c,_=setup();summon(w,c);start_grove(w,c);w.car=[b.GROVE_X+60,b.GROVE_Y,75];w.step(c,n=8);assert w.shared[b.STATE]==22;w.car=[w.shared[b.DEST_X],w.shared[b.DEST_Y],w.shared[b.DEST_Z]+18.];w.speed=0;w.step(c,n=6);command(w,c,12,ticks=6);w.car=[c.v[26],c.v[27],14.85];w.altitude=1.5;w.step(c,n=14)
assert w.incar.get(1)==c.v[5] and w.shared[b.STATE]==12
before=len(calls(w,0x4a2));command(w,c,9,ticks=8)
assert w.shared[b.STATE]==12 and w.incar.get(1)==c.v[5] and 'HCEXIT' in w.messages and len(calls(w,0x4a2))==before
passed('Takeoff-follow requests CJ to exit; no unintended hover with CJ aboard')

w,c,_=setup();summon(w,c);f=VM('Helicover_Fire',w);w.step(c,f,n=3);w.shared[b.FIRE]=2;w.shooting=True
for npc,x in [(900,10.),(901,50.)]:w.exists.add(npc);w.pos[npc]=[x,0.,0.];w.skin[npc]=20;w.pedtype[npc]=4
w.civilians=[900,901];w.targeting=901;w.step(c,f,n=8)
assert calls(w,0x74d) and all(x[2][1]==901 for x in calls(w,0x74d))
passed('Follow-shots finds the game auto-aim target instead of the first nearby NPC')

w,c,p=setup(True);summon(w,c);launch=VM('Helicover',w);w.step(c,p,launch,n=15);w.events.append(3);w.step(c,p,n=4)
assert b'TAKE OFF / FOLLOW' in w.menu and w.menu[-1]==b'< BACK'
passed('Evacuation menu exposes the new takeoff command')

w,c,f=fire_world();n=target(w);w.damage.add((1,n));w.step(c,f,n=12)
assert calls(w,0x6bc) and all(x[2][1]==n for x in calls(w,0x74d))
w.shared[b.FIRE]=0;w.step(c,f,n=5);count=len(calls(w,0x6bc));w.step(c,f,n=6);assert len(calls(w,0x6bc))==count
passed('Protect CJ and cease-fire remain active after aim and takeoff changes')

w,c,p=setup(True);summon(w,c);f=VM('Helicover_Fire',w);w.step(c,p,f,n=3);w.shared[b.FIRE]=3;w.step(c,p,f,n=5)
launch=VM('Helicover',w);w.step(c,p,f,launch,n=15);w.events.append(5);w.step(c,p,f,n=4);w.events.append(3);w.step(c,p,f,n=4)
assert w.menu[0]==b'WEAPONS / LIVE' and b'MP5' in w.menu
w.events.append(1);w.step(c,p,f,n=12)
assert w.shared[b.WEAPON_SETTING]==29 and w.shared[b.WPN]==29
assert all(w.weapons[c.v[v]]==29 for v in [13,14,15,16]) and b'MP5 [ON]' in w.menu
passed('Weapon menu changes all four live guards to MP5')
w.events.append(0);w.step(c,p,f,n=12)
assert w.shared[b.WEAPON_SETTING]==0 and w.shared[b.WPN]==31
assert all(w.weapons[c.v[v]]==31 for v in [13,14,15,16])
passed('Crew-based automatic weapon selection can be restored')
for index, weapon in [(1,29),(2,30),(3,31),(4,34),(0,31)]:
 w.events.append(index);w.step(c,p,f,n=12)
 assert w.shared[b.WPN]==weapon
 assert all(w.weapons[c.v[v]]==weapon for v in [13,14,15,16])
passed('All weapon selections update the four guards in the mock')

w,c,p=setup(True);w.touches[7]=0;w.step(c,p,n=15);w.touches[5]=w.now;w.step(c,p,n=8)
assert w.menu is None and not calls(w,0xde0)
launch=VM('Helicover',w);w.step(c,p,launch,n=15);assert w.menu is not None
passed('Gesture activation is removed; CLEO menu invocation still opens the panel')

# Additional SWAT team: safe deployment, protection from targeting, cleanup.
w,c,p=setup(True);summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0
fire=VM('Helicover_Fire',w);ground=VM('Helicover_Ground',w);w.step(c,p,fire,ground,n=5)
w.shared[b.ROPE_COMMAND]=1;w.step(c,p,fire,ground,n=6)
squad=[w.shared[b.GROUND_PUB+i] for i in range(4)]
assert len(set(squad))==4 and all(x in w.exists for x in squad), (squad,w.messages)
assert len(calls(w,0x503))>=4 and all(c.v[i] in w.attach for i in [13,14,15,16])
passed('Rope insertion creates four additional guards while aircraft guards remain attached')
launch=VM('Helicover',w);w.step(c,p,fire,ground,launch,n=15);w.events.append(3);w.step(c,p,fire,ground,n=4)
assert b'ROPE EVACUATION' in w.menu and b'FLY TO GROVE' in w.menu and b'LAND NEAR CJ' not in w.menu and b'BOARD CJ' not in w.menu and w.menu[-1]==b'< BACK'
passed('Evacuation menu exposes rope insertion')
w.random_char=squad[0];w.damage.add((1,squad[0]));w.shared[b.FIRE]=3;w.step(c,p,fire,ground,n=12)
assert not any(x[2][1]==squad[0] for x in calls(w,0x74d))
passed('Protect CJ does not target a member of the ground team')
# Descent ends, then the additional guards follow their formation positions.
w.now+=8000;w.random_char=-1;w.step(c,p,fire,ground,n=5)
assert any(x[2][0] in squad for x in calls(w,0x5d3))
passed('Ground team receives CJ-relative formation tasks after descent')
# The existing worker chooses a hostile; ground guards receive the same target.
hostile=target(w,typ=7,skin=21);w.damage.add((1,hostile));w.step(c,p,fire,ground,n=22)
assert any(x[2][0] in squad and x[2][1]==hostile for x in calls(w,0x74d)), (w.shared[b.FIRE_TARGET], squad)
passed('Ground team attacks the hostile selected by Protect CJ in the mock')
command(w,c,2,ticks=5);w.step(c,p,fire,ground,n=5)
assert all(x not in w.exists for x in squad) and all(w.shared[b.GROUND_PUB+i]==-1 for i in range(4))
passed('Leaving hold removes the temporary ground squad and clears friendly handles')
w,c,_=setup();summon(w,c);ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=5)
assert not calls(w,0x503) and 'RGHOLD' in w.messages
passed('Insertion is rejected unless helicopter is holding')

# Exercise automatic CJ ascent, reverse animation commands and sequential guard return.
w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0
ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=5)
squad=[w.shared[b.GROUND_PUB+i] for i in range(4)]
for ch,(x,y) in zip(squad,[(-1.5,1.2),(1.5,1.2),(-1.5,-1.2),(1.5,-1.2)]):w.pos[ch]=[x,y,.7]
w.now+=8000;w.player=[0.,-3.,.7];w.step(c,ground,n=8)
assert w.control is False and calls(w,0x393), (w.control,w.messages)
w.step(c,ground,n=80)
assert w.incar.get(1)==c.v[5] and w.control is True, (w.incar,w.messages)
w.step(c,ground,n=240)
assert all(ch not in w.exists for ch in squad) and all(w.shared[b.GROUND_PUB+i]==-1 for i in range(5))
assert not w.frozen.get(c.v[5],False)
passed('Fifth rope proximity triggers simulated reverse ascent, restores CJ control and returns four guards')
# Changing flight state during ascent must restore control and place CJ back at the ground position.
w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0
ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=5)
w.now+=8000;w.player=[0.,-3.,.7];w.step(c,ground,n=8);assert w.control is False
command(w,c,2,ticks=2);w.step(c,ground,n=6)
assert w.control is True and w.player[2]<2 and w.incar.get(1)!=c.v[5]
passed('Interrupting player ascent restores control and the last ground position')
# A failed animation task must not receive speed/time adjustments or leave control disabled.
w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0;w.animation_available=False
ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=5)
w.now+=8000;w.player=[0.,-3.,.7];stream_count=len(calls(w,0x38b));w.step(c,ground,n=85)
assert len(calls(w,0x38b))==stream_count and not calls(w,0x4ed)
assert not calls(w,0x614) and not calls(w,0x393) and w.control and w.incar.get(1)==c.v[5]
passed('CJ ascent avoids new animation streaming and tolerates an unavailable animation task')
w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0;w.animation_loaded=False
ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=5)
w.now+=8000;w.player=[0.,-3.,.7];w.step(c,ground,n=20)
assert 'RGANIM' in w.messages and w.control and w.incar.get(1)!=c.v[5] and not calls(w,0x1b4)
passed('Missing resident PED animation cancels safely before disabling CJ control')
assert all(op!=0x0432 for op,_,_ in VM('Helicover_Fire',World()).code.values())
passed('Fire worker omits passenger getter implicated by the AML crash log')

# A rope request flies to a site and triggers deployment only after stable arrival.
w,c,p=setup(True);summon(w,c);ground=VM('Helicover_Ground',w);w.step(c,p,ground,n=3)
w.shared[b.CMD]=10;w.step(c,p,ground,n=6);assert w.shared[b.STATE]==19 and calls(w,0x4a2)
assert not calls(w,0x503)
w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;w.step(c,p,ground,n=12)
assert w.shared[b.STATE]==3 and len(calls(w,0x503))>=4, (w.shared[b.STATE],w.messages)
passed('Rope command approaches a clear site, then starts deployment when hovering')
w,c,_=setup();ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.shared[b.CMD]=10;w.step(c,ground,n=12)
assert w.shared[b.STATE]==19 and c.v[5] in w.exists
passed('Rope command summons helicopter when no support is active')
w,c,p=setup(True);launch=VM('Helicover',w);w.step(c,p,launch,n=15);w.events.append(3);w.step(c,p,n=4);assert b'ROPE EVACUATION' in w.menu
w.events.append(0);w.step(c,p,n=12);assert w.shared[b.STATE]==19
passed('CLEO menu rope action summons and starts the approach')
w,c,_=setup();summon(w,c);w.siteclear=False;ground=VM('Helicover_Ground',w);w.step(c,ground,n=3)
w.shared[b.CMD]=10;w.step(c,ground,n=6)
assert w.shared[b.STATE]!=19 and not calls(w,0x503)
passed('Rope approach rejects blocked sites without spawning the team')
# Min altitude is relative to terrain; max altitude is an absolute world height.
w,c,_=setup();w.player=[0.,0.,30.];w.ground_fn=lambda x,y,z:30.;summon(w,c);ground=VM('Helicover_Ground',w);w.step(c,ground,n=3)
w.shared[b.CMD]=10;w.step(c,ground,n=6);mission=calls(w,0x4a2)[-1][2]
assert mission[3:]==[45.,12.,45.],mission
w.car=[c.v[26]+4.,c.v[27],45.];w.speed=0.;w.step(c,ground,n=12)
assert w.shared[b.STATE]==3 and len(calls(w,0x503))>=4, (w.shared[b.STATE],w.messages)
passed('At elevated terrain, hovering 4m from pickup starts deployment at safe height')
assert len(calls(w,0x503))>=5 and w.shared[b.GROUND_PUB+4] in w.exists and w.now<ground.v[27]
passed('Fifth rope is created during guard descent rather than waiting for it to end')
w,c,_=setup();summon(w,c);w.shared[b.CMD]=10;w.step(c,n=6);assert w.shared[b.STATE]==19
w.now+=36000;w.step(c,n=5);assert w.shared[b.STATE]==18 and 'HCRWAIT' in w.messages
passed('A stalled rope approach reports failure after 35 seconds')
# Reject the literal/local argument swap observed in the crash log.
from asm_v25 import Script, V, F
for opcode,args in [(0x0023,(V(19),F(12.0))),(0x0021,(F(1.5),V(8)))]:
 bad=Script();bad.add(opcode,*args)
 try:bad.build('_invalid_comparison','csa')
 except AssertionError:pass
 else:raise AssertionError('Malformed comparison unexpectedly accepted')
passed('Assembler rejects both inverted literal/local comparison forms')

# At high frame rates, ascent must advance in small time-based increments.
for frame_ms in [16,33]:
 w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,15.];w.speed=0
 ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=6)
 w.now+=2000;w.player=[0.,-3.,.7];w.frame_ms=frame_ms
 for _ in range(100):
  w.step(c,ground,n=1)
  if not w.control:break
 assert not w.control,(frame_ms,w.messages)
 for _ in range(160):
  w.step(c,ground,n=1)
  if w.control:break
 assert w.control and w.incar.get(1)==c.v[5]
 motion=[x for x in calls(w,0x83c) if x[2][0]==1]
 assert len(motion)>40,(frame_ms,len(motion))
 assert all(x[2][3]>0 for x in motion[:-1]) and motion[-1][2][3]==0
 assert 1700 <= motion[-1][0]-motion[0][0] <= 1900,(frame_ms,motion[-1][0]-motion[0][0])
 assert len([x for x in calls(w,0xa1) if x[2][0]==1])==1
 frames=[x[2][2] for x in calls(w,0x614) if x[2][0]==1]
 assert len(frames)>40 and frames[-1]<frames[1]
passed('CJ ascent advances smoothly over about 1.8 seconds at two frame rates')
# Landing recognition must not interrupt SWAT rope tasks in the air.
w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,15.];w.speed=0
ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=6)
squad=[w.shared[b.GROUND_PUB+i] for i in range(4)];w.ped_heights={ch:8. for ch in squad}
w.now+=2000;w.step(c,ground,n=20)
assert not any(x[2][0] in squad for x in calls(w,0x5d3))
w.ped_heights[squad[0]]=0.;w.step(c,ground,n=15)
assert any(x[2][0]==squad[0] and x[2][4]==6 for x in calls(w,0x5d3))
assert not any(x[2][0] in squad[1:] for x in calls(w,0x5d3))
passed('Only guards who reach the ground receive running formation tasks')

# Grove flight waits for a climb and reports if the helicopter remains low.
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.altitude=5;command(w,c,7,ticks=8)
assert w.shared[b.STATE]==20
w.now+=31000;w.step(c,n=6)
assert w.shared[b.STATE]==18 and 'HCGCLMB' in w.messages
passed('Grove flight waits for safe climb and reports a stalled ascent')

# Weapons remain selected during cease fire and while CJ is not shooting.
w,c,_=setup();summon(w,c);f=VM('Helicover_Fire',w);w.shared[b.FIRE]=0;w.step(c,f,n=15)
assert all(w.weapons[c.v[v]]==31 for v in [13,14,15,16])
w.shared[b.FIRE]=2;w.shooting=False;w.step(c,f,n=15)
assert all(w.weapons[c.v[v]]==31 for v in [13,14,15,16])
passed('Guards keep selected weapons in cease fire and without CJ shooting')

# Map flight snapshots the marker, reaches a hover, then allows a rope descent.
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.marker=[200.,150.,0.];ground=VM('Helicover_Ground',w);w.step(c,ground,n=3)
command(w,c,11,ticks=8);assert w.shared[b.STATE]==25
w.altitude=50;w.step(c,n=8);assert w.shared[b.STATE]==21
w.car=[205.,150.,80.];w.step(c,ground,n=8);assert w.shared[b.STATE]==22,(w.shared[b.STATE],w.messages)
w.car=[w.shared[b.DEST_X],w.shared[b.DEST_Y],w.shared[b.DEST_Z]+18.];w.speed=0;w.step(c,ground,n=8);assert w.shared[b.STATE]==23
command(w,c,13,ticks=3);w.step(c,ground,n=45)
assert w.control and 1 not in w.incar and w.shared[b.STATE]==3,(w.shared[b.STATE],w.messages,w.control)
assert all(c.v[i] in w.attach for i in [13,14,15,16])
passed('Map marker -> hover -> selected rope descent restores CJ control and preserves onboard team')
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];command(w,c,11,ticks=6)
assert w.shared[b.STATE]==2 and 'HCNOMAP' in w.messages
passed('Map flight rejects an absent marker')
# Distinct threats are assigned separately when candidates occupy different scan cells.
w,c,f=fire_world();w.civilians=[]
for npc,x,y in [(900,0.,0.),(901,-12.,0.),(902,12.,0.),(903,0.,12.)]:
 w.exists.add(npc);w.pos[npc]=[x,y,0.];w.skin[npc]=20;w.pedtype[npc]=7;w.civilians.append(npc)
w.step(c,f,n=16)
assigned=[w.shared[b.GUARD_TARGET+i] for i in range(4)]
assert len(set(assigned))==4 and all(x in w.civilians for x in assigned),assigned
assert any(x[2][-1]==18 for x in calls(w,0x6bc))
passed('Four guards acquire separate eligible threats when available, with stronger checked bullets')

# Search a nearby landing candidate when the exact map marker is obstructed.
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.marker=[200.,150.,0.];w.clear_fn=lambda x,y:not(abs(x-200.)<.2 and abs(y-150.)<.2)
command(w,c,11,ticks=8);assert w.shared[b.STATE]==25;w.altitude=50;w.step(c,n=8);w.car=[205.,150.,80.];w.step(c,n=8)
assert w.shared[b.STATE]==22 and (w.shared[b.DEST_X],w.shared[b.DEST_Y])!=(200.,150.)
passed('Map destination searches a nearby clear landing footprint')
# A blocked rope shaft must not pull CJ out of the helicopter or disable control.
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.shared[b.STATE]=23;w.car=[0.,0.,18.];w.siteclear=False
ground=VM('Helicover_Ground',w);w.step(c,ground,n=4);w.shared[b.DROP_COMMAND]=1;w.step(c,ground,n=8)
assert w.control and w.incar.get(1)==c.v[5] and 'RPDFAIL' in w.messages
passed('Blocked descent shaft leaves CJ aboard with control enabled')
# Patrol uses multiple nearby offsets and switches back to follow when commanded.
w,c,_=setup();summon(w,c);command(w,c,14,ticks=8);assert w.shared[b.STATE]==24
first=calls(w,0x4a2)[-1][2][1:3];w.now+=4500;w.step(c,n=8);second=calls(w,0x4a2)[-1][2][1:3]
assert first!=second,(first,second)
command(w,c,2,ticks=8);assert w.shared[b.STATE]==2
passed('Patrol changes position around CJ and can return to follow')
w,c,_=setup();w.shared[b.CMD]=14;w.step(c,n=15);assert w.shared[b.STATE]==24
passed('Patrol summons a helicopter if none is active')
# When follow falls behind, the script reissues the native follow order.
w,c,_=setup();summon(w,c);w.car=[200.,0.,25.];before=len(calls(w,0x726));w.now+=5000;w.step(c,n=8)
assert len(calls(w,0x726))>before
passed('Follow reissues its order if the helicopter is far from CJ')

# A marked destination can also be landed at after the hover choice.
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.marker=[200.,150.,0.];command(w,c,11,ticks=8);assert w.shared[b.STATE]==25
w.altitude=50.;w.step(c,n=8);w.car=[205.,150.,80.];w.step(c,n=8);assert w.shared[b.STATE]==22
w.car=[w.shared[b.DEST_X],w.shared[b.DEST_Y],w.shared[b.DEST_Z]+18.];w.speed=0;w.step(c,n=8);assert w.shared[b.STATE]==23
command(w,c,12,ticks=6);assert w.shared[b.STATE]==11
w.car=[w.shared[b.DEST_X],w.shared[b.DEST_Y],w.shared[b.DEST_Z]+1.5];w.altitude=1.5;w.step(c,n=15)
assert w.shared[b.STATE]==12 and w.incar.get(1)==c.v[5]
passed('Marked destination hover -> choose landing preserves CJ aboard')
# Protect CJ excludes Grove and ground squad while distributing targets.
w,c,f=fire_world();w.civilians=[]
for npc,x,skin,typ in [(900,0.,20,7),(901,-12.,105,7),(902,12.,20,7)]:
 w.exists.add(npc);w.pos[npc]=[x,0.,0.];w.skin[npc]=skin;w.pedtype[npc]=typ;w.civilians.append(npc)
w.shared[b.GROUND_PUB]=902;w.step(c,f,n=16)
assigned=[w.shared[b.GUARD_TARGET+i] for i in range(4)]
assert 901 not in assigned and 902 not in assigned and 900 in assigned,assigned
passed('Target distribution excludes Grove and the additional ground squad')

# Menu dispatch for patrol and map flight.
w,c,p=setup(True);summon(w,c);launch=VM('Helicover',w);w.step(c,p,launch,n=15);w.events.append(5);w.step(c,p,n=5)
assert b'PATROL AROUND CJ' in w.menu;w.events.append(5);w.step(c,p,n=12);assert w.shared[b.STATE]==24
passed('CLEO setup menu starts patrol')
w,c,p=setup(True);summon(w,c);w.incar[1]=c.v[5];w.marker=[200.,150.,0.];launch=VM('Helicover',w);w.step(c,p,launch,n=15);w.events.append(3);w.step(c,p,n=5)
assert b'FLY TO MAP MARKER' in w.menu;w.events.append(2);w.step(c,p,n=12);assert w.shared[b.STATE]==25
passed('CLEO evacuation menu starts the marked route')

# A forward obstruction produces a clear side detour, then resumes the destination.
w,c,_=setup();summon(w,c);start_grove(w,c)
w.los_fn=lambda a,z: not (abs(z[0]-a[0])<.1 and z[1]-a[1]>30.)
w.now+=1500;w.step(c,n=5)
assert w.shared[b.AVOID_STAGE]==1 and w.shared[b.STATE]==10
assert calls(w,0x4a2)[-1][2][1] != b.GROVE_X
w.los_fn=lambda a,z:True;w.now+=7000;w.step(c,n=5)
assert w.shared[b.AVOID_STAGE]==0 and calls(w,0x4a2)[-1][2][1:3]==[b.GROVE_X,b.GROVE_Y]
passed('Blocked forward cruise chooses a side detour then resumes the Grove route')
w,c,_=setup();summon(w,c);start_grove(w,c);w.los_fn=lambda a,z:False;w.now+=1500;w.step(c,n=5)
assert w.shared[b.STATE]==18 and 'HCAVOID' in w.messages
passed('When both detours are obstructed, cruise reports a blocked route')

# The pilot brings a distant active target into view while following CJ.
w,c,f=fire_world();npc=target(w,typ=7,skin=20);w.damage.add((1,npc));w.step(c,f,n=25)
assert any(x[2][1]==npc for x in calls(w,0x780)),calls(w,0x780)
passed('Pilot can reposition to keep an active threat in view')
# A player follow order cancels an active cruise detour.
w,c,_=setup();summon(w,c);start_grove(w,c);w.los_fn=lambda a,z:not (abs(z[0]-a[0])<.1 and z[1]-a[1]>30.)
w.now+=1500;w.step(c,n=5);assert w.shared[b.AVOID_STAGE]==1
# CJ is aboard, so a HOLD order cancels the cruise without ejecting CJ.
command(w,c,3,ticks=8);assert w.shared[b.STATE]==3 and w.shared[b.AVOID_STAGE]==0 and w.incar.get(1)==c.v[5]
passed('New hold command cancels an active detour without ejecting CJ')

text='\n'.join(results)+'\nMocked script execution only: actual GTA flight, collisions, gunfire, animations and Android behavior are not tested.\n'
(b.OUT/'scenario_tests.txt').write_text(text);print(text)
