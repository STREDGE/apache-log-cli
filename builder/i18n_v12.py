"""Helicover 1.2 language data: every Russian text, and the two ways a Cyrillic letter can reach the game's font.

The game draws help-box messages (FXT keys) and CLEO menu rows with CFont::PrintString from single-byte codes. For
Russian the font texture is not laid out like CP1251: libGTASA carries `russian_table` (128 entries, indexed by
CP1251 byte - 0x80) that gives the glyph slot of every Cyrillic letter. Which of the two reaches the screen depends on
where the game applies that table, which cannot be told from the code alone, so the beta ships both and a FONT TEST page:

  RUS-1  plain CP1251 bytes (the engine maps them itself)
  RUS-2  the byte is replaced by russian_table[byte - 0x80] (the text is already in glyph codes)

tools/verify_russian_table.py checks GLYPH_TABLE against a libGTASA.so.
"""
import re
# russian_table of libGTASA (arm64 build 2.00): glyph slot for CP1251 byte 0x80 + index (0 = not a letter)
GLYPH_TABLE=(0,0,0,0,0,133,0,0,0,0,0,0,0,141,142,143,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,32,0,0,0,0,0,0,0,177,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,210,0,0,0,0,0,0,0,
 193,208,192,184,198,182,199,187,205,178,181,197,204,183,196,194,195,203,206,180,190,188,179,202,185,186,189,191,207,200,209,201,
 226,241,225,217,231,215,232,220,238,211,214,230,237,216,229,227,228,236,239,213,223,221,212,235,218,219,222,224,240,233,242,234)
PROFILES=('en','cp1251','glyph')
def encode(text,profile):
 """Text -> bytes for a profile. Latin text, digits and punctuation stay ASCII; Cyrillic goes through CP1251 (and the glyph table)."""
 if profile=='en':return text.encode('ascii')
 out=bytearray()
 for ch in text:
  if ord(ch)<128:out.append(ord(ch));continue
  b=ch.encode('cp1251')[0]
  if profile=='cp1251':out.append(b)
  else:
   g=GLYPH_TABLE[b-0x80]
   assert g,('no glyph for',ch)
   out.append(g)
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

# FONT TEST: the Cyrillic alphabet, once per layout. Row 1-4 of each page; every letter of the game's table appears.
ALPHA_UP1='АБВГДЕЖЗИЙКЛМНОП';ALPHA_UP2='РСТУФХЦЧШЩЪЫЬЭЮЯ';ALPHA_LO1='абвгдежзийклмноп';ALPHA_LO2='рстуфхцчшщъыьэюя'
RU_MESSAGES['HFTEST']='~b~ТЕСТ ШРИФТА~w~ '+ALPHA_UP1+' '+ALPHA_LO1
def font_test_rows(profile):
 tag='1: ' if profile=='cp1251' else '2: '
 return [encode(tag+s,profile) for s in (ALPHA_UP1,ALPHA_UP2,ALPHA_LO1,ALPHA_LO2)]
