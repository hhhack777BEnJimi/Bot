import google.generativeai as genai
import PIL.Image
import os
import sqlite3
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# --- ТВОИ ДАННЫЕ (ВСТАВЛЕНЫ) ---
API_KEY = "AIzaSyA-W41rqsINwz5hwrEU-I1LN_MHWtdUqbI" # ЗАМЕНИ НА НОВЫЙ ПОСЛЕ REVOKE!
TELEGRAM_TOKEN = "8285487433:AAHYPgB_wsoRtoDpM1GwdyNPoAZG6Fj05Ug" # ЗАМЕНИ НА НОВЫЙ ПОСЛЕ REVOKE!
SECRET_PASSWORD = "Venerabako1986" 

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro')

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ---
def init_db():
    conn = sqlite3.connect('trading_intelligence.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS allowed_users (user_id INTEGER PRIMARY KEY)')
    conn.commit()
    conn.close()

init_db()

class TradingState(StatesGroup):
    auth = State()
    pair = State()
    tf = State()
    photo = State()

def is_allowed(user_id):
    conn = sqlite3.connect('trading_intelligence.db')
    user = conn.cursor().execute("SELECT user_id FROM allowed_users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return user is not None

# --- КОМАНДЫ ---
@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message):
    if is_allowed(message.from_user.id):
        await message.answer("🏦 **ТЕРМИНАЛ S010lvloon ГОТОВ.**\nКакую монету анализируем?")
        await TradingState.pair.set()
    else:
        await message.answer("🔒 Введите пароль доступа:")
        await TradingState.auth.set()

@dp.message_handler(state=TradingState.auth)
async def process_auth(message: types.Message, state: FSMContext):
    if message.text == SECRET_PASSWORD:
        conn = sqlite3.connect('trading_intelligence.db')
        conn.cursor().execute("INSERT OR IGNORE INTO allowed_users (user_id) VALUES (?)", (message.from_user.id,))
        conn.commit()
        conn.close()
        await message.answer("✅ Доступ открыт. Введите пару (напр. BTC/USDT):")
        await TradingState.pair.set()
    else:
        await message.answer("❌ Неверно.")

@dp.message_handler(state=TradingState.pair)
async def get_pair(message: types.Message, state: FSMContext):
    await state.update_data(pair=message.text.upper())
    await message.answer("Таймфрейм (1m, 5m, 1h, 1d):")
    await TradingState.tf.set()

@dp.message_handler(state=TradingState.tf)
async def get_tf(message: types.Message, state: FSMContext):
    await state.update_data(tf=message.text)
    await message.answer("📸 Пришли скриншот графика:")
    await TradingState.photo.set()

@dp.message_handler(content_types=['photo'], state=TradingState.photo)
async def process_analysis(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_name = f"chart_{message.from_user.id}.jpg"
    await message.photo[-1].download(destination_file=photo_name)
    img = PIL.Image.open(photo_name)

    await message.answer("📡 Вычисляю математические точки входа и выхода...")

    prompt = f"""
    Анализируй пару {data['pair']} на таймфрейме {data['tf']}.
    ОТВЕТЬ СТРОГО ПО ПУНКТАМ:
    1. 🟢 ТОЧКА ВХОДА: конкретная цена.
    2. 🔴 STOP LOSS: цена защиты.
    3. 🎯 TAKE PROFIT 1: первая цель.
    4. 🎯 TAKE PROFIT 2: вторая цель.
    5. 📊 ВЕРОЯТНОСТЬ: % успеха.
    6. 📰 НОВОСТИ: краткий фон.
    Пиши на русском.
    """

    try:
        response = model.generate_content([prompt, img])
        await message.answer(f"📊 **ТОРГОВЫЙ ПЛАН {data['pair']}:**\n\n{response.text}", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        os.remove(photo_name)
        await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
