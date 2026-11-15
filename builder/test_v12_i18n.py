"""Helicover 1.2 language and menu (beta 4, beta 5: the menu opens at once): one rule for the language - the game's own Russian -> Russian, anything else -> English -
no language page, no FONT TEST, no SanLTD layout; the menu pages in both languages; rows that show an operation in progress instead of
a button that could be pressed twice; the exit rows as switches; DISMISS with a squad on the ground.
The game's Russian font is simulated from libGTASA's CFont code; the layout itself was confirmed on the player's phone (beta 3)."""
import math,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;P=HERE/'test_v25.py'
_src=P.read_text();g={'__file__':str(P),'__name__':'v25_harness'}
exec(compile(_src[:_src.index('results=[]')],str(P),'exec'),g)
for _m in re.finditer(r'^def [a-z_0-9]+\(.*?(?=^\S)',_src,re.S|re.M):exec(compile(_m.group(0),str(P),'exec'),g)
World,VM,b,setup,summon,calls,command,invariants=g['World'],g['VM'],g['b'],g['setup'],g['summon'],g['calls'],g['command'],g['invariants']
import i18n_v12 as i18n
import msg_v42 as mv
results=[]
def passed(t):results.append('PASS: '+t)

# =================================================================== the game's Russian font
UP=i18n.ALPHABET;LO=UP.lower();BAD='�'   # a code the font has no glyph for
def draw_game(raw):
 """The game's own Russian: one atlas, glyph = code - 0x20, 164 glyphs; past its end everything is '@' (GetJapaneseWidth / PrintChar)."""
 out=''
 for c in raw:
  if c<0x7F:out+=chr(c)
  elif 0x80<=c<=0x9F:out+=UP[c-0x80]
  elif 0xA0<=c<=0xBF:out+=LO[c-0xA0]
  elif 0xC0<=c<=0xC3:out+='…⛊★♥'[c-0xC0]      # ellipsis, shield, star, heart
  else:out+='@' if c>0xC3 else BAD
 return out
old_keyboard=bytes([203,206,195,182,197,181,205])+b': '+bytes([235,238,236,239,229])+b'.'     # "СТРЕЛКИ: чисто." in the wrong layout of beta 1
assert draw_game(old_keyboard)=='@@♥ц@х@: @@@@@.','screenshot of beta 1: the help box in the game\'s Russian'
assert draw_game(bytes(range(0xC0,0xD0)))=='…⛊★♥'+'@'*12,'screenshot of beta 1: a row of CP1251 capitals in the game\'s Russian'
passed('The simulated font of the game\'s Russian reproduces the player\'s screenshots of beta 1 (@@♥ц@х@)')

# =================================================================== the table and the FXT files
assert i18n.PROFILES==('en','game') and not hasattr(i18n,'vkey') and not hasattr(i18n,'SANLTD') and not hasattr(b,'LANG_SETTING'),'one Russian layout, no language setting'
assert i18n.encode('АЯая','game')==bytes([0x80,0x9F,0xA0,0xBF]) and i18n.encode('хц','game')==bytes([181,182]),'the two letters read off the screenshot sit where the layout puts them'
assert i18n.encode('Ёё','game')==i18n.encode('Ее','game'),'no IO in the official atlas'
assert len({i18n.encode(ch,'game') for ch in UP+LO})==64 and all(0x80<=i18n.encode(ch,'game')[0]<=0xBF for ch in UP+LO)
assert i18n.encode('Hello ~b~1 2 3!','game')==b'Hello ~b~1 2 3!','Latin text, digits and colour tags stay as they are'
passed('Game Russian: А-Я = 0x80-0x9F, а-я = 0xA0-0xBF (х = 181, ц = 182 as on the screenshot), Latin and tags untouched; it is the only Russian layout')
fxt={};en_raw=(b.OUT/'Helicover.fxt').read_bytes();raw=(b.OUT/'Helicover_RU.fxt').read_bytes()
assert max(en_raw)<0x80,'the English file stays plain ASCII'
for line in en_raw.split(b'\n')+raw.split(b'\n'):
 if line.strip():k,v=line.split(b' ',1);assert k.decode() not in fxt,('duplicate key',k);fxt[k.decode()]=v
en_keys=[k for k in fxt if k[0]!='U'];ru_keys=[k for k in fxt if k[0]=='U']
assert len(en_keys)==len(i18n.RU_MESSAGES)==len(ru_keys) and not [k for k in fxt if k[0]=='V' or 'FTEST' in k],(len(en_keys),len(ru_keys))
assert {k.split(b' ',1)[0].decode() for k in raw.split(b'\n') if k.strip()}==set(ru_keys),'Helicover_RU.fxt holds the U keys and nothing else'
for k in en_keys:
 assert i18n.ukey(k) in fxt,k
 ru=i18n.RU_MESSAGES[k];assert fxt[i18n.ukey(k)]==i18n.fxt_text(k),k
 assert len(k)<=7 and len(i18n.ukey(k))<=7 and b'\r' not in fxt[i18n.ukey(k)]
 assert re.findall(rb'~.~',fxt[i18n.ukey(k)])==re.findall(rb'~.~',fxt[k]),('colour tags',k)
 assert len(i18n.visible(ru))<=i18n.RU_PLAIN_LIMIT,(k,len(i18n.visible(ru)))
