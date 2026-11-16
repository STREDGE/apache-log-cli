HELICOVER 1.4 BETA 2 - support helicopter with a smart crew
GTA San Andreas (Android, 64-bit), a CLEO mod + the Helicover Brain 0.4.2 mod. They only work together.

WHAT IT IS
Call a support helicopter: it flies in from far away, follows CJ and covers him with four door
gunners. Drop a four-man team on foot, get picked up by rope, fly to the map marker or Grove
Street and get out there by landing or by rope.

NEW IN BRAIN 0.4.2 - FIXED FROM YOUR LOG (a 14-minute game)
- The door gunners had not fired one round of their own in the whole game: the brain waited for the wrong crew state.
  Fixed - they fire while they are in their doors.
- The commander said "into cover" / "CJ is in cover" / "stay with me" several times a second and started and stopped
  leading CJ (177 times). Now: 2.5 s between any two things said, "into cover" every 6 s at most, "in cover" after CJ
  has stayed there a second; a shooter moving in a car no longer throws the cover spot away.
- Guards were run over (7 in the game). A guard now sprints out of the path of a car coming at him.
- The detail no longer turns round for every new shooter: it keeps the man it fights for 3 s at least.
  The scripts did not change (1.4 beta 2): only libHelicoverBrain64.so is new.

NEW IN BRAIN 0.4.1 - ONE LOG FOR THE WHOLE GAME
- Everything needed for a diagnosis goes into ONE file: mods/hcbrain_log.txt. It is added to as the game goes (twice a
  second) until the game is closed (swiped away), crashes or hangs; swiped away, at most the last half second is lost.
  A crash or a hang is written into it at once. There is no hcbrain_crash.txt any more.
- Every second: CJ (where, health, car, weapon, stars), the alert and the danger, the detail's mode and commander,
  cover, the helicopter's spot, each guard and gunner (where, health, weapon, his post and how far, whom he fires at
  and why he holds), each threat (why, distance, where, weapon), the pilot, Helicover's values that changed, the
  scripts' calls to the brain and the timing. Hits on CJ and ours, and our hits, line by line. Every 5 s where each
  CLEO script stands, every 30 s all of Helicover's values. The pause menu and the game going to the background too.
- A new start of the game is added below in the same file (the game before, a crash included, stays above). Over
  24 MB, the file is renamed hcbrain_log_old.txt at the next start and a new one begun.
- What to send after a game: mods/hcbrain_log.txt (and the newest hcbrain_report_NN.bin, if there is one).
  The scripts did not change: this is the same 1.4 beta 2, only libHelicoverBrain64.so is new (the zip has both).

NEW IN 1.4 BETA 2 (brain 0.4) - AFTER YOUR 1.4 CHECK
The detail on the ground
- Eight men instead of four: the commander is a soldier, the other seven are agents in black suits; the helicopter crew
  stays SWAT. Fixed, not on the menu. The brain gives the roles: commander, two bodyguards (either side of CJ), the
  advance pair, the counter-assault pair (flanks), a marksman further back. Weapons by role.
- The commander walks CJ to cover himself: 2-3 m ahead on the way, between CJ and the shooter, the bodyguards at CJ's
  sides. No more mark on the ground. CJ decides: if he does not come, after 3 s the commander goes back to his side and
  offers the way again a few seconds later. Already in cover: CJ stays.
- The formation is chosen by the brain (diamond walking, narrower running, posts on the approaches when CJ stands a
  while, a spot behind a wall comes in). The threat is remembered for 12 s: no standing down between shots.
- The brain picks how to fight: HOLD (cover, bounding), PULL OUT (ring, the commander leads CJ away, call the pickup -
  at 5 stars, against many or when CJ is badly hurt), ASSAULT (few enemies, CJ in cover - the pairs push and flank).
  Menu SQUAD TACTICS: AUTO (default) / ASSAULT / GUARD.
