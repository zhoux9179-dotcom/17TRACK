"""
邮件推送模块 - 跨境热点日报邮件发送
"""

import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Optional

# 在导入 ssl 模块前禁用 SSL 密钥日志，防止 NSS / 本机代理写盘失败
for _k in ("SSLKEYLOGFILE", "SSL_KEYLOGFILE"):
    os.environ.pop(_k, None)

# ─────────────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────────────

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "286590856@qq.com")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "")

# 收件人列表，可改为你希望收取日报的邮箱
RECIPIENT_EMAILS = ["286590856@qq.com"]

SENDER_NAME = "17TRACK 跨境热点日报"
GITHUB_PAGES_URL = "https://zhoux9179-dotcom.github.io/17TRACK/"


# ─────────────────────────────────────────────────────────────
# 公共接口
# ─────────────────────────────────────────────────────────────

def send_report(
    html_content: str,
    date_str: str,
    recipient: Optional[str] = None,
) -> dict:
    recipients = [recipient] if recipient else RECIPIENT_EMAILS

    # ── 主路径：单 HTML 邮件，正文即看板 ─────────────────────
    try:
        msg = _build_html_message(date_str, html_content, recipients)
        _send_via_smtp(msg, recipients)
        return {"ok": True, "sent": recipients}
    except Exception as smtp_err:
        pass

    # ── 备选：标准 multipart/alternative ────────────────────
    try:
        msg = _build_multipart_message(date_str, html_content, recipients)
        _send_via_smtp(msg, recipients)
        return {"ok": True, "sent": recipients, "via": "multipart"}
    except Exception as mp_err:
        return {"ok": False, "error": f"html_only: {smtp_err} | multipart: {mp_err}"}


# ─────────────────────────────────────────────────────────────
# 内部函数
# ─────────────────────────────────────────────────────────────

def _build_html_message(date_str: str, html_content: str, recipients: list[str]) -> MIMEText:
    """纯 HTML 邮件：正文直接是看板，顶部附链接提示"""
    styles = _extract_style_blocks(html_content)
    body = _extract_body(html_content)

    # 顶部插入一行链接提示（横跨全宽，背景醒目）
    link_banner = (
        f'<div style="background:#0f2044;padding:18px 24px;text-align:center;">'
        f'<p style="color:#fff;font-size:14px;margin:0 0 8px;">'
        f'📌 邮件可能无法正常显示，强烈建议点击以下链接在浏览器中查看完整看板：'
        f'</p>'
        f'<a href="{GITHUB_PAGES_URL}" '
        f'style="display:inline-block;background:#2563eb;color:#fff;font-size:15px;'
        f'font-weight:700;padding:10px 28px;border-radius:8px;text-decoration:none;">'
        f'👉 立即打开跨境热点日报看板'
        f'</a>'
        f'<p style="color:rgba(255,255,255,0.45);font-size:12px;margin:10px 0 0;">'
        f'{GITHUB_PAGES_URL}'
        f'</p>'
        f'</div>'
    )

    inner = link_banner + body
    # 保留 <style>（否则邮件里无样式）；QQ 邮箱对完整文档更友好
    full_html = (
        '<!DOCTYPE html><html lang="zh-CN"><head>'
        '<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"{styles}</head><body>{inner}</body></html>"
    )

    msg = MIMEText(full_html, "html", "utf-8")
    msg["Subject"] = Header(
        f"【跨境热点日报】{date_str} — 点击链接查看完整可视化版本", "utf-8"
    ).encode()
    msg["From"] = Header(SENDER_NAME, "utf-8").encode() + f" <{SENDER_EMAIL}>"
    msg["To"] = ", ".join(recipients)
    return msg


def _build_multipart_message(date_str: str, html_content: str, recipients: list[str]) -> MIMEMultipart:
    """标准 multipart/alternative（MIME 部分邮件）"""
    styles = _extract_style_blocks(html_content)
    body = _extract_body(html_content)
    link_banner = (
        f'<div style="background:#0f2044;padding:18px 24px;text-align:center;">'
        f'<p style="color:#fff;font-size:14px;margin:0 0 8px;">'
        f'📌 建议点击链接在浏览器中打开完整看板：'
        f'</p>'
        f'<a href="{GITHUB_PAGES_URL}" '
        f'style="display:inline-block;background:#2563eb;color:#fff;font-size:15px;'
        f'font-weight:700;padding:10px 28px;border-radius:8px;text-decoration:none;">'
        f'👉 打开跨境热点日报看板'
        f'</a>'
        f'<p style="color:rgba(255,255,255,0.45);font-size:12px;margin:10px 0 0;">'
        f'{GITHUB_PAGES_URL}</p></div>'
    )
    inner = link_banner + body
    full_html = (
        '<!DOCTYPE html><html lang="zh-CN"><head>'
        '<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"{styles}</head><body>{inner}</body></html>"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(f"【跨境热点日报】{date_str}", "utf-8").encode()
    msg["From"] = Header(SENDER_NAME, "utf-8").encode() + f" <{SENDER_EMAIL}>"
    msg["To"] = ", ".join(recipients)

    plain = _html_to_plain(inner)
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(full_html, "html", "utf-8"))
    return msg


def _extract_style_blocks(html: str) -> str:
    """从原始日报 HTML 中取出 <style>，供邮件内嵌样式"""
    m = re.search(r"<head[^>]*>(.*?)</head>", html, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    return "\n".join(
        re.findall(r"<style[^>]*>.*?</style>", m.group(1), flags=re.IGNORECASE | re.DOTALL)
    )


def _extract_body(html: str) -> str:
    """去掉 DOCTYPE / <html> / <head> 等外层标签，保留 <body> 内容"""
    # 移除 DOCTYPE
    html = re.sub(r"<!DOCTYPE[^>]*>", "", html, flags=re.IGNORECASE).strip()
    # 移除 <html ...> 和 </html>
    html = re.sub(r"<html[^>]*>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"</html>", "", html, flags=re.IGNORECASE)
    # 移除 <head>...</head>
    html = re.sub(r"<head[^>]*>.*?</head>", "", html, flags=re.IGNORECASE | re.DOTALL)
    # 包裹 <body> 内容
    body_match = re.search(r"<body[^>]*>(.*)</body>", html, flags=re.IGNORECASE | re.DOTALL)
    if body_match:
        return body_match.group(1).strip()
    return html.strip()


def _html_to_plain(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"</div>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _send_via_smtp(msg, recipients: list[str]):
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, recipients, msg.as_string())
