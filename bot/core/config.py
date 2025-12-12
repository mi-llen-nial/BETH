import os
from dotenv import load_dotenv

load_dotenv()

# Локально токен читается из TOKEN,
# в облаке (Sourcecraft / Yandex Functions) — из BOT_TOKEN.
TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Настройки вебхука (опционально, используются при деплое)
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # полный внешний URL вебхука
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.getenv("PORT", os.getenv("WEBAPP_PORT", "8080")))

if not TOKEN:
    raise ValueError("TOKEN/BOT_TOKEN не найден")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL (строка подключения к БД) не найдена")