- A man who does not get nearer to his post for 1.5 s is given another way round, then the game's path network.
- Targets are shared: the men on the ground take those close to CJ, the door gunners those further off.
The helicopter
- The door gunners fire their own weapons through the game's weapon code: real sound, muzzle flash, tracer and hit;
  every round is still checked by the brain first. Their pose is the brain's: seated on the skids in flight, kneeling
  at the door over a fight. The pose, crew and crew weapon settings are gone.
- In a fight the helicopter holds a spot 28 m from CJ on the far side from the shooter, 24 m up, where the gunners see him.
Diagnostics
- A game crash is written down: mods/hcbrain_log.txt says where it happened and what the brain was doing, and a
  report is saved. Should a gunner's shot through the game's code ever crash the game, from the
  next start the gunners go back to the old way by themselves (it is in the log).
- The log has the brain's journal: alert and detail changes, the commander's words, "leading CJ to cover", and every
  30 s a summary (how much the gunners and the guards fired, what held them, posts not reached).

NEW IN 1.4 BETA 1 (brain 0.3)
Door gunners
- They fire their own weapons (like a drive-by from a car window): the fire visibly comes from them, not "from the
  sky". Who fires at whom and when is still the brain's call; "stop" works in the same frame.
- They sit on the skids with their legs hanging and fire seated. SETTINGS > GUNNERS: SITTING / KNEELING / STANDING.
- No fire at a place the man has just ducked away from.
The team on the ground - a close-protection detail
- Roles: commander "Alpha", the bodyguard, the point man and the rear man. In peace a diamond round CJ, turned the way
  he goes, each man watching his own sector; men who fell behind run, men close by walk.
- An armed suspect nearby: the bodyguard steps between him and CJ, the others keep their weapons on him.
- Under fire: the commander finds CJ cover (a wall, a car - never towards the shooter, and only where there is ground)
  and tells him where: "CJ, cover - on your left! Go to the mark" (a green mark on the ground). With CJ in cover the
  bodyguard crouches beside him, the commander takes the next cover, the fire team fights from the shooter's side
  and bounds: one runs while the other covers him, crouched.
- No cover near: "stay by your guard", and the bodyguard covers CJ with his body.
- CJ badly hurt under fire: a tight ring round him and "we pull out - call the rope pickup".
- The commander falls: the next man says "I have command".
- When CJ shoots nobody stands in front of his gun.
- When it is over: "clear - regroup on CJ".
The pilot
- Flights to the map marker and to Grove Street are flown by the brain like a person would: nose down to speed up,
  banked into turns, slower for a sharp turn, 35 m over the roofs ahead (it looks 250 m ahead), slows down and
  climbs early for a tall building, brakes with the nose up without overshooting and hovers 25 m over the point.
  Up to 245 km/h. Smooth at any frame rate.
- The descent to the landing spot and the landing are still the old ones (the next step).

HONESTLY
- Everything was checked on a computer (a model of the game, an emulator with your libGTASA.so and CLEO), not in the
  game yet.
- The seated pose will be tuned from your screenshot. The brain writes the helicopter's tilt straight into its
  position: should it shake or spin in the game, send a video/screenshots and mods/hcbrain_log.txt.
- Should the game hang, close it and send mods/hcbrain_log.txt and the newest mods/hcbrain_report_NN.bin.

FIXED IN BRAIN 0.2.1 (scripts 1.3 beta 1)
- The game hung when the helicopter came in to Grove Street / the map marker: the brain spent almost half of every
  frame on line-of-sight checks, and in a busy street with shooting the game all but stopped. The checks now have a
  hard budget (at most 2.5 ms a frame, the brain at most a quarter of the time), and coordinates that are not a
  number or lie off the map never reach the game.
- Should the game still hang or crawl, the mod saves a report by itself and writes to mods/hcbrain_log.txt where the
  game stopped. Close the game and send mods/hcbrain_log.txt and the newest mods/hcbrain_report_NN.bin.

