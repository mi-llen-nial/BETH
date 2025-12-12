import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Настройки вебхука (опционально, используются при деплое)
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # полный внешний URL вебхука
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.getenv("PORT", os.getenv("WEBAPP_PORT", "8080")))

if not TOKEN:
    raise ValueError("TOKEN не найден")
if not DATABASE_URL:
    raise ValueError("База данных не найдена")


