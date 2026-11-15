"""Mutation check: break one rule at a time in a scratch copy of builder/ and make sure the tests notice.
   python3 tools/mutate.py            all mutants      python3 tools/mutate.py --new     only the 1.2 ones      --b4  only the beta 4 ones      --b5  only the beta 5 ones      --b6  only the beta 6 ones      --b7  only the 1.3 (brain) ones      (names as arguments pick single mutants)
   A line 'MISSED ... <<<<<<' means a rule has no test that guards it."""
import shutil,subprocess,sys,os,tempfile
from pathlib import Path
SRC=Path(__file__).resolve().parent.parent;ROOT=Path(os.environ.get('HC_MUT_ROOT') or Path(tempfile.gettempdir())/'helicover_mut')   # HC_MUT_ROOT: a second run in parallel needs its own scratch copy
M=[
 ('build_v25.py',"msg(c,'HCSHOT')","pass",'evade on shots'),
 ('build_v25.py',"c.check(0x0019,[V(8),I(0)],'ORBIT_DIR_SET')","c.check(0x0019,[V(8),I(100)],'ORBIT_DIR_SET')",'orbit door'),
 ('build_v25.py',"c.check(0x0021,[V(8),F(6)],'TRACK_POS');a(0x000b,V(11),F(15))","c.check(0x0021,[V(8),F(6)],'TRACK_POS');a(0x000b,V(11),F(0))",'roof orbit'),
 ('build_v25_squad.py',"else:msg('SQ'+'XSVR'[kind-1]+letter,throttle)","else:msg('SQC'+letter,throttle)",'typed call-outs'),
 ('build_v25_squad.py',"s.check(0x06bd,[V(19),V(20),V(29),V(26),V(27),V(30),I(1),I(1),I(0),I(1),I(0)],blk);s.go(nxt)","s.check(0x06bd,[V(19),V(20),V(29),V(26),V(27),V(30),I(1),I(1),I(0),I(1),I(0)],nxt);s.go(blk)",'cover chest'),
 ('build_v25_squad.py',"s.check(0x0019,[V(19),I(10000)],P+'NO_RELOAD')","s.check(0x0019,[V(19),I(1000000)],P+'NO_RELOAD')",'reload'),
 ('build_v25_squad.py',"a(0xddc,I(b.ENG_T+k),V(31))\n","a(0xddc,I(b.ENG_T+k),V(12))\n",'reload stagger'),
 ('build_v25_squad.py',"msg('SQEVAC',False)","s.add(0)",'evac'),
 ('build_v25_squad.py',"s.check(0x0019,[V(30),I(20000)],P+'ALERT')","s.check(0x0019,[V(30),I(2000000)],P+'ALERT')",'relax'),
 ('build_v25_squad.py',"s.check(0x0021,[V(18),F(6)],P+'SPD_GO');a(6,V(20),I(7))","s.check(0x0021,[V(18),F(6)],P+'SPD_GO');a(6,V(20),I(6))",'sprint'),
]
M+=[
 ('msg_v42.py',"  s.get(18,MSG_PRIO);s.check(0x0019,[V(18),I(p)],show)\n","  s.go(show)\n",'dispatcher priority'),
 ('msg_v42.py',"s.get(18,HUD);s.check(0x0019,[V(18),I(LEVEL_IMPORTANT if p==CHATTER else LEVEL_OFF)],skip)","pass",'dispatcher level'),
 ('msg_v42.py',"s.get(18,MSG_UNTIL);s.check(0x001d,[V(18),V(19)],show)","s.go(show)",'dispatcher hold time'),
 ('build_v25.py',"p.get(19,NOTICE_SKIP);p.check(0x003b,[V(8),V(19)],'NOTICE_SAY')","p.go('NOTICE_SAY')",'notice skip'),
 ('build_v25.py',"for pend,key in [(1,'HCRTEAM'),(2,'HCRBACK')]:","for pend,key in []:",'rope notice variants'),
 ('build_v25.py',"c.set(HELLO_AT,-1);","c.set(HELLO_AT,0);",'hello once'),
 ('build_v25.py',"a(0x0013,V(26),F(.3));","a(0x0013,V(26),F(0));",'orbit centre shift'),
 ('build_v25_squad.py',"s.label(hurt);s.check(0x0021,[V(24),F(limit*.7)],ok)","s.label(hurt);s.check(0x0021,[V(24),F(limit)],ok)",'wounded leash'),
]
M12=[
 # E1 helicopter
 ('build_v25.py',"c.get(8,CR_DT);a(0x006b,V(19),V(8))","a(0x0007,V(8),F(.1));a(0x006b,V(19),V(8))",'12 glide frame clock'),
 ('build_v25.py',"c.check(0x0021,[V(19),F(25)],'GL_SP_OK');a(0x0007,V(19),F(25))","c.check(0x0021,[V(19),F(250)],'GL_SP_OK');a(0x0007,V(19),F(250))",'12 glide speed cap'),
 ('build_v25.py',"a(0x04df,V(5),I(0));a(0x04a2,V(5),V(9),V(10),V(11),F(15),V(11));a(0x00ad,V(5),F(20))","a(0x00ab,V(5),V(9),V(10),V(11))",'12 unstick teleport'),
 ('build_v25.py',"c.check(0x0021,[V(19),F(8)],'EXH_AT');a(0x000b,V(19),F(10))","c.check(0x0021,[V(19),F(8)],'EXH_AT');a(0x000b,V(19),F(0))",'12 exit point ahead'),
 ('build_v25.py',"a(0xddc,I(CR_V),V(30));c.ret()   # 1.2: continues","a(0x0007,V(30),F(0));a(0xddc,I(CR_V),V(30));c.ret()   # 1.2: continues",'12 cruise real speed'),
 ('build_v25.py',"c.check(0x0019,[V(17),I(15000)],'BLOCK_WATCH_DONE');c.check(0x80db","c.check(0x0019,[V(17),I(15000000)],'BLOCK_WATCH_DONE');c.check(0x80db",'12 state 18 watchdog'),
 ('build_v25.py',"for cmd in [2,3,4,14]:","for cmd in []:",'12 emergency refuses orders'),
 ('build_v25.py',"[(0,0),(25,0),(-25,0),(0,25),(0,-25)]","[(0,0)]",'12 emergency site search'),
 ('build_v25.py',"c.eq(19,2,'ARRIVE_GO');c.get(17,ESCORT_ON);c.eq(17,1,'ARRIVE_TEAM_GONE')","c.eq(19,2,'ARRIVE_GO');c.go('ARRIVE_GO')",'12 recall of gone team'),
 ('build_v25.py',"c.get(17,ROPE_BUSY);c.eq(17,0,'SWAP_DEFER');c.set(SWAP_MSG,0)","c.set(SWAP_MSG,0)",'12 swap waits for rope'),
 ('build_v25.py',"c.get(19,FROZEN);c.eq(19,1,'RESUME_HOLD_FREE');a(0x0574,V(5),I(1));c.ret()","c.call('BLOCK_HOVER');c.ret()",'12 swap keeps frozen'),
 ('build_v25.py',"c.call('PUBLISH');c.call('ARM_CREW');c.get(19,CREWGEN)","c.call('PUBLISH');c.get(19,CREWGEN)",'12 arm new gunners'),
 ('build_v25.py',"if k:c.check(0x02ca,[V(5)],'SPAWN_PLACED')","if k:c.go('SPAWN_PLACED')",'12 spawn unseen'),
 ('msg_v42.py',"s.get(18,LANG);s.eq(18,0,P+'LU')","a(6,V(18),I(0));s.eq(18,0,P+'LU')",'12 say language'),
 # E2 ground team
 ('build_v25_ground.py',"s.check(0x0019,[V(16),I(60000)],nxt)","s.check(0x0019,[V(16),I(60000000)],nxt)",'12 lag 60 s'),
 ('build_v25_ground.py',"s.check(0x82cb,[V(var)],seen);a(0x009b,V(var));s.go(done)","a(0x009b,V(var));s.go(done)",'12 release in view'),
 ('build_v25_ground.py',"a(0x01bd,V(18));a(0x000a,V(18),I(25000));a(6,V(24),I(0))","a(0x01bd,V(18));a(0x000a,V(18),I(2500));a(6,V(24),I(0))",'12 recall wait 25 s'),
 ('build_v25_ground.py',"s.check(0x0021,[V(16),F(2.5)],keep)","s.go(keep)",'12 leave laggards'),
 ('build_v25_ground.py',"a(0x0633,V(var));s.go(skip)","s.go(skip)",'12 guard leaves car'),
 ('build_v25_ground.py',"s.check(0x0019,[V(16),I(90000)],'ACTIVE_FRESH')","s.check(0x0019,[V(16),I(90000000)],'ACTIVE_FRESH')",'12 rope timeout'),
 ('build_v25_ground.py',"s.check(0x0256,[I(0)],'ABANDON');s.check(0x056e,[V(1)],'NOHOLD')","s.check(0x0256,[I(0)],'WAIT');s.check(0x056e,[V(1)],'NOHOLD')",'12 abandoned deploy'),
 ('build_v25_squad.py',"s.check(0x0021,[V(24),F(40)],P+'NEAR');form_point(k)","s.check(0x0021,[V(24),F(4000)],P+'NEAR');form_point(k)",'12 far guards sprint'),
 ('build_v25_squad.py',"s.get(25,b.SQ_DRIVES);s.eq(25,1,R)","pass",'12 driver only'),
 ('build_v25_squad.py',"a(0x05ca,V(G),V(6),I(8000),I(k))","a(0x05ca,V(G),V(6),I(8000),I(0))",'12 own seat'),
 ('build_v25_squad.py',"a(0x05f5,V(G),V(26),V(27),V(28),I(7),I(20000));setk_lit(k,'TASK',7)","a(0x00a1,V(G),V(26),V(27),V(28));setk_lit(k,'TASK',7)",'12 far guard teleport'),
 # D: the shooter / own-shot / helicopter-hit logic of the bullet-trace scan (lines, not exact end points)
 # independent review of 1.2: crew change vs rope, scripted exit, platform handle, shared aim, muster
 ('build_v25.py',"(the rope workers abort when the state is 17)\nc.get(17,ROPE_BUSY);c.eq(17,0,'SWAP_DEFER')\n","(the rope workers abort when the state is 17)\n",'12 crew change waits'),
 ('build_v25.py',"c.call('EXIT_UNFREEZE');a(0x01bd,V(21))","c.call('UNFREEZE');a(0x01bd,V(21))",'12 exit keeps cruise'),
 ('build_v25.py',"c.set(FROZEN,0);c.set(CR_V,0);c.ret()","c.set(FROZEN,0);c.ret()",'12 unfreeze clears speed'),
 ('build_v25_ground.py'," a(0x009a,I(8),V(mdl),V(10),V(11),V(12),V(8));s.check(0x056d,[V(8)],skip)\n a(0x0173,V(8),V(13));a(0x0085,V(7),V(8));s.call('GSETUP');a(0x0223,V(8),V(14));a(0x035f,V(8),V(9))\n s.check(0x0019,[V(4),I(0)],noarm2);a(0x01b2,V(8),V(4),I(30000));a(0x01b9,V(8),V(4));s.label(noarm2)\n a(0x009b,V(var));a(0x0085,V(var),V(8));"," a(0x009a,I(8),V(mdl),V(10),V(11),V(12),V(6));s.check(0x056d,[V(6)],skip)\n a(0x0173,V(6),V(13));a(0x0085,V(7),V(6));s.call('GSETUP');a(0x0223,V(6),V(14));a(0x035f,V(6),V(9))\n s.check(0x0019,[V(4),I(0)],noarm2);a(0x01b2,V(6),V(4),I(30000));a(0x01b9,V(6),V(4));s.label(noarm2)\n a(0x009b,V(var));a(0x0085,V(var),V(6));",'12 decor keeps platform handle'),
 ('build_v25.py',"[(13,4,2,1),(14,-4,2,2),(15,4,-2,-1),(16,-4,-2,-1)]","[(13,-4,2,1),(14,4,2,2),(15,-4,-2,-1),(16,4,-2,-1)]",'12 muster side'),
 ('build_v25.py',"a(0x0407,V(5),F(x),F(y),F(0),V(17),V(19),V(31));a(0x050a,V(9),V(10),V(11),V(17),V(19),V(31),V(29))","a(0x00aa,V(5),V(17),V(19),V(31));a(0x050a,V(9),V(10),V(11),V(17),V(19),V(31),V(29))",'12 muster point'),
 # E3 / E4
 ('build_v25_squad.py',"s.check(0x0019,[V(30),I(1500)],'AN_RET')","s.check(0x0019,[V(30),I(15)],'AN_RET')",'12 anchor 1.5 s'),
 ('build_v25_squad.py',"s.check(0x0021,[V(31),F(.5)],'AN_OFF')","s.check(0x0021,[V(31),F(-2)],'AN_OFF')",'12 anchor 60 deg'),
 ('build_v25_squad.py',"s.check(0x8019,[V(30),I(1200)],skip)","s.check(0x8019,[V(30),I(1200000)],skip)",'12 fire line stale'),
 ('build_v25_squad.py',"a(0x000b,V(31),F(2))\n  a(0x006b,V(31),V(20))","a(0x000b,V(31),F(0))\n  a(0x006b,V(31),V(20))",'12 fire line shift'),
 ('build_v25_squad.py',"leash(k,G,25,7);cover=","leash(k,G,40,7);cover=",'12 assault cap'),
 ('build_v25_squad.py'," if k==3:s.go(P+'BODYGUARD')"," if False:s.go(P+'BODYGUARD')",'12 medic stays'),
 # E5 decor
 ('build_v25_ground.py',"s.check(0x02f2,[V(var),V(mdl)],need);s.go(skip)","s.go(skip)",'12 team re-skin'),
 ('build_v25_ground.py',"a(0x01b2,V(var),V(4),I(30000));a(0x01b9,V(var),V(4));a(0x02e2,V(var),I(100));s.label(noarm)","s.label(noarm)",'12 team weapon'),
 ('build_v25_ground.py',"s.label(need);a(6,V(16),I(0));s.check(0x00df,[V(var)],foot);s.go(skip)","s.label(need);a(6,V(16),I(0));s.go(foot)",'12 rider keeps clothes'),
 ('build_v25_ground.py',"s.get(19,b.BUSY);s.eq(19,1,'ACT_NOT_BUSY');s.go('ACTIVE')","s.go('ACT_NOT_BUSY')",'12 rope sits out swap'),
 ('build_v25_squad.py',"s.eq(19,16,'STATE_OK_16');s.get(19,b.SQ_ROPE);s.eq(19,1,'RELEASE')","s.eq(19,16,'STATE_OK_16');s.go('RELEASE')",'12 squad keeps ground team'),
 ('build_v25_ground.py',"a(6,V(2),I(106));a(6,V(3),I(107));s.eq(19,0,'GM_NOT_GROVE')","a(6,V(2),I(285));a(6,V(3),I(285));s.eq(19,0,'GM_NOT_GROVE')",'12 grove clothes'),
 # menu / i18n
 ('build_v25.py',"for model in [105,106,107,285,287]:a(0x0247,I(model))","pass",'12 model preload'),
 ('build_v25.py',"p.label('DO_EXIT_ROPE');p.set(EXIT_MODE,1)","p.label('DO_EXIT_ROPE');p.set(EXIT_MODE,0)",'12 exit rope row'),
 # third pass (facts checked against libGTASA): driver from the car, CREATE_CHAR height, drive-by aim ray
 ('build_v25_squad.py',"s.check(0x003b,[V(26),V(0)],'DRV_DONE');s.set(b.SQ_DRIVES,1)","s.set(b.SQ_DRIVES,1)",'12 driver is CJ'),
 ('build_v25_squad.py',"a(0x046c,V(6),V(26));s.check(0x003b,[V(26),V(0)],'DRV_DONE')","a(0x01ea,V(6),V(26));s.check(0x0431,[V(6),I(1)],'DRV_DONE')",'12 driver not guessed from seats'),
 ('build_v25_ground.py'," a(0x000b,V(12),F(-1.0))\n","",'12 re-skin height'),
 # beta 3: the Russian layout read off the player's screenshots
 ('i18n_v12.py',"out.append((0x80 if ch.isupper() else 0xA0)+i)","out.append((0x7F if ch.isupper() else 0x9F)+i)",'12 game layout base'),
 # second independent review: FOLLOW MY SHOTS
] 
# beta 4: one language rule, exit rows as switches, the command gate (an order twice, orders during rope work), guards never handed to the game, tap guards
M14=[
 ('msg_v42.py',"a(0x0dd8,V(17),I(GAME_RU_FLAG),I(1),I(1));s.eq(17,1,'RL_EN');s.set(LANG,1);s.ret()","a(0x0dd8,V(17),I(GAME_RU_FLAG),I(1),I(1));s.eq(17,1,'RL_EN');s.set(LANG,0);s.ret()",'14 Russian with the game'),
 ('msg_v42.py',"a(0x0dd8,V(17),I(GAME_RU_FLAG),I(1),I(1));s.eq(17,1,'RL_EN');s.set(LANG,1);s.ret()","s.set(LANG,1);s.ret()",'14 English in every other language'),
 ('msg_v42.py',"s.get(17,game_ok_key);s.eq(17,1,'RL_EN')","s.get(17,game_ok_key)",'14 unknown build English'),
 ('build_v25.py',"launch.eq(1,1,'MISSING_EN');a(0x03e5,S('UCOFF'))","a(0x03e5,S('UCOFF'))",'14 launcher language'),
 ('build_v25.py',"p.get(9,LANG);p.eq(9,0,k+'_RU')","a(6,V(9),I(0));p.eq(9,0,k+'_RU')",'14 menu language'),
 ('build_v25.py',"p.label('DO_EXIT_LAND');p.set(EXIT_MODE,0);say(p,'HCXBL');p.go('FORCE_REFRESH')","p.label('DO_EXIT_LAND');p.set(EXIT_MODE,0);p.set(CMD,15);p.go('FORCE_REFRESH')",'14 exit row is a switch'),
 ('build_v25.py',"p.label('DO_EXIT_ROPE');p.set(EXIT_MODE,1);say(p,'HCXBR');p.go('FORCE_REFRESH')","p.label('DO_EXIT_ROPE');p.set(EXIT_MODE,1);p.go('FORCE_REFRESH')",'14 exit row hint'),
 ('build_v25.py',"GATE_SAME=[(2,[2]),(3,[3]),(14,[24]),(7,[20,10,11])]","GATE_SAME=[(7,[20,10,11])]",'14 gate same mode'),
 ('build_v25.py',"GATE_SAME=[(2,[2]),(3,[3]),(14,[24]),(7,[20,10,11])]","GATE_SAME=[(2,[2]),(3,[3]),(14,[24])]",'14 gate same grove flight'),
 ('build_v25.py',"c.eq(19,1,'MAP_NEW');c.get(9,DEST_X);c.get(10,DEST_Y);a(0x0509,V(9),V(10),V(26),V(27),V(31));c.check(0x0021,[V(31),F(10)],'TICK')","c.go('MAP_NEW')",'14 same marker'),
 ('build_v25.py',"c.check(0x0021,[V(31),F(10)],'TICK')\nc.label('MAP_NEW')","c.go('TICK')\nc.label('MAP_NEW')",'14 moved marker'),
 ('build_v25.py',"for cmd in [16,17]:\n nxt='GATE_SQUAD_NOT_%d'%cmd","for cmd in []:\n nxt='GATE_SQUAD_NOT_%d'%cmd",'14 gate squad moving'),
 ('build_v25.py',"c.eq(8,10,'GATE_SQUAD_NOT_10');c.eq(17,1,'GATE_SQUAD_NOT_10');msg(c,'HCRBSY');c.go('GATE_DROP');c.label('GATE_SQUAD_NOT_10')","c.label('GATE_SQUAD_NOT_10')",'14 gate rope during squad move'),
 ('build_v25.py',"for cmd in GATE_ROPE_ORDERS:","for cmd in []:",'14 gate rope work'),
 ('build_v25.py',"GATE_ROPE_ORDERS=[2,3,4,7,10,11,14,15,16,17]","GATE_ROPE_ORDERS=[2,3,4,10,14,16,17]",'14 gate rope work aboard'),
 ('build_v25.py',"c.eq(8,10,'GATE_NOT_ROPE');c.eq(7,19,'GATE_NOT_ROPE');msg(c,'HCRCAN');a(6,V(8),I(2));c.label('GATE_NOT_ROPE')","c.label('GATE_NOT_ROPE')",'14 rope again cancels the approach'),
 ('build_v25.py',"c.eq(8,10,'GW_NOT_10');c.set(ROPE_COMMAND,1);c.go('GATE_DROP');c.label('GW_NOT_10')","c.label('GW_NOT_10')",'14 rope again cancels at the rope'),
 ('build_v25.py',"c.eq(8,17,'GW_NOT_17');c.eq(19,1,'GATE_DROP');c.set(ESCORT_CMD,2);c.go('GATE_DROP');c.label('GW_NOT_17')","c.label('GW_NOT_17')",'14 recall at the rope'),
 ('build_v25.py',"c.eq(8,16,'GW_NOT_16');c.eq(19,0,'GATE_DROP');c.set(ESCORT_CMD,1);c.go('GATE_DROP');c.label('GW_NOT_16')","c.label('GW_NOT_16')",'14 deploy at the rope'),
 ('build_v25.py',"for cmd in [2,4,14]:   # the helicopter is sent elsewhere","for cmd in []:   # the helicopter is sent elsewhere",'14 cover team back before the order'),
 ('build_v25.py',"c.eq(8,cmd,nxt);c.eq(19,0,'GATE_NO_WAIT');c.set(AFTER_ROPE,cmd)","c.eq(8,cmd,nxt);c.set(AFTER_ROPE,cmd)",'14 squad carries on at the rope'),
 ('build_v25.py',"for st in MAP_FLIGHT_STATES:\n nxt='GATE_EXIT_NOT_%d'%st","for st in []:\n nxt='GATE_EXIT_NOT_%d'%st",'14 exit once on the way'),
 ('build_v25.py',"c.eq(7,23,'GATE_EXIT_FLY');c.get(19,ROPE_PENDING);c.eq(19,0,'GATE_DROP');c.go('GATE_NOT_EXIT')","c.eq(7,23,'GATE_EXIT_FLY');c.go('GATE_NOT_EXIT')",'14 rope drop once'),
 ('build_v25.py',"c.set(AUTO_EXIT,0);c.set(ROPE_PENDING,0)   # a new destination","c.set(AUTO_EXIT,0)   # a new destination",'14 new destination ends retries'),
 ('build_v25_ground.py',"s.get(9,b.AFTER_ROPE);s.set(b.AFTER_ROPE,0);s.eq(9,0,'CL_AFTER')","a(6,V(9),I(0));s.set(b.AFTER_ROPE,0);s.eq(9,0,'CL_AFTER')",'14 order after the ropes'),
 ('build_v25_ground.py',"s.label(seen);a(0x0085,V(8),V(var));s.call('LEAVE_ADD')","s.label(seen);a(0x01c2,V(var))",'14 guard not handed to the game'),
 ('build_v25_ground.py',"s.label('LEAVE_ADD');a(0x048f,V(8))","s.label('LEAVE_ADD')",'14 leaver unarmed'),
 ('build_v25_ground.py',"s.label('LA_FOOT');a(0x05de,V(8))","s.label('LA_FOOT')",'14 leaver walks off'),
 ('build_v25_ground.py',"s.check(0x82cb,[V(8)],seen);a(0x009b,V(8));s.set(b.LEAVE+k,-1);s.go(nxt)","s.go(seen)",'14 leaver removed unseen'),
 ('build_v25_ground.py',"a(0x009b,V(9));s.label('LA_ROT_GONE_%d'%k);a(0xddc,I(b.LEAVE+k),V(8))","s.label('LA_ROT_GONE_%d'%k);a(0x01c2,V(8))",'14 ninth leaver'),
 ('build_v25_ground.py',"s.label('ACTIVE_RECALL');s.set(b.ROPE_WAIT,0);s.get(19,b.ESCORT_ON);s.eq(19,1,'ACTIVE_COVER_UP')","s.label('ACTIVE_RECALL');s.set(b.ROPE_WAIT,0);s.get(19,b.ESCORT_ON);s.eq(19,1,'CLEANUP')",'14 cover team climbs back'),
 ('build_v25_ground.py',"s.get(19,b.ESCORT_ON);s.eq(19,1,'CLEANUP');s.go('ACTIVE_TO_ESCORT')\n# the pickup ended by itself","s.go('CLEANUP')\n# the pickup ended by itself",'14 squad stays when the helicopter leaves'),
 ('build_v25_ground.py',"s.label('ACTIVE_LEFT');s.set(b.ROPE_COMMAND,0);s.set(b.ESCORT_CMD,0);","s.label('ACTIVE_LEFT');",'14 a waiting cancel ends with the pickup'),
 ('build_v25_ground.py',"a(6,V(15),I(0));a(6,V(16),I(0));a(0x01bd,V(19));s.check(0x001d,[V(19),V(27)],'ACT_ORDERS_DONE')","a(6,V(15),I(0));a(6,V(16),I(0));a(0x01bd,V(19))",'14 cancel waits for the landing'),
 ('build_v25_ground.py',"s.eq(15,1,'CONTINUE');say(s,'HCRCAN');s.go('ACTIVE_RECALL')","s.go('CONTINUE')",'14 cancel is carried out'),
 ('build_v25_ground.py',"s.eq(16,2,'ACT_NOT_UP');s.eq(9,1,'ACT_NOT_UP');say(s,'HCRUP');s.set(b.ROPE_WAIT,0);s.go('ACTIVE_COVER_UP');s.label('ACT_NOT_UP')","s.label('ACT_NOT_UP')",'14 squad up the hanging ropes'),
 ('build_v25_ground.py',"s.eq(16,1,'ACT_NOT_STAY');s.eq(9,0,'ACT_NOT_STAY');s.go('ACTIVE_STAY');s.label('ACT_NOT_STAY')","s.label('ACT_NOT_STAY')",'14 cover team becomes the squad'),
 ('build_v25_ground.py',"s.set(b.ESCORT_ON,2);s.set(b.ROPE_BUSY,1);s.go('PICKUP_VALIDATE')","s.set(b.ESCORT_ON,2);s.go('PICKUP_VALIDATE')",'14 busy from the order'),
 ('build_v25_ground.py',"s.label('ESCORT_NO_EXTRACT');s.set(b.ESCORT_CMD,0);","s.label('ESCORT_NO_EXTRACT');",'14 stale squad order'),
 ('build_v25_ground.py',"s.check(0x0019,[V(16),I(90000)],'ACTIVE_FRESH');say(s,'RGLATE');s.go('ACTIVE_RECALL')","s.check(0x0019,[V(16),I(90000)],'ACTIVE_FRESH');say(s,'RGLATE');s.go('CLEANUP')",'14 timeout brings the team back'),
 ('build_v25.py',"p.check(0x0019,[V(27),I(MENU_GUARD_MS)],'CHECK_MENU_STATUS');p.eq(28,0,'CHECK_MENU_STATUS')","p.eq(28,0,'CHECK_MENU_STATUS')",'14 tap guard'),
 ('build_v25.py',"p.check(0x8019,[V(27),I(MENU_REPEAT_MS)],'HP_GUARD');a(6,V(28),I(1));p.go('HP_GUARD')","p.go('HP_GUARD')",'14 hammered row'),
 ('build_v25.py',"a(0x0085,V(27),V(18));a(0x0062,V(27),V(26));a(0x0085,V(26),V(18));p.check(0x8019","a(0x0085,V(27),V(18));a(0x0062,V(27),V(26));p.check(0x8019",'14 ignored taps count'),
 ('build_v25.py',"# beta 4: nothing is taken while what is drawn is out of date (the page is redrawn first)\np.call('MAIN_KEY');p.check(0x003b,[V(6),V(3)],'CHECK_MENU_STATUS')\n","",'14 stale page'),
 ('build_v25.py',"p.label('TT_NOT_DEPLOY');p.eq(12,1,'FORCE_REFRESH');p.go('DO_TEAM_RECALL')","p.label('TT_NOT_DEPLOY');p.eq(12,1,'DO_TEAM_DEPLOY');p.go('DO_TEAM_RECALL')",'14 progress row is no button'),
 ('build_v25.py',"Tx(('TEAM_ON','TEAM_OFF','TEAM_DOWN','TEAM_UP')[team],prof)","Tx(('TEAM_ON','TEAM_OFF','TEAM_ON','TEAM_OFF')[team],prof)",'14 squad progress rows'),
 ('build_v25.py',"Tx('ROPE_CANCEL' if rope else 'ROPE',prof)","Tx('ROPE',prof)",'14 cancel row'),
 ('build_v25.py',"Tx('HOLD',prof,st==3 and not rope)","Tx('HOLD',prof,st==3)",'14 rope hover is not HOLD'),
 ('build_v25.py',"Tx({1:'WAIT_IN',4:'WAIT_OUT',13:'WAIT_OUT'}.get(st,'WAIT_SWAP'),prof)","Tx('WAIT_SWAP',prof)",'14 inbound / leaving rows'),
 ('build_v25.py',"p.label('DT_FREE');p.call('DT_PHASE');p.eq(22,0,'DT_SQUAD');p.go('DT_GO')","p.label('DT_FREE');p.go('DT_GO')",'14 dismiss recalls first'),
 ('build_v25.py',"p.get(21,ROPE_BUSY);p.eq(21,1,'DT_FREE');p.ret()","p.go('DT_FREE')",'14 dismiss waits for ropes'),
 ('build_v25.py',"p.label('DT_SQUAD');p.eq(22,1,'DT_RET')","p.label('DT_SQUAD')",'14 dismiss waits for a moving squad'),
 ('build_v25.py',"p.check(0x0019,[V(21),I(45000)],'DT_ASK');p.go('DT_GO')","p.check(0x0019,[V(21),I(45000000)],'DT_ASK');p.go('DT_GO')",'14 dismiss timeout'),
 ('build_v25.py',"a(0x0085,V(21),V(20));a(0x000a,V(21),I(6000));a(0xddc,I(DISMISS_NEXT),V(21))","a(0x0085,V(21),V(20));a(0x000a,V(21),I(6000000));a(0xddc,I(DISMISS_NEXT),V(21))",'14 dismiss asks again'),
 ('build_v25.py',"p.label('DT_ASK');p.get(21,DISMISS_NEXT);p.check(0x001d,[V(20),V(21)],'DT_RET')","p.label('DT_ASK')",'14 dismiss does not spam the recall'),
 ('build_v25.py'," if cmd!=17:p.set(DISMISS_T,0)"," if False:p.set(DISMISS_T,0)",'14 another order withdraws the dismissal'),
 ('build_v25.py',"p.label('DDA_SQUAD');say(p,'HCDSQ')","p.label('DDA_SQUAD')",'14 dismiss says why it waits'),
 ('build_v25.py',"p.call('DT_PHASE');p.eq(22,0,'DRAW_6_TEAM');draw('DISMISS_MENU',2)","p.go('DRAW_6_TEAM');draw('DISMISS_MENU',2)",'14 dismiss page by squad'),
]
B='build_v25.py'
M15=[   # beta 5: the menu opens at once
 (B,"launch.check(0x8019,[V(2),I(PANEL_FRESH_MS)],'PANEL_SLOW');","",'15 launcher: an old stamp is no proof'),
 (B,"launch.check(0x0019,[V(2),I(-1)],'PANEL_SLOW')","a(0)",'15 launcher: a stamp from the future is no proof'),
 (B,"launch.eq(1,0,'PANEL_SEEN');launch.go('PANEL_SLOW')","launch.go('PANEL_SEEN')",'15 launcher: no stamp at all'),
 (B,"launch.label('ENTRY');a(0);","launch.label('ENTRY');a(0);a(1,I(400));",'15 launcher: no fixed pause'),
 (B,"launch.check(0x003b,[V(2),V(1)],'PANEL_OK');","",'15 launcher: old stamp but alive'),
 (B,"launch.check(0x001d,[V(2),V(3)],'PANEL_SLOW_LOOP')","launch.go('PANEL_SLOW_LOOP')",'15 launcher: gives up'),
 (B,"PANEL_PROOF_MS=650","PANEL_PROOF_MS=6500",'15 launcher: gives up in time'),
 (B,"p.check(0x8019,[V(14),I(CORE_FRESH_MS)],'CORE_SLOW');","",'15 panel: an old core stamp is no proof'),
 (B,"p.check(0x0019,[V(14),I(-1)],'CORE_SLOW')","a(0)",'15 panel: a core stamp from the future is no proof'),
 (B,"p.eq(13,0,'CORE_SEEN');p.go('CORE_SLOW')","p.go('CORE_SEEN')",'15 panel: no core stamp at all'),
 (B,"p.label('CORE_SEEN');","p.label('CORE_SEEN');a(1,I(250));",'15 panel: no fixed pause'),
 (B,"p.check(0x003b,[V(14),V(13)],'CORE_OK');","",'15 panel: old core stamp but alive'),
 (B,"CORE_PROOF_MS=250","CORE_PROOF_MS=2500",'15 panel: OFFLINE in time'),
 (B,"p.label('WATCH');a(1,I(0));","p.label('WATCH');a(1,I(50));",'15 panel: watches every frame'),
 (B,"p.label('MENU_POLL');a(1,I(0));","p.label('MENU_POLL');a(1,I(50));",'15 panel: taps read every frame'),
 (B," p.set(CMD,cmd)   # beta 5"," p.set(CMD,cmd);a(1,I(200))   # beta 5",'15 panel: no pause after a tap'),
 (B,"c.get(19,CMD);c.eq(19,0,'NAP_END');","",'15 core: an order ends the nap'),
 (B,"a(0x000a,V(19),I(100));a(0xddc,I(NAP_UNTIL),V(19))","a(0xddc,I(NAP_UNTIL),V(19))",'15 core: the nap is 100 ms'),
 (B,"c.check(0x801d,[V(17),V(19)],'NAP_LOOP')","c.check(0x001d,[V(19),V(17)],'NAP_LOOP')",'15 core: the nap ends on time'),
 (B,"c.label('IDLE');c.call('NAP')","c.label('IDLE');a(1,I(100))",'15 core: idle nap'),
 (B,"c.label('TICK_NORMAL_WAIT');c.call('NAP')","c.label('TICK_NORMAL_WAIT');a(1,I(100))",'15 core: flight nap'),
]
G='build_v25_ground.py';Q='build_v25_squad.py';MS='msg_v42.py'
M16=[   # beta 6: threats only, fire discipline, CJ's safety, notifications as a drawn line, brave crew, kneeling gunners
 (B,"a(0x0227,V(15),V(30));f.check(0x8019,[V(30),I(BURN_HP-1)],nxt)","a(0x0227,V(15),V(30))",'16 burning: only a burning car'),
 (B,"f.check(0x8119,[V(15)],nxt);","",'16 burning: not a wreck'),
 (B,"a(0x000a,V(31),I(4000));a(0xddc,I(BURN_SAID),V(31))","a(0xddc,I(BURN_SAID),V(31))",'16 burning: every 4 s'),
 (B,"BURN_WARN_M=12.0","BURN_WARN_M=80.0",'16 burning: near CJ only'),
 (MS,"s.get(t1,BANNER_ARMED);s.eq(t1,0,P+'DRAW');s.set(BANNER_ARMED,1);s.ret()","s.go(P+'DRAW')",'16 line: first frame only arms'),
 (MS,"s.check(0x001d,[V(t2),V(t1)],P+'OFF');a(0x03f0,I(1))","s.check(0x001d,[V(t2),V(t1)],P+'OFF')",'16 line: wipe every frame'),
 (MS,"s.check(0x001d,[V(t2),V(t1)],P+'OFF');a(0x03f0,I(1))","a(0x03f0,I(1))",'16 line: ends on time'),
 (MS,"s.get(t2,MSG_ID);s.get(t1,LANG);s.eq(t1,0,P+'RU')","s.get(t2,MSG_ID);s.get(t1,LANG)",'16 line: language'),
 (MS,"for b0 in range(0,len(KEYS),16):s.check(0x0019,[V(t2),I(b0+15)],P+'%s_B%d'%(lang,b0))","for b0 in range(0,len(KEYS),16):s.check(0x0019,[V(t2),I(b0+14)],P+'%s_B%d'%(lang,b0))",'16 line: dispatch'),
 (MS,"MIN_SHOW_MS=1200","MIN_SHOW_MS=0",'16 say: readable first'),
 (MS,"s.check(0x8019,[V(18),I(1)],skip)","s.check(0x8019,[V(18),I(3)],skip)",'16 say: one level at most'),
 (MS,"ack=level is None and key in ORDER_ACK","ack=False",'16 say: an acknowledgement takes the line'),
 (MS,"s.set(MSG_PRIO,p+1 if ack else p)","s.set(MSG_PRIO,p)",'16 say: an acknowledgement yields to alarms only'),
 (MS,"a(0x000a,V(19),I(SHOW_MS[p]));a(0xddc,I(MSG_UNTIL),V(19))","a(0x000a,V(19),I(SHOW_MS[p]+900));a(0xddc,I(MSG_UNTIL),V(19))",'16 say: lasts its time'),
 (B,"brave(c,v,'BRAVE_CREW_%d'%v)","a(0)",'16 brave: gunners'),
 (B,";brave(c,4,'BRAVE_PILOT')","",'16 brave: pilot'),
 (B,"brave(c,29,'BRAVE_NEW_%d'%var);","",'16 brave: new crew'),
 (G,"b.brave(s,7,'GSETUP_BRAVE');","",'16 brave: squad'),
 (B,"s.check(0x09f2,[I(EMPTY_DM)],P+'_NO_DM');","",'16 brave: only when the decision maker exists'),
 (Q,"s.label(P+'RELOAD_ISSUE');a(0x04eb,V(G),I(1))","s.label(P+'RELOAD_ISSUE');a(0x05c5,V(G),I(1500))",'16 reload drill: weapon crouch'),
 (B,"c.get(11,POSE);c.eq(11,1,'ATTACH_END_'+str(var));a(0x04eb,V(var),I(1))","c.get(11,POSE);c.eq(11,1,'ATTACH_END_'+str(var))",'16 pose: kneel when mounted'),
 (B,"c.get(11,POSE);c.eq(11,1,'ATTACH_END_'+str(var));a(0x04eb,V(var),I(1))","a(0x04eb,V(var),I(1))",'16 pose: the setting is obeyed'),
 (B,"c.call('CHANGE_CREW');c.call('CHANGE_POSE');","c.call('CHANGE_CREW');",'16 pose: the switch acts at once'),
 (B,"a(0xddc,I(POSE_DONE),V(19));c.call('REATTACH_TEAM')","c.call('REATTACH_TEAM')",'16 pose: re-mounted once'),
 (B,"f.check(0x0a32,[V(var)],P);a(0x04eb,V(var),I(1));f.label(P)","f.label(P)",'16 pose: back on one knee after a fight'),
]
# ---- 1.3: the brain gives the orders (B = build_v25.py, Q = build_v25_squad.py)
M17=[
 (B,"c.label('LOAD');c.get(19,BRAIN_HELLO);c.check(0x0039,[V(19),I(BRAIN_MAGIC)],'NO_BRAIN');c.go('LOAD_GO')","c.label('LOAD');c.go('LOAD_GO')",'17 no brain: the helicopter is not called'),
 (B,"c.label('NO_BRAIN');msg(c,'HCNOBR');c.go('IDLE')","c.label('NO_BRAIN');c.go('IDLE')",'17 no brain: the player is told why'),
 (B,"f.label('BRAIN');f.get(30,BRAIN_HELLO);f.check(0x0039,[V(30),I(BRAIN_MAGIC)],'NO_BRAIN')","f.label('BRAIN')",'17 fire: no opcode before the handshake'),
 (Q,"s.label('BF_GO');s.get(26,b.BRAIN_HELLO);s.check(0x0039,[V(26),I(b.BRAIN_MAGIC)],'BF_NONE')","s.label('BF_GO')",'17 squad frame: no opcode before the handshake'),
 (Q,"s.label('PERCEIVE');s.get(19,b.BRAIN_HELLO);s.check(0x0039,[V(19),I(b.BRAIN_MAGIC)],'PV_NONE')","s.label('PERCEIVE')",'17 squad picture: no opcode before the handshake'),
 (B,"f.eq(9,2,nofire);a(0x06bc,V(11),V(12),V(13),V(14),V(15),V(16),I(ROUND_DAMAGE));f.label(nofire)","a(0x06bc,V(11),V(12),V(13),V(14),V(15),V(16),I(ROUND_DAMAGE));f.label(nofire)",'17 gunner: a round only on the brain\'s word'),
 (B,"f.eq(9,2,nofire);a(0x06bc,V(11),V(12),V(13),V(14),V(15),V(16),I(ROUND_DAMAGE));f.label(nofire)","f.label(nofire)",'17 gunner: the round is fired'),
 (B,"a(0x06bc,V(11),V(12),V(13),V(14),V(15),V(16),I(ROUND_DAMAGE))","a(0x06bc,V(11),V(12),V(13),V(14),V(15),V(13),I(ROUND_DAMAGE))",'17 gunner: the round flies the checked line'),
 (B,"alive(f,var,skip);f.check(0x0a32,[V(var)],skip);a(0x0085,V(8),V(var));a(0x0e48,V(8),I(9),I(1))","alive(f,var,skip);a(0x0085,V(8),V(var));a(0x0e48,V(8),I(9),I(1))",'17 gunner: a crewman on foot makes no rounds'),
 (B,"a(0x0667,V(var),V(17),V(18),V(19),I(1500));a(0xddc,I(G_AIM+g),V(10))","a(0x074d,V(var),V(10),I(1500));a(0xddc,I(G_AIM+g),V(10))",'17 gunner: he aims, the game\'s weapon never fires'),
 (B,"a(0x0667,V(var),V(17),V(18),V(19),I(1500));a(0xddc,I(G_AIM+g),V(10))","a(0xddc,I(G_AIM+g),V(10))",'17 gunner: weapon on the man'),
 (B,"a(0x000a,V(31),I(700));a(0xddc,I(G_AIM_T+g),V(31))","a(0x000a,V(31),I(700000));a(0xddc,I(G_AIM_T+g),V(31))",'17 gunner: the aim follows a moving man'),
 (B,"rest(var,'REST2_'+str(var));f.set(G_AIM+g,-1)","f.set(G_AIM+g,-1)",'17 gunner: weapon down when the brain says rest'),
 (B,"for typ in range(32):a(0x077a,V(var),I(2),I(typ))","for typ in range(0):a(0x077a,V(var),I(2),I(typ))",'17 gunner: hates nobody'),
 (B,"a(0xddc,I(BR_KILLS),V(11));f.get(31,KILLS);a(0x000a,V(31),I(1));a(0xddc,I(KILLS),V(31))","a(0xddc,I(BR_KILLS),V(11));f.get(31,KILLS)",'17 kills are counted from the brain'),
 (B,"f.eq(30,-1,'KILL_KNOWN');a(0xddc,I(BR_KILLS),V(11));f.go('KILL_DONE')","f.eq(30,-1,'KILL_KNOWN');a(0xddc,I(BR_KILLS),I(0));f.go('KILL_DONE')",'17 kills: the brain\'s old count is not a new kill'),
 (B,"a(0x01bd,V(31));a(0x0062,V(31),V(16));a(0xddc,I(HELI_SHOT_T),V(31));f.label('HELI_SHOT_DONE')","f.label('HELI_SHOT_DONE')",'17 fire at the helicopter reaches the pilot'),
 (B,"f.check(0x0019,[V(12),I(0)],'TOP_SET');a(0x0085,V(30),V(12))","f.check(0x0019,[V(12),I(0)],'TOP_SET')",'17 the pilot is told the most dangerous man'),
 (B,"a(6,V(30),I(-1));f.eq(25,0,'TOP_FIRE_ALLOWED');f.go('TOP_SET');f.label('TOP_FIRE_ALLOWED')","a(6,V(30),I(-1))",'17 hold fire: no fight for the pilot either'),
 (B,"f.set(ENGAGED,1);f.get(30,SQ_GROUP);f.eq(30,0,'CONTACT_DONE');msg(f,'HCCONT')","f.set(ENGAGED,1);f.get(30,SQ_GROUP);f.eq(30,0,'CONTACT_DONE')",'17 contact is called'),
 (B,"f.set(ENGAGED,0);f.set(CLEAR_AT,0);f.get(30,SQ_GROUP);f.eq(30,0,'CONTACT_DONE');msg(f,'HCCLEAR')","f.set(ENGAGED,0);f.set(CLEAR_AT,0);f.get(30,SQ_GROUP);f.eq(30,0,'CONTACT_DONE')",'17 area clear is called'),
 (B,"f.eq(30,0,'CLEAR_TIMED');a(0x000a,V(31),I(3000));a(0xddc,I(CLEAR_AT),V(31))","f.eq(30,0,'CLEAR_TIMED');a(0x000a,V(31),I(0));a(0xddc,I(CLEAR_AT),V(31))",'17 area clear: after 3 s of quiet'),
 (B,"f.label('CONTACT_NO');f.check(0x8019,[V(9),I(0)],'CONTACT_DONE');","f.label('CONTACT_NO');",'17 area clear: not while a threat is left'),
 (B,"for m in (0,2,3,4):\n nxt='MODE_REPORT_NOT_'+str(m)","for m in ():\n nxt='MODE_REPORT_NOT_'+str(m)",'17 the fire rule is confirmed'),
 (Q,"a(0x0085,V(26),V(G));a(0x0e48,V(26),I(3),I(2));a(0xddc,I(b.SQ_BR_ST+k),V(27));a(0xddc,I(b.SQ_BR_TG+k),V(28))","a(0x0085,V(26),V(G));a(0x0e48,V(26),I(3),I(2));a(0xddc,I(b.SQ_BR_ST+k),I(2));a(0xddc,I(b.SQ_BR_TG+k),V(28))",'17 squad: fire only on the brain\'s word'),
 (Q,"s.eq(27,3,nxt);s.get(29,fk(k,'TASK'))","s.go(nxt);s.get(29,fk(k,'TASK'))",'17 squad: cease fire in the same frame'),
 (Q,"s.get(31,b.SQ_BR_ST+k);s.check(0x0039,[V(31),I(2)],no)","s.get(31,b.SQ_BR_ST+k)",'17 squad: no firing task without leave'),
 (Q,"a(0x0085,V(19),V(12));a(0x0062,V(19),V(29));a(0xddc,I(b.CJ_AIM_T),V(19))","a(0x0085,V(19),V(12));a(0x0062,V(19),V(29))",'17 squad: CJ\'s line of fire from the brain'),
 (Q,"s.check(0x0019,[V(19),I(1)],nx);s.get(13+k,b.SQ_BR_TG+k)","s.check(0x0019,[V(19),I(1)],nx)",'17 squad: each guard has the man the brain gave him'),
 (Q,"s.check(0x0019,[V(19),I(1)],nx);s.get(13+k,b.SQ_BR_TG+k)","s.check(0x0019,[V(19),I(0)],nx);s.get(13+k,b.SQ_BR_TG+k)",'17 squad: a covered suspect is not a man to fight'),
 (Q,"s.check(0x801d,[V(19),V(12)],'LOOP')","s.check(0x001d,[V(12),V(19)],'LOOP')",'17 squad: the full pass ten times a second'),
 ('brain_mock.py',"for k in range(18):","for k in range(10):",'17 let-go guards are ours for the brain'),
 (B,"f.label('NO_HELI');f.set(FIRE_ACTIVE,0);f.set(FIRE_TARGET,-1);f.set(ENGAGED,0);f.set(CLEAR_AT,0);f.go('WAIT')","f.label('NO_HELI');f.go('WAIT')",'17 no helicopter: the fight is over for the gunners'),
]
if sys.argv[1:2]==['--new']:
 M=M12+M14+M15+M16+M17;sys.argv.pop(1)