NEW IN 1.3 BETA 1 - THE BRAIN CONTROLS THE FIRE
- The archive has two parts now: the scripts (CLEO folder) and the mod libHelicoverBrain64.so (mods
  folder). The brain decides who of your people fires at whom and when; the scripts only carry it out.
  Without the brain the helicopter is not called ("NO BRAIN MOD"). The brain has no off switch
  and there is no fallback mode.
- Door gunners open fire 0.15-0.35 s after somebody fires at CJ or points a weapon at him (targets
  used to be looked for every 1.5 s). Two take the most dangerous man, the others take the rest; a
  man is not dropped while he lives; never more than three rifles on one man.
- A car on a collision course with CJ is met early - the driver is fired at; cars next to CJ are not
  blown up.
- Every round of a door gunner is checked before it leaves: not within 2 m of CJ or 1 m of your own
  people, not across the cabin, not past the gunner beside him. No more fire "at a spot" or at empty cars.
- The squad on the ground fires only at the men the brain names and ceases fire in the very frame CJ
  or one of yours enters the line. Squad tactics (formation, cover) are still the old ones.
- GUNNER FIRE page: four rules - PROTECT ME / ARMED ONLY / WHERE I SHOOT / HOLD FIRE (FIRE AT ALL is
  gone) - and two switches: POLICE: FIRE BACK (with stars, only at policemen who fired) / NEVER FIRE;
  MISSIONS: DEFEND ONLY (in a mission, only at those who attacked) / AS USUAL.
  HOLD FIRE is absolute now: nobody fires, whatever happens.
- WHERE I SHOOT: the targets are the people CJ fires at and the crew of a car he fires at.
- The pilot still flies by the old rules; his turn is a later stage.

NEW IN 1.2 BETA 6
- Messages arrive at once. In the mobile game the help box is a queue: every message stayed for 5
  seconds and the next one waited its turn, so calls ran far behind the events. The mod now draws
  one line of its own at the top centre of the screen: it is there in the same frame and is replaced
  at once by the next one. One line only - messages never overlap. The answer to a button you
  pressed takes the line immediately; only an alarm may replace it early.
- PROTECT ME is close protection now, not a gang war. The gunners engage real threats only: whoever
  hurt CJ, the crew or the helicopter, whoever fires towards CJ, or an armed gang member (a
  policeman when CJ is wanted) on foot within 40 m, turned to CJ and in sight. Gang members walking
  by and cars driving past are left alone. No fire mode makes the gunners "hate" a ped type any
  more, so the game's own AI no longer opens fire on cars.
- The gunners do not blow cars up. Nobody aims at an engine; a car below 700 health (it burns below
  250) is not fired at at all - in every mode, WHERE I SHOOT included.
- CJ in the line of fire: if a round would pass within 2 m of CJ the gunner holds fire and lowers
  his weapon.
- New call "CAR ON FIRE! Get away from it." when a car burns within 12 m of CJ.
- Your people no longer cower. Punched or shot at they used to duck with their hands over their
  heads: the game gave them an ordinary pedestrian's behaviour. Pilot, gunners and squad now have
  the "empty" behaviour - they carry on with their orders and can never turn on CJ. For the reload
  drill the squad takes a knee with the weapon instead of the scared pose.
- Door gunners kneel on the skids instead of standing bolt upright. If it looks worse in the game:
  SETTINGS > GUNNERS: KNEELING / STANDING.

NEW IN BETA 5
- The menu opens at once. After a tap on "helicover" in the CLEO list it used to take almost a
  second: the mod's scripts checked each other with fixed pauses. Now the menu is there on the
  next frame.
- The rows answer at once: the order reaches the pilot in the same frame and the page is redrawn
  without the 0.2 s pause. The double-tap protection (0.35 s after a page change, 1 s for the same
  row) is unchanged.
- Flight, gunners and the squad are as in beta 4: only the menu was changed.

NEW IN BETA 4
- The mod's language simply follows the game's: game set to Russian - menu and messages in Russian;
  any other game language (English, SanLTD and the rest) - English. There is no language choice in
  the menu any more; the LANGUAGE and FONT TEST pages are gone.
