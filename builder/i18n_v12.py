"""Helicover 1.2 language data: every Russian text, and how a Cyrillic letter reaches the game's font.

The game draws help-box messages (FXT keys) and CLEO menu rows with CFont::PrintString; a text byte becomes a 16-bit code as it is.
What the font shows for a code depends on the language the GAME is set to (libGTASA 2.00 arm64 + the player's screenshots of the
first beta's FONT TEST):

  English / other  the standard font texture has no Cyrillic at all (codes above its last glyph are blanked) -> English only.
  Russian          CFont::UsingRussianLanguage: every font style goes through one atlas (RussianFont.met); the glyph is entry
                   "code - 0x20" and every code past the end of the atlas is drawn as '@'. On screen: 181 = kha, 182 = tse,
                   192 = an ellipsis, 193-195 = shield / star / heart, 196+ = '@'. So the letters run in alphabet order,
                   A-YA = 0x80-0x9F, a-ya = 0xA0-0xBF (Unicode - 0x390), with no IO.                         -> profile 'game'
  SanLTD           a fan localisation in the French slot (CFont::UsingEFIGSLanguage, language index 1): the ordinary font with
                   SanLTD's texture. Letters that look Latin use the Latin glyph, the rest sit at 0x80-0x95 (22 of 22 confirmed
                   on the player's screenshot). The codes of a few lower-case letters are not confirmed, so this profile
                   writes everything in CAPITALS.                                                            -> profile 'sanltd'

The first beta shipped CP1251 and "russian_table" layouts; both were wrong (that table only serves the keyboard key names).
"""
import re
ALPHABET='АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'   # 32 letters, no IO: the official atlas has none
# SanLTD: capital letter -> byte. Latin look-alikes first, then the Cyrillic glyphs of the texture.
SANLTD={'А':0x41,'В':0x42,'Е':0x45,'Ё':0x45,'К':0x4B,'М':0x4D,'Н':0x48,'О':0x4F,'Р':0x50,'С':0x43,'Т':0x54,'У':0x59,'Х':0x58,
 'Б':0x80,'Ф':0x81,'Г':0x82,'Д':0x83,'Ж':0x84,'И':0x85,'Й':0x86,'Л':0x87,'З':0x88,'Ц':0x89,'Щ':0x8A,'П':0x8C,'Ч':0x8D,'Ш':0x8E,
 'Ъ':0x90,'Ы':0x91,'Ь':0x92,'Э':0x93,'Ю':0x94,'Я':0x95}
PROFILES=('en','game','sanltd')
def upper_keep_tags(text):
 """Capitals everywhere except inside the ~x~ colour / number tags (they are commands for the game, case matters)."""
 return ''.join(part if re.fullmatch(r'~[^~]~',part) else part.upper() for part in re.split(r'(~[^~]~)',text))
def encode(text,profile):
 """Text -> bytes for a profile. Latin text, digits and punctuation stay ASCII; Cyrillic goes to the codes of that font."""
 if profile=='en':return text.encode('ascii')
 if profile=='sanltd':text=upper_keep_tags(text)
 out=bytearray()
 for ch in text:
  if ord(ch)<128:out.append(ord(ch));continue
  if profile=='game':
   ch={'Ё':'Е','ё':'е'}.get(ch,ch);i=ALPHABET.find(ch.upper())
   assert i>=0,('no glyph for',ch)
   out.append((0x80 if ch.isupper() else 0xA0)+i)
  else:
   assert ch in SANLTD,('no SanLTD glyph for',ch)
   out.append(SANLTD[ch])
 return bytes(out)
def ukey(key):return 'U'+key[1:]
def vkey(key):return 'V'+key[1:]
def key_for(key,lang):return (key,ukey(key),vkey(key))[lang]

