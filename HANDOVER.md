# Steward Discord Bot Handover

Last updated: 2026-07-09

## Project Summary

Steward is a Python/disnake Discord bot for Game of Thrones Conquest server coordination. It is currently designed for Render hosting with Firebase Firestore as the database.

The bot is intentionally server-isolated. Almost all persistent data lives under:

```text
guilds/{guild_id}
```

Do not move the project to a global/shared user model unless there is a deliberate migration plan. Discord users can appear in multiple guilds with different profiles, roles, stats, rosters, and settings.

## Runtime Shape

Entry point:

```text
main.py
```

Main behavior:

- Starts a tiny Flask health server for Render.
- Loads `.env`.
- Creates a disnake bot with `Intents.all()`.
- Automatically loads every `.py` file in `cogs/`.
- Runs the bot with `DISCORD_TOKEN`.

Render health routes:

```text
GET /        -> "Steward is Online!"
GET /health  -> "OK", 200
```

## Environment And Secrets

Required environment variables:

```text
DISCORD_TOKEN
FIREBASE_CONFIG
PORT
```

Notes:

- `FIREBASE_CONFIG` should be a JSON string for Render/cloud deployment.
- Local development can fall back to `serviceAccount.json`.
- Do not commit or print `.env`, `serviceAccount.json`, Discord tokens, Firebase credentials, or Render secrets.
- `.gitignore` already excludes `.env`, `venv/`, `serviceAccount.json`, `__pycache__/`, and `repomix-output.xml`.

## Dependencies

Install from:

```text
requirements.txt
```

Core libraries:

- `disnake`
- `firebase_admin`
- `google-cloud-firestore`
- `Flask`
- `python-dotenv`
- `pandas`
- `pytz`

Use the existing virtual environment if present:

```powershell
venv\Scripts\python.exe -m compileall main.py database.py cogs services
```

## Important Verification Commands

Run these after meaningful code changes:

```powershell
venv\Scripts\python.exe -m compileall main.py database.py cogs services
```

```powershell
venv\Scripts\python.exe -c "import os, disnake; from disnake.ext import commands; bot=commands.Bot(command_prefix='!', intents=disnake.Intents.all()); [bot.load_extension('cogs.'+f[:-3]) for f in os.listdir('cogs') if f.endswith('.py')]; print('loaded', len(bot.cogs), 'cogs')"
```

```powershell
git diff --check
```

Useful command discovery:

```powershell
rg -n "@commands\.slash_command|class .*commands\.Cog|tasks\.loop" cogs services
```

## Firestore Initialization

Database module:

```text
database.py
```

Behavior:

- Loads `.env`.
- If `FIREBASE_CONFIG` exists, parses it as JSON credentials.
- Otherwise uses local `serviceAccount.json`.
- Initializes Firebase only if no app is already initialized.
- Exposes:

```python
db = firestore.client()
```

## Cog Overview

### `cogs/registration.py`

Profile and access management.

Commands:

- `/register`
- `/add_register`
- `/add_access`
- `/update_access`
- `/update_name`

Important storage:

```text
guilds/{guild_id}/users/{discord_user_id}
guilds/{guild_id}/users/{discord_user_id}/alts/{alt_name}
```

Main profile fields include:

```text
ign
tier
timezone
access_list
registered_by
registered_via
updated_at
```

Admin/logistics proxy registration:

- `/add_register`
- Writes to the selected member's user document.
- Does not create a separate proxy collection.

### `cogs/stats.py`

Stat entry modals and alt purpose selection.

Commands:

- `/add_alt`
- `/update_attack`
- `/update_defense`
- `/update_dragon_attack_stats`
- `/update_dragon_defense_stats`
- `/add_update`

Main stats storage:

```text
guilds/{guild_id}/users/{discord_user_id}.attack_stats
guilds/{guild_id}/users/{discord_user_id}.defence_stats
guilds/{guild_id}/users/{discord_user_id}.dragon_attack_stats
guilds/{guild_id}/users/{discord_user_id}.dragon_defense_stats
```

Alt stats storage:

```text
guilds/{guild_id}/users/{discord_user_id}/alts/{alt_name}.attack_stats
guilds/{guild_id}/users/{discord_user_id}/alts/{alt_name}.defence_stats
guilds/{guild_id}/users/{discord_user_id}/alts/{alt_name}.dragon_attack_stats
guilds/{guild_id}/users/{discord_user_id}/alts/{alt_name}.dragon_defense_stats
```

Compatibility note:

- The existing Firestore key is still `defence_stats`.
- User-facing command/text should use American spelling: `defense`.
- Do not rename `defence_stats` without a migration.

Current standard attack modal fields:

```text
m_att
m_def
m_health
r_cap
r_sop
```

Current standard defense modal fields:

```text
s_def
s_att
s_health
rein_sop
```

Current dragon attack fields:

