"""Static check: find control-flow cycles that contain no WAIT (0001) in compiled scripts.
Such a cycle freezes the game thread (picture stops, audio keeps playing)."""
import struct,sys,json
from asm_v25 import LIB,OUT
SIZES={1:4,2:2,3:2,4:1,5:2,6:4,9:8,15:16}
def parse(name):
    meta=json.loads((OUT/(name+'.meta.json')).read_text());raw=(OUT/(name+('.csi' if name=='Helicover' else '.csa'))).read_bytes()
    p=0;ins={};order=[]
    while p<meta['code_size']:
        start=p;op=struct.unpack_from('<H',raw,p)[0];p+=2;args=[]
        for _ in range(LIB[op&0x7fff]['num_params']):
            t=raw[p];p+=1
            v=struct.unpack_from({1:'<i',2:'<h',3:'<h',4:'<b',5:'<h',6:'<f',9:'8s',15:'16s'}[t],raw,p)[0];p+=SIZES[t];args.append(v)
        ins[start]=(op,args,p);order.append(start)
    return ins,order
def succ(ins,a):
    op,args,nxt=ins[a];base=op&0x7fff
    if base==0x0002:return [-args[0]]
    if base in(0x0051,0x004e):return []
    if base==0x004d:return [nxt,-args[0]]
    if base==0x0050:return [-args[0],nxt]   # gosub: callee, then the return point
    return [nxt] if nxt in ins else []
def check(name):
    ins,order=parse(name)
    nodes=[a for a in order if (ins[a][0]&0x7fff)!=0x0001]
    # A subroutine that cannot return without passing a WAIT (beta 5: the core's NAP) is itself a wait:
    # the caller's return point is then not reachable 'for free' from the GOSUB.
    memo={}
    def always_waits(entry):
        if entry not in memo:
            memo[entry]=True;seen=set();todo=[entry];ok=True   # (recursion is treated as waiting; the scripts have none)
            while todo and ok:
                a=todo.pop()
                if a in seen or a not in ins or (ins[a][0]&0x7fff)==0x0001:continue
                seen.add(a);base=ins[a][0]&0x7fff
                if base==0x0051:ok=False
                elif base==0x0050:
                    if not always_waits(-ins[a][1][0]):todo.append(ins[a][2])
                else:todo.extend(succ(ins,a))
            memo[entry]=ok
        return memo[entry]
    def edges(a):
        if (ins[a][0]&0x7fff)==0x0050 and always_waits(-ins[a][1][0]):return [-ins[a][1][0]]
        return succ(ins,a)
    g={a:[b for b in edges(a) if b in ins and (ins[b][0]&0x7fff)!=0x0001] for a in nodes}
    # Tarjan SCC
    idx={};low={};st=[];on=set();res=[];n=[0]
    sys.setrecursionlimit(100000)
    def sc(v):
        idx[v]=low[v]=n[0];n[0]+=1;st.append(v);on.add(v)
        for w in g[v]:
            if w not in idx:sc(w);low[v]=min(low[v],low[w])
            elif w in on:low[v]=min(low[v],idx[w])
        if low[v]==idx[v]:
            comp=[]
            while True:
                w=st.pop();on.discard(w);comp.append(w)
                if w==v:break
            if len(comp)>1 or v in g[v]:res.append(sorted(comp))
    for v in nodes:
        if v not in idx:sc(v)
    return res
# Reviewed cycles that are bounded at run time: RAY_STEP counts to 11; TRACE_SCAN_LOOP steps through the
# 16 bullet-trace entries (address += 44 on every path); EVAC <-> START_MUSTER
# always reaches TICK (WAIT) for every value of the phase variable 24@.
REVIEWED={'Helicover_Fire':{'RAY_STEP','TRACE_SCAN_LOOP'},'Helicover_Core':{'EVAC'}}
def label_names(name,comp):
    labels=json.loads((OUT/(name+'.meta.json')).read_text())['labels'];inv={}
    for k,v in labels.items():inv.setdefault(v,set()).add(k)
    return set().union(*[inv.get(a,set()) for a in comp])
if __name__=='__main__':
    bad=0
    for name in ['Helicover_Core','Helicover_Panel','Helicover','Helicover_Fire','Helicover_Ground','Helicover_Squad']:
        r=[c for c in check(name) if not (label_names(name,c)&REVIEWED.get(name,set()))];bad+=len(r)
        print(name,'unreviewed WAIT-less cycles:',len(r),[sorted(label_names(name,c))[:6] for c in r])
    sys.exit(1 if bad else 0)
