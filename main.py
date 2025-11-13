import asyncio
import random
import sqlite3
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import F
from aiogram.client.default import DefaultBotProperties
import logging

# ---------------- CONFIG ----------------
TOKEN = "7836307093:AAHJA0Fd5P2aIkRxEZVduAfmUJHCT-jVXCQ"

# Если хочешь, укажи абсолютный путь, чтобы исключить проблему с разными CWD при systemd/container:
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "users.db")

# ---------------- INIT ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher(storage=MemoryStorage())

# ================= DB =================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        pair TEXT
    )
    """)
    conn.commit()
    conn.close()
    logging.info(f"DB initialized at {DB_FILE}")

def save_pair(user_id: int, pair: str):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO users (user_id, pair) VALUES (?, ?)", (user_id, pair))
    conn.commit()
    conn.close()
    logging.info(f"Saved pair for {user_id}: {pair}")

def save_user(user_id: int):
    """Добавляет пользователя в базу без пары (чтобы его можно было найти в get_all_users)."""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, pair) VALUES (?, NULL)", (user_id,))
    conn.commit()
    conn.close()
    logging.info(f"Ensured user exists in DB: {user_id}")

def get_pair(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT pair FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]

# ================= FSM =================
class Form(StatesGroup):
    waiting_for_id = State()
    waiting_for_type = State()
    waiting_for_pair = State()
    ready_for_signals = State()

# ================= DATA =================
otc_pairs = [
    "EUR/USD OTC", "USD/CHF OTC", "AUD/USD OTC", "Gold OTC",
    "AUD/CAD OTC", "AUD/CHF OTC", "AUD/JPY OTC", "AUD/NZD OTC",
    "CAD/CHF OTC", "CAD/JPY OTC", "CHF/JPY OTC"
]
real_pairs = [
    "EUR/USD", "AUD/USD", "Gold", "AUD/CAD", "AUD/JPY", "CAD/JPY"
]
index_pairs = [
    "Compound Index", "Asia Composite Index", "Crypto Composite Index"
]

all_pairs = otc_pairs + real_pairs + index_pairs

timeframes = ["10 minutos"] * 5 + ["20 minutos"] * 3 + ["30 minutos"] * 2 + ["50 minutos"]
budget_options = ["20$", "30$", "40$"]
directions = ["📈 Вверх", "📉 Вниз"]

user_cooldowns = {}

# ================= KEYBOARDS =================
def get_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕹 OTC Пары", callback_data="type_otc")],
        [InlineKeyboardButton(text="📈 Реальные пары", callback_data="type_real")],
        [InlineKeyboardButton(text="📊 Индексы", callback_data="type_index")]
    ])

def get_pairs_keyboard(pairs):
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=p, callback_data=f"pair:{p}")] for p in pairs] +
                        [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_types")]]
    )

# ================= HANDLERS =================
@dp.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    save_user(user_id)
    await message.answer("👋 Привет! Пожалуйста, пришли мне свой ID аккаунта (либо просто нажми любую кнопку ниже):")
    await state.set_state(Form.waiting_for_id)

@dp.message(Form.waiting_for_id)
async def process_id(message: Message, state: FSMContext):
    # Если пользователь отправил ID текстом — можно валидировать/сохранить, но мы уже сохранили user в БД
    await message.answer(
        "✅ Идентификатор принят (или подтверждён). Теперь выберите тип валютной пары:",
        reply_markup=get_type_keyboard()
    )
    await state.set_state(Form.waiting_for_type)

@dp.callback_query(F.data == "type_otc")
async def show_otc_pairs(callback: CallbackQuery, state: FSMContext):
    await callback.answer()  # ACK
    await callback.message.answer("Выберите валютную пару OTC:", reply_markup=get_pairs_keyboard(otc_pairs))
    await state.set_state(Form.waiting_for_pair)

@dp.callback_query(F.data == "type_real")
async def show_real_pairs(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Выберите реальную пару:", reply_markup=get_pairs_keyboard(real_pairs))
    await state.set_state(Form.waiting_for_pair)

@dp.callback_query(F.data == "type_index")
async def show_index_pairs(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Выберите индекс:", reply_markup=get_pairs_keyboard(index_pairs))
    await state.set_state(Form.waiting_for_pair)

@dp.callback_query(F.data == "back_to_types")
async def back_to_type_selection(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Выберите тип валютных пар:", reply_markup=get_type_keyboard())
    await state.set_state(Form.waiting_for_type)

@dp.callback_query(F.data.startswith("pair:"))
async def select_pair(callback: CallbackQuery, state: FSMContext):
    await callback.answer()  # ACK — убирает спиннер в Telegram
    pair = callback.data.split(":", 1)[1]
    uid = callback.from_user.id

    save_pair(uid, pair)
    logging.info(f"✅ User {uid} выбрал пару {pair}")

    btn = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📩 ПОЛУЧИТЬ СИГНАЛ", callback_data="get_signal")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_types")]
        ]
    )
    await callback.message.answer(f"Отличная пара: {pair}\nГотов к отправке сигнала. 👇", reply_markup=btn)
    await state.set_state(Form.ready_for_signals)


@dp.callback_query(F.data == "get_signal")
async def send_signal(callback: CallbackQuery, state: FSMContext):
    await callback.answer()  # ACK
    user_id = callback.from_user.id
    logging.info(f"👉 SIGNAL запрос от {user_id}")

    pair = get_pair(user_id)
    logging.info(f"🔍 Пара из базы для {user_id}: {pair}")

    if not pair:
        await callback.message.answer("⚠️ Сначала выберите пару валют!")
        return

    # cooldown check (используем UTC везде)
    now = datetime.utcnow()
    cooldown_until = user_cooldowns.get(user_id)
    if cooldown_until and (cooldown_until - now).total_seconds() > 0:
        remaining = int((cooldown_until - now).total_seconds())
        minutes = remaining // 60
        seconds = remaining % 60
        await callback.answer(f"⏳ Ожидайте {minutes} минут {seconds} секунд до следующего сигнала.", show_alert=True)
        return

    user_cooldowns[user_id] = now + timedelta(minutes=5)

    # UX: показываем "готовим" и убираем быстро
    msg = await callback.message.answer("⏳ Готовлю сигнал...")
    await asyncio.sleep(1.5)
    try:
        await msg.delete()
    except Exception:
        pass

    tf = random.choice(timeframes)
    budget = random.choice(budget_options)
    direction = random.choice(directions)

    signal_text = (
        f"Пара: *{pair}*\n"
        f"Время сделки: *{tf}*\n"
        f"Бюджет: *{budget}*\n"
        f"Направление: *{direction}*"
    )

    btn = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📩 ПОЛУЧИТЬ СИГНАЛ", callback_data="get_signal")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_types")]
        ]
    )
    await callback.message.answer(signal_text, reply_markup=btn)
    await state.set_state(Form.ready_for_signals)

# ================= AUTO SIGNALS =================
async def scheduled_signals():
    """
    Работает по локальному графику UTC+5:
     - с 19:00 до 04:00 → раз в 3 часа
     - с 04:00 до 10:00 → раз в 1 час
     - с 10:00 до 19:00 → пауза до 19:00
    Защищено от падений — логируем исключения и пытаемся снова.
    """
    while True:
        try:
            now_utc = datetime.utcnow()
            now_local = now_utc + timedelta(hours=5)
            hour = now_local.hour

            if 19 <= hour or hour < 4:
                interval_hours = 3
            elif 4 <= hour < 10:
                interval_hours = 1
            else:
                # пауза до 19:00 локального времени
                next_local = now_local.replace(hour=19, minute=0, second=0, microsecond=0)
                if next_local <= now_local:
                    next_local += timedelta(days=1)
                next_utc = next_local - timedelta(hours=5)
                sleep_seconds = (next_utc - datetime.utcnow()).total_seconds()
                logging.info(f"Auto signals paused until {next_local.isoformat()} (local). Sleeping {int(sleep_seconds)}s.")
                if sleep_seconds > 0:
                    await asyncio.sleep(sleep_seconds)
                continue

            # формируем сигнал
            pair = random.choice(all_pairs)
            tf = random.choice(timeframes)
            budget = random.choice(budget_options)
            direction = random.choice(directions)

            text = (
                f"Пара: *{pair}*\n"
                f"Время сделки: *{tf}*\n"
                f"Бюджет: *{budget}*\n"
                f"Направление: *{direction}*"
            )

            btn = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(
                    text="📩 ПОЛУЧИТЬ СИГНАЛ",
                    callback_data="get_signal"
                )]]
            )

            users = get_all_users()
            logging.info(f"Рассылаю сигнал {len(users)} пользователям. Пара: {pair}")

            for uid in users:
                try:
                    await bot.send_message(uid, text, reply_markup=btn)
                except Exception as e:
                    logging.warning(f"❌ Не удалось отправить {uid}: {e}")

            # считаем локальное время следующего события и конвертим в UTC для sleep
            next_local = (now_local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=interval_hours))
            next_utc = next_local - timedelta(hours=5)
            sleep_seconds = (next_utc - datetime.utcnow()).total_seconds()
            if sleep_seconds > 0:
                logging.info(f"Next auto signal at (local) {next_local.isoformat()} — sleeping {int(sleep_seconds)}s.")
                await asyncio.sleep(sleep_seconds)
            else:
                # защитная заглушка
                await asyncio.sleep(1)
        except Exception as exc:
            logging.exception(f"Ошибка в scheduled_signals: {exc}")
            await asyncio.sleep(10)

# ================= MAIN =================
async def main():
    init_db()
    # стартуем таску рассылки
    asyncio.create_task(scheduled_signals())
    logging.info("Starting polling...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Shutting down bot...")
