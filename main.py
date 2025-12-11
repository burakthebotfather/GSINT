# main.py
import os
import re
import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# -------------------------
# Config / Environment
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "ВАША_ТАБЛИЦА")
SERVICE_JSON_STR = os.getenv("SERVICE_JSON")  # теперь ожидаем JSON как строку

# По умолчанию — та пара, что ты указывал:
DEFAULT_TARGET_CHAT = -1002360529455
DEFAULT_TARGET_THREAD = 3
# Организация для этой пары:
ORG_MAP = {
    (DEFAULT_TARGET_CHAT, DEFAULT_TARGET_THREAD): "333."
}

# Временная зона — Asia/Singapore
TZ = ZoneInfo("Asia/Singapore")

# -------------------------
# Проверки окружения
# -------------------------
if not BOT_TOKEN:
    raise RuntimeError("Установи BOT_TOKEN в переменных окружения")

if not SERVICE_JSON_STR:
    raise RuntimeError("SERVICE_JSON не задана в переменных окружения")

# -------------------------
# Google Sheets init
# -------------------------
try:
    service_info = json.loads(SERVICE_JSON_STR)
except json.JSONDecodeError as e:
    raise RuntimeError(f"Ошибка чтения SERVICE_JSON: {e}")

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_info, scope)
gc = gspread.authorize(creds)
sh = gc.open(SPREADSHEET_NAME)
worksheet = sh.sheet1  # используем первый лист

# -------------------------
# Заголовки (как в задаче)
# -------------------------
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

# Если заголовок отсутствует — создаём
try:
    current_header = worksheet.row_values(1)
    if not current_header or [c.strip() for c in current_header] != HEADER:
        worksheet.delete_rows(1) if current_header else None
        worksheet.insert_row(HEADER, index=1)
except Exception as e:
    print("Warning: не удалось проверить/установить заголовок в таблице:", e)

# -------------------------
# Логика триггеров
# -------------------------
TRIGGERS_PHRASES = {
    "+": "+",
    "мк": "+ мк",
    "мк синяя": "+ мк синяя",
    "мк красная": "+ мк красная",
    "мк оранжевая": "+ мк оранжевая",
    "мк салатовая": "+ мк салатовая",
    "мк коричневая": "+ мк коричневая",
    "мк светло-серая": "+ мк светло-серая",
    "мк розовая": "+ мк розовая",
    "мк темно-серая": "+ мк темно-серая",
    "мк голубая": "+ мк голубая",
    "габ": "габ"
}

TRIGGER_COLUMNS = HEADER[5:]

def parse_right_of_plus(text: str) -> str:
    if "+" not in text:
        return ""
    return text.split("+", 1)[1].strip()

def extract_first_number(s: str) -> int:
    m = re.search(r"\b(\d+)\b", s)
    return int(m.group(1)) if m else 0

def build_trigger_vector(right: str) -> dict:
    r = right.lower()
    vec = {col: 0 for col in TRIGGER_COLUMNS}
    for key in sorted(TRIGGERS_PHRASES.keys(), key=lambda x: -len(x)):
        col = TRIGGERS_PHRASES[key]
        if key == "+":
            continue
        if key in r:
            if col in vec:
                vec[col] = 1
    return vec

# -------------------------
# Telegram bot
# -------------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(F.chat.id == DEFAULT_TARGET_CHAT, F.message_thread_id == DEFAULT_TARGET_THREAD)
async def handle_driver_message(message: Message):
    text = (message.text or "").lower()
    if not text or "+" not in text:
        return

    right = parse_right_of_plus(text)
    cash = extract_first_number(right)
    trigger_vec = build_trigger_vector(right)

    if "+" in TRIGGER_COLUMNS:
        trigger_vec["+"] = 1

    org = ORG_MAP.get((message.chat.id, message.message_thread_id), "")

    now = datetime.now(tz=TZ)
    time_str = now.strftime("%H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")

    row = [
        time_str,
        date_str,
        str(message.from_user.id),
        org,
        str(cash),
    ] + [str(trigger_vec.get(col, 0)) for col in TRIGGER_COLUMNS]

    try:
        worksheet.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        print("Error appending row to Google Sheet:", e)

    try:
        await message.reply("Отметка принята ✅")
    except Exception:
        pass

# -------------------------
# Запуск
# -------------------------
if __name__ == "__main__":
    print("Starting bot...")
    try:
        asyncio.run(dp.start_polling(bot))
    except KeyboardInterrupt:
        print("Stopped by user")
