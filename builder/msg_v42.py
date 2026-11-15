"""Helicover 1.1 message dispatcher, shared by every script.

say(s,key) shows a help-box message only when it deserves the screen:
- priority 4 (answer to the player's own action) is always shown;
- otherwise MESSAGES: ALL shows 1-3, IMPORTANT shows 2-3, OFF shows none;
- a message replaces the one on screen only when that one has expired or is not more important,
  so a fight produces a few clear radio calls instead of a beeping stream.
The two registers it needs are saved to shared slots and restored, so it can be dropped into any
place of any script (scripts never preempt each other between two instructions without a WAIT).
"""
from asm_v25 import *
STATE=0x48456A00
HUD=STATE+9              # 2 ALL, 1 IMPORTANT, 0 OFF
MSG_UNTIL=STATE+331;MSG_PRIO=STATE+332;SAVE_A=STATE+333;SAVE_B=STATE+334
# 1.2 language: LANG_SETTING 0 AUTO / 1 ENGLISH / 2 RUSSIAN for the game's own Russian / 3 RUSSIAN for SanLTD; LANG is what is in force:
# 0 English, 1 Russian in the codes of the game's Russian font (FXT keys U...), 2 Russian in SanLTD codes (FXT keys V...)
LANG=STATE+409;LANG_SETTING=STATE+410
# bytes in libGTASA 2.00 arm64: CFont::UsingRussianLanguage, CFont::UsingEFIGSLanguage, FrontEndMenuManager + 0x48 (the language index
# opcode 09FB returns: 0 English, 1 French, 2 German, 3 Italian, 4 Spanish; SanLTD is installed over French)
GAME_RU_FLAG=0xCE1771;GAME_EFIGS_FLAG=0xCE1773;GAME_LANG_BYTE=0xC1DE88;SANLTD_SLOT=1
from i18n_v12 import ukey,vkey
LEVEL_ALL,LEVEL_IMPORTANT,LEVEL_OFF=2,1,0
SHOW_MS={1:2500,2:3000,3:3500,4:3000}
ACTION=4;DANGER=3;TACTICAL=2;CHATTER=1
PRIO={}
def prio(level,*keys):
 for k in keys:PRIO[k]=level
prio(ACTION,'HCNEED','HCVER','HCNOMAP','HCIN','HCEXIT','HCNOSEA','HCNOSIT','HCFAR','HCLOSE','HCXWAIT','HCDWAIT','HCXARR',
 'HCXHERE','HCSNO','HCSFAIL','HCCFAIL','SQALR','SQNONE','SQFOOT',
 'SQCREW','HCOUT','HCFAIL','HCOFF','HCBLOCK','HCRWAIT','HCGCLMB','HCWAIT','HCXROPE','HCNOPAD','HCCHOS','HCHELLO','HCHELLV',
 'RGFAIL','RGHOLD','RGHIGH','RGMOVE','RGBLOCK',
 'RGSEAT','RGANIM','RPDFAIL','HCMAPOF','HCDBG','HCBUSY')
prio(DANGER,'HCFOCUS','HCSHOT','HCEVADE','HCAIR','SQCOV','SQDOWN','SQEVAC','SQLOST','HCDAMAG','HCEMERG',
 *['SQ'+k+d for k in 'XSVR' for d in 'FLBR'])
prio(TACTICAL,'HCLOAD','HCFOLL','HCHOLD','HCPAT','HCDEPT','HCROPE','HCRTEAM','HCRBACK','HCSWAP','HCCREW',
 'HCFM0','HCFM1','HCFM2','HCFM3','HCFM4','HCCONT','HCCLEAR','SQCLR','SQIN','SQBACK','SQCOVER','RGUP','RGABO','RGDEP','RGDONE','HCAVOID','HCEVAC','HCTEAM',
 'HCBOARD','HCGROVE','HCHOME','HCARRIV','HCMUST','RGLATE','SQAWAY','SQSTAY',*['SQ'+k+d for k in 'CA' for d in 'FLBR'])
prio(CHATTER,'SQRLD','SQCVR','SQMED','SQMEDG','SQCAR')
_n=[0]
def print_key(s,key,P,number=None):
 """PRINT_HELP / PRINT_WITH_NUMBER_NOW for `key` in the language in force (V18 is free to use at the call sites)."""
 a=s.add
 def pr(k):
  if number is None:a(0x03e5,S(k))
  else:a(0x01e5,S(k),*number)
 s.get(18,LANG);s.eq(18,0,P+'LU');pr(key);s.go(P+'LD')
 s.label(P+'LU');s.eq(18,1,P+'LV');pr(ukey(key));s.go(P+'LD')
 s.label(P+'LV');pr(vkey(key));s.label(P+'LD')
def emit_resolve_lang(s,game_ok_key):
 """Subroutine RESOLVE_LANG (Core): LANG from LANG_SETTING. AUTO follows the language the game is set to: its own Russian -> 1,
 the French slot with the EFIGS font (where SanLTD lives) -> 2, anything else -> English (those fonts have no Cyrillic).
 Uses V17 and V19. `game_ok_key` is the shared flag that says the libGTASA build is the known one (memory reads are safe)."""
 a=s.add;s.label('RESOLVE_LANG');s.get(19,LANG_SETTING);s.eq(19,0,'RL_FIXED')
 s.set(LANG,0);s.get(17,game_ok_key);s.eq(17,1,'RL_DONE')
 a(0x0dd8,V(17),I(GAME_RU_FLAG),I(1),I(1));s.eq(17,1,'RL_EFIGS');s.set(LANG,1);s.ret()
 s.label('RL_EFIGS');a(0x0dd8,V(17),I(GAME_EFIGS_FLAG),I(1),I(1));s.eq(17,1,'RL_DONE')
 a(0x0dd8,V(17),I(GAME_LANG_BYTE),I(1),I(1));s.eq(17,SANLTD_SLOT,'RL_DONE');s.set(LANG,2);s.ret()
 s.label('RL_FIXED');s.eq(19,1,'RL_RU1');s.set(LANG,0);s.ret()
 s.label('RL_RU1');s.eq(19,2,'RL_RU2');s.set(LANG,1);s.ret()
 s.label('RL_RU2');s.set(LANG,2)
 s.label('RL_DONE');s.ret()
def say(s,key,level=None):
 """Inline: show `key` through the dispatcher (uses no registers of the caller)."""
 a=s.add;p=PRIO.get(key,TACTICAL) if level is None else level;_n[0]+=1;P='SAY%d_'%_n[0];skip=P+'SKIP';show=P+'SHOW'
 a(0xddc,I(SAVE_A),V(18));a(0xddc,I(SAVE_B),V(19));a(0x01bd,V(19))
 if p<ACTION:
  s.get(18,HUD);s.check(0x0019,[V(18),I(LEVEL_IMPORTANT if p==CHATTER else LEVEL_OFF)],skip)
  s.get(18,MSG_UNTIL);s.check(0x001d,[V(18),V(19)],show)
  s.get(18,MSG_PRIO);s.check(0x0019,[V(18),I(p)],show);s.go(skip)
 s.label(show);print_key(s,key,P)
 a(0x000a,V(19),I(SHOW_MS[p]));a(0xddc,I(MSG_UNTIL),V(19));s.set(MSG_PRIO,p)
 s.label(skip);s.get(18,SAVE_A);s.get(19,SAVE_B)
