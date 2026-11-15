"""Tests final CLEO bytecode with mocked game opcodes, not an Android/GTA emulator."""
import struct,json,math,sys,random
from collections import defaultdict,deque
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import build_v25 as b
import brain_mock
class World:
 def __init__(self):
  self.shared=defaultdict(int);self.now=0;self.models=True;self.playing=True;self.control=True;self.interior=0
  self.exists={1};self.dead=set();self.next=100;self.player=[0.,0.,0.];self.car=[0.,-45.,28.]
  self.onscreen=True;self.calls=[];self.events=deque();self.menu=None;self.touches={}
  self.incar={};self.attach={};self.pos={};self.model={};self.skin={};self.health=defaultdict(lambda:1000)
  self.weapons=defaultdict(int);self.velocity={};self.speed=0;self.altitude=25;self.siteclear=True;self.auto_board=True;self.ground_fn=lambda x,y,z: 13.35 if 2400<x<2600 and -1750<y< -1600 else 0.;self.clear_fn=lambda x,y: True
  self.random_char=-1;self.civilians=[];self.traffic=[];self.seats={};self.damage=set();self.messages=[];self.cars={};self.current_car=None;self.fallback_car=self.car.copy();self.heading=72.;self.attached_reports_incar=True;self.shooting=False;self.targeting=-1;self.camera=[0.,-5.,2.];self.lookat=[100.,-5.,2.];self.ray_block_distance=None;self.pedtype={};self.armor=defaultdict(int);self.wanted=0;self.shooting_chars=set();self.actor_heading=defaultdict(float);self.frozen={};self.accuracy={};self.attack_rate={};self.create_calls=0;self.fail_create_after=None
  self.walk={};self.released=set();self.teleports=[];self.russian=False;self.visible_fn=None;self.rng=random.Random(7)
  self.creator={};self.kind={};self.handed=[];self.wander=set();self.invisible=set();self.released_cars=set()   # beta 4: who made what, living guards handed to the game, leavers
  # 1.3: the brain mod is installed (None = it is not: the scripts must then never run opcode 0E48). Every round the scripts let go is
  # looked at by the world itself: `bullets` = all of them, `bullet_violations` = those that passed within 2 m of CJ or 1 m of one of ours
  self.brain=brain_mock.BrainSim();self.bullets=[];self.bullet_violations=[]
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
   if getattr(self,'pending_car',None):car,pos=self.pending_car;self.cars[car]['pos']=pos;self.pending_car=None
   for actor,velocity in self.velocity.items():
    if actor in self.incar:continue
    if actor==1:self.player=[self.player[i]+velocity[i]*delta/1000. for i in range(3)]
    elif actor in self.pos:self.pos[actor]=[self.pos[actor][i]+velocity[i]*delta/1000. for i in range(3)]
   for ped,order in list(self.walk.items()):
    # 1.2: TASK_GO_* orders move the ped at the pace of the move state (4 walk, 5 jog, 6 run, 7 sprint); no teleport
    if ped not in self.pos and ped!=1:self.walk.pop(ped);continue
    cur=self.coords(ped);to=order['to'];dd=math.dist(cur[:2],to[:2])
    if dd<=.4 or self.now>=order['until']:self.walk.pop(ped);continue
    if ped in getattr(self,'blocked',()):continue   # wedged against something: the order runs, the ped does not move
    step=min(dd,order['speed']*delta/1000.);self.pos[ped]=[cur[0]+(to[0]-cur[0])*step/dd,cur[1]+(to[1]-cur[1])*step/dd,cur[2]]
   if self.brain is not None:self.brain.frame(self)   # the mod's per-frame hook runs before the scripts
   for vm in vms:vm.run()
 @staticmethod
 def seg_dist(a,b2,p):
  """Distance from point p to the segment a-b2."""
  d=[b2[i]-a[i] for i in range(3)];l2=sum(x*x for x in d)
  s=0. if l2<1e-9 else max(0.,min(1.,sum((p[i]-a[i])*d[i] for i in range(3))/l2))
  return math.dist(p,[a[i]+d[i]*s for i in range(3)])
 def visible(self,who):
  """IS_CHAR_ON_SCREEN / IS_CAR_ON_SCREEN: a position function (camera model) when set, else the global flag."""
  if self.visible_fn is not None:return bool(self.visible_fn(self.cars[who]['pos'] if who in self.cars else self.coords(who)))
  return self.onscreen and who not in getattr(self,'offscreen',set())
 def note_teleport(self,op,who,old,new):
  """Position jumps of more than 3 m (SET_CHAR_COORDINATES, WARP..., SET_CAR_COORDINATES): the detector for 'no teleports'."""
  d=math.dist(old,new)
  if d>3.:self.teleports.append({'op':op,'who':who,'dist':d,'visible':self.visible(who),'time':self.now,'from':list(old),'to':list(new)})
 def engine_trace(self,start,end):
  """CBulletTraces::AddTrace(start,end,weaponType,victim) as libGTASA does it: a random 2-5 m piece somewhere on the bullet path."""
  d=[end[i]-start[i] for i in range(3)];length=math.sqrt(sum(x*x for x in d))
  if length<.01:return None
  u=[x/length for x in d];s=length*self.rng.random();piece=2.+3.*self.rng.random();rem=length-s
  piece=rem if piece>=rem else 2.+3.*self.rng.random()
  return {'start':[start[i]+u[i]*s for i in range(3)],'end':[start[i]+u[i]*(s+piece) for i in range(3)],'time':self.now}
 def ped_bullet(self,start,end):
  """A bullet fired by a ped (or CJ): leaves an engine-style trace."""
  tr=self.engine_trace(start,end)
  if tr:self.traces=[x for x in getattr(self,'traces',[]) if self.now-x['time']<300]+[tr]
  return tr
 def exact_bullet(self,start,end):
  """FIRE_SINGLE_BULLET / police helicopter: FireOneInstantHitRound adds the exact start and end."""
  tr={'start':list(start),'end':list(end),'time':self.now};self.traces=[x for x in getattr(self,'traces',[]) if self.now-x['time']<300]+[tr];return tr
 def bullet(self,start,end,damage):
  """FIRE_SINGLE_BULLET: a round from start to end. The first living person within 0.5 m of it is hit. Independently of whoever let it go,
  the world notes a round that passes within 2 m of CJ, or within 1 m of one of ours further than 1 m from where it starts."""
  self.bullets.append((self.now,list(start),list(end),damage));self.exact_bullet(start,end)
  ours=[self.shared[b.PUB+i] for i in range(2,7)]+[self.shared[b.GROUND_PUB+i] for i in range(5)]+[self.shared[b.LEAVE+i] for i in range(8)]   # (the men who were let go and walk away are still ours)
  if self.seg_dist(start,end,self.coords(1))<2.:self.bullet_violations.append((self.now,'CJ',self.seg_dist(start,end,self.coords(1))))
  for o in ours:
   if o in self.exists and o not in self.dead and o not in self.cars and self.seg_dist(start,end,self.coords(o))<1.:self.bullet_violations.append((self.now,o,self.seg_dist(start,end,self.coords(o))))
  hit=None;best=1e9
  for ped in list(self.exists):
   if ped==1 or ped in self.cars or ped in self.dead or ped in ours or not (ped in self.pos or ped in self.incar or ped in self.attach):continue
   pp=self.coords(ped);chest=[pp[0],pp[1],pp[2]+.2]
   if self.seg_dist(start,end,chest)<.5 and math.dist(chest,start)<best:hit=ped;best=math.dist(chest,start)
  if hit is not None:
   self.health[hit]-=damage;self.hits=getattr(self,'hits',[])+[(self.now,hit,damage)]
   if self.health[hit]<=0:self.dead.add(hit)
 def coords(self,char):
  if char in self.incar:return self.cars[self.incar[char]]['pos'].copy()
  if char in self.attach:return [self.cars[self.attach[char][0]]['pos'][i]+self.attach[char][1][i] for i in range(3)]
  if char==1:return self.player.copy()
  xyz=self.pos.get(char,[0.,0.,0.]).copy()
  if char in getattr(self,'ped_heights',{}):xyz[2]+=self.ped_heights[char]
  return xyz
