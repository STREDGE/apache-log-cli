"""Helicover message dispatcher, shared by every script.

Beta 6: the messages are no longer help boxes. On the mobile game the help box is a queue (CWidgetHelpText::AddMessageToQueue): every
message stays 5 s plus 0.65 s of fades and a new one NEVER replaces the one on screen, so a busy minute ran up to 50 s behind the events.
say() now only writes "which message, until when" into shared slots, and the fire worker - the one script that runs every frame -
draws that message as a line of script text at the top of the screen (BANNER): it is there on the next frame and gone or replaced at once.

say(s,key) gives a message the screen only when it deserves it:
- priority 4 (answer to the player's own action) is always shown;
- otherwise MESSAGES: ALL shows 1-3, IMPORTANT shows 2-3, OFF shows none;
- a message replaces the one on screen when that one has expired or is not more important; a message ONE level less important may
  replace it once it has been readable for MIN_SHOW_MS (an answer to a button must not hide "SHOOTER ON CJ!" for three seconds),
  so a fight produces a few clear radio calls instead of a beeping stream - one line, never two on top of each other.
The two registers it needs are saved to shared slots and restored, so it can be dropped into any
place of any script (scripts never preempt each other between two instructions without a WAIT).
"""
from asm_v25 import *
STATE=0x48456A00
HUD=STATE+9              # 2 ALL, 1 IMPORTANT, 0 OFF
MSG_UNTIL=STATE+331;MSG_PRIO=STATE+332;SAVE_A=STATE+333;SAVE_B=STATE+334
MSG_ID=STATE+437;BANNER_ARMED=STATE+438;MSG_HOLD=STATE+439   # which message (index into KEYS), drawing started, end of its protected time
MIN_SHOW_MS=1200
# The line of text: script space is 640 x 448 (x mapped to the centred 4:3 area, y to the full height). Centred on the screen, two lines at
# most above the CLEO menu (its top edge is at 0.075 of the height). Font size = height * H / 448 / 2; a line breaks at CENTRE_SIZE * W / 640.
BANNER_X=320.0;BANNER_Y=3.0;BANNER_HEIGHT=1.4;BANNER_CENTRE_SIZE=352.0
from i18n_v12 import RU_MESSAGES
KEYS=sorted(RU_MESSAGES);KEY_ID={k:i for i,k in enumerate(KEYS)}   # every message of every script (the Russian table has them all): say() names one by its index
# 1.2 language: LANG is what is in force: 0 English, 1 Russian in the codes of the game's Russian font (FXT keys U...). It follows the
# game: Russian when the game is set to its own Russian (byte CFont::UsingRussianLanguage of libGTASA 2.00 arm64), English otherwise.
LANG=STATE+409;GAME_RU_FLAG=0xCE1771
from i18n_v12 import ukey
LEVEL_ALL,LEVEL_IMPORTANT,LEVEL_OFF=2,1,0
SHOW_MS={1:2500,2:3000,3:3500,4:3000}
ACTION=4;DANGER=3;TACTICAL=2;CHATTER=1
PRIO={}
def prio(level,*keys):
 for k in keys:PRIO[k]=level
prio(ACTION,'HCNOBR','HCNEED','HCVER','HCNOMAP','HCIN','HCEXIT','HCNOSEA','HCNOSIT','HCFAR','HCLOSE','HCXWAIT','HCDWAIT','HCXARR',
 'HCXHERE','HCSNO','HCSFAIL','HCCFAIL','SQALR','SQNONE','SQFOOT',
 'SQCREW','HCOUT','HCFAIL','HCOFF','HCBLOCK','HCRWAIT','HCGCLMB','HCWAIT','HCXROPE','HCNOPAD','HCCHOS','HCHELLO','HCHELLV',
 'RGFAIL','RGHOLD','RGHIGH','RGMOVE','RGBLOCK',
 'RGSEAT','RGANIM','RPDFAIL','HCMAPOF','HCDBG','HCBUSY','HCXBL','HCXBR','HCRBSY','HCRCAN','HCRUP','HCDSQ')
prio(DANGER,'HCBURN','HCSHOT','HCEVADE','SQDOWN','SQEVAC','SQLOST','HCDAMAG','HCEMERG','SQCMD',*['SQGO'+d for d in 'FRBL'],*['SQME'+d for d in 'FRBL'],
 *['SQ'+k+d for k in 'XSVR' for d in 'FLBR'])
prio(TACTICAL,'HCLOAD','HCFOLL','HCHOLD','HCPAT','HCDEPT','HCROPE','HCRTEAM','HCRBACK','HCSWAP','HCCREW',
 'HCFM0','HCFM2','HCFM3','HCFM4','HCCONT','HCCLEAR','SQCLR','SQSAFE','SQMEM','SQIN','SQBACK','SQCOVER','RGUP','RGABO','RGDEP','RGDONE','HCAVOID','HCEVAC','HCTEAM',
 'HCBOARD','HCGROVE','HCHOME','HCARRIV','HCMUST','RGLATE','SQAWAY','SQSTAY',*['SQ'+k+d for k in 'CA' for d in 'FLBR'])
