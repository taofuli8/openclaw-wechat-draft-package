#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 文件路径: dist/wechat_draft_simple_cmd.py
# 创建时间: 2026-03-31
# 上次修改时间: 2026-03-31
# 开发者: aidaox
"""
最简指令层：把自然语言里的 key=value 拼成 wechat-draft-cli 并执行。

OpenClaw 示例（整条作为一个参数或空格拆开均可）：

  wechat-draft-quick '发草稿 标题=测试 文件=/opt/wechat-draft-cli/a.html 账号=main'

正文文件可为 .html 或 .md（.md 会自动包成 HTML）。可选键：摘要= 作者= 封面= 原文= 评论=0|1 仅粉丝=0|1
英文别名：title= file= account= digest= author= thumb= source=
"""

import os
import re
import subprocess
import sys
from typing import Dict, List

# CliModule — 直接 python 调 CLI 模块，避免经 shell 包装时再受 PATH 影响
_CLI_MODULE = os.environ.get("WECHAT_DRAFT_CLI_MODULE", "/opt/wechat-draft-cli/wechat_draft_cli.py")

# 已知键的正则片段：用于在连续文本里定位每个键的起始位置
_键名正则 = (
    r"标题|文件|账号|摘要|作者|封面|原文|评论|仅粉丝|"
    r"title|file|account|digest|author|thumb|source|open_comment|fans_only"
)

# 中文/英文键映射到 wechat-draft-cli 的参数名（不含 --）
_键映射 = {
    "标题": "title",
    "title": "title",
    "文件": "content-file",
    "file": "content-file",
    "账号": "account-name",
    "account": "account-name",
    "摘要": "digest",
    "digest": "digest",
    "作者": "author",
    "author": "author",
    "封面": "thumb-media-id",
    "thumb": "thumb-media-id",
    "原文": "source-url",
    "source": "source-url",
    "评论": "open-comment",
    "open_comment": "open-comment",
    "仅粉丝": "fans-only-comment",
    "fans_only": "fans-only-comment",
}


def _打印日志(内容: str) -> None:
    """用统一前缀打印一行，方便在 OpenClaw 日志里检索。"""
    print(f"[wechat-draft-quick] {内容}")


def _去掉指令前缀(原文: str) -> str:
    """去掉开头的「发草稿」或 draft，只保留键值对部分。"""
    文本 = 原文.strip()
    if 文本.startswith("发草稿"):
        文本 = 文本[3:].strip()
    elif 文本.lower().startswith("draft"):
        文本 = 文本[5:].lstrip().strip()
    return 文本


def _解析键值对(原文: str) -> Dict[str, str]:
    """
    从一行文本里解析出多个 key=value。
    value 支持到下一个已知键之前（可含空格）。
    """
    文本 = _去掉指令前缀(原文)
    if not 文本:
        return {}

    模式 = re.compile(rf"\s*({_键名正则})\s*=\s*", re.IGNORECASE)
    所有匹配 = list(模式.finditer(文本))
    if not 所有匹配:
        return {}

    结果: Dict[str, str] = {}
    for 索引, 匹配对象 in enumerate(所有匹配):
        原始键 = 匹配对象.group(1)
        值起始 = 匹配对象.end()
        值结束 = 所有匹配[索引 + 1].start() if 索引 + 1 < len(所有匹配) else len(文本)
        值 = 文本[值起始:值结束].strip()
        if len(值) >= 2 and ((值[0] == 值[-1] == '"') or (值[0] == 值[-1] == "'")):
            值 = 值[1:-1]
        键小写 = 原始键.lower() if 原始键.isascii() else 原始键
        规范键 = _键映射.get(原始键) or _键映射.get(键小写) or 原始键
        结果[规范键] = 值
    return 结果


def _拼出_cli参数(键值: Dict[str, str]) -> List[str]:
    """把规范键转成 wechat-draft-cli 的命令行列表。"""
    必填 = ("title", "content-file", "account-name")
    for 项 in 必填:
        if not 键值.get(项):
            raise SystemExit(
                f"缺少必填项：{项}。请写：标题=… 文件=… 账号=…（见 wechat_draft_simple_cmd.py 注释）"
            )

    参数列表: List[str] = [
        sys.executable,
        _CLI_MODULE,
        "--account-name",
        键值["account-name"],
        "--title",
        键值["title"],
        "--content-file",
        键值["content-file"],
    ]
    if 键值.get("author"):
        参数列表 += ["--author", 键值["author"]]
    if 键值.get("digest"):
        参数列表 += ["--digest", 键值["digest"]]
    if 键值.get("thumb-media-id"):
        参数列表 += ["--thumb-media-id", 键值["thumb-media-id"]]
    if 键值.get("source-url"):
        参数列表 += ["--source-url", 键值["source-url"]]

    评论值 = 键值.get("open-comment", "1")
    粉丝值 = 键值.get("fans-only-comment", "0")
    if 评论值 not in ("0", "1"):
        raise SystemExit("评论= 只能是 0 或 1")
    if 粉丝值 not in ("0", "1"):
        raise SystemExit("仅粉丝= 只能是 0 或 1")
    参数列表 += ["--open-comment", 评论值, "--fans-only-comment", 粉丝值]
    return 参数列表


def main() -> int:
    """入口：合并 argv，解析键值对，exec 转交 wechat-draft-cli。"""
    if len(sys.argv) < 2:
        print(
            "用法：wechat-draft-quick '发草稿 标题=… 文件=… 账号=… [摘要=…] [作者=…] [封面=…]'",
            file=sys.stderr,
        )
        return 2

    # 整条指令：把除脚本名外的参数用空格拼回一行（兼容 OpenClaw 拆成多词）
    合并文本 = " ".join(sys.argv[1:])
    键值对 = _解析键值对(合并文本)
    if not 键值对:
        print("未解析到任何 键=值，请检查格式。", file=sys.stderr)
        return 2

    参数列表 = _拼出_cli参数(键值对)
    _打印日志("执行: " + " ".join(参数列表[:6]) + " ...（共 " + str(len(参数列表)) + " 项）")

    # 继承当前环境（含 WECHAT_DEFAULT_THUMB_MEDIA_ID）；未传 封面= 时由底层 CLI 读环境或报错
    结果 = subprocess.run(参数列表, check=False)
    return int(结果.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
