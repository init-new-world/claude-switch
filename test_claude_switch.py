"""Tests for claude-switch package."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add parent dir to path for test imports
sys.path.insert(0, str(Path(__file__).parent))

from claude_switch.config import (
    SETTINGS_PATH,
    CONFIG_DIR,
    PROFILES_PATH,
    load_settings,
    save_settings,
    load_profiles,
    save_profiles,
    _generate_toml,
    _escape_toml_string,
)
from claude_switch.profiles import (
    get_model_display,
    find_current_profile,
    rename_profile,
    copy_profile,
)
from claude_switch.commands import (
    cmd_list,
    cmd_use,
    cmd_show,
    cmd_add,
    cmd_delete,
    cmd_rename,
    cmd_copy,
    cmd_init,
    _mask_sensitive,
    _is_sensitive_key,
)
from claude_switch.interactive import (
    _prompt_choice,
    _prompt_input,
    run_interactive,
)
from claude_switch.main import build_parser, dispatch
from claude_switch.errors import (
    ClaudeSwitchError,
    ProfileNotFoundError,
    ProfileExistsError,
    SettingsNotFoundError,
    ProfilesNotFoundError,
)


@pytest.fixture
def tmp_env(tmp_path):
    """Set up temp settings.json and profiles.toml."""
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir()
    config_dir = tmp_path / ".claude-switch"
    config_dir.mkdir()

    settings = {
        "env": {
            "ANTHROPIC_BASE_URL": "https://api.example.com",
            "ANTHROPIC_API_KEY": "sk-test-key-12345678",
        },
        "permissions": {"allow": ["Read(//etc/**)"]},
        "model": "opus",
    }
    settings_path = settings_dir / "settings.json"
    settings_path.write_text(json.dumps(settings, indent=2))

    profiles_toml = """\
[profiles.prod]
model = "opus"

[profiles.prod.env]
ANTHROPIC_BASE_URL = "https://api.example.com"
ANTHROPIC_API_KEY = "sk-test-key-12345678"

[profiles.dev]
model = "sonnet"