class VM:
 def __init__(self,name,w):
  self.w=w;self.ip=0;self.v=defaultdict(int);self.wake=0;self.done=False;self.stack=[];self.name=name
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
  for _ in range(getattr(self,"budget",5000)):
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
   elif op==0xdd8:
    assert vals[3]==1
    marker=getattr(w,'marker',None);addr,size=vals[1],vals[2];entry=b.RADAR_TRACE_OFS+5*48
    mem={**{(ofs,4):val for ofs,val in b.GAME_SIG},(0xCE1771,1):1 if getattr(w,'russian',False) else 0,(0xCE1773,1):getattr(w,'efigs',1 if 1<=getattr(w,'game_lang',0)<=4 else 0),(0xC1DE88,1):getattr(w,'game_lang',0),(b.WAYPOINT_OFS,4):(5|7<<16) if marker else 0,(b.WAYPOINT_OFS,2):5 if marker else 0xffff,(b.WAYPOINT_OFS+2,2):7 if marker else 0xffff,
         (entry+20,2):getattr(w,'wp_ref',7),(entry+41,1):getattr(w,'wp_flags',0x42),(entry+8,4):marker[0] if marker else 0.,(entry+12,4):marker[1] if marker else 0.}
    for k,tr in enumerate(getattr(w,'traces',[])):
     tb=b.BULLET_TRACES_OFS+k*b.BULLET_TRACE_SIZE
     for i in range(3):mem[(tb+4*i,4)]=tr['start'][i];mem[(tb+12+4*i,4)]=tr['end'][i]
     mem[(tb+24,1)]=1 if tr.get('used',True) else 0;mem[(tb+28,4)]=tr['time']
    put(0,mem.get((addr,size),0))
   elif base==0xab6:
    marker=getattr(w,'marker',None)
    for i in range(3):put(i,marker[i] if marker else 0.)
    cond(marker is not None)
   elif base==0x9e7:cond(w.control)
   elif base==0x248:cond(w.models)
   elif base==0x4ee:cond(getattr(w,'animation_loaded',True))
   elif base==0x611:cond(getattr(w,'animation_available',True))
   elif base in [0x56d,0x56e,0x3ca]:cond(vals[0] in w.exists)
   elif base in [0x118,0x119]:cond(vals[0] in w.dead)
   elif base in [0x2ca,0x2cb]:cond(w.visible(vals[0]))
   elif base in [0xdb,0x448]:cond(w.incar.get(vals[0])==vals[1] or (base==0xdb and w.attached_reports_incar and vals[0] in w.attach and w.attach[vals[0]][0]==vals[1]))
   elif base==0xdf:cond(vals[0] in w.incar or (w.attached_reports_incar and vals[0] in w.attach))
   elif base==0xa32:cond(vals[0] in w.attach)
   elif base==0x9f2:cond(getattr(w,'empty_dm',True))
   elif base==0x2e0:cond(w.shooting if vals[0]==1 else vals[0] in w.shooting_chars)
   elif base==0x10f:cond(w.wanted>vals[1])
   elif base==0x2f2:cond(w.skin.get(vals[0])==vals[1])
   elif base==0x457:cond(w.targeting==vals[1])
   elif base==0x431:cond((vals[0],vals[1]) not in w.seats)
   elif base==0x205:cond(all(abs(w.coords(vals[0])[i]-w.car[i])<=vals[2+i] for i in range(3)))
   elif base==0x6bd:cond(w.siteclear and w.clear_fn(vals[0],vals[1]) and getattr(w,'los_fn',lambda a,b:True)(vals[:3],vals[3:6]) and (w.ray_block_distance is None or math.dist(vals[:3],vals[3:6])<w.ray_block_distance) and not (vals[8] and any(w.seg_dist(vals[:3],vals[3:6],pos)<rad for pos,rad in getattr(w,'blockers',[]))) and not (vals[7] and getattr(w,'car_body',None) and w.incar.get(1) in w.cars and w.seg_dist(vals[:3],vals[3:6],w.cars[w.incar[1]]['pos'])<w.car_body))   # car_body: CJ's own car is solid for lines that include vehicles
   elif base in [0x51a,0x51c]:cond((vals[0],vals[1]) in w.damage)
   elif op==0xddd:put(0,w.shared[vals[1]])
   elif op==0xddc:
    w.shared[vals[0]]=vals[1]
    if vals[0]==b.MSG_ID:w.messages.append(b._mv.KEYS[vals[1]])   # beta 6: a message is 'said' by naming it; the fire worker draws it
   elif op in [6,7,0x85,0x87]:put(0,vals[1])
   elif op==0x93:put(0,float(vals[1]))
   elif op==0x62:put(0,vals[0]-vals[1])
   elif op in [0xa,0xb,0x5a,0x5b]:put(0,vals[0]+vals[1])
   elif op in [0x12,0x13,0x6b]:put(0,vals[0]*vals[1])
   elif op==0x63:put(0,vals[0]-vals[1])
   elif op==0x73:put(0,vals[0]/vals[1])
   elif op==0x16:put(0,int(vals[0]/vals[1]))
   elif op==0x1bd:put(0,w.now)
   elif op==0x1f5:put(1,1)
   elif op==0x1b4:w.control=bool(vals[1])
   elif op==0x83c:w.velocity[vals[0]]=vals[1:4]
   elif op==0x208:put(2,w.rng.uniform(vals[0],vals[1]) if getattr(w,'jitter',False) else (vals[0]+vals[1])/2.)   # GENERATE_RANDOM_FLOAT_IN_RANGE (centre unless a test enables the jitter)
   elif op==0x1c2:
    w.released.add(vals[0])   # MARK_CHAR_AS_NO_LONGER_NEEDED: the game owns him from now on (an ordinary pedestrian with whatever he wears and holds)
    if vals[0] in w.exists and vals[0] not in w.dead and w.creator.get(vals[0])=='Helicover_Ground':w.handed.append((w.now,vals[0]))   # beta 4: a living guard must never be handed to the game
   elif op==0x5de:w.wander.add(vals[0])   # TASK_WANDER_STANDARD: strolls away like a pedestrian
   elif op==0x1c3:w.released_cars.add(vals[0])   # MARK_CAR_AS_NO_LONGER_NEEDED: the departing helicopter flies off as the game's own
   elif op==0x337:
    if not vals[1]:w.invisible.add(vals[0])
   elif op in [0x5d3,0x5f5]:w.walk[vals[0]]={'to':list(vals[1:4]),'speed':{4:1.6,5:3.,6:4.6,7:6.5}.get(int(vals[4]),1.6),'until':w.now+int(vals[5])}
   elif op==0xa1:
    w.velocity.pop(vals[0],None);w.note_teleport(0xa1,vals[0],w.coords(vals[0]),vals[1:4])
    if vals[0]==1:w.player=vals[1:4].copy()
    else:w.pos[vals[0]]=vals[1:4].copy()
   elif op==0xab:
    pos=[vals[1],vals[2],vals[3]+getattr(w,'car_z_offset',1.2)];w.note_teleport(0xab,vals[0],w.cars[vals[0]]['pos'],pos)
    if getattr(w,'teleport_delay',False):w.pending_car=(vals[0],pos)
    else:w.cars[vals[0]]['pos']=pos
   elif op==0x1e5:w.debug=getattr(w,'debug',[]);w.debug.append(vals[1])
   elif op==0x20a:w.locks=getattr(w,'locks',{});w.locks[vals[0]]=vals[1]
   elif base==0xa52:
    if getattr(w,'release_frame',None) is not None:cond(vals[0]==0 and w.release_frame==w.now)  # one-frame event, like the real widget
    else:
     hit=getattr(w,'widget_released',None)==vals[0];w.widget_released=None if hit else getattr(w,'widget_released',None);cond(hit)
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
   elif op==0x2e3:put(1,0. if w.frozen.get(vals[0]) else getattr(w,'car_speeds',{}).get(vals[0],w.speed))
   elif op==0x6ac:put(1,getattr(w,'char_speed',{}).get(vals[0],0.))
   elif op==0x633:
    car=w.incar.pop(vals[0],None)
    if car is not None and car in w.cars:w.pos[vals[0]]=w.cars[car]['pos'].copy()
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
   elif op==0x88c:w.note_teleport(0x88c,vals[0],w.cars[vals[0]]['pos'],vals[1:4]);w.cars[vals[0]]['pos']=vals[1:4].copy()
   elif op==0x1ea:put(1,0 if w.model.get(vals[0])==425 else getattr(w,'seats_count',3))
   elif op==0x73f:put(7,w.random_char)
   elif op==0x503:
    w.next+=1;new=w.next;put(5,new);w.exists.add(new);w.pos[new]=[vals[2],vals[3],w.ground_fn(vals[2],vals[3],vals[4])];w.skin[new]=vals[1];w.pedtype[new]=vals[0];w.creator[new]=self.name
   elif op==0xa3e:
    candidates=w.civilians or ([w.random_char] if w.random_char in w.exists else [])
    found=next((ch for ch in candidates if ch in w.exists and ch not in w.dead and ch not in w.incar and ch not in w.attach and all(abs(w.coords(ch)[i]-vals[i])<=vals[i+3] for i in range(3))),-1)
    put(6,found)
   elif op==0x53e:
    found=next((car for car in w.traffic if car in w.exists and vals[0]<=w.cars[car]['pos'][0]<=vals[2] and vals[1]<=w.cars[car]['pos'][1]<=vals[3] and (vals[4]<0 or w.model[car]==vals[4])),-1)
    put(5,found)
   elif op==0x46c:put(1,w.seats.get((vals[0],-1),1 if (w.incar.get(1)==vals[0] and not getattr(w,'cj_is_passenger',False)) else -1))   # the driver's handle: an explicit one, else CJ when he sits in it (not as a passenger)
   elif op==0x432:
    assert (vals[0],vals[1]) in w.seats, 'empty passenger seat dereference'
    put(2,w.seats[(vals[0],vals[1])])
   elif op==0x3c0:put(1,w.incar.get(vals[0],-1))
   elif op==0x2e2:w.accuracy[vals[0]]=vals[1]
   elif op==0x7dd:w.attack_rate[vals[0]]=vals[1]
   elif op==0x107:
    new=w.next;w.next+=1;w.exists.add(new);w.objects=getattr(w,'objects',{});w.objects[new]=vals[1:4].copy();put(4,new)
   elif op==0x1bc:w.objects[vals[0]]=vals[1:4].copy()
   elif op==0x108:w.exists.discard(vals[0]);w.objects.pop(vals[0],None)
   elif op==0x750:pass
   elif op in [0xa5,0x129,0x9a,0x186,0x187]:
    w.create_calls+=1
    if op==0x9a and w.fail_create_after is not None and w.create_calls>=w.fail_create_after:put(len(aa)-1,-1);continue
    w.next+=1;new=w.next;put(len(aa)-1,new);w.exists.add(new);w.creator[new]=self.name;w.kind[new]={0xa5:'heli',0x129:'pilot',0x9a:'ped'}.get(op,'blip')
    if op==0xa5:w.model[new]=vals[0];w.cars[new]={'pos':vals[1:4].copy(),'heading':w.heading};w.current_car=new
    elif op==0x129:w.incar[new]=vals[0];w.skin[new]=vals[2]
    elif op==0x9a:w.pos[new]=[vals[2],vals[3],vals[4]+1.];w.skin[new]=vals[1];w.pedtype[new]=vals[0]   # CREATE_CHAR: z += 1.0 as in libGTASA (a ped's position is its centre, 1 m above its feet)
   elif op in [0x9b,0xa6]:w.exists.discard(vals[0]);w.incar.pop(vals[0],None);w.attach.pop(vals[0],None);w.cars.pop(vals[0],None)
   elif op==0x464:
    w.incar.pop(vals[0],None);w.attach[vals[0]]=(vals[1],vals[2:5].copy());w.weapons[vals[0]]=vals[-1]
   elif op==0x465:w.pos[vals[0]]=w.coords(vals[0]);w.attach.pop(vals[0],None)
   elif op in [0x36a,0x430]:w.attach.pop(vals[0],None);w.incar[vals[0]]=vals[1]
   elif op==0x362:w.note_teleport(0x362,vals[0],w.coords(vals[0]),vals[1:4]);w.pos[vals[0]]=vals[1:4].copy();w.incar.pop(vals[0],None);w.attach.pop(vals[0],None)
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
   elif op==0x6bc:w.bullet(vals[:3],vals[3:6],vals[6])
   elif op==0xe48:
    assert w.brain is not None,'0E48 was run without the brain mod: on the phone its parameters would be executed as code'
    assert aa[0][0]==3,'0E48 takes a local variable first'
    w.brain.exchange(self,aa[0][1],vals[1],vals[2])
   elif op==0xdd0:put(0,-vals[1])
   elif op==0xdf2:
    fields=self.raw[vals[0]+4:].split(b'\0');w.menu=fields[:2+vals[1]]
   elif op==0xdf3:w.menu=None
   elif op==0xdf4:put(0,w.events.popleft() if w.events else -1)
   elif op==0xde0:put(0,int(vals[1] in w.touches and w.now-w.touches[vals[1]]>=vals[2]))
   else:
    assert op in [0x33e,0x33f,0x340,0x342,0x344,0x81c,0x3f0,0x60b,0x1e5,0x247,0x38b,0x39f,0x1c5,0x8af,0x54a,0x446,0x77a,0x168,0x165,0x7e0,0x957,0x35f,0x825,0x918,0x7bb,0x249,0x4df,0x726,0x780,0x4a2,0x743,0x164,0x1c2,0x1c3,0x1b9,0x687,0x74d,0x5d3,0x4eb,0x637,0x667,0x792,0x619,0x83c,0x99a,0x4ba,0x668,0x713,0x6bc,0xaf,0x7db,0x4e4,0xad,0x853,0x337,0x4ed,0x605,0x614,0x393,0x634,0x7a5,0x856,0x350,0x5ba,0x639,0x5f5,0x78f,0x637,0x5c5],hex(op)
  raise AssertionError('loop without WAIT')
