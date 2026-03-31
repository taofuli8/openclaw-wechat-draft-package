#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 文件路径: dist/wechat_draft_cli.py
# 创建时间: 2026-03-31
# 上次修改时间: 2026-03-31（默认封面：同目录 wechat_default_cover.png 自动上传并缓存 media_id）
# 开发者: aidaox
"""
用途：
- 作为 OpenClaw 固定调用的 CLI 工具，稳定创建公众号草稿。
- 解决临时脚本丢失（/tmp）和 thumb_media_id 缺失导致的失败。
- 默认封面：与本脚本同目录的 wechat_default_cover.png，首次发草稿时自动上传为永久素材并写入 default_thumb_media_id.cache。
"""

import argparse
import html
import json
import mimetypes
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib import parse, request

# 微信接口基础地址常量：统一管理，避免散落硬编码
微信接口基础地址 = "https://api.weixin.qq.com/cgi-bin"

# 脚本所在目录：用于定位默认封面图与 thumb 缓存文件（容器内一般为 /opt/wechat-draft-cli）
_脚本目录 = Path(__file__).resolve().parent
# 默认封面文件名：与脚本一起部署；微信公众号要求封面为合法图片素材
_默认封面图片名 = "wechat_default_cover.png"
# 上传成功后把 media_id 写入此缓存，避免每次发草稿都重复上传
_封面媒体缓存文件名 = "default_thumb_media_id.cache"

# 历史兜底 thumb_media_id：仅当未部署 wechat_default_cover.png、且无缓存、且未设置环境变量时使用（建议尽快改用 PNG 自动上传）
_内置默认封面ID = "8zunvJ23QzitMta_B33BeIgNT6PTLWsWctRO3oHxmXCtaZoclTUsQs9a3i1MhUSQ"


def 打印日志(日志内容: str) -> None:
    """统一日志输出函数：让 OpenClaw 日志可读。"""
    print(f"[wechat-draft-cli] {日志内容}")


def 读取文件内容(文件路径: Path) -> str:
    """读取文章正文文件：优先 UTF-8，失败回退 GBK。"""
    try:
        return 文件路径.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return 文件路径.read_text(encoding="gbk")


def _行内加粗(已转义文本: str) -> str:
    """
    在已做过 html.escape 的片段上，把 **文字** 转成 <strong>。
    已转义文本中不应含原始 < >，避免 XSS；星号不会被 escape 改变。
    """
    return re.sub(r"\*\*([^*]+?)\*\*", r"<strong>\1</strong>", 已转义文本)


def _单行转义并加粗(行文本: str) -> str:
    """单行：先转义 HTML 特殊字符，再处理加粗。"""
    return _行内加粗(html.escape(行文本.strip(), quote=False))


def _markdown无库转html(原始: str) -> str:
    """
    未安装 markdown 包时的兜底：按空行分段、标题/列表/分隔线单独处理，段落内单换行变 <br/>。
    不追求完整 CommonMark，只保证公众号里段落不再糊成一块。
    """
    文本 = 原始.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not 文本:
        return ""
    块列表 = re.split(r"\n{2,}", 文本)
    输出片段: List[str] = []

    for 块 in 块列表:
        块 = 块.strip()
        if not 块:
            continue
        行们 = [x for x in 块.split("\n")]
        非空行 = [x.strip() for x in 行们 if x.strip()]

        # 整块只有一行且为 --- / *** 分隔线
        if len(非空行) == 1 and re.fullmatch(r"-{3,}|\*{3,}|_{3,}", 非空行[0]):
            输出片段.append("<p><br/></p>")
            continue

        # 整块均为有序列表
        if 非空行 and all(re.match(r"^\d+\.\s+", x) for x in 非空行):
            输出片段.append("<ol>")
            for 行 in 非空行:
                mm = re.match(r"^\d+\.\s+(.+)$", 行)
                if mm:
                    输出片段.append(f"<li>{_单行转义并加粗(mm.group(1))}</li>")
            输出片段.append("</ol>")
            continue

        # 整块均为无序列表
        if 非空行 and all(re.match(r"^[-*]\s+", x) for x in 非空行):
            输出片段.append("<ul>")
            for 行 in 非空行:
                mm = re.match(r"^[-*]\s+(.+)$", 行)
                if mm:
                    输出片段.append(f"<li>{_单行转义并加粗(mm.group(1))}</li>")
            输出片段.append("</ul>")
            continue

        # 混排：逐行判断标题，其余累积成一段（段内 br）
        缓冲行: List[str] = []

        def 刷出段落() -> None:
            """把缓冲里的普通行合成一个 <p>，行与行之间 <br/>。"""
            if not 缓冲行:
                return
            输出片段.append("<p>" + "<br/>".join(_单行转义并加粗(x) for x in 缓冲行) + "</p>")
            缓冲行.clear()

        for 原始行 in 行们:
            行 = 原始行.strip()
            if not 行:
                continue
            if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", 行):
                刷出段落()
                输出片段.append("<p><br/></p>")
                continue
            m = re.match(r"^(#{1,6})\s+(.+)$", 行)
            if m:
                刷出段落()
                级 = min(len(m.group(1)), 6)
                输出片段.append(f"<h{级}>{_单行转义并加粗(m.group(2))}</h{级}>")
            else:
                缓冲行.append(行)
        刷出段落()

    return "\n".join(输出片段)


