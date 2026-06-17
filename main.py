import warnings
import nest_asyncio
import asyncio
import json
import psutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler,
)
from telegram.request import HTTPXRequest
from telegram.error import BadRequest
from telegram.warnings import PTBUserWarning
from config import TELEGRAM_TOKEN, ADMIN_ID, PREMIUM_PRICE, PAYMENT_INFO, WEBHOOK_HOST, WEBHOOK_PORT
from modules import automator, sender, receiver, storage

warnings.filterwarnings("ignore", category=PTBUserWarning)
nest_asyncio.apply()

LANG_LABELS = ["𝗜𝗗𝗡 𝗣𝗥𝗢𝗫𝗬", "𝗕𝗥𝗭 𝗣𝗥𝗢𝗫𝗬", "𝗘𝗡𝗚 𝗣𝗥𝗢𝗫𝗬"]
global_app = None

async def cleanup_loop(app: Application):
    while True:
        try:
            expired_accounts = storage.get_expired_or_used_accounts()
            for uid, email in expired_accounts:
                email_user, email_domain = email.split("@")
                command = [
                    "cyberpanel", "deleteEmail",
                    "--domainName", email_domain,
                    "--userName", email_user,
                ]
                proc = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
                storage.delete_email(uid)
        except Exception:
            pass
        await asyncio.sleep(21600)

async def handle_payment_webhook(reader, writer):
    data = await reader.read(4096)
    request = data.decode(errors="ignore")
    try:
        if "POST" in request:
            parts = request.split("\r\n\r\n")
            if len(parts) > 1:
                body = parts[1]
                payload = json.loads(body)
                if payload.get("status") == "success":
                    target_user = int(payload.get("user_id"))
                    storage.set_premium(target_user, True)
                    if global_app:
                        await global_app.bot.send_message(
                            chat_id=target_user,
                            text=(
                                "┌─〔 ⟁ 𝗛𝗔𝗞 𝗔𝗞𝗦𝗘𝗦 𝗗𝗜𝗕𝗘𝗥𝗜𝗞𝗔𝗡 〕─┐\n"
                                "│\n"
                                "├─ ◈ 𝗦𝘁𝗮𝘁𝘂𝘀   : `PREMIUM AKTIF`\n"
                                "│\n"
                                "└─〔 𝗦𝗲𝗹𝗮𝗺𝗮𝘁 𝗠𝗲𝗻𝗶𝗸𝗺𝗮𝘁𝗶 𝗙𝗶𝘁𝘂𝗿 𝗣𝗥𝗢 〕─┘"
                            ),
                            parse_mode="Markdown"
                        )
    except Exception:
        pass

    response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"status\":\"ok\"}"
    writer.write(response.encode())
    await writer.drain()
    writer.close()

async def start_webhook_server():
    try:
        server = await asyncio.start_server(handle_payment_webhook, WEBHOOK_HOST, WEBHOOK_PORT)
        async with server:
            await server.serve_forever()
    except Exception:
        pass

async def post_init(app: Application):
    global global_app
    global_app = app
    asyncio.create_task(cleanup_loop(app))
    asyncio.create_task(start_webhook_server())

