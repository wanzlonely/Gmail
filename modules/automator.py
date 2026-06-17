import asyncio
import random
import string
import imaplib
import ssl
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import DOMAIN_LIST, MAIL_SERVER, IMAP_PORT
from modules import storage

_BTN_HOME = [[InlineKeyboardButton("⎔ **KEMBALI KE MENU** ⎔", callback_data="home")]]

def _generate_credentials(user_id: int) -> tuple[str, str]:
    uid_str = str(user_id)[-4:]
    rand_hex = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    username = f"u{uid_str}{rand_hex}"
    chars = string.ascii_letters + string.digits
    rand_pass = ''.join(random.choices(chars, k=10))
    password = f"Nx26@{rand_pass}!"
    return username, password

def _verify_imap_sync(email: str, password: str) -> bool:
    mail = None
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        mail = imaplib.IMAP4_SSL(MAIL_SERVER, IMAP_PORT, ssl_context=ctx)
        mail.login(email, password)
        mail.logout()
        return True
    except Exception:
        if mail:
            try: 
                mail.logout()
            except Exception: 
                pass
        return False

async def auto_create_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if storage.has_email(user_id):
        await query.edit_message_text(
            "┌─〔 ⊗ **AKSES DITOLAK** 〕─┐\n│\n├─ ◈ **Status** : `Jalur Sudah Aktif`\n├─ ◈ `Hancurkan jalur lama`\n├─ ◈ `untuk membuat jalur baru.`\n│\n└─〔 **Sesi Pembatalan** 〕─┘",
            reply_markup=InlineKeyboardMarkup(_BTN_HOME),
            parse_mode="Markdown"
        )
        return

    msg_ui = await query.edit_message_text(
        "┌─〔 ⟁ **PROSES GENERATOR** 〕─┐\n│\n├─ ◈ **Status** : `Mengkalkulasi Node`\n│\n└─〔 **Mohon Tunggu** 〕─┘",
        parse_mode="Markdown"
    )

    target_domain = random.choice(DOMAIN_LIST)
    username, password = _generate_credentials(user_id)
    full_email = f"{username}@{target_domain}"

    command = [
        "cyberpanel", "createEmail",
        "--domainName", target_domain,
        "--userName", username,
        "--password", password,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        output_log = (stdout.decode() + "\n" + stderr.decode()).strip().lower()

        is_success = False
        if proc.returncode == 0:
            if not any(err in output_log for err in ["error", "fail", "already", "cannot", "invalid"]):
                is_success = True
        if "success" in output_log or "berhasil" in output_log:
            is_success = True

        if is_success:
            await msg_ui.edit_text(
                "┌─〔 ⟁ **PROSES GENERATOR** 〕─┐\n│\n├─ ◈ **Status** : `Sinkronisasi IMAP`\n│\n└─〔 **Mohon Tunggu** 〕─┘",
                parse_mode="Markdown"
            )
            
            verified = False
            for _ in range(3):
                await asyncio.sleep(2)
                verified = await asyncio.to_thread(_verify_imap_sync, full_email, password)
                if verified: 
                    break
            
            if verified:
                storage.set_email(user_id, full_email, password)
                tmpl_idx = storage.assign_template(user_id)
                from modules.sender import LANG_LABELS
                lang_label = LANG_LABELS[tmpl_idx]
                
                await msg_ui.edit_text(
                    "┌─〔 ◈ **NODE BERHASIL AKTIF** ◈ 〕─┐\n"
                    "│\n"
                    f"├─ ⊛ **ID Node** : `{username}@xxxxxxxxx`\n" 
                    f"├─ ⊛ **Sandi** : `Disembunyikan`\n"
                    f"├─ ⊛ **Modul** : `[#0x{tmpl_idx + 1}] {lang_label}`\n"
                    "│\n"
                    "└─〔 **Sistem Siap Eksekusi** 〕─┘",
                    reply_markup=InlineKeyboardMarkup(_BTN_HOME),
                    parse_mode="Markdown"
                )
            else:
                await msg_ui.edit_text(
                    "┌─〔 ⊗ **NODE ERROR** 〕─┐\n│\n├─ ◈ **Kegagalan** : `Verifikasi IMAP`\n│\n└─〔 **Silakan Coba Lagi** 〕─┘",
                    reply_markup=InlineKeyboardMarkup(_BTN_HOME),
                    parse_mode="Markdown"
                )
        else:
            await msg_ui.edit_text(
                "┌─〔 ⊗ **NODE ERROR** 〕─┐\n│\n├─ ◈ **Kegagalan** : `Panel CyberPanel`\n│\n└─〔 **Silakan Coba Lagi** 〕─┘",
                reply_markup=InlineKeyboardMarkup(_BTN_HOME),
                parse_mode="Markdown"
            )
    except Exception:
        await msg_ui.edit_text(
            "┌─〔 ⊗ **KESALAHAN SYSTEM** 〕─┐\n│\n├─ ◈ **Kondisi** : `Fatal Hardware`\n│\n└─〔 **Sistem Dihentikan** 〕─┘",
            reply_markup=InlineKeyboardMarkup(_BTN_HOME),
            parse_mode="Markdown"
        )

async def auto_destroy_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ **YA, LANJUTKAN**", callback_data="confirm_destroy")],
        [InlineKeyboardButton("⎔ **BATAL**", callback_data="home")]
    ]
    
    await query.edit_message_text(
        "┌─〔 ⚠️ **KONFIRMASI JALUR** 〕─┐\n"
        "│\n"
        "├─ ◈ **Peringatan** : `Yakin Ingin Hapus?`\n"
        "├─ ◈ `Seluruh data pada node`\n"
        "├─ ◈ `akan dihapus permanen.`\n"
        "│\n"
        "└─〔 **Tindakan Irreversible** 〕─┘",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def confirm_destroy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    stored = storage.get_email(user_id)
    
    if not stored:
        from main import render_home
        await render_home(update, context)
        return

    email_user, email_domain = stored["email"].split("@")
    msg_ui = await query.edit_message_text(
        "┌─〔 ⟁ **PEMBERSIHAN NODE** 〕─┐\n│\n├─ ◈ **Status** : `Menghapus Jejak`\n│\n└─〔 **Mohon Tunggu** 〕─┘",
        parse_mode="Markdown",
    )

    command = [
        "cyberpanel", "deleteEmail",
        "--domainName", email_domain,
        "--userName", email_user,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        storage.delete_email(user_id)
        
        await msg_ui.edit_text(
            "┌─〔 ◈ **PROSES SELESAI** ◈ 〕─┐\n"
            "│\n"
            "├─ ⊛ **Status** : `Node Dimusnahkan`\n"
            "│\n"
            "└─〔 **Server Kembali Bersih** 〕─┘",
            reply_markup=InlineKeyboardMarkup(_BTN_HOME),
            parse_mode="Markdown",
        )
    except Exception:
        storage.delete_email(user_id)
        await msg_ui.edit_text(
            "┌─〔 ◈ **PROSES PAKSA** ◈ 〕─┐\n"
            "│\n"
            "├─ ◈ **Status** : `Database Dibersihkan`\n"
            "│\n"
            "└─〔 **Pembersihan Lokal** 〕─┘",
            reply_markup=InlineKeyboardMarkup(_BTN_HOME),
            parse_mode="Markdown",
        )