# ----------------------------------------------------------------------------------------------- on-screen messages
# key -> Russian text (standard game Russian: no slang, no quotes, no yo). Colour tags and ~1~ stay as they are.
RU_MESSAGES={
 'HCLOAD':'~b~ПИЛОТ:~w~ лечу к вам.',
 'HCFOLL':'~b~ПИЛОТ:~w~ лечу за вами.',
 'HCHOLD':'~b~ПИЛОТ:~w~ зависаю на месте.',
 'HCDEPT':'~b~ПИЛОТ:~w~ возвращаюсь на базу. Вызывайте в любой момент.',
 'HCFAIL':'~r~HELICOVER:~w~ не удалось загрузить вертолет. Повторите.',
 'HCOUT':'~y~HELICOVER:~w~ выйдите на улицу, чтобы вызвать вертолет.',
 'HCRWAIT':'~y~ПИЛОТ:~w~ здесь не зависнуть. Выйдите на открытое место.',
 'HCGCLMB':'~y~ПИЛОТ:~w~ здесь вас не поднять. Выйдите на открытое место.',
 'HCMAPOF':'~y~HELICOVER:~w~ полет к метке на карте недоступен.',
 'HCDBG':'DBG ~1~',
 'HCNEED':'~y~HELICOVER:~w~ сначала вызовите вертолет.',
 'HCVER':'~y~HELICOVER:~w~ метка на карте не работает в этой версии игры.',
 'HCNOMAP':'~y~HELICOVER:~w~ сначала поставьте метку на карте.',
 'HCCHOS':'~b~ПИЛОТ:~w~ прибыли. Нажмите выход, чтобы покинуть вертолет.',
 'HCAIR':'~r~ПОЛИЦЕЙСКИЙ ВЕРТОЛЕТ!~w~ Стрелки отвечают огнем.',
 'HCCONT':'~r~КОНТАКТ!~w~ Стрелки открыли огонь.',
 'HCKILL':'~g~ЦЕЛЬ УНИЧТОЖЕНА~w~ ~1~',
 'HCCLEAR':'~g~СТРЕЛКИ:~w~ чисто.',
 'HCFM0':'~y~СТРЕЛКИ:~w~ прекратить огонь.',
 'HCFM1':'~r~СТРЕЛКИ:~w~ огонь по всем, кроме своих.',
 'HCFM2':'~b~СТРЕЛКИ:~w~ стреляем туда, куда стреляете вы.',
 'HCFM3':'~g~СТРЕЛКИ:~w~ защищаем CJ.',
 'HCFM4':'~p~СТРЕЛКИ:~w~ прикрытие - только вооруженные враги.',
 'HCXROPE':'~b~ПИЛОТ:~w~ сесть негде - спускаю вас по веревке.',
 'HCNOPAD':'~b~ПИЛОТ:~w~ ровной площадки нет - зависаю для спуска.',
 'HCXHERE':'~b~ПИЛОТ:~w~ ищу место, чтобы вас высадить.',
 'HCXARR':'~b~ПИЛОТ:~w~ высадка по прибытии.',
 'HCXWAIT':'~y~ПИЛОТ:~w~ подождите, пока сядем или зависнем.',
 'HCDWAIT':'~y~ПИЛОТ:~w~ подождите, пока долетим.',
 'HCPAT':'~b~ПИЛОТ:~w~ патрулирую вокруг вас.',
 'HCAVOID':'~y~ПИЛОТ:~w~ путь закрыт - жду, пока освободится.',
 'HCROPE':'~b~ПИЛОТ:~w~ подлетаю - идите к веревке.',
 'HCRTEAM':'~b~ПИЛОТ:~w~ подлетаю, чтобы высадить отряд.',
 'HCRBACK':'~b~ПИЛОТ:~w~ подлетаю, чтобы забрать отряд.',
 'HCEVAC':'~b~ПИЛОТ:~w~ сажусь рядом.',
 'HCTEAM':'~g~ОТРЯД:~w~ охраняем вертолет. Садитесь, когда будете готовы.',
 'HCBOARD':'~b~ПИЛОТ:~w~ CJ на борту. Откройте меню и выберите маршрут.',
 'HCGROVE':'~b~ПИЛОТ:~w~ летим на Гроув-стрит.',
 'HCHOME':'~b~ПИЛОТ:~w~ подлетаем к Гроув-стрит.',
 'HCARRIV':'~b~ПИЛОТ:~w~ сели. Нажмите выход.',
 'HCDAMAG':'~r~МЭЙДЭЙ!~w~ Критические повреждения - ухожу.',
 'HCMUST':'~b~ПИЛОТ:~w~ жду, пока экипаж вернется на борт.',
 'HCEMERG':'~r~МЭЙДЭЙ!~w~ Критические повреждения - аварийная посадка.',
 'HCNOSEA':'~y~HELICOVER:~w~ на Hunter нет пассажирского места.',
 'HCNOSIT':'~y~ПИЛОТ:~w~ здесь не сесть. Найдите открытое ровное место.',
 'HCFAR':'~y~ПИЛОТ:~w~ подойдите к вертолету ближе чем на 12 м.',
 'HCWAIT':'~y~ПИЛОТ:~w~ жду экипаж. Освободите ему дорогу.',
 'HCIN':'~y~HELICOVER:~w~ сначала сядьте в вертолет.',
 'HCOFF':'~r~HELICOVER:~w~ не хватает файлов. Скопируйте все в CLEO и перезапустите игру.',
 'HCSWAP':'~b~ПИЛОТ:~w~ вертолет заменен.',
 'HCSNO':'~y~HELICOVER:~w~ на Hunter нет пассажирского места - сначала выйдите.',
 'HCSFAIL':'~r~HELICOVER:~w~ замена не удалась, оставлен прежний вертолет.',
 'HCCREW':'~g~HELICOVER:~w~ экипаж заменен.',
 'HCCFAIL':'~r~HELICOVER:~w~ замена экипажа не удалась, оставлен прежний.',
 'HCBLOCK':'~y~ПИЛОТ:~w~ здесь не сесть. Выберите открытое место или ЛЕТЕТЬ ЗА МНОЙ.',
 'HCLOSE':'~y~ПИЛОТ:~w~ сначала посадите вертолет.',
 'HCEXIT':'~y~HELICOVER:~w~ сначала выйдите из вертолета.',
 'SQALR':'~y~ОТРЯД:~w~ отряд уже на земле.',
 'SQNONE':'~y~ОТРЯД:~w~ на земле нет отряда.',
 'SQFOOT':'~y~ОТРЯД:~w~ чтобы высадить отряд, CJ должен быть пешком.',
 'SQCREW':'~y~ОТРЯД:~w~ подождите, пока экипаж вернется на борт.',
 'HCBUSY':'~y~ПИЛОТ:~w~ аварийная посадка - не могу выполнить.',
 'HCSLATE':'~y~ПИЛОТ:~w~ сделаю замену сразу после подъема по веревке.',
 'HCFOCUS':'~r~СТРЕЛОК ПО CJ!~w~ Стрелки бьют по нему.',
 'HCEVADE':'~r~ПОПАДАНИЯ!~w~ Пилот уходит от огня.',
 'HCSHOT':'~r~ОБСТРЕЛ!~w~ Пилот уходит от огня.',
 'HCHELLO':'~b~HELICOVER 1.2 БЕТА~w~ готов. Меню CLEO > Helicover.',
 'HCHELLV':'~b~HELICOVER 1.2 БЕТА~w~ готов. Метка на карте отключена.',
 'RGDEP':'~b~ПИЛОТ:~w~ отряд спускается по веревкам.',
 'RGDONE':'~g~ОТРЯД:~w~ отряд на борту.',
 'RGFAIL':'~r~HELICOVER:~w~ не удалось загрузить отряд.',
 'RGHOLD':'~y~ПИЛОТ:~w~ сначала нужно устойчиво зависнуть.',
 'RGHIGH':'~y~ПИЛОТ:~w~ неподходящая высота для веревок. Найдите открытое место.',
 'RGMOVE':'~y~ПИЛОТ:~w~ подождите, пока стабилизируемся.',
 'RGBLOCK':'~y~ПИЛОТ:~w~ нет свободной площадки. Найдите открытое место.',
 'RGUP':'~b~ПИЛОТ:~w~ поднимаю вас.',
 'RGABO':'~b~ПИЛОТ:~w~ CJ на борту. Отряд поднимается.',
 'RGSEAT':'~y~ПИЛОТ:~w~ нет свободного места.',
 'RGANIM':'~y~HELICOVER:~w~ анимация веревки недоступна.',
 'RPDFAIL':'~y~ПИЛОТ:~w~ здесь не спустить веревку. Выберите другое место.',
 'SQIN':'~g~ОТРЯД:~w~ на земле. Сопровождаем CJ.',
 'SQBACK':'~g~ОТРЯД:~w~ отряд на борту.',
 'SQLOST':'~r~ОТРЯД ПОТЕРЯН!~w~ Группа сопровождения погибла.',
 'SQCOVER':'~g~ОТРЯД:~w~ прикрываем вашу эвакуацию.',
 'SQAWAY':'~g~ОТРЯД:~w~ потеряли вас. Отряд отозван.',
 'SQSTAY':'~g~ОТРЯД:~w~ остаемся на земле.',
 'RGLATE':'~y~ПИЛОТ:~w~ вы не пришли. Поднимаю веревки.',
 'SQCLR':'~g~ОТРЯД:~w~ зона зачищена, собираемся у CJ.',
 'SQDOWN':'~r~БОЕЦ ПОГИБ!~w~ Потеряли одного.',
 'SQCOV':'~r~CJ РАНЕН!~w~ Прикрываем.',
 'SQMED':'~g~МЕДИК:~w~ CJ перевязан.',
 'SQMEDG':'~g~МЕДИК:~w~ боец перевязан.',
 'SQCAR':'~g~ОТРЯД:~w~ садимся в машину.',
 'SQRLD':'~g~ОТРЯД:~w~ перезарядка!',
 'SQCVR':'~g~ОТРЯД:~w~ уходим в укрытие.',
 'SQEVAC':'~r~СЛИШКОМ ЖАРКО!~w~ CJ ранен - вызывайте подъем по веревке.',
}
_DIRS={'F':'СПЕРЕДИ','L':'СЛЕВА','B':'СЗАДИ','R':'СПРАВА'}
for _d,_ru in _DIRS.items():
 RU_MESSAGES['SQX'+_d]='~r~ОГОНЬ ПО CJ - %s!~w~ Прикрываем.'%_ru
 RU_MESSAGES['SQS'+_d]='~r~СНАЙПЕР - %s!~w~ CJ в укрытие.'%_ru
 RU_MESSAGES['SQV'+_d]='~r~МАШИНА - %s!~w~ Бьем по водителю.'%_ru
 RU_MESSAGES['SQR'+_d]='~r~КРЫША - %s!~w~ Стрелок наверху.'%_ru
 RU_MESSAGES['SQC'+_d]='~r~КОНТАКТ %s!~w~ Отряд стреляет.'%_ru
 RU_MESSAGES['SQA'+_d]='~r~КОНТАКТ %s!~w~ Штурм - идем вперед.'%_ru
