"""Helicover 1.2 language and menu: the Russian texts for the game's own Russian font and for SanLTD, language selection, the menu,
FONT TEST. The two fonts are simulated from what the player's screenshots of the first beta showed and from libGTASA's CFont code;
how the real font draws the bytes is still only seen on a phone (that is what FONT TEST is for)."""
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

# =================================================================== the two fonts, as the phone showed them
UP=i18n.ALPHABET;LO=UP.lower();BAD='\ufffd'   # a code the font has no glyph for
def draw_game(raw):
 """The game's own Russian: one atlas, glyph = code - 0x20, 164 glyphs; past its end everything is '@' (GetJapaneseWidth / PrintChar)."""
 out=''
 for c in raw:
  if c<0x7F:out+=chr(c)
  elif 0x80<=c<=0x9F:out+=UP[c-0x80]
  elif 0xA0<=c<=0xBF:out+=LO[c-0xA0]
  elif 0xC0<=c<=0xC3:out+='\u2026\u26ca\u2605\u2665'[c-0xC0]      # ellipsis, shield, star, heart
  else:out+='@' if c>0xC3 else BAD
 return out
SUB={**{144+i:str(i) for i in range(10)},**{155+i:chr(65+i) for i in range(26)},**{181+i:ch for i,ch in enumerate('БФГДЖИЙЛЗЦЩВПЧШТЪЫЬЭЮЯ')},203:'М',204:'Н',205:'М'}
def draw_sanltd_menu(raw):
 """SanLTD, menu font: CFont::FindSubFontCharacter moves digits, letters and the accented range into the second half of the texture,
 whose glyphs are what the player's screenshot showed (181.. = the SanLTD capitals)."""
 out=''
 for c in raw:
  i=c-0x20
  if 16<=i<=25:i+=128
  elif 33<=i<=58:i+=122
  elif 65<=i<=90:i+=90
  elif 96<=i<=118:i+=85
  elif 119<=i<=140:i+=62
  elif 141<=i<=142:i=204
  out+=SUB[i] if i in SUB else (chr(c) if c<0x80 else BAD)
 return out
def draw_sanltd_text(raw):
 """SanLTD, help-box font (the first half of the texture, same letters at the same codes): capitals at 0x80-0x95."""
 return ''.join(chr(c) if c<0x80 else (SUB[c-0x80+181] if 0x80<=c<=0x95 else BAD) for c in raw)
LOOK=str.maketrans('АВЕЁКМНОРСТУХ','ABEEKMHOPCTYX')      # what a SanLTD line looks like: these letters ARE the Latin glyphs
def sanltd_look(text):return i18n.upper_keep_tags(text).translate(LOOK)
# the simulation itself against the three screenshots of the first beta
old_keyboard=bytes([203,206,195,182,197,181,205])+b': '+bytes([235,238,236,239,229])+b'.'     # "СТРЕЛКИ: чисто." in the wrong layout of beta 1
assert draw_game(old_keyboard)=='@@\u2665ц@х@: @@@@@.','screenshot 1: the help box in the game\'s Russian'
assert draw_game(bytes(range(0xC0,0xD0)))=='\u2026\u26ca\u2605\u2665'+'@'*12,'screenshot 2: FONT TEST row of CP1251 capitals in the game\'s Russian'
assert [draw_sanltd_menu(bytes(range(lo,hi))) for lo,hi in ((0xC0,0xD0),(0xD0,0xE0),(0xE0,0xEE))]==['FGHIJKLMNOPQRSTU','VWXYZБФГДЖИЙЛЗЦЩ','ВПЧШТЪЫЬЭЮЯМНМ'],'screenshot 4: the same rows in SanLTD'
assert draw_sanltd_menu(bytes([200,181,205,194,193,199])+b' >')=='N5SHGM >','screenshot 5: the settings row of beta 1 in SanLTD'
passed('The two simulated fonts reproduce the player\'s screenshots of beta 1 (@@♥ц@х@ in the game\'s Russian; FGHIJ... / N5SHGM in SanLTD)')