async def render_home(update: Update, context):
    user_id    = update.effective_user.id
    first_name = update.effective_user.first_name or "N/A"
    stored     = storage.get_email(user_id)
    count      = storage.get_send_count(user_id)
    premium    = storage.is_premium(user_id)
    max_daily  = storage.get_max_daily(user_id)
    tier_badge = "𝗔𝗞𝗦𝗘𝗦 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 ⟁" if premium else "𝗔𝗞𝗦𝗘𝗦 𝗙𝗥𝗘𝗘 ⊛"

    if stored:
        tmpl_idx        = storage.get_template_index(user_id)
        lang_label      = LANG_LABELS[tmpl_idx]
        bar_filled      = round((count / max_daily) * 10) if max_daily > 0 else 0
        bar             = "▰" * bar_filled + "▱" * (10 - bar_filled)
        username_sensor = stored['email'].split('@')[0]

        status_line = (
            f"├─ ◈ 𝗣𝗲𝗻𝗴𝗴𝘂𝗻𝗮  : `{first_name}`\n"
            f"├─ ◈ 𝗟𝗶𝘀𝗲𝗻𝘀𝗶   : {tier_badge}\n"
            "├────────────────────────\n"
            f"├─ ⊛ 𝗝𝗮𝗹𝘂𝗿     : `{username_sensor}@xxxxxxxxx`\n"
            f"├─ ⊛ 𝗠𝗼𝗱𝘂𝗹     : `[#0x{tmpl_idx + 1}]` {lang_label}\n"
            f"├─ ⊛ 𝗗𝗮𝘆𝗮      : `[{bar}] {count}/{max_daily}`"
        )
        rows = [
            [InlineKeyboardButton("⚡ 𝗞𝗜𝗥𝗜𝗠 𝗣𝗘𝗦𝗔𝗡", callback_data="send_email")],
            [
                InlineKeyboardButton("🐊 𝗖𝗘𝗞 𝗜𝗡𝗕𝗢𝗫", callback_data="check_inbox"),
                InlineKeyboardButton("⚙️ 𝗦𝗧𝗔𝗧𝗨𝗦", callback_data="status"),
            ],
            [InlineKeyboardButton("🔄 𝗛𝗔𝗣𝗨𝗦 & 𝗕𝗨𝗔𝗧 𝗕𝗔𝗥𝗨", callback_data="auto_destroy")],
        ]
        if not premium:
            rows.append([InlineKeyboardButton("⟁ 𝗠𝗜𝗡𝗧𝗔 𝗔𝗞𝗦𝗘𝗦 𝗣𝗥𝗘𝗠𝗜𝗨𝗠", callback_data="premium_info")])
    else:
        status_line = (
            f"├─ ◈ 𝗣𝗲𝗻𝗴𝗴𝘂𝗻𝗮  : `{first_name}`\n"
            f"├─ ◈ 𝗟𝗶𝘀𝗲𝗻𝘀𝗶   : {tier_badge}\n"
            "├────────────────────────\n"
            "├─ ⊗ 𝗦𝘁𝗮𝘁𝘂𝘀    : `JALUR TERPUTUS`\n"
            "│\n"
            "├─ ⊛ 𝗧𝗲𝗸𝗮𝗻 𝘁𝗼𝗺𝗯𝗼𝗹 𝗱𝗶 𝗯𝗮𝘄𝗮𝗵\n"
            "├─ ⊛ 𝘂𝗻𝘁𝘂𝗸 𝗺𝗲𝗺𝗯𝘂𝗮𝘁 𝗷𝗮𝗹𝘂𝗿 𝗻𝗼𝗱𝗲."
        )
        rows = [
            [InlineKeyboardButton("⚡ 𝗖𝗥𝗘𝗔𝗧𝗘 𝗚𝗠𝗔𝗜𝗟", callback_data="auto_create")],
            [InlineKeyboardButton("⚙️ 𝗦𝗧𝗔𝗧𝗨𝗦 𝗦𝗜𝗦𝗧𝗘𝗠", callback_data="status")],
        ]
        if not premium:
            rows.insert(1, [InlineKeyboardButton("⟁ 𝗠𝗜𝗡𝗧𝗔 𝗔𝗞𝗦𝗘𝗦 𝗣𝗥𝗘𝗠𝗜𝗨𝗠", callback_data="premium_info")])

    if user_id == ADMIN_ID:
        rows.append([InlineKeyboardButton("😈 𝗗𝗔𝗦𝗛𝗕𝗢𝗔𝗥𝗗 𝗖𝗢𝗡𝗧𝗥𝗢𝗟", callback_data="admin_dashboard")])

    text = (
        "┌─〔 ⎔ 𝗪𝗔𝗟𝗭𝗬 𝗡𝗢 𝗖𝗢𝗨𝗡𝗧𝗘𝗥 ⎔ 〕─┐\n"
        "│\n"
        f"{status_line}\n"
        "│\n"
        "└─〔 𝗦𝗶𝘀𝘁𝗲𝗺 𝗔𝗸𝘁𝗶𝗳 〕─┘"
    )
    reply_markup = InlineKeyboardMarkup(rows)

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def home(update: Update, context):
    await render_home(update, context)