- Aboard, EXIT BUTTON: LAND and EXIT BUTTON: ROPE are switches only: they start nothing. You get out
  with the vehicle exit button, the way that is marked [X].
- Pressing something twice no longer breaks anything:
  . an order that is already being carried out is not started again (follow, hold, patrol, the
    flight to the same marker or to Grove Street, deploying and recalling the squad, the exit button);
  . the squad row shows progress - "SQUAD ROPING DOWN..." / "SQUAD COMING BACK..." - and is not a
    button meanwhile; CLIMB ABOARD BY ROPE turns into CANCEL ROPE PICKUP;
  . while anybody is on the ropes the pilot answers "wait - rope work in progress" and finishes
    the job; a cancel is remembered and carried out as soon as the men have landed;
  . double taps: nothing is taken for 0.35 s after a tap or a page change (a second tap on "CREW >"
    used to change the crew at once), and a row that is being hammered is taken once: the next
    tap on it counts after a second's pause.
- Guards are never handed to the game any more. A guard who lagged behind or was let go used to
  become an ordinary armed pedestrian in uniform (shooting him gave a wanted star). Now he puts the
  gun away, walks off and is removed once out of sight - and stays one of ours all the while.
- The cover team at the rope is not abandoned: on a cancelled pickup, on FOLLOW / PATROL / DISMISS,
  or if you do not come within 90 s, it climbs back up first and then the helicopter carries out
  the order. DEPLOY SQUAD at that moment keeps the same four men on the ground as your squad.
- DISMISS HELICOPTER with a squad on the ground: the helicopter picks the squad up first (waits for
  the ropes, tries again if it cannot start, 45 s at most), then leaves; any other order cancels it.

WHAT IS NEW IN 1.2 (beta)
- Russian language for the menu and every message, when the game itself is set to Russian.
- A clearer menu: one row = one action, modes are marked [X], DISMISS HELICOPTER asks first and
  recalls a squad on the ground before leaving.
- WHERE I SHOOT (follow my shots) was rebuilt: the gunners fire at the target you lock on to (the
  game's auto-aim), in free aim at the line of your bullets (read from the bullet traces; the camera
  is the fallback), and stay on it while you shoot and 0.9 s after. Rounds of other people that flew
  past you do not count as your fire. It works from a car (drive-by) too.
- No teleports: the helicopter flies in from afar and leaves out of sight; the squad catches up by
  sprinting along the road network and a guard who lags for 60 s is let go; the pilot waits up to
  25 s for the squad at the ropes; the squad only rides in a car CJ drives himself (one seat each),
  never in taxis, buses or other people's cars; nobody is removed in view.
- Helicopter: eased braking at the rope and when you exit while flying fast, a self-powered climb
  instead of a jump when wedged, the emergency landing picks a clear spot, a helicopter stuck in
  "landing blocked" comes back to you after 15 s. Door gunners are no longer lasers: rounds scatter
  (more with distance and helicopter speed).
- Squad: the formation hangs on the direction CJ travels in (no running round him when he turns on
  the spot), steps out of his line of fire, the medic does not leave him in ASSAULT, targets stick.
- Helicopter model, crew clothes and crew weapon change at once, when chosen; the only wait is while
  somebody hangs on a rope (then the helicopter is replaced right after, with an on-screen note).
  The squad on the ground changes clothes and weapon on the fly too.

REQUIREMENTS
- GTA San Andreas for Android, 64-bit, with AML (the mods folder) and CLEO Android.
- The brain mod compares instructions of the game and of CLEO with its own table and works only on
  the build it was made for. On any other build it touches nothing and Helicover says
  "NO BRAIN MOD" (the reason is in mods/hcbrain_log.txt).

INSTALLATION
1. Close the game.
2. Put mods/libHelicoverBrain64.so from the archive into the game's mods folder
   (Android_unprotected/data/com.rockstargames.gtasa/mods/), replacing an older one.