def invariants(w):
 """Beta 4: what must hold between any two frames, whatever was pressed and however often. Returns the list of violations.
 A living man made by the rope worker is in one of its four team slots, is the rope dummy, or is walking away in a LEAVE slot -
 so there is never a second team; none of them was handed to the game; one helicopter and one crew (two while a swap is under way)."""
 bad=[];alive=lambda h:h in w.exists and h not in w.dead
 ground=[h for h,who in w.creator.items() if who=='Helicover_Ground' and alive(h)]
 known={w.shared[b.GROUND_PUB+i] for i in range(5)}|{w.shared[b.LEAVE+k] for k in range(8)}
 orphans=[h for h in ground if h not in known and h not in w.released]
 if orphans:bad.append(('guards nobody owns',orphans))
 if w.handed:bad.append(('living guards handed to the game',list(w.handed)))
 helis=[h for h,k in w.kind.items() if k=='heli' and h in w.exists and h not in w.released_cars]   # a helicopter that was sent home is the game's
 if len(helis)>(2 if w.shared[b.STATE]==16 else 1):bad.append(('more than one helicopter',helis))
 crew=[h for h,k in w.kind.items() if w.creator.get(h)=='Helicover_Core' and k in ('pilot','ped') and alive(h) and h not in w.released]
 if len(crew)>(10 if w.shared[b.STATE] in (16,17) else 5):bad.append(('more than a pilot and four gunners',crew))
 if w.bullet_violations:bad.append(('rounds too close to CJ or to one of ours',w.bullet_violations[:3]))
 # 1.3: nobody of ours is given a task that fires the game's own weapon unless the brain has said "fire" to him, for that man, in that frame
 ours={w.shared[b.PUB+i] for i in range(2,7)}|{w.shared[b.GROUND_PUB+i] for i in range(5)}|({x[1] for x in w.brain.said} if w.brain is not None else set())
 leave={(t,who):(st,man) for t,who,st,man in (w.brain.said if w.brain is not None else [])}
 wild=[(t,hex(op),v[:2]) for t,op,v in w.calls if op in (0x74d,0x634,0x637,0x7a5,0x713) and v and v[0] in ours and leave.get((t,v[0]),(0,0))[0]!=2]
 wild+=[(t,hex(op),v[:2]) for t,op,v in w.calls if op==0x668 and v and v[0] in ours]   # fire at a place: nobody checks a line to a place
 if wild:bad.append(('a firing task without the brain\'s leave',wild[:3]))
 aimed=[(t,hex(op),v) for t,op,v in w.calls if op in (0x74d,0x634,0x7a5) and v and v[0] in ours and leave.get((t,v[0]),(0,0))[1]!=v[1]]+[(t,hex(op),v) for t,op,v in w.calls if op==0x637 and v and v[0] in ours and leave.get((t,v[0]),(0,0))[1]!=v[7]]
 if aimed:bad.append(('a firing task at somebody the brain did not name',aimed[:3]))
 return bad
def setup(panel=False):
 w=World();c=VM('Helicover_Core',w);p=VM('Helicover_Panel',w) if panel else None;v=[c]+([p] if p else []);w.step(*v,n=3);return w,c,p
def command(w,c,n,extra=None,ticks=5):w.shared[b.CMD]=n;w.step(c,*([extra] if extra else []),n=ticks)
def summon(w,c):
 command(w,c,1,ticks=8);assert w.shared[b.STATE]==2
 w.car=[0.,-45.,28.];w.shared[b.FOLLOW_NEXT]=0;w.speed=12.  # 1.2: it is created far away and flies in; the mock has no flight AI, so it 'arrives' here (a following helicopter is moving)

results=[]
def passed(t):results.append('PASS: '+t)
def calls(w,op):return [x for x in w.calls if x[1]==op]

def near_cj_landing(w,c):
 command(w,c,5,ticks=8)
 assert w.shared[b.STATE]==7
 w.car=[c.v[26],c.v[27],1.5];w.altitude=1.5;w.speed=0
 w.step(c,n=14)
 assert w.shared[b.STATE]==8

def fly_until(w,state,*vms,limit=600):
 # v33: the frozen helicopter keeps its own commanded height, so tests let it fly instead of teleporting it.
 for _ in range(limit):
  if w.shared[b.STATE]==state:return
  # v37: emulate the native pilot finishing the final hover descent once it owns the helicopter
  if w.shared[b.STATE]==22 and w.shared.get(b.DEST_NATIVE)==1 and not w.frozen.get(vms[0].v[5]):
   target=calls(w,0x4a2)[-1][2];w.car=list(target[1:4]);w.speed=0.
  w.step(*vms)
 raise AssertionError(('never reached',state,w.shared[b.STATE],w.messages))
def start_grove(w,c):
 near_cj_landing(w,c)
 w.player=w.car.copy()
 command(w,c,6,ticks=24)
 assert w.incar.get(1)==c.v[5] and w.shared[b.STATE]==9,(w.incar,w.shared[b.STATE],c.v[24])
 command(w,c,7,ticks=15)
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
assert w.frozen.get(car) and calls(w,0xab),'scripted cruise drives the helicopter'
w.car=[b.GROVE_X+150,b.GROVE_Y,75];w.step(c,n=3)
assert calls(w,0x4e4)[-1][2]==[b.GROVE_X,b.GROVE_Y]
assert calls(w,0x7bb)[-1][2]==[car,0] and calls(w,0xad)[-1][2]==[car,21.]
w.car=[b.GROVE_X+60,b.GROVE_Y,75];w.step(c,n=8)
assert w.shared[b.STATE]==22
w.speed=0;fly_until(w,23,c)
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
w.speed=0;fly_until(w,23,c);command(w,c,12,ticks=6)
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
w.car=[c.v[26]+8,c.v[27],15.];w.speed=0.;w.now+=26000;w.step(c,n=4)
assert len(calls(w,0x743))==2 and calls(w,0x743)[-1][2][4:]==[0.,0.]
w.step(c,n=15);assert len(calls(w,0x743))==2
passed('Final descent is ordered once after coming close and slow')

w,c,_=setup();summon(w,c);command(w,c,5,ticks=8);target=[c.v[x] for x in [26,27,28]]
w.shared[b.MODEL]=497;w.step(c,n=12)
assert w.model[c.v[5]]==497 and calls(w,0x743)[-1][2][1:4]==target
assert calls(w,0x7bb)[-1][2]==[c.v[5],0] and calls(w,0x853)[-1][2]==[c.v[5],3]
w.shared[b.CREW]=0;w.step(c,n=12);assert w.shared[b.ACREW]==0 and calls(w,0x743)[-1][2][1:4]==target
passed('Changing helicopter or crew resumes the same native landing')

w,c,p=setup(True);summon(w,c);launch=VM('Helicover',w);w.step(c,p,launch,n=15)
assert w.menu[0]==b'HELICOVER / FOLLOWING'
w.shared[b.CMD]=5;w.step(c,p,n=8);assert w.menu[0]==b'HELICOVER / EVAC INBOUND'
passed('Main menu updates the status in its title while it is open')

def fire_world():
 w,c,_=setup();summon(w,c);f=VM('Helicover_Fire',w);w.step(c,f,n=3);w.shared[b.FIRE]=3;return w,c,f
def threaten(w,*npcs,weapon=30):
 """Beta 6: PROTECT CJ engages a real threat only - arm the man and turn him to CJ (an armed gang member / policeman on foot, close, in sight)."""
 for npc in npcs:
  w.weapons[npc]=weapon;p=w.pos[npc];w.actor_heading[npc]=math.degrees(math.atan2(-(w.player[0]-p[0]),w.player[1]-p[1]))%360
def target(w,typ=4,skin=20):
 npc=900;w.exists.add(npc);w.pos[npc]=[20.,0.,0.];w.skin[npc]=skin;w.pedtype[npc]=typ;w.random_char=npc;return npc
def attacks(w):return w.bullets   # 1.3: the rounds the gunners let go (each one allowed by the brain); the game's shooting tasks are no longer used for them
def hit(w):return {x[1] for x in getattr(w,'hits',[])}
def aims(w,at=None):return [x for x in calls(w,0x667) if at is None or math.dist(x[2][1:4],w.coords(at))<.5]
def no_game_fire(w):
 """A door gunner never gets a task that fires the game's own weapon (nobody could check those rounds)."""
 crew={w.shared[b.PUB+i] for i in range(3,7)};return not [x for x in w.calls if x[1] in (0x74d,0x713,0x668,0x634,0x637,0x7a5) and x[2][0] in crew]
w,c,f=fire_world();npc=target(w);w.step(c,f,n=7);assert not attacks(w) and not aims(w),'a passer-by is nobody'
w.damage.add((1,npc));w.step(c,f,n=14);assert attacks(w) and hit(w)=={npc} and aims(w,npc) and no_game_fire(w) and not invariants(w),(len(attacks(w)),hit(w),invariants(w))
assert all(x[3]==b.ROUND_DAMAGE for x in attacks(w))
passed('The fire worker asks the brain: a passer-by is left alone; the man who hurts CJ gets the gunners\' weapons on him and their rounds (30 damage each, each one let go by the brain); no gunner is ever given a task that fires the game\'s own weapon')
w,c,f=fire_world();npc=target(w,typ=8,skin=105);threaten(w,npc);w.wanted=6;w.step(c,f,n=14);assert not attacks(w) and not aims(w)
w,c,f=fire_world();npc=target(w,typ=7,skin=102);threaten(w,npc);w.step(c,f,n=14);assert attacks(w) and hit(w)=={npc}
passed('Friends come from the game, not from a list of models: an armed Grove man looking at CJ is left alone, an armed Balla looking at CJ is engaged')
w,c,f=fire_world();w.shared[b.FIRE]=0;npc=target(w,typ=7);w.damage.add((1,npc));w.step(c,f,n=14);assert not attacks(w) and not aims(w)
w.shared[b.FIRE]=3;w.step(c,f,n=10);assert attacks(w)
w.shared[b.FIRE]=0;w.step(c,f,n=3);count=len(attacks(w));w.step(c,f,n=8);assert len(attacks(w))==count
passed('HOLD FIRE: no weapon comes up and no round goes, even at a man who has hurt CJ; with PROTECT ME they open fire, and HOLD FIRE stops them within 0.3 s')
w,c,f=fire_world();asked=len(calls(w,0xe48));assert asked;w.brain=None;w.shared[b.BRAIN_HELLO]=0;npc=target(w,typ=7);w.damage.add((1,npc));threaten(w,npc);w.step(c,f,n=14)
assert not attacks(w) and len(calls(w,0xe48))==asked and not aims(w),'without the answer to the handshake the opcode is never run'
passed('The brain mod gone: the fire worker never runs its opcode (an unregistered opcode would have its parameters executed as code) and nobody fires')
w,c,_=setup();w.brain=None;w.shared[b.BRAIN_HELLO]=0;command(w,c,1,ticks=10)
assert w.shared[b.STATE]==0 and 'HCNOBR' in w.messages and not calls(w,0xa5) and not calls(w,0x9a),(w.shared[b.STATE],w.messages)
command(w,c,14,ticks=10);assert w.shared[b.STATE]==0 and not calls(w,0xa5),'PATROL does not call it either'
w.brain=brain_mock.BrainSim();w.step(c,n=2);assert w.shared[b.BRAIN_HELLO]==b.BRAIN_MAGIC;command(w,c,1,ticks=8);assert w.shared[b.STATE]==2 and calls(w,0xa5)
w2=World();assert b.BRAIN_HELLO not in w2.shared;w2.brain.frame(w2);assert b.BRAIN_HELLO not in w2.shared,'the mod answers only in a value the scripts created'
passed('No brain, no Helicover: without the mod\'s answer to the handshake the helicopter is not called (CALL and PATROL), the player is told to install the mod, and nothing is created; with the mod it comes as before')

w,c,_=setup();summon(w,c);start_grove(w,c);w.car=[b.GROVE_X+60,b.GROVE_Y,75];w.step(c,n=8);assert w.shared[b.STATE]==22;w.speed=0;fly_until(w,23,c);command(w,c,12,ticks=6);w.car=[c.v[26],c.v[27],14.85];w.altitude=1.5;w.step(c,n=14)
assert w.shared[b.STATE]==12;command(w,c,8,ticks=5);assert 1 not in w.incar
w.player=[2400.,-1600.,13.]
for v in [13,14,15,16]:w.pos[c.v[v]]=w.player.copy()
w.onscreen=False;command(w,c,9,ticks=10)
assert w.shared[b.STATE]==2 and c.v[24]==3 and 1 not in w.incar
assert all(c.v[v] in w.attach for v in [13,14,15,16])
assert calls(w,0x918)[-1][2]==[c.v[5],1] and calls(w,0x726)[-1][2][1]==1
passed('All four onboard guards remain attached after Grove and follow takeoff')

