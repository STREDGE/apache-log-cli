HELICOVER 1.2 BETA - support helicopter with a smart crew
GTA San Andreas (Android), CLEO mod. Russian language, a clearer menu, realistic behaviour.

WHAT IT IS
Call a support helicopter: it flies in from far away, follows CJ and covers him with four door
gunners. Drop a four-man team on foot, get picked up by rope, fly to the map marker or Grove
Street and get out there by landing or by rope.

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
CLIMB ABOARD BY ROPE (CANCEL ROPE PICKUP until the climb starts), DEPLOY SQUAD / RECALL SQUAD
(a progress row while the squad is on its way), SETTINGS >, DISMISS HELICOPTER.
CJ aboard: FLY TO MAP MARKER, FLY TO GROVE STREET, EXIT BUTTON: LAND / EXIT BUTTON: ROPE (a switch:
[X] marks what the vehicle exit button does - the exit itself is that button), GUNNER FIRE >,
SETTINGS >.
SETTINGS: crew, helicopter model, crew weapon, squad tactics (GUARD / ASSAULT),
messages (ALL / IMPORTANT / OFF).

LANGUAGE
The mod draws its text with the game's own font, and the game has a different font per language.
So there is one rule: game set to Russian - the mod is Russian; any other game language - English
(those fonts have no Cyrillic; the SanLTD fan localisation has it at other codes and is not
supported). The language changes together with the game's, no restart needed.

MESSAGES
Calls sound like radio traffic: PILOT (blue), GUNNERS, SQUAD and MEDIC (green), HELICOVER hints
(yellow), alarms in red capitals. Important calls replace less important ones. ALL shows
everything; IMPORTANT only alarms and tactics; OFF is silent except for why a command was refused.

TIPS
- If it cannot land or hover, move to open, level ground.
- The Hunter has no passenger seat: no boarding or evacuation with it.
- Settings last until the game is restarted.
- WHERE I SHOOT takes your lock-on target first, then the line of your bullet traces, then the camera.
  On other game versions the traces are not read (lock-on and camera work). Grenades and flamethrowers
  leave no traces, so the gunners use your aim target or the camera there.

HONEST LIMITS
- This is a beta. I cannot see a phone screen, so the logic was checked on a simulation of the game,
  not in the game: flight, the squad, the double-press protection and the WHERE I SHOOT mode need
  your check. The Russian letters in the game's Russian were confirmed on a phone (beta 3).
- The look of the menu itself (the blue box) is drawn by CLEO, not by Helicover: the mod only
  supplies the rows. A new look for the CLEO menu is a separate project.
- In 1.1 I wrongly assumed a bullet trace holds the exact start and end of a shot. For people's shots
  it does not (it is a random piece up to 5 m long on the bullet's path), so "spot the shooter by
  the trace" and "rounds hit the helicopter" worked worse than promised. 1.2 uses lines instead.
- Running, aiming and small obstacles are handled by the game's own AI.
- Mobile CLEO cannot tell when CJ crouches or is getting into a car, so the team does not react to that.
- Slow phones may drop frames in a big fight.

Author: STREDGE. Made together with Claude (Anthropic).
