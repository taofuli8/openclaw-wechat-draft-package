#!/usr/bin/env bash
# 文件路径: install_openclaw_wechat.sh
# 创建时间: 2026-03-31
# 上次修改时间: 2026-03-31
# 开发者: aidaox
set -euo pipefail

# RawBase 默认值：请在发布到 GitHub 后改成你的仓库 raw 根地址，或通过 --raw-base 传入
RAW_BASE_DEFAULT="https://raw.githubusercontent.com/taofuli8/openclaw-wechat-draft-package/main"

# RawBase 最终值：优先命令行 --raw-base，其次默认值
RAW_BASE="${RAW_BASE_DEFAULT}"

# InstallDir 安装目录：统一放到该目录，避免散落
INSTALL_DIR="/opt/wechat-draft-cli"

# ToolsPath OpenClaw TOOLS 路径：用于注入最小使用说明
TOOLS_PATH="/root/.openclaw/workspace/TOOLS.md"

# 解析命令行参数：当前只支持 --raw-base
while [[ $# -gt 0 ]]; do
  case "$1" in
    --raw-base)
      RAW_BASE="${2:-}"
      shift 2
      ;;
    *)
      echo "[WARN] 忽略未知参数: $1"
      shift
      ;;
  esac
done

# 基础依赖检查：需要 curl 和 python3
command -v curl >/dev/null 2>&1 || { echo "[ERROR] 缺少 curl"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "[ERROR] 缺少 python3"; exit 1; }

echo "[INFO] 安装目录: ${INSTALL_DIR}"
echo "[INFO] RAW_BASE: ${RAW_BASE}"

# 创建目录：统一存放脚本与配置
mkdir -p "${INSTALL_DIR}"

# 下载脚本与模板文件
curl -fsSL "${RAW_BASE}/wechat_draft_cli.py" -o "${INSTALL_DIR}/wechat_draft_cli.py"
curl -fsSL "${RAW_BASE}/wechat_draft_simple_cmd.py" -o "${INSTALL_DIR}/wechat_draft_simple_cmd.py"
curl -fsSL "${RAW_BASE}/wechat_draft_agent.py" -o "${INSTALL_DIR}/wechat_draft_agent.py"
curl -fsSL "${RAW_BASE}/wechat_accounts.template.json" -o "${INSTALL_DIR}/accounts.template.json"

# 默认封面图：可选下载，下载失败不终止安装
if ! curl -fsSL "${RAW_BASE}/wechat_default_cover.png" -o "${INSTALL_DIR}/wechat_default_cover.png"; then
  echo "[WARN] 默认封面图下载失败，将继续安装（后续可手动补充）。"
fi

# 初始化账号配置：不存在才复制模板，避免覆盖用户已配置内容
if [[ ! -f "${INSTALL_DIR}/accounts.json" ]]; then
  cp "${INSTALL_DIR}/accounts.template.json" "${INSTALL_DIR}/accounts.json"
  echo "[INFO] 已生成 ${INSTALL_DIR}/accounts.json（请手动填写 appid/appsecret）"
fi

# 生成统一命令入口：wechat-draft-cli / wechat-draft-quick / wechat-draft
cat > /usr/local/bin/wechat-draft-cli <<'EOF'
#!/usr/bin/env bash
python3 /opt/wechat-draft-cli/wechat_draft_cli.py "$@"
EOF

cat > /usr/local/bin/wechat-draft-quick <<'EOF'
#!/usr/bin/env bash
python3 /opt/wechat-draft-cli/wechat_draft_simple_cmd.py "$@"
EOF

cat > /usr/local/bin/wechat-draft <<'EOF'
#!/usr/bin/env bash
python3 /opt/wechat-draft-cli/wechat_draft_agent.py "$@"
EOF

chmod +x /usr/local/bin/wechat-draft-cli /usr/local/bin/wechat-draft-quick /usr/local/bin/wechat-draft

# 尝试安装 markdown 依赖：失败不终止（CLI 有兜底）
python3 -m pip install -q --upgrade markdown >/dev/null 2>&1 || true

# 若 TOOLS.md 存在，补充一段最小说明，避免重复写入
if [[ -f "${TOOLS_PATH}" ]]; then
  if ! grep -q "wechat-draft publish" "${TOOLS_PATH}"; then
    cat >> "${TOOLS_PATH}" <<'EOF'

## WeChat Draft Quick Start

Use:
/usr/local/bin/wechat-draft publish '发草稿 标题=文章标题 文件=/opt/wechat-draft-cli/article.html 账号=main'

Success must include:
- [OK] 草稿创建成功
- [WECHAT_API] ok=1 media_id=...
EOF
  fi
fi

echo "[OK] 安装完成。"
echo "[NEXT] 请编辑 ${INSTALL_DIR}/accounts.json 填写真实 appid/appsecret。"
echo "[TEST] /usr/local/bin/wechat-draft help"
