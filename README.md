# OpenClaw WeChat Draft（60 秒上手）

给全新 OpenClaw 环境加上“微信公众号草稿发布”能力。

## 1) 先装 OpenClaw（新环境只做一次）

```bash
npm config set registry https://registry.npmjs.org
npm install -g openclaw@latest
openclaw --version
openclaw onboard
```

## 2) 一句话安装本工具

把 `<RAW_BASE_URL>` 换成你的仓库 raw 地址：

```bash
bash -lc "curl -fsSL <RAW_BASE_URL>/dist/install_openclaw_wechat.sh | bash -s -- --raw-base <RAW_BASE_URL>"
```

示例：

```bash
bash -lc "curl -fsSL https://raw.githubusercontent.com/<github-username>/openclaw-wechat-draft-package/main/dist/install_openclaw_wechat.sh | bash -s -- --raw-base https://raw.githubusercontent.com/<github-username>/openclaw-wechat-draft-package/main"
```

## 3) 填账号并发第一篇

编辑 `/opt/wechat-draft-cli/accounts.json` 填入你自己的 `appid/appsecret`，再执行：

```bash
/usr/local/bin/wechat-draft publish '发草稿 标题=文章标题 文件=/opt/wechat-draft-cli/article.html 账号=main'
```

看到以下两行即成功：

- `[OK] 草稿创建成功`
- `[WECHAT_API] ok=1 media_id=...`

## 开源安全提醒

- 不要提交真实 `accounts.json`、Token、Cookie、密钥、日志
- 只提交模板文件（`*.template.json`）

![肥猫AI干货二维码](docs/wechat-qrcode.png)