# =================================================================== the tables and the FXT file
assert i18n.encode('АЯая','game')==bytes([0x80,0x9F,0xA0,0xBF]) and i18n.encode('хц','game')==bytes([181,182]),'the two letters read off the screenshot sit where the layout puts them'
assert i18n.encode('Ёё','game')==i18n.encode('Ее','game'),'no IO in the official atlas'
assert len({i18n.encode(ch,'game') for ch in UP+LO})==64 and all(0x80<=i18n.encode(ch,'game')[0]<=0xBF for ch in UP+LO)
assert i18n.encode('Hello ~b~1 2 3!','game')==b'Hello ~b~1 2 3!' and i18n.encode('~b~пилот~w~ x','sanltd')==b'~b~'+i18n.encode('ПИЛОТ','sanltd')+b'~w~ X','Latin text and digits stay; the tags are never touched (nor upper-cased)'
assert draw_sanltd_menu(i18n.encode(UP,'sanltd'))==UP.translate(LOOK) and draw_sanltd_text(i18n.encode(UP+LO,'sanltd'))==(UP+UP).translate(LOOK)
assert set(i18n.encode(UP+LO+'Ёё','sanltd'))<=set(range(0x41,0x5B))|set(range(0x80,0x96)),'SanLTD: only capitals, only the codes confirmed on the screenshot (0x80-0x95) and Latin look-alikes'
passed('Game Russian: А-Я = 0x80-0x9F, а-я = 0xA0-0xBF (х = 181, ц = 182 as on the screenshot); SanLTD: capitals only, Latin look-alikes + 0x80-0x95')
fxt={};en_raw=(b.OUT/'Helicover.fxt').read_bytes();raw=(b.OUT/'Helicover_RU.fxt').read_bytes()
assert max(en_raw)<0x80,'the English file stays plain ASCII'
for line in en_raw.split(b'\n')+raw.split(b'\n'):
 if line.strip():k,v=line.split(b' ',1);assert k.decode() not in fxt,('duplicate key',k);fxt[k.decode()]=v
en_keys=[k for k in fxt if k[0] not in 'UV'];assert len(en_keys)==len(i18n.RU_MESSAGES)==len([k for k in fxt if k[0]=='U'])==len([k for k in fxt if k[0]=='V'])
for k in en_keys:
 assert i18n.ukey(k) in fxt and i18n.vkey(k) in fxt,k
 ru=i18n.RU_MESSAGES[k];assert fxt[i18n.ukey(k)]==i18n.fxt_text(k,'game') and fxt[i18n.vkey(k)]==i18n.fxt_text(k,'sanltd'),k
 for key in (k,i18n.ukey(k),i18n.vkey(k)):assert len(key)<=7
 assert b'\r' not in fxt[i18n.ukey(k)] and b'\n' not in fxt[i18n.vkey(k)]
 for key in (i18n.ukey(k),i18n.vkey(k)):assert re.findall(rb'~.~',fxt[key])==re.findall(rb'~.~',fxt[k]),('colour tags',key)
 assert len(i18n.visible(ru))<=i18n.RU_PLAIN_LIMIT,(k,len(i18n.visible(ru)))
passed('Helicover.fxt (ASCII) holds the English messages, Helicover_RU.fxt the same ones with U keys for the game\'s Russian and V keys for SanLTD, same colour tags')
for k in en_keys:   # what the player would read
 ru=i18n.RU_MESSAGES[k]
 shown=draw_game(fxt[i18n.ukey(k)]);assert shown==ru.replace('ё','е').replace('Ё','Е') and '@' not in shown and BAD not in shown,(k,shown)
 if k!='HFTEST':shown=draw_sanltd_text(fxt[i18n.vkey(k)]);assert shown==sanltd_look(ru) and BAD not in shown,(k,shown)
passed('Every one of the %d messages reads back as its Russian text in both simulated fonts (mixed case in the game\'s Russian, capitals in SanLTD), no @ anywhere'%len(en_keys))
assert draw_sanltd_text(fxt['VFTEST'])[:11]=='~b~TEST~w~ ' and set(fxt['VFTEST'])>=set(range(0x80,0xB0)),'the SanLTD test message shows every raw code 0x80-0xAF (to learn the lower-case letters)'
passed('The SanLTD test message carries the raw codes 0x80-0xAF in groups of eight')

# =================================================================== which language is in force
def lang_world(setting,russian=False,game_lang=0,efigs=None):
 w,c,p=setup(True);w.russian=russian;w.game_lang=game_lang;w.shared[b.LANG_SETTING]=setting
 if efigs is not None:w.efigs=efigs
 w.step(c,p,n=3);return w,c,p
for setting,russian,game_lang,expect in [(0,False,0,0),(0,True,5,1),(0,False,1,2),(0,False,2,0),(0,False,3,0),(0,False,4,0),(0,False,6,0),(1,True,5,0),(1,False,1,0),(2,False,0,1),(3,False,0,2),(3,True,5,2)]:
 w,c,p=lang_world(setting,russian,game_lang);assert w.shared[b.LANG]==expect,(setting,russian,game_lang,w.shared[b.LANG])