passed('Helicover.fxt (ASCII) holds the %d English messages, Helicover_RU.fxt the same ones with U keys (no third layout, no test message), same colour tags'%len(en_keys))
for k in en_keys:   # what the player reads
 ru=i18n.RU_MESSAGES[k];shown=draw_game(fxt[i18n.ukey(k)]);assert shown==ru.replace('ё','е').replace('Ё','Е') and '@' not in shown and BAD not in shown,(k,shown)
passed('Every one of the %d messages reads back as its Russian text in the simulated font, no @ anywhere'%len(en_keys))

# =================================================================== which language is in force: the game decides, nothing else
def lang_world(russian=False,game_lang=0,efigs=None):
 w,c,p=setup(True);w.russian=russian;w.game_lang=game_lang
 if efigs is not None:w.efigs=efigs
 w.step(c,p,n=3);return w,c,p
for russian,game_lang,efigs,expect in [(False,0,None,0),(True,5,None,1),(False,1,1,0),(False,1,0,0),(False,2,None,0),(False,3,None,0),(False,4,None,0),(False,6,None,0)]:
 w,c,p=lang_world(russian,game_lang,efigs);assert w.shared[b.LANG]==expect,(russian,game_lang,efigs,w.shared[b.LANG])
w,c,p=lang_world(True,5);w.shared[b.GAME_OK]=0;w.step(c,p,n=3);assert w.shared[b.LANG]==0,'an unknown game build is never probed: English'
passed('The language follows the game: its own Russian -> Russian; English, SanLTD (the French slot), German, Italian, Spanish, Japanese -> English; an unknown build -> English')
def keys_printed(w):return [x[2][0] for x in calls(w,0x3e5)]
w,c,p=lang_world(False);w.calls.clear();w.shared[b.CMD]=1;w.step(c,p,n=8);ks=keys_printed(w);assert ks and all(k_[0]=='H' for k_ in ks),ks
w.russian=True;w.game_lang=5;w.step(c,p,n=3);assert w.shared[b.LANG]==1,'the player switched the game to Russian in the pause menu'
w.calls.clear();w.shared[b.MSG_UNTIL]=0;w.shared[b.CMD]=3;w.step(c,p,n=8);ks=keys_printed(w);assert ks and all(k_[0]=='U' for k_ in ks),ks
w.russian=False;w.game_lang=1;w.step(c,p,n=3);assert w.shared[b.LANG]==0
w.calls.clear();w.shared[b.MSG_UNTIL]=0;w.shared[b.CMD]=2;w.step(c,p,n=8);ks=keys_printed(w);assert ks and all(k_[0]=='H' for k_ in ks),ks
passed('Changing the game language while playing changes the mod\'s language at once (messages: English keys / U keys)')

# =================================================================== the menu
def open_menu(russian=False,summoned=True,aboard=False):
 w,c,p=setup(True);w.russian=russian;w.game_lang=5 if russian else 0
 if summoned:summon(w,c)
 if aboard:w.incar[1]=c.v[5]
 launch=VM('Helicover',w);w.step(c,p,launch,n=15);return w,c,p
