"""交互式向导模式。使用依赖注入使函数可测试。"""

from .config import load_settings, load_profiles, save_profiles, PROFILES_PATH
from .profiles import get_model_display, find_current_profile
from .commands import cmd_use, cmd_add, cmd_show, cmd_delete, cmd_rename, cmd_copy
from .errors import ClaudeSwitchError


def _prompt_choice(
    prompt: str,
    options: list[str],
    *,
    _input=input,
    _print=print,
) -> int:
    """显示编号选项，返回 0-based index。"""
    for i, opt in enumerate(options, 1):
        _print(f"  {i}) {opt}")
    while True:
        try:
            choice = int(_input(f"{prompt} "))
            if 1 <= choice <= len(options):
                return choice - 1
        except (ValueError, EOFError):
            pass
        _print(f"  请输入 1-{len(options)}")


def _prompt_input(
    prompt: str,
    default: str = "",
    *,
    _input=input,
) -> str:
    """带默认值的输入提示。"""
    suffix = f" [{default}]" if default else ""
    val = _input(f"{prompt}{suffix}: ").strip()
    return val or default


def _header(settings: dict, profiles: dict[str, dict], *, _print=print) -> None:
    """显示交互式头部信息。"""
    _print("\n╭─ claude-switch ─╮")
    current = find_current_profile(settings, profiles) if profiles else None
    model_display = get_model_display(settings)
    if current:
        _print(f"│ 当前: {current} (model={model_display})")
    else:
        _print(f"│ 当前: (未匹配) model={model_display}")
    _print("╰─────────────────╯\n")


def _do_switch(
    settings: dict,
    profiles: dict[str, dict],
    *,
    _input=input,
    _print=print,
) -> bool:
    """切换 profile 子流程。返回是否继续。"""
    if not profiles:
        _print("  没有可用的 profile")
        return True

    current = find_current_profile(settings, profiles)
    names = list(profiles.keys())
    display = []
    for n in names:
        profile = profiles[n]
        model_display = get_model_display(profile)
        marker = " *" if n == current else ""
        display.append(f"{n}{marker} (model={model_display})")
    display.append("回到上一层")

    choice = _prompt_choice("切换到:", display, _input=_input, _print=_print)
    if choice < len(names):
        result = cmd_use(names[choice])
        _print(result)
    return True


def _do_add(
    profiles: dict[str, dict],
    *,
    _input=input,
    _print=print,
) -> bool:
    """添加 profile 子流程。返回是否继续。"""
    name = _prompt_input("Profile 名称", _input=_input)
    if not name:
        return True
    if name in profiles:
        _print(f"  [{name}] 已存在")
        return True

    base = _prompt_input("ANTHROPIC_BASE_URL", _input=_input)

    auth_idx = _prompt_choice(
        "认证方式:",
        ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "回到上一层"],
        _input=_input,
        _print=_print,
    )
    if auth_idx == 2:
        return True
    auth_key_name = "ANTHROPIC_API_KEY" if auth_idx == 0 else "ANTHROPIC_AUTH_TOKEN"
    auth_value = _prompt_input(auth_key_name, _input=_input)

    model_config_idx = _prompt_choice(
        "模型配置方式:",
        ["model (opus/sonnet/haiku)", "ANTHROPIC_MODEL", "回到上一层"],
        _input=_input,
        _print=_print,
    )
    if model_config_idx == 2:
        return True

    model = None
    anthropic_model = None
    extra_env: list[str] = []

    if model_config_idx == 0:
        model = _prompt_input("model (opus/sonnet/haiku)", "opus", _input=_input)
        model_opus = _prompt_input("ANTHROPIC_DEFAULT_OPUS_MODEL", _input=_input)
        model_sonnet = _prompt_input("ANTHROPIC_DEFAULT_SONNET_MODEL", model_opus, _input=_input)
        model_haiku = _prompt_input("ANTHROPIC_DEFAULT_HAIKU_MODEL", model_opus, _input=_input)
        if model_opus:
            extra_env.append(f"ANTHROPIC_DEFAULT_OPUS_MODEL={model_opus}")
        if model_sonnet:
            extra_env.append(f"ANTHROPIC_DEFAULT_SONNET_MODEL={model_sonnet}")
        if model_haiku:
            extra_env.append(f"ANTHROPIC_DEFAULT_HAIKU_MODEL={model_haiku}")
    else:
        anthropic_model = _prompt_input("ANTHROPIC_MODEL", _input=_input)
        if anthropic_model:
            extra_env.append(f"ANTHROPIC_MODEL={anthropic_model}")

    while True:
        ev = _prompt_input("额外 env (KEY=VALUE, 留空结束)", _input=_input)
        if not ev:
            break
        extra_env.append(ev)

    try:
        result = cmd_add(
            name=name,
            base=base or None,
            api_key=auth_value if auth_idx == 0 else None,
            auth_token=auth_value if auth_idx == 1 else None,
            model=model or None,
            anthropic_model=anthropic_model or None,
            env=extra_env or None,
            use=False,
        )
        _print(result)
    except ClaudeSwitchError as e:
        _print(f"错误: {e}")
        return True

    switch = _input("立即切换到此 profile? (y/N) ").strip().lower()
    if switch == "y":
        result = cmd_use(name)
        _print(result)
    return True


def _do_delete(
    profiles: dict[str, dict],
    *,
    _input=input,
    _print=print,
) -> bool:
    """删除 profile 子流程。返回是否继续。"""
    if not profiles:
        _print("  没有可用的 profile")
        return True

    names = list(profiles.keys())
    display = []
    for n in names:
        profile = profiles[n]
        model_display = get_model_display(profile)
        display.append(f"{n} (model={model_display})")
    display.append("回到上一层")

    choice = _prompt_choice("删除:", display, _input=_input, _print=_print)
    if choice < len(names):
        confirm = _input(f"  确认删除 [{names[choice]}]? (y/N) ").strip().lower()
        if confirm == "y":
            try:
                result = cmd_delete(names[choice], force=True)
                if result:
                    _print(result)
                # 重新加载 profiles
                profiles.clear()
                profiles.update(load_profiles() if PROFILES_PATH.exists() else {})
            except ClaudeSwitchError as e:
                _print(f"错误: {e}")
    return True


def run_interactive(
    *,
    _input=input,
    _print=print,
) -> None:
    """运行交互式向导主循环。"""
    while True:
        settings = load_settings()
        profiles = load_profiles() if PROFILES_PATH.exists() else {}
        _header(settings, profiles, _print=_print)

        actions = ["切换 profile", "添加 profile", "删除 profile", "查看详情", "退出"]
        idx = _prompt_choice("选择操作:", actions, _input=_input, _print=_print)

        if idx == 4:  # 退出
            break
        elif idx == 0:
            if not _do_switch(settings, profiles, _input=_input, _print=_print):
                break
        elif idx == 1:
            if not _do_add(profiles, _input=_input, _print=_print):
                break
        elif idx == 2:
            if not _do_delete(profiles, _input=_input, _print=_print):
                break
        elif idx == 3:
            result = cmd_show()
            _print(result)
