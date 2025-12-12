import random

import aiohttp

QUOTE_API_URL = "https://api.quotable.io/random"

FALLBACK_QUOTES = [
    "Даже самый маленький Бэт оставляет след в большом мире.",
    "Сила не в редкости, а в том, кто верит в тебя.",
    "Каждое ношение — это шанс изменить свою коллекцию.",
    "Проигрыш — всего лишь подготовка к легендарной победе.",
]


async def fetch_random_quote() -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(QUOTE_API_URL, timeout=5) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Bad status: {resp.status}")

                data = await resp.json()
                text = data.get("content")
                author = data.get("author")

                if not text:
                    raise RuntimeError("Empty quote")

                if author:
                    return f"{text} — {author}"
                return text
    except Exception:
        return random.choice(FALLBACK_QUOTES)
