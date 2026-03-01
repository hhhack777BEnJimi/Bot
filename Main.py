from google import genai
from google.genai import types
import os
import sqlite3
import logging
import PIL.Image
from aiogram import Bot, Dispatcher, types as tg_types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# --- 1. НАСТРОЙКИ ---
logging.basicConfig(level=logging.INFO)

API_KEY = "AIzaSyDxvNiFriZWjDhV5JzrFKMS2v9R_hMCdbY" 
TELEGRAM_TOKEN = "8285487433:AAHYPgB_wsoRtoDpM1GwdyNPoAZG6Fj05Ug"
SECRET_PASSWORD = "Venerabako1986"

# --- 2. ИНИЦИАЛИЗАЦИЯ БОТА ---
bot = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- 3. КЛИЕНТ И УМНЫЙ ПОДБОР МОДЕЛИ ---
client = genai.Client(api_key=API_KEY)

def get_best_available_model():
    print("🔍 Сканирую доступные модели Google...")
    try:
        # Получаем список всех моделей, которые видит твой API-ключ
        available_models = [m.name for m in client.models.list()]
        
        # Приоритетный список (от лучших к запасным)
        priority = [
            'gemini-2.0-flash', 
            'gemini-1.5-flash', 
            'gemini-1.5-flash-latest',
            'gemini-3-flash-preview'
        ]
        
        for target in priority:
            for actual in available_models:
                if target in actual:
                    print(f"✅ Выбрана оптимальная модель: {actual}")
                    return actual
        
        # Если ничего не нашли из списка, берем первую попавшуюся
        print(f"⚠️ Точных совпадений нет, беру: {available_models[0]}")
        return available_models[0]
    except Exception as e:
        print(f"❌ Ошибка при поиске моделей: {e}. Ставлю дефолт.")
        return 'gemini-1.5-flash'

# Активируем найденную модель
MODEL_NAME = get_best_available_model()

# --- 4. БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('trading_intelligence.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS allowed_users (user_id INTEGER PRIMARY KEY)')
    conn.commit()
    conn.close()

init_db()

def is_allowed(user_id):
    conn = sqlite3.connect('trading_intelligence.db')
    res = conn.cursor().execute("SELECT user_id FROM allowed_users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return res is not None

# --- 5. СОСТОЯНИЯ ---
class TradingState(StatesGroup):
    auth = State()
    pair = State()
    tf = State()
    photo = State()

# --- 6. ОБРАБОТЧИКИ ---

@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: tg_types.Message, state: FSMContext):
    await state.finish()
    if is_allowed(message.from_user.id):
        await message.answer(f"🏦 **ТЕРМИНАЛ S010lvloon v5.0**\nАктивная модель: `{MODEL_NAME}`\nВведите пару:")
        await TradingState.pair.set()
    else:
        await message.answer("🔒 Введите пароль доступа:")
        await TradingState.auth.set()

@dp.message_handler(state=TradingState.auth)
async def process_auth(message: tg_types.Message):
    if message.text == SECRET_PASSWORD:
        conn = sqlite3.connect('trading_intelligence.db')
        conn.cursor().execute("INSERT OR IGNORE INTO allowed_users (user_id) VALUES (?)", (message.from_user.id,))
        conn.commit()
        conn.close()
        await message.answer("✅ Доступ разрешен! Введите пару:")
        await TradingState.pair.set()
    else:
        await message.answer("❌ Пароль неверный.")

@dp.message_handler(state=TradingState.pair)
async def get_pair(message: tg_types.Message, state: FSMContext):
    await state.update_data(pair=message.text.upper())
    await message.answer("Таймфрейм?")
    await TradingState.tf.set()

@dp.message_handler(state=TradingState.tf)
async def get_tf(message: tg_types.Message, state: FSMContext):
    await state.update_data(tf=message.text)
    await message.answer("📸 Скидывай график:")
    await TradingState.photo.set()

@dp.message_handler(content_types=['photo'], state=TradingState.photo)
async def process_analysis(message: tg_types.Message, state: FSMContext):
    data = await state.get_data()
    photo_name = f"chart_{message.from_user.id}.jpg"
    await message.photo[-1].download(destination_file=photo_name)
    
    status_msg = await message.answer(f"📡 **АНАЛИЗ ЧЕРЕЗ {MODEL_NAME}...**")
    
    try:
        with open(photo_name, 'rb') as f:
            image_bytes = f.read()

        prompt = (
            f"Ты профессиональный трейдер. Проанализируй график {data['pair']} ({data['tf']}). "
            "Укажи уровни поддержки/сопротивления и дай: Вход, Стоп, Тейк. На русском."
        )

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                prompt
            ]
        )
        
        await status_msg.edit_text(f"📊 **ВЕРДИКТ:**\n\n{response.text}")

    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка API: {str(e)}")
    
    finally:
        if os.path.exists(photo_name):
            os.remove(photo_name)
        await state.finish()

if __name__ == '__main__':
    print("🚀 БОТ ЗАПУСКАЕТСЯ...")
    executor.start_polling(dp, skip_updates=True)
