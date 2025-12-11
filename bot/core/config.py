import os
from dotenv import load_dotenv

load_dotenv()

TOKEN=os.getenv('TOKEN')
DATABASE_URL=os.getenv('DATABASE_URL')

if not TOKEN:
    raise ValueError('TOKEN не найден')
if not DATABASE_URL:
    raise ValueError('База данных не найдена')


