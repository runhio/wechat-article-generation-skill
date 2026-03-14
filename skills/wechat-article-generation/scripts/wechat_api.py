#!/usr/bin/env python3
"""
WeChat Official Account API client.
Publish Markdown articles to WeChat drafts via official API.

Usage:
    # First-time setup
    python wechat_api.py setup

    # Check config
    python wechat_api.py check-env

    # Publish markdown article
    python wechat_api.py publish --markdown /path/to/article.md

    # Publish with options
    python wechat_api.py publish --markdown article.md --author "Author Name"
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://api.weixin.qq.com/cgi-bin"
CONFIG_DIR = Path.home() / ".wechat-publisher"
CONFIG_FILE = CONFIG_DIR / "config.json"
TOKEN_CACHE_FILE = CONFIG_DIR / "token_cache.json"

ERROR_CODES = {
    40001: "AppSecret 错误或不属于此 AppID",
    40002: "请确保 grant_type 为 client_credential",
    40013: "AppID 不合法",
    40125: "AppSecret 无效",
    40164: "IP 地址不在白名单中",
    41001: "缺少 access_token",
    42001: "access_token 已过期",
    45009: "每日 API 调用次数已达上限",
    48001: "API 功能未授权，请确认公众号类型",
}


# ============================================================
# Config management
# ============================================================

def load_env_file():
    """Search for .env file from cwd upward, load into os.environ."""
    current = Path.cwd()
    for _ in range(5):
        env_file = current / ".env"
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and value:
                            os.environ.setdefault(key, value)
            return
        current = current.parent

    # Also check skill directory
    skill_env = Path(__file__).parent.parent / ".env"
    if skill_env.exists():
        with open(skill_env, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        os.environ.setdefault(key, value)


def load_config():
    """Load AppID and AppSecret. Priority: .env > ~/.wechat-publisher/config.json"""
    # Try .env first
    load_env_file()
    appid = os.environ.get("WECHAT_APPID", "").strip()
    appsecret = os.environ.get("WECHAT_SECRET", "").strip()

    if appid and appsecret:
        return appid, appsecret

    # Fallback to config file
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            appid = config.get("appid", "").strip()
            appsecret = config.get("appsecret", "").strip()
            if appid and appsecret:
                return appid, appsecret
        except Exception:
            pass

    print("未找到微信公众号配置。请通过以下任一方式配置：", file=sys.stderr)
    print("", file=sys.stderr)
    print("  方式1: 在 .env 文件中添加:", file=sys.stderr)
    print("    WECHAT_APPID=你的AppID", file=sys.stderr)
    print("    WECHAT_SECRET=你的AppSecret", file=sys.stderr)
    print("", file=sys.stderr)
    print("  方式2: 运行交互式配置:", file=sys.stderr)
    print("    python wechat_api.py setup", file=sys.stderr)
    sys.exit(1)


def save_config(appid, appsecret):
    """Save config to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = {"appid": appid, "appsecret": appsecret}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    os.chmod(CONFIG_FILE, 0o600)
    print(f"配置已保存: {CONFIG_FILE} (权限 600)")


# ============================================================
# Access token
# ============================================================

def get_access_token(force_refresh=False):
    """Get access_token, use cache if valid."""
    # Try cache first
    if not force_refresh and TOKEN_CACHE_FILE.exists():
        try:
            with open(TOKEN_CACHE_FILE, "r") as f:
                cache = json.load(f)
            if time.time() < cache.get("expires_at", 0) - 300:
                return cache["access_token"]
        except Exception:
            pass

    appid, appsecret = load_config()
    params = urlencode({
        "grant_type": "client_credential",
        "appid": appid,
        "secret": appsecret,
    })
    url = f"{BASE_URL}/token?{params}"

    try:
        with urlopen(url, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"获取 access_token 失败: {e}", file=sys.stderr)
        sys.exit(1)

    if "errcode" in result and result["errcode"] != 0:
        code = result["errcode"]
        print(result)
        msg = ERROR_CODES.get(code, result.get("errmsg", "Unknown"))
        print(f"获取 access_token 失败 ({code}): {msg}", file=sys.stderr)
        if code == 40164:
            print("\n请将服务器 IP 添加到微信公众平台白名单：", file=sys.stderr)
            print("  微信公众平台 → 设置与开发 → 基本配置 → IP白名单", file=sys.stderr)
        sys.exit(1)

    token = result["access_token"]
    expires_in = result.get("expires_in", 7200)

    # Cache token
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_CACHE_FILE, "w") as f:
        json.dump({
            "access_token": token,
            "expires_at": time.time() + expires_in,
        }, f)

    return token


