"""argparse 入口和命令分发。"""

import argparse
import sys

from . import __version__
from .commands import (
    cmd_list,
    cmd_use,
    cmd_show,
    cmd_add,
    cmd_delete,
    cmd_init,
    cmd_rename,
    cmd_copy,
)
from .interactive import run_interactive
from .errors import ClaudeSwitchError


def build_parser() -> argparse.ArgumentParser:
    """构建 ArgumentParser。"""
    parser = argparse.ArgumentParser(
        prog="claude-switch",
        description="切换 ~/.claude/settings.json 中的 env 和 model 配置",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="列出所有 profile")

    p_use = sub.add_parser("use", help="切换到指定 profile")
    p_use.add_argument("name", help="profile 名称")
    p_use.add_argument("--dry-run", action="store_true", help="预览将要写入的配置而不实际修改")

    sub.add_parser("show", help="显示当前配置")
    sub.add_parser("init", help="从当前 settings.json 生成初始 profiles.toml")

    p_add = sub.add_parser("add", help="添加新 profile")
    p_add.add_argument("name", help="profile 名称")
    p_add.add_argument("--base", help="ANTHROPIC_BASE_URL")
    p_add.add_argument("--key", dest="api_key", help="ANTHROPIC_API_KEY")
    p_add.add_argument("--auth-token", dest="auth_token", help="ANTHROPIC_AUTH_TOKEN (与 --key 二选一)")
    p_add.add_argument("--model", dest="model", help="模型名称 (opus/sonnet/haiku) (与 --anthropic-model 二选一)")
    p_add.add_argument("--anthropic-model", dest="anthropic_model", help="ANTHROPIC_MODEL 值 (与 --model 二选一)")
    p_add.add_argument("--env", action="append", metavar="KEY=VALUE", help="额外环境变量")
    p_add.add_argument("--use", action="store_true", help="添加后立即切换")

    p_del = sub.add_parser("delete", help="删除 profile")
    p_del.add_argument("name", help="profile 名称")
    p_del.add_argument("-f", "--force", action="store_true", help="跳过确认")

    p_rename = sub.add_parser("rename", help="重命名 profile")
    p_rename.add_argument("old_name", help="原名称")
    p_rename.add_argument("new_name", help="新名称")

    p_copy = sub.add_parser("copy", help="复制 profile")
    p_copy.add_argument("source", help="源 profile 名称")
    p_copy.add_argument("target", help="目标 profile 名称")

    sub.add_parser("interactive", aliases=["i"], help="交互式向导")

    return parser


def dispatch(args: argparse.Namespace) -> str | None:
    """根据解析后的参数调用对应命令，返回结果字符串。"""
    if args.command == "list":
        return cmd_list()
    elif args.command == "use":
        return cmd_use(args.name, dry_run=args.dry_run)
    elif args.command == "show":
        return cmd_show()
    elif args.command == "init":
        return cmd_init()
    elif args.command == "add":
        return cmd_add(
            name=args.name,
            base=args.base,
            api_key=args.api_key,
            auth_token=args.auth_token,
            model=args.model,
            anthropic_model=args.anthropic_model,
            env=args.env,
            use=args.use,
        )
    elif args.command == "delete":
        return cmd_delete(args.name, force=args.force)
    elif args.command == "rename":
        return cmd_rename(args.old_name, args.new_name)
    elif args.command == "copy":
        return cmd_copy(args.source, args.target)
    elif args.command in ("interactive", "i"):
        run_interactive()
        return None
    return None


def main() -> None:
    """入口函数。"""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        result = dispatch(args)
        if result is not None:
            print(result)
    except ClaudeSwitchError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(e.exit_code)


if __name__ == "__main__":
    main()