RU_PLAIN_LIMIT=80   # visible characters in a help-box message

def visible(text):return re.sub(r'~.~','',text)
def check_keys():
 """Every key must stay unique and at most 7 characters after the U / V rewrite."""
 seen={}
 for k in RU_MESSAGES:
  for lang in (0,1,2):
   kk=key_for(k,lang)
   assert len(kk)<=7 and re.fullmatch(r'[A-Z0-9]+',kk),kk
   assert kk not in seen,(kk,k,seen.get(kk));seen[kk]=k
 return seen


# ----------------------------------------------------------------------------------------------- menu
# id -> (English, Russian). Rows stay short (the CLEO menu panel is narrow): at most 26 characters in English, 28 in Russian.
MENU={
 'CALL':('CALL HELICOPTER','ПОЗВАТЬ ВЕРТОЛЕТ'),
 'WAIT':('PLEASE WAIT...','ПОДОЖДИТЕ...'),
 'SETTINGS':('SETTINGS >','НАСТРОЙКИ (SETTINGS) >'),   # beta: the Latin word keeps the way to LANGUAGE readable if the Cyrillic layout is wrong
 'GUNFIRE':('GUNNER FIRE >','ОГОНЬ СТРЕЛКОВ >'),
 'FOLLOW':('FOLLOW ME','ЛЕТЕТЬ ЗА МНОЙ'),
 'HOLD':('HOLD HERE','ЖДАТЬ ЗДЕСЬ'),
 'PATROL':('PATROL AROUND ME','ПАТРУЛЬ ВОКРУГ'),
 'ROPE':('CLIMB ABOARD BY ROPE','НА БОРТ ПО ВЕРЕВКЕ'),
 'TEAM_ON':('DEPLOY SQUAD','ВЫСАДИТЬ ОТРЯД'),
 'TEAM_OFF':('RECALL SQUAD','ЗАБРАТЬ ОТРЯД'),
 'DISMISS':('DISMISS HELICOPTER','ОТПУСТИТЬ ВЕРТОЛЕТ'),
 'MAP':('FLY TO MAP MARKER','ЛЕТЕТЬ К МЕТКЕ НА КАРТЕ'),
 'GROVE':('FLY TO GROVE STREET','ЛЕТЕТЬ НА ГРОУВ-СТРИТ'),
 'EXIT_LAND':('EXIT: LAND','ВЫСАДКА: ПОСАДКА'),
 'EXIT_ROPE':('EXIT: ROPE','ВЫСАДКА: ВЕРЕВКА'),
 'BACK':('< BACK','< НАЗАД'),
 'SET_TITLE':('HELICOVER / SETTINGS','HELICOVER / НАСТРОЙКИ'),
 'SET_CREW':('CREW >','ЭКИПАЖ >'),
 'SET_MODEL':('HELICOPTER MODEL >','МОДЕЛЬ ВЕРТОЛЕТА >'),
 'SET_WEAPON':('CREW WEAPON >','ОРУЖИЕ ЭКИПАЖА >'),
 'TAC_GUARD':('SQUAD TACTICS: GUARD','ТАКТИКА: ОХРАНА'),
 'TAC_ASSAULT':('SQUAD TACTICS: ASSAULT','ТАКТИКА: ШТУРМ'),
 'EXB_LAND':('EXIT BUTTON: LAND','КНОПКА ВЫХОДА: ПОСАДКА'),
 'EXB_ROPE':('EXIT BUTTON: ROPE','КНОПКА ВЫХОДА: ВЕРЕВКА'),
 'MSG_OFF':('MESSAGES: OFF','СООБЩЕНИЯ: ВЫКЛ'),
 'MSG_IMP':('MESSAGES: IMPORTANT','СООБЩЕНИЯ: ВАЖНЫЕ'),
 'MSG_ALL':('MESSAGES: ALL','СООБЩЕНИЯ: ВСЕ'),
 'LANGUAGE':('LANGUAGE >','LANGUAGE >'),
 'FIRE_TITLE':('HELICOVER / GUNNER FIRE','HELICOVER / ОГОНЬ СТРЕЛКОВ'),
 'FIRE3':('PROTECT ME','ЗАЩИЩАТЬ МЕНЯ'),
 'FIRE4':('ARMED ONLY','ТОЛЬКО ВООРУЖЕННЫЕ'),
 'FIRE2':('WHERE I SHOOT','ТАМ, ГДЕ СТРЕЛЯЮ Я'),
 'FIRE1':('FIRE AT ALL','ОГОНЬ ПО ВСЕМ'),
 'FIRE0':('HOLD FIRE','НЕ СТРЕЛЯТЬ'),
 'CREW_TITLE':('HELICOVER / CREW','HELICOVER / ЭКИПАЖ'),
 'CREW0':('GROVE STREET','ГРОУВ-СТРИТ'),
 'CREW1':('ARMY','АРМИЯ'),
 'CREW2':('SWAT','СПЕЦНАЗ'),
 'MODEL_TITLE':('HELICOVER / HELICOPTER','HELICOVER / МОДЕЛЬ'),
 'MODEL487':('MAVERICK','MAVERICK'),
 'MODEL497':('POLICE MAVERICK','ПОЛИЦЕЙСКИЙ MAVERICK'),
 'MODEL425':('HUNTER (NO PASSENGERS)','HUNTER (БЕЗ ПАССАЖИРОВ)'),
 'WEAPON_TITLE':('HELICOVER / CREW WEAPON','HELICOVER / ОРУЖИЕ ЭКИПАЖА'),
 'WEAPON0':('AUTO (BY CREW)','АВТО (ПО ЭКИПАЖУ)'),
 'WEAPON29':('MP5','MP5'),
 'WEAPON30':('AK-47','AK-47'),
 'WEAPON31':('M4','M4'),
 'WEAPON34':('SNIPER RIFLE','СНАЙПЕРСКАЯ ВИНТОВКА'),
 'DISMISS_TITLE':('SEND THE HELICOPTER AWAY?','ОТПУСТИТЬ ВЕРТОЛЕТ?'),
 'DISMISS_YES':('YES, DISMISS IT','ДА, ОТПУСТИТЬ'),
 'DISMISS_YES_TEAM':('YES, RECALL SQUAD FIRST','ДА, СНАЧАЛА ЗАБРАТЬ ОТРЯД'),
 'DISMISS_NO':('NO, KEEP IT','НЕТ, ОСТАВИТЬ'),
 'OFFLINE_TITLE':('HELICOVER / OFFLINE','HELICOVER / НЕТ ФАЙЛОВ'),
 'OFFLINE_ROW':('COPY ALL FILES, RESTART GAME','СКОПИРУЙТЕ ВСЕ ФАЙЛЫ, ПЕРЕЗАПУСТИТЕ'),
 'TITLE_READY':('HELICOVER 1.2 BETA','HELICOVER 1.2 БЕТА'),
}
# menu title tail for every helicopter state (English names are in build_v25.STATES)
STATE_RU={0:'ГОТОВ',1:'ЗАГРУЗКА',2:'ЛЕТИТ ЗА ВАМИ',3:'ЖДЕТ',4:'УЛЕТАЕТ',5:'ОШИБКА ЗАГРУЗКИ',6:'ВЫЙДИТЕ НА УЛИЦУ',7:'ЛЕТИТ НА ПОСАДКУ',
 8:'ОТРЯД ПРИКРЫВАЕТ',9:'CJ НА БОРТУ',10:'ЛЕТИТ НА ГРОУВ-СТРИТ',11:'ПОСАДКА НА ГРОУВ-СТРИТ',12:'НА ЗЕМЛЕ',13:'ПОВРЕЖДЕН - НА БАЗУ',
 14:'ОТРЯД САДИТСЯ',15:'АВАРИЙНАЯ ПОСАДКА',16:'СМЕНА ВЕРТОЛЕТА',17:'СМЕНА ЭКИПАЖА',18:'ПОСАДКА НЕВОЗМОЖНА',19:'ПОДЛЕТАЕТ К ВЕРЕВКЕ',
 20:'НАБОР ВЫСОТЫ',21:'ЛЕТИТ К МЕТКЕ',22:'ЗАХОД НА ЦЕЛЬ',23:'ЖДЕТ ВЫСАДКИ',24:'ПАТРУЛИРУЕТ',25:'НАБОР ВЫСОТЫ'}
