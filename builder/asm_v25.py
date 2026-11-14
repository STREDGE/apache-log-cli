import json,struct
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parent;OUT=Path(os.environ.get('HC_OUT',ROOT.parent/'build'))
OUT.mkdir(parents=True,exist_ok=True)
LIB={int(c['id'],16):c for e in json.load(open(ROOT/'sa_mobile.json'))['extensions'] for c in e['commands']}
# Official CLEO source defines 0DF4, missing from the downloaded library snapshot.
LIB[0x0df4]={'id':'0DF4','name':'GET_MENU_TOUCHED_ITEM_INDEX','num_params':2}
# Native SA command (self, x, y, z), absent from the trimmed library snapshot.
LIB[0x00ab]={'id':'00AB','name':'SET_CAR_COORDINATES','num_params':4}
LIB[0x0016]={'id':'0016','name':'DIV_INT_LVAR_BY_VAL','num_params':2}
# CLEO Android: 0DD8 result = read_mem_addr addr size add_ib (destination first).
LIB[0x0dd8]={'id':'0DD8','name':'READ_MEM_ADDR','num_params':4}
for _op,_name,_n in [(0x020a,'SET_CAR_DOORS_LOCKED',2),(0x0a52,'IS_WIDGET_RELEASED',1),(0x01e5,'PRINT_WITH_NUMBER_NOW',4),(0x0107,'CREATE_OBJECT',5),(0x0108,'DELETE_OBJECT',1),(0x01bc,'SET_OBJECT_COORDINATES',4),(0x03ca,'DOES_OBJECT_EXIST',1),(0x0750,'SET_OBJECT_VISIBLE',2),
 # v40 squad AI (parameter counts from the Sanny Builder SA mobile library)
 (0x0634,'TASK_KILL_CHAR_ON_FOOT_WHILE_DUCKING',5),(0x07a5,'TASK_KILL_CHAR_ON_FOOT_TIMED',3),(0x0667,'TASK_AIM_GUN_AT_COORD',5),
 (0x0633,'TASK_LEAVE_ANY_CAR',1),(0x081a,'SET_CHAR_WEAPON_SKILL',2),(0x0856,'SET_CHAR_ALLOWED_TO_DUCK',2),(0x06ac,'GET_CHAR_SPEED',2),
 (0x05f5,'TASK_FOLLOW_PATH_NODES_TO_COORD',6),(0x0350,'SET_CHAR_STAY_IN_SAME_PLACE',2),(0x05ba,'TASK_STAND_STILL',2),(0x0639,'TASK_TURN_CHAR_TO_FACE_CHAR',2),
 (0x078f,'TASK_CLIMB',2),(0x0637,'TASK_GO_TO_COORD_WHILE_SHOOTING',8),(0x05c5,'TASK_DUCK',2)]:
 LIB.setdefault(_op,{'id':'%04X'%_op,'name':_name,'num_params':_n})
STATE=0x48454d00;CMD=STATE+1;HEART=STATE+2
# Protocol: commands 1 summon, 2 follow, 3 hold, 4 depart.
# States 0 ready, 1 loading, 2 follow, 3 hold, 4 depart, 5 model error, 6 outdoors required.
def I(n):return(1,n)
def V(n):return(3,n)
def F(n):return(6,float(n))
def L(s):return('label',s)
def S(s):
 assert len(s.encode('ascii'))<=7
 return(9,s)
class Script:
 def __init__(self):self.rows=[];self.data={};self.auto=0
 def label(self,n):self.rows.append(n)
 def add(self,op,*args):self.rows.append((op,list(args)))
 def go(self,n):self.add(2,L(n))
 def check(self,op,args,fail):self.add(0xd6,I(0));self.add(op,*args);self.add(0x4d,L(fail))
 def eq(self,var,value,fail):self.check(0x0039,[V(var),I(value)],fail)
 def set(self,key,value):self.add(0xddc,I(key),I(value))
 def get(self,var,key):self.add(0xddd,V(var),I(key))
 def call(self,n):self.add(0x50,L(n))
 def ret(self):self.add(0x51)
 def blob(self,label,title,items):self.data[label]=struct.pack('<I',0)+(title+'\0CLOSE\0'+'\0'.join(items)+'\0\0').encode('ascii')
 def build(self,name,ext):
  def param(t,v,labels=None):
   if t==9:return b'\x09'+v.encode('ascii').ljust(8,b'\0')
   if t=='label':return b'\1'+struct.pack('<i',-labels[v] if labels else 0)
   return bytes([t])+struct.pack({1:'<i',2:'<h',3:'<h',4:'<b',5:'<h',6:'<f'}[t],v)
  labels={};pos=0;instructions={}
  for r in self.rows:
   if isinstance(r,str):assert r not in labels;labels[r]=pos;continue
   op,args=r;assert op&0x7fff in LIB and len(args)==LIB[op&0x7fff]['num_params'],r
   meta=LIB[op&0x7fff];spec=meta.get('input',[])+meta.get('output',[])
   if len(spec)==len(args):
    for index,((kind,value),parameter) in enumerate(zip(args,spec)):
     source=parameter.get('source','')
     assert not (source=='var_local' and kind!=3), (hex(op),index,'expected local variable',r)
     assert not (source=='literal' and kind==3), (hex(op),index,'expected literal',r)
   instructions[pos]=r;pos+=2+sum(len(param(t,v)) for t,v in args)
  code_size=pos
  for label,data in self.data.items():assert label not in labels;labels[label]=pos;pos+=len(data)
  b=bytearray();src=['{$CLEO .'+ext+'}','// Helicover v21 preview. Built for CLEO Android.','// 0DDD/0DD0/0DF4 use destination-first bytecode order.','']
  def fmt(t,v):return '@'+v if t=='label' else str(v)+'@' if t==3 else repr(v)
  for r in self.rows:
   if isinstance(r,str):src.append(':'+r);continue
   op,args=r;b+=struct.pack('<H',op)+b''.join(param(t,v,labels) for t,v in args)
   src.append(f'{op:04X}: '+' '.join(fmt(t,v) for t,v in args)+' // '+LIB[op&0x7fff]['name'])
  for label,data in self.data.items():
   src+=[':'+label,'hex',data.hex(' '),'end'];b+=data
  # Parse output independently: arity, branches and menu pointer labels.
  p=0;starts=set();branches=[];pointers=[];count=0
  while p<code_size:
   starts.add(p);op=struct.unpack_from('<H',b,p)[0];p+=2
   for i in range(LIB[op&0x7fff]['num_params']):
    t=b[p];p+=1
    if op in [2,0x4d,0x50] and i==0:branches.append(-struct.unpack_from('<i',b,p)[0])
    if op==0xdd0 and i==1:pointers.append(-struct.unpack_from('<i',b,p)[0])
    p+={1:4,2:2,3:2,4:1,5:2,6:4,9:8}[t]
   count+=1
  assert p==code_size and all(t in starts for t in branches)
  assert all(t in [labels[n] for n in self.data] for t in pointers)
  (OUT/(name+'.'+ext)).write_bytes(b);(OUT/(name+'.txt')).write_text('\n'.join(src)+'\n')
  metadata={'code_size':code_size,'labels':labels,'data':{k:v.hex() for k,v in self.data.items()}}
  (OUT/(name+'.meta.json')).write_text(json.dumps(metadata,indent=2))
  return f'{name}.{ext}: PASS, {count} instructions, {len(branches)} jumps, {len(pointers)} menu pointers, {len(b)} bytes.'