# ============================================================
# Markdown to HTML conversion (AI Tech Purple Theme)
# ============================================================

# --- Inline style constants (WeChat requires all CSS inline) ---

S_H2 = (
    "font-size:22px;font-weight:700;line-height:1.4;"
    "margin:32px 0 16px;color:#333;"
    "padding:8px 16px;border-left:4px solid #7c3aed;"
    "background:#faf5ff;"
)
S_H3 = (
    "font-size:18px;font-weight:700;line-height:1.4;"
    "margin:28px 0 12px;color:#333;"
    "padding-left:12px;border-left:3px solid #7c3aed;"
)
S_H4 = "font-size:16px;font-weight:700;margin:24px 0 10px;color:#7c3aed;"
S_SECTION = "color:#333;font-size:16px;line-height:1.8;word-wrap:break-word;"
S_P = "margin:16px 0;line-height:1.8;color:#333;font-size:16px;"
S_URL = "color:#7c3aed;word-break:break-all;font-size:14px;"
S_STRONG = "font-weight:600;color:#333;"
S_EM = "font-style:italic;color:#4b5563;"
S_INLINE_CODE = (
    "background:#f5f5f5;color:#e83e8c;padding:2px 6px;border-radius:4px;"
    "font-family:SFMono-Regular,Consolas,monospace;font-size:0.9em;"
)
S_PRE = (
    "background:#282c34;color:#abb2bf;padding:16px 20px;border-radius:8px;"
    "overflow-x:auto;margin:20px 0;line-height:1.6;font-size:14px;"
    "font-family:SFMono-Regular,Consolas,Liberation Mono,Menlo,monospace;"
)
S_BLOCKQUOTE = (
    "margin:24px 0;padding:16px 20px;background:#f3f4f6;"
    "border-left:4px solid #7c3aed;border-radius:0 8px 8px 0;"
)
S_BQ_P = "margin:0;font-style:italic;color:#4b5563;line-height:1.8;"
S_UL = "margin:16px 0;padding-left:24px;"
S_OL = "margin:16px 0;padding-left:24px;"
S_LI = "margin:8px 0;line-height:1.8;color:#333;"
S_TABLE = "width:100%;border-collapse:collapse;margin:20px 0;font-size:15px;"
S_TH = (
    "padding:12px 16px;text-align:left;font-weight:600;"
    "background:#7c3aed;color:#ffffff;border:1px solid #7c3aed;"
)
S_TD = "padding:12px 16px;border:1px solid #e5e7eb;color:#333;"
S_TD_EVEN = S_TD + "background:#f9fafb;"
S_HR = "border:none;height:2px;background:#7c3aed;margin:40px 0;opacity:0.5;"