def 正文转公众号html(文件路径: Path, 原始正文: str) -> str:
    """
    微信 draft/add 的 content 必须是 HTML；不会替你渲染 Markdown。
    旧版把 .md 塞进 <pre>，公众号后台常剥离 white-space 样式，导致全文挤成一行。
    现改为：优先用 PyPI「markdown」转成 <p>/<h*>/<ul> 等；若无该包则用内置简化转换。
    """
    后缀 = 文件路径.suffix.lower()
    if 后缀 not in (".md", ".markdown"):
        return 原始正文

    去空白正文 = 原始正文.strip()
    if not 去空白正文:
        return ""

    try:
        import markdown as markdown模块  # type: ignore[import-untyped]

        # nl2br：单换行变 <br/>；sane_lists：列表缩进更稳；fenced_code：代码块（微信可能弱化 pre，尽量少用）
        html体 = markdown模块.markdown(
            去空白正文,
            extensions=[
                "markdown.extensions.nl2br",
                "markdown.extensions.sane_lists",
                "markdown.extensions.tables",
                "markdown.extensions.fenced_code",
            ],
        )
        return f'<section class="imported-md">{html体}</section>'
    except ImportError:
        打印日志("提示：未安装 markdown 包，已用内置简化转换。建议在容器内执行: pip install markdown")
        return f'<section class="imported-md">{_markdown无库转html(去空白正文)}</section>'


