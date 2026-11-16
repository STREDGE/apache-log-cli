"""Helicover 1.2 language and menu (beta 4, beta 5: the menu opens at once, beta 6: notifications as a drawn line, brave crew, kneeling gunners): one rule for the language - the game's own Russian -> Russian, anything else -> English -
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
def keys_printed(w):return [x[2][2] for x in calls(w,0x33e)]   # beta 6: the key the fire worker draws on the screen
w,c,p=lang_world(False);fw_=VM('Helicover_Fire',w);V_=(c,p,fw_);w.step(*V_,n=2);w.calls.clear();w.shared[b.CMD]=1;w.step(*V_,n=8);ks=keys_printed(w);assert ks and all(k_[0]=='H' for k_ in ks),ks
w.russian=True;w.game_lang=5;w.step(*V_,n=3);assert w.shared[b.LANG]==1,'the player switched the game to Russian in the pause menu'
w.calls.clear();w.shared[b.MSG_UNTIL]=0;w.shared[b.CMD]=3;w.step(*V_,n=8);ks=keys_printed(w);assert ks and all(k_[0]=='U' for k_ in ks),ks
w.russian=False;w.game_lang=1;w.step(*V_,n=3);assert w.shared[b.LANG]==0
w.calls.clear();w.shared[b.MSG_UNTIL]=0;w.shared[b.CMD]=2;w.step(*V_,n=8);ks=keys_printed(w);assert ks and all(k_[0]=='H' for k_ in ks),ks
passed('Changing the game language while playing changes the mod\'s language at once (messages: English keys / U keys)')
# the kill counter is the one line still printed directly (a text with a number): it follows the language too
for russian_,key_ in ((False,'HCKILL'),(True,'UCKILL')):
 w,c,f_=g['fire_world']();w.russian=russian_;w.game_lang=5 if russian_ else 0;w.step(c,f_,n=3);npc_=g['target'](w,typ=7);w.weapons[npc_]=30;w.health[npc_]=100;w.damage.add((1,npc_))
 w.calls.clear();w.step(c,f_,n=40);assert npc_ in w.dead,'the gunners brought the attacker down (the brain counts the kill)'
 assert [x[2][0] for x in calls(w,0x1e5)]==[key_],(russian_,[x[2] for x in calls(w,0x1e5)])
passed('The kill counter ("TARGET DOWN n") is printed with the English key or its U key, like every other message')

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
assert w.menu[0]==b'HELICOVER / FOLLOWING' and rows_of(w)==[b'FOLLOW ME [X]',b'HOLD HERE',b'PATROL AROUND ME',b'MODE AND FIRE >',b'CLIMB ABOARD BY ROPE',b'DEPLOY SQUAD',b'SETTINGS >',b'DISMISS HELICOPTER']
MAIN_RU=('ЛЕТЕТЬ ЗА МНОЙ [X]','ЖДАТЬ ЗДЕСЬ','ПАТРУЛЬ ВОКРУГ','РЕЖИМ И ОГОНЬ >','НА БОРТ ПО ВЕРЕВКЕ','ВЫСАДИТЬ ОТРЯД','НАСТРОЙКИ >','ОТПУСТИТЬ ВЕРТОЛЕТ')
w,c,p=open_menu(True)
assert rows_of(w)==[i18n.encode(x,'game') for x in MAIN_RU],rows_of(w)
assert [draw_game(r_) for r_ in rows_of(w)]==list(MAIN_RU) and draw_game(w.menu[0])=='HELICOVER / ЛЕТИТ ЗА ВАМИ',[draw_game(r_) for r_ in w.menu]
press(w,(c,p),6,5);assert [draw_game(r_) for r_ in w.menu]==['HELICOVER / НАСТРОЙКИ','CLOSE','МОДЕЛЬ ВЕРТОЛЕТА >','СООБЩЕНИЯ: ВСЕ','МИССИИ: ОБОРОНА','< НАЗАД'],[draw_game(r_) for r_ in w.menu]
passed('With the game in Russian the menu is Russian and reads correctly in the simulated font: main page, state in the title, settings')
w,c,p=open_menu(True);press(w,(c,p),3,5)
assert [draw_game(r_) for r_ in w.menu]==['HELICOVER / РЕЖИМ И ОГОНЬ','CLOSE','РЕЖИМ: ЗАЩИТА','ОТМЕНА: КО МНЕ','ЗАЩИЩАТЬ МЕНЯ [X]','НЕ СТРЕЛЯТЬ','ТОЛЬКО ВООРУЖЕННЫЕ','ТАМ, ГДЕ СТРЕЛЯЮ Я','ПОЛИЦИЯ: ОТВЕЧАТЬ','< НАЗАД'],[draw_game(r_) for r_ in w.menu]
w.step(c,p,n=3);press(w,(c,p),6,5);w.step(c,p,n=3);press(w,(c,p),0,5)
assert [draw_game(r_) for r_ in (w.menu[8],w.menu[2])]==['ПОЛИЦИЯ: НЕ СТРЕЛЯТЬ','РЕЖИМ: НАСТУПЛЕНИЕ'] and (w.shared[b.POLICE],w.shared[b.MODE])==(1,1),[draw_game(r_) for r_ in w.menu]
passed('The fire page in Russian: four rules and the two switches (police, missions), every row readable in the simulated font')
w,c,p=open_menu(True,aboard=True)
assert [draw_game(r_) for r_ in rows_of(w)]==['ЛЕТЕТЬ К МЕТКЕ НА КАРТЕ','ЛЕТЕТЬ НА ГРОУВ-СТРИТ','КНОПКА ВЫХОДА: ПОСАДКА [X]','КНОПКА ВЫХОДА: ВЕРЕВКА','РЕЖИМ И ОГОНЬ >','НАСТРОЙКИ >'],[draw_game(r_) for r_ in rows_of(w)]
w.calls.clear();w.messages.clear();press(w,(c,p),3)
assert w.shared[b.EXIT_MODE]==1 and draw_game(rows_of(w)[3])=='КНОПКА ВЫХОДА: ВЕРЕВКА [X]' and not orders_given(w) and w.incar.get(1)==c.v[5] and 'HCXBR' in w.messages,(w.menu,orders_given(w),w.messages)
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
assert all(len([f_ for f_ in b.p.data[l_][4:].split(b'\0')[2:] if f_])==4 for l_ in b.p.data if l_.startswith('SETUP_')),'settings (2.0): helicopter model, messages, missions, BACK - the crews, the gunners\' pose and the tactics are fixed / the brain\'s'
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
 w,c,p=open_menu();w.shared[b.STATE]=st;w.step(p,n=4);assert rows_of(w)==[row,b'MODE AND FIRE >',b'SETTINGS >'],(st,w.menu)
 w.calls.clear()
 for _ in range(3):press(w,(p,),0,3)
 assert not orders_given(w) and rows_of(w)[0]==row,(st,orders_given(w))
passed('While the helicopter is being prepared, swapped or is leaving the first row says so ("HELICOPTER INBOUND...", "CHANGING, PLEASE WAIT...", "HELICOPTER LEAVING...") and orders nothing')
def squad_menu(russian=False):
 w,c,p=setup(True);w.russian=russian;w.game_lang=5 if russian else 0;summon(w,c);ground=VM('Helicover_Ground',w);sq=VM('Helicover_Squad',w);launch=VM('Helicover',w)
 V=(c,p,ground,sq);w.step(*V,launch,n=15);return w,c,p,V
def hover(w,c):w.car=[c.v[26],c.v[27],c.v[28]+18.];w.speed=0.
w,c,p,V=squad_menu()
w.calls.clear();w.messages.clear();press(w,V,0);press(w,V,0);assert not orders_given(w) or set(orders_given(w))=={2} and w.shared[b.STATE]==2,'FOLLOW ME [X] pressed again changes nothing'
assert 'HCFOLL' not in w.messages,'and the pilot does not repeat himself'
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
assert w.shared[b.STATE]==4 and w.menu[0]==b'HELICOVER / DEPARTING' and rows_of(w)==[b'HELICOPTER LEAVING...',b'MODE AND FIRE >',b'SETTINGS >'],(w.shared[b.STATE],w.menu)
w.calls.clear()
for _ in range(3):press(w,(c,p),0,3)
assert not orders_given(w) and w.shared[b.STATE]==4
passed('DISMISS: the page becomes "HELICOPTER LEAVING..." and nothing can be ordered until it is gone')

# =================================================================== taps that must not count (beta 4)
w,c,p=open_menu();press(w,(c,p),6,5);assert w.menu[0]==b'HELICOVER / SETTINGS'
w.events.append(0);w.step(c,p);w.events.append(0);w.step(c,p,n=5)   # a double tap on "HELICOPTER MODEL >"
assert w.menu[0]==b'HELICOVER / HELICOPTER' and w.shared[b.MODEL]==487,(w.menu,w.shared[b.MODEL])
w,c,p=open_menu();w.events.append(3);w.step(c,p);w.events.append(3);w.step(c,p,n=5)   # a double tap on "GUNNER FIRE >"
assert w.menu[0]==b'HELICOVER / MODE AND FIRE' and w.shared[b.FIRE]==3,(w.menu,w.shared[b.FIRE])
w.step(c,p,n=2);press(w,(c,p),3,5);assert w.shared[b.FIRE]==0,'a deliberate tap half a second later is taken (the fourth row: HOLD FIRE)'
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

# models for the HELICOPTER page are requested while the page is open and released after
w,c,p=open_menu();w.calls.clear();press(w,(c,p),6,4);press(w,(c,p),0,4)
assert w.menu[0]==b'HELICOVER / HELICOPTER' and {x[2][0] for x in calls(w,0x247)}=={487,497,425},'the helicopter models when the HELICOPTER page opens'
w.calls.clear();press(w,(c,p),3,4);press(w,(c,p),3,4);assert w.menu[0]==b'HELICOVER / FOLLOWING' and {x[2][0] for x in calls(w,0x249)}>={487,497,425},('and released when the pages are left',w.menu)
passed('The helicopter models are pre-requested while their page is open, so choosing one does not stall a frame')

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

# =================================================================== beta 6: notifications are a line of script text, drawn at once
mv=b._mv
def banner_world(russian=False):
 w,c,p=setup(True);w.russian=russian;w.game_lang=5 if russian else 0;f_=VM('Helicover_Fire',w);V_=(c,p,f_);w.step(*V_,n=3);return w,c,p,f_,V_
def drawn(w):return [x[2][2] for x in calls(w,0x33e)]
def say_now(w,key,prio=None,ms=3000):
 """What say() leaves behind (the scripts' own say() is exercised by every other test)."""
 w.shared[b.MSG_ID]=mv.KEYS.index(key);w.shared[b.MSG_UNTIL]=w.now+ms;w.shared[b.MSG_HOLD]=w.now+mv.MIN_SHOW_MS;w.shared[b.MSG_PRIO]=mv.PRIO.get(key,2) if prio is None else prio
for frame_ms in (100,33,16):
 w,c,p,f_,V_=banner_world();w.frame_ms=frame_ms;w.step(*V_,n=5);w.calls.clear();w.shared[b.CMD]=1
 n=frames_until(w,V_,lambda w:drawn(w));assert n is not None and n<=3 and set(drawn(w))<={'HCLOAD','HCFOLL'},(frame_ms,n,drawn(w))
passed('CALL HELICOPTER: the pilot\'s answer is on the screen within 3 frames of the order at 10, 30 and 60 fps (the help box needed 0.3-1.1 s when free and queued 5.65 s per message when not)')
w,c,p,f_,V_=banner_world();w.calls.clear();say_now(w,'HCFOLL',ms=1000);w.step(*V_);assert not drawn(w) and [x[2] for x in calls(w,0x3f0)]==[[1]],'the first frame only switches the per-frame wiping on'
frames=[]
for _ in range(14):w.calls.clear();w.step(*V_);frames.append(drawn(w))
assert frames[:8]==[['HCFOLL']]*8 and frames[8:]==[[]]*6,frames   # 1000 ms at 100 ms frames: armed at +100, drawn +200..+900, gone at +1000
w.calls.clear();say_now(w,'HCFOLL');w.step(*V_,n=2);k=w.calls
order=[x[1] for x in k if x[1] in (0x3f0,0x33f,0x340,0x342,0x344,0x81c,0x33e)][-7:];assert order==[0x3f0,0x33f,0x340,0x342,0x344,0x81c,0x33e],[hex(o) for o in order]
line=calls(w,0x33e)[-1][2];near=lambda a_,b_:abs(a_-b_)<1e-4;assert near(line[0],mv.BANNER_X) and near(line[1],mv.BANNER_Y) and near(calls(w,0x33f)[-1][2][1],mv.BANNER_HEIGHT) and calls(w,0x342)[-1][2]==[1] and near(calls(w,0x344)[-1][2][0],mv.BANNER_CENTRE_SIZE)
passed('The line is drawn every frame while the message lasts (exactly its time, to the frame) and never after: wipe on, size, colour, centred, line width, outline, text - one line of text per frame')
w,c,p,f_,V_=banner_world();say_now(w,'HCFOLL');w.step(*V_,n=3);w.calls.clear();say_now(w,'HCBURN');w.step(*V_);assert drawn(w)==['HCBURN'],'a new message is on the screen in the very next frame, in place of the old one'
passed('A new message replaces the one on screen in the next frame: never two at once, no queue')
w,c,p,f_,V_=banner_world(True);say_now(w,'HCBURN');w.step(*V_,n=3);assert set(drawn(w))=={'UCBURN'}
assert draw_game(fxt['UCBURN'])==i18n.RU_MESSAGES['HCBURN'].replace('ё','е'),draw_game(fxt['UCBURN'])
passed('In the game\'s Russian the line shows the U key of the same message ("%s")'%i18n.visible(i18n.RU_MESSAGES['HCBURN']))
assert len(mv.KEYS)==len(en_keys) and set(mv.KEYS)==set(en_keys),'every message can be drawn'
w,c,p,f_,V_=banner_world()
for i_,k_ in enumerate(mv.KEYS):
 for russian in (False,True):
  w.shared[b.LANG]=int(russian);w.calls.clear();say_now(w,k_);w.step(f_,n=2);assert set(drawn(w))=={i18n.ukey(k_) if russian else k_},(k_,russian,drawn(w))
passed('Each of the %d messages is drawn with its own text in both languages (two-level dispatch by number)'%len(mv.KEYS))
# who may take the line from whom
shown={}
import asm_v25 as asm,tempfile
PROBE_DIR=Path(tempfile.mkdtemp(prefix='hc_probe_'))
def probe_vm(name,w):
 keep=b.OUT;b.OUT=PROBE_DIR
 try:return VM(name,w)
 finally:b.OUT=keep
PROBE={4:'HCBUSY',3:'HCBURN',2:'HCCLEAR',1:'SQCAR',5:'HCFOLL'}   # an answer to a refused order, an alarm, a routine call, chatter; 5 = the acknowledgement of an order
assert [mv.PRIO[PROBE[k_]] for k_ in (4,3,2,1,5)]==[4,3,2,1,2] and PROBE[5] in mv.ORDER_ACK and PROBE[2] not in mv.ORDER_ACK
for new in PROBE:
 sc=asm.Script();a_=sc.add;a_(0);mv.say(sc,PROBE[new]);sc.label('END');a_(1,asm.I(100000));sc.go('END');_keep=asm.OUT;asm.OUT=PROBE_DIR;sc.build('SayProbe%d'%new,'csa');asm.OUT=_keep   # scratch scripts, built outside build/ so that nothing can ship them
def probe(new,on_screen=0,age=0,hud=2):
 w=World();w.shared[b.HUD]=hud;w.now=50000;w.shared[b.MSG_PRIO]=on_screen;w.shared[b.MSG_UNTIL]=w.now+(3000 if on_screen else -1);w.shared[b.MSG_HOLD]=w.now+mv.MIN_SHOW_MS-age;w.step(probe_vm('SayProbe%d'%new,w));return w
for on_screen in (4,3,2,1):
 for age in (0,mv.MIN_SHOW_MS+100):
  for new in (4,3,2,1):
   got=bool(probe(new,on_screen,age).messages);want=new==4 or new>=on_screen or (age>0 and on_screen-new==1);assert got==want,(on_screen,age,new,got)
passed('Who takes the line: an answer to a refused order always; an equally or more important call at once; a call one level lower only after the line has been readable for %.1f s; anything lower waits for it to end'%(mv.MIN_SHOW_MS/1000.))
for on_screen in (4,3,2,1):assert probe(5,on_screen).messages==['HCFOLL'],on_screen
w=probe(5,4);assert w.shared[b.MSG_PRIO]==3 and probe(3,3,0).messages and not probe(2,3,0).messages and probe(2,3,mv.MIN_SHOW_MS+100).messages
assert not probe(5,hud=0).messages and probe(5,hud=1).messages and probe(4,hud=0).messages and not probe(1,hud=1).messages and not probe(3,hud=0).messages
passed('The acknowledgement of an order ("PILOT: following you") takes the line at once whatever is on it; an alarm may replace it at once, a routine call after %.1f s. MESSAGES: OFF still silences it (not the answers to refused orders), IMPORTANT drops only chatter'%(mv.MIN_SHOW_MS/1000.))
w=probe(3);assert w.shared[b.MSG_UNTIL]==w.now+mv.SHOW_MS[3] and w.shared[b.MSG_HOLD]==w.now+mv.MIN_SHOW_MS and w.shared[b.MSG_PRIO]==3 and w.shared[b.MSG_ID]==mv.KEYS.index('HCBURN')
for name in ('Helicover_Core','Helicover_Fire','Helicover_Ground','Helicover_Squad','Helicover_Panel'):
 import check_wait_loops as cw
 ins,order=cw.parse(name);assert not [a_ for a_ in order if (ins[a_][0]&0x7fff)==0x3e5],name
passed('No script but the launcher ("files missing") uses the help box any more')

# =================================================================== beta 6: our people do not cower
w,c,p=open_menu();dm=[x[2] for x in calls(w,0x60b)];crew=[c.v[4]]+[c.v[v] for v in (13,14,15,16)]
assert sorted(x[0] for x in dm)==sorted(crew) and all(x[1]==b.EMPTY_DM for x in dm),dm
w,c,p,V=squad_menu();w.calls.clear();press(w,V,5);hover(w,c);w.step(*V,n=40);team=[w.shared[b.GROUND_PUB+i] for i in range(4)]
assert all(t in w.exists for t in team) and sorted(x[2][0] for x in calls(w,0x60b))==sorted(team),(team,[x[2] for x in calls(w,0x60b)])
before=set(w.exists);w.calls.clear();w.shared[b.CREW]=(w.shared[b.CREW]+1)%3;w.step(*V,n=40);fresh={x[2][0] for x in calls(w,0x60b)};made={x[5] if False else x for x in set(w.exists)-before}
assert len(made)>=5 and made<=fresh and all(x[2][1]==b.EMPTY_DM for x in calls(w,0x60b)) and all(t in w.exists for t in team),('everybody created for the change of the helicopter crew - pilot, four gunners - gets it again (1.4.1: the ground team is not re-dressed)',sorted(made),sorted(fresh))
w2,c2,p2=setup(True);w2.empty_dm=False;summon(w2,c2);assert not calls(w2,0x60b),'no such decision maker in this game build: nothing is set (they behave as before)'
for name in ('Helicover_Core','Helicover_Ground','Helicover_Squad','Helicover_Fire'):
 ins,order=cw.parse(name);assert not [a_ for a_ in order if (ins[a_][0]&0x7fff)==0x5c5],name
passed('Pilot, gunners and every squad member (also after a change of clothes) get the game\'s empty decision maker: punched or shot at they keep their task instead of ducking with their hands over their heads; TASK_DUCK (the scared pose) is not used anywhere')

# =================================================================== 1.4: door gunners sit on the skids (beta 6: kneel)
def pose_calls(w,c):return {c.v[v]:[x[2][1] for x in calls(w,0x4eb) if x[2][0]==c.v[v]] for v in (13,14,15,16)}
def seats(w,c):return {x[2][0]:x[2][2:5] for x in calls(w,0x464) if x[2][0] in [c.v[v] for v in (13,14,15,16)]}
w,c,p=open_menu();pc=pose_calls(w,c);assert all(v and v[-1]==1 for v in pc.values()),pc
att={x[2][0]:x[0] for x in calls(w,0x464)};assert all([x[0] for x in calls(w,0x4eb) if x[2]==[g_,1]][-1]>=att[g_] for g_ in att),'the crouch is asked for after the attach'
sit=seats(w,c);assert all(abs(o[2]-(-.1-b.SEAT_DROP))<.01 and abs(abs(o[0])-(1.4+b.SEAT_OUT))<.01 for o in sit.values()),sit
passed('Door gunners sit on the skids by default (mounted %.2f m lower and %.2f m further out than kneeling, crouched right after they are mounted)'%(b.SEAT_DROP,b.SEAT_OUT))
press(w,(c,p),6,4);assert not [r_ for r_ in rows_of(w) if b'GUNNERS' in r_],'no pose setting: the brain seats the gunners'
w.calls.clear();w.shared[b.POSE]=1;w.step(c,p,n=6)                       # the brain: kneel at the door over a fight
assert w.shared[b.POSE_DONE]==1 and len(calls(w,0x464))==4 and all(v and v[-1]==1 for v in pose_calls(w,c).values()),pose_calls(w,c)
assert all(abs(o[2]+.1)<.01 and abs(abs(o[0])-1.4)<.01 for o in seats(w,c).values()),seats(w,c)
assert all(w.weapons[c.v[v]]!=0 for v in (13,14,15,16)),'re-mounting strips the weapons: they are handed back at once'
w.calls.clear();w.step(c,p,n=20);assert not calls(w,0x464),'the crew is re-mounted once per change, not every pass'
passed('The gunners\' pose is the brain\'s (no setting): when it changes they are re-seated once at once (seated on the skid -> kneeling at the door), weapons back in their hands')
w,c,f=g['fire_world']();npc=g['target'](w);w.damage.add((1,npc));w.step(c,f,n=14);w.calls.clear();w.exists.discard(npc);w.step(c,f,n=20)
gun=[c.v[v] for v in (13,14,15,16)];assert calls(w,0x687) and all([x[0] for x in calls(w,0x4eb) if x[2]==[g_,1]] for g_ in gun if g_ in w.attach),(len(calls(w,0x687)),[x[2] for x in calls(w,0x4eb)])
passed('After a fight the gunners go back to one knee (clearing their fire task would leave them standing)')

text='\n'.join(results)+'\nMocked script execution only: the Russian layout was confirmed on the player\'s phone (beta 3); the look of the menu itself is the game\'s.\n'
(b.OUT/'i18n_tests.txt').write_text(text);print(text)
