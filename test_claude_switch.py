"""Tests for claude-switch."""

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the script as a module (no .py extension)
import importlib.util

_script = Path(__file__).parent / "claude-switch"
spec = importlib.util.spec_from_loader(
    "claude_switch",
    importlib.util.spec_from_file_location("claude_switch", _script).submodule_search_locations
    if False else None,
)
# Use a direct loader approach for extensionless scripts
loader = importlib.machinery.SourceFileLoader("claude_switch", str(_script))
spec = importlib.util.spec_from_file_location("claude_switch", str(_script), loader=loader)
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)


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

    with patch.object(cs, "SETTINGS_PATH", settings_path), \
         patch.object(cs, "CONFIG_DIR", config_dir), \
         patch.object(cs, "PROFILES_PATH", profiles_path):
        yield {
            "settings_path": settings_path,
            "profiles_path": profiles_path,
            "config_dir": config_dir,
        }


class TestLoadSettings:
    def test_load_existing(self, tmp_env):
        settings = cs.load_settings()
        assert settings["model"] == "opus"
        assert "ANTHROPIC_BASE_URL" in settings["env"]

    def test_load_missing(self, tmp_path):
        fake_path = tmp_path / "nonexistent.json"
        with patch.object(cs, "SETTINGS_PATH", fake_path):
            with pytest.raises(SystemExit):
                cs.load_settings()


class TestLoadProfiles:
    def test_load_existing(self, tmp_env):
        profiles = cs.load_profiles()
        assert "prod" in profiles
        assert "dev" in profiles

    def test_load_missing(self, tmp_path):
        fake_path = tmp_path / "nonexistent.toml"
        with patch.object(cs, "PROFILES_PATH", fake_path):
            with pytest.raises(SystemExit):
                cs.load_profiles()


class TestFindCurrentProfile:
    def test_match(self, tmp_env):
        settings = cs.load_settings()
        profiles = cs.load_profiles()
        assert cs.find_current_profile(settings, profiles) == "prod"

    def test_no_match(self, tmp_env):
        settings = cs.load_settings()
        settings["env"]["ANTHROPIC_BASE_URL"] = "https://unknown.com"
        profiles = cs.load_profiles()
        assert cs.find_current_profile(settings, profiles) is None


class TestCmdUse:
    def test_switch_profile(self, tmp_env):
        import argparse
        cs.cmd_use(argparse.Namespace(name="dev"))
        settings = cs.load_settings()
        assert settings["model"] == "sonnet"
        assert settings["env"]["ANTHROPIC_BASE_URL"] == "https://dev.example.com"
        assert settings["permissions"]["allow"] == ["Read(//etc/**)"]

    def test_switch_nonexistent(self, tmp_env):
        import argparse
        with pytest.raises(SystemExit):
            cs.cmd_use(argparse.Namespace(name="nonexistent"))


class TestCmdAdd:
    def test_add_profile_with_quoted_value(self, tmp_env):
        import argparse
        cs.cmd_add(argparse.Namespace(
            name="quoted",
            base="https://api.example.com",
            key="sk-test-key",
            auth_token=None,
            model="opus",
            env=['DESCRIPTION=test with "double" quotes'],
            use=False,
        ))
        profiles = cs.load_profiles()
        assert "quoted" in profiles
        assert profiles["quoted"]["env"]["DESCRIPTION"] == 'test with "double" quotes'

    def test_add_profile(self, tmp_env):
        import argparse
        cs.cmd_add(argparse.Namespace(
            name="staging",
            base="https://staging.example.com",
            key="sk-staging-key",
            auth_token=None,
            model="haiku",
            env=["CUSTOM_VAR=hello"],
            use=False,
        ))
        profiles = cs.load_profiles()
        assert "staging" in profiles
        assert profiles["staging"]["model"] == "haiku"
        assert profiles["staging"]["env"]["ANTHROPIC_BASE_URL"] == "https://staging.example.com"
        assert profiles["staging"]["env"]["CUSTOM_VAR"] == "hello"

    def test_add_with_auth_token(self, tmp_env):
        import argparse
        cs.cmd_add(argparse.Namespace(
            name="token_profile",
            base="https://token.example.com",
            key=None,
            auth_token="tok-abc123",
            model="opus",
            env=None,
            use=False,
        ))
        profiles = cs.load_profiles()
        assert "token_profile" in profiles
        assert profiles["token_profile"]["env"]["ANTHROPIC_AUTH_TOKEN"] == "tok-abc123"
        assert "ANTHROPIC_API_KEY" not in profiles["token_profile"]["env"]

    def test_add_key_and_token_conflict(self, tmp_env):
        import argparse
        with pytest.raises(SystemExit):
            cs.cmd_add(argparse.Namespace(
                name="conflict",
                base=None, key="sk-x", auth_token="tok-x",
                model=None, env=None, use=False,
            ))

    def test_add_duplicate(self, tmp_env):
        import argparse
        with pytest.raises(SystemExit):
            cs.cmd_add(argparse.Namespace(
                name="prod", base=None, key=None, auth_token=None,
                model=None, env=None, use=False,
            ))

    def test_add_and_use(self, tmp_env):
        import argparse
        cs.cmd_add(argparse.Namespace(
            name="new",
            base="https://new.example.com",
            key="sk-new",
            auth_token=None,
            model="sonnet",
            env=None,
            use=True,
        ))
        settings = cs.load_settings()
        assert settings["model"] == "sonnet"
        assert settings["env"]["ANTHROPIC_BASE_URL"] == "https://new.example.com"


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
        with patch.object(cs, "SETTINGS_PATH", settings_path), \
             patch.object(cs, "CONFIG_DIR", config_dir), \
             patch.object(cs, "PROFILES_PATH", profiles_path):
            import argparse
            cs.cmd_init(argparse.Namespace())
            assert profiles_path.exists()
            content = profiles_path.read_text()
            assert "profiles.default" in content
            assert "https://x.com" in content

    def test_init_skips_existing(self, tmp_env, capsys):
        import argparse
        cs.cmd_init(argparse.Namespace())
        captured = capsys.readouterr()
        assert "已存在" in captured.err