w,c,_=setup();summon(w,c);start_grove(w,c);w.car=[b.GROVE_X+60,b.GROVE_Y,75];w.step(c,n=8);assert w.shared[b.STATE]==22;w.speed=0;fly_until(w,23,c);command(w,c,12,ticks=6);w.car=[c.v[26],c.v[27],14.85];w.altitude=1.5;w.step(c,n=14)
assert w.incar.get(1)==c.v[5] and w.shared[b.STATE]==12
before=len(calls(w,0x4a2));command(w,c,9,ticks=8)
assert w.shared[b.STATE]==12 and w.incar.get(1)==c.v[5] and 'HCEXIT' in w.messages and len(calls(w,0x4a2))==before
passed('Takeoff-follow requests CJ to exit; no unintended hover with CJ aboard')

w,c,_=setup();summon(w,c);f=VM('Helicover_Fire',w);w.step(c,f,n=3);w.shared[b.FIRE]=2;w.shooting=True
for npc,x,y in [(900,10.,8.),(901,50.,0.)]:w.exists.add(npc);w.pos[npc]=[x,y,0.];w.skin[npc]=20;w.pedtype[npc]=4
w.civilians=[900,901];w.targeting=901;w.step(c,f,n=14)
assert attacks(w) and hit(w)=={901} and not invariants(w),(hit(w),invariants(w))
passed('WHERE I SHOOT: the man CJ has locked on and is firing at is the gunners\' man, not the first passer-by near him')

w,c,p=setup(True);launch=VM('Helicover',w);w.step(c,p,launch,n=15)
assert w.menu[1]==b'CLOSE' and w.menu[2:]==[b'CALL HELICOPTER',b'SETTINGS >'],w.menu
summon(w,c);w.step(c,p,n=4)
assert w.menu[2:]==[b'FOLLOW ME [X]',b'HOLD HERE',b'PATROL AROUND ME',b'GUNNER FIRE >',b'CLIMB ABOARD BY ROPE',b'DEPLOY SQUAD',b'SETTINGS >',b'DISMISS HELICOPTER'],w.menu
w.incar[1]=c.v[5];w.step(c,p,n=4)
assert w.menu[2:]==[b'FLY TO MAP MARKER',b'FLY TO GROVE STREET',b'EXIT BUTTON: LAND [X]',b'EXIT BUTTON: ROPE',b'GUNNER FIRE >',b'SETTINGS >'],w.menu
passed('Main menu shows only what fits the moment: call it; on foot - three modes (marked), gunner fire, rope, squad, dismiss; aboard - destinations and the two exit-button switches')

w,c,f=fire_world();n=target(w);w.damage.add((1,n));w.step(c,f,n=12)
assert calls(w,0x6bc) and hit(w)=={n}
w.shared[b.FIRE]=0;w.step(c,f,n=5);count=len(calls(w,0x6bc));w.step(c,f,n=6);assert len(calls(w,0x6bc))==count
passed('Protect CJ and cease-fire remain active after aim and takeoff changes')

w,c,p=setup(True);summon(w,c);f=VM('Helicover_Fire',w);w.step(c,p,f,n=3);w.shared[b.FIRE]=3;w.step(c,p,f,n=5)
launch=VM('Helicover',w);w.step(c,p,f,launch,n=15);w.events.append(6);w.step(c,p,f,n=4);w.events.append(2);w.step(c,p,f,n=4)
assert w.menu[0]==b'HELICOVER / CREW WEAPON' and b'MP5' in w.menu,w.menu
w.events.append(1);w.step(c,p,f,n=12)
assert w.shared[b.WEAPON_SETTING]==29 and w.shared[b.WPN]==29
assert all(w.weapons[c.v[v]]==29 for v in [13,14,15,16]) and b'MP5 [X]' in w.menu
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
launch=VM('Helicover',w);w.step(c,p,fire,ground,launch,n=15)
assert b'CANCEL ROPE PICKUP' in w.menu and b'CLIMB ABOARD BY ROPE' not in w.menu and b'FLY TO GROVE STREET' not in w.menu,w.menu
passed('With CJ on foot and the rope out the rope row is the cancel, and there are no destinations')
w.random_char=squad[0];w.damage.add((1,squad[0]));w.shared[b.FIRE]=3;w.step(c,p,fire,ground,n=12)
assert squad[0] not in hit(w) and not attacks(w) and not aims(w)
passed('One of our own ground team is never a target, whatever the game says he did to CJ')
# Descent ends, then the additional guards follow their formation positions.
w.now+=8000;w.random_char=-1;w.step(c,p,fire,ground,n=5)
assert any(x[2][0] in squad for x in calls(w,0x5d3))
passed('Ground team receives CJ-relative formation tasks after descent')
# The existing worker chooses a hostile; ground guards receive the same target.
hostile=target(w,typ=7,skin=21);w.damage.add((1,hostile));w.step(c,p,fire,ground,n=22)
assert hit(w)=={hostile} and w.shared[b.FIRE_TARGET]==hostile and not [x for x in w.calls if x[1] in (0x74d,0x634,0x637,0x7a5,0x668) and x[2][0] in squad] and not invariants(w),(hit(w),w.shared[b.FIRE_TARGET],invariants(w))
passed('The rope worker gives its team no fire order of its own (only the squad worker, with the brain behind it, puts a guard on a man): the gunners deal with the man who hurt CJ, and the pilot is told who the fight is about')
# beta 4: FOLLOW while the cover team waits by the rope = the pickup is cancelled: the team climbs back up its ropes, then the helicopter follows
w.messages.clear();command(w,c,2,ticks=5);assert w.shared[b.STATE]==3 and all(x in w.exists for x in squad),'the helicopter waits for its men'
for _ in range(400):
 w.step(c,p,fire,ground)
 if w.shared[b.STATE]==2:break
assert w.shared[b.STATE]==2 and 'HCRCAN' in w.messages,(w.shared[b.STATE],w.messages)
assert all(x not in w.exists for x in squad) and not set(squad)&w.released and not w.handed and all(w.shared[b.GROUND_PUB+i]==-1 for i in range(4)) and not invariants(w),(w.handed,invariants(w))
passed('FOLLOW with the rope out cancels the pickup: the cover team climbs back aboard, then the helicopter follows - nobody is handed to the game')
# the helicopter is driven off (badly damaged) while the cover team is down: the men are let go - in view they put the guns away and walk off as ours
w,c,p=setup(True);summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0
fire=VM('Helicover_Fire',w);ground=VM('Helicover_Ground',w);w.step(c,p,fire,ground,n=5)
w.shared[b.ROPE_COMMAND]=1;w.step(c,p,fire,ground,n=6);squad=[w.shared[b.GROUND_PUB+i] for i in range(4)]
w.now+=8000;w.step(c,p,fire,ground,n=8);w.health[c.v[5]]=300;w.step(c,p,fire,ground,n=12)
assert w.shared[b.STATE]==13,w.shared[b.STATE]
assert all(x in w.exists and x not in w.released and x in w.wander and w.weapons[x]==0 for x in squad) and not w.handed,(w.released,w.wander,w.handed)
assert sorted(w.shared[b.LEAVE+k] for k in range(4))==sorted(squad) and w.shared[b.LEAVE_N]==1 and all(w.shared[b.GROUND_PUB+i]==-1 for i in range(4)) and not invariants(w),invariants(w)
passed('A team that is let go in view is never handed to the game: unarmed, walking away, still ours and no longer a target list entry')
w.onscreen=False;w.step(c,p,fire,ground,n=5)
assert all(x not in w.exists for x in squad) and w.shared[b.LEAVE_N]==0 and all(w.shared[b.LEAVE+k]==-1 for k in range(8)) and not w.handed
passed('The guards who were let go are removed as soon as nobody sees them')
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
w.messages.clear();command(w,c,2,ticks=2);w.step(c,ground,n=6)
assert w.shared[b.STATE]==3 and 'HCRBSY' in w.messages and w.control is False,(w.shared[b.STATE],w.messages)
w.step(c,ground,n=80);assert w.incar.get(1)==c.v[5] and w.control is True,(w.incar,w.messages)
passed('An order given during the ascent does not interrupt the rope work (beta 4): the pilot says wait and CJ arrives aboard')
w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0
ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=5)
w.now+=8000;w.player=[0.,-3.,.7];w.step(c,ground,n=8);assert w.control is False
w.health[c.v[5]]=300;w.step(c,ground,n=8)
assert w.shared[b.STATE]==13 and w.control is True and w.player[2]<2 and w.incar.get(1)!=c.v[5],(w.shared[b.STATE],w.control,w.player)
passed('A helicopter driven off during the ascent restores control and the last ground position')
# A failed animation task must not receive speed/time adjustments or leave control disabled.
w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0;w.animation_available=False
ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=5)
w.now+=8000;w.player=[0.,-3.,.7];stream_count=len(calls(w,0x38b));w.step(c,ground,n=85)
assert len(calls(w,0x38b))<=stream_count+1 and not calls(w,0x4ed)  # v32: one load for the rope platform
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
w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.;w.step(c,p,ground,n=40)   # 1.2: the glide eases out (about 2.3 s from 18 m), no hard stop
assert w.shared[b.STATE]==3 and len(calls(w,0x503))>=4, (w.shared[b.STATE],w.messages)
passed('Rope command approaches a clear site, then starts deployment when hovering')
# v38: without active support, evacuation commands ask for CALL SUPPORT instead of summoning.
for cmd in [5,7,10,11,12,13]:
 w,c,_=setup();ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.shared[b.CMD]=cmd;w.step(c,ground,n=12)
 assert w.shared[b.STATE]==0 and not calls(w,0xa5) and 'HCNEED' in w.messages,(cmd,w.shared[b.STATE],w.messages)
passed('Evacuation commands without support show CALL SUPPORT first and do not summon')
w,c,p=setup(True);launch=VM('Helicover',w);w.step(c,p,launch,n=15);assert b'CLIMB ABOARD BY ROPE' not in w.menu
w.events.append(0);w.step(c,p,n=12);assert w.shared[b.STATE] in (1,2),w.shared[b.STATE]
w.step(c,p,n=10);assert w.shared[b.STATE]==2 and b'CLIMB ABOARD BY ROPE' in w.menu,w.menu
w.events.append(4);w.step(c,p,n=12);assert w.shared[b.STATE]==19
passed('Without a helicopter the menu only offers CALL HELICOPTER; once it is here the rope pickup works')
# v38: every on-screen message key used by any script has text in Helicover.fxt
import build_all
assert not build_all.missing_keys(),build_all.missing_keys()
passed('All message keys used by the scripts exist in Helicover.fxt')
w,c,_=setup();summon(w,c);w.siteclear=False;ground=VM('Helicover_Ground',w);w.step(c,ground,n=3)
w.shared[b.CMD]=10;w.step(c,ground,n=6)
assert w.shared[b.STATE]!=19 and not calls(w,0x503)
passed('Rope approach rejects blocked sites without spawning the team')
# Min altitude is relative to terrain; max altitude is an absolute world height.
w,c,_=setup();w.player=[0.,0.,30.];w.ground_fn=lambda x,y,z:30.;summon(w,c);ground=VM('Helicover_Ground',w);w.step(c,ground,n=3)
w.shared[b.CMD]=10;w.step(c,ground,n=6);mission=calls(w,0x4a2)[-1][2]
assert mission[3:]==[45.,12.,45.],mission
w.car=[c.v[26]+4.,c.v[27],45.];w.speed=0.;w.step(c,ground,n=40)
assert w.shared[b.STATE]==3 and len(calls(w,0x503))>=4, (w.shared[b.STATE],w.messages)
passed('At elevated terrain, hovering 4m from pickup starts deployment at safe height')
assert len(calls(w,0x503))>=5 and w.shared[b.GROUND_PUB+4] in w.exists and w.now<ground.v[27]
passed('Fifth rope is created during guard descent rather than waiting for it to end')
w,c,_=setup();summon(w,c);w.car=[0.,-90.,28.];w.shared[b.CMD]=10;w.step(c,n=6);assert w.shared[b.STATE]==19
w.now+=36000;w.step(c,n=5);assert w.shared[b.STATE]==18 and 'HCRWAIT' in w.messages
passed('A stalled rope approach reports failure after 35 seconds')
# v27: inside 45 m the helicopter is frozen and glided by script to the hover point; no circling.
w,c,_=setup();summon(w,c);ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.car=[20.,-30.,40.];w.speed=9.
w.shared[b.CMD]=10;w.step(c,ground,n=4)
assert w.shared[b.FROZEN]==1 and w.frozen.get(c.v[5]),(w.shared[b.STATE],w.messages)
for _ in range(80):
 w.step(c,ground)
 if w.shared[b.STATE]!=19:break
