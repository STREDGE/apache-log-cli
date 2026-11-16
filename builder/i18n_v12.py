"""Helicover 1.2 language data: every Russian text and the codes of the game's Russian font.

The game draws help-box messages (FXT keys) and CLEO menu rows with CFont::PrintString; a text byte becomes a 16-bit code as it is.
What the font shows for a code depends on the language the GAME is set to (libGTASA 2.00 arm64 + the player's screenshots):

  Russian          CFont::UsingRussianLanguage: every font style goes through one atlas (RussianFont.met); the glyph is entry
                   "code - 0x20" and every code past the end of the atlas is drawn as '@'. The letters run in alphabet order,
                   A-YA = 0x80-0x9F, a-ya = 0xA0-0xBF (Unicode - 0x390), with no IO. Confirmed on the phone (FONT TEST of beta 3).
  anything else    the font has no Cyrillic (English) or a different, unofficial layout (the SanLTD fan localisation): the mod
                   stays in English there. The player asked for exactly this: Russian with the game's Russian, English otherwise.

Beta 1-2 shipped CP1251 and "russian_table" layouts (both wrong), beta 3 added a SanLTD profile and a LANGUAGE page (removed
at the player's request).
"""
import re
ALPHABET='АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'   # 32 letters, no IO: the official atlas has none
PROFILES=('en','game')
def encode(text,profile):
 """Text -> bytes for a profile. Latin text, digits and punctuation stay ASCII; Cyrillic goes to the codes of the game's Russian font."""
 if profile=='en':return text.encode('ascii')
 out=bytearray()
 for ch in text:
  if ord(ch)<128:out.append(ord(ch));continue
  ch={'Ё':'Е','ё':'е'}.get(ch,ch);i=ALPHABET.find(ch.upper())
  assert i>=0,('no glyph for',ch)
  out.append((0x80 if ch.isupper() else 0xA0)+i)
 return bytes(out)
