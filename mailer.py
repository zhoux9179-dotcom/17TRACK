"""
邮件推送模块 - 跨境热点日报邮件发送
"""

import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

# 在导入 ssl 模块前禁用 SSL_KEYLOGFILE，防止 NSS 安全软件拦截
os.environ.pop("SSL_KEYLOGFILE", None)

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


# ─────────────────────────────────────────────────────────────
# 公共接口
# ─────────────────────────────────────────────────────────────

def send_report(
    html_content: str,
    date_str: str,
    recipient: Optional[str] = None,
) -> dict:
    recipients = [recipient] if recipient else RECIPIENT_EMAILS

    # ── 主路径：标准 MIMEMultipart，QQ 邮箱兼容性最佳 ───────
    try:
        msg = _build_message(date_str, html_content)
        _send_via_smtp(msg, recipients)
        return {"ok": True, "sent": recipients}
    except Exception as smtp_err:
        pass

    # ── 备选：yagmail（部分 SMTP 受限环境）───────────────────
    try:
        _send_via_yagmail(date_str, html_content, recipients)
        return {"ok": True, "sent": recipients, "via": "yagmail"}
    except Exception as yag_err:
        return {"ok": False, "error": f"smtp: {smtp_err} | yagmail: {yag_err}"}


# ─────────────────────────────────────────────────────────────
# 内部函数
# ─────────────────────────────────────────────────────────────

def _build_message(date_str: str, html_content: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"【跨境热点日报】{date_str}"
    msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"] = ", ".join(RECIPIENT_EMAILS)
    plain = _html_to_plain(html_content)
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))
    return msg


def _html_to_plain(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"</div>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _send_via_yagmail(date_str: str, html_content: str, recipients: list[str]):
    import yagmail
    subject = f"【跨境热点日报】{date_str}"
    yag = yagmail.SMTP(
        user=SENDER_EMAIL,
        password=SENDER_PASSWORD,
        host=SMTP_HOST,
        port=SMTP_PORT,
        smtp_starttls=True,
        smtp_ssl=False,
    )
    yag.send(
        to=recipients,
        subject=subject,
        contents=[_html_to_plain(html_content), html_content],
    )
    yag.close()


def _send_via_smtp(msg: MIMEMultipart, recipients: list[str]):
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, recipients, msg.as_string())