assert w.shared[b.STATE]==3,(w.shared[b.STATE],w.messages)
hx,hy,hz=w.car;assert abs(hz-(c.v[28]+15.))<.05 and math.dist([hx,hy],[c.v[26],c.v[27]])<.05,(w.car,c.v[26:29])
w.step(c,ground,n=12);assert len(calls(w,0x503))>=4,w.messages
passed('Rope approach glides from 45 m to an exact hover without circling, compensating the z offset')
w,c,_=setup();summon(w,c);w.car=[0.,-200.,40.];w.shared[b.CMD]=10;w.step(c,n=6)
assert w.shared[b.STATE]==19 and not w.frozen.get(c.v[5]) and calls(w,0x4a2)[-1][2][1:3]==[c.v[26],c.v[27]]
passed('Beyond 45 m the native autopilot flies the approach at higher speed')
w,c,_=setup();summon(w,c);w.car=[0.,-30.,40.];w.los_fn=lambda a,z:not(abs(a[1]+30.)<.01 and abs(a[2]-40.)<.01);w.shared[b.CMD]=10;w.step(c,n=8)
assert w.shared[b.STATE]==19 and not w.frozen.get(c.v[5])
passed('An obstructed glide path keeps the native approach instead of teleporting through it')
# v28: downtown spawn is placed 20 m above the highest surface instead of inside a tower.
w,c,_=setup();w.ground_fn=lambda x,y,z:(120. if z>500 else 0.);summon(w,c)
spawn=calls(w,0xa5)[-1][2];assert spawn[3]>=140.,spawn
passed('Spawn height clears tall buildings')
# v28: a following helicopter that stops far from CJ for 5 s is lifted above the roofs.
w,c,_=setup();summon(w,c);w.calls.clear();w.teleports.clear();w.car=[0.,-80.,20.];w.speed=0.;w.step(c,n=3);assert not calls(w,0xab)
w.now+=5200;w.step(c,n=3)
climb=calls(w,0x4a2)[-1][2];assert not calls(w,0xab) and not w.teleports,(calls(w,0xab),w.teleports)   # 1.2: no teleport
assert climb[1:3]==[0.,-80.] and climb[3]>=30. and w.shared[b.FOLLOW_NEXT]>=w.now+5000,(climb,w.shared[b.FOLLOW_NEXT],w.now)
n_orders=len(calls(w,0x4a2));w.now+=6500;w.step(c,n=3);assert len(calls(w,0x4a2))>n_orders,'follow resumes after the climb'
passed('A wedged helicopter climbs out under its own power (no teleport) and resumes its order')
w,c,_=setup();summon(w,c);w.calls.clear();w.car=[0.,-10.,20.];w.speed=0.;w.step(c,n=3);w.now+=8000;w.step(c,n=3);assert not calls(w,0xab)
passed('A slow hover close to CJ is not mistaken for being stuck')
# 1.2: a dismissed helicopter is never deleted in view; one that cannot get away in 60 s is released and support can be called again.
w,c,_=setup();summon(w,c);w.onscreen=True;w.speed=0.;command(w,c,4,ticks=3);assert w.shared[b.STATE]==4
old=c.v[5];w.now+=30000;w.step(c,n=5);assert w.shared[b.STATE]==4 and old in w.exists,'on screen: not deleted (v28 removed it after 12 s in view)'
w.now+=31000;w.step(c,n=5);assert w.shared[b.STATE]==0 and old in w.exists and not calls(w,0xa6),(w.shared[b.STATE],)
command(w,c,1,ticks=8);assert w.shared[b.STATE]==2
passed('Dismiss: a helicopter that stays in view is never deleted; after 60 s it is released and a new call works')
# v28: rope descent starts 3 m below the helicopter centre (outside the hull) and still lands CJ.
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.shared[b.STATE]=23;w.car=[0.,0.,18.]
ground=VM('Helicover_Ground',w);w.step(c,ground,n=4);w.shared[b.DROP_COMMAND]=1;w.step(c,ground,n=40)
start=[x for x in calls(w,0x362) if x[2][0]==1][0][2];assert abs(start[3]-(18.-3.))<1e-4,start
assert w.control and 1 not in w.incar,(w.messages,)
passed('Rope descent starts below the hull and restores control on the ground')
# v32: an invisible platform follows 0.45 m below CJ's feet during the descent, then is removed.
plats=[x for x in calls(w,0x107) if x[2][0]==3095];moves=[x for x in calls(w,0x1bc)]
assert len(plats)==1 and calls(w,0x750) and len(moves)>20 and plats[0][2][4] not in w.exists
zs=[m[2][3] for m in moves];assert all(zs[i+1]<zs[i] for i in range(len(zs)-1)) and zs[0]-zs[-1]>8.,('v37: the platform descends on its own schedule like a lift',zs[:3],zs[-3:])
passed('Rope descent keeps an invisible platform under CJ so the game never starts free fall')
# v32: CJ is not lifted while any squad member is still above the ground, even at the rope.
w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0
ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=6)
squad=[w.shared[b.GROUND_PUB+i] for i in range(4)];w.ped_heights={squad[2]:6.}
w.now+=6000;w.player=[0.,-3.,.7];w.step(c,ground,n=10);assert w.control and w.incar.get(1)!=c.v[5]
w.ped_heights={};w.step(c,ground,n=10);assert w.control is False
passed('Pickup waits until every rope guard is on the ground')
# v33: CJ standing 1 m off the rope drifts onto it during the climb (no snap), then the four
# rope guards sprint back and rise together, all aboard within ~4 s of CJ.
w,c,_=setup();summon(w,c);command(w,c,3,ticks=5);w.car=[0.,0.,18.];w.speed=0
ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.shared[b.ROPE_COMMAND]=1;w.step(c,ground,n=6)
squad=[w.shared[b.GROUND_PUB+i] for i in range(4)]
w.now+=6000;w.player=[1.,-3.,.7]
for _ in range(80):
 w.step(c,ground)
 if w.incar.get(1)==c.v[5]:break
assert w.incar.get(1)==c.v[5] and not [x for x in calls(w,0xa1) if x[2][0]==1]
drift=[x for x in calls(w,0x83c) if x[2][0]==1 and x[2][3]>0];assert drift and drift[0][2][1]<0,'moves toward the rope'
assert abs(drift[0][2][3]-(18.-4.5-.7)/1.5)<.05,('v35: climb ends 4.5 m below the hull centre',drift[0][2][3])
aboard=w.now
for _ in range(80):
 w.step(c,ground)
 if all(ch not in w.exists for ch in squad):break
assert all(ch not in w.exists for ch in squad) and w.now-aboard<=4500,(w.now-aboard)
rises=[x for x in calls(w,0x83c) if x[2][0] in squad and x[2][3]>0]
starts={ch:min(x[0] for x in rises if x[2][0]==ch) for ch in squad};assert max(starts.values())-min(starts.values())<=100,starts
passed('Rope guards return together and fast; CJ drifts onto the rope without a snap')
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
 w.now+=5000;w.player=[0.,-3.,.7];w.frame_ms=frame_ms
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
 assert 1400 <= motion[-1][0]-motion[0][0] <= 1600,(frame_ms,motion[-1][0]-motion[0][0])  # v34: 1.5 s climb
 assert not [x for x in calls(w,0xa1) if x[2][0]==1]  # v33: no snap to the rope point
 assert all(abs(x[2][1])<1e-6 and abs(x[2][2])<1e-6 for x in motion)  # CJ already on the rope line in this test
 frames=[x[2][2] for x in calls(w,0x614) if x[2][0]==1]
 assert len(frames)>40 and frames[-1]<frames[1]
passed('CJ ascent advances smoothly over about 1.5 seconds at two frame rates')
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

# v31: the scripted cruise climbs in place until it clears tall roofs ahead.
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.speed=0.;w.ground_fn=lambda x,y,z:(200. if z>500 else 0.);command(w,c,7,ticks=2)   # from a hover (1.2: a moving helicopter would carry on ~2 m while braking)
x0,y0,z0=w.car;w.step(c,n=5);x1,y1,z1=w.car
assert w.shared[b.STATE]==10 and (x1,y1)==(x0,y0) and z1>z0,(w.car,x0,y0,z0)
passed('Cruise climbs in place before passing tall buildings')
# v31: open-sky cruise covers ~70 m/s and keeps 35 m above the highest surface.
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];command(w,c,7,ticks=2)
speeds=[]
for _ in range(60):
 p0=w.car.copy();w.step(c);speeds.append(math.dist(p0[:2],w.car[:2])/.1)
# v32: smooth start (no jump to full speed), monotonic acceleration while heading settles
assert speeds[1]<15. and max(abs(speeds[i+1]-speeds[i]) for i in range(len(speeds)-1))<4.,speeds[:20]
start=w.car.copy();w.step(c,n=10);moved=math.dist(start[:2],w.car[:2])
assert 60.<moved<75. and abs(w.car[2]-35.)<1.,(moved,w.car)
passed('Cruise accelerates smoothly to about 3x speed at a fixed clearance')

# Weapons remain selected during cease fire and while CJ is not shooting.
w,c,_=setup();summon(w,c);f=VM('Helicover_Fire',w);w.shared[b.FIRE]=0;w.step(c,f,n=15)
assert all(w.weapons[c.v[v]]==31 for v in [13,14,15,16])
w.shared[b.FIRE]=2;w.shooting=False;w.step(c,f,n=15)
assert all(w.weapons[c.v[v]]==31 for v in [13,14,15,16])
passed('Guards keep selected weapons in cease fire and without CJ shooting')

