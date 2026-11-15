"""Mutation check: break one rule at a time in a scratch copy of builder/ and make sure the tests notice.
   python3 tools/mutate.py            all mutants      python3 tools/mutate.py --new     only the 1.2 ones      (names as arguments pick single mutants)
   A line 'MISSED ... <<<<<<' means a rule has no test that guards it."""
import shutil,subprocess,sys,os,tempfile
from pathlib import Path
SRC=Path(__file__).resolve().parent.parent;ROOT=Path(tempfile.gettempdir())/'helicover_mut'
M=[
 ('threat_v41.py',"s.check(0x8019,[V(t2),I(SHOOTER_FRESH_MS)],P+'NOT_SHOOTER');a(0x000a,V(out),I(100))","s.check(0x8019,[V(t2),I(SHOOTER_FRESH_MS)],P+'NOT_SHOOTER');a(0x000a,V(out),I(0))",'shooter +100'),
 ('threat_v41.py',"s.check(0x0023,[F(4),V(d)],heli_k)","s.check(0x0023,[F(0.01),V(d)],heli_k)",'trace end at CJ'),
 ('threat_v41.py',"a(0x000a,V(n),I(1))","a(0x000a,V(n),I(0))",'heli hit count'),
 ('threat_v41.py',"s.check(0x0021,[V(t1),F(-30)],P+'RET');a(0x000a,V(out),I(50))","s.check(0x0021,[V(t1),F(-30)],P+'RET');a(0x000a,V(out),I(0))",'car +50'),
 ('threat_v41.py',"a(0x000a,V(out),I(-40))","a(0x000a,V(out),I(0))",'cop -40'),
 ('threat_v41.py',"s.check(0x0021,[V(t1),F(6)],P+'NOT_ROOF');a(0x000a,V(out),I(15))","s.check(0x0021,[V(t1),F(6)],P+'NOT_ROOF');a(0x000a,V(out),I(0))",'roof +15 score'),
 ('threat_v41.py',"s.label(P+'W_SNIPER');a(0x000a,V(out),I(35))","s.label(P+'W_SNIPER');a(0x000a,V(out),I(0))",'sniper weight'),
 ('build_v25.py',"f.check(0x0019,[V(22),I(1)],P+'ROOM')","f.check(0x0019,[V(22),I(0)],P+'ROOM')",'focus two gunners'),
 ('build_v25.py',"f.eq(30,1,'SG_PRIMARY_%d'%guard);f.set(GT_SUPP+g,1)","f.eq(30,1,'SG_PRIMARY_%d'%guard);f.set(GT_SUPP+g,0)",'suppression flag'),
 ('build_v25.py',"f.check(0x8019,[V(31),I(4000)],fail)","f.check(0x8019,[V(31),I(400000)],fail)",'suppression 4 s'),
 ('build_v25.py',"f.get(12,SUP_Y+var-3)","f.get(31,SUP_Y+var-3)",'suppression aim'),
 ('build_v25.py',"f.check(0x001d,[V(30),V(31)],'GSI_NEXT_%d'%gp)","f.check(0x001d,[V(31),V(30)],'GSI_NEXT_%d'%gp)",'sorted insert'),
 ('build_v25.py',"msg(c,'HCSHOT')","pass",'evade on shots'),
 ('build_v25.py',"c.check(0x0019,[V(8),I(0)],'ORBIT_DIR_SET')","c.check(0x0019,[V(8),I(100)],'ORBIT_DIR_SET')",'orbit door'),
 ('build_v25.py',"c.check(0x0021,[V(8),F(6)],'TRACK_POS');a(0x000b,V(11),F(15))","c.check(0x0021,[V(8),F(6)],'TRACK_POS');a(0x000b,V(11),F(0))",'roof orbit'),
 ('build_v25_squad.py',"keep=uid('SORT_KEEP');s.check(0x001d,[V(SREG[j]),V(SREG[i])],keep)","keep=uid('SORT_KEEP');s.go(keep)",'squad sort'),
 ('build_v25_squad.py',"for key in [b.TB_SHOOTER,b.FIRE_TARGET]","for key in [b.FIRE_TARGET]",'squad considers shooter'),
 ('build_v25_squad.py',"s.go('CL_ACCEPT');s.label('CL_NOT_SHOOTER')","s.go('CL_NOT_SHOOTER');s.label('CL_NOT_SHOOTER')",'classify shooter'),
 ('build_v25_squad.py',"else:msg('SQ'+'XSVR'[kind-1]+letter,throttle)","else:msg('SQC'+letter,throttle)",'typed call-outs'),
 ('build_v25_squad.py',"s.check(0x06bd,[V(19),V(20),V(29),V(26),V(27),V(30),I(1),I(1),I(0),I(1),I(0)],blk);s.go(nxt)","s.check(0x06bd,[V(19),V(20),V(29),V(26),V(27),V(30),I(1),I(1),I(0),I(1),I(0)],nxt);s.go(blk)",'cover chest'),
 ('build_v25_squad.py',"s.check(0x0019,[V(19),I(10000)],P+'NO_RELOAD')","s.check(0x0019,[V(19),I(1000000)],P+'NO_RELOAD')",'reload'),
 ('build_v25_squad.py',"a(0xddc,I(b.ENG_T+k),V(31))\n","a(0xddc,I(b.ENG_T+k),V(12))\n",'reload stagger'),
 ('build_v25_squad.py',"msg('SQEVAC',False)","s.add(0)",'evac'),
 ('build_v25_squad.py',"s.check(0x0019,[V(30),I(20000)],P+'ALERT')","s.check(0x0019,[V(30),I(2000000)],P+'ALERT')",'relax'),
 ('build_v25_squad.py',"s.check(0x0021,[V(18),F(6)],P+'SPD_GO');a(6,V(20),I(7))","s.check(0x0021,[V(18),F(6)],P+'SPD_GO');a(6,V(20),I(6))",'sprint'),
]
M+=[
 ('msg_v42.py',"s.get(18,MSG_PRIO);s.check(0x0019,[V(18),I(p)],show);s.go(skip)","s.go(show)",'dispatcher priority'),
 ('msg_v42.py',"s.get(18,HUD);s.check(0x0019,[V(18),I(LEVEL_IMPORTANT if p==CHATTER else LEVEL_OFF)],skip)","pass",'dispatcher level'),
 ('msg_v42.py',"s.get(18,MSG_UNTIL);s.check(0x001d,[V(18),V(19)],show)","s.go(show)",'dispatcher hold time'),
 ('build_v25.py',"p.get(19,NOTICE_SKIP);p.check(0x003b,[V(8),V(19)],'NOTICE_SAY')","p.go('NOTICE_SAY')",'notice skip'),
 ('build_v25.py',"for pend,key in [(1,'HCRTEAM'),(2,'HCRBACK')]:","for pend,key in []:",'rope notice variants'),
 ('build_v25.py',"c.set(HELLO_AT,-1);","c.set(HELLO_AT,0);",'hello once'),
 ('build_v25.py',"squad_owns(f,'SOLO_HCCONT',30,31)","pass",'contact de-dup'),
 ('build_v25.py'," if var in (3,5):a(0x0407,V(22),F(0),F(1.8),F(.3),V(11),V(12),V(13))"," pass",'engine shots'),
 ('build_v25.py',"f.check(0x0457,[I(0),V(29)],nxt);f.call('GUNNER_FOCUS_%d'%guard)","f.check(0x0457,[I(0),V(29)],nxt);f.go(nxt);f.call('GUNNER_FOCUS_%d'%guard)",'CJ aim focus'),
 ('build_v25.py',"f.check(0x8019,[V(31),I(5000)],P+'YIELD')","f.check(0x8019,[V(31),I(500000)],P+'YIELD')",'yield after 5 s'),
 ('build_v25.py',"a(0x0013,V(26),F(.3));","a(0x0013,V(26),F(0));",'orbit centre shift'),
 ('build_v25_squad.py',"a(0x0668,V(G),V(26),V(27),V(28),I(1500));order(k,17,25,1500)","pass",'ground suppression'),
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
 ('msg_v42.py',"a(0x0dd8,V(17),I(GAME_RU_FLAG),I(1),I(1));s.eq(17,1,'RL_DONE');s.set(LANG,2);s.ret()","a(0x0dd8,V(17),I(GAME_RU_FLAG),I(1),I(1));s.eq(17,1,'RL_DONE');s.set(LANG,0);s.ret()",'12 AUTO language'),
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
 ('threat_v41.py',"jgt(t4,1.0,P+'INCOMING');jlt(t4,-160.0,P+'HELI');jgt(t3,2.25,P+'HELI')","jgt(t4,1.0,P+'INCOMING');jlt(t4,-160.0,P+'HELI');jgt(t3,225.0,P+'HELI')",'12 CJ line distance'),
 ('threat_v41.py',"s.check(0x8019,[V(t6),I(350)],P+'HELI')","s.check(0x8019,[V(t6),I(35000)],P+'HELI')",'12 CJ shot window'),
 ('threat_v41.py',"s.label(P+'INCOMING');jgt(t4,220.0,P+'HELI');jgt(t3,4.0,P+'HELI')","s.label(P+'INCOMING');jgt(t4,220.0,P+'HELI');jgt(t3,400.0,P+'HELI')",'12 incoming line distance'),
 ('threat_v41.py',"jgt(t3,36.0,P+'NEXT');a(0x000a,V(n),I(1))","jgt(t3,3600.0,P+'NEXT');a(0x000a,V(n),I(1))",'12 helicopter hit distance'),
 ('threat_v41.py',"a(0x000b,V(t6),F(.3));s.check(0x8025,[V(t3),V(t6)],P+'HELI')","a(0x000b,V(t6),F(.3))",'12 friend takes the credit'),
 ('threat_v41.py',"s.get(t5,b.TB_SEARCH_T);a(0x01bd,V(t6));a(0x0062,V(t6),V(t5));s.check(0x0019,[V(t6),I(250)],P+'HELI')","s.get(t5,b.TB_SEARCH_T);a(0x01bd,V(t6));a(0x0062,V(t6),V(t5));s.check(0x0019,[V(t6),I(0)],P+'HELI')",'12 search throttle'),
 ('build_v25_squad.py',"for key in [b.TB_SHOOTER,b.FIRE_TARGET]","for key in [b.FIRE_TARGET]",'12 squad adopts traced shooter'),
 # independent review of 1.2: crew change vs rope, scripted exit, platform handle, shared aim, muster
 ('build_v25.py',"(the rope workers abort when the state is 17)\nc.get(17,ROPE_BUSY);c.eq(17,0,'SWAP_DEFER')\n","(the rope workers abort when the state is 17)\n",'12 crew change waits'),
 ('build_v25.py',"c.call('EXIT_UNFREEZE');a(0x01bd,V(21))","c.call('UNFREEZE');a(0x01bd,V(21))",'12 exit keeps cruise'),
 ('build_v25.py',"c.set(FROZEN,0);c.set(CR_V,0);c.ret()","c.set(FROZEN,0);c.ret()",'12 unfreeze clears speed'),
 ('build_v25_ground.py'," a(0x009a,I(8),V(mdl),V(10),V(11),V(12),V(8));s.check(0x056d,[V(8)],skip)\n a(0x0173,V(8),V(13));a(0x0085,V(7),V(8));s.call('GSETUP');a(0x0223,V(8),V(14));a(0x035f,V(8),V(9))\n s.check(0x0019,[V(4),I(0)],noarm2);a(0x01b2,V(8),V(4),I(30000));a(0x01b9,V(8),V(4));s.label(noarm2)\n a(0x009b,V(var));a(0x0085,V(var),V(8));"," a(0x009a,I(8),V(mdl),V(10),V(11),V(12),V(6));s.check(0x056d,[V(6)],skip)\n a(0x0173,V(6),V(13));a(0x0085,V(7),V(6));s.call('GSETUP');a(0x0223,V(6),V(14));a(0x035f,V(6),V(9))\n s.check(0x0019,[V(4),I(0)],noarm2);a(0x01b2,V(6),V(4),I(30000));a(0x01b9,V(6),V(4));s.label(noarm2)\n a(0x009b,V(var));a(0x0085,V(var),V(6));",'12 decor keeps platform handle'),
 ('build_v25.py',"f.label('PRECISE_M2_'+str(var));f.get(11,PB_AIM);f.get(12,PB_AIM+1);f.get(13,PB_AIM+2);f.label('PRECISE_MODE_DONE_'+str(var))","f.label('PRECISE_M2_'+str(var));f.label('PRECISE_MODE_DONE_'+str(var))",'12 shared aim reload'),
 ('build_v25.py',"[(13,4,2,1),(14,-4,2,2),(15,4,-2,-1),(16,-4,-2,-1)]","[(13,-4,2,1),(14,4,2,2),(15,-4,-2,-1),(16,4,-2,-1)]",'12 muster side'),
 ('build_v25.py',"a(0x0407,V(5),F(x),F(y),F(0),V(17),V(19),V(31));a(0x050a,V(9),V(10),V(11),V(17),V(19),V(31),V(29))","a(0x00aa,V(5),V(17),V(19),V(31));a(0x050a,V(9),V(10),V(11),V(17),V(19),V(31),V(29))",'12 muster point'),
 # E3 / E4
 ('build_v25_squad.py',"s.check(0x0019,[V(30),I(1500)],'AN_RET')","s.check(0x0019,[V(30),I(15)],'AN_RET')",'12 anchor 1.5 s'),
 ('build_v25_squad.py',"s.check(0x0021,[V(31),F(.5)],'AN_OFF')","s.check(0x0021,[V(31),F(-2)],'AN_OFF')",'12 anchor 60 deg'),
 ('build_v25_squad.py',"s.check(0x8019,[V(30),I(1200)],skip)","s.check(0x8019,[V(30),I(1200000)],skip)",'12 fire line stale'),
 ('build_v25_squad.py',"a(0x000b,V(31),F(2))\n  a(0x006b,V(31),V(20))","a(0x000b,V(31),F(0))\n  a(0x006b,V(31),V(20))",'12 fire line shift'),
 ('build_v25_squad.py',"leash(k,G,25,7);cover=","leash(k,G,40,7);cover=",'12 assault cap'),
 ('build_v25_squad.py'," if k==3:s.go(P+'BODYGUARD')"," if False:s.go(P+'BODYGUARD')",'12 medic stays'),
 ('build_v25.py',"a(0x0208,F(-1),F(1),V(21))","a(0x0208,F(0),F(0),V(21))",'12 dispersion'),
 # E5 decor
 ('build_v25_ground.py',"s.check(0x02f2,[V(var),V(mdl)],need);s.go(skip)","s.go(skip)",'12 team re-skin'),
 ('build_v25_ground.py',"a(0x01b2,V(var),V(4),I(30000));a(0x01b9,V(var),V(4));a(0x02e2,V(var),I(100));s.label(noarm)","s.label(noarm)",'12 team weapon'),
 ('build_v25_ground.py',"s.label(need);a(6,V(16),I(0));s.check(0x00df,[V(var)],foot);s.go(skip)","s.label(need);a(6,V(16),I(0));s.go(foot)",'12 rider keeps clothes'),
 ('build_v25_ground.py',"s.get(19,b.BUSY);s.eq(19,1,'ACT_NOT_BUSY');s.go('ACTIVE')","s.go('ACT_NOT_BUSY')",'12 rope sits out swap'),
 ('build_v25_squad.py',"s.eq(19,16,'STATE_OK_16');s.get(19,b.SQ_ROPE);s.eq(19,1,'RELEASE')","s.eq(19,16,'STATE_OK_16');s.go('RELEASE')",'12 squad keeps ground team'),
 ('build_v25_ground.py',"a(6,V(2),I(106));a(6,V(3),I(107));s.eq(19,0,'GM_NOT_GROVE')","a(6,V(2),I(285));a(6,V(3),I(285));s.eq(19,0,'GM_NOT_GROVE')",'12 grove clothes'),
 # menu / i18n
 ('build_v25.py',"p.get(9,LANG);p.eq(9,0,k+'_R1')","a(6,V(9),I(0));p.eq(9,0,k+'_R1')",'12 menu language'),
 ('build_v25.py',"p.get(9,ESCORT_ON);p.eq(9,1,'DO_DISMISS_NOW')","p.go('DO_DISMISS_NOW')",'12 dismiss recalls first'),
 ('build_v25.py',"p.check(0x0019,[V(21),I(45000)],'DT_RET')","p.check(0x0019,[V(21),I(45000000)],'DT_RET')",'12 dismiss timeout'),
 ('build_v25.py',"for model in [105,106,107,285,287,487,497,425]:a(0x0247,I(model))","pass",'12 model preload'),
 ('build_v25.py',"p.label('DO_EXIT_ROPE');p.set(EXIT_MODE,1)","p.label('DO_EXIT_ROPE');p.set(EXIT_MODE,0)",'12 exit rope row'),
 # second independent review: FOLLOW MY SHOTS
 ('threat_v41.py',"jgt(t1,100.0,P+'HELI');jlt(t1,-100.0,P+'HELI')","jgt(t1,1000.0,P+'HELI');jlt(t1,-1000.0,P+'HELI')",'12 aim direction check'),
 ('threat_v41.py',"jgt(t1,100.0,P+'HELI');jlt(t1,-100.0,P+'HELI')","jgt(t1,60.0,P+'HELI');jlt(t1,-60.0,P+'HELI')",'12 aim direction tight'),
 ('threat_v41.py',"jgt(t1,100.0,P+'HELI');jlt(t1,-100.0,P+'HELI')","jgt(t1,150.0,P+'HELI');jlt(t1,-150.0,P+'HELI')",'12 aim direction loose'),
 ('threat_v41.py'," s.check(0x80df,[V(cj)],P+'DIR_OK')\n"," pass\n",'12 aim direction in a car'),
 ('threat_v41.py',"s.check(0x0023,[F(-180),V(t1)],P+'D_LO');a(0x000b,V(t1),F(360));s.label(P+'D_LO')","s.label(P+'D_LO')",'12 aim direction seam low'),
 ('threat_v41.py',"s.check(0x0021,[V(t1),F(180)],P+'D_HI');a(0x000b,V(t1),F(-360));s.label(P+'D_HI')","s.label(P+'D_HI')",'12 aim direction seam high'),
 ('threat_v41.py',"s.label(P+'W_HEAVY');s.check(0x8019,[V(t1),I(38)],W)","s.label(P+'W_HEAVY');s.check(0x0019,[V(t1),I(38)],W)",'12 heavy weapon bonus'),
 ('build_v25.py',"a(0x0062,V(31),V(30));f.check(0x8019,[V(31),I(250)],'CJ_POLL_RET')","a(0x0062,V(31),V(30));f.check(0x0019,[V(31),I(250)],'CJ_POLL_RET')",'12 scan after a shot'),
 ('build_v25.py',"f.check(0x0019,[V(31),I(20)],'CJ_POLL_RET');f.call('TRACE_RUN')","f.check(0x0019,[V(31),I(200)],'CJ_POLL_RET');f.call('TRACE_RUN')",'12 scan every frame'),
 ('build_v25.py',"f.check(0x0019,[V(31),I(99)],'TRACE_TICK_RET');f.call('TRACE_RUN')","f.check(0x0019,[V(31),I(0)],'TRACE_TICK_RET');f.call('TRACE_RUN')",'12 scan tick 100 ms'),
 ('build_v25.py',"f.label('CJ_POLL');f.check(0x02e0,[V(0)],'CJ_POLL_IDLE')","f.label('CJ_POLL');f.get(30,GAME_OK);f.eq(30,1,'CJ_POLL_RET');f.check(0x02e0,[V(0)],'CJ_POLL_IDLE')",'12 stamp on every build'),
 ('build_v25.py',"f.call('FIND_CJ_AIMED');alive(f,29,'AIM_NO_LOCK');f.call('SHOOT_CHAR');f.go('WAIT')\nf.label('AIM_NO_LOCK');f.get(30,CJ_AIM_T);a(0x01bd,V(31));a(0x0062,V(31),V(30));f.check(0x0019,[V(31),I(900)],'AIM_LINE');f.go('AIM_RAY')","f.get(30,CJ_AIM_T);a(0x01bd,V(31));a(0x0062,V(31),V(30));f.check(0x0019,[V(31),I(900)],'AIM_LINE');f.go('AIM_NO_LOCK')\nf.label('AIM_NO_LOCK');f.call('FIND_CJ_AIMED');alive(f,29,'AIM_RAY');f.call('SHOOT_CHAR');f.go('WAIT')",'12 lock-on before line'),
]
if sys.argv[1:2]==['--new']:
 M=M12;sys.argv.pop(1)
