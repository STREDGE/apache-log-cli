"""Pack the release archive: <name>/CLEO/ (all files of install/) + <name>/mods/libHelicoverBrain64.so (1.3: the scripts do not
work without the brain) + the two READMEs.
    python3 tools/make_release.py "Helicover 1.3" /path/to/Helicover_1.3_beta1_Android.zip
"""
import sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent.parent
def main(name,out):
 files=sorted((ROOT/'install').iterdir());assert files,'install/ is empty: run build_all.py first'
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr(name+'/',b'');z.writestr(name+'/CLEO/',b'')
  for f in files:z.write(f,'%s/CLEO/%s'%(name,f.name))
  brain=ROOT/'brain'/'libHelicoverBrain64.so';assert brain.exists(),'brain/libHelicoverBrain64.so is missing: sh brain/build.sh and copy it there'
  z.writestr(name+'/mods/',b'');z.write(brain,'%s/mods/%s'%(name,brain.name))
  for doc in ('README_RU.txt','README_EN.txt'):z.write(ROOT/'release'/doc,'%s/%s'%(name,doc))
 print('wrote',out)
 with zipfile.ZipFile(out) as z:
  for i in z.infolist():print('%8d  %s'%(i.file_size,i.filename))
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