elif sys.argv[1:2]==['--b7']:
 M=M17;sys.argv.pop(1)
elif sys.argv[1:2]==['--b6']:
 M=M16;sys.argv.pop(1)
elif sys.argv[1:2]==['--b5']:
 M=M15;sys.argv.pop(1)
elif sys.argv[1:2]==['--b4']:
 M=M14;sys.argv.pop(1)
elif sys.argv[1:2]==['--12']:
 M=M12;sys.argv.pop(1)
elif sys.argv[1:2]==['--old']:
 sys.argv.pop(1)
else:M=M+M12+M14+M15+M16+M17
if os.environ.get('HC_MUT_SHARD'):   # 'i/n': every n-th mutant starting with the i-th (several runs side by side, each with its own HC_MUT_ROOT)
 i_,n_=map(int,os.environ['HC_MUT_SHARD'].split('/'));M=M[i_::n_]
only=sys.argv[1:]
for fname,old,new,name in M:
 if only and name not in only:continue
 if ROOT.exists():shutil.rmtree(ROOT)
 (ROOT/'install').mkdir(parents=True);(ROOT/'sources').mkdir();shutil.copytree(SRC,ROOT/'builder',ignore=shutil.ignore_patterns('__pycache__'))
 os.symlink(SRC.parent/'brain',ROOT/'brain')   # the scripts are tested against the real core (brain_mock.py)
 p=ROOT/'builder'/fname;t=p.read_text() if p.exists() else ''
 if t.count(old)<1:print('GONE    '+name+'  (the code this mutant broke no longer exists)',flush=True);continue
 p.write_text(t.replace(old,new))
 env=dict(os.environ);env.pop('HC_OUT',None)
 r=subprocess.run([sys.executable,'build_all.py'],cwd=ROOT/'builder',capture_output=True,text=True,env=env)
 if r.returncode:print('BUILD FAIL',name,r.stderr[-300:]);continue
 rc=0
 for tf in ('test_v25.py','test_v40_squad.py','test_v12_realism.py','test_v12_i18n.py'):   # the quick ones first: most mutants are caught there
  r=subprocess.run([sys.executable,tf],cwd=ROOT/'builder',capture_output=True,text=True,env=env)
  if r.returncode:rc=1;break
 print(('CAUGHT  ' if rc else 'MISSED  ')+name+('' if rc else '  <<<<<<'),flush=True)