async def admin_broadcast(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text(
            "┌─〔 📢 𝗕𝗥𝗢𝗔𝗗𝗖𝗔𝗦𝗧 〕─┐\n"
            "│\n"
            "├─ ⊗ 𝗦𝗶𝗻𝘁𝗮𝗸𝘀 : `/broadcast <pesan>`\n"
            "│\n"
            "└──────────────────┘",
            parse_mode="Markdown"
        )
        return

    broadcast_msg = " ".join(context.args)
    all_users = storage.get_all_users()
    s = 0
    f = 0
    for uid in all_users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=broadcast_msg, parse_mode="Markdown")
            s += 1
        except Exception:
            f += 1

    await update.message.reply_text(
        "┌─〔 📢 𝗦𝗜𝗔𝗥𝗔𝗡 𝗠𝗔𝗦𝗦𝗔𝗟 〕─┐\n"
        "│\n"
        f"├─ ◈ 𝗦𝘂𝗸𝘀𝗲𝘀  : `{s}`\n"
        f"├─ ◈ 𝗚𝗮𝗴𝗮𝗹   : `{f}`\n"
        "│\n"
        "└──────────────────┘",
        parse_mode="Markdown"
    )

async def show_admin_dashboard(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return

    metrics = storage.get_global_metrics()
    text = (
        "┌─〔 📊 𝗧𝗘𝗟𝗘𝗠𝗘𝗧𝗥𝗜 𝗗𝗔𝗦𝗛𝗕𝗢𝗔𝗥𝗗 〕─┐\n"
        "│\n"
        "├─ ◈ 𝗦𝗧𝗔𝗧𝗜𝗦𝗧𝗜𝗞 𝗚𝗟𝗢𝗕𝗔𝗟 :\n"
        f"│  ├─ 𝗧𝗼𝘁𝗮𝗹 𝗨𝘀𝗲𝗿  : `{metrics['total_users']}`\n"
        f"│  ├─ 𝗨𝘀𝗲𝗿 𝗣𝗿𝗼    : `{metrics['premium_users']}`\n"
        f"│  └─ 𝗨𝘀𝗲𝗿 𝗧𝗮𝗺𝘂   : `{metrics['guest_users']}`\n"
        "├────────────────────────\n"
        "├─ ◈ 𝗦𝗘𝗥𝗩𝗘𝗥 𝗩𝗣𝗦 :\n"
        f"│  ├─ 𝗕𝗲𝗯𝗮𝗻 𝗖𝗣𝗨   : `{psutil.cpu_percent()}%`\n"
        f"│  └─ 𝗠𝗲𝗺𝗼𝗿𝗶 𝗥𝗔𝗠  : `{psutil.virtual_memory().percent}%`\n"
        "│\n"
        "└─〔 𝗦𝗶𝗻𝘆𝗮𝗹 𝗢𝗽𝗲𝗿𝗮𝘀𝗶𝗼𝗻𝗮𝗹 𝗔𝗺𝗮𝗻 〕─┘"
    )
    keyboard = [[InlineKeyboardButton("⎔ 𝗞𝗘𝗠𝗕𝗔𝗟𝗜", callback_data="home")]]

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )

async def button_router(update: Update, context):
    query = update.callback_query
    await query.answer()

    back_btn = [[InlineKeyboardButton("⎔ 𝗞𝗘𝗠𝗕𝗔𝗟𝗜", callback_data="home")]]

    if query.data == "home":
        await render_home(update, context)
    elif query.data == "auto_create":
        await automator.auto_create_route(update, context)
    elif query.data == "auto_destroy":
        await automator.auto_destroy_route(update, context)
    elif query.data == "confirm_destroy":
        await automator.confirm_destroy(update, context)
    elif query.data == "check_inbox":
        await receiver.execute_check(update, context)
    elif query.data == "admin_dashboard":
        await show_admin_dashboard(update, context)
    elif query.data == "status":
        await query.edit_message_text(
            "┌─〔 ⚙️ 𝗦𝗧𝗔𝗧𝗨𝗦 𝗞𝗜𝗡𝗘𝗥𝗝𝗔 〕─┐\n"
            "│\n"
            "├─ ◈ 𝗨𝗽𝘁𝗶𝗺𝗲    : `Stable`\n"
            "├─ ◈ 𝗣𝗿𝗼𝘁𝗼𝗸𝗼𝗹  : `Direct SMTP`\n"
            "├─ ◈ 𝗔𝘂𝘁𝗼𝗖𝗹𝗲𝗮𝗻 : `Aktif`\n"
            "│\n"
            "└─〔 𝗦𝗶𝘀𝘁𝗲𝗺 𝗡𝗼𝗿𝗺𝗮𝗹 〕─┘",
            reply_markup=InlineKeyboardMarkup(back_btn),
            parse_mode="Markdown"
        )
    elif query.data == "premium_info":
        await query.edit_message_text(
            "┌─〔 ⟁ 𝗛𝗔𝗞 𝗔𝗞𝗦𝗘𝗦 𝗣𝗥𝗢 〕─┐\n"
            "│\n"
            f"├─ ◈ 𝗞𝘂𝗼𝘁𝗮     : `{storage.PREMIUM_DAILY} Req / Siklus`\n"
            "├─ ◈ 𝗙𝗶𝘁𝘂𝗿     : `Multi-Node Pooling`\n"
            "├─ ◈ 𝗣𝗿𝗶𝗼𝗿𝗶𝘁𝗮𝘀 : `Bypass Antrean`\n"
            "│\n"
            "└─〔 𝗦𝗶𝗹𝗮𝗸𝗮𝗻 𝗛𝘂𝗯𝘂𝗻𝗴𝗶 𝗔𝗱𝗺𝗶𝗻 〕─┘",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("💳 𝗕𝗘𝗟𝗜", callback_data="premium_buy"),
                    InlineKeyboardButton("⎔ 𝗞𝗘𝗠𝗕𝗔𝗟𝗜", callback_data="home"),
                ]
            ]),
            parse_mode="Markdown"
        )
    elif query.data == "premium_buy":
        await query.edit_message_text(
            "┌─〔 💳 𝗟𝗢𝗞𝗘𝗧 𝗧𝗥𝗔𝗡𝗦𝗔𝗞𝗦𝗜 〕─┐\n"
            "│\n"
            f"├─ ◈ 𝗜𝗻𝗳𝗼 : `{PAYMENT_INFO}`\n"
            "│\n"
            "└─〔 𝗞𝗶𝗿𝗶𝗺 𝗕𝘂𝗸𝘁𝗶 𝗣𝗲𝗺𝗯𝗮𝘆𝗮𝗿𝗮𝗻 〕─┘",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ 𝗦𝗨𝗗𝗔𝗛 𝗧𝗘𝗥𝗞𝗜𝗥𝗜𝗠", callback_data="premium_confirm_payment")],
                [InlineKeyboardButton("⎔ 𝗞𝗘𝗠𝗕𝗔𝗟𝗜", callback_data="premium_info")],
            ]),
            parse_mode="Markdown"
        )
    elif query.data == "premium_confirm_payment":
        await query.edit_message_text(
            "┌─〔 ⏳ 𝗣𝗥𝗢𝗦𝗘𝗦 𝗩𝗘𝗥𝗜𝗙𝗜𝗞𝗔𝗦𝗜 〕─┐\n"
            "│\n"
            "├─ ◈ 𝗦𝘁𝗮𝘁𝘂𝘀 : `Menunggu Validasi...`\n"
            "├─ ◈ 𝗜𝗻𝗳𝗼   : `Admin akan segera memproses.`\n"
            "│\n"
            "└─〔 𝗠𝗼𝗵𝗼𝗻 𝗧𝘂𝗻𝗴𝗴𝘂 〕─┘",
            reply_markup=InlineKeyboardMarkup(back_btn),
            parse_mode="Markdown"
        )