def ukey(key):return 'U'+key[1:]
def key_for(key,lang):return (key,ukey(key))[lang]

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
 'HCCONT':'~r~КОНТАКТ!~w~ Стрелки открыли огонь.',
 'HCKILL':'~g~ЦЕЛЬ УНИЧТОЖЕНА~w~ ~1~',
 'HCCLEAR':'~g~СТРЕЛКИ:~w~ чисто.',
 'HCNOBR':'~r~НЕТ МОДА МОЗГА.~w~ Положите libHelicoverBrain64.so в папку mods.',
 'HCFM0':'~y~СТРЕЛКИ:~w~ прекратить огонь.',
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
 'HCBURN':'~r~МАШИНА ГОРИТ!~w~ Отойдите от нее.',
 'HCEVADE':'~r~ПОПАДАНИЯ!~w~ Пилот уходит от огня.',
 'HCSHOT':'~r~ОБСТРЕЛ!~w~ Пилот уходит от огня.',
 'HCHELLO':'~b~HELICOVER 1.5 БЕТА 3~w~ готов. Меню CLEO > Helicover.',
 'HCHELLV':'~b~HELICOVER 1.5 БЕТА 3~w~ готов. Метка на карте отключена.',
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
 'SQCAR':'~g~ОТРЯД:~w~ садимся в машину.',
 'SQEVAC':'~r~СЛИШКОМ ЖАРКО!~w~ Уходим - вертолет идет с веревкой.',
 'SQGOF':'~g~КОМАНДИР:~w~ CJ, за мной! Укрытие прямо - беги ко мне.',
 'SQGOR':'~g~КОМАНДИР:~w~ CJ, за мной! Укрытие справа - беги ко мне.',
 'SQGOB':'~g~КОМАНДИР:~w~ CJ, за мной! Укрытие сзади - беги ко мне.',
 'SQGOL':'~g~КОМАНДИР:~w~ CJ, за мной! Укрытие слева - беги ко мне.',
 'SQMEF':'~g~КОМАНДИР:~w~ укрытия нет - держись у охраны, вперед!',
 'SQMER':'~g~КОМАНДИР:~w~ укрытия нет - держись у охраны, вправо!',
 'SQMEB':'~g~КОМАНДИР:~w~ укрытия нет - держись у охраны, назад!',
 'SQMEL':'~g~КОМАНДИР:~w~ укрытия нет - держись у охраны, влево!',
 'SQSAFE':'~g~КОМАНДИР:~w~ CJ в укрытии. Держись там, работаем.',
 'SQMEM':'~y~КОМАНДИР:~w~ здесь на нас уже нападали. Смотрим в оба.',
 'SQGF':'~r~ГРАНАТА - СПЕРЕДИ!~w~ Прочь от нее!', 'SQGR':'~r~ГРАНАТА - СПРАВА!~w~ Прочь от нее!', 'SQGB':'~r~ГРАНАТА - СЗАДИ!~w~ Прочь от нее!', 'SQGL':'~r~ГРАНАТА - СЛЕВА!~w~ Прочь от нее!',
 'SQWATER':'~y~КОМАНДИР:~w~ CJ в воде - вертолет над тобой, бери веревку.',
 'SQAHEAD':'~y~ПИЛОТ:~w~ впереди по пути вооруженные.',
 'SQCMD':'~r~КОМАНДИР ВЫБЫЛ!~w~ БРАВО: командую я.',
 'HCXBL':'~b~ПИЛОТ:~w~ кнопка выхода - посадка.',
 'HCXBR':'~b~ПИЛОТ:~w~ кнопка выхода - спуск по веревке.',
 'HCRBSY':'~y~ПИЛОТ:~w~ подождите, идет работа на веревке.',
 'HCRUP':'~b~ПИЛОТ:~w~ отряд, поднимайтесь по веревкам.',
 'HCDSQ':'~b~ПИЛОТ:~w~ сначала заберу отряд, потом улетаем.',
 'HCRCAN':'~b~ПИЛОТ:~w~ подъем отменен. Убираю веревки.',
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
 """Every key must stay unique and at most 7 characters after the U rewrite."""
 seen={}
 for k in RU_MESSAGES:
  for lang in (0,1):
   kk=key_for(k,lang)
   assert len(kk)<=7 and re.fullmatch(r'[A-Z0-9]+',kk),kk
   assert kk not in seen,(kk,k,seen.get(kk));seen[kk]=k
 return seen


