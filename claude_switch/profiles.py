"""Profile 操作：查找、匹配、重命名、复制。"""

from .config import load_settings, load_profiles, save_profiles
from .errors import ProfileNotFoundError, ProfileExistsError


def get_model_display(profile_or_env: dict) -> str:
    """从 profile dict 或 settings 中提取用于显示的模型值。

    优先级：ANTHROPIC_MODEL > model key 对应的 ANTHROPIC_DEFAULT_<MODEL>_MODEL > model 值本身。
    """
    env = profile_or_env.get("env", profile_or_env)

    if isinstance(env, dict) and "ANTHROPIC_MODEL" in env:
        return env["ANTHROPIC_MODEL"]

    model = profile_or_env.get("model")
    if model:
        model_key = f"ANTHROPIC_DEFAULT_{model.upper()}_MODEL"
        if isinstance(env, dict) and model_key in env:
            return env[model_key]
        return model

    return "?"


def find_current_profile(settings: dict, profiles: dict[str, dict]) -> str | None:
    """查找当前 settings 匹配的 profile 名称。

    匹配规则：profile 中定义的 env 键值对必须完全一致地出现在 settings.env 中，
    且 model 必须一致。settings.env 可以有额外键（宽松匹配）。
    """
    current_env = settings.get("env", {})
    current_model = settings.get("model")

    for name, profile in profiles.items():
        profile_env = profile.get("env", {})
        profile_model = profile.get("model")

        if profile_model != current_model:
            continue

        # profile 中所有 env 键必须在当前 settings 中存在且值一致
        if all(current_env.get(k) == v for k, v in profile_env.items()):
            return name

    return None


def rename_profile(old_name: str, new_name: str) -> None:
    """重命名 profile。"""
    profiles = load_profiles()
    if old_name not in profiles:
        raise ProfileNotFoundError(old_name)
    if new_name in profiles:
        raise ProfileExistsError(new_name)

    profiles[new_name] = profiles.pop(old_name)
    save_profiles(profiles)


def copy_profile(source_name: str, target_name: str) -> dict:
    """复制 profile 到新名称，返回新 profile 数据。"""
    profiles = load_profiles()
    if source_name not in profiles:
        raise ProfileNotFoundError(source_name)
    if target_name in profiles:
        raise ProfileExistsError(target_name)

    import copy
    profiles[target_name] = copy.deepcopy(profiles[source_name])
    save_profiles(profiles)
    return profiles[target_name]