[profiles.dev.env]
ANTHROPIC_BASE_URL = "https://dev.example.com"
ANTHROPIC_API_KEY = "sk-dev-key-99999999"
"""
    profiles_path = config_dir / "profiles.toml"
    profiles_path.write_text(profiles_toml)

    with patch("claude_switch.config.SETTINGS_PATH", settings_path), \
         patch("claude_switch.config.CONFIG_DIR", config_dir), \
         patch("claude_switch.config.PROFILES_PATH", profiles_path), \
         patch("claude_switch.commands.SETTINGS_PATH", settings_path), \
         patch("claude_switch.commands.CONFIG_DIR", config_dir), \
         patch("claude_switch.commands.PROFILES_PATH", profiles_path), \
         patch("claude_switch.profiles.load_settings") as mock_load_s, \
         patch("claude_switch.profiles.load_profiles") as mock_load_p, \
         patch("claude_switch.profiles.save_profiles") as mock_save_p:
        # Wire up profile mocks to use real functions with patched paths
        mock_load_s.side_effect = lambda: json.loads(settings_path.read_text())
        mock_load_p.side_effect = lambda: load_profiles.__wrapped__ if hasattr(load_profiles, '__wrapped__') else _load_profiles_with_path(profiles_path)
        mock_save_p.side_effect = lambda profiles: _save_profiles_with_path(profiles, profiles_path, config_dir)

        yield {
            "settings_path": settings_path,
            "profiles_path": profiles_path,
            "config_dir": config_dir,
        }


def _load_profiles_with_path(path):
    """Helper to load profiles with a specific path."""
    import tomllib
    if not path.exists():
        raise ProfilesNotFoundError(str(path))
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data.get("profiles", {})


def _save_profiles_with_path(profiles, path, config_dir):
    """Helper to save profiles with a specific path."""
    config_dir.mkdir(parents=True, exist_ok=True)
    content = _generate_toml(profiles)
    tmp_path = Path(str(path) + ".tmp")
    tmp_path.write_text(content)
    tmp_path.replace(path)


# ── Error Tests ──


class TestErrors:
    def test_claude_switch_error(self):
        e = ClaudeSwitchError("test")
        assert str(e) == "test"
        assert e.exit_code == 1

    def test_profile_not_found_error(self):
        e = ProfileNotFoundError("foo")
        assert "foo" in str(e)
        assert e.exit_code == 1

    def test_profile_exists_error(self):
        e = ProfileExistsError("foo")
        assert "foo" in str(e)

    def test_settings_not_found_error(self):
        e = SettingsNotFoundError("/path")
        assert "/path" in str(e)

    def test_profiles_not_found_error(self):
        e = ProfilesNotFoundError("/path")
        assert "/path" in str(e)


# ── Config Tests ──


class TestConfig:
    def test_load_settings(self, tmp_env):
        settings = load_settings()
        assert settings["model"] == "opus"
        assert "ANTHROPIC_BASE_URL" in settings["env"]

    def test_load_settings_missing(self, tmp_path):
        fake_path = tmp_path / "nonexistent.json"
        with patch("claude_switch.config.SETTINGS_PATH", fake_path):
            with pytest.raises(SettingsNotFoundError):
                load_settings()

    def test_save_settings_with_backup(self, tmp_env):
        settings = load_settings()
        settings["model"] = "haiku"
        save_settings(settings)
        # Check backup was created
        backup_path = Path(str(tmp_env["settings_path"]) + ".bak")
        assert backup_path.exists()
        backup_data = json.loads(backup_path.read_text())
        assert backup_data["model"] == "opus"

    def test_load_profiles(self, tmp_env):
        profiles = load_profiles()
        assert "prod" in profiles
        assert "dev" in profiles

    def test_load_profiles_missing(self, tmp_path):
        fake_path = tmp_path / "nonexistent.toml"
        with patch("claude_switch.config.PROFILES_PATH", fake_path):
            with pytest.raises(ProfilesNotFoundError):
                load_profiles()

    def test_save_profiles_atomic(self, tmp_env):
        profiles = load_profiles()
        profiles["new"] = {"model": "haiku", "env": {}}
        save_profiles(profiles)
        reloaded = load_profiles()
        assert "new" in reloaded

    def test_escape_toml_string(self):
        assert _escape_toml_string('hello "world"') == 'hello \\"world\\"'
        assert _escape_toml_string("back\\slash") == "back\\\\slash"
        assert _escape_toml_string("line\nbreak") == "line\\nbreak"

    def test_generate_toml_roundtrip(self, tmp_env):
        profiles = load_profiles()
        toml_str = _generate_toml(profiles)
        assert "[profiles.prod]" in toml_str
        assert '[profiles.dev]' in toml_str
        assert 'model = "opus"' in toml_str


# ── Profiles Tests ──


class TestGetModelDisplay:
    def test_anthropic_model_first(self):
        profile = {"model": "opus", "env": {"ANTHROPIC_MODEL": "custom-model"}}
        assert get_model_display(profile) == "custom-model"

    def test_fallback_to_specific_model_env(self):
        profile = {"model": "opus", "env": {"ANTHROPIC_DEFAULT_OPUS_MODEL": "my-opus"}}
        assert get_model_display(profile) == "my-opus"

    def test_fallback_to_model_value(self):
        profile = {"model": "opus", "env": {}}
        assert get_model_display(profile) == "opus"

    def test_no_model(self):
        profile = {"env": {}}
        assert get_model_display(profile) == "?"


class TestFindCurrentProfile:
    def test_exact_match(self, tmp_env):
        settings = load_settings()
        profiles = load_profiles()
        assert find_current_profile(settings, profiles) == "prod"

    def test_extra_env_in_settings(self, tmp_env):
        """Relaxed matching: settings can have extra env vars."""
        settings = load_settings()
        settings["env"]["EXTRA_VAR"] = "should-not-affect-match"
        profiles = load_profiles()
        assert find_current_profile(settings, profiles) == "prod"

    def test_model_mismatch(self, tmp_env):
        settings = load_settings()
        settings["model"] = "haiku"
        profiles = load_profiles()
        assert find_current_profile(settings, profiles) is None

    def test_env_value_mismatch(self, tmp_env):
        settings = load_settings()
        settings["env"]["ANTHROPIC_API_KEY"] = "different-key"
        profiles = load_profiles()
        assert find_current_profile(settings, profiles) is None


# ── Commands Tests ──


class TestCmdList:
    def test_list_profiles(self, tmp_env, capsys):
        result = cmd_list()
        assert "prod" in result
        assert "dev" in result

    def test_list_empty(self, tmp_env):
        save_profiles({})
        result = cmd_list()
        assert "没有定义" in result


class TestCmdUse:
    def test_switch_profile(self, tmp_env):
        result = cmd_use("dev")
        assert "dev" in result
        settings = load_settings()
        assert settings["model"] == "sonnet"
        assert settings["env"]["ANTHROPIC_BASE_URL"] == "https://dev.example.com"
        assert settings["permissions"]["allow"] == ["Read(//etc/**)"]

    def test_switch_nonexistent(self, tmp_env):
        with pytest.raises(ProfileNotFoundError):
            cmd_use("nonexistent")

    def test_dry_run(self, tmp_env):
        result = cmd_use("dev", dry_run=True)
        data = json.loads(result)
        assert data["model"] == "sonnet"
        # Verify actual file unchanged
        settings = load_settings()
        assert settings["model"] == "opus"


class TestCmdShow:
    def test_show_current(self, tmp_env):
        result = cmd_show()
        assert "prod" in result
        assert "opus" in result
        assert "sk-test-...5678" in result

    def test_show_masks_auth_token(self, tmp_env):
        settings = load_settings()
        settings["env"] = {"ANTHROPIC_AUTH_TOKEN": "tok-secret-value-1234"}
        save_settings(settings)
        result = cmd_show()
        assert "tok-secr...1234" in result
        assert "tok-secret-value-1234" not in result

    def test_show_no_match(self, tmp_env):
        settings = load_settings()
        settings["env"]["ANTHROPIC_BASE_URL"] = "https://unknown.com"
        save_settings(settings)
        result = cmd_show()
        assert "不匹配" in result


class TestCmdAdd:
    def test_add_profile(self, tmp_env):
        result = cmd_add(
            name="staging",
            base="https://staging.example.com",
            api_key="sk-staging-key",
            model="haiku",
            env=["CUSTOM_VAR=hello"],
        )
        assert "staging" in result
        profiles = load_profiles()
        assert "staging" in profiles
        assert profiles["staging"]["model"] == "haiku"
        assert profiles["staging"]["env"]["CUSTOM_VAR"] == "hello"

    def test_add_with_auth_token(self, tmp_env):
        cmd_add(name="token_p", base="https://t.com", auth_token="tok-abc", model="opus")
        profiles = load_profiles()
        assert profiles["token_p"]["env"]["ANTHROPIC_AUTH_TOKEN"] == "tok-abc"

    def test_add_does_not_append_to_file(self, tmp_env):
        """Verify that add loads existing data, merges, and writes (no append corruption)."""
        original_content = tmp_env["profiles_path"].read_text()
        cmd_add(name="new_one", base="https://x.com", api_key="sk-x", model="sonnet")
        # File should still be valid TOML
        profiles = load_profiles()
        assert "prod" in profiles
        assert "dev" in profiles
        assert "new_one" in profiles

    def test_add_duplicate(self, tmp_env):
        with pytest.raises(ProfileExistsError):
            cmd_add(name="prod", base=None, api_key=None, model=None)

    def test_add_key_and_token_conflict(self, tmp_env):
        with pytest.raises(ClaudeSwitchError, match="不能同时使用"):
            cmd_add(name="c", api_key="sk-x", auth_token="tok-x")

    def test_add_and_use(self, tmp_env):
        cmd_add(
            name="new2",
            base="https://new.example.com",
            api_key="sk-new",
            model="sonnet",
            use=True,
        )
        settings = load_settings()
        assert settings["model"] == "sonnet"
        assert settings["env"]["ANTHROPIC_BASE_URL"] == "https://new.example.com"

    def test_add_with_anthropic_model(self, tmp_env):
        cmd_add(
            name="am",
            base="https://x.com",
            api_key="sk-x",
            anthropic_model="claude-3-opus-20250620",
        )
        profiles = load_profiles()
        assert profiles["am"]["env"]["ANTHROPIC_MODEL"] == "claude-3-opus-20250620"


class TestCmdDelete:
    def test_delete_with_force(self, tmp_env):
        result = cmd_delete("dev", force=True)
        assert "dev" in result
        profiles = load_profiles()
        assert "dev" not in profiles

    def test_delete_nonexistent(self, tmp_env):
        with pytest.raises(ProfileNotFoundError):
            cmd_delete("nope", force=True)

    def test_delete_confirm_yes(self, tmp_env):
        result = cmd_delete("dev", confirm_fn=lambda _: "y")
        assert result is not None
        profiles = load_profiles()
        assert "dev" not in profiles

    def test_delete_confirm_no(self, tmp_env):
        result = cmd_delete("dev", confirm_fn=lambda _: "n")
        assert result is None
        profiles = load_profiles()
        assert "dev" in profiles


class TestCmdRename:
    def test_rename_success(self, tmp_env):
        result = cmd_rename("dev", "development")
        assert "dev" in result
        assert "development" in result
        profiles = load_profiles()
        assert "dev" not in profiles
        assert "development" in profiles

    def test_rename_source_not_found(self, tmp_env):
        with pytest.raises(ProfileNotFoundError):
            cmd_rename("nope", "yep")

    def test_rename_target_exists(self, tmp_env):
        with pytest.raises(ProfileExistsError):
            cmd_rename("dev", "prod")


class TestCmdCopy:
    def test_copy_success(self, tmp_env):
        result = cmd_copy("dev", "dev_copy")
        assert "dev" in result
        assert "dev_copy" in result
        profiles = load_profiles()
        assert "dev_copy" in profiles
        assert profiles["dev_copy"]["model"] == profiles["dev"]["model"]
        assert profiles["dev_copy"]["env"] == profiles["dev"]["env"]
        # Ensure deep copy (modifying copy doesn't affect original)
        profiles["dev_copy"]["env"]["ANTHROPIC_BASE_URL"] = "https://changed.com"
        assert profiles["dev"]["env"]["ANTHROPIC_BASE_URL"] == "https://dev.example.com"

    def test_copy_source_not_found(self, tmp_env):
        with pytest.raises(ProfileNotFoundError):
            cmd_copy("nope", "yep")

    def test_copy_target_exists(self, tmp_env):
        with pytest.raises(ProfileExistsError):
            cmd_copy("dev", "prod")


class TestCmdInit:
    def test_init_creates_file(self, tmp_path):
        settings_dir = tmp_path / ".claude"
        settings_dir.mkdir()
        config_dir = tmp_path / ".claude-switch"
        profiles_path = config_dir / "profiles.toml"
        settings_path = settings_dir / "settings.json"
        settings_path.write_text(json.dumps({
            "env": {"ANTHROPIC_BASE_URL": "https://x.com", "ANTHROPIC_API_KEY": "sk-x"},
            "model": "opus",
        }))

        with patch("claude_switch.config.SETTINGS_PATH", settings_path), \
             patch("claude_switch.config.CONFIG_DIR", config_dir), \
             patch("claude_switch.config.PROFILES_PATH", profiles_path), \
             patch("claude_switch.commands.SETTINGS_PATH", settings_path), \
             patch("claude_switch.commands.CONFIG_DIR", config_dir), \
             patch("claude_switch.commands.PROFILES_PATH", profiles_path):
            result = cmd_init()
            assert "已生成" in result
            assert profiles_path.exists()
            content = profiles_path.read_text()
            assert "profiles.default" in content

    def test_init_skips_existing(self, tmp_env):
        result = cmd_init()
        assert "已存在" in result


class TestMasking:
    def test_mask_sensitive_normal(self):
        assert _mask_sensitive("sk-test-key-12345678") == "sk-test-...5678"

    def test_mask_sensitive_short(self):
        assert _mask_sensitive("abc12345defg") == "abc1...defg"

    def test_is_sensitive_key(self):
        assert _is_sensitive_key("ANTHROPIC_API_KEY") is True
        assert _is_sensitive_key("ANTHROPIC_AUTH_TOKEN") is True
        assert _is_sensitive_key("MY_SECRET") is True
        assert _is_sensitive_key("DB_PASSWORD") is True
        assert _is_sensitive_key("ANTHROPIC_BASE_URL") is False
        assert _is_sensitive_key("ANTHROPIC_MODEL") is False


# ── Interactive Tests ──


class TestInteractive:
    def test_prompt_choice_basic(self):
        inputs = iter(["1"])
        result = _prompt_choice("选择:", ["a", "b"], _input=lambda _: next(inputs))
        assert result == 0

    def test_prompt_choice_invalid_then_valid(self):
        inputs = iter(["5", "abc", "2"])
        result = _prompt_choice("选择:", ["a", "b", "c"], _input=lambda _: next(inputs))
        assert result == 1

    def test_prompt_input_with_default(self):
        result = _prompt_input("Name", "default", _input=lambda _: "")
        assert result == "default"

    def test_prompt_input_custom_value(self):
        result = _prompt_input("Name", _input=lambda _: "custom")
        assert result == "custom"

    def test_run_interactive_exit(self, capsys):
        """Test interactive exits immediately on '退出'."""
        inputs = iter(["5"])  # "退出" is option 5
        run_interactive(_input=lambda _: next(inputs))
        captured = capsys.readouterr()
        assert "claude-switch" in captured.out

    def test_run_interactive_show_details(self, capsys):
        """Test interactive can enter show details then exit."""
        inputs = iter(["4", "5"])  # "查看详情" then "退出"
        run_interactive(_input=lambda _: next(inputs))
        captured = capsys.readouterr()
        assert "当前" in captured.out


# ── Main / Argparse Tests ──


class TestArgparse:
    def test_parser_list(self):
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"

    def test_parser_use(self):
        parser = build_parser()
        args = parser.parse_args(["use", "prod"])
        assert args.command == "use"
        assert args.name == "prod"
        assert args.dry_run is False

    def test_parser_use_dry_run(self):
        parser = build_parser()
        args = parser.parse_args(["use", "prod", "--dry-run"])
        assert args.dry_run is True

    def test_parser_rename(self):
        parser = build_parser()
        args = parser.parse_args(["rename", "old", "new"])
        assert args.command == "rename"
        assert args.old_name == "old"
        assert args.new_name == "new"

    def test_parser_copy(self):
        parser = build_parser()
        args = parser.parse_args(["copy", "src", "dst"])
        assert args.command == "copy"
        assert args.source == "src"
        assert args.target == "dst"

    def test_parser_interactive_alias(self):
        parser = build_parser()
        args = parser.parse_args(["i"])
        assert args.command == "i"  # argparse stores alias value as-is

    def test_parser_version(self, capsys):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--version"])

    def test_parser_empty(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None
