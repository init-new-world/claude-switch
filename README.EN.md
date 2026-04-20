# claude-switch

Quickly switch API configurations (env + model) in `~/.claude/settings.json`.

Pre-define multiple parameter sets and switch API keys, Base URLs, and models with a single command.

[中文](README.md)

## Install

```bash
git clone <repo-url> && cd claude-switch

# Option 1: symlink to PATH (recommended)
ln -s "$(pwd)/claude-switch" ~/.local/bin/claude-switch

# Option 2: copy project to PATH
cp claude-switch ~/.local/bin/
cp -r claude_switch ~/.local/bin/

# Option 3: run directly
./claude-switch
```

Requires Python 3.11+ (uses built-in `tomllib`, no extra dependencies).

## Usage

### Initialize

Generate initial config from current `~/.claude/settings.json`:

```bash
claude-switch init
```

Creates `~/.claude-switch/profiles.toml` with current settings saved as `[default]` profile.

### Show current config

```bash
claude-switch show
```

API keys and auth tokens are automatically masked in output.

### List all profiles

```bash
claude-switch list
```

`*` marks the currently active profile.

### Switch profile

```bash
claude-switch use <name>           # switch directly
claude-switch use <name> --dry-run # preview changes without applying
```

### Add a new profile

Using `--key` for API Key:

```bash
claude-switch add myapi \
  --base "https://api.example.com" \
  --key "sk-xxx" \
  --model sonnet \
  --env "ANTHROPIC_DEFAULT_OPUS_MODEL=claude-opus-4-6" \
  --env "ANTHROPIC_DEFAULT_SONNET_MODEL=claude-sonnet-4-5-20250929" \
  --env "ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-haiku-4-5-20251001"
```

Or using `--auth-token` (mutually exclusive with `--key`):

```bash
claude-switch add myapi \
  --base "https://api.example.com" \
  --auth-token "tok-xxx" \
  --model opus
```

Switch immediately after adding:

```bash
claude-switch add myapi --base "..." --key "..." --model opus --use
```

### Delete a profile

```bash
claude-switch delete <name>      # with confirmation prompt
claude-switch delete <name> -f   # skip confirmation
```

### Rename a profile

```bash
claude-switch rename <old-name> <new-name>
```

### Copy a profile

```bash
claude-switch copy <source> <target>
```

### Interactive wizard

```bash
claude-switch interactive   # or shorthand: claude-switch i
```

Menu-driven interface with guided flows for:
- Switching / adding / deleting profiles
- Auth method selection (API_KEY or AUTH_TOKEN)
- Model ID setup (after setting OPUS, SONNET and HAIKU default to the same value)

### Show version

```bash
claude-switch --version
```

## Config format

`~/.claude-switch/profiles.toml`:

```toml
[profiles.prod]
model = "opus"

[profiles.prod.env]
ANTHROPIC_BASE_URL = "https://api.example.com"
ANTHROPIC_API_KEY = "sk-xxx"
ANTHROPIC_DEFAULT_OPUS_MODEL = "claude-opus-4-6"
ANTHROPIC_DEFAULT_SONNET_MODEL = "claude-sonnet-4-5-20250929"
ANTHROPIC_DEFAULT_HAIKU_MODEL = "claude-haiku-4-5-20251001"

[profiles.dev]
model = "sonnet"

[profiles.dev.env]
ANTHROPIC_BASE_URL = "https://dev.example.com"
ANTHROPIC_AUTH_TOKEN = "tok-yyy"
```

Only `env` and `model` are replaced on switch; `permissions` and other fields are preserved. A backup is automatically saved to `settings.json.bak` before each write.

## Use as a Python library

```python
from claude_switch.commands import cmd_use, cmd_list
from claude_switch.errors import ClaudeSwitchError

try:
    print(cmd_list())
    cmd_use("prod")
except ClaudeSwitchError as e:
    print(f"Error: {e}")
```

## Tests

```bash
python3 -m pytest test_claude_switch.py -v
```
