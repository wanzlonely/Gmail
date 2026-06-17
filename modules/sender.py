import smtplib
import asyncio
import random
import uuid
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import MAIL_SERVER, SMTP_PORT
from modules import storage

ASK_NOMOR = 1

_RECEIVER_LIST = [
    "smb_web@support.whatsapp.com",
    "android_web@support.whatsapp.com",
    "iphone_web@support.whatsapp.com",
    "support@whatsapp.com",
    "support@support.whatsapp.com"
]

DEFAULT_SUBJECT_LIST = [
    "Urgent: Account Access Issue",
    "Request for Account Review - Connection Error",
    "Appealing Account Restriction",
    "Need Assistance with Number Registration"
]

LANG_LABELS = ["𝗜𝗗𝗡_𝗣𝗥𝗢𝗫𝗬", "𝗕𝗥𝗭_𝗣𝗥𝗢𝗫𝗬", "𝗘𝗡𝗚_𝗣𝗥𝗢𝗫𝗬"]

_DISPLAY_NAMES = [
    "WhatsApp Support",
    "Helpdesk Team",
    "System Administrator",
    "Service Center",
    "User Appeal"
]

_TEMPLATES = [
    (
        "Halo Tim Support,\n\nSaya mohon bantuannya. Sepertinya ada kesalahan teknis "
        "yang menyebabkan nomor saya ({nomor}) tidak bisa menggunakan aplikasi WhatsApp. "
        "Saya tidak pernah menggunakan aplikasi pihak ketiga atau melanggar ketentuan. "
        "Mohon bantuannya untuk memulihkan akses saya karena nomor ini terhubung dengan keluarga dan pekerjaan saya.\n\nTerima kasih."
    ),
    (
        "Olá Equipe de Suporte,\n\nEstou enfrentando um problema e preciso de ajuda. "
        "Meu número {nomor} foi bloqueado ou apresenta erro de registro sem motivo aparente. "
        "Utilizo apenas a versão oficial do aplicativo e sigo os termos de serviço. "
        "Por favor, revisem minha conta, pois preciso muito dela para contatos familiares.\n\nMuito obrigado."
    ),
    (
        "Hello Support Team,\n\nI am writing to appeal an issue with my number: {nomor}. "
        "I am currently unable to log in, and it says my number is restricted. "
        "I strictly use the official application and have not violated any terms of service. "
        "Could you please review my account and restore my access? I rely on this number for daily communication.\n\nThank you for your time."
    ),
]

_XMAILER_LIST = [
    "Microsoft Outlook 16.0.14931.20132",
    "Apple Mail 16.0 (3696.120.41.1.1)",
    "Mozilla Thunderbird 115.12.0",
    "iPhone Mail (18E212)",
]

_BTN_HOME = [[InlineKeyboardButton("⎔ **KEMBALI KE MENU** ⎔", callback_data="home")]]

def _build_email(nomor: str, user_id: int) -> tuple[str, str]:
    subject  = random.choice(DEFAULT_SUBJECT_LIST)
    tmpl_idx = storage.get_template_index(user_id)
    body     = _TEMPLATES[tmpl_idx].format(nomor=nomor)
    return subject, body

def _send_email(sender_email: str, sender_pass: str, receiver: str, subject: str, body: str) -> None:
    msg        = MIMEMultipart("alternative")
    domain     = sender_email.split("@")[1]
    
    display_name      = random.choice(_DISPLAY_NAMES)
    msg["From"]       = f"{display_name} <{sender_email}>"
    msg["To"]         = receiver
    msg["Subject"]    = subject
    msg["Date"]       = formatdate(localtime=True)
    msg["Message-ID"] = f"<{uuid.uuid4().hex}.{uuid.uuid4().hex[:8]}@{domain}>"
    msg["Reply-To"]   = sender_email
    msg["X-Mailer"]   = random.choice(_XMAILER_LIST)
    msg["MIME-Version"] = "1.0"
    
    msg.attach(MIMEText(body, "plain", "utf-8"))
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    server = smtplib.SMTP(MAIL_SERVER, SMTP_PORT, timeout=30)
    server.ehlo()
    server.starttls(context=ctx)
    server.login(sender_email, sender_pass)
    server.send_message(msg)
    server.quit()