def rows_of(w):return w.menu[2:]
def press(w,vms,index,n=8):w.events.append(index);w.step(*vms,n=n)
def orders_given(w):return [x[2][1] for x in calls(w,0xddc) if x[2][0]==b.CMD and x[2][1]!=0]
w,c,p=open_menu()
assert w.menu[0]==b'HELICOVER / FOLLOWING' and rows_of(w)==[b'FOLLOW ME [X]',b'HOLD HERE',b'PATROL AROUND ME',b'GUNNER FIRE >',b'CLIMB ABOARD BY ROPE',b'DEPLOY SQUAD',b'SETTINGS >',b'DISMISS HELICOPTER']
MAIN_RU=('ЛЕТЕТЬ ЗА МНОЙ [X]','ЖДАТЬ ЗДЕСЬ','ПАТРУЛЬ ВОКРУГ','ОГОНЬ СТРЕЛКОВ >','НА БОРТ ПО ВЕРЕВКЕ','ВЫСАДИТЬ ОТРЯД','НАСТРОЙКИ >','ОТПУСТИТЬ ВЕРТОЛЕТ')
w,c,p=open_menu(True)
assert rows_of(w)==[i18n.encode(x,'game') for x in MAIN_RU],rows_of(w)
assert [draw_game(r_) for r_ in rows_of(w)]==list(MAIN_RU) and draw_game(w.menu[0])=='HELICOVER / ЛЕТИТ ЗА ВАМИ',[draw_game(r_) for r_ in w.menu]
press(w,(c,p),6,5);assert [draw_game(r_) for r_ in w.menu]==['HELICOVER / НАСТРОЙКИ','CLOSE','ЭКИПАЖ >','МОДЕЛЬ ВЕРТОЛЕТА >','ОРУЖИЕ ЭКИПАЖА >','ТАКТИКА: ОХРАНА','СООБЩЕНИЯ: ВСЕ','< НАЗАД'],[draw_game(r_) for r_ in w.menu]
passed('With the game in Russian the menu is Russian and reads correctly in the simulated font: main page, state in the title, settings')
w,c,p=open_menu(True,aboard=True)
assert [draw_game(r_) for r_ in rows_of(w)]==['ЛЕТЕТЬ К МЕТКЕ НА КАРТЕ','ЛЕТЕТЬ НА ГРОУВ-СТРИТ','КНОПКА ВЫХОДА: ПОСАДКА [X]','КНОПКА ВЫХОДА: ВЕРЕВКА','ОГОНЬ СТРЕЛКОВ >','НАСТРОЙКИ >'],[draw_game(r_) for r_ in rows_of(w)]
w.calls.clear();w.messages.clear();press(w,(c,p),3)
assert w.shared[b.EXIT_MODE]==1 and draw_game(rows_of(w)[3])=='КНОПКА ВЫХОДА: ВЕРЕВКА [X]' and not orders_given(w) and w.incar.get(1)==c.v[5] and 'UCXBR' in w.messages,(w.menu,orders_given(w),w.messages)
passed('Aboard in Russian: the two exit-button switches; switching shows the Russian hint and starts nothing')
# every page: both languages, at most 8 rows, short rows, nothing unreadable, nothing left of the language page
for label,data in b.p.data.items():
 fields=data[4:].split(b'\0');rows=[f_ for f_ in fields[2:] if f_]
 assert len(rows)<=8,(label,len(rows))
 assert not label.endswith('_V') and not any(word in f_ for f_ in fields for word in (b'LANGUAGE',b'FONT TEST',b'SANLTD',b'RUSSIAN')),('nothing of the language page is left',label)
 if label.startswith(('MAIN_','SETUP_','PREF_','DISMISS_')):
  for r_ in rows:assert len(r_)<=(30 if label.endswith('_U') else 26),(label,r_,len(r_))
  if label.endswith('_U'):
   for f_ in [fields[0]]+rows:assert '@' not in draw_game(f_) and BAD not in draw_game(f_),(label,draw_game(f_))
bases=[l_ for l_ in b.p.data if l_.startswith(('MAIN_','SETUP_','PREF_','DISMISS_')) and not l_.endswith('_U')]
for base in bases:
 assert base+'_U' in b.p.data and len(b.p.data[base].split(b'\0'))==len(b.p.data[base+'_U'].split(b'\0')),base
assert all(len([f_ for f_ in b.p.data[l_][4:].split(b'\0')[2:] if f_])==6 for l_ in b.p.data if l_.startswith('SETUP_')),'settings: three sub-pages, two switches, BACK'
passed('Every one of the %d menu pages has an English and a Russian version with the same rows; at most 8 rows, none longer than 26 (RU 30) characters; no language page, no FONT TEST'%len(bases))
# the launcher's "files missing" message follows the same rule
def missing_key(russian,game_lang):
 w=World();w.russian=russian;w.game_lang=game_lang;launch=VM('Helicover',w);w.step(launch,n=12);return [x[2][0] for x in calls(w,0x3e5)]
assert missing_key(False,0)==['HCOFF'] and missing_key(True,5)==['UCOFF'] and missing_key(False,1)==['HCOFF'] and missing_key(False,3)==['HCOFF'],(missing_key(False,0),missing_key(True,5),missing_key(False,1))
passed('The launcher\'s "files missing" message is Russian in the game\'s Russian and English otherwise')

# =================================================================== rows that show an operation in progress (beta 4)
w,c,p=open_menu(summoned=False);assert rows_of(w)==[b'CALL HELICOPTER',b'SETTINGS >'],w.menu
w.calls.clear();press(w,(c,p),0,6);assert w.shared[b.STATE]==2 and w.menu[0]==b'HELICOVER / FOLLOWING' and rows_of(w)[0]==b'FOLLOW ME [X]',(w.shared[b.STATE],w.menu)
for _ in range(3):press(w,(c,p),0,3)
assert len(calls(w,0xa5))==1 and not invariants(w),(len(calls(w,0xa5)),invariants(w))
passed('CALL HELICOPTER: once called the page is the FOLLOWING page - there is no CALL row to press twice, and one helicopter exists')
# the "preparing" state itself (a frame or two in the game) and the swap states: a progress row, not a button
for st,row in [(1,b'HELICOPTER INBOUND...'),(16,b'CHANGING, PLEASE WAIT...'),(17,b'CHANGING, PLEASE WAIT...'),(13,b'HELICOPTER LEAVING...')]:
 w,c,p=open_menu();w.shared[b.STATE]=st;w.step(p,n=4);assert rows_of(w)==[row,b'GUNNER FIRE >',b'SETTINGS >'],(st,w.menu)
 w.calls.clear()
 for _ in range(3):press(w,(p,),0,3)
 assert not orders_given(w) and rows_of(w)[0]==row,(st,orders_given(w))
