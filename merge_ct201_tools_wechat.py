#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 文件路径: dist/merge_ct201_tools_wechat.py
# 创建时间: 2026-03-31
# 上次修改时间: 2026-03-31（按 OpenClaw 真实链路修正：不虚构 TOOLS.md，缺失则报错退出）
# 开发者: aidaox
"""
作用：通过 SSH 连 PVE，在目标容器内合并 workspace/TOOLS.md。

与 OpenClaw 执行逻辑的关系（本仓库能还原的部分，便于改脚本前对齐预期）：

1) TOOLS.md 是什么
   - 路径固定为容器内 /root/.openclaw/workspace/TOOLS.md。
   - 在 OpenClaw 工作流里，它作为「环境备忘」给模型看；具体何时加载、是否热更新以你安装的 OpenClaw 版本为准。
   - 本脚本**只改磁盘上的这一份文件**，不调用 OpenClaw 插件 API。

2) 合并后为什么要 restart openclaw-gateway
   - 运维文档与历史经验：改完 TOOLS 后执行 systemctl restart openclaw-gateway，让网关进程尽快按新文件工作。
   - 是否「必须重启才生效」因版本而异；脚本仍保留重启，与现有 SOP 一致。

3) 公众号草稿与 OpenClaw 主进程的关系
   - 发草稿**不是**网关内置能力；模型按 TOOLS.md 去执行**宿壳命令**：
     /usr/local/bin/wechat-draft → Python3 调 /opt/wechat-draft-cli/wechat_draft_agent.py
     → 再 subprocess 到 wechat_draft_simple_cmd.py 或 wechat_draft_cli.py（全程绝对路径，不依赖 PATH）。
   - 因此「设置 OpenClaw」在公众号场景下 = TOOLS 写对 + 容器里已部署 wechat-draft 脚本与 accounts.json；与微信通道（openclaw-weixin）是两条线。

本脚本具体做三件事：
- 删掉易误导的「WeChat MP Publishing Workflow」等旧段；
- 删掉已合并过的「微信公众号草稿（通用）…」避免重复；
- 在页脚句「Add whatever helps you do your job…」之前插入 TOOLS-workspace-公众号草稿片段.md（若该行不存在则把片段接在文末）。
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import paramiko

# PveHost — PVE SSH 地址
PVE_HOST = os.environ.get("PVE_HOST", "").strip()
# PveUser — SSH 用户
PVE_USER = os.environ.get("PVE_USER", "root")
# CtId — 龙虾容器 ID
CT_ID = os.environ.get("CT_ID", "201").strip()
# ToolsPath — 容器内 TOOLS.md 路径
TOOLS_PATH = "/root/.openclaw/workspace/TOOLS.md"
# FooterLine — TOOLS.md 末尾固定句，插入点在其之前
FOOTER_NEEDLE = "Add whatever helps you do your job. This is your cheat sheet."


def 读取片段正文(片段文件: Path) -> str:
    """从片段文件取出可写入 TOOLS 的正文（从首个 --- 到文件末，去掉首尾空行）。"""
    文本 = 片段文件.read_text(encoding="utf-8-sig")
    行列表 = 文本.splitlines()
    起始 = 0
    for 索引, 行 in enumerate(行列表):
        if 行.strip() == "---":
            起始 = 索引
            break
    块 = "\n".join(行列表[起始:]).strip()
    if not 块:
        raise RuntimeError("片段文件为空或找不到 --- 起始行")
    return 块


def 清理旧内容(全文: str) -> str:
    """删除冲突段落：旧 Workflow + 已合并过的公众号小节。"""
    结果 = 全文

    # 1) 删除 ## WeChat MP Publishing Workflow 到其后的 --- 与空行（止于 Add whatever 之前）
    标记 = "## WeChat MP Publishing Workflow"
    if 标记 in 结果:
        起点 = 结果.find(标记)
        尾点 = 结果.find("\n\n" + FOOTER_NEEDLE, 起点)
        if 尾点 == -1:
            尾点 = 结果.find(FOOTER_NEEDLE, 起点)
        if 尾点 > 起点:
            # 去掉 Workflow 到页脚前的内容，保留页脚
            结果 = 结果[:起点].rstrip() + "\n\n" + 结果[尾点:].lstrip()

    # 2) 删除已存在的「微信公众号草稿（通用）」整段（到页脚前）
    标记2 = "## 微信公众号草稿（通用）— 唯一正确用法"
    if 标记2 in 结果:
        起点 = 结果.find(标记2)
        尾点 = 结果.find("\n\n" + FOOTER_NEEDLE, 起点)
        if 尾点 == -1:
            尾点 = 结果.find(FOOTER_NEEDLE, 起点)
        if 尾点 > 起点:
            结果 = 结果[:起点].rstrip() + "\n\n" + 结果[尾点:].lstrip()

    return 结果


def 插入片段(全文: str, 片段: str) -> str:
    """在页脚句之前插入片段（若尚无 wechat-draft-quick 则必插；已清理后总是插入）。"""
    if FOOTER_NEEDLE not in 全文:
        return 全文.rstrip() + "\n\n" + 片段 + "\n"
    位置 = 全文.find(FOOTER_NEEDLE)
    前缀 = 全文[:位置].rstrip()
    后缀 = 全文[位置:]
    return 前缀 + "\n\n" + 片段 + "\n\n" + 后缀


def main() -> int:
    """主流程：拉取 TOOLS → 合并 → 写回 → 可选重启网关。"""
    密码 = os.environ.get("PVE_PASS", "").strip()
    if not PVE_HOST:
        print("请设置环境变量 PVE_HOST", flush=True)
        return 2
    if not 密码:
        print("请设置环境变量 PVE_PASS", flush=True)
        return 2

    脚本目录 = Path(__file__).resolve().parent
    片段路径 = 脚本目录 / "TOOLS-workspace-公众号草稿片段.md"
    if not 片段路径.exists():
        print(f"缺少文件: {片段路径}", flush=True)
        return 2

    片段正文 = 读取片段正文(片段路径)

    客户端 = paramiko.SSHClient()
    客户端.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    客户端.connect(PVE_HOST, username=PVE_USER, password=密码, timeout=30)

    try:
        # 确保父目录存在：仅在为「即将 pct push 写回」做准备；若 TOOLS 尚不存在，下面 cat 会失败并提示先 onboard
        _, _, _ = 客户端.exec_command(f"pct exec {CT_ID} -- mkdir -p /root/.openclaw/workspace")
        # 读出当前 TOOLS.md（必须由 OpenClaw 初始化或用户已创建，禁止在此脚本里伪造整份 TOOLS，以免与官方模板/版本不一致）
        命令 = f"pct exec {CT_ID} -- cat {TOOLS_PATH}"
        _, stdout, stderr = 客户端.exec_command(命令)
        原始 = stdout.read().decode("utf-8", errors="replace")
        错 = stderr.read().decode("utf-8", errors="replace")
        退出码 = stdout.channel.recv_exit_status()
        if 错.strip():
            print(错, flush=True)
        if 退出码 != 0 or not 原始.strip():
            print(
                "[ERROR] 读不到有效 TOOLS.md（文件不存在或为空）。"
                "请先在容器内完成 OpenClaw 初始化（如 onboard），确认 "
                f"{TOOLS_PATH} 已由官方生成且含正文后，再运行本合并脚本。",
                flush=True,
            )
            return 1

        处理后 = 清理旧内容(原始)
        新全文 = 插入片段(处理后, 片段正文)

        if 新全文 == 原始:
            print("[INFO] TOOLS.md 无需变更（内容与目标一致）", flush=True)
        else:
            # 写入本机临时文件再 pct push
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", delete=False, suffix="_TOOLS.md"
            ) as 临时:
                临时.write(新全文)
                本地临时 = 临时.name

            try:
                sftp = 客户端.open_sftp()
                sftp.put(本地临时, "/tmp/TOOLS_merged.md")
                sftp.close()
                推送命令 = f"pct push {CT_ID} /tmp/TOOLS_merged.md {TOOLS_PATH}"
                _, out2, err2 = 客户端.exec_command(推送命令)
                out2.read()
                e2 = err2.read().decode("utf-8", errors="replace")
                if e2.strip():
                    print(e2, flush=True)
            finally:
                try:
                    os.unlink(本地临时)
                except OSError:
                    pass

            print(f"[OK] 已写回 {TOOLS_PATH}", flush=True)

        # 重启网关使会话尽快读到新 TOOLS（具体是否热加载以 OpenClaw 版本为准）
        _, _, _ = 客户端.exec_command(
            f"pct exec {CT_ID} -- systemctl restart openclaw-gateway"
        )
        print("[OK] 已执行 systemctl restart openclaw-gateway", flush=True)
        return 0
    finally:
        客户端.close()


if __name__ == "__main__":
    raise SystemExit(main())
