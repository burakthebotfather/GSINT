import os
import re
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ParseMode

import gspread
from google.oauth2.service_account import Credentials

# ================== НАСТРОЙКИ ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")

TARGET_CHAT_ID = -1002360529455
TARGET_THREAD_ID = 3
ORGANIZATION = "333."

SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")  # имя таблицы
SHEET_NAME = os.getenv("SHEET_NAME", "Лист1")

# ================== GOOGLE SHEETS ==================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

creds = Credentials.from_service_account_info(
    {
        "type": "service_account",
        "project_id": os.getenv("GS_PROJECT_ID"),
        "private_key_id": os.getenv("GS_PRIVATE_KEY_ID"),
        "private_key": os.getenv("GS_PRIVATE_KEY").replace("\\n", "\n"),
        "client_email": os.getenv("GS_CLIENT_EMAIL"),
        "client_id": os.getenv("GS_CLIENT_ID"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": os.getenv("GS_CLIENT_CERT_URL"),
    },
    scopes=SCOPES,
)

gc = gspread.authorize(creds)
sh = gc.open(SPREADSHEET_NAME)
worksheet = sh.worksheet(SHEET_NAME)

# ================== ТРИГГЕРЫ ==================

COLUMNS = [
    '"+""',
    '"+ мк"',
    '"+ мк синяя"',
    '"+ мк красная"',
    '"+ мк оранжевая"',
    '"+ мк салатовая"',
    '"+ мк коричневая"',
    '"+ мк светло-серая"',
    '"+ мк розовая"',
    '"+ мк темно-серая"',
    '"+ мк голубая"',
    "габ",
]

MK_COLORS = [
    "синяя",
    "красная",
    "оранжевая",
    "салатовая",
    "коричневая",
    "светло-серая",
    "розовая",
    "темно-серая",
    "голубая",
]

# ================== ПАРСИНГ ==================

def parse_message(text: str):
    text = text.lower()

    if "+" not in text:
        return None

    right = text.split("+", 1)[1].strip()

    # Наличные
    cash = 0
    cash_match = re.search(r"\b\d+\b", right)
    if cash_match:
        cash = int(cash_match.group())

    flags = {col: 0 for col in COLUMNS}

    # "+" всегда если дошли сюда
    flags['"+"'] = 1

    if "мк" in right:
        flags['"+ мк"'] = 1

    for color in MK_COLORS:
        if f"мк {color}" in right:
            flags[f'"+ мк {color}"'] = 1

    if "габ" in right:
        flags["габ"] = 1

    return cash, flags

# ================== GOOGLE SHEETS ==================

def append_row(user_id: int, cash: int, flags: dict):
    now = datetime.now()

    row = [
        now.strftime("%H:%M:%S"),
        now.strftime("%d.%m.%Y"),
        user_id,
        ORGANIZATION,
        cash,
    ]

    for col in COLUMNS:
        row.append(flags[col])

    worksheet.append_row(row, value_input_option="USER_ENTERED")

# ================== BOT ==================

bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

@dp.message(F.text)
async def handle_message(message: Message):
    if message.chat.id != TARGET_CHAT_ID:
        return

    if message.message_thread_id != TARGET_THREAD_ID:
        return

    parsed = parse_message(message.text)
    if not parsed:
        return

    cash, flags = parsed

    append_row(
        user_id=message.from_user.id,
        cash=cash,
        flags=flags,
    )

# ================== START ==================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
