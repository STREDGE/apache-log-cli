"""Helicover 1.2 language and menu: the Russian texts in both byte layouts, language selection, the redesigned menu, FONT TEST.
Mocked script execution only: how the game's font draws the bytes can only be seen on a phone (that is what FONT TEST is for)."""
import math,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;P=HERE/'test_v25.py'
_src=P.read_text();g={'__file__':str(P),'__name__':'v25_harness'}
exec(compile(_src[:_src.index('results=[]')],str(P),'exec'),g)
for _m in re.finditer(r'^def [a-z_0-9]+\(.*?(?=^\S)',_src,re.S|re.M):exec(compile(_m.group(0),str(P),'exec'),g)
World,VM,b,setup,summon,calls,command=g['World'],g['VM'],g['b'],g['setup'],g['summon'],g['calls'],g['command']
import i18n_v12 as i18n
import msg_v42 as mv
results=[]
def passed(t):results.append('PASS: '+t)

# =================================================================== the tables and the FXT file
letters=[chr(c) for c in range(0x0410,0x0450)]+['Ё','ё']
glyphs=[i18n.encode(ch,'glyph')[0] for ch in letters];cps=[i18n.encode(ch,'cp1251')[0] for ch in letters]
assert len(set(glyphs))==66 and len(set(cps))==66,'every letter has its own glyph slot and its own CP1251 byte'
assert all(0xA0<=g_<=0xFF for g_ in glyphs),'the glyph slots sit in the high half of the font, like the accented Latin letters they replaced'
assert i18n.encode('А','cp1251')==b'\xc0' and i18n.encode('А','glyph')==b'\xc1' and i18n.encode('Б','glyph')==b'\xd0' and i18n.encode('я','glyph')==b'\xea'
assert i18n.encode('Hello ~b~1 2 3!','glyph')==b'Hello ~b~1 2 3!','Latin text, digits and the colour tags are never touched'
passed('Both layouts cover all 66 Cyrillic letters without collisions; CP1251 А = 0xC0, glyph slot of А = 0xC1 (russian_table of libGTASA)')
fxt={};en_raw=(b.OUT/'Helicover.fxt').read_bytes();raw=(b.OUT/'Helicover_RU.fxt').read_bytes()
assert max(en_raw)<0x80,'the English file stays plain ASCII'
for line in en_raw.split(b'\n')+raw.split(b'\n'):
 if line.strip():k,v=line.split(b' ',1);assert k.decode() not in fxt,('duplicate key',k);fxt[k.decode()]=v
en_keys=[k for k in fxt if k[0] not in 'UV'];assert len(en_keys)==len(i18n.RU_MESSAGES)==len([k for k in fxt if k[0]=='U'])==len([k for k in fxt if k[0]=='V'])
for k in en_keys:
 assert i18n.ukey(k) in fxt and i18n.vkey(k) in fxt,k
 ru=i18n.RU_MESSAGES[k];assert fxt[i18n.ukey(k)]==i18n.encode(ru,'cp1251') and fxt[i18n.vkey(k)]==i18n.encode(ru,'glyph'),k
 for key in (k,i18n.ukey(k),i18n.vkey(k)):assert len(key)<=7
 assert b'\r' not in fxt[i18n.ukey(k)] and b'\n' not in fxt[i18n.vkey(k)]
 assert re.findall(rb'~.~',fxt[i18n.ukey(k)])==re.findall(rb'~.~',fxt[k].encode() if isinstance(fxt[k],str) else fxt[k]),('colour tags',k)
 assert len(i18n.visible(ru))<=i18n.RU_PLAIN_LIMIT,(k,len(i18n.visible(ru)))
passed('Helicover.fxt (ASCII) holds the English messages, Helicover_RU.fxt the same ones with U keys in CP1251 and V keys in glyph codes, same colour tags')
inv={g_:ch for ch,g_ in zip(letters,glyphs)}
for k in en_keys:   # the glyph line decodes back to the same Russian text
 back=''.join(inv.get(c_,chr(c_)) if c_>=0x80 else chr(c_) for c_ in fxt[i18n.vkey(k)]);assert back==i18n.RU_MESSAGES[k],k
passed('The glyph-coded lines read back to the original Russian text')

# =================================================================== which language is in force
def lang_world(setting,russian=False):
 w,c,p=setup(True);w.russian=russian;w.shared[b.LANG_SETTING]=setting;w.step(c,p,n=3);return w,c,p
for setting,russian,expect in [(0,False,0),(0,True,2),(1,True,0),(2,False,1),(3,False,2),(2,True,1)]:
 w,c,p=lang_world(setting,russian);assert w.shared[b.LANG]==expect,(setting,russian,w.shared[b.LANG])