passed('While the helicopter is being prepared, swapped or is leaving the first row says so ("HELICOPTER INBOUND...", "CHANGING, PLEASE WAIT...", "HELICOPTER LEAVING...") and orders nothing')
def squad_menu(russian=False):
 w,c,p=setup(True);w.russian=russian;w.game_lang=5 if russian else 0;summon(w,c);ground=VM('Helicover_Ground',w);sq=VM('Helicover_Squad',w);launch=VM('Helicover',w)
 V=(c,p,ground,sq);w.step(*V,launch,n=15);return w,c,p,V
def hover(w,c):w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.
w,c,p,V=squad_menu()
w.calls.clear();press(w,V,0);press(w,V,0);assert not orders_given(w) or set(orders_given(w))=={2} and w.shared[b.STATE]==2,'FOLLOW ME [X] pressed again changes nothing'
assert not [k for k in keys_printed(w) if k=='HCFOLL'],'and the pilot does not repeat himself'
press(w,V,5);assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==1 and rows_of(w)[5]==b'SQUAD ROPING DOWN...' and rows_of(w)[4]==b'CLIMB ABOARD BY ROPE',(w.shared[b.STATE],w.menu)
w.calls.clear()
for _ in range(3):press(w,V,5,4)
assert not orders_given(w) and w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==1,'the progress row is not a button'
w.step(*V,n=14);w.calls.clear();press(w,V,5,6);assert not orders_given(w) and w.shared[b.ESCORT_PENDING]==1,'nor is it one for a single deliberate tap after a pause'
hover(w,c)
for _ in range(60):
 w.step(*V)
 if w.shared[b.ESCORT_ON]==2:break
w.step(*V,n=2);assert w.shared[b.ESCORT_ON]==2 and rows_of(w)[5]==b'SQUAD ROPING DOWN...',(w.shared[b.ESCORT_ON],w.menu)
first=[w.shared[b.GROUND_PUB+i] for i in range(4)];w.calls.clear()
for _ in range(3):press(w,V,5,4)
assert not {16,17}&set(orders_given(w)) and [w.shared[b.GROUND_PUB+i] for i in range(4)]==first and len(calls(w,0x503))==0,'pressing while the team is on the ropes creates nobody'
w.step(*V,n=40);assert w.shared[b.ESCORT_ON]==1 and rows_of(w)[5]==b'RECALL SQUAD',(w.shared[b.ESCORT_ON],w.menu)
w.car=[0.,-45.,28.];w.speed=12.;w.step(*V,n=12)   # the helicopter went back to following: it is not over the squad any more
press(w,V,5);assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==2 and rows_of(w)[5]==b'SQUAD COMING BACK...',(w.shared[b.STATE],w.menu)
w.calls.clear()
for _ in range(3):press(w,V,5,4)
assert not {16,17}&set(orders_given(w)) and w.shared[b.ESCORT_PENDING]==2
hover(w,c)
for _ in range(600):
 w.step(*V)
 if w.shared[b.ESCORT_ON]==0:break