def markdown_to_html(md_text):
    """Convert Markdown to WeChat-compatible HTML with AI Tech theme."""
    lines = md_text.split("\n")
    html_parts = []
    in_code_block = False
    code_lines = []
    code_lang = ""
    in_list = False
    list_type = None
    # Table state
    in_table = False
    table_rows = []

    def close_list():
        nonlocal in_list, list_type
        if in_list:
            tag = "ol" if list_type == "ol" else "ul"
            html_parts.append(f"</{tag}>")
            in_list = False
            list_type = None

    def close_table():
        nonlocal in_table, table_rows
        if in_table and table_rows:
            html_parts.append(build_table(table_rows))
            table_rows = []
            in_table = False

    def inline_format(text):
        """Handle inline formatting."""
        # Inline code (before bold/italic to avoid conflicts)
        text = re.sub(
            r"`([^`]+)`",
            rf'<code style="{S_INLINE_CODE}">\1</code>',
            text,
        )
        # Bold
        text = re.sub(
            r"\*\*(.+?)\*\*",
            rf'<strong style="{S_STRONG}">\1</strong>',
            text,
        )
        # Italic
        text = re.sub(
            r"\*([^*]+)\*",
            rf'<em style="{S_EM}">\1</em>',
            text,
        )
        # URLs — render as styled span (WeChat blocks external hyperlinks)
        text = re.sub(
            r'(https?://[^\s<>"\']+)',
            rf'<span style="{S_URL}">\1</span>',
            text,
        )
        return text

    def build_table(rows):
        """Build styled HTML table from parsed rows."""
        if not rows:
            return ""
        parts = [f'<table style="{S_TABLE}">']

        for i, row in enumerate(rows):
            # Skip separator row (---)
            if all(cell.strip().replace("-", "") == "" for cell in row):
                continue
            parts.append("<tr>")
            for cell in row:
                cell_text = inline_format(cell.strip())
                if i == 0:
                    parts.append(f'<th style="{S_TH}">{cell_text}</th>')
                else:
                    style = S_TD_EVEN if i % 2 == 0 else S_TD
                    parts.append(f'<td style="{style}">{cell_text}</td>')
            parts.append("</tr>")

        parts.append("</table>")
        return "\n".join(parts)

    for line in lines:
        stripped = line.strip()

        # --- Code block ---
        if stripped.startswith("```"):
            if in_code_block:
                code_content = "\n".join(code_lines)
                lang_label = ""
                if code_lang:
                    lang_label = (
                        f'<span style="position:relative;float:right;'
                        f'color:#5c6370;font-size:12px;'
                        f'text-transform:uppercase;">{code_lang}</span>'
                    )
                html_parts.append(
                    f'<pre style="{S_PRE}">'
                    f"{lang_label}"
                    f"<code>{code_content}</code></pre>"
                )
                code_lines = []
                code_lang = ""
                in_code_block = False
            else:
                close_list()
                close_table()
                code_lang = stripped[3:].strip()
                in_code_block = True
            continue

        if in_code_block:
            escaped = (
                line.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            code_lines.append(escaped)
            continue

        # --- Table ---
        if "|" in stripped and stripped.startswith("|"):
            close_list()
            cells = [c for c in stripped.split("|")[1:-1]]  # strip outer |
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(cells)
            continue
        else:
            close_table()

        # --- Empty line ---
        if not stripped:
            close_list()
            continue

        # --- Horizontal rule ---
        if stripped in ("---", "***", "___"):
            close_list()
            html_parts.append(f'<hr style="{S_HR}">')
            continue

        # --- Headers ---
        if stripped.startswith("# ") and not stripped.startswith("## "):
            close_list()
            text = inline_format(stripped[2:])
            html_parts.append(
                f'<h1 style="font-size:26px;font-weight:700;'
                f'margin:24px 0 16px;color:#333;'
                f'padding-bottom:12px;border-bottom:3px solid #7c3aed;">'
                f"{text}</h1>"
            )
            continue
        if stripped.startswith("## ") and not stripped.startswith("### "):
            close_list()
            text = inline_format(stripped[3:])
            html_parts.append(f'<h2 style="{S_H2}">{text}</h2>')
            continue
        if stripped.startswith("### ") and not stripped.startswith("#### "):
            close_list()
            text = inline_format(stripped[4:])
            html_parts.append(f'<h3 style="{S_H3}">{text}</h3>')
            continue
        if stripped.startswith("#### "):
            close_list()
            text = inline_format(stripped[5:])
            html_parts.append(f'<h4 style="{S_H4}">{text}</h4>')
            continue

        # --- Blockquote ---
        if stripped.startswith("> "):
            close_list()
            text = inline_format(stripped[2:])
            html_parts.append(
                f'<blockquote style="{S_BLOCKQUOTE}">'
                f'<p style="{S_BQ_P}">{text}</p></blockquote>'
            )
            continue

        # --- Unordered list (use <p> with bullet char for WeChat compat) ---
        if stripped.startswith("- ") or stripped.startswith("* "):
            close_list()
            text = inline_format(stripped[2:])
            html_parts.append(
                f'<p style="{S_P}margin:4px 0;">• {text}</p>'
            )
            continue

        # --- Ordered list ---
        ol_match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if ol_match:
            text = inline_format(ol_match.group(2))
            if not in_list or list_type != "ol":
                close_list()
                html_parts.append(f'<ol style="{S_OL}">')
                in_list = True
                list_type = "ol"
            html_parts.append(f'<li style="{S_LI}">{text}</li>')
            continue

        # --- Skip empty lines ---
        if not stripped:
            continue

        # --- Regular paragraph ---
        close_list()
        text = inline_format(stripped)
        html_parts.append(f'<p style="{S_P}">{text}</p>')

    # Close any open structures
    close_list()
    close_table()
    if in_code_block and code_lines:
        code_content = "\n".join(code_lines)
        html_parts.append(f'<pre style="{S_PRE}"><code>{code_content}</code></pre>')

    body = "\n".join(html_parts)
    return f'<section style="{S_SECTION}">{body}</section>'


# ============================================================
# Parse markdown file
# ============================================================

def parse_markdown(filepath):
    """Parse a markdown file, extract title and body."""
    path = Path(filepath)
    if not path.exists():
        print(f"文件不存在: {filepath}", file=sys.stderr)
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
    lines = content.strip().split("\n")

    # Extract H1 as title
    title = "Untitled"
    content_start = 0
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            content_start = idx + 1
            break
        elif not stripped.startswith("!["):
            title = stripped[:64]
            break

    body_md = "\n".join(lines[content_start:]).strip()

    # Extract summary from first paragraph
    summary = ""
    for line in lines[content_start:]:
        stripped = line.strip()
        if stripped and not stripped.startswith(("#", "!", ">", "-", "*", "`")):
            summary = stripped[:120]
            break

    return {
        "title": title,
        "body_markdown": body_md,
        "body_html": markdown_to_html(body_md),
        "summary": summary,
    }


# ============================================================
# Publish
# ============================================================

def upload_thumb_image(image_path):
    """Upload a thumb image to WeChat and return media_id."""
    token = get_access_token()
    url = f"{BASE_URL}/material/add_material?access_token={token}&type=image"

    import mimetypes
    content_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    filename = os.path.basename(image_path)

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    with open(image_path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    try:
        with urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"上传封面图失败: {e}", file=sys.stderr)
        return None

    if "media_id" in result:
        print(f"封面图上传成功: {result['media_id']}")
        return result["media_id"]
    else:
        print(f"上传封面图失败: {result}", file=sys.stderr)
        return None


def create_draft(title, html_content, author="", digest="", thumb_media_id=""):
    """Create a draft article via WeChat API."""
    token = get_access_token()
    url = f"{BASE_URL}/draft/add?access_token={token}"

    # Truncate fields to WeChat limits
    title = title[:64]
    if author:
        # 20 bytes max
        while len(author.encode("utf-8")) > 20:
            author = author[:-1]
    if not digest:
        digest = title
    while len(digest.encode("utf-8")) > 120:
        digest = digest[:-1]

    # Upload cover image if no thumb_media_id provided
    if not thumb_media_id:
        skill_dir = Path(__file__).parent.parent
        cover_candidates = [
            skill_dir / "assets" / "default_cover.jpg",
            skill_dir / "assets" / "default_cover.png",
        ]
        for cover_path in cover_candidates:
            if cover_path.exists():
                thumb_media_id = upload_thumb_image(str(cover_path))
                if thumb_media_id:
                    break

    article = {
        "title": title,
        "author": author,
        "digest": digest,
        "content": html_content,
        "content_source_url": "",
        "thumb_media_id": thumb_media_id or "",
        "show_cover_pic": 0,
        "need_open_comment": 1,
        "only_fans_can_comment": 0,
    }

    data = json.dumps({"articles": [article]}, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")

    try:
        with urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"创建草稿失败: {e}", file=sys.stderr)
        sys.exit(1)

    errcode = result.get("errcode", 0)
    if errcode != 0:
        # Retry once if token expired
        if errcode in (40001, 42001):
            print("access_token 已过期，正在刷新...")
            token = get_access_token(force_refresh=True)
            url = f"{BASE_URL}/draft/add?access_token={token}"
            req = Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json; charset=utf-8")
            with urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            if result.get("errcode", 0) != 0:
                msg = ERROR_CODES.get(result["errcode"], result.get("errmsg", "Unknown"))
                print(f"创建草稿失败 ({result['errcode']}): {msg}", file=sys.stderr)
                sys.exit(1)
        else:
            msg = ERROR_CODES.get(errcode, result.get("errmsg", "Unknown"))
            print(f"创建草稿失败 ({errcode}): {msg}", file=sys.stderr)
            if errcode == 40164:
                print("\n请将 IP 添加到微信公众平台白名单", file=sys.stderr)
            sys.exit(1)

    media_id = result.get("media_id", "")
    print(f"草稿创建成功! media_id: {media_id}")
    return result


# ============================================================
# CLI commands
# ============================================================

def cmd_setup():
    """Interactive setup."""
    print("=" * 50)
    print("  微信公众号配置向导")
    print("=" * 50)
    print()
    print("获取方式：")
    print("  1. 登录 https://mp.weixin.qq.com")
    print("  2. 设置与开发 → 基本配置")
    print("  3. 复制 AppID 和 AppSecret")
    print()

    appid = input("AppID (wx开头): ").strip()
    appsecret = input("AppSecret: ").strip()

    if not appid:
        print("AppID 不能为空", file=sys.stderr)
        sys.exit(1)
    if not appsecret:
        print("AppSecret 不能为空", file=sys.stderr)
        sys.exit(1)

    save_config(appid, appsecret)
    print()

    # Test connection
    print("正在测试连接...")
    try:
        token = get_access_token(force_refresh=True)
        print(f"连接成功! access_token: {token[:10]}...")
    except SystemExit:
        print("连接失败，请检查 AppID、AppSecret 和 IP 白名单", file=sys.stderr)


def cmd_check_env():
    """Check config status."""
    appid, appsecret = load_config()
    masked_secret = appsecret[:4] + "..." + appsecret[-4:] if len(appsecret) > 8 else "***"
    print(f"AppID:     {appid}")
    print(f"AppSecret: {masked_secret}")

    # Test token
    print("\n正在测试 access_token...")
    try:
        token = get_access_token()
        print(f"access_token: {token[:10]}... (有效)")
    except SystemExit:
        print("access_token 获取失败", file=sys.stderr)


def cmd_publish(args):
    """Publish article."""
    if not args.markdown:
        print("需要 --markdown 参数", file=sys.stderr)
        sys.exit(1)

    parsed = parse_markdown(args.markdown)
    title = args.title or parsed["title"]
    html = parsed["body_html"]
    author = args.author or ""
    digest = args.summary or parsed["summary"]

    print(f"标题: {title}")
    print(f"作者: {author or '(未设置)'}")
    print(f"摘要: {digest[:50]}...")
    print(f"内容: {len(parsed['body_markdown'])} 字符 (Markdown)")
    print(f"HTML: {len(html)} 字符")
    print()

    result = create_draft(title=title, html_content=html, author=author, digest=digest)
    print(f"\n发布成功! 请前往微信公众号后台查看草稿:")
    print("https://mp.weixin.qq.com")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="微信公众号 API 客户端")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("setup", help="配置 AppID 和 AppSecret")
    subparsers.add_parser("check-env", help="检查配置状态")

    pub = subparsers.add_parser("publish", help="发布文章到草稿箱")
    pub.add_argument("--markdown", required=True, help="Markdown 文件路径")
    pub.add_argument("--title", help="自定义标题（默认从文件提取）")
    pub.add_argument("--author", help="作者名")
    pub.add_argument("--summary", help="摘要（默认从首段提取）")

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup()
    elif args.command == "check-env":
        cmd_check_env()
    elif args.command == "publish":
        cmd_publish(args)


if __name__ == "__main__":
    main()
