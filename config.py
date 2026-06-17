import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

PREMIUM_PRICE = os.getenv("PREMIUM_PRICE", "Rp 50.000")
PAYMENT_INFO = os.getenv("PAYMENT_INFO", "Bank BCA - 123456789")

DOMAIN_LIST = [
    "walzhop.site",
    "alpha.walzhop.site",
    "beta.walzhop.site",
    "support.walzhop.site"
]

MAIL_SERVER = os.getenv("MAIL_SERVER", "mail.walzhop.site")
IMAP_PORT = int(os.getenv("IMAP_PORT", 993))
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

WEBHOOK_HOST = "0.0.0.0"
WEBHOOK_PORT = 8080
