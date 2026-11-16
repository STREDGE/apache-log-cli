# Tactics notes for Helicover 2.0 (Brain 1.0): what the two modes are built on

**Read this first - how far the reading really went.** The research for 2.0 was done by three search agents inside this work
session. The session's network opens GitHub pages only; every other site was reached through the search tool, which returns
short excerpts. So:

- **read in full (54 pages):** source code and headers on GitHub - `gta-reversed` (the decompiled PC game), `aml-psdk`
  (Android headers), `plugin-sdk`, reVC, AML, SAUtils. These decided HOW things are done in the game.
- **read as search excerpts only (about 145 pages, listed at the end):** close protection, infantry and police tactics, game
  AI talks. Nothing here was read as a whole document, and **no video was watched** (the tools cannot play one).
- A rule marked **source** was stated in at least one excerpt; a rule marked **assumption** is a number or a simplification
  chosen for the game (distances in GTA are short, a fight lasts a minute, CJ is the player and cannot be commanded).
- Nothing below has been tried in the game.

## PROTECT (close protection)

| Rule in the brain | Where it is | Basis |
|---|---|---|
| Concentric rings: an inner ring that never leaves the principal, an outer ring that meets the threat, overwatch above | `hcb_detail.c` (three at CJ, four out, the marksman) | source (protective-detail formations: inner / middle / outer rings; counter-sniper overwatch) |
| The commander ("detail leader") stays at arm's length, behind the principal's right shoulder | commander's post `at_off(cjp, f, -0.8, r, 1.2)` | source |
| Three at CJ: the commander, one ahead-left (3-5 m, out of CJ's way), one behind-left who looks back | posts CLOSE / CLOSE2 | source for the roles (point, rear guard); the metres are an **assumption** |
| "Cover and evacuate": on an attack the inner ring shields and moves the principal away, it does not chase; the outer men / counter-assault team engage | duties SHIELD / COVER, `leading`, nobody of the three gets an assault post in PROTECT | source (the Reagan 1981 and later reviews are the usual illustration) |
| Outer men stand in cover that hides them from the threat **and** lets them see both the threat and the principal | `find_cover(..., low)`, `hidden_hi`, the check from the place to CJ | source for the principle; the test (a crouching man hidden, a standing one sees over) is an **assumption** |
| One outer man moves at a time, the rest stay put | `turn` in the outer loop | source (bounding by one element) |
| The marksman watches from a high place and reports first | `overwatch()`, `HCB_ROLE_MARKSMAN` holding while 3 m or more above CJ | source; "a roof 4-35 m up, 12-70 m from CJ, CJ must be seen from it" is an **assumption** |
| Reaction 0.3-0.6 s, shield within 1 s, away from the spot within 2.5 s | the brain looks 10-20 times a second; no extra delay is added | the times are from excerpts; **not measured here** |
| Explosions, grenades, a ramming car: everybody leaves the circle, the commander calls the side | 0.8 / 0.9 rules, kept | assumption |

## ASSAULT (a small unit going for one target)

| Rule in the brain | Where it is | Basis |
|---|---|---|
| Split into a base of fire and an assault element; the assault element moves only while the base of fire is firing | `hcb_squad.c`: fire team REAR / REAR2 / MARKSMAN, assault pairs CLOSE+POINT and CLOSE2+POINT2; a bound starts after 2 s of fire | source (fire and movement, FM 3-21.8 "squad attack"; the same in British and Russian small-unit manuals) |
| Bounding overwatch by pairs: one pair moves, the other covers | `mover`, alternating | source |
| Short rushes: 3-5 s up, then down ("I'm up, he sees me, I'm down") | rushes of 8 m, a pause in between | source for 3-5 s; 8 m is an **assumption** |
| The assault element comes in from the flank, off the line of the base of fire (never across it) | assault pairs on a line 35 degrees off | source for the principle; the angle is an **assumption** |
| Gather at the last cover before the target, then go | GATHER at 32 m (three quarters present or 15 s) | source ("last covered position"); the numbers are an **assumption** |
| Small assault groups of 2-4 with their own covering group (what both sides use in Ukraine since 2022) | pairs + fire team instead of a line of eight | source (excerpts of RUSI / ISW / ArmyInform write-ups) |
| A lost target: watch where he was, then go and look; never chase what was never seen | SEARCH after 6 s unseen, target dropped after 20 s | assumption (the brain only knows what its men or CJ saw) |
| After the target is down: all-round watch at a point to the side of it, then back | CONSOLIDATE 8 s, 12 m to the side, then REGROUP | source ("consolidate and reorganise" off the objective) |
| Break off when a third of the unit is down | WITHDRAW at three men down | assumption |
| The principal's safety first: with CJ under 40 health the two bodyguards go back to him | `danger_cj` | assumption (it is this mod's first rule) |