async def start_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user_id = update.effective_user.id
    ok, reason = storage.can_send(user_id)
    
    if not ok:
        await update.callback_query.edit_message_text(
            reason, 
            reply_markup=InlineKeyboardMarkup(_BTN_HOME), 
            parse_mode="Markdown"
        )
        return ConversationHandler.END
        
    stored = storage.get_email(user_id)
    
    if not stored:
        await update.callback_query.edit_message_text(
            "┌─〔 ⊗ **AKSES MINIMAL** 〕─┐\n│\n├─ ◈ **Kondisi** : `Jalur Belum Dibuat`\n├─ ◈ `Silakan buat jalur`\n├─ ◈ `terlebih dahulu.`\n│\n└─〔 **Sesi Dibatalkan** 〕─┘",
            reply_markup=InlineKeyboardMarkup(_BTN_HOME), 
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    if storage.is_used(user_id):
        await update.callback_query.edit_message_text(
            "┌─〔 ⊗ **AKSES TERKUNCI** 〕─┐\n│\n├─ ◈ **Kondisi** : `Node Telah Terpakai`\n├─ ◈ `Hancurkan jalur lama dan`\n├─ ◈ `buat jalur baru.`\n│\n└─〔 **Proteksi Spam** 〕─┘",
            reply_markup=InlineKeyboardMarkup(_BTN_HOME), 
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    await update.callback_query.edit_message_text(
        "┌─〔 ◈ **TARGET ROUTING** ◈ 〕─┐\n│\n├─ ◈ **Perintah** : `Masukkan Nomor Target`\n├─ ◈ **Format** : `+6281234567890`\n│\n└─〔 **Menunggu Input** 〕─┘",
        reply_markup=InlineKeyboardMarkup(_BTN_HOME), 
        parse_mode="Markdown"
    )
    return ASK_NOMOR

async def process_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nomor   = update.message.text.strip()
    user_id = update.effective_user.id
    
    ok, reason = storage.can_send(user_id)
    if not ok:
        await update.message.reply_text(reason, reply_markup=InlineKeyboardMarkup(_BTN_HOME), parse_mode="Markdown")
        return ConversationHandler.END

    stored = storage.get_email(user_id)
    if not stored: 
        return ConversationHandler.END

    sender_email = stored["email"]
    sender_pass  = stored["password"]
    subject, body = _build_email(nomor, user_id)
    tmpl_idx      = storage.get_template_index(user_id)
    lang_label    = LANG_LABELS[tmpl_idx]
    target_rcv    = random.choice(_RECEIVER_LIST)

    msg_ui = await update.message.reply_text(
        "┌─〔 ⟁ **EKSEKUSI TRANSMISI** 〕─┐\n│\n├─ ◈ **Status** : `Meneruskan ke VPS`\n│\n└─〔 **Mohon Tunggu** 〕─┘", 
        parse_mode="Markdown"
    )
    
    try:
        await asyncio.to_thread(_send_email, sender_email, sender_pass, target_rcv, subject, body)
        storage.log_send(user_id)
        storage.mark_used(user_id)
        
        count     = storage.get_send_count(user_id)
        max_daily = storage.get_max_daily(user_id)
        tier      = "**PREMIUM**" if storage.is_premium(user_id) else "**TAMU**"
        
        await msg_ui.edit_text(
            "┌─〔 ◈ **TRANSMISI SUKSES** ◈ 〕─┐\n"
            "│\n"
            f"├─ ⊛ **Gateway** : `{target_rcv}`\n"
            f"├─ ⊛ **Target** : `{nomor}`\n"
            f"├─ ⊛ **Modul** : `[#0x{tmpl_idx + 1}] {lang_label}`\n"
            f"├─ ⊛ **Daya** : `{count}/{max_daily}` ❲{tier}❳\n"
            "│\n"
            "└─〔 **Sesi Selesai Ditutup** 〕─┘",
            reply_markup=InlineKeyboardMarkup(_BTN_HOME),
            parse_mode="Markdown"
        )
    except Exception as e:
        await msg_ui.edit_text(
            f"┌─〔 ⊗ **TRANSMISI GAGAL** 〕─┐\n│\n├─ ◈ **Error** : `{e}`\n│\n└─〔 **Eksekusi Dibatalkan** 〕─┘",
            reply_markup=InlineKeyboardMarkup(_BTN_HOME),
            parse_mode="Markdown"
        )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "┌─〔 ⊗ **TRANSMISI BATAL** 〕─┐\n│\n└─〔 **Sistem Diberhentikan** 〕─┘", 
        reply_markup=InlineKeyboardMarkup(_BTN_HOME), 
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    from main import render_home
    await render_home(update, context)
    return ConversationHandler.END
