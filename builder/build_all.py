"""Build every Helicover script, check that every on-screen message key has text in
Helicover.fxt, and copy the results into install/, sources/ and tests/.
Always use this instead of running the two builders separately: build_v25.py rewrites
Helicover.fxt and build_v25_ground.py appends the ground-team texts to it."""
import re,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'build'
NAMES=['Helicover','Helicover_Core','Helicover_Panel','Helicover_Fire','Helicover_Ground']
def run(script):
    r=subprocess.run([sys.executable,script],cwd=HERE,capture_output=True,text=True)
    sys.stdout.write(r.stdout);sys.stderr.write(r.stderr)
    if r.returncode:sys.exit(r.returncode)
def missing_keys():
    have={line.split(' ',1)[0] for line in (OUT/'Helicover.fxt').read_text().splitlines() if line.strip()}
    used=set()
    for n in NAMES:
        for line in (OUT/(n+'.txt')).read_text().splitlines():
            m=re.match(r"^([0-9A-F]{4}): '([A-Z0-9]+)'",line)
            if m and int(m.group(1),16)&0x7fff in(0x03e5,0x01e5):used.add(m.group(2))
    return sorted(used-have)
if __name__=='__main__':
    run('build_v25.py');run('build_v25_ground.py')
    miss=missing_keys()
    if miss:sys.exit('Missing FXT texts: '+', '.join(miss))
    for f in OUT.iterdir():
        if f.suffix in('.csa','.csi','.fxt'):shutil.copy(f,ROOT/'install'/f.name)
    for n in NAMES:shutil.copy(OUT/(n+'.txt'),ROOT/'sources'/(n+'.txt'))
    print('FXT keys OK; install/ and sources/ updated.')