w,c,p=lang_world(0,False,1,efigs=0);assert w.shared[b.LANG]==0,'language index 1 without the EFIGS font in use is not SanLTD'
for russian,game_lang in ((True,5),(False,1)):
 w,c,p=lang_world(0,russian,game_lang);w.shared[b.GAME_OK]=0;w.shared[b.LANG_SETTING]=0;w.step(c,p,n=3);assert w.shared[b.LANG]==0,'an unknown game build is never probed'
passed('AUTO follows the game: its own Russian -> game layout, the French slot with the EFIGS font (SanLTD) -> SanLTD layout, English / German / Italian / Spanish / Japanese -> English; explicit settings win; an unknown build stays English')
# messages use the key of the language in force
def keys_printed(w):return [x[2][0] for x in calls(w,0x3e5)]
for setting,prefix in [(1,'H'),(2,'U'),(3,'V')]:
 w,c,p=lang_world(setting);w.calls.clear();w.shared[b.CMD]=1;w.step(c,p,n=8);ks=keys_printed(w);assert ks and all(k_[0]==prefix for k_ in ks),(setting,ks)
passed('Notices use the English key, the U key (game Russian) or the V key (SanLTD) depending on the language')

# =================================================================== the menu
def open_menu(setting=1,summoned=True,aboard=False):
 w,c,p=setup(True);w.shared[b.LANG_SETTING]=setting
 if summoned:summon(w,c)
 if aboard:w.incar[1]=c.v[5]
 launch=VM('Helicover',w);w.step(c,p,launch,n=15);return w,c,p
def rows_of(w):return w.menu[2:]
w,c,p=open_menu()
assert w.menu[0]==b'HELICOVER / FOLLOWING' and rows_of(w)==[b'FOLLOW ME [X]',b'HOLD HERE',b'PATROL AROUND ME',b'GUNNER FIRE >',b'CLIMB ABOARD BY ROPE',b'DEPLOY SQUAD',b'SETTINGS >',b'DISMISS HELICOPTER']
MAIN_RU=('ЛЕТЕТЬ ЗА МНОЙ [X]','ЖДАТЬ ЗДЕСЬ','ПАТРУЛЬ ВОКРУГ','ОГОНЬ СТРЕЛКОВ >','НА БОРТ ПО ВЕРЕВКЕ','ВЫСАДИТЬ ОТРЯД','НАСТРОЙКИ (SETTINGS) >','ОТПУСТИТЬ ВЕРТОЛЕТ')
for setting,prof,draw,look in [(2,'game',draw_game,lambda s:s),(3,'sanltd',draw_sanltd_menu,sanltd_look)]:
 w,c,p=open_menu(setting)
 assert rows_of(w)==[i18n.encode(x,prof) for x in MAIN_RU],(setting,rows_of(w))
 assert [draw(r_) for r_ in rows_of(w)]==[look(x) for x in MAIN_RU],('what the player reads',[draw(r_) for r_ in rows_of(w)])
 assert draw(w.menu[0])==look('HELICOVER / ЛЕТИТ ЗА ВАМИ'),draw(w.menu[0])
passed('The main menu in Russian reads correctly in both simulated fonts: rows and the state in the title')
# every blob: at most 8 rows, short rows, all three languages present, nothing unreadable
import collections
panel=VM('Helicover_Panel',World())
for label,data in b.p.data.items():
 fields=data[4:].split(b'\0')
 rows=[f_ for f_ in fields[2:] if f_]
 assert len(rows)<=8,(label,len(rows))
 if label.startswith(('MAIN_','SETUP_','PREF_','DISMISS_')):
  for r_ in rows:assert len(r_)<=(30 if label.endswith(('_U','_V')) else 26),(label,r_,len(r_))
  if label.endswith('_U'):
   for f_ in [fields[0]]+rows:assert '@' not in draw_game(f_) and BAD not in draw_game(f_),(label,draw_game(f_))
  if label.endswith('_V'):
   for f_ in [fields[0]]+rows:assert BAD not in draw_sanltd_menu(f_),(label,draw_sanltd_menu(f_))
for base in [l_ for l_ in b.p.data if l_.startswith('MAIN_') and not l_.endswith(('_U','_V'))]:
 assert base+'_U' in b.p.data and base+'_V' in b.p.data
 assert len(b.p.data[base].split(b'\0'))==len(b.p.data[base+'_U'].split(b'\0'))==len(b.p.data[base+'_V'].split(b'\0')),base