prio(CHATTER,'SQCAR')
# beta 6: the pilot's / gunners' acknowledgement of an order the player has just given. It is still a routine message for the MESSAGES
# setting, but it takes the line at once whatever is on it ("press a button - the answer is there"), and only an alarm may replace it early.
ORDER_ACK={'HCLOAD','HCFOLL','HCHOLD','HCPAT','HCDEPT','HCEVAC','HCFM0','HCFM2','HCFM3','HCFM4','HCGROVE','HCRBACK','HCROPE','HCRTEAM','HCSWAP','HCCREW','SQSTAY'}
_n=[0]
def print_key(s,key,P,number=None):
 """PRINT_HELP / PRINT_WITH_NUMBER_NOW for `key` in the language in force (V18 is free to use at the call sites)."""
 a=s.add
 def pr(k):
  if number is None:a(0x03e5,S(k))
  else:a(0x01e5,S(k),*number)
 s.get(18,LANG);s.eq(18,0,P+'LU');pr(key);s.go(P+'LD')
 s.label(P+'LU');pr(ukey(key));s.label(P+'LD')
def emit_resolve_lang(s,game_ok_key):
 """Subroutine RESOLVE_LANG (Core): Russian when the game itself is set to its own Russian, English otherwise.
 Uses V17. `game_ok_key` is the shared flag that says the libGTASA build is the known one (the memory read is safe)."""
 a=s.add;s.label('RESOLVE_LANG');s.get(17,game_ok_key);s.eq(17,1,'RL_EN')
 a(0x0dd8,V(17),I(GAME_RU_FLAG),I(1),I(1));s.eq(17,1,'RL_EN');s.set(LANG,1);s.ret()
 s.label('RL_EN');s.set(LANG,0);s.ret()
def say(s,key,level=None):
 """Inline: show `key` through the dispatcher (uses no registers of the caller)."""
 a=s.add;p=PRIO.get(key,TACTICAL) if level is None else level;_n[0]+=1;P='SAY%d_'%_n[0];skip=P+'SKIP';show=P+'SHOW';ack=level is None and key in ORDER_ACK
 a(0xddc,I(SAVE_A),V(18));a(0xddc,I(SAVE_B),V(19));a(0x01bd,V(19))
 if p<ACTION:
  s.get(18,HUD);s.check(0x0019,[V(18),I(LEVEL_IMPORTANT if p==CHATTER else LEVEL_OFF)],skip)
 if p<ACTION and not ack:
  s.get(18,MSG_UNTIL);s.check(0x001d,[V(18),V(19)],show)
  s.get(18,MSG_PRIO);s.check(0x0019,[V(18),I(p)],show)
  a(0x000a,V(18),I(-p));s.check(0x8019,[V(18),I(1)],skip);s.get(18,MSG_HOLD);s.check(0x001d,[V(18),V(19)],show);s.go(skip)
 s.label(show);s.set(MSG_ID,KEY_ID[key]);a(0x0085,V(18),V(19));a(0x000a,V(18),I(MIN_SHOW_MS));a(0xddc,I(MSG_HOLD),V(18))
 a(0x000a,V(19),I(SHOW_MS[p]));a(0xddc,I(MSG_UNTIL),V(19));s.set(MSG_PRIO,p+1 if ack else p)
 s.label(skip);s.get(18,SAVE_A);s.get(19,SAVE_B)
def emit_banner(s,label='BANNER',t1=30,t2=31):
 """Subroutine for a script that runs every frame: draw the current message. USE_TEXT_COMMANDS 1 makes the game wipe the script text
 lines at the start of every script pass, so the line is issued again each frame and is gone the frame after we stop. The first frame of
 a message only switches that wiping on (should another script have left stale lines, DISPLAY_TEXT must not be added to them)."""
 a=s.add;P=label+'_'
 s.label(label);s.get(t2,MSG_UNTIL);a(0x01bd,V(t1));s.check(0x001d,[V(t2),V(t1)],P+'OFF');a(0x03f0,I(1))
 s.get(t1,BANNER_ARMED);s.eq(t1,0,P+'DRAW');s.set(BANNER_ARMED,1);s.ret()
 s.label(P+'OFF');s.set(BANNER_ARMED,0);s.ret()
 s.label(P+'DRAW');a(0x033f,F(.5),F(BANNER_HEIGHT));a(0x0340,I(255),I(255),I(255),I(255));a(0x0342,I(1));a(0x0344,F(BANNER_CENTRE_SIZE));a(0x081c,I(1),I(0),I(0),I(0),I(255))
 s.get(t2,MSG_ID);s.get(t1,LANG);s.eq(t1,0,P+'RU')
 for lang,conv in (('EN',lambda k:k),('RU',ukey)):
  if lang=='RU':s.label(P+'RU')
  for b0 in range(0,len(KEYS),16):s.check(0x0019,[V(t2),I(b0+15)],P+'%s_B%d'%(lang,b0))
  s.ret()
  for b0 in range(0,len(KEYS),16):
   s.label(P+'%s_B%d'%(lang,b0))
   for i in range(b0,min(b0+16,len(KEYS))):
    nxt=P+'%s_N%d'%(lang,i);s.eq(t2,i,nxt);a(0x033e,F(BANNER_X),F(BANNER_Y),S(conv(KEYS[i])));s.ret();s.label(nxt)
   s.ret()
