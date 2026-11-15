HELICOVER 1.2 BETA - support helicopter with a smart crew
GTA San Andreas (Android), CLEO mod. Russian language, a clearer menu, realistic behaviour.

WHAT IT IS
Call a support helicopter: it flies in from far away, follows CJ and covers him with four door
gunners. Drop a four-man team on foot, get picked up by rope, fly to the map marker or Grove
Street and get out there by landing or by rope.

WHAT IS NEW IN 1.2 (beta)
- Russian language for the menu and every message. Chosen automatically from the game's language
  or by hand (SETTINGS > LANGUAGE). Which of the two Russian letter layouts fits your font is shown
  by the FONT TEST pages - see below; this is the main thing to check in the beta.
- A clearer menu: one row = one action, modes are marked [X], the two exit methods are separate
  rows, DISMISS HELICOPTER asks first and recalls a squad on the ground before leaving.
- WHERE I SHOOT (follow my shots) was rebuilt: the gunners take the line of your fire from the
  bullet traces (not only the camera), stay on it while you shoot and 0.9 s after.
- No teleports: the helicopter flies in from afar and leaves out of sight; the squad catches up by
  sprinting along the road network and a guard who lags for 60 s is let go; the pilot waits up to
  25 s for the squad at the ropes; the squad only rides in a car CJ drives himself (one seat each),
  never in taxis, buses or other people's cars; nobody is deleted in view.
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
- GTA San Andreas for Android with CLEO (CLEO Android).
- Tested on the 64-bit game with AML. Map-marker flight, spotting shooters by bullet traces and the
  automatic Russian language work on that build only; on other builds they switch off by themselves.

INSTALLATION
1. Close the game.
2. Copy all 8 files from the CLEO folder of the archive into the game's CLEO folder
   (Helicover.csi, Helicover.fxt, Helicover_RU.fxt and the five Helicover_*.csa).
   Helicover_RU.fxt is a binary file with Russian letters: copy it as it is, do not open or re-save
   it in a text editor (the English Helicover.fxt is plain text).
3. Replace any older Helicover files; keep no duplicates.
4. Start the game.

HOW TO USE
Open the CLEO menu and choose Helicover. The menu shows only what makes sense right now and the
title says what the helicopter is doing.
No helicopter: CALL HELICOPTER.
CJ on foot: FOLLOW ME / HOLD HERE / PATROL AROUND ME (the current one is marked [X]),
GUNNER FIRE > (protect me / armed only / where I shoot / fire at all / hold fire),
CLIMB ABOARD BY ROPE, DEPLOY SQUAD / RECALL SQUAD, SETTINGS >, DISMISS HELICOPTER.
CJ aboard: FLY TO MAP MARKER, FLY TO GROVE STREET, EXIT: LAND, EXIT: ROPE (the last one used is
what the vehicle exit button does), GUNNER FIRE >, SETTINGS >.
SETTINGS: crew, helicopter model, crew weapon, squad tactics (GUARD / ASSAULT), exit button
(LAND / ROPE), messages (ALL / IMPORTANT / OFF), LANGUAGE.

LANGUAGE AND FONT TEST (IMPORTANT FOR THE BETA)
The game draws text with its own font and the code alone cannot tell how Russian letters are laid
out in it, so the beta carries two layouts and test pages. If Russian words look like rubbish:
1. SETTINGS > LANGUAGE: AUTO picks "RUSSIAN 2" when the game itself is set to Russian. Try
   RUSSIAN 1 (CP1251), RUSSIAN 2 (GAME FONT) and ENGLISH.
2. Open LANGUAGE > FONT TEST. Page 1 rows start with "1:", page 2 rows with "2:". The page where
   you see the Cyrillic alphabet in order is the right layout. SHOW MESSAGE prints the same in a
   help box.
3. Send a screenshot of both pages: the final version keeps only the right layout and drops the
   test pages. Until then you can play in English (LANGUAGE > ENGLISH).

MESSAGES
Calls sound like radio traffic: PILOT (blue), GUNNERS, SQUAD and MEDIC (green), HELICOVER hints
(yellow), alarms in red capitals. Important calls replace less important ones. ALL shows
everything; IMPORTANT only alarms and tactics; OFF is silent except for why a command was refused.

TIPS
- If it cannot land or hover, move to open, level ground.
- The Hunter has no passenger seat: no boarding or evacuation with it.
- Settings last until the game is restarted.
- WHERE I SHOOT follows bullet traces: grenades and flamethrowers leave none, so the gunners use
  your aim target or the camera there.

HONEST LIMITS
- This is a beta. I cannot see a phone screen, so the logic was checked on a simulation of the game,
  not in the game: how the Russian letters look, flight, the squad and the new WHERE I SHOOT mode
  need your check.
- In 1.1 I wrongly assumed a bullet trace holds the exact start and end of a shot. For people's shots
  it does not (it is a random piece up to 5 m long on the bullet's path), so "spot the shooter by
  the trace" and "rounds hit the helicopter" worked worse than promised. 1.2 uses lines instead.
- Running, aiming and small obstacles are handled by the game's own AI.
- Mobile CLEO cannot tell when CJ crouches or is getting into a car, so the team does not react to that.
- Slow phones may drop frames in a big fight.

Author: STREDGE. Made together with Claude (Anthropic).