w,c,p=lang_world(0,True);w.shared[b.GAME_OK]=0;w.shared[b.LANG_SETTING]=0;w.step(c,p,n=3);assert w.shared[b.LANG]==0,'an unknown game build is never probed'
passed('AUTO follows the game flag (Russian game -> RUSSIAN 2 in the beta, otherwise English); the other settings are explicit; an unknown build stays English')
# messages use the key of the language in force
def keys_printed(w):return [x[2][0] for x in calls(w,0x3e5)]
for setting,prefix in [(1,'H'),(2,'U'),(3,'V')]:
 w,c,p=lang_world(setting);w.calls.clear();w.shared[b.CMD]=1;w.step(c,p,n=8);ks=keys_printed(w);assert ks and all(k_[0]==prefix for k_ in ks),(setting,ks)
passed('Notices use the English, CP1251 or glyph-coded key depending on the language')

# =================================================================== the menu
def open_menu(setting=1,summoned=True,aboard=False):
 w,c,p=setup(True);w.shared[b.LANG_SETTING]=setting
 if summoned:summon(w,c)
 if aboard:w.incar[1]=c.v[5]
 launch=VM('Helicover',w);w.step(c,p,launch,n=15);return w,c,p
def rows_of(w):return w.menu[2:]
w,c,p=open_menu()
assert w.menu[0]==b'HELICOVER / FOLLOWING' and rows_of(w)==[b'FOLLOW ME [X]',b'HOLD HERE',b'PATROL AROUND ME',b'GUNNER FIRE >',b'CLIMB ABOARD BY ROPE',b'DEPLOY SQUAD',b'SETTINGS >',b'DISMISS HELICOPTER']
for setting,prof in [(2,'cp1251'),(3,'glyph')]:
 w,c,p=open_menu(setting)
 want=[i18n.encode(x,prof) for x in ('ЛЕТЕТЬ ЗА МНОЙ [X]','ЖДАТЬ ЗДЕСЬ','ПАТРУЛЬ ВОКРУГ','ОГОНЬ СТРЕЛКОВ >','НА БОРТ ПО ВЕРЕВКЕ','ВЫСАДИТЬ ОТРЯД','НАСТРОЙКИ (SETTINGS) >','ОТПУСТИТЬ ВЕРТОЛЕТ')]
 assert rows_of(w)==want,(setting,rows_of(w))
 assert w.menu[0]==i18n.encode('HELICOVER / ЛЕТИТ ЗА ВАМИ',prof),w.menu[0]
passed('The main menu is drawn in Russian in either byte layout: rows and the state in the title')
# every blob: at most 8 rows, short rows, all three languages present
import collections
panel=VM('Helicover_Panel',World())
for label,data in b.p.data.items():
 fields=data[4:].split(b'\0')
 rows=[f_ for f_ in fields[2:] if f_]
 assert len(rows)<=8,(label,len(rows))
 if label.startswith(('MAIN_','SETUP_','PREF_','DISMISS_')):
  for r_ in rows:assert len(r_)<=(30 if label.endswith(('_U','_V')) else 26),(label,r_,len(r_))
for base in [l_ for l_ in b.p.data if l_.startswith('MAIN_') and not l_.endswith(('_U','_V'))]:
 assert base+'_U' in b.p.data and base+'_V' in b.p.data
 assert len(b.p.data[base].split(b'\0'))==len(b.p.data[base+'_U'].split(b'\0'))==len(b.p.data[base+'_V'].split(b'\0')),base
passed('Every menu page has an English, a CP1251 and a glyph-coded version with the same rows; at most 8 rows, none longer than 26 (RU 30) characters')

# =================================================================== language and FONT TEST pages
w,c,p=open_menu(1)
w.events.append(6);w.step(c,p,n=4);assert w.menu[0]==b'HELICOVER / SETTINGS' and w.menu[8]==b'LANGUAGE >',w.menu
w.events.append(6);w.step(c,p,n=4);assert w.menu[0]==b'LANGUAGE' and rows_of(w)==[b'AUTO',b'ENGLISH [X]',b'RUSSIAN 1 (CP1251)',b'RUSSIAN 2 (GAME FONT)',b'FONT TEST',b'< BACK'],w.menu
w.events.append(3);w.step(c,p,n=6);assert w.shared[b.LANG_SETTING]==3 and w.shared[b.LANG]==2 and rows_of(w)[3]==b'RUSSIAN 2 (GAME FONT) [X]',(w.shared[b.LANG_SETTING],w.menu)
w.events.append(0);w.step(c,p,n=6);assert w.shared[b.LANG_SETTING]==0 and rows_of(w)[0]==b'AUTO [X]'
w.events.append(2);w.step(c,p,n=6);assert w.shared[b.LANG]==1
w.events.append(5);w.step(c,p,n=5);assert w.menu[0]==i18n.encode('HELICOVER / НАСТРОЙКИ','cp1251'),'BACK from LANGUAGE leaves the settings page in the language just chosen'
passed('SETTINGS > LANGUAGE: AUTO / ENGLISH / RUSSIAN 1 / RUSSIAN 2, the choice applies at once and the pages follow')
w,c,p=open_menu(1)
w.events.append(6);w.step(c,p,n=4);w.events.append(6);w.step(c,p,n=4);w.events.append(4);w.step(c,p,n=4)
assert w.menu[0]==b'FONT TEST 1 / 2' and rows_of(w)[:4]==i18n.font_test_rows('cp1251') and rows_of(w)[4:]==[b'SHOW MESSAGE (RUS 1)',b'NEXT >',b'< BACK'],w.menu
for row in rows_of(w)[:4]:assert all(c_<0x80 or 0xC0<=c_ for c_ in row.replace(b'1: ',b'')),row
w.calls.clear();w.events.append(4);w.step(c,p,n=3);assert [k for k in keys_printed(w) if k=='UFTEST'],keys_printed(w)
w.events.append(5);w.step(c,p,n=4);assert w.menu[0]==b'FONT TEST 2 / 2' and rows_of(w)[:4]==i18n.font_test_rows('glyph') and rows_of(w)[4]==b'SHOW MESSAGE (RUS 2)'
w.calls.clear();w.events.append(4);w.step(c,p,n=3);assert [k for k in keys_printed(w) if k=='VFTEST'],keys_printed(w)
w.events.append(5);w.step(c,p,n=4);assert w.menu[0]==b'FONT TEST 1 / 2'
w.events.append(6);w.step(c,p,n=4);assert w.menu[0]==b'LANGUAGE'
passed('FONT TEST pages show the alphabet in both layouts and print a test message with the matching key')
# the alphabet rows together contain every letter of the game's table
seen=set()
for prof in ('cp1251','glyph'):
 for row in i18n.font_test_rows(prof):seen|=set(row[3:])