class TestCmdShow:
    def test_show_current(self, tmp_env, capsys):
        import argparse
        cs.cmd_show(argparse.Namespace())
        captured = capsys.readouterr()
        assert "prod" in captured.out
        assert "opus" in captured.out
        assert "sk-test-...5678" in captured.out

    def test_show_with_anthropic_model(self, tmp_env, capsys):
        import argparse
        settings = cs.load_settings()
        settings["env"]["ANTHROPIC_MODEL"] = "claude-3-opus-20250620"
        settings.pop("model", None)
        cs.save_settings(settings)
        cs.cmd_show(argparse.Namespace())
        captured = capsys.readouterr()
        assert "claude-3-opus-20250620" in captured.out

    def test_show_with_model_specific_env(self, tmp_env, capsys):
        import argparse
        settings = cs.load_settings()
        settings["env"]["ANTHROPIC_MODEL_OPUS"] = "custom-opus-model"
        cs.save_settings(settings)
        cs.cmd_show(argparse.Namespace())
        captured = capsys.readouterr()
        assert "custom-opus-model" in captured.out

    def test_show_no_match(self, tmp_env, capsys):
        import argparse
        settings = cs.load_settings()
        settings["env"]["ANTHROPIC_BASE_URL"] = "https://unknown.com"
        cs.save_settings(settings)
        cs.cmd_show(argparse.Namespace())
        captured = capsys.readouterr()
        assert "不匹配" in captured.out

    def test_show_masks_auth_token(self, tmp_env, capsys):
        import argparse
        settings = cs.load_settings()
        settings["env"] = {"ANTHROPIC_AUTH_TOKEN": "tok-secret-value-1234"}
        cs.save_settings(settings)
        cs.cmd_show(argparse.Namespace())
        captured = capsys.readouterr()
        assert "tok-secr...1234" in captured.out
        assert "tok-secret-value-1234" not in captured.out


class TestCmdList:
    def test_list_profiles(self, tmp_env, capsys):
        import argparse
        cs.cmd_list(argparse.Namespace())
        captured = capsys.readouterr()
        assert "prod" in captured.out
        assert "dev" in captured.out
        assert "*" in captured.out

    def test_list_with_anthropic_model_profile(self, tmp_env, capsys):
        import argparse
        # 添加一个使用 ANTHROPIC_MODEL 的 profile
        cs.cmd_add(argparse.Namespace(
            name="anthropic_model_profile",
            base="https://test.example.com",
            key="sk-test-anthropic",
            auth_token=None,
            model=None,
            anthropic_model="claude-3-5-sonnet-20241022",
            anthropic_small_fast_model="claude-3-5-haiku-20241022",
            env=None,
            use=False,
        ))
        cs.cmd_list(argparse.Namespace())
        captured = capsys.readouterr()
        assert "anthropic_model_profile" in captured.out
        assert "claude-3-5-sonnet-20241022" in captured.out

    def test_list_with_model_specific_env_profile(self, tmp_env, capsys):
        import argparse
        # 添加一个使用 ANTHROPIC_MODEL_OPUS 的 profile
        cs.cmd_add(argparse.Namespace(
            name="model_specific_profile",
            base="https://test.example.com",
            key="sk-test-specific",
            auth_token=None,
            model="opus",
            anthropic_model=None,
            anthropic_small_fast_model=None,
            env=["ANTHROPIC_MODEL_OPUS=custom-opus-2025"],
            use=False,
        ))
        cs.cmd_list(argparse.Namespace())
        captured = capsys.readouterr()
        assert "model_specific_profile" in captured.out
        assert "custom-opus-2025" in captured.out


class TestCmdDelete:
    def test_delete_with_force(self, tmp_env):
        import argparse
        cs.cmd_delete(argparse.Namespace(name="dev", force=True))
        profiles = cs.load_profiles()
        assert "dev" not in profiles
        assert "prod" in profiles

    def test_delete_nonexistent(self, tmp_env):
        import argparse
        with pytest.raises(SystemExit):
            cs.cmd_delete(argparse.Namespace(name="nope", force=True))

    def test_delete_confirm_yes(self, tmp_env, monkeypatch):
        import argparse
        monkeypatch.setattr("builtins.input", lambda _: "y")
        cs.cmd_delete(argparse.Namespace(name="dev", force=False))
        profiles = cs.load_profiles()
        assert "dev" not in profiles

    def test_delete_confirm_no(self, tmp_env, monkeypatch):
        import argparse
        monkeypatch.setattr("builtins.input", lambda _: "n")
        cs.cmd_delete(argparse.Namespace(name="dev", force=False))
        profiles = cs.load_profiles()
        assert "dev" in profiles


class TestSaveProfiles:
    def test_roundtrip(self, tmp_env):
        profiles = cs.load_profiles()
        cs.save_profiles(profiles)
        reloaded = cs.load_profiles()
        assert reloaded == profiles

    def test_save_after_modification(self, tmp_env):
        profiles = cs.load_profiles()
        profiles["new"] = {"model": "haiku", "env": {"ANTHROPIC_BASE_URL": "https://new.com"}}
        cs.save_profiles(profiles)
        reloaded = cs.load_profiles()
        assert "new" in reloaded
        assert reloaded["new"]["model"] == "haiku"
