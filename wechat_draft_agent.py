#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 文件路径: dist/wechat_draft_agent.py
# 创建时间: 2026-03-31
# 上次修改时间: 2026-03-31
# 开发者: aidaox
"""
微信公众号草稿「Agent 式」统一入口（用法对齐 agent-browser：一个主命令 + 子命令）。

容器内固定路径（勿改相对路径，避免 pct exec 无 PATH 时失效）：
- 本入口：/opt/wechat-draft-cli/wechat_draft_agent.py
- 一句话发草稿：/opt/wechat-draft-cli/wechat_draft_simple_cmd.py
- 全参数 CLI：/opt/wechat-draft-cli/wechat_draft_cli.py
"""

from __future__ import annotations

import subprocess
import sys

# AgentPy — 当前解释器（python3）
_AGENT_PY = sys.executable
# SimpleModule — 一句话解析脚本绝对路径
_SIMPLE = "/opt/wechat-draft-cli/wechat_draft_simple_cmd.py"
# CliModule — 全参数脚本绝对路径（不经过 shell 包装，避免 PATH 问题）
_CLI_MODULE = "/opt/wechat-draft-cli/wechat_draft_cli.py"


def _打印帮助() -> None:
    """打印帮助信息：与 TOOLS.md 中描述保持一致，便于 OpenClaw 检索。"""
    文本 = """
wechat-draft — 微信公众号草稿（Agent 风格，类似 agent-browser 一条主命令）

用法:
  wechat-draft help
  wechat-draft publish  发草稿 标题=... 文件=... 账号=...
  wechat-draft p        同上简写
  wechat-draft cli      --account-name ... --title ... --content-file ...（透传到底层 CLI）

也可省略子命令（自动当作 publish）:
  wechat-draft 发草稿 标题=... 文件=... 账号=...

推荐 OpenClaw 固定写（绝对路径，避免 PATH 为空）:
  /usr/local/bin/wechat-draft publish '发草稿 标题=文章标题 文件=/opt/wechat-draft-cli/article.html 账号=main'

说明:
  - 正文文件用绝对路径；.html 原样；.md/.markdown 由 wechat_draft_cli 转为公众号可用 HTML（优先 markdown 包，无则内置简化）。
  - 多账号见 /opt/wechat-draft-cli/accounts.json 中的别名。
  - 成功时终端必有 [WECHAT_API] ok=1 media_id=... 与 JSON；模型若只口头说成功而无此行，视为未执行命令。
"""
    print(文本.strip())


def _转发一句话(参数列表: list[str]) -> int:
    """转发到 wechat_draft_simple_cmd：解析 标题= 文件= 账号=。"""
    命令 = [_AGENT_PY, _SIMPLE, *参数列表]
    结果 = subprocess.run(命令, check=False)
    return int(结果.returncode)


def _转发全参数(参数列表: list[str]) -> int:
    """转发到 wechat_draft_cli：透传所有 argparse 参数。"""
    命令 = [_AGENT_PY, _CLI_MODULE, *参数列表]
    结果 = subprocess.run(命令, check=False)
    return int(结果.returncode)


def main() -> int:
    """主入口：解析子命令并分发。"""
    参数 = sys.argv[1:]

    if not 参数 or 参数[0].lower() in ("help", "-h", "--help"):
        _打印帮助()
        return 0

    子命令 = 参数[0].lower()
    剩余 = 参数[1:]

    if 子命令 in ("publish", "p", "quick", "q"):
        return _转发一句话(剩余)

    if 子命令 == "cli":
        return _转发全参数(剩余)

    # 若首词不是子命令，但整句像「发草稿 / title=」则当作一句话模式
    合并 = " ".join(参数)
    if "发草稿" in 合并 or "=" in 合并:
        return _转发一句话(参数)

    print(f"未知子命令: {参数[0]}，请执行 wechat-draft help", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
