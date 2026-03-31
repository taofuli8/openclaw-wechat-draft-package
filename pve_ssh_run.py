# -*- coding: utf-8 -*-
# 文件路径: dist/pve_ssh_run.py
# 创建时间: 2026-03-29
# 上次修改时间: 2026-03-31
# 开发者: aidaox
# 作用: 从本机通过密码 SSH 在 PVE 上执行一条 shell 命令（密码从环境变量 PVE_PASS 读取，避免写进仓库）。
import os
import sys

import paramiko  # 需本机已 pip install paramiko

# PveHost — PVE 管理地址
PVE_HOST = os.environ.get("PVE_HOST", "").strip()
# PveUser — SSH 登录用户
PVE_USER = os.environ.get("PVE_USER", "root")


def main() -> int:
    # PvePass — 从环境变量读取，不在命令行明文传参
    pwd = os.environ.get("PVE_PASS")
    if not PVE_HOST:
        print("请设置环境变量 PVE_HOST", file=sys.stderr)
        return 2
    if not pwd:
        print("请设置环境变量 PVE_PASS", file=sys.stderr)
        return 2
    if len(sys.argv) < 2:
        print('用法: set PVE_PASS=*** && py -3 scripts\\pve_ssh_run.py "要执行的命令"', file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(PVE_HOST, username=PVE_USER, password=pwd, timeout=25)
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    client.close()
    sys.stdout.write(out)
    sys.stderr.write(err)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