if b.MAP_MARKER:
 # Map flight snapshots the marker, reaches a hover, then allows a rope descent.
 w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.marker=[200.,150.,0.];ground=VM('Helicover_Ground',w);w.step(c,ground,n=3)
 command(w,c,11,ticks=8);assert w.shared[b.STATE]==21
 w.car=[205.,150.,80.];w.step(c,ground,n=8);assert w.shared[b.STATE]==22,(w.shared[b.STATE],w.messages)
 w.speed=0;fly_until(w,23,c,ground)
 command(w,c,13,ticks=3);w.step(c,ground,n=45)
 assert w.control and 1 not in w.incar and w.shared[b.STATE]==3,(w.shared[b.STATE],w.messages,w.control)
 assert all(c.v[i] in w.attach for i in [13,14,15,16])
 passed('Map marker -> hover -> selected rope descent restores CJ control and preserves onboard team')
 w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];command(w,c,11,ticks=6)
 assert w.shared[b.STATE]==2 and 'HCNOMAP' in w.messages
 passed('Map flight rejects an absent marker')
 assert all(x[2][1]==0x8BE7E8 for x in calls(w,0xdd8) if x[2][2]==4 and x[2][1]<0x8C0000 and x[2][1] not in dict(b.GAME_SIG)),calls(w,0xdd8)
 # other game builds: the start-up signature does not match -> no map reads, a clear message instead
 sig=b.GAME_SIG;b.GAME_SIG=[(sig[0][0],12345),sig[1]]
 w,c,_=setup();b.GAME_SIG=sig;summon(w,c);w.incar[1]=c.v[5];w.marker=[200.,150.,0.];w.calls.clear();command(w,c,11,ticks=6)
 assert w.shared[b.GAME_OK]==0 and w.shared[b.STATE]==2 and 'HCVER' in w.messages and not [x for x in calls(w,0xdd8) if x[2][1]==b.WAYPOINT_OFS],w.messages
 passed('On another game build the map marker is switched off with a message instead of reading foreign memory')
 for attr,val,name in [('wp_ref',8,'a stale waypoint handle'),('wp_flags',0x40,'an inactive radar trace')]:
  w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.marker=[200.,150.,0.];setattr(w,attr,val);command(w,c,11,ticks=6)
  assert w.shared[b.STATE]==2 and 'HCNOMAP' in w.messages
  passed('Map flight rejects '+name)
 w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.marker=[200.,150.,0.];command(w,c,11,ticks=6)
 assert [w.shared[b.DEST_X],w.shared[b.DEST_Y]]==[200.,150.] and not calls(w,0xab6)
 assert all(x[2][3]==1 for x in calls(w,0xdd8))
 passed('Map marker is read from libGTASA memory with 0DD8, never 0AB6')
 # v33: repeated FLY TO MAP MARKER with a one-frame teleport delay must not make the helicopter climb away.
 w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.speed=0.;w.marker=[2000.,150.,0.];w.teleport_delay=True   # from a hover
 for _ in range(3):command(w,c,11,ticks=40)
 heights=[]
 for _ in range(200):w.step(c);heights.append(w.car[2])
 assert max(heights)<40. and max(heights[-100:])-min(heights[-100:])<.5,(max(heights),heights[-100:][:3],heights[-1])
 passed('Repeated map flight with delayed teleports keeps a steady cruise height')
 # v36: a marker read outside the map (or NaN) is rejected before any world query
 for bad in [[9999.,0.,0.],[float('nan'),0.,0.]]:
  w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.marker=bad;command(w,c,11,ticks=6)
  assert w.shared[b.STATE]==2 and 'HCNOMAP' in w.messages
 passed('Off-map or NaN marker coordinates are rejected')
 # v36: diagnostic breadcrumbs show the state and step (21xx while cruising to the marker)
 w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.marker=[800.,150.,0.];command(w,c,11,ticks=10)
 if b.DEBUG_BREADCRUMBS:
  assert any(2101<=d<=2102 for d in getattr(w,'debug',[])),getattr(w,'debug',None)
  passed('Diagnostic breadcrumbs report the cruise step')
 else:
  assert not calls(w,0x1e5);passed('Release build shows no DBG breadcrumbs')
else:
 w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.marker=[200.,150.,0.];command(w,c,11,ticks=6)
 assert w.shared[b.STATE]==2 and 'HCMAPOF' in w.messages and not calls(w,0xab6)
 passed('Disabled map marker flight reports instead of executing 0AB6')
# Four attackers, two on each side of the helicopter: every gunner gets a man of his own (the brain shares them out; a door gunner
# cannot fire across his own cabin, so the men on the other side are his mates' business).
w,c,f=fire_world();w.civilians=[]
for npc,x,y in [(900,-12.,10.),(901,12.,10.),(902,-15.,-85.),(903,15.,-85.)]:
 w.exists.add(npc);w.pos[npc]=[x,y,0.];w.skin[npc]=102;w.pedtype[npc]=7;w.weapons[npc]=30;w.health[npc]=100000;w.civilians.append(npc);w.damage.add((1,npc))
w.step(c,f,n=25)
gunners=[w.shared[b.PUB+i] for i in range(3,7)];men={}
for r in w.brain.rounds:
 if r.verdict==0 and r.ray:men.setdefault(r.who,set()).add(r.target)
assert set(men)==set(gunners) and all(len(v)==1 for v in men.values()) and set().union(*men.values())=={900,901,902,903} and hit(w)=={900,901,902,903} and not invariants(w),(men,hit(w),invariants(w))
assert all(x[3]==b.ROUND_DAMAGE for x in attacks(w))
passed('Four attackers, two on each side of the helicopter: each of the four gunners has a man of his own and hits him')

if b.MAP_MARKER:
 # Search a nearby landing candidate when the exact map marker is obstructed.
 w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.marker=[200.,150.,0.];w.clear_fn=lambda x,y:not(abs(x-200.)<.2 and abs(y-150.)<.2)
 command(w,c,11,ticks=8);assert w.shared[b.STATE]==21;w.car=[205.,150.,80.];w.step(c,n=8)
 assert w.shared[b.STATE]==22 and (w.shared[b.DEST_X],w.shared[b.DEST_Y])!=(200.,150.)
 passed('Map destination searches a nearby clear landing footprint')
else:
 pass
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
w,c,_=setup();summon(w,c);w.car=[200.,0.,25.];w.speed=20.;before=len(calls(w,0x726));w.now+=5000;w.step(c,n=8)   # moving: not 'wedged'
assert len(calls(w,0x726))>before
passed('Follow reissues its order if the helicopter is far from CJ')

if b.MAP_MARKER:
 # A marked destination can also be landed at after the hover choice.
 w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.marker=[200.,150.,0.];command(w,c,11,ticks=8);assert w.shared[b.STATE]==21
 w.car=[205.,150.,80.];w.step(c,n=8);assert w.shared[b.STATE]==22
 w.speed=0;fly_until(w,23,c)
 command(w,c,12,ticks=6);assert w.shared[b.STATE]==11
 w.car=[w.shared[b.DEST_X],w.shared[b.DEST_Y],w.shared[b.DEST_Z]+1.5];w.altitude=1.5;w.step(c,n=15)
 assert w.shared[b.STATE]==12 and w.incar.get(1)==c.v[5]
 passed('Marked destination hover -> choose landing preserves CJ aboard')
else:
 pass
# Three armed men looking at CJ: a Balla, a Grove man and one of our own ground team. Only the Balla is a target.
w,c,f=fire_world();w.civilians=[]
for npc,x,y,skin,typ in [(900,15.,10.,102,7),(901,-12.,10.,105,8),(902,12.,-10.,285,8)]:
 w.exists.add(npc);w.pos[npc]=[x,y,0.];w.skin[npc]=skin;w.pedtype[npc]=typ;w.civilians.append(npc)
threaten(w,900,901,902);w.shared[b.GROUND_PUB]=902;w.step(c,f,n=20)
assert hit(w)=={900} and not invariants(w) and {r.target for r in w.brain.rounds}=={900},(hit(w),invariants(w))
passed('Three armed men looking at CJ - a Balla, a Grove man and one of our ground team: only the Balla is engaged')

# Menu dispatch for patrol and map flight.
w,c,p=setup(True);summon(w,c);launch=VM('Helicover',w);w.step(c,p,launch,n=15)
for idx,st,row in [(1,3,b'HOLD HERE [X]'),(2,24,b'PATROL AROUND ME [X]'),(0,2,b'FOLLOW ME [X]')]:
 w.events.append(idx);w.step(c,p,n=12);assert w.shared[b.STATE]==st and row in w.menu and sum(1 for r in w.menu if r.endswith(b'[X]'))==1,(st,w.shared[b.STATE],w.menu)
passed('Three explicit mode rows: FOLLOW ME / HOLD HERE / PATROL AROUND ME - one tap each, the active one marked [X]')
if b.MAP_MARKER:
 w,c,p=setup(True);summon(w,c);w.incar[1]=c.v[5];w.marker=[200.,150.,0.];launch=VM('Helicover',w);w.step(c,p,launch,n=15)
 assert w.menu[2]==b'FLY TO MAP MARKER';w.events.append(0);w.step(c,p,n=12);assert w.shared[b.STATE]==21
 passed('CLEO evacuation menu starts the marked route')

# v31: a blocked cruise segment never teleports through geometry; it climbs instead.
w,c,_=setup();summon(w,c);start_grove(w,c);w.los_fn=lambda a,z:False;x0,y0,z0=w.car;w.step(c,n=3)
assert (w.car[0],w.car[1])==(x0,y0) and w.car[2]>z0 and w.shared[b.STATE]==10
passed('Blocked cruise segment climbs in place instead of passing through')
# v37: the cruise brings the helicopter exactly overhead, then the native pilot descends (no frozen teleports near roofs).
w,c,_=setup();summon(w,c);start_grove(w,c);w.car=[b.GROVE_X+60,b.GROVE_Y,75];w.step(c,n=8);assert w.shared[b.STATE]==22
for _ in range(200):
 w.step(c)
 if w.shared.get(b.DEST_NATIVE)==1:break
assert w.shared[b.DEST_NATIVE]==1 and not w.frozen.get(c.v[5]) and w.shared[b.FROZEN]==0
assert math.dist(w.car[:2],[w.shared[b.DEST_X],w.shared[b.DEST_Y]])<1.
mission=calls(w,0x4a2)[-1][2];assert mission[1:4]==[w.shared[b.DEST_X],w.shared[b.DEST_Y],w.shared[b.DEST_Z]+18.] and calls(w,0x853)[-1][2][1]==10 and calls(w,0x4ba)[-1][2][1]==0.
w.step(c,n=5);assert w.shared[b.STATE]==22,'still descending'
w.car=list(mission[1:4]);w.speed=0.;w.step(c,n=3);assert w.shared[b.STATE]==23 and not w.frozen.get(c.v[5])
passed('Destination: scripted cruise to overhead, then native vertical descent to 18 m')
# v37: if the native descent stalls, the hover is accepted after 25 s when close enough.
w,c,_=setup();summon(w,c);start_grove(w,c);w.car=[b.GROVE_X+60,b.GROVE_Y,75];w.step(c,n=8)
for _ in range(200):
 w.step(c)
 if w.shared.get(b.DEST_NATIVE)==1:break
w.now+=26000;w.step(c,n=3);assert w.shared[b.STATE]==23
passed('A stalled native descent still offers LAND / ROPE after 25 s')

# The pilot brings a distant active target into view while following CJ.
w,c,f=fire_world();npc=target(w,typ=7,skin=20);w.damage.add((1,npc));w.step(c,f,n=25)
assert not calls(w,0x780),'0780 keeps a dangling ped pointer; never use it'
assert w.shared[b.TRACKED_TARGET]==npc and calls(w,0x4a2),calls(w,0x4a2)
passed('Pilot can reposition to keep an active threat in view')
# A player follow order cancels an active cruise detour.
w,c,_=setup();summon(w,c);start_grove(w,c);w.los_fn=lambda a,z:not (abs(z[0]-a[0])<.1 and z[1]-a[1]>30.)
w.step(c,n=5);assert w.frozen.get(c.v[5])
# CJ is aboard, so a HOLD order cancels the cruise without ejecting CJ.
command(w,c,3,ticks=8);assert w.shared[b.STATE]==3 and not w.frozen.get(c.v[5]) and w.incar.get(1)==c.v[5]
passed('New hold command stops the scripted cruise without ejecting CJ')

# ---- v39: exit button and exit mode ----
def to_destination(w,c,*vms):
 w.incar[1]=c.v[5];w.marker=[200.,150.,0.];command(w,c,11,ticks=8);assert w.shared[b.STATE]==21
 w.car=[205.,150.,80.];w.step(c,*vms,n=8);fly_until(w,23,c,*vms)
