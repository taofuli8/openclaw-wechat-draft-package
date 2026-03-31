# OpenClaw WeChat Draft Package

这个仓库用于给全新 OpenClaw 环境快速增加“微信公众号草稿发布”能力，目标是：

- 可开源共享：不包含真实账号密钥、密码、个人环境路径。
- 可一键安装：给 OpenClaw 一句话，它就能把工具装到目标 Linux 容器。
- 可维护复用：账号配置走模板文件，后续只改 `accounts.json` 即可。

## 一句话给 OpenClaw（核心）

直接把下面这句话发给 OpenClaw 即可：

```bash
bash -lc "curl -fsSL https://raw.githubusercontent.com/taofuli8/openclaw-wechat-draft-package/main/install_openclaw_wechat.sh | bash -s -- --raw-base https://raw.githubusercontent.com/taofuli8/openclaw-wechat-draft-package/main"
```

## 安装后怎么用

先准备正文文件（HTML 或 Markdown）到容器里，例如 `/opt/wechat-draft-cli/article.html`，然后执行：

```bash
/usr/local/bin/wechat-draft publish '发草稿 标题=文章标题 文件=/opt/wechat-draft-cli/article.html 账号=main'
```

成功判据（必须同时出现）：

- `[OK] 草稿创建成功`
- `[WECHAT_API] ok=1 media_id=...`

## 首次必改配置

编辑容器内文件：

- `/opt/wechat-draft-cli/accounts.json`

模板结构：

```json
{
  "accounts": {
    "main": {
      "appid": "替换成你的AppID",
      "appsecret": "替换成你的AppSecret"
    }
  }
}
```

## 数据脱敏说明

本仓库默认仅保留模板和示例，不应提交以下内容：

- 真实 `accounts.json`、`.env`、日志、备份密钥文件
- 个人内网地址、个人路径、个人昵称/实名等环境痕迹
- 明文密码、Token、Cookie、AccessKey 等

## 公众号信息（肥猫AI干货）

- 名称：`肥猫AI干货`
- 简介：专注 AI 干货｜大模型资讯 + 优惠 + 实战计划，每天带你薅羊毛、学代码

二维码（请保存在仓库根目录 `wechat-qrcode.png`）：

![肥猫AI干货二维码](wechat-qrcode.png)