w.step(*V,n=8)
assert w.shared[b.ESCORT_ON]==0 and rows_of(w)[5]==b'DEPLOY SQUAD' and all(t not in w.exists for t in first) and not w.handed and not invariants(w),(w.shared[b.ESCORT_ON],w.menu,w.handed,invariants(w))
passed('The squad row: DEPLOY SQUAD -> "SQUAD ROPING DOWN..." -> RECALL SQUAD -> "SQUAD COMING BACK..." -> DEPLOY SQUAD; the two progress rows order nothing however often they are pressed')
w,c,p,V=squad_menu(True)
press(w,V,5);assert draw_game(rows_of(w)[5])=='ОТРЯД ВЫСАЖИВАЕТСЯ...',draw_game(rows_of(w)[5])
hover(w,c);w.step(*V,n=60);assert draw_game(rows_of(w)[5])=='ЗАБРАТЬ ОТРЯД'
press(w,V,5);assert draw_game(rows_of(w)[5])=='ОТРЯД ВОЗВРАЩАЕТСЯ...'
w,c,p,V=squad_menu(True);press(w,V,4);assert draw_game(rows_of(w)[4])=='ОТМЕНИТЬ ПОДЪЕМ' and draw_game(w.menu[0])=='HELICOVER / ЛЕТИТ К ВАМ С ВЕРЕВКОЙ' or draw_game(rows_of(w)[4])=='ОТМЕНИТЬ ПОДЪЕМ',(draw_game(rows_of(w)[4]),draw_game(w.menu[0]))
passed('The same rows in Russian: ОТРЯД ВЫСАЖИВАЕТСЯ... / ЗАБРАТЬ ОТРЯД / ОТРЯД ВОЗВРАЩАЕТСЯ... / ОТМЕНИТЬ ПОДЪЕМ')
# the rope row: order -> cancel
w,c,p,V=squad_menu()
press(w,V,4);assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==0 and rows_of(w)[4]==b'CANCEL ROPE PICKUP' and rows_of(w)[5]==b'DEPLOY SQUAD',(w.shared[b.STATE],w.menu)
w.calls.clear();press(w,V,4,5);assert w.shared[b.STATE]==19 and not orders_given(w),'a second tap within a second of the first is the same tap (no order - cancel - order flicker)'
w.step(*V,n=8);w.messages.clear();press(w,V,4);assert w.shared[b.STATE]==2 and 'HCRCAN' in w.messages and rows_of(w)[4]==b'CLIMB ABOARD BY ROPE' and rows_of(w)[0]==b'FOLLOW ME [X]',(w.shared[b.STATE],w.messages,w.menu)
w.step(*V,n=8);press(w,V,4);hover(w,c);w.step(*V,n=30);assert w.shared[b.STATE]==3 and w.shared[b.ROPE_WAIT]==1 and rows_of(w)[4]==b'CANCEL ROPE PICKUP' and rows_of(w)[1]==b'HOLD HERE',(w.shared[b.STATE],w.shared[b.ROPE_WAIT],w.menu)
passed('The rope row: CLIMB ABOARD BY ROPE -> CANCEL ROPE PICKUP (on the way in the cancel sends the helicopter back to following); the hover for the rope is not marked as HOLD')
w,c,p=open_menu();press(w,(c,p),7,4);press(w,(c,p),0,8)
assert w.shared[b.STATE]==4 and w.menu[0]==b'HELICOVER / DEPARTING' and rows_of(w)==[b'HELICOPTER LEAVING...',b'GUNNER FIRE >',b'SETTINGS >'],(w.shared[b.STATE],w.menu)
w.calls.clear()
for _ in range(3):press(w,(c,p),0,3)
assert not orders_given(w) and w.shared[b.STATE]==4
passed('DISMISS: the page becomes "HELICOPTER LEAVING..." and nothing can be ordered until it is gone')

# =================================================================== taps that must not count (beta 4)
w,c,p=open_menu();press(w,(c,p),6,5);assert w.menu[0]==b'HELICOVER / SETTINGS' and w.shared[b.CREW]==2
w.events.append(0);w.step(c,p);w.events.append(0);w.step(c,p,n=5)   # a double tap on "CREW >"
assert w.menu[0]==b'HELICOVER / CREW' and w.shared[b.CREW]==2 and rows_of(w)[2]==b'SWAT [X]','the second tap of a double tap must not pick the first row of the page that opened (it used to change the crew to GROVE STREET)'
press(w,(c,p),3,5);w.events.append(1);w.step(c,p);w.events.append(1);w.step(c,p,n=5)   # back, then a double tap on "HELICOPTER MODEL >"
assert w.menu[0]==b'HELICOVER / HELICOPTER' and w.shared[b.MODEL]==487,(w.menu,w.shared[b.MODEL])
w,c,p=open_menu();w.events.append(3);w.step(c,p);w.events.append(3);w.step(c,p,n=5)   # a double tap on "GUNNER FIRE >"
assert w.menu[0]==b'HELICOVER / GUNNER FIRE' and w.shared[b.FIRE]==3,(w.menu,w.shared[b.FIRE])
w.step(c,p,n=2);press(w,(c,p),3,5);assert w.shared[b.FIRE]==1,'a deliberate tap half a second later is taken'
passed('A double tap on a row that opens a page opens the page and nothing more (no crew, helicopter or fire mode changed by the second tap)')
w,c,p=open_menu();w.incar[1]=c.v[5];w.calls.clear();w.events.append(1);w.step(c,p,n=4)   # CJ got aboard and the tap comes before the page is redrawn
assert not orders_given(w) and rows_of(w)[:2]==[b'FLY TO MAP MARKER',b'FLY TO GROVE STREET'] and w.shared[b.STATE]==2,(orders_given(w),w.menu)
passed('A tap on a page that is out of date (the situation changed this very moment) is not taken: the page is redrawn first')
w,c,p=open_menu();w.shared[b.ROPE_BUSY]=1;press(w,(c,p),7,5);w.calls.clear();press(w,(c,p),0,8)
assert not orders_given(w) and w.shared[b.DISMISS_T]!=0 and w.shared[b.STATE]==2,'ropes are moving: the dismissal waits (it used to be refused by the pilot and forgotten)'
w.shared[b.ROPE_BUSY]=0;w.step(c,p,n=6);assert 4 in orders_given(w) and w.shared[b.STATE]==4 and w.shared[b.DISMISS_T]==0
passed('DISMISS confirmed during rope work is carried out when the ropes are free')