# menu (beta 4): the two EXIT BUTTON rows are switches for the game's own exit button - they start nothing themselves
w,c,p=setup(True);summon(w,c);w.incar[1]=c.v[5];launch=VM('Helicover',w);w.step(c,p,launch,n=15)
assert b'EXIT BUTTON: LAND [X]' in w.menu and b'EXIT BUTTON: ROPE' in w.menu and b'GET OUT HERE' not in w.menu,w.menu
w.events.append(5);w.step(c,p,n=5);assert w.menu==[b'HELICOVER / SETTINGS',b'CLOSE',b'CREW >',b'HELICOPTER MODEL >',b'CREW WEAPON >',b'SQUAD TACTICS: GUARD',b'MESSAGES: ALL',b'GUNNERS: KNEELING',b'< BACK'] and not any(b'EXIT' in r or b'LANGUAGE' in r for r in w.menu),w.menu
w.events.append(6);w.step(c,p,n=5);assert w.menu[0]==b'HELICOVER / FOLLOWING',w.menu
st=w.shared[b.STATE];pos=list(w.car)
for idx,mode,row,key in [(3,1,b'EXIT BUTTON: ROPE [X]','HCXBR'),(3,1,b'EXIT BUTTON: ROPE [X]','HCXBR'),(2,0,b'EXIT BUTTON: LAND [X]','HCXBL'),(2,0,b'EXIT BUTTON: LAND [X]','HCXBL'),(3,1,b'EXIT BUTTON: ROPE [X]','HCXBR')]:
 w.calls.clear();w.messages.clear();w.shared[b.MSG_UNTIL]=0;w.events.append(idx);w.step(c,p,n=12)
 assert w.shared[b.EXIT_MODE]==mode and row in w.menu and sum(1 for r in w.menu if r.endswith(b'[X]'))==1,(idx,w.shared[b.EXIT_MODE],w.menu)
 assert not any(x[2][0]==b.CMD and x[2][1]!=0 for x in calls(w,0xddc)) and w.shared[b.STATE]==st and w.shared[b.AUTO_EXIT]==0 and w.shared[b.DROP_COMMAND]==0 and w.incar.get(1)==c.v[5],'a switch row gives no order: no exit, no landing, no rope'
 assert key in w.messages,(key,w.messages)
passed('Aboard, the two EXIT BUTTON rows only switch what the exit button does (hint shown, [X] moves): no order, no exit; settings has no exit or language row')
# doors are locked against the player while CJ is aboard, unlocked when he is outside
w,c,_=setup();summon(w,c);w.step(c,n=3);assert w.locks.get(c.v[5])==1
w.incar[1]=c.v[5];w.step(c,n=3);assert w.locks[c.v[5]]==4
passed('Doors lock while CJ is aboard so the native exit cannot drop him')
# exit button over the destination, ROPE mode -> rope descent starts at once
w,c,_=setup();summon(w,c);ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);to_destination(w,c,ground)
w.shared[b.EXIT_MODE]=1;w.widget_released=b.EXIT_WIDGET;w.step(c,ground,n=45)
assert any(x[2][0]==1 for x in calls(w,0x362)) and w.control and 1 not in w.incar,(w.messages,)
passed('Exit button over the destination in ROPE mode starts the rope descent')
# exit button over the destination, LAND mode -> lands, then CJ leaves automatically
w,c,_=setup();summon(w,c);to_destination(w,c)
w.shared[b.EXIT_MODE]=0;w.widget_released=b.EXIT_WIDGET;w.step(c,n=4);assert w.shared[b.STATE]==11
w.car=[w.shared[b.DEST_X],w.shared[b.DEST_Y],w.shared[b.DEST_Z]+1.5];w.altitude=1.5;w.step(c,n=20)
assert w.shared[b.STATE]==12 and calls(w,0x5cd) and calls(w,0x5cd)[-1][2][:2]==[1,c.v[5]] and w.locks[c.v[5]]==1,(w.shared[b.STATE],w.messages)
passed('Exit button over the destination in LAND mode lands and then lets CJ out')
# v39.2 / 1.2: exit button in flight, ROPE mode -> the helicopter slows down on the way (a point ahead, no dead stop), then freezes and CJ abseils
w,c,_=setup();summon(w,c);ground=VM('Helicover_Ground',w);w.incar[1]=c.v[5];w.marker=[1500.,150.,0.];command(w,c,11,ticks=8)
w.step(c,ground,n=20);start=w.car.copy();cruise=w.shared[b.CR_V];assert cruise>8.,cruise
w.shared[b.EXIT_MODE]=1;w.widget_released=b.EXIT_WIDGET;w.step(c,ground,n=3)
assert w.shared[b.STATE] in (21,22) and 'HCXHERE' in w.messages and not [x for x in calls(w,0x362) if x[2][0]==1],(w.shared[b.STATE],w.messages)
fly_until(w,23,c,ground,limit=900);here=w.car.copy()
assert 8.<math.dist(here[:2],start[:2])<130.,(here,start)
w.step(c,ground,n=3)
drop=[x for x in calls(w,0x362) if x[2][0]==1];assert w.frozen.get(c.v[5]) and drop and math.dist(drop[0][2][1:3],here[:2])<4.,(drop,here)
w.step(c,ground,n=80);assert 1 not in w.incar and w.control and w.shared[b.ROPE_PENDING]==0,(w.messages,)
passed('Exit button in flight (ROPE): the helicopter slows down on the way, stops, and CJ abseils')
# the abseil time scales with the height: ~6 m/s, 2-6 s
motion=[x for x in calls(w,0x83c) if x[2][0]==1 and x[2][3]<0];span=motion[-1][0]-motion[0][0]
height=here[2]-3.-.7;expected=min(6000.,max(2000.,height*1000./6.))
assert abs(span-expected)<=200 and abs(-motion[0][2][3]-height*1000./expected)<.05,(span,expected,motion[0][2][3])
passed('Abseil duration scales with the height (2-6 s)')
# exit button in flight, LAND mode -> find a spot below, land, CJ leaves
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.marker=[1500.,150.,0.];command(w,c,11,ticks=8)
w.step(c,n=20);here=w.car[:2];w.shared[b.EXIT_MODE]=0;w.widget_released=b.EXIT_WIDGET;w.step(c,n=2)
assert w.shared[b.AUTO_EXIT]==1 and 'HCXHERE' in w.messages and 5.<math.dist([w.shared[b.DEST_X],w.shared[b.DEST_Y]],here)<=105.   # 1.2: a spot ahead where the cruise slows down
fly_until(w,11,c);assert w.shared[b.STATE]==11
passed('Exit button in flight (LAND): finds a spot ahead (the cruise slows down on the way) and starts the landing')
# exit button on the ground -> CJ simply leaves
w,c,_=setup();summon(w,c);to_destination(w,c);command(w,c,12,ticks=6)
w.car=[w.shared[b.DEST_X],w.shared[b.DEST_Y],w.shared[b.DEST_Z]+1.5];w.altitude=1.5;w.step(c,n=20);assert w.shared[b.STATE]==12
before=len(calls(w,0x5cd));w.widget_released=b.EXIT_WIDGET;w.step(c,n=3);assert len(calls(w,0x5cd))>before
passed('Exit button after landing lets CJ out')
# ---- v39b: robust exit ----
# a failed rope drop repositions and retries silently, then succeeds
w,c,_=setup();summon(w,c);ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);to_destination(w,c,ground)
w.shared[b.EXIT_MODE]=1;w.siteclear=False;before=len(calls(w,0x4a2));w.widget_released=b.EXIT_WIDGET;w.step(c,ground,n=6)
assert w.shared[b.ROPE_TRIES]==1 and len(calls(w,0x4a2))>before and 'RPDFAIL' not in w.messages and 1 in w.incar,(w.shared[b.ROPE_TRIES],w.messages)
retry=calls(w,0x4a2)[-1][2];assert math.dist(retry[1:3],[w.shared[b.DEST_X],w.shared[b.DEST_Y]])>5.
w.siteclear=True;w.car=list(retry[1:4]);w.now+=3600;w.step(c,ground,n=45)
assert any(x[2][0]==1 for x in calls(w,0x362)) and 1 not in w.incar and 'RPDFAIL' not in w.messages,(w.messages,)
passed('A blocked rope drop moves a few metres and retries automatically')
# five failed attempts end with one RPDFAIL message
w,c,_=setup();summon(w,c);ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);to_destination(w,c,ground)
w.shared[b.EXIT_MODE]=1;w.siteclear=False;w.widget_released=b.EXIT_WIDGET
for _ in range(8):w.step(c,ground,n=4);w.now+=3600
w.step(c,ground,n=6);assert w.messages.count('RPDFAIL')==1 and w.shared[b.ROPE_PENDING]==0 and 1 in w.incar,(w.messages,w.shared[b.ROPE_TRIES])
passed('After five failed rope attempts the player gets one clear message and stays aboard')
# LAND mode where the site is not landable -> rope instead
w,c,_=setup();summon(w,c);ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);to_destination(w,c,ground)
w.shared[b.EXIT_MODE]=0;w.clear_fn=lambda x,y:False;w.widget_released=b.EXIT_WIDGET;w.step(c,ground,n=4)
assert 'HCXROPE' in w.messages and w.shared[b.STATE]==23 and w.shared[b.ROPE_PENDING]==1,(w.messages,w.shared[b.STATE])
w.clear_fn=lambda x,y:True;w.step(c,ground,n=45);assert any(x[2][0]==1 for x in calls(w,0x362)) and 1 not in w.incar
passed('LAND mode falls back to the rope when there is no place to land')
# no flat pad near the marker -> still hover over it (rope possible) instead of LAND_BLOCKED
w,c,_=setup();summon(w,c);w.incar[1]=c.v[5];w.marker=[200.,150.,0.];w.los_fn=lambda a,z:not(abs(a[0]-z[0])<.01 and abs(a[1]-z[1])<.01);command(w,c,11,ticks=8)
w.car=[205.,150.,80.];w.step(c,n=8);w.now+=13000;w.step(c,n=8)
assert w.shared[b.STATE]==22 and 'HCNOPAD' in w.messages and 'HCBLOCK' not in w.messages,(w.shared[b.STATE],w.messages)
fly_until(w,23,c);passed('No flat pad near the marker: hover over it for a rope exit instead of giving up')
# v39.3: the exit widget's release lasts one frame; the core ticks every 100 ms. Without the
# per-frame fire worker the press is missed (the user's "works on the 3rd press"); with it the
# first press is caught, and a second press within 1.5 s does not start another exit.
def one_press(w,c,*vms):
 w.frame_ms=16;w.step(c,*vms,n=1)
 for _ in range(10):
  if c.wake>w.now+16:break
  w.step(c,*vms,n=1)
 w.release_frame=w.now+16;w.step(c,*vms,n=1);w.release_frame=-1
w,c,_=setup();summon(w,c);ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);to_destination(w,c,ground)
w.shared[b.EXIT_MODE]=1;one_press(w,c,ground);w.step(c,ground,n=30)
assert w.shared[b.ROPE_PENDING]==0 and 1 in w.incar,'core alone misses a one-frame press'
w,c,_=setup();summon(w,c);ground=VM('Helicover_Ground',w);f=VM('Helicover_Fire',w);w.step(c,ground,f,n=3);to_destination(w,c,ground,f)
w.shared[b.EXIT_MODE]=1;one_press(w,c,ground,f);w.step(c,ground,f,n=30)
assert any(x[2][0]==1 for x in calls(w,0x362)),'first press starts the abseil'
cmds=w.shared[b.EXIT_LAST];one_press(w,c,ground,f);w.step(c,ground,f,n=5);assert w.shared[b.EXIT_LAST]==cmds,'debounced'
passed('Exit works on the first press: per-frame polling of the one-frame widget release, with debounce')
# v39.2: rope evacuation hangs the rope 6 m in front of CJ; standing still never lifts him
w,c,_=setup();summon(w,c);ground=VM('Helicover_Ground',w);w.step(c,ground,n=3);w.car=[0.,-30.,40.]
w.shared[b.CMD]=10
for _ in range(120):
 w.step(c,ground)
 if w.shared[b.STATE]==3 and calls(w,0x503):break