3. Copy all 8 files from the CLEO folder of the archive into the game's CLEO folder
   (Helicover.csi, Helicover.fxt, Helicover_RU.fxt and the five Helicover_*.csa).
   Helicover_RU.fxt is a binary file with Russian letters: copy it as it is, do not open or re-save
   it in a text editor (the English Helicover.fxt is plain text).
4. Replace any older Helicover files; keep no duplicates.
5. Start the game.

HOW TO USE
Open the CLEO menu and choose Helicover. The menu shows only what makes sense right now and the
title says what the helicopter is doing.
No helicopter: CALL HELICOPTER.
CJ on foot: FOLLOW ME / HOLD HERE / PATROL AROUND ME (the current one is marked [X]),
GUNNER FIRE > (protect me / armed only / where I shoot / hold fire; police: fire back / never fire;
missions: defend only / as usual),
CLIMB ABOARD BY ROPE (CANCEL ROPE PICKUP until the climb starts), DEPLOY SQUAD / RECALL SQUAD
(a progress row while the squad is on its way), SETTINGS >, DISMISS HELICOPTER.
CJ aboard: FLY TO MAP MARKER, FLY TO GROVE STREET, EXIT BUTTON: LAND / EXIT BUTTON: ROPE (a switch:
[X] marks what the vehicle exit button does - the exit itself is that button), GUNNER FIRE >,
SETTINGS >.
SETTINGS: crew, helicopter model, crew weapon, squad tactics (GUARD / ASSAULT),
messages (ALL / IMPORTANT / OFF), gunners' pose (KNEELING / STANDING).

LANGUAGE
The mod draws its text with the game's own font, and the game has a different font per language.
So there is one rule: game set to Russian - the mod is Russian; any other game language - English
(those fonts have no Cyrillic; the SanLTD fan localisation has it at other codes and is not
supported). The language changes together with the game's, no restart needed.

MESSAGES
Calls sound like radio traffic: PILOT (blue), GUNNERS, SQUAD and MEDIC (green), HELICOVER hints
(yellow), alarms in red capitals. One line at the top of the screen; important calls replace
less important ones at once. ALL shows everything; IMPORTANT only alarms and tactics; OFF is
silent except for why a command was refused.

TIPS
- If it cannot land or hover, move to open, level ground.
- The Hunter has no passenger seat: no boarding or evacuation with it.
- Settings last until the game is restarted.
- A report for the author: game Settings > Mods Settings > "Brain report" saves the last ~10 minutes to
  mods/hcbrain_report_NN.bin (a new number every time). The debug markers over people ("Brain markers",
  same page) are off by default.

HONEST LIMITS
- This is a beta. The fire control of 1.3 was checked on a computer (simulated fights, a fight
  recorded on a tablet, an emulator with the real game library and the real CLEO code), but it has
  not run in the game itself yet.
- The squad fires the game's own weapons: the brain stops a guard within one frame, but it does not
  steer the game's bullet (the door gunners' rounds are checked one by one).
- An enemy standing right next to CJ cannot be fired at from the helicopter (the line passes within
  2 m of CJ). A close bodyguard, cover and getting CJ out of fire are later stages; the pilot still
  flies by the old rules.
- The police helicopter is not fired at yet.
- The look of the menu itself (the blue box) is drawn by CLEO, not by Helicover: the mod only
  supplies the rows. A new look for the CLEO menu is a separate mod (CLEO UI).
- In 1.1 I wrongly assumed a bullet trace holds the exact start and end of a shot. For people's shots
  it does not (it is a random piece up to 5 m long on the bullet's path), so "spot the shooter by
  the trace" and "rounds hit the helicopter" worked worse than promised. 1.2 uses lines instead.
- Running, aiming and small obstacles are handled by the game's own AI.
- Mobile CLEO cannot tell when CJ crouches or is getting into a car, so the team does not react to that.
- Slow phones may drop frames in a big fight.

Author: STREDGE. Made together with Claude (Anthropic).
