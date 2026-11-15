"""Check i18n_v12.GLYPH_TABLE against the `russian_table` / `russian_unicode_table` arrays of a libGTASA.so (arm64 build 2.00).

    python3 tools/verify_russian_table.py /path/to/libGTASA.so

The tables are exported data symbols: russian_table (128 x uint16, glyph slot of CP1251 byte 0x80 + i) and
russian_unicode_table (128 x uint16, Unicode of the same byte). Their virtual addresses come from the symbol table.
"""
import struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import i18n_v12 as i18n
def symbols(data):
 """Name -> (vaddr, size) of the dynamic symbols."""
 shoff=struct.unpack_from('<Q',data,0x28)[0];shentsize,shnum,shstrndx=struct.unpack_from('<HHH',data,0x3A)
 secs=[struct.unpack_from('<IIQQQQIIQQ',data,shoff+i*shentsize) for i in range(shnum)]
 out={}
 for s in secs:
  if s[1]==11:  # SHT_DYNSYM
   strtab=secs[s[6]];n=s[5]//24
   for i in range(n):
    st_name,st_info,st_other,st_shndx,st_value,st_size=struct.unpack_from('<IBBHQQ',data,s[4]+i*24)
    end=data.index(b'\0',strtab[4]+st_name);name=data[strtab[4]+st_name:end].decode()
    out[name]=(st_value,st_size)
 return out
def read_vaddr(data,va,n):
 phoff=struct.unpack_from('<Q',data,0x20)[0];phentsize,phnum=struct.unpack_from('<HH',data,0x36)
 for i in range(phnum):
  p_type,_,p_offset,p_vaddr,_,p_filesz,_,_=struct.unpack_from('<IIQQQQQQ',data,phoff+i*phentsize)
  if p_type==1 and p_vaddr<=va<p_vaddr+p_filesz:return data[p_offset+va-p_vaddr:p_offset+va-p_vaddr+n]
 raise SystemExit('address not in a PT_LOAD segment')
def main(path):
 data=Path(path).read_bytes();sym=symbols(data)
 rt=struct.unpack('<128H',read_vaddr(data,sym['russian_table'][0],256))
 ru=struct.unpack('<128H',read_vaddr(data,sym['russian_unicode_table'][0],256))
 assert tuple(rt)==i18n.GLYPH_TABLE,'GLYPH_TABLE differs from the game'
 for i,u in enumerate(ru):
  if 0x0400<=u<0x0460:assert bytes([0x80+i]).decode('cp1251')==chr(u),(i,u)
 print('OK: GLYPH_TABLE matches libGTASA (%d Cyrillic letters, russian_table at 0x%x)'%(sum(1 for i,u in enumerate(ru) if 0x0400<=u<0x0460),sym['russian_table'][0]))
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else '/tmp/claude-0/-home-user-apache-log-cli/37e0b7ea-27cc-54be-9142-04c6cb0a572e/scratchpad/gtasa/libGTASA.so')
