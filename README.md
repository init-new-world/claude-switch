# claude-switch

快速切换 `~/.claude/settings.json` 中的 API 配置（env + model）。

预定义多组参数组合，一条命令切换 API 密钥、Base URL、模型等。

[English](README.EN.md)

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

API 密钥和 Auth Token 自动脱敏显示。

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

使用 `--key` 设置 API Key：

```bash
claude-switch add myapi \
  --base "https://api.example.com" \
  --key "sk-xxx" \
  --model sonnet \
  --env "ANTHROPIC_MODEL_OPUS=claude-opus-4-6" \
  --env "ANTHROPIC_MODEL_SONNET=claude-sonnet-4-5-20250929" \
  --env "ANTHROPIC_MODEL_HAIKU=claude-haiku-4-5-20251001"
```

或使用 `--auth-token`（与 `--key` 二选一）：

```bash
claude-switch add myapi \
  --base "https://api.example.com" \
  --auth-token "tok-xxx" \
  --model opus
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

提供菜单式操作，向导流程包括：
- 切换 / 添加 / 删除 profile
- 认证方式选择（API_KEY 或 AUTH_TOKEN）
- 模型 ID 设置（设置 OPUS 后，SONNET 和 HAIKU 默认使用相同值）

## 配置文件格式

`~/.claude-switch/profiles.toml`：

```toml
[profiles.prod]
model = "opus"

[profiles.prod.env]
ANTHROPIC_BASE_URL = "https://api.example.com"
ANTHROPIC_API_KEY = "sk-xxx"
ANTHROPIC_MODEL_OPUS = "claude-opus-4-6"
ANTHROPIC_MODEL_SONNET = "claude-sonnet-4-5-20250929"
ANTHROPIC_MODEL_HAIKU = "claude-haiku-4-5-20251001"

[profiles.dev]
model = "sonnet"

[profiles.dev.env]
ANTHROPIC_BASE_URL = "https://dev.example.com"
ANTHROPIC_AUTH_TOKEN = "tok-yyy"
```

切换时只替换 `env` 和 `model`，`permissions` 等其他配置保持不变。

## 测试

```bash
python3 -m pytest test_claude_switch.py -v
```