## Helicopter and ropes

| Rule | Where | Basis |
|---|---|---|
| Fast-roping from a stable hover, low (8-12 m), one man per rope at a time, the helicopter leaves after the last man | the ground worker holds the helicopter until the second four are down (2.0); the marksman's rope from 11 m | source (fast-rope procedures); in the game the height is what the helicopter has |
| The helicopter does not hang over the principal in a fight; it orbits with a door to the target | 0.6 pilot, kept | source for door-gunner orbits; the radius is an assumption |

## Game AI

| Idea | Used for | Basis |
|---|---|---|
| A squad layer that hands out tasks + an individual layer that carries them out (Killzone 2 / Halo 3: no full planner) | `hcb_squad.c` over `hcb_agent.c` | source (talk excerpts); chosen over GOAP because the set of actions is small and the time budget hard |
| Position evaluation as a weighted sum: cover from the main threat, line of fire, distance, neighbours | cover search in `hcb_detail.c` (not yet a separate weighted evaluator: see "not done") | source (Killzone "tactical position evaluation"); the weights of the plan were NOT implemented as such |
| Explicit action life cycle with failure reasons and a failure ladder | `hcb_agent.c`: CHOSEN - MOVING - ARRIVED - ACTING / FAILED, reasons in the log | assumption (common practice) |

## Not done from the plan (said plainly)

- no separate `hcb_places.c` with the plan's weights: positions are still found by the detail's own cover search (with the new
  "crouching hidden / standing sees over" test and the check that CJ is seen);
- no stop-and-look drill at corners and doors, no "tokens" (three shooters per target, staggered reloads);
- the mod does not clear the game's event responses and does not re-register ropes: instead the guards keep the scripts' empty
  decision maker, the helicopter is held for the second four and a fall is slowed by the mod;
- no disk cache of the map, no background thread; no tunable numbers in the ini file (only the off-switches).

## Pages found by search (excerpts only; listed so the trail is not lost)

