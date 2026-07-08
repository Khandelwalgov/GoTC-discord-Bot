# Agent Instructions For Steward

This file is for Codex or any future coding agent working in this repository.

Read `HANDOVER.md` first. It contains the product model, Firestore paths, command list, and compatibility warnings.

## Project Identity

This is a Python/disnake Discord bot for Game of Thrones Conquest coordination.

The bot uses:

- Python
- disnake
- Firebase Firestore through `database.py`
- Auto-loaded cogs from `cogs/`
- Helper modules under `services/`
- Render-compatible Flask health server in `main.py`

## Non-Negotiable Product Rules

### Keep Firestore Server-Isolated

Use:

```text
guilds/{guild_id}
```

Do not create a global users collection unless the user explicitly requests a migration.

### Do Not Break Existing Data Paths

Existing profile path:

```text
guilds/{guild_id}/users/{discord_user_id}
```

Existing alt path:

```text
guilds/{guild_id}/users/{discord_user_id}/alts/{alt_name}
```

Existing main stat fields:

```text
attack_stats
defence_stats
dragon_attack_stats
dragon_defense_stats
```

The field `defence_stats` is intentionally British-spelled for legacy compatibility. User-facing text should say `defense`.

### Keep Legion Roster Lightweight And Separate

Do not connect roster entries to:

- Discord owners
- registered users
- access lists
- normal `/add_alt`
- combat stats

Roster entries must remain simple:

```text
serial
name
seat_tier
parent_serial
type
expiry
```

Do not add slot indexes, locks, troop tier, owner IDs, or main-account flags.

### Preserve Role ID Behavior

Role panels must use saved role IDs first.

Relevant field:

```text
guilds/{guild_id}.role_ids
```

Renaming Discord roles should keep working after `/setup_gotc_roles` has saved role IDs.

### Keep Command Names Streamlined

Current stats commands:

```text
/update_attack
/update_defense
/update_dragon_attack_stats
/update_dragon_defense_stats
```

Do not re-add old names:

```text
/update_defence
/upgrade_dragon_attack_stats
/upgrade_dragon_defense_stats
```

Current export commands:

```text
/account_export
/roster_export
```

Do not add a second generic roster/account export command.

## Coding Workflow

1. Inspect relevant files with `rg` before editing.
2. Keep changes scoped.
3. Prefer existing patterns in the cog.
4. Update `cogs/help.py` whenever adding, renaming, or removing a command.
5. Preserve Firestore paths and existing field names unless a migration is explicitly requested.
6. Run verification commands.
7. Summarize changed files and tests.

## Editing Rules

- Do not modify `.env`, `serviceAccount.json`, or secrets.
- Do not delete user changes.
- Do not run destructive git commands.
- Do not introduce a web dashboard unless explicitly requested.
- Do not add a new database technology.
- Keep Render free-tier behavior in mind: process memory is disposable.

## Verification Commands

Compile:

```powershell
venv\Scripts\python.exe -m compileall main.py database.py cogs services
```

Load all cogs:

```powershell
venv\Scripts\python.exe -c "import os, disnake; from disnake.ext import commands; bot=commands.Bot(command_prefix='!', intents=disnake.Intents.all()); [bot.load_extension('cogs.'+f[:-3]) for f in os.listdir('cogs') if f.endswith('.py')]; print('loaded', len(bot.cogs), 'cogs')"
```

Whitespace:

```powershell
git diff --check
```

Useful search:

```powershell
rg -n "@commands\.slash_command|tasks\.loop|collection\(|document\(" cogs services
```

## Common Implementation Patterns

### Firestore Guild Ref

Many cogs use:

```python
def guild_ref(guild_id):
    return db.collection("guilds").document(str(guild_id))
```

Use that local pattern if present.

### Timestamps

Use:

```python
firestore.SERVER_TIMESTAMP
```

Do not invent string timestamps unless the surrounding code already requires string dates.

### Interaction Responses

For non-modal commands:

```python
await inter.response.defer(ephemeral=True)
...
await inter.edit_original_message(...)
```

For modal commands:

```python
await inter.response.send_modal(...)
```

Do not defer before sending a modal.

### Admin Or Logistics Access

Use:

```python
from services.access_control import has_logistics_access, logistics_denied_message
```

Expected behavior:

- Admin passes.
- Configured Logistics role passes.
- Normal member receives the shared denial message.

### Admin-Only Server Settings

Use disnake permissions for server-level settings:

```python
@commands.has_permissions(manage_guild=True)
```

or administrator where the existing cog uses it.

## Feature-Specific Warnings

### Stats

User-facing text is Americanized:

- `Defense`
- `Offense`

Storage compatibility:

- Keep `defence_stats`.

Dragon defense form currently has exactly three fields:

```text
dragon_def_player_sop
dragon_att_player_sop
dragon_health_player_sop
```

Do not re-add `dragon_def_vs_dragon` unless the user asks.

### Roster

Weekly roster update parsing supports both:

```text
T1:
Name
```

and:

```text
T1: Name | T2: A, B | PROTECT: Name | REMOVE:
```

Do not break CSV parsing while changing text parsing.

### BG Events

Reminder loops must persist sent reminder state to Firestore. Do not rely only on in-memory sets because Render restarts.

### Polls

Poll votes should stay Firestore-backed. Do not put vote state only in a view instance.

### Autorole And Logs

Steward should not create autorole targets. It only assigns an existing configured role.

Join/leave logs should go only to configured `logs_channel`.

## Final Response Checklist

When finishing a coding task, report:

- Main files changed.
- Behavior added or fixed.
- Verification commands run.
- Any deployment notes, especially Discord slash command rename/sync notes.

Keep the final answer concise but precise.

