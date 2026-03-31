#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 文件路径: dist/deploy_wechat_draft_cli_to_ct201.py
# 创建时间: 2026-03-31
# 上次修改时间: 2026-03-31（部署后安装 markdown，.md 正文转 HTML 更完整）
# 开发者: aidaox
"""
用途：
- 将本地 wechat_draft_cli.py 与账号模板部署到目标 LXC 容器。
- 在容器内创建固定命令 /usr/local/bin/wechat-draft-cli。
"""

import os
from pathlib import Path

import paramiko


def 运行远程命令(client: paramiko.SSHClient, 命令: str) -> None:
    """执行远程命令并在失败时抛异常。"""
    _, stdout, stderr = client.exec_command(命令)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out)
    if err.strip():
        print(err)
    if "command not found" in err.lower():
        raise RuntimeError(f"远程命令失败: {命令}\n{err}")


def main() -> int:
    """部署主流程。"""
    pve_host = os.environ.get("PVE_HOST", "").strip()
    pve_user = os.environ.get("PVE_USER", "root").strip()
    pve_pass = os.environ.get("PVE_PASS", "")
    ct_id = os.environ.get("CT_ID", "201").strip()
    if not pve_host:
        raise SystemExit("请先设置环境变量 PVE_HOST")
    if not pve_pass:
        raise SystemExit("请先设置环境变量 PVE_PASS")

    工作区 = Path(__file__).resolve().parent
    cli脚本 = 工作区 / "wechat_draft_cli.py"
    简易指令脚本 = 工作区 / "wechat_draft_simple_cmd.py"
    统一入口脚本 = 工作区 / "wechat_draft_agent.py"
    账号模板 = 工作区 / "wechat_accounts.template.json"
    测试正文 = 工作区 / "wechat_test_article.html"
    默认封面图 = 工作区 / "wechat_default_cover.png"
    if not cli脚本.exists():
        raise SystemExit(f"未找到文件: {cli脚本}")
    if not 简易指令脚本.exists():
        raise SystemExit(f"未找到文件: {简易指令脚本}")
    if not 统一入口脚本.exists():
        raise SystemExit(f"未找到文件: {统一入口脚本}")
    if not 账号模板.exists():
        raise SystemExit(f"未找到文件: {账号模板}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(pve_host, username=pve_user, password=pve_pass, timeout=25)

    try:
        sftp = ssh.open_sftp()
        sftp.put(str(cli脚本), "/tmp/wechat_draft_cli.py")
        sftp.put(str(简易指令脚本), "/tmp/wechat_draft_simple_cmd.py")
        sftp.put(str(统一入口脚本), "/tmp/wechat_draft_agent.py")
        sftp.put(str(账号模板), "/tmp/wechat_accounts.template.json")
        if 测试正文.exists():
            sftp.put(str(测试正文), "/tmp/wechat_test_article.html")
        if not 默认封面图.exists():
            raise SystemExit(f"未找到默认公众号封面图: {默认封面图}")
        sftp.put(str(默认封面图), "/tmp/wechat_default_cover.png")
        sftp.close()

        # 推送到目标容器固定目录
        运行远程命令(ssh, f"pct exec {ct_id} -- mkdir -p /opt/wechat-draft-cli")
        运行远程命令(ssh, f"pct push {ct_id} /tmp/wechat_draft_cli.py /opt/wechat-draft-cli/wechat_draft_cli.py")
        运行远程命令(ssh, f"pct push {ct_id} /tmp/wechat_draft_simple_cmd.py /opt/wechat-draft-cli/wechat_draft_simple_cmd.py")
        运行远程命令(ssh, f"pct push {ct_id} /tmp/wechat_draft_agent.py /opt/wechat-draft-cli/wechat_draft_agent.py")
        运行远程命令(ssh, f"pct push {ct_id} /tmp/wechat_accounts.template.json /opt/wechat-draft-cli/accounts.template.json")
        if 测试正文.exists():
            运行远程命令(ssh, f"pct push {ct_id} /tmp/wechat_test_article.html /opt/wechat-draft-cli/wechat_test_article.html")
        运行远程命令(ssh, f"pct push {ct_id} /tmp/wechat_default_cover.png /opt/wechat-draft-cli/wechat_default_cover.png")

        # 让 .md 走完整 Markdown→HTML（标题、列表、表格等）；失败则 CLI 内置兜底仍可用
        运行远程命令(
            ssh,
            f"pct exec {ct_id} -- bash -lc 'python3 -m pip install -q --upgrade markdown 2>/dev/null || python3 -m ensurepip --upgrade >/dev/null 2>&1 || true; python3 -m pip install -q --upgrade markdown 2>/dev/null || true'",
        )

        # 首次生成 accounts.json（如果不存在）
        运行远程命令(
            ssh,
            f"pct exec {ct_id} -- bash -lc 'test -f /opt/wechat-draft-cli/accounts.json || cp /opt/wechat-draft-cli/accounts.template.json /opt/wechat-draft-cli/accounts.json'",
        )

        # 生成固定命令入口
        运行远程命令(
            ssh,
            f"pct exec {ct_id} -- bash -lc 'printf \"#!/bin/bash\\npython3 /opt/wechat-draft-cli/wechat_draft_cli.py \\\"\\$@\\\"\\n\" > /usr/local/bin/wechat-draft-cli && chmod +x /usr/local/bin/wechat-draft-cli'",
        )
        运行远程命令(
            ssh,
            f"pct exec {ct_id} -- bash -lc 'printf \"#!/bin/bash\\npython3 /opt/wechat-draft-cli/wechat_draft_simple_cmd.py \\\"\\$@\\\"\\n\" > /usr/local/bin/wechat-draft-quick && chmod +x /usr/local/bin/wechat-draft-quick'",
        )
        运行远程命令(
            ssh,
            f"pct exec {ct_id} -- bash -lc 'printf \"#!/bin/bash\\npython3 /opt/wechat-draft-cli/wechat_draft_agent.py \\\"\\$@\\\"\\n\" > /usr/local/bin/wechat-draft && chmod +x /usr/local/bin/wechat-draft'",
        )

        # 默认封面改为同目录 wechat_default_cover.png：首次发草稿时 CLI 自动上传并写入 default_thumb_media_id.cache。
        # 若容器的 /etc/environment 里有旧版 WECHAT_DEFAULT_THUMB_MEDIA_ID，会优先于自动封面；需用新图时请手动删掉该行。

        print("[OK] 部署完成：目标容器已可使用 wechat-draft / wechat-draft-cli / wechat-draft-quick。")
        print("     默认封面：/opt/wechat-draft-cli/wechat_default_cover.png（首次发草稿自动上传并缓存 media_id）。")
        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())

