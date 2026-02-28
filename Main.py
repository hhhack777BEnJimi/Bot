from google import genai
from google.genai import types
import os
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types as tg_types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# --- НАСТРОЙКИ ---
logging.basicConfig(level=logging.INFO)

# ТВОИ ДАННЫЕ (ВСТАВЬ СВОЙ НОВЫЙ КЛЮЧ)
API_KEY = "AIzaSyDxvNiFriZWjDhV5JzrFKMS2v9R_hMCdbY" 
TELEGRAM_TOKEN = "8285487433:AAHYPgB_wsoRtoDpM1GwdyNPoAZG6Fj05Ug"
SECRET_PASSWORD = "Venerabako1986"

# Инициализация нового клиента Gemini 3 Flash
# Этот клиент автоматически использует стабильные endpoint-ы API
client = genai.Client(api_key=API_KEY)
MODEL_NAME = 'gemini-3-flash' 

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# --- БАЗА ДАННЫХ ---
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

class TradingState(StatesGroup):
    auth = State()
    pair = State()
    tf = State()
    photo = State()

# --- ЛОГИКА ---

@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: tg_types.Message, state: FSMContext):
    await state.finish()
    if is_allowed(message.from_user.id):
        await message.answer("🏦 **ТЕРМИНАЛ S010lvloon v5.0 (SDK v3)**\nВведите торговую пару:")
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
    await message.answer("Укажите таймфрейм (напр. 15m, 1h):")
    await TradingState.tf.set()

@dp.message_handler(state=TradingState.tf)
async def get_tf(message: tg_types.Message, state: FSMContext):
    await state.update_data(tf=message.text)
    await message.answer("📸 Скидывай скриншот графика:")
    await TradingState.photo.set()

@dp.message_handler(content_types=['photo'], state=TradingState.photo)
async def process_analysis(message: tg_types.Message, state: FSMContext):
    data = await state.get_data()
    photo_name = f"chart_{message.from_user.id}.jpg"
    
    # Загружаем фото на диск
    await message.photo[-1].download(destination_file=photo_name)
    
    status_msg = await message.answer("📡 **ОБРАБОТКА БАЙТОВ И АНАЛИЗ...**")
    
    try:
        # 🔱 ЧИТАЕМ ФАЙЛ КАК БАЙТЫ (ПО ДОКУМЕНТАЦИИ)
        with open(photo_name, 'rb') as f:
            image_bytes = f.read()

        prompt = (
            f"Ты эксперт-трейдер. Проанализируй скриншот {data['pair']} на таймфрейме {data['tf']}. "
            "Дай четкий план: точка входа, стоп-лосс и тейк-профит. Отвечай на русском языке."
        )

        # 🔱 ОТПРАВКА ЧЕРЕЗ НОВЫЙ SDK (Contents -> Part -> Bytes)
        # 
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                prompt
            ]
        )
        
        # Вывод результата
        await status_msg.edit_text(f"📊 **ВЕРДИКТ {data['pair']}:**\n\n{response.text}")

    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка SDK v3: {str(e)}")
    
    finally:
        # Чистим временный файл
        if os.path.exists(photo_name):
            os.remove(photo_name)
        await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