- https://www.1stmardiv.marines.mil/Photos/igphoto/2000715556
- https://www.24thmeu.marines.mil/News/Article/Article/511064/marines-master-the-ropes-to-step-up-jump-off-aircraft/
- https://abc17news.com/news/national-world/cnn-europe-mideast-africa/2023/01/23/deadly-and-disposable-wagners-brutal-tactics-in-ukraine-revealed-by-intelligence-report/
- https://abcnews.go.com/US/wireStory/secret-services-counter-sniper-team-112080779
- https://ace3.acemod.org/wiki/feature/fastroping
- https://aerocorner.com/aircraft/md-mh-6m-little-bird/
- https://www.aljazeera.com/news/2022/7/9/undeniable-flaws-in-shinzo-abes-security-japan-police-officer
- https://allieduniversal-ep-public.exceedlms.com/student/page/1192687-attack-on-principal-countermeasures-atc-201
- https://www.americanspecialops.com/photos/law-enforcement/swat-sniper.php
- https://apps.dtic.mil/sti/pdfs/ADA071116.pdf
- https://arcsar.organizations.mchs.gov.ru/export/docx/News/4239361
- https://armchairgeneral.com/?p=10036
- https://armyinform.com.ua/2023/03/03/dlya-rosiyan-shturmovi-zagony-vagnerivcziv-strukturyzovane-garmatne-myaso/
- https://armyinform.com.ua/2023/03/12/girski-pihotynczi-gotuyutsya-do-shturmiv-pozyczij-voroga/
- https://armyinform.com.ua/2023/11/01/yak-pihotynczi-gotuyutsya-do-shturmiv/
- https://armyinform.com.ua/2025/07/18/odyn-prykryvaye-inshyj-prosuvayetsya-u-navchalnomu-czentri-pokazaly-yak-trenuyutsya-shturmovi-grupy/
- https://armyrecognition.com/news/aerospace-news/2026/u-s-marines-test-uh-1y-aerial-sniper-capability-from-uss-tripoli-in-centcom-waters
- https://artofcombatblog.blogspot.com/2016/12/action-versus-reaction.html
- https://www.artofmanliness.com/skills/tactical/military-hand-signals/
- https://www.asisonline.org/security-management-magazine/articles/2005/10/one-on-one-protection/
- https://asteriamtec.neocities.org/psd
- https://www.aus.com/de/node/7356
- https://www.aus.com/good-executive-protection-agent-social-chameleon
- https://blog.roninsgrips.com/the-praetorians-sword-an-analysis-of-the-u-s-secret-service-counter-assault-team/
- https://bodyguard-books.com/training/rings-of-defence.html
- https://brainscape.com/flashcards/11-vehicle-embus-debus-16769656/packs/22303645
- https://carnegieendowment.org/research/2024/10/assessing-russian-military-adaptation-in-2023
- https://cavac.at/cavacopedia/Attempted_assassination_of_Ronald_Reagan
- https://www.chathamhouse.org/2024/07/assessing-russian-plans-military-regeneration/03-ground-forces
- https://www.circuit-magazine.com/p/counter-ambush-tactics-for-security-professionals-part-2
- https://www.circuit-magazine.com/p/countering-snipers-part-2
- https://www.circuit-magazine.com/p/covert-protective-details-invisible-shield
- https://www.circuit-magazine.com/p/formations-body-cover-professional-distance
- https://www.circuit-magazine.com/p/when-push-comes-to-shove-combat-principles-for-executive-protection
- https://citizendium.org/wiki/Bounding_overwatch
- https://clayhiggins.house.gov/wp-content/uploads/2024/12/Higgins-additional-views-J13-TF-Report.pdf
- https://community.bistudio.com/wiki/React_to_Contact
- https://www.cs.uky.edu/~sgware/reading/papers/orkin2005agent.pdf
- https://www.deccanherald.com/amp/story/world%2Fexplained-how-the-trump-rally-gunman-had-an-edge-over-the-counter-snipers-3129774
- https://defence-blog.com/russia-adopts-new-infantry-doctrine-amid-manpower-strain/
- https://dspace.vutbr.cz/bitstream/handle/11012/137296/READ-2018-08.pdf
- https://dupuyinstitute.org/2018/10/11/human-factors-in-warfare-suppression/
- https://www.dvidshub.net/news/115254/fast-roping-prepares-marines-rapid-ship-shore-deployment
- https://en.wikipedia.org/wiki/Bounding_overwatch
- https://en.wikipedia.org/wiki/Countersniper
- https://en.wikipedia.org/wiki/Individual_movement_techniques
- https://en.wikipedia.org/wiki/Tactical_reload
- https://en.wikipedia.org/wiki/Tueller_Drill
- https://erenow.org/common/in-the-presidents-secret-service/11.php
- https://euromaidanpress.com/2026/08/27/new-way-of-war/
- https://euromaidanpress.com/?p=372311
- https://euromaidanpress.com/?p=377012
- https://www.euronews.com/2024/05/17/ficos-security-detail-failed-second-bullet-should-have-hit-bodyguard-expert-explains
- https://focus.ua/voennye-novosti/752729-voyna-v-ukraine-vsu-zastavili-rossiyan-izmenit-taktiku-vedeniya-nastupleniy-i-shturmov-smi
- https://www.forcesnews.com/services/army/section-attack-six-steps-success-when-british-army-engages-enemy
- https://forum.dcs.world/topic/354369-helo-doorgunnery-pilot-tips-and-tactics-for-operating-with-human-doorgunner-how-to
- https://www.globalsecurity.org/military/library/policy/army/accp/in0202/le2c.htm
- https://www.globalsecurity.org/military/library/policy/army/accp/in0202/le2d.htm
- https://www.globalsecurity.org/military/library/policy/army/accp/in0721/ch3.htm
- https://www.globalsecurity.org/military/library/policy/army/accp/mp1005/lsn3.htm
- https://www.globalsecurity.org/military/library/policy/army/fm/1-140/CH6.HTM
- https://www.globalsecurity.org/military/library/policy/army/fm/19-10/Ch19.htm
- https://www.globalsecurity.org/military/library/policy/army/fm/3-06-11/ch3.htm
- https://www.globalsecurity.org/military/library/policy/army/fm/7-7/Ch4.htm
- https://www.globalsecurity.org/military/library/policy/army/fm/7-8/ch4.htm
- https://www.globalsecurity.org/military/library/policy/army/fm/7-93/Appj.htm
- https://www.goodreads.com/author_blog_posts/2707315-a-marine-s-afghan-aar-v-learn-how-to-patrol-dammit?tab=author
- https://www.govexec.com/workforce/2025/09/secret-service-73-short-snipers-it-requires/407827/
- https://www.grunt.com/blogs/news/squad-tactics-in-fallujah
- https://www.gsaglobal.com/?p=2959
- https://www.guerrilla-games.com/read/killzones-ai-dynamic-procedural-tactics
- https://historyrise.com/article/understanding-the-military-term-overwatch-and-its-tactical-application/
- https://home.army.mil/campbell/download_file/view/20c0cc59-3a74-44e6-b77a-9dfc0217e7f4/782
- https://www.hsgac.senate.gov/wp-content/uploads/2024.09.23_Initial-Findings-One-Pager_RMP.pdf
- https://inside.safariland.com/?p=39009
- https://isdacenter.org/science-walking-driving-principal-time-distance/
- https://israeled.org/wp-content/uploads/2015/06/1996-3-28-Shamgar-Commission-Report-on-the-Assassination-of-Prime-Minister-Yitzhak-Rabin.pdf
- https://issuu.com/circuit-magazine/docs/issue_57/s/12049495
- https://issuu.com/circuit-magazine/docs/issue_61/s/14906323
- https://www.jewishvirtuallibrary.org/the-assassination-of-yitzhak-rabin
- https://www.jns.org/israel-news/what-the-embattled-u-s-secret-service-can-learn-from-israels-shin-bet
- https://joseph-bernard-jnt9.squarespace.com/blog/2017/3/5/debate-4-limited-penetration-vs-points-of-domination
- https://www.jta.org/archive/panel-concludes-shin-bet-failed-in-protecting-rabin
- https://ke.linkedin.com/in/ali-seif-97a732211
- https://ke.linkedin.com/in/kefa-oganda-549345228
- https://kiwix.lema.org/wikipedia_en_all_mini_2024-02/A/Designated_marksman
- https://kurs.com.ua/ru/novost/1458048-rossija-menjaet-mjasnie-shturmi-na-malie-gruppi-chem-ato-opasno-dlja-fronta
- https://kyivindependent.com/no-tanks-lone-soldiers-ukraine-details-new-russian-assault-tactics/
- https://lapdonlinestrgeacc.blob.core.usgovcloudapi.net/lapdonlinemedia/2021/12/Dignitary_Security_33020.pdf
- https://www.lasorsa.com/wp-content/uploads/2017/03/Assessments-Advances-Planning-Checklists.docx
- https://www.lawfaremedia.org/article/how-the-secret-service-failed-to-prevent-a-trump-assassination-attempt
- https://libeldoc.bsuir.by/bitstream/123456789/63323/1/Volkov_Vliyanie.pdf
- https://loadoutroom.com/?p=118480
- https://londonsecuritycollege.co.uk/?p=5528
- https://www.marines.mil/News/News-Display/Article/3088609/us-marines-improve-advanced-marksmanship-with-aerial-sniper-training/
- https://www.marines.mil/Portals/1/Publications/FM%203-21.8%20%20The%20Infantry%20Rifle%20Platoon%20and%20Squad_3.pdf
- https://www.marines.mil/Portals/1/Publications/MCRP%203-11.4%20A%20Helicopter%20Rope%20Suspension%20Techniques%20(HRST
- https://maxvelocitytactical.com/?p=114805
- https://maxvelocitytactical.com/?p=4157
- https://meduza.io/feature/2025/03/17/tsentr-dosie-vyyasnil-kto-ohranyaet-putina-i-kto-gotovit-emu-edu
- https://www.met.police.uk/foi-ai/metropolitan-police/disclosure-2025/december-2025/overview-functions-mpss-so-units/
- https://www.mindomo.com/mindmap/section-battle-drills-a719149e58ad4c2782e42d21a52ca50f
- https://msk1.ru/text/gorod/2023/05/09/72289079/
- https://navyadministration.tpub.com/14137A/Walking-Formation-Guidelines-127.html
- https://www.nbcnews.com/investigations/secret-service-criticized-long-took-get-trump-stage-rcna162363
- https://news.liga.net/politics/news/snachala-prosachivanie-zatem-nakoplenie-spiker-vsu-rasskazal-o-novoy-taktike-okkupantov
- https://news.liga.net/war/news/rossiyane-izmenili-taktiku-nebolshaya-pehotnaya-gruppa-teper-sostoit-iz-odnogo-soldata-24-ombr
- https://nij.ojp.gov/library/publications/protective-intelligence-and-threat-assessment-investigations-guide-state-and
- https://novayagazeta.eu/articles/2025/11/08/chetvero-iz-piati-soldat-na-fronte-pogibaiut-ot-udarov-bespilotnikov
- https://www.offgridweb.com/?p=21128
- https://officer.com/on-the-street/article/10248885/aviation-dignitary-protection
- https://open-exam-prep.com/study-guides/dss-special-agent/situational-judgment-dignitary-protection/dignitary-protection-advance-operations
- https://parkingday.org/?p=57528
- https://www.pbs.org/newshour/world/japan-police-chief-to-resign-over-killing-of-former-prime-minister-abe
- https://www.pendleton.marines.mil/In-the-News/Press-Releases/Article/535667/getting-the-hang-of-it-again
- https://www.police1.com//officer-safety/articles/how-much-do-finger-placement-and-ready-position-matter-aVMZMe7Xh9wqJB2d
- https://www.police1.com/officer-shootings/articles/action-vs-reaction-the-shoot-first-fallacy-AxWyVoHO0jU9ByeJ/
- https://www.police1.com/officer-shootings/articles/study-muzzle-position-can-have-major-impact-on-shooting-decisions-fbBb5o9qTubx92hY
- https://www.police1.com/secure/why-securing-the-high-ground-is-critical-for-officer-and-public-safety
- https://police1.com/swat/articles/dynamic-entry-versus-deliberate-entry-s86BB28VVWLfwJXW
- https://www.police1.com/swat/slicing-the-pie-vs-button-hook-for-room-entry
- https://policeandsecuritynews.com/2017/01/18/doing-the-combat-glide/
- https://www.policemag.com/articles/video-cars-cover-and-concealment
- https://public.3.basecamp.com/p/2QaBa6QJdWKnR7GWDxVkfamL/vault/8068569423
- https://publicsafety.westchestercountyny.gov/special-operations/counter-snipermarksman-team
- https://pulaski.pl/wp-content/uploads/2023/06/Pulaski-Report-Russian-Assault-Tactics-in-Ukraine.pdf
- https://www.reaganlibrary.gov/usss0330198-1
- https://relayto.com/explore/ranger-handbook-xq5p163k9y49e/QF1oGru6101
- https://relayto.com/explore/ranger-handbook-xq5p163k9y49e/gPUcHVal102
- https://www.rnz.co.nz/news/world/471245/the-2-point-5-seconds-that-sealed-shinzo-abe-s-fatal-security-lapses
- https://rtvi.com/obyasnyaem/bronya-krepka-no-tanki-nashi-skrylis-kak-svo-otpravila-groznoe-oruzhie-na-pokoj/
- https://rusi.org/explore-our-research/publications/special-resources/meatgrinder-russian-tactics-second-year-its-invasion-ukraine
- https://www.sandboxx.us/news/russia-is-now-trying-a-strategy-of-a-thousand-cuts-in-ukraine-but-its-not-working/
- https://www.scribd.com/doc/259848100/Bodyguard-Manual
- https://www.scribd.com/doc/39930896/1-FOOM
- https://www.scribd.com/document/81838994/Fast-Rope
- https://www.scribd.com/presentation/300868795/Dignitary-Protection-slides
- https://www.scribd.com/presentation/688816580/Movement-Techniques-2
- https://www.secretservice.gov/careers/special-agent/CAT
- https://www.secretservice.gov/node/5492
- https://secretservice.gov/reagan40thanniversary
- https://www.securitymagazine.com/articles/102210-beyond-the-bodyguard-why-executive-protection-requires-a-new-playbook
- https://www.securitymagazine.com/articles/97967-the-ins-and-outs-of-launching-an-executive-protection-program
- https://www.simhq.com/_land/fps_021f.html
- https://www.skycoreaviation.com/blog/skycore-explains-fast-rope-insertion-extraction-system-fries
- https://skycoreaviation.com/blog/skycore-explains-fast-rope-insertion-extraction-system-fries
- https://smallwarsjournal.com/2026/02/13/the-dispersion-paradox/
- https://sofrep.com/news/former-secret-service-agent-describes-presidents-security-detail
- https://sofrep.com/news/ranger-helicopter-assault-force-learning-to-assault-from-the-little-bird
- https://sofrep.com/news/watch-360-degree-video-shows-what-its-like-to-hitch-a-ride-dangling-under-a-blackhawk
- https://spotterup.com/?p=28111
- https://stf-website-five.vercel.app/sop/close-quarters-battle/clearing-methods
- https://www.strategypage.com/htmw/htinf/articles/20100308.aspx
- https://tacticaloperationscenter.fandom.com/wiki/File:CQBForm,_SColumn.png
- https://tacticaltuesdaywithmodernmilsim.buzzsprout.com/1674331/8303662
- https://tacticaltuesdaywithmodernmilsim.buzzsprout.com/1674331/episodes/8303662-tactical-tuesday-episode-three-fire-and-maneuver-bounding-under-fire
- https://taskandpurpose.com/military-life/us-army-battle-drills/
- https://taskforce.house.gov/sites/evo-subsites/july13taskforce.house.gov/files/evo-media-document/CAT-Op.pdf
- https://telex.hu/kulfold/2024/05/16/robert-fico-merenylet-szemelyi-vedelem-biztonsag-testorok-hibak-pomozi
- https://temp.ufopaedia.org/Field_Manual:_Movement_Tactics
- https://thecxfile.substack.com/p/saved-rounds-929
- https://thefewgoodmen.com/thefgmforum/goto/post?id=243790
- https://thefirearmblog.com/blog/ex-secret-service-agent-explains-trump-assassination-attempt-44814979
- https://www.thefiscaltimes.com/node/59868
- https://www.torchstoneglobal.com/keep-executive-protection-teams-sharp
- https://www.twz.com/4518/the-fascinating-anatomy-of-the-presidential-motorcade
- https://www.twz.com/news-features/experienced-snipers-break-down-the-trump-assassination-attempt
- https://ufpro.com/blog/client-movement-tactics-close-protection
- https://www.ukstandards.org.uk/en/nos-finder/SFSPCP6/maintain-the-safety-and-security-of-principals-whilst-on-foot
- https://unitedtaskforce.net/handbook/block/1507/avoiding-regrouping-on-enemy-positions
- https://unitedtaskforce.net/handbook/gochapter/93
- https://unitedtaskforce.net/handbook/group/206/transport-insertion-methods
- https://unitedtaskforce.net/handbook?c=movement
- https://vk.ru/@unfair_advantage-pyat-zon-na-puti-shturmovoi-gruppy
- https://vk.ru/@unfair_advantage-rabota-dvoek-i-troek
- https://vk.ru/@unfair_advantage-shturmovoe-otdelenie-vo-vzvode
- https://vukladach.pp.ua/MyWeb/manual/pidruchnuku13122023/Defense%20of%20Ukraine/Presentation/6.3.4.pdf
- https://warontherocks.com/2025/06/the-meaning-of-drone-enabled-infantry-striking-beyond-line-of-sight/
- https://www.washingtonexaminer.com/?p=3007457
- https://www.wearethemighty.com/lists/5-important-rules-every-grunt-should-follow-in-a-foot-patrol/
- https://webcf.waybackmachine.org/web/20220223153109/https://en.wikipedia.org/wiki/Fast-roping
- https://weekend.rambler.ru/read/56805843-kak-ohranyali-sovetskih-vozhdey/
- https://www.westminstersecurity.co.uk/?p=1595
- https://www.westminstersecurity.co.uk/?p=1635
- https://westminstersecurity.co.uk/close-protection/roles-and-responsibilities
- https://www.wikipedia.org/wiki/Fire_and_movement
- https://www1.ru/news/2026/05/13/413605-vysadka-s-vertoleta-ka-27.html

## Source code read in full (GitHub)

- gta-reversed (gta-reversed/gta-reversed): tasks, task manager, events and their priorities, CCover, CRopes, CPathFind
- aml-psdk (AndroidModLoader/aml-psdk): the Android (arm64) names and layouts of the same classes
- plugin-sdk (DK22Pac/plugin-sdk), reVC (the GTA VC decompilation), AndroidModLoader, SAUtils