MARK=' [X]'
def menu_text(key,profile):
 en,ru=MENU[key];return encode(en if profile=='en' else ru,profile)
def state_title(state,en_name,profile):
 return encode('HELICOVER / '+en_name,'en') if profile=='en' else encode('HELICOVER / '+STATE_RU[state],profile)

# FONT TEST: page 1 is for the game's own Russian (profile 'game'), page 2 for SanLTD. Each shows the alphabet as this build writes it;
# page 2 adds raw codes whose letters are not known yet (the lower-case half of SanLTD), so one screenshot settles them.
ALPHA_UP1='АБВГДЕЖЗИЙКЛМНОП';ALPHA_UP2='РСТУФХЦЧШЩЪЫЬЭЮЯ';ALPHA_LO1='абвгдежзийклмноп';ALPHA_LO2='рстуфхцчшщъыьэюя'
RU_MESSAGES['HFTEST']='~b~ТЕСТ ШРИФТА~w~ '+ALPHA_UP1+' '+ALPHA_LO1
def font_test_rows(profile):
 if profile=='game':return [encode('1: '+s,'game') for s in (ALPHA_UP1,ALPHA_UP2,ALPHA_LO1,ALPHA_LO2)]
 return [encode('2: '+ALPHA_UP1,'sanltd'),encode('2: '+ALPHA_UP2,'sanltd'),b'R: '+bytes(range(0x96,0xA6)),b'R: '+bytes(range(0xA6,0xB0))]
def _groups(lo,hi,n=8):return b' '.join(bytes(range(i,min(i+n,hi))) for i in range(lo,hi,n))
# texts that are not a translation: the SanLTD test message shows the raw codes 0x80-0xAF in the help-box font
FXT_OVERRIDE={('sanltd','HFTEST'):b'~b~TEST~w~ '+_groups(0x80,0xB0)}
def fxt_text(key,profile):
 return FXT_OVERRIDE.get((profile,key)) or encode(RU_MESSAGES[key],profile)