for ch in 'АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдежзийклмнопрстуфхцчшщъыьэюя':
 assert i18n.encode(ch,'cp1251')[0] in seen and i18n.encode(ch,'glyph')[0] in seen,ch
passed('The FONT TEST pages together cover every Russian letter except Ё / ё (which the texts never use)')

# =================================================================== DISMISS with a squad on the ground
w,c,p=open_menu(1);ground=VM('Helicover_Ground',w);w.shared[b.ESCORT_ON]=1
w.events.append(7);w.step(c,p,n=4);assert w.menu[0]==b'SEND THE HELICOPTER AWAY?' and rows_of(w)==[b'YES, RECALL SQUAD FIRST',b'NO, KEEP IT'],w.menu
w.events.append(0);w.step(c,p,n=6);assert w.shared[b.STATE]==19 or any(x[2]==[b.CMD,17] for x in calls(w,0xddc)),'the squad is recalled first'
assert w.shared[b.DISMISS_T]!=0 and not any(x[2]==[b.CMD,4] for x in calls(w,0xddc)),'the helicopter does not leave while the team is still down'
w.shared[b.ESCORT_ON]=0;w.step(c,p,n=8);assert any(x[2]==[b.CMD,4] for x in calls(w,0xddc)) and w.shared[b.DISMISS_T]==0
passed('DISMISS with a squad on the ground: recall first, the helicopter leaves when the squad is back aboard')
w,c,p=open_menu(1);w.shared[b.ESCORT_ON]=1;w.events.append(7);w.step(c,p,n=4);w.events.append(0);w.step(c,p,n=6)
w.now+=46000;w.step(c,p,n=6);assert any(x[2]==[b.CMD,4] for x in calls(w,0xddc)),'after 45 s the dismissal goes ahead anyway'
passed('A recall that never finishes does not keep the helicopter for ever: DISMISS goes through after 45 s')
w,c,p=open_menu(1);w.events.append(7);w.step(c,p,n=4);assert rows_of(w)==[b'YES, DISMISS IT',b'NO, KEEP IT'];w.events.append(0);w.step(c,p,n=8);assert w.shared[b.STATE]==4
passed('DISMISS without a squad is immediate after the confirmation')

# models for the CREW and HELICOPTER pages are requested while the page is open and released after
w,c,p=open_menu(1);w.calls.clear();w.events.append(6);w.step(c,p,n=4);w.events.append(0);w.step(c,p,n=4)
assert {x[2][0] for x in calls(w,0x247)}=={105,106,107,285,287},'only the crew skins are requested when the CREW page opens (not three helicopter models)'
w.calls.clear();w.events.append(3);w.step(c,p,n=4);w.events.append(1);w.step(c,p,n=4)
assert {x[2][0] for x in calls(w,0x247)}=={487,497,425},'the helicopter models when the HELICOPTER page opens'
w.calls.clear();w.events.append(3);w.step(c,p,n=4);w.events.append(7);w.step(c,p,n=4);assert {x[2][0] for x in calls(w,0x249)}>={285,287,487,497,425},'and released when the pages are left'
passed('Crew and helicopter models are pre-requested while their pages are open, so choosing one does not stall a frame')

text='\n'.join(results)+'\nMocked script execution only: the real look of Cyrillic in the game font is checked on the phone with FONT TEST.\n'
(b.OUT/'i18n_tests.txt').write_text(text);print(text)
