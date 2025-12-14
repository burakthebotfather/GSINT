import os
import asyncio
import json
import base64
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message

import gspread
from google.oauth2.service_account import Credentials

# ================== ENV ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")
SERVICE_JSON_B64 = os.getenv("SERVICE_JSON_B64")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")

if not SPREADSHEET_NAME:
    raise RuntimeError("SPREADSHEET_NAME не задан")

if not SERVICE_JSON_B64:
    raise RuntimeError("SERVICE_JSON_B64 не задан")

# ================== GOOGLE CREDS ==================

try:
    raw_json = base64.b64decode(SERVICE_JSON_B64).decode("utf-8")
    service_info = json.loads(raw_json)
except Exception as e:
    raise RuntimeError(f"Ошибка чтения SERVICE_JSON_B64: {e}")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    service_info,
    scopes=SCOPES
)

gc = gspread.authorize(creds)
sh = gc.open(SPREADSHEET_NAME)
worksheet = sh.sheet1

# ================== BOT CONFIG ==================

DEFAULT_TARGET_CHAT = -1002360529455
DEFAULT_TARGET_THREAD = 3

ORG_MAP = {
    (DEFAULT_TARGET_CHAT, DEFAULT_TARGET_THREAD): "333."
}

TZ = ZoneInfo("Europe/Minsk")

# ================== SHEET HEADER ==================

HEADER = [
    "время отметки",
    "дата отметки",
    "ID водителя",
    "организация",
    "наличные",
    "+",
    "+ мк",
    "+ мк синяя",
    "+ мк красная",
    "+ мк оранжевая",
    "+ мк салатовая",
    "+ мк коричневая",
    "+ мк светло-серая",
    "+ мк розовая",
    "+ мк темно-серая",
    "+ мк голубая",
    "габ"
]

TRIGGER_COLUMNS = HEADER[5:]

TRIGGERS = {
    "мк синяя": "+ мк синяя",
    "мк красная": "+ мк красная",
    "мк оранжевая": "+ мк оранжевая",
    "мк салатовая": "+ мк салатовая",
    "мк коричневая": "+ мк коричневая",
    "мк светло-серая": "+ мк светло-серая",
    "мк розовая": "+ мк розовая",
    "мк темно-серая": "+ мк темно-серая",
    "мк голубая": "+ мк голубая",
    "мк": "+ мк",
    "габ": "габ"
}

# ================== UTILS ==================

def extract_first_number(text: str) -> int:
    import re
    m = re.search(r"\b(\d+)\b", text)
    return int(m.group(1)) if m else 0


def build_trigger_vector(text: str) -> dict:
    t = text.lower()
    vec = {col: 0 for col in TRIGGER_COLUMNS}

    for key, col in TRIGGERS.items():
        if key in t and col in vec:
            vec[col] = 1

    vec["+"] = 1
    return vec


# ================== BOT ==================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(
    F.chat.id == DEFAULT_TARGET_CHAT,
    F.message_thread_id == DEFAULT_TARGET_THREAD
)
async def handle_message(message: Message):
    text = (message.text or "").lower()
    if "+" not in text:
        return

    cash = extract_first_number(text)
    triggers = build_trigger_vector(text)

    now = datetime.now(tz=TZ)

    row = [
        now.strftime("%H:%M:%S"),
        now.strftime("%Y-%m-%d"),
        str(message.from_user.id),
        ORG_MAP.get((message.chat.id, message.message_thread_id), ""),
        str(cash),
    ] + [str(triggers[col]) for col in TRIGGER_COLUMNS]

    try:
        worksheet.append_row(row, value_input_option="USER_ENTERED")
        await message.reply("Отметка принята ✅")
    except Exception as e:
        print("Ошибка записи в Google Sheets:", e)

# ================== START ==================

if __name__ == "__main__":
    print("Bot started")
    asyncio.run(dp.start_polling(bot))