# ----------------------------------------------------------------------------------------------- menu
# id -> (English, Russian). Rows stay short (the CLEO menu panel is narrow): at most 26 characters in English, 28 in Russian.
MENU={
 'CALL':('CALL HELICOPTER','ПОЗВАТЬ ВЕРТОЛЕТ'),
 'WAIT_IN':('HELICOPTER INBOUND...','ВЕРТОЛЕТ ЛЕТИТ...'),
 'WAIT_OUT':('HELICOPTER LEAVING...','ВЕРТОЛЕТ УЛЕТАЕТ...'),
 'WAIT_SWAP':('CHANGING, PLEASE WAIT...','ИДЕТ ЗАМЕНА...'),
 'SETTINGS':('SETTINGS >','НАСТРОЙКИ >'),
 'GUNFIRE':('GUNNER FIRE >','ОГОНЬ СТРЕЛКОВ >'),
 'FOLLOW':('FOLLOW ME','ЛЕТЕТЬ ЗА МНОЙ'),
 'HOLD':('HOLD HERE','ЖДАТЬ ЗДЕСЬ'),
 'PATROL':('PATROL AROUND ME','ПАТРУЛЬ ВОКРУГ'),
 'ROPE':('CLIMB ABOARD BY ROPE','НА БОРТ ПО ВЕРЕВКЕ'),
 'ROPE_CANCEL':('CANCEL ROPE PICKUP','ОТМЕНИТЬ ПОДЪЕМ'),
 'TEAM_ON':('DEPLOY SQUAD','ВЫСАДИТЬ ОТРЯД'),
 'TEAM_OFF':('RECALL SQUAD','ЗАБРАТЬ ОТРЯД'),
 'TEAM_DOWN':('SQUAD ROPING DOWN...','ОТРЯД ВЫСАЖИВАЕТСЯ...'),
 'TEAM_UP':('SQUAD COMING BACK...','ОТРЯД ВОЗВРАЩАЕТСЯ...'),
 'DISMISS':('DISMISS HELICOPTER','ОТПУСТИТЬ ВЕРТОЛЕТ'),
 'MAP':('FLY TO MAP MARKER','ЛЕТЕТЬ К МЕТКЕ НА КАРТЕ'),
 'GROVE':('FLY TO GROVE STREET','ЛЕТЕТЬ НА ГРОУВ-СТРИТ'),
 'EXIT_LAND':('EXIT BUTTON: LAND','КНОПКА ВЫХОДА: ПОСАДКА'),   # switches for the game's exit button, they do nothing by themselves
 'EXIT_ROPE':('EXIT BUTTON: ROPE','КНОПКА ВЫХОДА: ВЕРЕВКА'),
 'BACK':('< BACK','< НАЗАД'),
 'SET_TITLE':('HELICOVER / SETTINGS','HELICOVER / НАСТРОЙКИ'),
 'SET_CREW':('CREW >','ЭКИПАЖ >'),
 'SET_MODEL':('HELICOPTER MODEL >','МОДЕЛЬ ВЕРТОЛЕТА >'),
 'SET_WEAPON':('CREW WEAPON >','ОРУЖИЕ ЭКИПАЖА >'),
 'TAC_AUTO':('SQUAD TACTICS: AUTO','ТАКТИКА: АВТО'),
 'TAC_GUARD':('SQUAD TACTICS: GUARD','ТАКТИКА: ОХРАНА'),
 'TAC_ASSAULT':('SQUAD TACTICS: ASSAULT','ТАКТИКА: ШТУРМ'),
 'POSE_KNEEL':('GUNNERS: KNEELING','СТРЕЛКИ: С КОЛЕНА'),
 'POSE_STAND':('GUNNERS: STANDING','СТРЕЛКИ: СТОЯ'),
 'POSE_SIT':('GUNNERS: SITTING','СТРЕЛКИ: СИДЯ'),
 'MSG_OFF':('MESSAGES: OFF','СООБЩЕНИЯ: ВЫКЛ'),
 'MSG_IMP':('MESSAGES: IMPORTANT','СООБЩЕНИЯ: ВАЖНЫЕ'),
 'MSG_ALL':('MESSAGES: ALL','СООБЩЕНИЯ: ВСЕ'),
 'FIRE_TITLE':('HELICOVER / GUNNER FIRE','HELICOVER / ОГОНЬ СТРЕЛКОВ'),
 'FIRE3':('PROTECT ME','ЗАЩИЩАТЬ МЕНЯ'),
 'FIRE4':('ARMED ONLY','ТОЛЬКО ВООРУЖЕННЫЕ'),
 'FIRE2':('WHERE I SHOOT','ТАМ, ГДЕ СТРЕЛЯЮ Я'),
 'POL_ANSWER':('POLICE: FIRE BACK','ПОЛИЦИЯ: ОТВЕЧАТЬ'),
 'POL_NEVER':('POLICE: NEVER FIRE','ПОЛИЦИЯ: НЕ СТРЕЛЯТЬ'),
 'MIS_DEF':('MISSIONS: DEFEND ONLY','МИССИИ: ОБОРОНА'),
 'MIS_FREE':('MISSIONS: AS USUAL','МИССИИ: КАК ОБЫЧНО'),
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
 'TITLE_READY':('HELICOVER 1.5 BETA 3','HELICOVER 1.5 БЕТА 3'),
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

def fxt_text(key):
 return encode(RU_MESSAGES[key],'game')
