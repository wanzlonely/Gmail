import imaplib
import email
import asyncio
import ssl
import re
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import MAIL_SERVER, IMAP_PORT
from modules import storage

_BTN_HOME = [[InlineKeyboardButton("⎔ **KEMBALI KE MENU** ⎔", callback_data="home")]]

def _safe_md(text: str) -> str:
    if not text: 
        return ""
    return text.replace('`', "'").replace('_', '-').replace('*', '•').replace('[', '(').replace(']', ')')

def _clean_html(raw_html: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', raw_html, flags=re.IGNORECASE)
    text = re.sub(r'</?(p|div|tr|li|ul|ol)[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<style.*?>.*?</style>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    text = text.replace("Contact usIf", "If").replace("Hubungi kamiJika", "Jika")
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n', text)
    return text.strip()

def _check_inbox(check_email: str, check_pass: str) -> str:
    mail = None
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        mail = imaplib.IMAP4_SSL(MAIL_SERVER, IMAP_PORT, ssl_context=ctx)
        mail.login(check_email, check_pass)
        mail.select("INBOX")
        status, messages = mail.search(None, "ALL")
        email_ids = messages[0].split()
        
        if not email_ids:
            mail.logout()
            return "┌─〔 ◈ **KOTAK POS KOSONG** 〕─┐\n│\n├─ ◈ **Informasi** : `Tidak Ada Data`\n│\n└─〔 **Pemindaian Selesai** 〕─┘"
            
        latest_ids = email_ids[-3:]
        username = check_email.split('@')[0]
        
        result_text = (
            "┌─〔 ◈ **KOTAK POS MASUK** ◈ 〕─┐\n"
            "│\n"
            f"├─ ⊛ **Node Host** : `{username}@xxxxxxxxx`\n"
            "├──────────────────────────\n"
        )
        
        for e_id in reversed(latest_ids):
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    subject = msg.get("Subject", "No Subject")
                    decoded = email.header.decode_header(subject)[0]
                    subject_str = decoded[0]
                    if isinstance(subject_str, bytes):
                        subject_str = subject_str.decode(errors="ignore")
                        
                    sender = msg.get("From", "Unknown")
                    body = ""
                    
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode(errors="ignore")
                                break
                    else:
                        body = msg.get_payload(decode=True).decode(errors="ignore")
                        
                    body_clean = _clean_html(body).strip()
                    
                    if "mailer-daemon" in str(sender).lower() or "bounce" in body_clean.lower():
                        match = re.search(r'status:\s*([0-9\.]+)', body_clean, re.IGNORECASE)
                        err_code = match.group(0) if match else "Bounce Detected"
                        body_clean = f"⚠️ **TERBANTUL (BOUNCED)**\n`Kode: {err_code}`\n\n" + body_clean
                        
                    if not body_clean: 
                        body_clean = "[Format Non-Teks]"
                        
                    result_text += (
                        f"│ ◈ **Pengirim** : `{_safe_md(str(sender))}`\n"
                        f"│ ◈ **Perihal** : {_safe_md(subject_str)}\n"
                        f"│ ◈ **Isi Teks** :\n`{_safe_md(body_clean[:220])}...`\n"
                        "├──────────────────────────\n"
                    )
                    
        result_text += "└─〔 **Akhir Transmisi Kotak Pos** 〕─┘"
        mail.logout()
        return result_text.strip()
        
    except Exception as e:
        if mail:
            try: 
                mail.logout()
            except Exception: 
                pass
        raise e

async def execute_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    stored = storage.get_email(user_id)
    
    if not stored:
        await query.edit_message_text(
            "┌─〔 ⊗ **AKSES DITOLAK** 〕─┐\n│\n├─ ◈ **Informasi** : `Jalur Belum Aktif`\n│\n└─〔 **Sesi Pembatalan** 〕─┘",
            reply_markup=InlineKeyboardMarkup(_BTN_HOME),
            parse_mode="Markdown"
        )
        return

    msg_ui = await query.edit_message_text(
        "┌─〔 ⟁ **KONEKSI STORAGE** 〕─┐\n│\n├─ ◈ **Status** : `Menembus IMAP Gate`\n│\n└─〔 **Mohon Tunggu** 〕─┘",
        parse_mode="Markdown"
    )
    
    try:
        result_text = await asyncio.to_thread(_check_inbox, stored["email"], stored["password"])
        await msg_ui.edit_text(result_text, reply_markup=InlineKeyboardMarkup(_BTN_HOME), parse_mode="Markdown")
    except Exception as e:
        await msg_ui.edit_text(
            f"┌─〔 ⊗ **KONEKSI GAGAL** 〕─┐\n│\n├─ ◈ **Error** : `{_safe_md(str(e))}`\n│\n└─〔 **Pemindaian Batal** 〕─┘",
            reply_markup=InlineKeyboardMarkup(_BTN_HOME),
            parse_mode="Markdown"
        )

