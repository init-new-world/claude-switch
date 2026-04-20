"""CLI 命令实现。所有函数抛出异常而非 sys.exit，以支持作为库使用。"""

import argparse
from .config import (
    SETTINGS_PATH,
    CONFIG_DIR,
    PROFILES_PATH,
    load_settings,
    save_settings,
    load_profiles,
    save_profiles,
)
from .profiles import (
    get_model_display,
    find_current_profile,
    rename_profile,
    copy_profile,
)
from .errors import ProfileNotFoundError, ProfileExistsError, ClaudeSwitchError


def _mask_sensitive(value: str) -> str:
    """脱敏显示敏感值（API Key、Token 等）。"""
    if len(value) <= 12:
        return value[:4] + "..." + value[-4:]
    return value[:8] + "..." + value[-4:]


def _is_sensitive_key(key_name: str) -> bool:
    """判断是否为敏感字段名。"""
    upper = key_name.upper()
    return any(
        keyword in upper
        for keyword in ("KEY", "TOKEN", "SECRET", "PASSWORD")
    )


def cmd_list() -> str:
    """列出所有 profile，返回可打印的字符串。"""
    settings = load_settings()
    profiles = load_profiles()
    current = find_current_profile(settings, profiles)

    if not profiles:
        return "没有定义任何 profile"

    lines = []
    for name in profiles:
        marker = " *" if name == current else ""
        profile = profiles[name]
        model_display = get_model_display(profile)
        base = profile.get("env", {}).get("ANTHROPIC_BASE_URL", "?")
        lines.append(f"  {name}{marker}  (model={model_display}, base={base})")

    return "\n".join(lines)


def cmd_use(name: str, *, dry_run: bool = False) -> str:
    """切换到指定 profile，返回状态信息。

    dry_run=True 时仅返回将要写入的内容而不实际修改文件。
    """
    profiles = load_profiles()
    if name not in profiles:
        available = ", ".join(profiles.keys())
        raise ProfileNotFoundError(f"profile '{name}' 不存在\n可用: {available}")

    profile = profiles[name]
    settings = load_settings()
    new_settings = {**settings}
    new_settings["env"] = profile.get("env", {})
    if "model" in profile:
        new_settings["model"] = profile["model"]

    if dry_run:
        import json
        return json.dumps(new_settings, indent=2, ensure_ascii=False)

    save_settings(new_settings)
    return f"已切换到 [{name}]"


def cmd_show() -> str:
    """显示当前配置，返回格式化字符串。"""
    settings = load_settings()
    profiles = load_profiles() if PROFILES_PATH.exists() else {}
    current = find_current_profile(settings, profiles) if profiles else None

    lines = []
    if current:
        lines.append(f"当前 profile: {current}")
    else:
        lines.append("当前配置不匹配任何已定义的 profile")

    env = settings.get("env", {})
    model_display = get_model_display(settings)
    lines.append(f"model: {model_display}")

    for k, v in env.items():
        display = _mask_sensitive(v) if _is_sensitive_key(k) else v
        lines.append(f"  {k} = {display}")

    return "\n".join(lines)


def cmd_add(
    name: str,
    *,
    base: str | None = None,
    api_key: str | None = None,
    auth_token: str | None = None,
    model: str | None = None,
    anthropic_model: str | None = None,
    env: list[str] | None = None,
    use: bool = False,
) -> str:
    """添加新 profile。

    先加载现有 profiles，合并新数据后整体写入，避免追加损坏。
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    profiles = load_profiles() if PROFILES_PATH.exists() else {}

    if name in profiles:
        raise ProfileExistsError(name)
    if api_key and auth_token:
        raise ClaudeSwitchError("--key 和 --auth-token 不能同时使用")
    if model and anthropic_model:
        raise ClaudeSwitchError("--model 和 --anthropic-model 不能同时使用")

    env_pairs: dict[str, str] = {}
    if base:
        env_pairs["ANTHROPIC_BASE_URL"] = base
    if api_key:
        env_pairs["ANTHROPIC_API_KEY"] = api_key
    if auth_token:
        env_pairs["ANTHROPIC_AUTH_TOKEN"] = auth_token
    if anthropic_model:
        env_pairs["ANTHROPIC_MODEL"] = anthropic_model

    for item in env or []:
        if "=" not in item:
            raise ClaudeSwitchError(f"--env 格式应为 KEY=VALUE, 得到 '{item}'")
        k, v = item.split("=", 1)
        v = v.strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        env_pairs[k] = v

    new_profile: dict = {}
    if model:
        new_profile["model"] = model
    if env_pairs:
        new_profile["env"] = env_pairs

    profiles[name] = new_profile
    save_profiles(profiles)

    result = f"已添加 profile [{name}]"

    if use:
        use_result = cmd_use(name)
        result += "\n" + use_result

    return result


def cmd_delete(name: str, *, force: bool = False, confirm_fn=None) -> str | None:
    """删除 profile。force=True 跳过确认。

    confirm_fn 为确认回调，用于测试注入。
    返回 None 表示取消。
    """
    profiles = load_profiles()
    if name not in profiles:
        raise ProfileNotFoundError(name)

    if not force:
        response = confirm_fn(f"确认删除 [{name}]? (y/N) ") if confirm_fn else input(f"确认删除 [{name}]? (y/N) ")
        if response.strip().lower() != "y":
            return None

    del profiles[name]
    save_profiles(profiles)
    return f"已删除 profile [{name}]"


def cmd_rename(old_name: str, new_name: str) -> str:
    """重命名 profile。"""
    rename_profile(old_name, new_name)
    return f"已将 [{old_name}] 重命名为 [{new_name}]"


def cmd_copy(source_name: str, target_name: str) -> str:
    """复制 profile。"""
    copy_profile(source_name, target_name)
    return f"已从 [{source_name}] 复制到 [{target_name}]"


def cmd_init() -> str:
    """从当前 settings.json 生成初始 profiles.toml。"""
    if PROFILES_PATH.exists():
        return f"注意: {PROFILES_PATH} 已存在，跳过"

    settings = load_settings()
    env = settings.get("env", {})
    model = settings.get("model", "opus")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    profiles: dict[str, dict] = {"default": {"model": model, "env": env}}
    save_profiles(profiles)

    return f"已生成 {PROFILES_PATH}\n当前配置已保存为 [default] profile"