async def grant_premium(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text(
            "┌─〔 ⚠️ 𝗣𝗘𝗥𝗜𝗡𝗧𝗔𝗛 𝗦𝗔𝗟𝗔𝗛 〕─┐\n"
            "│\n"
            "├─ ◈ 𝗦𝗶𝗻𝘁𝗮𝗸𝘀 : `/grant <uid>`\n"
            "│\n"
            "└──────────────────┘",
            parse_mode="Markdown"
        )
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "┌─〔 ⊗ 𝗘𝗥𝗥𝗢𝗥 〕─┐\n"
            "│\n"
            "├─ ◈ 𝗣𝗲𝘀𝗮𝗻 : `UID tidak valid`\n"
            "│\n"
            "└──────────────────┘",
            parse_mode="Markdown"
        )
        return

    storage.set_premium(target_id, True)
    await update.message.reply_text(
        "┌─〔 ◈ 𝗔𝗞𝗦𝗘𝗦 𝗗𝗜𝗕𝗘𝗥𝗜𝗞𝗔𝗡 〕─┐\n"
        "│\n"
        f"├─ ◈ 𝗨𝗜𝗗    : `{target_id}`\n"
        "├─ ◈ 𝗦𝘁𝗮𝘁𝘂𝘀 : `FREE → PREMIUM`\n"
        "│\n"
        "└──────────────────┘",
        parse_mode="Markdown"
    )
    try:
        await context.bot.send_message(
            target_id,
            "┌─〔 ⟁ 𝗛𝗔𝗞 𝗔𝗞𝗦𝗘𝗦 𝗗𝗜𝗕𝗘𝗥𝗜𝗞𝗔𝗡 〕─┐\n"
            "│\n"
            "├─ ◈ 𝗦𝘁𝗮𝘁𝘂𝘀 : `Persetujuan Dikonfirmasi`\n"
            "├─ ◈ 𝗜𝗻𝗳𝗼   : `Ketik /start untuk muat ulang`\n"
            "│\n"
            "└─〔 𝗦𝗲𝗹𝗮𝗺𝗮𝘁 𝗗𝗮𝘁𝗮𝗻𝗴, 𝗣𝗿𝗲𝗺𝗶𝘂𝗺 〕─┘",
            parse_mode="Markdown"
        )
    except Exception:
        pass

async def revoke_premium(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        return
    try:
        target_id = int(context.args[0])
        storage.set_premium(target_id, False)
        await update.message.reply_text(
            "┌─〔 ⊗ 𝗔𝗞𝗦𝗘𝗦 𝗗𝗜𝗖𝗔𝗕𝗨𝗧 〕─┐\n"
            "│\n"
            f"├─ ◈ 𝗨𝗜𝗗    : `{target_id}`\n"
            "├─ ◈ 𝗦𝘁𝗮𝘁𝘂𝘀 : `PREMIUM → TAMU`\n"
            "│\n"
            "└──────────────────┘",
            parse_mode="Markdown"
        )
    except ValueError:
        pass

async def error_handler(update: object, context):
    try:
        if not isinstance(context.error, BadRequest) or "Message is not modified" not in str(context.error):
            print(f"[ ⊗ ] System Error: {context.error}")
    except Exception:
        pass

def main():
    req = HTTPXRequest(
        connection_pool_size=50,
        read_timeout=60.0,
        write_timeout=60.0,
        connect_timeout=60.0,
        pool_timeout=60.0
    )
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .request(req)
        .get_updates_request(req)
        .post_init(post_init)
        .build()
    )

    send_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(sender.start_send, pattern="^send_email$")],
        states={
            sender.ASK_NOMOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, sender.process_send)]
        },
        fallbacks=[
            CommandHandler("cancel", sender.cancel),
            CallbackQueryHandler(sender.cancel_callback, pattern="^home$")
        ]
    )

    app.add_handler(CommandHandler("start", home))
    app.add_handler(CommandHandler("grant", grant_premium))
    app.add_handler(CommandHandler("revoke", revoke_premium))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("dashboard", show_admin_dashboard))
    app.add_handler(send_conv)
    app.add_handler(
        CallbackQueryHandler(
            button_router,
            pattern="^(home|auto_create|auto_destroy|confirm_destroy|check_inbox|status|premium_info|premium_buy|premium_confirm_payment|admin_dashboard)$"
        )
    )
    app.add_error_handler(error_handler)
    print("[ ◈ ] 𝗦𝗶𝘀𝘁𝗲𝗺 𝗪𝗮𝗹𝘇𝘆 𝗠𝗲𝗺𝘂𝗹𝗮𝗶...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