assert w.shared[b.STATE]==3,(w.shared[b.STATE],w.messages)
rope=[w.car[0],w.car[1]-3.];assert 5.<math.dist(rope,w.player[:2])<7.,(rope,w.player)
w.now+=8000;w.step(c,ground,n=20);assert w.control and w.incar.get(1)!=c.v[5],'standing still: not lifted'
w.player=[rope[0],rope[1],.7];w.step(c,ground,n=10);assert w.control is False,'walked to the rope: lifted'
passed('Rope evacuation lifts CJ only after he walks to the rope (6 m away)')
# ---- v39-fire: fire control upgrade ----
# menu order and value mapping
w,c,p=setup(True);summon(w,c);launch=VM('Helicover',w);w.step(c,p,launch,n=15);w.events.append(3);w.step(c,p,n=5)
assert w.menu[0]==b'HELICOVER / GUNNER FIRE' and w.menu[2:]==[b'PROTECT ME [X]',b'ARMED ONLY',b'WHERE I SHOOT',b'HOLD FIRE',b'POLICE: FIRE BACK',b'MISSIONS: DEFEND ONLY',b'< BACK'],w.menu
for idx,val in [(3,0),(1,4),(2,2),(0,3)]:
 w.events.append(idx);w.step(c,p,n=5);assert w.shared[b.FIRE]==val and [r for r in w.menu if r.endswith(b'[X]')]==[w.menu[2+idx]],(idx,val,w.shared[b.FIRE],w.menu)
assert w.shared[b.POLICE]==0 and w.shared[b.MISSIONS]==0
w.events.append(4);w.step(c,p,n=5);assert w.shared[b.POLICE]==1 and w.menu[6]==b'POLICE: NEVER FIRE' and w.menu[2]==b'PROTECT ME [X]',w.menu
w.events.append(5);w.step(c,p,n=5);assert w.shared[b.MISSIONS]==1 and w.menu[7]==b'MISSIONS: AS USUAL' and w.menu[6]==b'POLICE: NEVER FIRE',w.menu
w.events.append(4);w.step(c,p,n=5);w.events.append(5);w.step(c,p,n=5);assert (w.shared[b.POLICE],w.shared[b.MISSIONS])==(0,0) and w.menu[6:8]==[b'POLICE: FIRE BACK',b'MISSIONS: DEFEND ONLY'],w.menu
w.events.append(6);w.step(c,p,n=5);assert w.menu[0]==b'HELICOVER / FOLLOWING'
passed('GUNNER FIRE page: four rules - PROTECT ME (default), ARMED ONLY, WHERE I SHOOT, HOLD FIRE (the old FIRE AT ALL is gone) - and two switches: POLICE fire back / never fire, MISSIONS defend only / as usual; BACK returns to the main page')
w.events.append(7);w.step(c,p,n=5);assert w.menu[0]==b'SEND THE HELICOPTER AWAY?' and w.shared[b.STATE]==2
w.events.append(1);w.step(c,p,n=5);assert w.shared[b.STATE]==2 and w.menu[0]==b'HELICOVER / FOLLOWING'
w.events.append(7);w.step(c,p,n=5);w.events.append(0);w.step(c,p,n=8);assert w.shared[b.STATE]==4,w.shared[b.STATE]
passed('DISMISS HELICOPTER asks for confirmation; NO keeps it, YES sends it away')
# ARMED ONLY: besides whoever threatens or attacks CJ, every armed man of a hostile kind in sight - even one who is looking the other way.
# An armed civilian is not a hostile kind; an unarmed gang member is not armed.
w,c,f=fire_world();w.shared[b.FIRE]=4;w.step(c,f,n=3);npc=target(w,typ=7,skin=102);w.weapons[npc]=0;w.step(c,f,n=15)
assert not attacks(w),'an unarmed gang member is not a target'
w.weapons[npc]=30;w.actor_heading[npc]=270.;w.step(c,f,n=20)      # armed, his back to CJ
assert attacks(w) and hit(w)=={npc} and not invariants(w)
w,c,f=fire_world();npc=target(w,typ=7,skin=102);w.weapons[npc]=30;w.actor_heading[npc]=270.;w.step(c,f,n=20)
assert not attacks(w) and aims(w,npc),'PROTECT ME: the same man is covered - weapons on him - but not fired at'
w,c,f=fire_world();w.shared[b.FIRE]=4;npc=target(w,typ=4);w.weapons[npc]=30;w.actor_heading[npc]=270.;w.step(c,f,n=20);assert not attacks(w) and not aims(w),'an armed civilian is nobody\'s target'
passed('ARMED ONLY: an armed gang member is engaged even with his back to CJ (PROTECT ME only covers him); unarmed gang members and armed civilians are not targets')
# police: without stars nobody; with stars a policeman is fired at only once he has fired himself ("fire back"), and never with POLICE: NEVER FIRE
w,c,f=fire_world();w.shared[b.FIRE]=4;w.step(c,f,n=3);npc=target(w,typ=6,skin=280);threaten(w,npc,weapon=22);w.step(c,f,n=15);assert not attacks(w) and not aims(w)
w.wanted=2;w.step(c,f,n=15);assert not attacks(w) and aims(w,npc),'stars up: weapons on him, no fire yet'
w.shooting_chars={npc};w.step(c,f,n=3);w.shooting_chars=set();w.step(c,f,n=12);assert attacks(w) and hit(w)=={npc} and not invariants(w)
w,c,f=fire_world();w.shared[b.POLICE]=1;w.wanted=2;npc=target(w,typ=6,skin=280);threaten(w,npc,weapon=22);w.shooting_chars={npc};w.step(c,f,n=3);w.shooting_chars=set();w.step(c,f,n=15);assert not attacks(w)
passed('Police: without stars a policeman is nobody; with stars he is covered and fired at only after he has fired (POLICE: FIRE BACK); with POLICE: NEVER FIRE not even then')
# callouts: contact, kill counter, area clear, mode report
w,c,f=fire_world();w.step(c,f,n=3);w.shared[b.MSG_UNTIL]=0;npc=target(w,typ=7,skin=102);w.health[npc]=70;w.damage.add((1,npc))
for _ in range(30):
 w.step(c,f)
 if npc in w.dead:break
assert npc in w.dead and 'HCCONT' in w.messages and w.messages.count('HCCONT')==1,w.messages
w.step(c,f,n=5);assert w.shared[b.KILLS]==1 and 1 in getattr(w,'debug',[]),(w.shared[b.KILLS],getattr(w,'debug',None))
assert 'HCCLEAR' not in w.messages;w.step(c,f,n=40);assert 'HCCLEAR' in w.messages and w.messages.count('HCCONT')==1 and w.shared[b.ENGAGED]==0,w.messages
w.shared[b.FIRE]=4;w.step(c,f,n=3);w.shared[b.FIRE]=2;w.step(c,f,n=3);w.shared[b.FIRE]=0;w.step(c,f,n=3);w.shared[b.FIRE]=3;w.step(c,f,n=3)
assert [m for m in w.messages if m.startswith('HCFM')]==['HCFM4','HCFM2','HCFM0','HCFM3'],w.messages
passed('Gunner callouts: CONTACT once when somebody attacks, TARGET DOWN with the kill count when a man dies under their fire, AREA CLEAR 3 s after the last dangerous man is gone, and a report for each fire rule')
w,c,f=fire_world();w.shared[b.HUD]=0;npc=target(w,typ=7,skin=102);w.health[npc]=70;w.damage.add((1,npc));w.step(c,f,n=30);assert npc in w.dead;w.step(c,f,n=45)
assert not [m for m in w.messages if m.startswith('HCC') or m.startswith('HCFM')] and not getattr(w,'debug',[]),w.messages
passed('Callouts stay silent when STATUS MESSAGES is disabled')
# fire at the helicopter: the brain reports it and the fire worker stamps the time the pilot's evasion looks at
def at_heli(w,who):
 w.shot_at={who:list(w.car)};w.shooting_chars={who}
w,c,f=fire_world();npc=target(w,typ=7,skin=102);w.weapons[npc]=30;w.step(c,f,n=5);quiet=w.shared[b.HELI_SHOT_T];assert w.now-quiet>5000
at_heli(w,npc);w.step(c,f,n=2);w.shooting_chars=set()
assert w.shared[b.HELI_SHOT_T]>0 and w.now-w.shared[b.HELI_SHOT_T]<=300,(w.now,w.shared[b.HELI_SHOT_T])
w,c,f=fire_world();npc=target(w,typ=7,skin=102);w.weapons[npc]=30;w.actor_heading[npc]=180.;w.shooting_chars={npc};w.step(c,f,n=4);assert w.now-w.shared[b.HELI_SHOT_T]>5000,'a round that goes nowhere near the helicopter'
w,c,f=fire_world();g0=w.shared[b.PUB+3];at_heli(w,g0);w.step(c,f,n=4);assert w.now-w.shared[b.HELI_SHOT_T]>5000,'our own fire'
passed('A stranger\'s round that passes within 6 m of the helicopter stamps the time the pilot\'s evasion looks at (it used to be read from the bullet traces); rounds elsewhere and our own fire do not')
# combat orbit around the threat at 28 m, 25 m above it, moving between points
w,c,f=fire_world();w.speed=18.;npc=target(w,typ=7,skin=20);w.damage.add((1,npc));w.step(c,f,n=10)   # an orbiting helicopter is moving (not 'wedged')
pts=set()
for _ in range(80):
 w.step(c,f);m=calls(w,0x4a2)[-1][2];pts.add((round(m[1],1),round(m[2],1)))
 assert abs(math.dist(m[1:3],w.pos[npc][:2])-b.ORBIT_RADIUS)<.5 and abs(m[3]-(w.pos[npc][2]+25.))<.01,m
assert len(pts)>=3,pts
passed('Combat orbit circles the threat at 28 m and 25 m above it')
# 1.1: every on-screen text is short, coloured consistently and names no removed button
import re as _re
_old=['BOARD CJ','LEAVE HELICOPTER','CALL SUPPORT','TAKE OFF','SETUP','SWAT:','TEAM ON FOOT >','EXIT NOW','LAND AT DESTINATION','DESCEND BY ROPE']
for _line in (b.OUT/'Helicover.fxt').read_bytes().decode('latin-1').splitlines():
 _k,_v=_line.split(' ',1)
 if _k[0] in 'UV':continue   # 1.2: the Russian lines (checked in test_v12_i18n)
 _plain=_re.sub(r'~.~','',_v)
 assert len(_plain)<=66,(_k,len(_plain),_plain)
 assert not any(o in _v for o in _old),(_k,_v)
 assert _k in ('HCDBG','HCKILL') or _re.match(r'~[rgbyp]~[A-Z0-9 .!-]+(:|!)?~w~ ',_v),(_k,_v)
passed('All on-screen texts: radio style (coloured source or alert, then the message), at most 66 characters, no removed buttons')
text='\n'.join(results)+'\nMocked script execution only: actual GTA flight, collisions, gunfire, animations and Android behavior are not tested.\n'
(b.OUT/'scenario_tests.txt').write_text(text);print(text)