def 发送_json请求(url地址: str, 方法: str = "GET", 请求体: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """发送微信 API 请求并返回 JSON 字典。"""
    数据字节 = None
    if 请求体 is not None:
        数据字节 = json.dumps(请求体, ensure_ascii=False).encode("utf-8")
    请求对象 = request.Request(
        url=url地址,
        data=数据字节,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method=方法,
    )
    with request.urlopen(请求对象, timeout=30) as 响应:
        return json.loads(响应.read().decode("utf-8"))


def 获取access_token(appid: str, appsecret: str) -> str:
    """获取 access_token：后续草稿接口都依赖它。"""
    参数 = {"grant_type": "client_credential", "appid": appid, "secret": appsecret}
    地址 = f"{微信接口基础地址}/token?{parse.urlencode(参数)}"
    返回 = 发送_json请求(地址, 方法="GET")
    token = 返回.get("access_token", "")
    if not token:
        raise RuntimeError(f"获取 access_token 失败: {返回}")
    return token


def _构造multipart表单(字段字典: Dict[str, str], 文件字段名: str, 文件路径: Path) -> Tuple[bytes, str]:
    """构造 multipart/form-data：与 wechat_draft_push 一致，用于上传永久图片素材。"""
    边界字符串 = f"----wechatdraft{uuid.uuid4().hex}"
    边界字节 = 边界字符串.encode("utf-8")
    文件字节 = 文件路径.read_bytes()
    文件名 = 文件路径.name
    文件类型 = mimetypes.guess_type(文件名)[0] or "application/octet-stream"
    片段列表: List[bytes] = []
    for 字段名, 字段值 in 字段字典.items():
        片段列表.extend(
            [
                b"--" + 边界字节 + b"\r\n",
                f'Content-Disposition: form-data; name="{字段名}"\r\n\r\n'.encode("utf-8"),
                字段值.encode("utf-8"),
                b"\r\n",
            ]
        )
    片段列表.extend(
        [
            b"--" + 边界字节 + b"\r\n",
            f'Content-Disposition: form-data; name="{文件字段名}"; filename="{文件名}"\r\n'.encode("utf-8"),
            f"Content-Type: {文件类型}\r\n\r\n".encode("utf-8"),
            文件字节,
            b"\r\n",
            b"--" + 边界字节 + b"--\r\n",
        ]
    )
    请求体 = b"".join(片段列表)
    内容类型 = f"multipart/form-data; boundary={边界字符串}"
    return 请求体, 内容类型


def 上传永久图片素材(access_token: str, 图片路径: Path) -> str:
    """
    调用 material/add_material 上传图片，返回 media_id。
    公众号图文草稿里的 thumb_media_id 即使用该永久素材的 media_id。
    """
    上传地址 = f"{微信接口基础地址}/material/add_material?{parse.urlencode({'access_token': access_token, 'type': 'image'})}"
    请求体, 内容类型 = _构造multipart表单({}, "media", 图片路径)
    请求对象 = request.Request(
        url=上传地址,
        data=请求体,
        headers={"Content-Type": 内容类型},
        method="POST",
    )
    with request.urlopen(请求对象, timeout=60) as 响应对象:
        响应字典 = json.loads(响应对象.read().decode("utf-8"))
    if 响应字典.get("errcode", 0) != 0:
        raise RuntimeError(f"上传默认封面失败: {响应字典}")
    媒体ID = 响应字典.get("media_id")
    if not 媒体ID:
        raise RuntimeError(f"上传封面未返回 media_id: {响应字典}")
    return str(媒体ID)


def 解析封面媒体ID(access_token: str, 命令行封面id: str) -> str:
    """
    决定草稿使用的 thumb_media_id。
    优先级：--thumb-media-id > 环境变量 WECHAT_DEFAULT_THUMB_MEDIA_ID > 本地缓存 >
    同目录 wechat_default_cover.png 自动上传并写缓存 > 历史内置字符串兜底。
    """
    显式 = (命令行封面id or "").strip()
    if 显式:
        return 显式
    环境 = os.environ.get("WECHAT_DEFAULT_THUMB_MEDIA_ID", "").strip()
    if 环境:
        return 环境
    缓存路径 = _脚本目录 / _封面媒体缓存文件名
    if 缓存路径.is_file():
        第一行 = 缓存路径.read_text(encoding="utf-8").strip().splitlines()[0].strip()
        if 第一行:
            return 第一行
    默认图路径 = _脚本目录 / _默认封面图片名
    if 默认图路径.is_file():
        打印日志(f"使用同目录默认封面并上传为素材: {默认图路径.name}")
        新id = 上传永久图片素材(access_token, 默认图路径)
        缓存路径.write_text(新id + "\n", encoding="utf-8")
        打印日志("已写入 default_thumb_media_id.cache，后续草稿不再重复上传")
        return 新id
    if _内置默认封面ID.strip():
        打印日志("未找到 wechat_default_cover.png，使用内置历史 thumb_media_id 兜底")
        return _内置默认封面ID.strip()
    raise RuntimeError(
        "缺少封面素材：请传 --thumb-media-id、或设置 WECHAT_DEFAULT_THUMB_MEDIA_ID、"
        "或与脚本同目录放置 wechat_default_cover.png"
    )


def 创建草稿(
    access_token: str,
    标题: str,
    作者: str,
    摘要: str,
    正文内容: str,
    封面媒体ID: str,
    原文地址: str,
    打开评论: int,
    粉丝评论: int,
) -> Dict[str, Any]:
    """调用微信草稿接口创建草稿。"""
    地址 = f"{微信接口基础地址}/draft/add?{parse.urlencode({'access_token': access_token})}"
    数据 = {
        "articles": [
            {
                "title": 标题,
                "author": 作者,
                "digest": 摘要,
                "content": 正文内容,
                "content_source_url": 原文地址,
                "thumb_media_id": 封面媒体ID,
                "need_open_comment": 打开评论,
                "only_fans_can_comment": 粉丝评论,
            }
        ]
    }
    返回 = 发送_json请求(地址, 方法="POST", 请求体=数据)
    if 返回.get("errcode", 0) != 0:
        raise RuntimeError(f"创建草稿失败: {返回}")
    return 返回


def 加载账号配置(配置路径: Path, 账号名: str) -> Dict[str, str]:
    """从 JSON 配置加载指定账号。"""
    配置文本 = 配置路径.read_text(encoding="utf-8-sig")
    配置对象 = json.loads(配置文本)
    账号对象 = 配置对象.get("accounts", {}).get(账号名, {})
    appid = str(账号对象.get("appid", "")).strip()
    appsecret = str(账号对象.get("appsecret", "")).strip()
    if not appid or not appsecret:
        raise RuntimeError(f"账号配置缺失 appid/appsecret: {账号名}")
    return {"appid": appid, "appsecret": appsecret}


def 解析参数() -> argparse.Namespace:
    """解析 CLI 参数。"""
    解析器 = argparse.ArgumentParser(description="稳定版公众号草稿 CLI")
    解析器.add_argument("--account-config", default="/opt/wechat-draft-cli/accounts.json", help="账号配置 JSON 路径")
    解析器.add_argument("--account-name", required=True, help="账号别名")
    解析器.add_argument("--title", required=True, help="文章标题")
    解析器.add_argument("--author", default="公众号作者", help="作者")
    解析器.add_argument("--digest", default="", help="摘要")
    解析器.add_argument(
        "--content-file",
        required=True,
        help="正文文件路径（.html 原样；.md/.markdown 会转为公众号可用 HTML 段落/标题）",
    )
    解析器.add_argument(
        "--thumb-media-id",
        default="",
        help="封面 thumb_media_id（可空：优先环境变量，其次缓存，再次自动上传同目录 wechat_default_cover.png）",
    )
    解析器.add_argument("--source-url", default="", help="原文链接")
    解析器.add_argument("--open-comment", type=int, choices=[0, 1], default=1, help="是否打开评论")
    解析器.add_argument("--fans-only-comment", type=int, choices=[0, 1], default=0, help="是否仅粉丝可评论")
    return 解析器.parse_args()


def main() -> int:
    """CLI 主流程：加载配置 -> 读取正文 -> 创建草稿。"""
    参数 = 解析参数()
    try:
        配置路径 = Path(参数.account_config).expanduser().resolve()
        正文路径 = Path(参数.content_file).expanduser().resolve()
        if not 配置路径.exists():
            raise RuntimeError(f"账号配置不存在: {配置路径}")
        if not 正文路径.exists():
            raise RuntimeError(f"正文文件不存在: {正文路径}")

        账号 = 加载账号配置(配置路径, 参数.account_name)
        原始正文 = 读取文件内容(正文路径)
        if not 原始正文.strip():
            raise RuntimeError("正文为空")
        正文 = 正文转公众号html(正文路径, 原始正文)

        打印日志("获取 access_token")
        token = 获取access_token(账号["appid"], 账号["appsecret"])
        封面ID = 解析封面媒体ID(token, 参数.thumb_media_id)
        打印日志("创建草稿")
        结果 = 创建草稿(
            access_token=token,
            标题=参数.title,
            作者=参数.author,
            摘要=参数.digest,
            正文内容=正文,
            封面媒体ID=封面ID,
            原文地址=参数.source_url,
            打开评论=参数.open_comment,
            粉丝评论=参数.fans_only_comment,
        )
        mid = 结果.get("media_id", "")
        print("[OK] 草稿创建成功")
        # 固定一行便于人类与日志检索，防止模型口头编造 media_id
        print(f"[WECHAT_API] ok=1 media_id={mid}")
        print(json.dumps(结果, ensure_ascii=False, indent=2))
        return 0
    except Exception as 异常对象:  # noqa: BLE001
        print(f"[ERROR] {异常对象}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