# =================================================================== DISMISS with a squad on the ground
w,c,p=open_menu();w.shared[b.ESCORT_ON]=1;w.step(c,p,n=6)
press(w,(c,p),7,4);assert w.menu[0]==b'SEND THE HELICOPTER AWAY?' and rows_of(w)==[b'YES, RECALL SQUAD FIRST',b'NO, KEEP IT'],w.menu
w.calls.clear();w.messages.clear();press(w,(c,p),0,6);assert w.shared[b.STATE]==19 and w.shared[b.ESCORT_PENDING]==2 and 17 in orders_given(w),'the squad is recalled first'
assert w.shared[b.DISMISS_T]!=0 and 4 not in orders_given(w) and 'HCDSQ' in w.messages,'the helicopter does not leave while the team is still down, and the pilot says so'
w.shared[b.ESCORT_ON]=0;w.shared[b.ESCORT_PENDING]=0;w.shared[b.CMD]=2;w.step(c,p,n=8);assert 4 in orders_given(w) and w.shared[b.DISMISS_T]==0 and w.shared[b.STATE]==4,(orders_given(w),w.shared[b.STATE])
passed('DISMISS with a squad on the ground: recall first ("picking the squad up first"), the helicopter leaves when the squad is back aboard')
w,c,p=open_menu();w.shared[b.ESCORT_ON]=2;w.step(c,p,n=6);press(w,(c,p),7,4);assert rows_of(w)==[b'YES, RECALL SQUAD FIRST',b'NO, KEEP IT'],'the team is on the ropes: it is still a squad to bring back'
w.calls.clear();press(w,(c,p),0,6);w.step(c,p,n=20);assert not orders_given(w) and w.shared[b.DISMISS_T]!=0,'nothing is ordered while the team is on its way down'
w.shared[b.ESCORT_ON]=1;w.step(c,p,n=4);assert 17 in orders_given(w) and 4 not in orders_given(w),'once it has landed the recall is asked for'
passed('DISMISS while the squad is still roping down waits for the landing, then recalls it (the order used to be lost)')
w,c,p=open_menu();w.shared[b.ESCORT_ON]=1;w.siteclear=False;w.step(c,p,n=6);press(w,(c,p),7,4);w.calls.clear();press(w,(c,p),0,6)
assert orders_given(w).count(17)==1 and w.shared[b.STATE]!=19,'no clear site: the recall did not start'
w.now+=7000;w.step(c,p,n=3);assert orders_given(w).count(17)==2,'it is asked for again a few seconds later'
w.now+=46000;w.step(c,p,n=6);assert 4 in orders_given(w) and w.shared[b.DISMISS_T]==0,'after 45 s the dismissal goes ahead anyway'
passed('A recall that cannot start is retried every 6 s and does not keep the helicopter for ever: DISMISS goes through after 45 s')
w,c,p=open_menu();w.shared[b.ESCORT_ON]=1;w.step(c,p,n=6);press(w,(c,p),7,4);press(w,(c,p),0,6);assert w.shared[b.DISMISS_T]!=0
w.shared[b.ESCORT_ON]=3;w.step(c,p,n=3);w.calls.clear();press(w,(c,p),0,6)   # FOLLOW ME: the player changed his mind
w.shared[b.ESCORT_ON]=0;w.shared[b.ESCORT_PENDING]=0;w.step(c,p,n=10);assert w.shared[b.DISMISS_T]==0 and 4 not in orders_given(w) and w.shared[b.STATE]!=4,(orders_given(w),w.shared[b.STATE])
passed('Another order withdraws a dismissal that was still waiting for the squad')
w,c,p=open_menu();press(w,(c,p),7,4);assert rows_of(w)==[b'YES, DISMISS IT',b'NO, KEEP IT'];press(w,(c,p),0,8);assert w.shared[b.STATE]==4
w,c,p=open_menu();press(w,(c,p),7,4);press(w,(c,p),1,5);assert w.shared[b.STATE]==2 and w.menu[0]==b'HELICOVER / FOLLOWING' and w.shared[b.DISMISS_T]==0
passed('DISMISS without a squad is immediate after the confirmation; "NO, KEEP IT" changes nothing')

# models for the CREW and HELICOPTER pages are requested while the page is open and released after
w,c,p=open_menu();w.calls.clear();press(w,(c,p),6,4);press(w,(c,p),0,4)
assert w.menu[0]==b'HELICOVER / CREW' and {x[2][0] for x in calls(w,0x247)}=={105,106,107,285,287},'only the crew skins are requested when the CREW page opens (not three helicopter models)'
w.calls.clear();press(w,(c,p),3,4);press(w,(c,p),1,4)
assert w.menu[0]==b'HELICOVER / HELICOPTER' and {x[2][0] for x in calls(w,0x247)}=={487,497,425},'the helicopter models when the HELICOPTER page opens'
w.calls.clear();press(w,(c,p),3,4);press(w,(c,p),5,4);assert w.menu[0]==b'HELICOVER / FOLLOWING' and {x[2][0] for x in calls(w,0x249)}>={285,287,487,497,425},'and released when the pages are left'
passed('Crew and helicopter models are pre-requested while their pages are open, so choosing one does not stall a frame')

