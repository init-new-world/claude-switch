"""自定义异常类，替代 sys.exit，使模块可作为库使用。"""


class ClaudeSwitchError(Exception):
    """claude-switch 通用错误。"""

    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


class ProfileNotFoundError(ClaudeSwitchError):
    """指定的 profile 不存在。"""

    def __init__(self, name: str):
        super().__init__(f"profile '{name}' 不存在", exit_code=1)


class ProfileExistsError(ClaudeSwitchError):
    """profile 已存在。"""

    def __init__(self, name: str):
        super().__init__(f"profile '{name}' 已存在", exit_code=1)


class SettingsNotFoundError(ClaudeSwitchError):
    """settings.json 不存在。"""

    def __init__(self, path: str):
        super().__init__(f"{path} 不存在\n运行 'claude-switch init' 生成初始配置", exit_code=1)


class ProfilesNotFoundError(ClaudeSwitchError):
    """profiles.toml 不存在。"""

    def __init__(self, path: str):
        super().__init__(f"{path} 不存在\n运行 'claude-switch init' 生成初始配置", exit_code=1)
