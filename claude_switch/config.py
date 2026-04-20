"""配置读写：settings.json 和 profiles.toml 的加载/保存/备份。"""

import json
import tomllib
from pathlib import Path
from .errors import SettingsNotFoundError, ProfilesNotFoundError

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
CONFIG_DIR = Path.home() / ".claude-switch"
PROFILES_PATH = CONFIG_DIR / "profiles.toml"
BACKUP_SUFFIX = ".bak"


def load_settings() -> dict:
    """加载 settings.json，文件不存在时抛异常。"""
    if not SETTINGS_PATH.exists():
        raise SettingsNotFoundError(str(SETTINGS_PATH))
    return json.loads(SETTINGS_PATH.read_text())


def save_settings(settings: dict, *, backup: bool = True) -> None:
    """保存 settings.json，默认先备份旧文件到 .bak。"""
    if backup and SETTINGS_PATH.exists():
        _backup_file(SETTINGS_PATH)
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")


def _backup_file(path: Path) -> None:
    """将文件复制到 path.bak。"""
    backup_path = Path(str(path) + BACKUP_SUFFIX)
    backup_path.write_bytes(path.read_bytes())


def load_profiles() -> dict[str, dict]:
    """加载 profiles.toml，返回 {name: {model, env: {}}} 字典。

    文件不存在时抛异常。
    """
    if not PROFILES_PATH.exists():
        raise ProfilesNotFoundError(str(PROFILES_PATH))
    with open(PROFILES_PATH, "rb") as f:
        data = tomllib.load(f)
    return data.get("profiles", {})


def save_profiles(profiles: dict[str, dict]) -> None:
    """将 profiles 写入 profiles.toml。

    使用原子写入：先写临时文件，再 rename，避免写入中断损坏文件。
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    content = _generate_toml(profiles)
    tmp_path = Path(str(PROFILES_PATH) + ".tmp")
    tmp_path.write_text(content)
    tmp_path.replace(PROFILES_PATH)


def _escape_toml_string(s: str) -> str:
    """转义 TOML 基本字符串中的特殊字符。"""
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\t", "\\t")
    s = s.replace("\r", "\\r")
    return s


def _generate_toml(profiles: dict[str, dict]) -> str:
    """从 profiles dict 生成 TOML 内容。"""
    lines = ["# claude-switch profiles\n"]
    for name, profile in profiles.items():
        lines.append(f"\n[profiles.{name}]\n")
        if "model" in profile:
            escaped_model = _escape_toml_string(profile["model"])
            lines.append(f'model = "{escaped_model}"\n')
        env = profile.get("env", {})
        if env:
            lines.append(f"\n[profiles.{name}.env]\n")
            for k, v in env.items():
                escaped_v = _escape_toml_string(v)
                lines.append(f'{k} = "{escaped_v}"\n')
    return "".join(lines)
