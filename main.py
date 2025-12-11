# main.py
import os
import re
import asyncio
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
SERVICE_JSON = os.getenv("SERVICE_JSON", "service.json")

# По умолчанию — та пара, что ты указывал:
DEFAULT_TARGET_CHAT = -1002360529455
DEFAULT_TARGET_THREAD = 3
# Организация для этой пары:
ORG_MAP = {
    (DEFAULT_TARGET_CHAT, DEFAULT_TARGET_THREAD): "333."
}

# Временная зона — Asia/Singapore (по твоему окружению)
TZ = ZoneInfo("Asia/Singapore")

# -------------------------
# Проверки окружения
# -------------------------
if not BOT_TOKEN:
    raise RuntimeError("Установи BOT_TOKEN в переменных окружения")

if not os.path.exists(SERVICE_JSON):
    raise RuntimeError(f"Файл сервисного аккаунта Google не найден: {SERVICE_JSON}")

# -------------------------
# Google Sheets init
# -------------------------
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_JSON, scope)
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
        # Запишем корректный заголовок (перезапишем первую строку)
        worksheet.delete_rows(1) if current_header else None
        worksheet.insert_row(HEADER, index=1)
except Exception as e:
    print("Warning: не удалось проверить/установить заголовок в таблице:", e)

# -------------------------
# Логика триггеров
# -------------------------
# Основные ключи поиска внутри правой части (после '+')
TRIGGERS_PHRASES = {
    "+": "+",  # специальная метка — ставим, если есть знак +
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

# Колонки триггеров в том порядке, как у тебя в шапке (без первых 5 общих колонок)
TRIGGER_COLUMNS = HEADER[5:]  # начиная с "+" до "габ"

# -------------------------
# Помощники
# -------------------------
def parse_right_of_plus(text: str) -> str:
    """
    Возвращает строчку, которая идёт справа от первого символа '+'.
    Если '+' нет — возвращает пустую строку.
    """
    if "+" not in text:
        return ""
    return text.split("+", 1)[1].strip()

def extract_first_number(s: str) -> int:
    """
    Ищет первое целое число в строке и возвращает его как int.
    Если ничего не найдено — возвращает 0.
    """
    m = re.search(r"\b(\d+)\b", s)
    return int(m.group(1)) if m else 0

def build_trigger_vector(right: str) -> dict:
    """
    По правой части возвращает словарь {column_name: 0/1}.
    Правила: ищем в правой части подстроки (точные слова/фразы),
    '+' — ставится в 1, если вообще был символ '+' (обрабатывается отдельно).
    """
    r = right.lower()
    vec = {col: 0 for col in TRIGGER_COLUMNS}

    # Если правой части пусто, но '+' был — в коде вызывающий поставит '+'=1 независя от right.
    # Здесь ищем все фразы.
    # Сначала проверим "мк синяя" и другие длинные совпадения (чтобы не "перекрывать" простое 'мк')
    # Проходим по TRIGGERS_PHRASES в порядке длинных -> коротких
    # Сортируем ключи по длине убыв.
    for key in sorted(TRIGGERS_PHRASES.keys(), key=lambda x: -len(x)):
        col = TRIGGERS_PHRASES[key]
        if key == "+":
            # плюс обрабатывается отдельно (вызов должен пометить '+')
            continue
        if key in r:
            if col in vec:
                vec[col] = 1

    return vec

# -------------------------
# Telegram bot (aiogram)
# -------------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(F.chat.id == DEFAULT_TARGET_CHAT, F.message_thread_id == DEFAULT_TARGET_THREAD)
async def handle_driver_message(message: Message):
    """
    Обработчик сообщений в нужном chat_id:thread_id.
    """
    text = (message.text or "").lower()
    if not text:
        return  # игнорируем нетекстовые сообщения

    # Если в сообщении нет символа '+' — по заданию не обрабатываем
    if "+" not in text:
        return

    right = parse_right_of_plus(text)  # правая часть
    cash = extract_first_number(right)
    trigger_vec = build_trigger_vector(right)

    # Поставим '+'=1, т.к. символ + в сообщении есть
    if "+" in TRIGGER_COLUMNS:
        trigger_vec["+"] = 1

    # Организация - читаем из ORG_MAP по (chat, thread)
    org = ORG_MAP.get((message.chat.id, message.message_thread_id), "")

    # Время и дата в Asia/Singapore
    now = datetime.now(tz=TZ)
    time_str = now.strftime("%H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")

    # Подготовка строки в том порядке, что HEADER задаёт
    row = [
        time_str,
        date_str,
        str(message.from_user.id),
        org,
        str(cash),
    ]

    # Добавляем значения триггеров по порядку TRIGGER_COLUMNS
    for col in TRIGGER_COLUMNS:
        row.append(str(trigger_vec.get(col, 0)))

    try:
        worksheet.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        # Логируем ошибку, но не падаем
        print("Error appending row to Google Sheet:", e)
        # Можно отправить уведомление админу или логировать в файл

    # Подтверждаем водителю
    try:
        await message.reply("Отметка принята ✅")
    except Exception:
        pass  # если reply не прошёл, молча продолжаем

# -------------------------
# Запуск
# -------------------------
if __name__ == "__main__":
    print("Starting bot...")
    try:
        asyncio.run(dp.start_polling(bot))
    except KeyboardInterrupt:
        print("Stopped by user")