```text
dragon_m_att
dragon_m_def
dragon_m_health
dragon_att_vs_dragon
```

Current dragon defense fields:

```text
dragon_def_player_sop
dragon_att_player_sop
dragon_health_player_sop
```

Admin/logistics proxy stats:

- `/add_update`
- Allows `stat_type: attack` or `stat_type: defense`.
- Writes to the selected member, not the admin.
- For alt target, the alt document must already exist.

### `cogs/council.py`

Account lookup, stats display, bubble up, and registered account export.

Commands:

- `/lookup_account`
- `/get_stats`
- `/bubble_up`
- `/account_export`

Notes:

- `/get_stats` displays Offense, Defense, Dragon Offense, and Dragon Defense sections.
- `/account_export` is the registered account/stat export.
- Legion seat rosters use `/roster_export`, not `/account_export`.

### `cogs/weekend.py`

Role setup, permanent role panels, weekend availability, and BG ping roles.

Commands:

- `/setup_gotc_roles`
- `/availability_report`
- `/availability_check`
- `/post_role_panel`
- `/post_battleground_ping_panel`

Role behavior:

- Role creation/saving uses `ROLE_DEFINITIONS`.
- Role use is ID-first through `guilds/{guild_id}.role_ids`.
- `find_role_by_key()` checks saved role ID first.
- Name matching is only a fallback if the saved role ID is missing/deleted.
- Once `/setup_gotc_roles` has saved IDs, server admins can rename roles and the bot should still assign/remove/check the correct roles.

Important role groups:

- Weekend availability:
  - Open
  - Mid-Shift
  - Close
  - Throughout
  - Absent
- Troop tiers:
  - T1 through T12
- Primary troop type:
  - Infantry
  - Ranged
  - Cavalry
- Specialist:
  - Hitter
  - Siege
  - Battlegrounds
- Dragon:
  - L41+ SoP Rally
  - L50+ Creature Rally
  - L55+ Rally Keep
  - L60+ Rein SoP/Keep
  - L65+ Rein Ally SoP
  - L69 Big Daddy
- Battleground pings:
  - All BG
  - Titans of the North
  - The Great Ranging

Availability behavior:

- Open, Mid-Shift, and Close can stack.
- Throughout and Absent are exclusive.
- Clicking a selected availability button removes that role where applicable.

### `cogs/battlegrounds.py`

Battleground signup events and reminders.

Command:

- `/create_battlegrounds_event`

Storage:

```text
guilds/{guild_id}/battleground_events/{event_id}
```

Reminder loop:

- Runs every minute.
- Sends reminders at configured offsets before the event.
- Uses stored `sent_reminders` to avoid repeat sends.

### `cogs/management.py`

Council setup, logistics role setup, announcements, and polls.

Commands:

- `/setup_council`
- `/setup_logistics`
- `/setup_announcements`
- `/announce`
- `/poll`

Important fields on:

```text
guilds/{guild_id}
```

```text
council_role
logistics_role
announcement_channel
```

Poll storage:

```text
guilds/{guild_id}/polls/{poll_id}
```

### `cogs/admin.py`

Moderation, logs channel, autorole, join/leave logs.

Commands:

- `/moderate`
- `/set_logs_channel`
- `/disable_logs_channel`
- `/set_autorole`
- `/disable_autorole`
- `/server_settings`

Guild config fields:

```text
logs_channel
autorole_id
autorole_enabled
settings_updated_by
updated_at
```

Autorole rules:

- Steward does not create autoroles.
- It only assigns an existing configured role.
- The configured role cannot be `@everyone`.
- Managed/integration/bot-managed roles are rejected.
- Bot must have `manage_roles`.
- Configured role must be below the bot's top role.

Logging rules:

- Join/leave logs only go to the configured `logs_channel`.
- If no log channel is configured, skip silently.

### `cogs/time_commands.py`

Discord timestamp helpers.

Commands:

- `/time24`
- `/time12`

Uses the invoking user's registered timezone from:

```text
guilds/{guild_id}/users/{discord_user_id}.timezone
```

### `cogs/roster.py`

Lightweight Legion roster feature.

Commands:

- `/roster_template`
- `/roster_import`
- `/roster_validate`
- `/roster_export`
- `/roster_update_positions`
- `/roster_alts`
- `/roster_update_expiry`
- `/roster_config`

Storage:

```text
guilds/{guild_id}/legion_rosters/{roster_id}
guilds/{guild_id}/legion_rosters/{roster_id}/entries/{serial}
guilds/{guild_id}/legion_rosters/{roster_id}/drafts/{draft_id}
```

Design rule:

- The roster is a lightweight seat-placement board.
- It must remain independent from registration, stats, access lists, and the normal `/add_alt` system.
- Do not force roster entries to be registered Discord users.
- Do not add Discord owner, troop tier, slot index, locked, or main-account fields to roster entries.

Roster entry fields:

```text
serial
name
seat_tier
parent_serial
type
expiry
```