# =================================================================== beta 5: the menu opens at once
def frames_until(w,vms,cond,limit=60):
 for n in range(1,limit+1):
  w.step(*vms)
  if cond(w):return n
 return None
def main_page(w):return w.menu is not None and w.menu[0]==b'HELICOVER / FOLLOWING'
OFFLINE=i18n.menu_text('OFFLINE_TITLE','en')
def missing(w):return [x[2][0] for x in calls(w,0x3e5) if x[2][0] in('HCOFF','UCOFF')]
def offline_page(w):return w.menu is not None and w.menu[0]==OFFLINE
def launch_world(frame_ms=100,phase=0,order=0,core=True,panel=True,summoned=True):
 w=World();c=VM('Helicover_Core',w);p=VM('Helicover_Panel',w);w.step(c,p,n=3)
 if summoned:summon(w,c)
 w.frame_ms=frame_ms;w.step(c,p,n=phase);launch=VM('Helicover',w)
 vms=[v for v,on in ((c,core),(p,panel))if on];vms=vms+[launch] if order==0 else [launch]+vms[::-1]
 return w,c,p,vms
slowest=0
for frame_ms in (100,33,16):
 for phase in range(8):
  for order in (0,1):
   w,c,p,vms=launch_world(frame_ms,phase,order);n=frames_until(w,vms,main_page);assert n is not None and n<=2,(frame_ms,phase,order,n);slowest=max(slowest,n)
   assert w.shared[b.OPEN]==0 and not missing(w),'the request is taken and nothing is reported missing'
passed('Tapping "helicover" in the CLEO list: the menu is on the screen %d frame(s) later at 10, 30 and 60 fps, whatever the scripts were doing (it used to take 0.9 s of fixed pauses)'%slowest)
# the launcher's proof of life when the stamp is no use: the panel is not there / has stopped / the stamp is out of date
w=World();launch=VM('Helicover',w);n=frames_until(w,(launch,),missing);assert n is not None and n*100<=b.PANEL_PROOF_MS+200 and w.shared[b.OPEN]==0 and w.menu is None,n
w,c,p,vms=launch_world(panel=False);w.now+=3000;n=frames_until(w,vms,missing)
assert n is not None and n*100<=b.PANEL_PROOF_MS+200 and missing(w)==['HCOFF'] and w.shared[b.OPEN]==0 and w.menu is None,(n,w.menu)
w,c,p,vms=launch_world(panel=False);w.shared[b.PANELHEART]=w.now+60000;n=frames_until(w,vms,missing);assert n is not None and w.shared[b.OPEN]==0,'a stamp ahead of the clock is no proof of life either'
passed('No menu script (never started, or stopped a few seconds ago): the launcher says "files missing" within 0.7 s and leaves no open request behind')
for order in (0,1):
 for shift in (5000,-60000):     # the scripts were held while the clock ran / a loaded save put the clock back
  w,c,p,vms=launch_world(order=order)
  if shift>0:w.now+=shift
  else:w.shared[b.PANELHEART]=w.now-shift;w.shared[b.HEART]=w.now-shift
  n=frames_until(w,vms,main_page);assert n is not None and n<=3 and not missing(w),(order,shift,n,w.menu)
passed('A heartbeat that is out of date (or ahead of the clock after a loaded save) with both scripts alive: the menu still opens, 3 frames at most - a stale stamp alone never means "missing"')
# the panel's proof of life for the core
for frame_ms in (100,33,16):
 w=World();p=VM('Helicover_Panel',w);w.frame_ms=frame_ms;w.step(p,n=3);launch=VM('Helicover',w);n=frames_until(w,(p,launch),lambda w:w.menu is not None)
 assert offline_page(w) and n*frame_ms<=b.CORE_PROOF_MS+3*frame_ms,(frame_ms,n,w.menu)
w,c,p,vms=launch_world(core=False);w.step(p,n=30);n=frames_until(w,vms,lambda w:w.menu is not None);assert offline_page(w) and n*100<=b.CORE_PROOF_MS+300,(n,w.menu)
w.events.append(0);w.step(*vms,n=3);assert not orders_given(w),'the OFFLINE page orders nothing'
w,c,p,vms=launch_world(core=False);w.shared[b.HEART]=w.now+60000;n=frames_until(w,vms,lambda w:w.menu is not None);assert offline_page(w),'a core stamp ahead of the clock is no proof of life either'
for stamp in (-5000,60000):     # the core is alive but its stamp is no use: the panel waits for the next one instead of giving up
 w,c,p,vms=launch_world();w.shared[b.OPEN]=1;w.shared[b.HEART]=w.now+stamp;n=frames_until(w,(p,c),lambda w:w.menu is not None);assert main_page(w) and n<=3,(stamp,n,w.menu)
