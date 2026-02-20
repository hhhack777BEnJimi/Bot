import logging
import sqlite3
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8285487433:AAHYPgB_wsoRtoDpM1GwdyNPoAZG6Fj05Ug' # Телеграм бот API
CRYPTO_PAY_TOKEN = '535427:AAUe3CLI9OeKRaXrW61dQgHvB7kLLtNPfXb' # CryptoBot API
ADMIN_ID = 8145949506  # Осы жерге @userinfobot арқылы өз ID-іңді жазып қой!
CARD_NUMBER = "4400430073664069"
CARD_HOLDER = "Bakdaylet O."

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- БАЗАНЫ БАПТАУ ---
def init_db():
    conn = sqlite3.connect('virt_akikaty.db')
    cur = conn.cursor()
    # state: 0 - төлем, 1 - номер күту, 2 - хат күту
    cur.execute('''CREATE TABLE IF NOT EXISTS orders 
                  (user_id INTEGER PRIMARY KEY, lang TEXT, 
                   phone TEXT, content TEXT, paid INTEGER DEFAULT 0, state INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

STRINGS = {
    'kz': {
        'start': "👋 @DelayedCall сервисіне қош келдіңіз. Тілді таңдаңыз:",
        'pay_msg': f"💳 **ТӨЛЕМ:** 1000 ₸\nКарта: `{CARD_NUMBER}`\nИесі: {CARD_HOLDER}\n\nАударып болған соң, чектің скриншотын жіберіңіз.",
        'ask_phone': "📱 **1-ші қадам:**\nБолашақта біз хабарласатын телефон номерін жазыңыз (мысалы: +77071234567):",
        'ask_text': "✍️ **2-ші қадам:**\nКеремет! Енді сол адамға айтылатын аманат хатыңызды жіберіңіз (мәтін немесе аудио):",
        'save_ok': "⭐ **Бәрі сақталды!** Мәліметтеріңіз қабылданды. Оны кез келген уақытта өзгерте аласыз."
    },
    'ru': {
        'start': "👋 Добро пожаловать в @DelayedCall. Выберите язык:",
        'pay_msg': f"💳 **ОПЛАТА:** 1100 ₸\nКарта: `{CARD_NUMBER}`\nПолучатель: {CARD_HOLDER}\n\nПришлите скриншот чека после оплаты.",
        'ask_phone': "📱 **Шаг 1:**\nВведите номер телефона, по которому нам нужно позвонить (+7707...):",
        'ask_text': "✍️ **Шаг 2:**\nОтлично! Теперь отправьте ваше сообщение (текст или аудио):",
        'save_ok': "⭐ **Все сохранено!** Ваши данные приняты."
    }
}

# --- ТІЛ ТАҢДАУ ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🇰🇿 Қазақша", callback_data="lang_kz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")
    )
    await message.answer(STRINGS['kz']['start'], reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('lang_'))
async def set_lang(c: types.CallbackQuery):
    lang = c.data.split('_')[1]
    conn = sqlite3.connect('virt_akikaty.db')
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO orders (user_id, lang) VALUES (?, ?)", (c.from_user.id, lang))
    conn.commit()
    conn.close()
    
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🗓 1 Year / 1 Жыл", callback_data=f"opt_1y_{lang}"))
    await bot.send_message(c.from_user.id, "Тарифті таңдаңыз:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('opt_'))
async def process_pay(c: types.CallbackQuery):
    lang = c.data.split('_')[2]
    await bot.send_message(c.from_user.id, STRINGS[lang]['pay_msg'], parse_mode="Markdown")

# --- ТӨЛЕМ ЖӘНЕ ДЕРЕКТЕРДІ ҚАБЫЛДАУ ---
@dp.message_handler(content_types=['photo', 'text', 'voice', 'audio'])
async def handle_all(message: types.Message):
    conn = sqlite3.connect('virt_akikaty.db')
    cur = conn.cursor()
    user = cur.execute("SELECT lang, state, paid FROM orders WHERE user_id = ?", (message.from_user.id,)).fetchone()
    
    if not user: return
    lang, state, paid = user

    # 1. Чек жіберу
    if message.photo and paid == 0:
        await message.answer("⌛ Тексерілуде... Күте тұрыңыз.")
        await bot.send_message(ADMIN_ID, f"💰 **ЖАҢА ТӨЛЕМ!**\nКімнен: @{message.from_user.username}")
        await message.forward(ADMIN_ID)
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ РАСТАУ", callback_data=f"adm_ok_{message.from_user.id}"))
        await bot.send_message(ADMIN_ID, "Төлемді растайсыз ба?", reply_markup=kb)

    # 2. Номерді жазу (State 1)
    elif state == 1 and message.text:
        cur.execute("UPDATE orders SET phone = ?, state = 2 WHERE user_id = ?", (message.text, message.from_user.id))
        conn.commit()
        await message.answer(STRINGS[lang]['ask_text'], parse_mode="Markdown")

    # 3. Хатты жазу (State 2)
    elif state == 2:
        content = message.text if message.text else (message.voice.file_id if message.voice else message.audio.file_id)
        cur.execute("UPDATE orders SET content = ?, state = 0 WHERE user_id = ?", (content, message.from_user.id))
        conn.commit()
        await message.answer(STRINGS[lang]['save_ok'], parse_mode="Markdown")

    conn.close()

# --- АДМИН РАСТАУЫ ---
@dp.callback_query_handler(lambda c: c.data.startswith('adm_ok_'))
async def admin_confirm(c: types.CallbackQuery):
    uid = c.data.split('_')[2]
    conn = sqlite3.connect('virt_akikaty.db')
    cur = conn.cursor()
    cur.execute("UPDATE orders SET paid = 1, state = 1 WHERE user_id = ?", (uid,))
    lang = cur.execute("SELECT lang FROM orders WHERE user_id = ?", (uid,)).fetchone()[0]
    conn.commit()
    conn.close()
    
    await bot.send_message(uid, STRINGS[lang]['ask_phone'], parse_mode="Markdown")
    await bot.answer_callback_query(c.id, "Пайдаланушыға рұқсат берілді")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
