"""Build every Helicover script, check that every on-screen message key has text in
Helicover.fxt, and copy the results into install/, sources/ and tests/.
Always use this instead of running the two builders separately: build_v25.py rewrites
Helicover.fxt and build_v25_ground.py appends the ground-team texts to it."""
import re,shutil,subprocess,sys
import i18n_v12 as i18n
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'build'
NAMES=['Helicover','Helicover_Core','Helicover_Panel','Helicover_Fire','Helicover_Ground','Helicover_Squad']
def run(script):
    r=subprocess.run([sys.executable,script],cwd=HERE,capture_output=True,text=True)
    sys.stdout.write(r.stdout);sys.stderr.write(r.stderr)
    if r.returncode:sys.exit(r.returncode)
def missing_keys():
    have=set()
    for fname in ('Helicover.fxt','Helicover_RU.fxt'):
        if (OUT/fname).exists():have|={line.split(' ',1)[0] for line in (OUT/fname).read_bytes().decode('latin-1').splitlines() if line.strip()}
    used=set()
    for n in NAMES:
        for line in (OUT/(n+'.txt')).read_text().splitlines():
            m=re.match(r"^([0-9A-F]{4}): '([A-Z0-9]+)'",line)
            if m and int(m.group(1),16)&0x7fff in(0x03e5,0x01e5):used.add(m.group(2))
    return sorted(used-have)
def write_languages():
    """Helicover.fxt stays plain ASCII English (as in 1.1, so a loader that dislikes high bytes can never break it); Helicover_RU.fxt carries
    the same messages in Russian twice: key U... in plain CP1251, key V... in the game's glyph codes."""
    path=OUT/'Helicover.fxt';lines=[l for l in path.read_text().splitlines() if l.strip()]
    en={l.split(' ',1)[0]:l.split(' ',1)[1] for l in lines}
    extra=set(i18n.RU_MESSAGES)-set(en);absent=set(en)-set(i18n.RU_MESSAGES)
    if extra or absent:sys.exit('Russian texts differ from the English ones: extra %s, missing %s'%(sorted(extra),sorted(absent)))
    i18n.check_keys()
    for k,v in i18n.RU_MESSAGES.items():
        if len(i18n.visible(v))>i18n.RU_PLAIN_LIMIT:sys.exit('Russian text too long: '+k)
    out=bytearray()
    for k in en:
        for prof,key in (('cp1251',i18n.ukey(k)),('glyph',i18n.vkey(k))):out+=key.encode('ascii')+b' '+i18n.encode(i18n.RU_MESSAGES[k],prof)+b'\n'
    (OUT/'Helicover_RU.fxt').write_bytes(bytes(out))
if __name__=='__main__':
    run('build_v25.py');run('build_v25_ground.py');run('build_v25_squad.py')
    write_languages()
    miss=missing_keys()
    if miss:sys.exit('Missing FXT texts: '+', '.join(miss))
    for f in OUT.iterdir():
        if f.suffix in('.csa','.csi','.fxt'):shutil.copy(f,ROOT/'install'/f.name)
    for n in NAMES:shutil.copy(OUT/(n+'.txt'),ROOT/'sources'/(n+'.txt'))
    print('FXT keys OK; install/ and sources/ updated.')