Roster tier capacity:

```text
T1: max 1
T2: max 5 under T1
T3: max 5 under each T2, max 25 total
T4: max 5 under each T3, max 125 total
Total: max 156
```

No T5 exists right now.

### `cogs/help.py`

Slash command help menu.

Command:

- `/help`

Update this file whenever adding, renaming, or removing commands.

## Services Overview

### `services/access_control.py`

Shared access helper for admin/logistics-permitted actions.

Important behavior:

- Server administrators always pass.
- Configured Logistics role also passes.
- Logistics role field is read from `guilds/{guild_id}.logistics_role`.

### `services/roster_parser.py`

CSV/text parsing for Legion roster import and weekly roster updates.

Weekly update text supports:

```text
T1:
vix

T2:
t2alt
IamT31
Gov

PROTECT:
vix
Gov
```

Inline weekly update text also supports:

```text
T1: vix | T2: t2alt, IamT31, Gov | T3: | T4: | PROTECT: vix, Gov | REMOVE:
```

### `services/roster_engine.py`

Roster validation and weekly draft planning.

Important rules:

- Preserve old parent relationships where possible.
- Requested placements are stronger than normal movement minimization.
- Protect requested/protected names from demotion/removal where possible.
- Normal accounts outrank PA, and PA outranks TA.
- Expired TA is easiest to remove or bench.
- Duplicate names in update requests need serial disambiguation.

### `services/roster_exporter.py`

CSV, JSON, and text exports for Legion roster data.

## Permission Model

Server administrator:

- Can configure server settings.
- Can setup roles.
- Can setup council/logistics.
- Can use admin proxy registration/stats.
- Can manage roster imports/updates/config.

Logistics role:

- Can use `/add_register`.
- Can use `/add_update`.
- Can use roster management commands.
- Should not gain moderation or server settings powers.

Normal users:

- Can register self.
- Can add own alts.
- Can update own stats.
- Can use role panels.
- Can participate in signups/polls based on command design.

## Slash Command Naming Notes

Current visible stats commands:

```text
/update_attack
/update_defense
/update_dragon_attack_stats
/update_dragon_defense_stats
```

Do not reintroduce:

```text
/update_defence
/upgrade_dragon_attack_stats
/upgrade_dragon_defense_stats
```

Current exports:

```text
/account_export   registered account/stat export
/roster_export    Legion seat roster export
```

Keep these distinct. Avoid creating another generic `/export_roster`.

## Deployment Notes

Render free tier behavior:

- Instance may sleep.
- Instance may restart.
- In-memory state is not reliable.

Therefore:

- Important state must be persisted in Firestore.
- Poll votes, BG events, roster drafts, and reminder state should not depend on process memory.
- Background reminder loops should rebuild from Firestore on startup.

When deploying command renames:

- Discord slash command sync may take time depending on disnake/global command behavior.
- Old commands can appear briefly in the client cache.
- Restart the Render service after deploying.

## Known Compatibility Choices

### `defence_stats`

The bot uses American-facing text now, but the Firestore field remains:

```text
defence_stats
```

This is deliberate for backwards compatibility.

### Role IDs

Role panels use saved role IDs first. Renaming roles is supported after `/setup_gotc_roles` has saved role IDs.

### Roster Independence

The Legion roster is intentionally not tied to registered Discord users, stats, access lists, or `/add_alt`.

## Common Failure Modes

### "The application did not respond"

Likely causes:

- Modal/view callback did not respond within Discord's interaction window.
- Render instance was waking or restarting.
- Exception before `inter.response.defer()` or `send_modal()`.
- Missing bot permissions.

Fix pattern:

- Defer quickly for non-modal actions.
- For modals, call `send_modal()` directly as the interaction response.
- Wrap Discord role operations with `disnake.Forbidden` handling.
- Persist view state where required.

### Role not found after rename

Expected behavior:

- If `role_ids` exists and points to a live role, rename should not matter.

If it fails:

- Check `guilds/{guild_id}.role_ids`.
- Run `/setup_gotc_roles`.
- Ensure the role was not deleted and recreated outside the bot.

### Bot cannot assign role

Check:

- Bot has `Manage Roles`.
- Target role is below Steward's top role.
- Role is not managed/integration/bot-managed.

### Firestore permissions or credential errors

Check:

- `FIREBASE_CONFIG` is valid JSON in Render.
- Local `serviceAccount.json` exists for local dev.
- Firebase Admin SDK can initialize only once.

## Before Handing To Another Developer

Tell them:

1. Do not move data out of `guilds/{guild_id}` without a migration.
2. Do not rename Firestore fields casually.
3. Do not connect Legion roster to registration/stats unless explicitly requested.
4. Keep role assignment ID-first.
5. Keep `/account_export` and `/roster_export` separate.
6. Update `/help` whenever commands change.
7. Run compile/load checks before pushing.

