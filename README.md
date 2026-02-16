# claude-switch

快速切换 `~/.claude/settings.json` 中的 API 配置（env + model）。

预定义多组参数组合，一条命令切换 API 密钥、Base URL、模型等。

## 安装

```bash
# 克隆仓库
git clone <repo-url> && cd claude-switch

# 方式一：复制到 PATH（推荐）
cp claude-switch ~/.local/bin/

# 方式二：symlink 到 PATH
ln -s "$(pwd)/claude-switch" ~/.local/bin/claude-switch

# 方式三：直接运行
./claude-switch
```

要求：Python 3.11+（使用内置 `tomllib`，无额外依赖）。

## 使用

### 初始化

从当前 `~/.claude/settings.json` 生成初始配置：

```bash
claude-switch init
```

生成 `~/.claude-switch/profiles.toml`，当前配置保存为 `[default]` profile。

### 查看当前配置

```bash
claude-switch show
```

### 列出所有 profile

```bash
claude-switch list
```

`*` 标记当前激活的 profile。

### 切换 profile

```bash
claude-switch use <name>
```

### 添加新 profile

```bash
claude-switch add myapi \
  --base "https://api.example.com" \
  --key "sk-xxx" \
  --model sonnet \
  --env "ANTHROPIC_MODEL_SONNET=claude-sonnet-4-5-20250929"
```

添加后立即切换：

```bash
claude-switch add myapi --base "..." --key "..." --model opus --use
```

### 删除 profile

```bash
claude-switch delete <name>      # 带确认提示
claude-switch delete <name> -f   # 跳过确认
```

### 交互式向导

```bash
claude-switch interactive   # 或简写 claude-switch i
```

提供菜单式操作：切换、添加、删除 profile，无需记命令。

## 配置文件格式

`~/.claude-switch/profiles.toml`：

```toml
[profiles.prod]
model = "opus"

[profiles.prod.env]
ANTHROPIC_BASE_URL = "https://api.example.com"
ANTHROPIC_API_KEY = "sk-xxx"
ANTHROPIC_MODEL_OPUS = "claude-opus-4-6"

[profiles.dev]
model = "sonnet"

[profiles.dev.env]
ANTHROPIC_BASE_URL = "https://dev.example.com"
ANTHROPIC_API_KEY = "sk-yyy"
```

切换时只替换 `env` 和 `model`，`permissions` 等其他配置保持不变。

## 测试

```bash
python3 -m pytest test_claude_switch.py -v
```

---

# claude-switch (English)

Quickly switch API configurations (env + model) in `~/.claude/settings.json`.

Pre-define multiple parameter sets and switch API keys, Base URLs, and models with a single command.

## Install

```bash
git clone <repo-url> && cd claude-switch

# Option 1: copy to PATH (recommended)
cp claude-switch ~/.local/bin/

# Option 2: symlink
ln -s "$(pwd)/claude-switch" ~/.local/bin/claude-switch
```

Requires Python 3.11+ (uses built-in `tomllib`, no extra dependencies).

## Usage

```bash
claude-switch init          # Generate initial profiles from current settings
claude-switch list          # List all profiles (* = active)
claude-switch show          # Show current configuration
claude-switch use <name>    # Switch to a profile
claude-switch add <name> \  # Add a new profile
  --base <url> --key <key> --model <model> \
  --env KEY=VALUE --use
claude-switch delete <name> # Delete a profile (-f to skip confirm)
claude-switch interactive   # Interactive wizard (alias: i)
```

## Config format

`~/.claude-switch/profiles.toml`:

```toml
[profiles.prod]
model = "opus"

[profiles.prod.env]
ANTHROPIC_BASE_URL = "https://api.example.com"
ANTHROPIC_API_KEY = "sk-xxx"
```

Only `env` and `model` are replaced on switch; `permissions` and other fields are preserved.
