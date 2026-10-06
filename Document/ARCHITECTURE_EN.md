# Application Structure Document

## 1. Overview

This Discord bot supports server operations, including member, role, and channel management, attachment retrieval, scenario progression, and event notifications. Source code and runtime data are under `Src/`; documentation is under `Document/`.

The entry point is `Src/bot_main.py`. The root-level `run_bot.cmd` can also launch the bot.

The scenario editor under `Src/tools/scenario_editor/` opens a scenario CSV or a folder of CSV files, lets users select scenarios by ID and filename from CSVs directly inside the selected folder, edits steps and branches in a GUI, and saves changes back to their original CSV files. Reaction completion values and branch reactions can be selected from a searchable Unicode emoji list.

## 2. Directory Layout

```text
Src/
  bot_main.py
  event/                   Discord events and commands
  function/                shared logic and services
  config/                  bot settings and scenario data
  templates/
    set/input/              Set CSV inputs
    set/response/           Set response category
    get/input/              Get CSV inputs
    get/result/              Get result category
  test/                    tests
  tools/scenario_editor/   scenario editing GUI (tkinter)
  tools/config_editor/     settings editor GUI (tkinter)
  tools/template_editor/   template CSV editor GUI (tkinter)

Document/
  README_JP.md / README_EN.md
  ARCHITECTURE_JP.md / ARCHITECTURE_EN.md

run_bot.cmd                bot launcher
```

## 3. Main Responsibilities

### `Src/bot_main.py`

Configures the Discord client and Intents, registers slash commands and event handlers, and starts the bot.

### `Src/event/`

Entry points for Discord events and commands. It handles ready, message, reaction, member-join, and voice-state events. Individual command handlers are under `event/on_message/command/`.

### `Src/function/`

Shared processing called by events and commands, including scenario management, Discord operations, file handling, and security-related services.

### `Src/config/`

`config.json` stores bot settings. `scenario_definitions.json` stores scenario definitions, and `scenario_states.json` stores per-server progress.

### `Src/templates/` and `Src/tools/`

CSV artifacts are grouped under `Src/templates/set/input/`, `set/response/`, `get/input/`, and `get/result/`. Set responses and Get results are generated at runtime, saved in their output folders, and sent as Discord attachments. Generated files are excluded from Git. `Src/tools/scenario_editor/` is a utility for reviewing and editing scenario CSV files.

## 4. Command Flow

```text
Discord interaction
  -> Src/event/on_message/command/slash_commands.py
  -> command handler
  -> shared processing in Src/function/
  -> Discord response
```

`slash_commands.py` adapts slash commands to the existing command handlers.

## 5. CSV Get and Set

- The `name,type,category` CSV from `/channel get` can be used with `/channel set`.
- The role-settings CSV from `/server role get` can be used with `/server role set`.
- The scenario CSV from `/scenario export` can be used with `/scenario set`.
- `/member role get` currently replies with a text role list, not CSV. `/member role template` provides the CSV format for `/member role set`.

The channel, member-role, and server-role `set` commands return the input CSV with `result` and `reason` columns added to each row. Scenario registration is a batch operation, so its overall success or failure reason is recorded on every data row. Existing columns with those names are overwritten instead of duplicated.

For channel settings, when one or more role columns are populated, only the listed roles retain access; existing grants for unlisted roles are removed. If all role columns are blank, existing role permissions are unchanged.

## 6. Scenario Persistence and Progression

Scenario definitions are stored in `Src/config/scenario_definitions.json`; per-server progress is stored in `Src/config/scenario_states.json`.

```text
/scenario set -> register or update CSV -> scenario_definitions.json
/scenario start -> create initial state -> scenario_states.json
message or reaction -> determine and send the next step
```

`/scenario set` preserves existing definitions and updates entries with matching scenario IDs and step numbers.

## 7. Adding Features

1. Add a command or event entry under `Src/event/`
2. Implement shared processing in `Src/function/`
3. Update `Src/config/` or CSV templates when needed
4. Register slash commands in `slash_commands.py`
