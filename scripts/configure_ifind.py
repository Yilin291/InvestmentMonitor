#!/usr/bin/env python3
"""Save the user's iFinD credential locally without echoing or logging it."""

import getpass
import json
import os
from pathlib import Path
import sys
import tempfile


def main() -> int:
    if not sys.stdin.isatty():
        print("请在本机交互式终端运行此脚本；密钥输入不会显示。")
        return 1
    config = Path.home() / ".codex/skills/ifind-finance-data/mcp_config.json"
    if not config.is_file():
        print("未找到已安装的 iFinD 技能配置。")
        return 1
    token = getpass.getpass("粘贴 iFinD MCP 密钥（不显示输入），然后回车：").strip()
    if len(token) < 8 or any(c.isspace() for c in token):
        print("未保存：输入为空、过短或包含空白，请检查完整密钥。")
        return 1
    data = json.loads(config.read_text(encoding="utf-8"))
    data["auth_token"] = token
    fd, tmp = tempfile.mkstemp(prefix=".ifind-config-", dir=config.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
            out.write("\n")
        os.replace(tmp, config)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print("密钥已保存到本机技能配置，权限为 600；未联网验证。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