else:M=M+M12
only=sys.argv[1:]
for fname,old,new,name in M:
 if only and name not in only:continue
 if ROOT.exists():shutil.rmtree(ROOT)
 (ROOT/'install').mkdir(parents=True);(ROOT/'sources').mkdir();shutil.copytree(SRC,ROOT/'builder',ignore=shutil.ignore_patterns('__pycache__'))
 p=ROOT/'builder'/fname;t=p.read_text()
 if t.count(old)<1:print('GONE    '+name+'  (the code this mutant broke no longer exists)',flush=True);continue
 p.write_text(t.replace(old,new))
 env=dict(os.environ);env.pop('HC_OUT',None)
 r=subprocess.run([sys.executable,'build_all.py'],cwd=ROOT/'builder',capture_output=True,text=True,env=env)
 if r.returncode:print('BUILD FAIL',name,r.stderr[-300:]);continue
 rc=0
 for tf in ('test_v12_realism.py','test_v12_i18n.py','test_v40_squad.py','test_v25.py'):
  r=subprocess.run([sys.executable,tf],cwd=ROOT/'builder',capture_output=True,text=True,env=env)
  if r.returncode:rc=1;break
 print(('CAUGHT  ' if rc else 'MISSED  ')+name+('' if rc else '  <<<<<<'),flush=True)
