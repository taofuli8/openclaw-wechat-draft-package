<!--
文件路径: dist/TOOLS-workspace-公众号草稿片段.md
创建时间: 2026-03-31
上次修改时间: 2026-03-31
开发者: aidaox
说明: 从下面「---」到文末整段，复制合并进 OpenClaw 容器 /root/.openclaw/workspace/TOOLS.md。
-->

---

## 微信公众号草稿（通用）— 唯一正确用法

### 重要：为什么你「看到成功但后台没有」

1. **模型会编造 `media_id`**（例如整齐像 UUID 的假串）。**只有终端里真实出现下面两行才算成功：**
   - `[OK] 草稿创建成功`
   - **`[WECHAT_API] ok=1 media_id=...`**（紧跟其后还有一段 JSON）
2. 若微信里只有聊天回复、**没有**把**完整终端输出**贴出来 → **不能算发过草稿**。
3. **禁止**再教用户用裸命令 `wechat-draft-quick`（无路径时容器里常找不到）。**必须写：** `/usr/local/bin/wechat-draft ...`

### 与 agent-browser 相同的使用习惯（推荐记这一条）

像 `agent-browser open / snapshot` 一样，**一个主命令 + 子命令**：

| 子命令 | 作用 |
|--------|------|
| `wechat-draft help` | 打印帮助 |
| `wechat-draft publish …` 或 `wechat-draft p …` | 一句话发草稿（`发草稿 标题=… 文件=… 账号=…`） |
| `wechat-draft cli …` | 透传全参数（等同 `wechat-draft-cli`） |

**OpenClaw 默认应执行的完整示例（务必绝对路径）：**

```bash
/usr/local/bin/wechat-draft publish '发草稿 标题=文章标题 文件=/opt/wechat-draft-cli/article.html 账号=main'
```

也可省略 `publish`，直接：

```bash
/usr/local/bin/wechat-draft '发草稿 标题=文章标题 文件=/opt/wechat-draft-cli/article.html 账号=main'
```

### 禁止再用的方式（会失败）

- **不要**在 `/tmp/wechat-draft/` 里跑 `publish.js`、`require('./index')` 等临时 Node 脚本（文件不全、thumb 缺失必挂）。
- **不要**让模型自己「现写」微信 API 调用再执行，除非你已经确认同一路径、同一份依赖长期存在。

### 兼容入口（与上表等价）

| 命令 | 用途 |
|------|------|
| `/usr/local/bin/wechat-draft` | **主入口**（Agent 风格，优先用这个） |
| `/usr/local/bin/wechat-draft-quick` | 仅一句话模式，无子命令 |
| `/usr/local/bin/wechat-draft-cli` | 仅全参数模式 |

### 最简：一句话发草稿（推荐 OpenClaw 默认用这个）

正文须先写成 **HTML 文件**（例如用 `write` 工具写到固定目录），再执行：

```bash
/usr/local/bin/wechat-draft publish '发草稿 标题=文章标题 文件=/opt/wechat-draft-cli/article.html 账号=main'
```

**必填三项**：`标题=`、`文件=`（**绝对路径**；`.html` 原样；`.md` 由 CLI 转为 HTML）、`账号=`（见下节 `accounts.json` 里的别名）。

**可选**：`摘要=`、`作者=`、`封面=`（= 微信素材 `thumb_media_id`）、`原文=`、`评论=0|1`、`仅粉丝=0|1`。  
不写 `封面=` 时：优先环境变量 **`WECHAT_DEFAULT_THUMB_MEDIA_ID`**；否则读同目录缓存；再否则自动上传 **`/opt/wechat-draft-cli/wechat_default_cover.png`** 并缓存 `media_id`（详见 `wechat_draft_cli.py`）。

英文键等价：`title=`、`file=`、`account=`、`digest=`、`author=`、`thumb=`、`source=`。

### 多账号（不同公众号）

- 配置文件：**`/opt/wechat-draft-cli/accounts.json`**
- 结构：`accounts.<别名>.appid` / `accounts.<别名>.appsecret`
- 发哪号就改 **`账号=别名`**，不要把 AppSecret 写进聊天或仓库。

### 完整参数版（需要精细控制时）

```bash
/usr/local/bin/wechat-draft cli \
  --account-name main \
  --title "标题" \
  --author "公众号作者" \
  --digest "摘要" \
  --content-file /opt/wechat-draft-cli/文章.html \
  --thumb-media-id "你的thumb_media_id" \
  --open-comment 1 \
  --fans-only-comment 0
```

### 成功判据

- 终端出现 **`[OK] 草稿创建成功`** 且打印 JSON 含 **`media_id`**。
- 若失败：先看是否 **文件路径不存在**、**账号别名写错**、**缺封面且未设默认 thumb**。

### 从维护电脑更新容器内脚本（PVE SSH）

在 Windows 上（需能 SSH 到 PVE，且已安装 Python + paramiko）：

```powershell
$env:PVE_PASS='PVE的root密码'
py -3 scripts\deploy_wechat_draft_cli_to_ct201.py
```

（脚本路径以你本机 `openwrt` 仓库为准。）

### OpenClaw 执行时注意

- 容器里 **非交互执行** 时 `PATH` 往往为空，请始终用 **`/usr/local/bin/wechat-draft`**（主入口，内部用绝对路径调 Python 脚本，不再依赖 PATH）。
- 整条「发草稿 …」建议用 **单引号** 包起来；需要时再套：`bash -lc '/usr/local/bin/wechat-draft publish '\''…'\'''`。
- 先把 HTML 写到 **`/opt/wechat-draft-cli/`** 或你约定的目录，**路径写绝对路径**。
