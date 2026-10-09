# Plan: Event Notifier (Discord webhook) — v1 built (logic_events.py, gui_events.py)

Status: idea captured 2026-10-06; first version built 2026-10-07. Desert Village Rumor keyword changed to "might not survive" (the rumor END message also says "Desert Village").

## Goal
Watch one or more Roblox instances (multi-Roblox, possibly over RDP) for server event
announcements, and post a Discord webhook message when an event the user cares about appears.

## Requirements (from user)
- Detect event announcement text on screen (OCR) and send it to Discord via webhook.
- **Checkbox per event**: notify / don't notify.
- **User-editable event list**: users can add/rename/remove events themselves (stored in
  settings/JSON), so new game events never need a code update.
- **Keyword matching is enough**: each event only needs a short, unique keyword/phrase
  (e.g. Devil Rift → "something" / "feels off"), not the full announcement.
- Multi-Roblox / RDP use in mind (see RDP notes below).

## Seed event list (default keywords are suggestions — users can edit)

### Clover / world events
| Event | Announcement | Suggested keyword |
|---|---|---|
| Bandit Lord | Whispers rise. One of the Bandit Lords emerges from the shadows. | `bandit lord` |
| Warlord | The Warlord of the Grasslands steps forward, challenge in his eyes. | `warlord` |
| Khamsin | The sands shift. Khamsin, the Sand Sage, emerges from the dunes. | `khamsin` |
| Desert Village Rumor | Somebody has seen something they might not survive to tell. Word has it they're in the Desert Village. | `desert village` |
| Craftsman | A seasoned Wolf Hunter Craftsman has arrived in the forest, his tools at the ready to forge exceptional gear for worthy adventurers. | `craftsman` |
| Corrupt Night | The air grows heavy, and darkness takes hold as every creature is consumed by corruption. | `corruption` |
| Mana Wisp | Mana fluttering can be heard across the Grasslands. | `mana fluttering` |
| Radiant Wisp | A Radiant Wisp has appeared in the Grasslands. | `radiant wisp` |
| Blood Wisp | A Blood Wisp has appeared in the Grasslands. | `blood wisp` |
| Wind Wisp | A Wind Wisp has appeared in the Grasslands. | `wind wisp` |
| Shadowhand Rift | A rift shrouded in sinister mana tears open. The Shadowhand stands watch, guarding what lies beyond. | `shadowhand` |
| Devil Rift | Something feels off... | `feels off` |
| Spirit Rift | A strange energy is felt throughout the kingdom. | `strange energy` |
| Giant Demon Assault | The seal has shattered. A Giant Demon now walks the land, its gaze fixed on the capital's destruction. | `giant demon` |
| Ayato | The veil shimmers, and a lone figure emerges. | `veil shimmers` |

Keyword notes:
- Devil Rift: plain `something` also appears in the Desert Village Rumor text
  ("Somebody has seen something…"), so `feels off` is safer.
- Mana Wisp text never says "wisp" — match `mana fluttering`.

### Dragon Ball events
| Event | Announcement (start) | Suggested keyword |
|---|---|---|
| One Star Dragon Ball | A single star shines, igniting the spark of an epic saga… | `single star` |
| Two Star Dragon Ball | Two stars align, forging alliances in the face of looming shadows… | `two stars align` |
| Three Star Dragon Ball | Three stars blaze, a beacon of trials overcome… | `three stars blaze` |
| Four Star Dragon Ball | Four stars glow, marking the corners of a journey… | `four stars glow` |
| Five Star Dragon Ball | Five stars radiate, a testament to battles fought… | `five stars radiate` |
| Six Star Dragon Ball | Six stars shimmer, near completion… | `six stars shimmer` |
| Seven Star Dragon Ball | As seven stars converge, the heavens themselves pause… | `seven stars` |
| Blessed Sphere | A Blessed Sphere has materialized somewhere in the Grasslands... | `blessed sphere` |

## Open questions for the planning session
- Where do announcements appear on screen (fixed banner/chat area)? → scan region per instance.
- Multi-Roblox: one scan region per window, or auto-detect each Roblox window? How to label
  which account/instance saw it in the Discord message?
- Webhook message format: plain text, embed, @role/@everyone ping per event, screenshot attached?
- De-duplication: cooldown per event so one announcement isn't posted many times
  (and the same event seen by several instances posts once?).
- Scan interval (OCR cost vs. how long the banner stays visible).
- Import/export of the event list so users can share lists.
- New macro card in the hub vs. a tab inside Skill Macro.

## Reuse from existing code
- OCR: `SpatialUtils.get_text_from_region` (RapidOCR) in `utils.py`.
- Fuzzy keyword match: `SmartMacroLogic._norm` / `match_items` pattern in `logic_smart.py`.
- Editable list UI (checkbox + entry + delete + "+ Add"): Items page in `gui_smart.py`.
- Region picker: `Overlay` in `overlay.py`.
- Setup guide pages: `gui_guide.py`.

## RDP notes (from discussion)
- Works while the RDP window is open; minimized/disconnected sessions stop rendering
  (black screenshots, dropped input).
- Client fix: `HKCU\Software\Microsoft\Terminal Server Client\RemoteDesktop_SuppressWhenMinimized` = 2 (DWORD).
- Leave running without a client: `tscon %sessionname% /dest:console` (cmd, as admin) — resolution may change.
- Keep resolution/window size fixed; redo regions after changes.
