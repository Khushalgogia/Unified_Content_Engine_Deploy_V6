"""
Notifier — Sends joke results via Telegram and Email.
Adapted from the daily_dispatcher.py notification pattern.
"""

import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# ─── Configuration ───────────────────────────────────────────────────────────

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

EMAIL_SENDER = os.environ.get("P99_SMTP_USER")
EMAIL_PASSWORD = os.environ.get("P99_SMTP_APP_PASSWORD")
EMAIL_RECEIVER = os.environ.get("P99_EMAIL_RECIPIENTS")


# ─── Telegram ────────────────────────────────────────────────────────────────

def send_telegram(message):
    """Send a message via Telegram Bot API. Splits long messages into chunks."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Skipping Telegram: Credentials not found.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # Telegram max message length is 4096 chars
    MAX_LEN = 4000
    chunks = []

    if len(message) <= MAX_LEN:
        chunks = [message]
    else:
        # Split by double newlines (between headlines)
        sections = message.split("\n\n")
        current_chunk = ""
        for section in sections:
            if len(current_chunk) + len(section) + 2 > MAX_LEN:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = section
            else:
                current_chunk += "\n\n" + section
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "HTML",
        }
        try:
            resp = requests.post(url, data=payload, timeout=30)
            if resp.status_code == 200:
                print(f"   ✅ Telegram chunk {i+1}/{len(chunks)} sent.")
            else:
                print(f"   ⚠️ Telegram chunk {i+1} failed: {resp.text[:200]}")
        except Exception as e:
            print(f"   ❌ Telegram failed: {e}")


# ─── Email ───────────────────────────────────────────────────────────────────

def send_email(subject, html_body):
    """Send an email via Gmail SMTP."""
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        print("⚠️ Skipping Email: Credentials not found.")
        return

    recipients = [email.strip() for email in EMAIL_RECEIVER.split(',')]

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, recipients, msg.as_string())
        server.quit()
        print(f"   ✅ Email sent to: {recipients}")
    except Exception as e:
        print(f"   ❌ Email failed: {e}")


# ─── Format & Send Jokes ────────────────────────────────────────────────────

def notify_jokes(headlines, jokes_by_headline):
    """
    Format 100 jokes nicely and send via Telegram + Email.
    
    Args:
        headlines: List of headline strings
        jokes_by_headline: Dict {headline: [joke_dicts]}
    """
    total = sum(len(j) for j in jokes_by_headline.values())

    # ── Build Telegram message (HTML format) ──
    tg_parts = [
        f"🎭 <b>DAILY COMEDY BRIEF</b> 🎭\n"
        f"📰 {len(headlines)} Headlines × 20 Jokes = {total} Total\n"
        f"{'─' * 30}"
    ]

    for headline in headlines:
        jokes = jokes_by_headline.get(headline, [])
        if not jokes:
            continue

        tg_parts.append(f"\n📰 <b>{headline}</b> ({len(jokes)} jokes)\n")

        for i, joke_data in enumerate(jokes, 1):
            joke_text = joke_data.get("joke", "N/A")
            engine = joke_data.get("engine", "?")
            tg_parts.append(f"  {i}. {joke_text}\n     <i>[{engine}]</i>")

    tg_message = "\n".join(tg_parts)

    # ── Build Email (HTML format) ──
    email_rows = []
    for headline in headlines:
        jokes = jokes_by_headline.get(headline, [])
        if not jokes:
            continue

        email_rows.append(
            f'<tr><td colspan="3" style="background:#1e1e2e;color:#fbbf24;'
            f'padding:12px;font-size:16px;font-weight:bold;border-radius:8px;">'
            f'📰 {headline} ({len(jokes)} jokes)</td></tr>'
        )

        for i, joke_data in enumerate(jokes, 1):
            joke_text = joke_data.get("joke", "N/A")
            engine = joke_data.get("engine", "?")
            strategy = joke_data.get("selected_strategy", "")[:60]
            bg = "#f8f9fa" if i % 2 == 0 else "#ffffff"

            email_rows.append(
                f'<tr style="background:{bg};">'
                f'<td style="padding:8px;color:#666;width:30px;">{i}.</td>'
                f'<td style="padding:8px;">{joke_text}</td>'
                f'<td style="padding:8px;color:#888;font-size:12px;">'
                f'<em>{engine}</em><br>{strategy}</td>'
                f'</tr>'
            )

    email_html = f"""
    <html>
    <body style="font-family: 'Inter', Arial, sans-serif; max-width: 800px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #667eea, #764ba2); color: white;
                    padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 20px;">
            <h1 style="margin: 0;">🎭 Daily Comedy Brief</h1>
            <p style="margin: 5px 0 0 0; opacity: 0.9;">
                {len(headlines)} Headlines × 20 Jokes = {total} Total
            </p>
        </div>
        
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
            {''.join(email_rows)}
        </table>
        
        <p style="text-align: center; color: #999; font-size: 12px; margin-top: 20px;">
            Unified Content Engine V6 — Automated Daily Brief
        </p>
    </body>
    </html>
    """

    # ── Send ──
    print("\n📨 Sending notifications...")

    print("   📱 Telegram...")
    send_telegram(tg_message)

    print("   📧 Email...")
    send_email(
        subject=f"🎭 Daily Comedy Brief — {total} Jokes from {len(headlines)} Headlines",
        html_body=email_html,
    )

    print("   ✅ Notifications complete!")


if __name__ == "__main__":
    # Test with dummy data
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).parent.parent.parent / ".env")

    test_headlines = ["Test Headline 1", "Test Headline 2"]
    test_jokes = {
        "Test Headline 1": [{"joke": "This is a test joke", "engine": "test", "selected_strategy": "testing"}],
        "Test Headline 2": [{"joke": "Another test joke", "engine": "test", "selected_strategy": "testing"}],
    }
    notify_jokes(test_headlines, test_jokes)
