"""Random-command fuzz on the mocked VM: every seed throws menu commands, setting changes, CJ boarding / leaving, hostiles and time jumps at
all workers and checks the invariants a player would notice:
  * no exception in the mock (a script that touches a dead handle, a bad opcode argument ...),
  * no teleport of a person (heli moves are scripted and excluded),
  * beta 4: every order and every menu tap comes one to three times in a row (a double or triple press), and after every step there is
    at most one helicopter, one crew, one team of four, nobody the scripts lost track of and no living guard handed to the game,
  * 1.3: hostiles of every kind (they hurt CJ, fire at him, stand armed, are fired at by CJ), stars, missions and the police / mission
    switches at random - and no round ever passes CJ or one of ours, no firing task without the brain's leave (the invariants),
  * after 90 s of quiet nothing is left half-done (rope busy / swap busy flags, squad state, pending orders).
    python3 tools/fuzz.py [first_seed] [count]
"""
import re,sys,random,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent.parent;P=HERE/'test_v25.py'
_src=P.read_text();g={'__file__':str(P),'__name__':'v25_harness'}
sys.path.insert(0,str(HERE))
exec(compile(_src[:_src.index('results=[]')],str(P),'exec'),g)
for _m in re.finditer(r'^def [a-z_0-9]+\(.*?(?=^\S)',_src,re.S|re.M):exec(compile(_m.group(0),str(P),'exec'),g)
World,VM,b,setup,summon,calls,command,invariants=g['World'],g['VM'],g['b'],g['setup'],g['summon'],g['calls'],g['command'],g['invariants']
def one(seed):
 rnd=random.Random(seed);w,c,p=setup(True);w.rng=random.Random(seed);w.jitter=rnd.random()<.5
 vms=[c,p,VM('Helicover_Ground',w),VM('Helicover_Squad',w),VM('Helicover_Fire',w),VM('Helicover',w)]
 w.step(*vms,n=10);w.teleports.clear();car=None;log=[];broken=[]
 def run(n):
  for _ in range(n):
   w.step(*vms)
   if not broken:
    inv=invariants(w)
    if inv:broken.append((w.now,inv,log[-6:]))
 for it in range(rnd.randint(30,70)):
  a=rnd.random();ev=None
  if a<.35:
   ev=('cmd',rnd.choice([1,2,3,4,6,7,9,10,11,12,14,15,16,17]),rnd.choice([1,1,2,3]))
   for k in range(ev[2]):
    w.shared[b.CMD]=ev[1]
    if k+1<ev[2]:run(rnd.randint(1,4))
  elif a<.5:
   key,val=rnd.choice([(b.CREW,rnd.choice([0,1,2])),(b.MODEL,rnd.choice([487,497,425])),(b.WEAPON_SETTING,rnd.choice([0,29,30,31,34])),(b.FIRE,rnd.choice([0,1,2,3,4])),(b.POLICE,rnd.choice([0,1])),(b.MISSIONS,rnd.choice([0,1])),('wanted',rnd.choice([0,0,2,4])),('mission',rnd.choice([0,0,1])),(b.TACTICS,rnd.choice([0,1])),(b.EXIT_MODE,rnd.choice([0,1])),('lang',rnd.choice([0,1]))])
   ev=('set',key,val)
   if key=='lang':w.russian=bool(val);w.game_lang=5 if val else rnd.choice([0,1,2])
   elif key=='wanted':w.wanted=val
   elif key=='mission':w.on_mission=bool(val)
   else:w.shared[key]=val
  elif a<.6:
   # 1.3: a gang member or a policeman, armed; he hurts CJ, fires at him, only stands there, or CJ fires at him
   hid=1000+it;w.exists.add(hid);w.pos[hid]=[w.player[0]+rnd.uniform(-25,25),w.player[1]+rnd.uniform(-25,25),0.];w.pedtype[hid]=rnd.choice([7,7,6]);w.weapons[hid]=rnd.choice([30,22,0]);w.civilians=[hid]
   how=rnd.choice(['hurts','fires','stands','cj fires'])
   if how=='hurts':w.damage.add((1,hid))
   if how=='fires':w.shooting_chars.add(hid);w.shot_at=dict(getattr(w,'shot_at',{}));w.shot_at[hid]=[w.player[0],w.player[1],1.]
   w.shooting=how=='cj fires'
   if w.shooting:w.cj_aim=list(w.pos[hid][:2])+[1.]
   ev=('hostile',hid,how)
  elif a<.7 and c.v[5] in w.exists:
   if 1 in w.incar:w.incar.pop(1);ev=('cj out',)
   else:w.incar[1]=c.v[5];ev=('cj in',)
  elif a<.78:
   ev=('menu',rnd.randint(0,7),rnd.choice([1,1,2,3]))
   for k in range(ev[2]):
    w.events.append(ev[1])
    if k+1<ev[2]:run(rnd.randint(1,5))
  elif a<.85:w.now+=rnd.choice([3000,12000,40000]);ev=('time',)
  elif a<.92:
   if 1 not in w.incar:w.player=[w.player[0]+rnd.uniform(-8,8),w.player[1]+rnd.uniform(-8,8),0.]
   ev=('walk',)
  log.append(ev)
  run(rnd.randint(2,25))
 # quiet period: CJ on foot, no hostiles, nothing pressed
 for hid in [x for x in w.exists if 1000<=x<2000]:w.dead.add(hid)      # every hostile of this run (the brain sees them all, not only the last one)
 w.damage.clear()
 w.shooting_chars.clear();w.shooting=False;w.wanted=0;w.on_mission=False;w.incar.pop(1,None);w.events.clear();w.shared[b.CMD]=0
 for _ in range(90):w.now+=1000;run(2)
 bad=[x for x in w.teleports if x['who'] not in (1,c.v[5],c.v[4]) and x['dist']>3.5 and x['who'] in w.pos]   # CJ's rope moves are scripted mechanics with their own tests
 problems=[]
 if broken:problems.append('invariant broken at %d ms: %s after %s'%broken[0])
 if w.bullet_violations:problems.append('a round passed CJ or one of ours: %s'%w.bullet_violations[:2])
 if w.shared[b.FIRE_ACTIVE]!=0 or w.shared[b.ENGAGED]!=0:problems.append('the fight did not end: FIRE_ACTIVE %d ENGAGED %d'%(w.shared[b.FIRE_ACTIVE],w.shared[b.ENGAGED]))
 if w.handed:problems.append('living guard handed to the game: %s'%w.handed[:3])
 for name in ('AFTER_ROPE','ESCORT_CMD','ROPE_WAIT','DISMISS_T','ROPE_COMMAND','DROP_COMMAND'):
  if w.shared[getattr(b,name)]!=0:problems.append('%s left at %s (state %d)'%(name,w.shared[getattr(b,name)],w.shared[b.STATE]))
 if bad:problems.append('person teleported: %s'%[(hex(x['op']),x['who'],round(x['dist'],1)) for x in bad[:3]])
 if w.shared[b.ROPE_BUSY]==1 and w.shared[b.STATE] not in (19,20,23,25):problems.append('ROPE_BUSY stuck (state %d)'%w.shared[b.STATE])
 if w.shared[b.BUSY]==1:problems.append('BUSY stuck')
 if w.shared[b.STATE] in (16,17):problems.append('state %d stuck'%w.shared[b.STATE])
 if w.shared[b.ESCORT_ON] in (2,3):problems.append('ESCORT_ON %d stuck'%w.shared[b.ESCORT_ON])
 return problems,log
if __name__=='__main__':
 first=int(sys.argv[1]) if len(sys.argv)>1 else 0;count=int(sys.argv[2]) if len(sys.argv)>2 else 40;bad=0
 for seed in range(first,first+count):
  try:problems,log=one(seed)
  except Exception as e:
   bad+=1;print('seed',seed,'EXCEPTION',type(e).__name__,str(e)[:160]);tb=traceback.extract_tb(e.__traceback__)[-1];print('   at',tb.filename.split('/')[-1],tb.lineno,tb.line);continue
  if problems:bad+=1;print('seed',seed,problems)
 print('fuzz done: %d seeds, %d with problems'%(count,bad))