passed('Every menu page has an English, a game-Russian and a SanLTD version with the same rows; at most 8 rows, none longer than 26 (RU 30) characters, no unreadable code in any title or row')

# =================================================================== language and FONT TEST pages
w,c,p=open_menu(1)
w.events.append(6);w.step(c,p,n=4);assert w.menu[0]==b'HELICOVER / SETTINGS' and w.menu[8]==b'LANGUAGE >',w.menu
w.events.append(6);w.step(c,p,n=4);assert w.menu[0]==b'LANGUAGE' and rows_of(w)==[b'AUTO',b'ENGLISH [X]',b'RUSSIAN (GAME RUSSIAN)',b'RUSSIAN (SANLTD)',b'FONT TEST',b'< BACK'],w.menu
w.events.append(3);w.step(c,p,n=6);assert w.shared[b.LANG_SETTING]==3 and w.shared[b.LANG]==2 and rows_of(w)[3]==b'RUSSIAN (SANLTD) [X]',(w.shared[b.LANG_SETTING],w.menu)
w.events.append(0);w.step(c,p,n=6);assert w.shared[b.LANG_SETTING]==0 and rows_of(w)[0]==b'AUTO [X]'
w.events.append(2);w.step(c,p,n=6);assert w.shared[b.LANG]==1
w.events.append(5);w.step(c,p,n=5);assert w.menu[0]==i18n.encode('HELICOVER / НАСТРОЙКИ','game'),'BACK from LANGUAGE leaves the settings page in the language just chosen'
passed('SETTINGS > LANGUAGE: AUTO / ENGLISH / RUSSIAN (GAME RUSSIAN) / RUSSIAN (SANLTD), the choice applies at once and the pages follow')
w,c,p=open_menu(1)
w.events.append(6);w.step(c,p,n=4);w.events.append(6);w.step(c,p,n=4);w.events.append(4);w.step(c,p,n=4)
assert w.menu[0]==b'FONT TEST 1 / 2' and rows_of(w)[:4]==i18n.font_test_rows('game') and rows_of(w)[4:]==[b'SHOW MESSAGE (GAME RUSSIAN)',b'NEXT >',b'< BACK'],w.menu
assert [draw_game(r_) for r_ in rows_of(w)[:4]]==['1: '+s for s in (i18n.ALPHA_UP1,i18n.ALPHA_UP2,i18n.ALPHA_LO1,i18n.ALPHA_LO2)],'page 1 shows the alphabet in order when the layout is right'
w.calls.clear();w.events.append(4);w.step(c,p,n=3);assert [k for k in keys_printed(w) if k=='UFTEST'],keys_printed(w)
w.events.append(5);w.step(c,p,n=4);assert w.menu[0]==b'FONT TEST 2 / 2' and rows_of(w)[:4]==i18n.font_test_rows('sanltd') and rows_of(w)[4]==b'SHOW MESSAGE (SANLTD)'
assert [draw_sanltd_menu(r_) for r_ in rows_of(w)[:2]]==['2: '+s.translate(LOOK) for s in (i18n.ALPHA_UP1,i18n.ALPHA_UP2)],'page 2 shows the capitals in order in SanLTD'
assert rows_of(w)[2][:3]==b'R: ' and set(rows_of(w)[2][3:]+rows_of(w)[3][3:])==set(range(0x96,0xB0)),'and the raw codes 0x96-0xAF that are still to be read off a screenshot'
w.calls.clear();w.events.append(4);w.step(c,p,n=3);assert [k for k in keys_printed(w) if k=='VFTEST'],keys_printed(w)
w.events.append(5);w.step(c,p,n=4);assert w.menu[0]==b'FONT TEST 1 / 2'
w.events.append(6);w.step(c,p,n=4);assert w.menu[0]==b'LANGUAGE'
passed('FONT TEST: page 1 is the alphabet for the game\'s Russian, page 2 the capitals and the unknown codes for SanLTD; each prints its test message')
# the launcher's "files missing" message follows the same rule
def missing_key(russian,game_lang):
 w=World();w.russian=russian;w.game_lang=game_lang;launch=VM('Helicover',w);w.step(launch,n=12);return [x[2][0] for x in calls(w,0x3e5)]
assert missing_key(False,0)==['HCOFF'] and missing_key(True,5)==['UCOFF'] and missing_key(False,1)==['VCOFF'] and missing_key(False,3)==['HCOFF'],(missing_key(False,0),missing_key(True,5),missing_key(False,1))
passed('The launcher\'s "files missing" message is English, game Russian or SanLTD by the same rule as AUTO')

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
