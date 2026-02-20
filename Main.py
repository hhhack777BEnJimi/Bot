import logging
import sqlite3
import requests
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8285487433:AAHYPgB_wsoRtoDpM1GwdyNPoAZG6Fj05Ug'
CRYPTO_PAY_TOKEN = '535427:AAUe3CLI9OeKRaXrW61dQgHvB7kLLtNPfXb'
ADMIN_ID = 8145949506  # Сенің Admin ID-ің
SUPPORT_USER = "@lenixe" # Сенің Юзернеймің
CARD_NUMBER = "4400430073664069"
CARD_HOLDER = "Bakdaylet O."

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- БАЗАНЫ БАСТАУ ---
conn = sqlite3.connect('delayed_call.db', check_same_thread=False)
cur = conn.cursor()
cur.execute('''CREATE TABLE IF NOT EXISTS orders 
               (user_id INTEGER PRIMARY KEY, lang TEXT, state INTEGER DEFAULT 0, 
                phone TEXT, content TEXT, paid INTEGER DEFAULT 0)''')
conn.commit()

# --- МӘТІНДЕР ---
WELCOME_TEXT = {
    'kz': "🚀 **@DelayedCall** — болашаққа хат пен қоңырау жеткізу сервисі.\n\nБіз сіздің аманатыңызды белгіленген уақытта нақты иесіне табыстаймыз. Дауысыңыз бен сөзіңіз жылдар өтсе де жоғалмайды.",
    'ru': "🚀 **@DelayedCall** — сервис доставки ваших посланий в будущее.\n\nМы доставим ваше сообщение или совершим звонок точно в назначенный срок. Ваши слова сохранятся сквозь года.",
    'en': "🚀 **@DelayedCall** — delivery service for your messages to the future.\n\nWe will deliver your message or make a call exactly on time. Your words will be preserved through the years."
}

# --- МӘЗІР ---
def main_menu(lang):
    kb = InlineKeyboardMarkup(row_width=1)
    if lang == 'kz':
        kb.add(InlineKeyboardButton("🗓 1 жылдық тариф (1000 ₸)", callback_data="buy_1y"),
               InlineKeyboardButton("⏳ 4 айлық тариф (1000 ₸)", callback_data="buy_4m"),
               InlineKeyboardButton("👨‍💻 Тех. қолдау", url=f"https://t.me/{SUPPORT_USER.replace('@', '')}"))
    else:
        kb.add(InlineKeyboardButton("🗓 1 Year / 1 Год (2.5 USDT)", callback_data="buy_1y"),
               InlineKeyboardButton("⏳ 4 Months / 4 Месяца (2.5 USDT)", callback_data="buy_4m"),
               InlineKeyboardButton("👨‍💻 Support / Поддержка", url=f"https://t.me/{SUPPORT_USER.replace('@', '')}"))
    return kb

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🇰🇿 Қазақша", callback_data="setlang_kz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_ru"),
        InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")
    )
    await message.answer("Tildi tandaniz / Выберите язык:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('setlang_'))
async def set_lang(c: types.CallbackQuery):
    lang = c.data.split('_')[1]
    cur.execute("INSERT OR REPLACE INTO orders (user_id, lang) VALUES (?, ?)", (c.from_user.id, lang))
    conn.commit()
    await bot.edit_message_text(WELCOME_TEXT[lang], c.from_user.id, c.message.message_id, 
                                reply_markup=main_menu(lang), parse_mode="Markdown")

# --- ТӨЛЕМ ЖҮЙЕСІ ---
@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def start_payment(c: types.CallbackQuery):
    user_id = c.from_user.id
    lang_row = cur.execute("SELECT lang FROM orders WHERE user_id=?", (user_id,)).fetchone()
    lang = lang_row[0] if lang_row else 'kz'
    
    if lang == 'kz':
        msg = f"🇰🇿 **Каспи арқылы төлем:**\n\nСомасы: 1000 ₸\nКарта: `{CARD_NUMBER}`\nИесі: {CARD_HOLDER}\n\nТөлеп болған соң, чекті фото ретінде жіберіңіз."
        await bot.send_message(user_id, msg, parse_mode="Markdown")
    else:
        # CryptoBot
        url = "https://pay.crypt.bot/api/createInvoice"
        headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
        payload = {"asset": "USDT", "amount": "2.5", "description": "DelayedCall Sub"}
        try:
            res = requests.post(url, headers=headers, json=payload).json()
            if res['ok']:
                pay_url = res['result']['pay_url']
                invoice_id = res['result']['invoice_id']
                kb = InlineKeyboardMarkup().add(InlineKeyboardButton("💸 Crypto Pay (2.5 USDT)", url=pay_url))
                await bot.send_message(user_id, "💳 **Payment via CryptoBot:**\nAutomatic confirmation after payment.", reply_markup=kb)
                asyncio.create_task(check_crypto(user_id, invoice_id, lang))
        except:
            await bot.send_message(user_id, f"Error. Please contact {SUPPORT_USER}")

async def check_crypto(user_id, inv_id, lang):
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    for _ in range(60):
        await asyncio.sleep(15)
        res = requests.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={inv_id}", headers=headers).json()
        if res['ok'] and res['result']['items'][0]['status'] == 'paid':
            cur.execute("UPDATE orders SET paid=1, state=1 WHERE user_id=?", (user_id,))
            conn.commit()
            await bot.send_message(user_id, "✅ Payment confirmed! Now, enter the phone number:")
            break

# --- ҚАДАМДАР ---
@dp.message_handler(content_types=['photo', 'text', 'voice'])
async def handle_steps(message: types.Message):
    user = cur.execute("SELECT lang, state, paid FROM orders WHERE user_id=?", (message.from_user.id,)).fetchone()
    if not user: return
    lang, state, paid = user

    if message.photo and paid == 0:
        await message.answer("⌛ Тексерілуде...")
        await bot.send_message(ADMIN_ID, f"💰 **ЖАҢА ЧЕК!**\nКімнен: @{message.from_user.username}")
        await message.forward(ADMIN_ID)
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ РАСТАУ", callback_data=f"ok_{message.from_user.id}"))
        await bot.send_message(ADMIN_ID, "Төлемді растайсыз ба?", reply_markup=kb)

    elif state == 1 and message.text:
        cur.execute("UPDATE orders SET phone=?, state=2 WHERE user_id=?", (message.text, message.from_user.id))
        conn.commit()
        await message.answer("✍️ Енді аманат хатыңызды жіберіңіз (мәтін немесе аудио):")

    elif state == 2:
        content = message.text if message.text else "Voice/Media"
        cur.execute("UPDATE orders SET content=?, state=0 WHERE user_id=?", (content, message.from_user.id))
        conn.commit()
        await message.answer("⭐ Бәрі сәтті сақталды! Сау болыңыз.")

@dp.callback_query_handler(lambda c: c.data.startswith('ok_'))
async def admin_ok(c: types.CallbackQuery):
    uid = c.data.split('_')[1]
    cur.execute("UPDATE orders SET paid=1, state=1 WHERE user_id=?", (uid,))
    conn.commit()
    await bot.send_message(uid, "✅ Төлем расталды! Енді номерді жазыңыз:")
    await bot.answer_callback_query(c.id)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