passed('No core script (never started, or stopped 3 s ago): the OFFLINE page, 0.25 s after the tap')
# an order is picked up at once: the page follows the tap
slow_page=slow_call=0
for frame_ms in (100,33,16):
 for phase in range(6):
  w,c,p=open_menu();w.frame_ms=frame_ms;w.step(c,p,n=phase);w.calls.clear();w.events.append(1)
  n=frames_until(w,(c,p),lambda w:rows_of(w)[1]==b'HOLD HERE [X]');assert n is not None and n<=2 and orders_given(w)==[3],(frame_ms,phase,n,w.menu);slow_page=max(slow_page,n)
  w,c,p=open_menu(summoned=False);w.frame_ms=frame_ms;w.step(c,p,n=phase);w.calls.clear();w.events.append(0)
  n=frames_until(w,(c,p),lambda w:w.shared[b.STATE]!=0);assert n is not None and n<=2,(frame_ms,phase,n);slow_call=max(slow_call,n)
  n=frames_until(w,(c,p),main_page);assert n is not None and n<=3 and len(calls(w,0xa5))==1,(frame_ms,phase,n,w.menu)
passed('A tapped row: the core takes the order within %d frame(s) and the page shows the result within %d (HOLD HERE gets its [X], CALL HELICOPTER turns into the FOLLOWING page) - no fixed 0.2 s pause, no waiting for the core\'s 0.1 s tick'%(slow_call,slow_page))
# CLEO may keep reporting a tap for up to 250 ms (the second argument of 0DF4): with a page that now changes at once the same
# report must not land on the new page
def tap_run(frame_ms,row,sticky_ms):
 w,c,p=open_menu();w.frame_ms=frame_ms;w.step(c,p,n=3);w.calls.clear();t0=w.now;w.events.append(row);w.step(c,p)
 while w.now-t0<sticky_ms:w.events.clear();w.events.append(row);w.step(c,p)
 w.events.clear();w.step(c,p,n=int(600/frame_ms));return w.menu,orders_given(w),[w.shared[k] for k in (b.FIRE,b.CREW,b.MODEL,b.TACTICS,b.EXIT_MODE,b.HUD,b.DISMISS_T)]
for frame_ms in (100,33,16):
 for row in range(8):assert tap_run(frame_ms,row,250)==tap_run(frame_ms,row,0) and len(tap_run(frame_ms,row,250)[1])<=1,(frame_ms,row,tap_run(frame_ms,row,250),tap_run(frame_ms,row,0))
passed('A tap that CLEO keeps reporting for 0.25 s does exactly what a single report does on all 8 rows at 10, 30 and 60 fps: one order at most, and nothing is chosen on the page that has just opened')
# the core's nap: 100 ms as before when nothing is asked, cut short by an order, never a frame-by-frame loop
for frame_ms,lo,hi in ((100,19,21),(33,14,16),(16,17,19)):
 w,c,_=setup();summon(w,c);w.frame_ms=frame_ms;w.step(c,n=5);w.calls.clear();w.step(c,n=int(2000/frame_ms))
 beats=len([x for x in calls(w,0xddc) if x[2][0]==b.HEART]);assert lo<=beats<=hi,(frame_ms,beats)
passed('Nothing asked: the core still works once per 0.1 s (20 passes in 2 s at 10 fps, 15 at 30 fps, 18 at 60 fps - the same as with the plain pause)')
late={}
for sit in ('none','follow','aboard','squad','rope','leaving'):
 for cmd in range(1,40):
  w,c,p=setup(True)
  if sit!='none':summon(w,c)
  if sit=='aboard':w.incar[1]=c.v[5]
  ground=VM('Helicover_Ground',w);sq=VM('Helicover_Squad',w);V=(c,p,ground,sq);w.step(*V,n=3)
  if sit in('squad','rope'):w.shared[b.CMD]=16;w.step(*V,n=6)
  if sit=='squad':hover(w,c);w.step(*V,n=40)
  if sit=='leaving':w.shared[b.CMD]=4;w.step(*V,n=6)
  w.frame_ms=16;w.shared[b.CMD]=cmd;n=frames_until(w,V,lambda w:w.shared[b.CMD]==0,limit=30)
  if n is None or n>(7 if sit=='leaving' else 2):late[(sit,cmd)]=n
  assert not invariants(w),(sit,cmd,invariants(w))
assert not late,late
passed('Any order number in any situation (no helicopter, following, aboard, squad down, roping, leaving) is taken or dropped within 2 frames (while leaving: 0.1 s) - an order never stays pending, so the nap cannot turn into a busy loop')

text='\n'.join(results)+'\nMocked script execution only: the Russian layout was confirmed on the player\'s phone (beta 3); the look of the menu itself is the game\'s.\n'
(b.OUT/'i18n_tests.txt').write_text(text);print(text)
