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
ADMIN_ID = 8145949506 
SUPPORT_USER = "@lenixe"
CARD_NUMBER = "4400430073664069"
CARD_HOLDER = "Bakdaylet O."

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- БАЗАНЫ ДАЙЫНДАУ ---
conn = sqlite3.connect('delayed_call.db', check_same_thread=False)
cur = conn.cursor()
cur.execute('''CREATE TABLE IF NOT EXISTS orders 
               (user_id INTEGER PRIMARY KEY, lang TEXT, state INTEGER DEFAULT 0, 
                phone TEXT, content TEXT, delivery_date TEXT, 
                to_name TEXT, from_name TEXT, paid INTEGER DEFAULT 0, tariff TEXT)''')
conn.commit()

# --- ТҮСІНДІРМЕ МӘТІНІ (ЖАҢАРТЫЛҒАН) ---
START_TEXT = (
    "🚀 **@DelayedCall** — болашаққа хат пен қоңырау жеткізу сервисі.\n"
    "✨ Біз сіздің атыңыздан арнайы мәтінді оқып, сезімдеріңізді немесе туған күн құттықтауларын жеткіземіз.\n"
    "📦 **Болашаққа хат:** Өзіңізге немесе жақыныңызға жылдар өткен соң жететін аманат қалдырыңыз!\n\n"
    
    "🚀 **@DelayedCall** — сервис доставки посланий и звонков в будущее.\n"
    "✨ Мы доставим ваши чувства или поздравления точно в срок.\n"
    "📦 **Письмо в будущее:** Оставьте послание себе или близким, которое придет спустя годы!\n\n"
    
    "🚀 **@DelayedCall** — future message and call delivery service.\n"
    "✨ We deliver your feelings or greetings exactly on time.\n"
    "📦 **Letter to the future:** Leave a message for yourself or your loved ones that will arrive years later!\n\n"
    
    "👇 **Тілді таңдаңыз / Выберите язык / Choose language:**"
)


# --- МӘЗІРДЕР ---
def get_main_menu(lang, is_paid):
    kb = InlineKeyboardMarkup(row_width=1)
    if is_paid:
        txt = {"kz": "👤 Жеке кабинет", "ru": "👤 Личный кабинет", "en": "👤 Cabinet"}[lang]
        kb.add(InlineKeyboardButton(txt, callback_data="cabinet"))
    else:
        txt = {"kz": "🗓 Тарифті таңдау", "ru": "🗓 Выбрать тариф", "en": "🗓 Select Tariff"}[lang]
        kb.add(InlineKeyboardButton(txt, callback_data="tariffs"))
    kb.add(InlineKeyboardButton("👨‍💻 Support", url=f"https://t.me/{SUPPORT_USER.replace('@', '')}"))
    return kb

# --- СТАРТ КОМАНДАСЫ ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("🇰🇿 Қазақша", callback_data="lang_kz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
    )
    await message.answer(START_TEXT, reply_markup=kb, parse_mode="Markdown")

# --- ТІЛ ЖӘНЕ ТАРИФ ТАҢДАУ ---
@dp.callback_query_handler(lambda c: c.data.startswith('lang_'))
async def set_lang(c: types.CallbackQuery):
    lang = c.data.split('_')[1]
    cur.execute("INSERT OR REPLACE INTO orders (user_id, lang) VALUES (?, ?)", (c.from_user.id, lang))
    conn.commit()
    user_paid = cur.execute("SELECT paid FROM orders WHERE user_id=?", (c.from_user.id,)).fetchone()[0]
    await bot.send_message(c.from_user.id, "✅ Тіл сақталды / Язык сохранен", reply_markup=get_main_menu(lang, user_paid))

@dp.callback_query_handler(lambda c: c.data == "tariffs")
async def show_tariffs(c: types.CallbackQuery):
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("🗓 Стандарт (1 жыл) - 1000 ₸", callback_data="pay_std"),
        InlineKeyboardButton("🎂 VIP: Құттықтау/Сезім - 2300 ₸", callback_data="pay_vip")
    )
    await bot.send_message(c.from_user.id, "Тарифті таңдаңыз / Выберите тариф:", reply_markup=kb)

# --- ТӨЛЕМ ЖҮЙЕСІ (KASPI + CRYPTO) ---
@dp.callback_query_handler(lambda c: c.data.startswith('pay_'))
async def process_payment(c: types.CallbackQuery):
    t_type = c.data.split('_')[1]
    user_id = c.from_user.id
    lang = cur.execute("SELECT lang FROM orders WHERE user_id=?", (user_id,)).fetchone()[0]
    cur.execute("UPDATE orders SET tariff=? WHERE user_id=?", (t_type, user_id))
    conn.commit()

    if lang == 'kz':
        price = "1000" if t_type == "std" else "2300"
        msg = f"🇰🇿 **Каспи төлем:**\n\nСумма: {price} ₸\nКарта: `{CARD_NUMBER}`\nИесі: {CARD_HOLDER}\n\nЧекті скриншот қылып жіберіңіз."
        await bot.send_message(user_id, msg, parse_mode="Markdown")
    else:
        # CRYPTOBOT ИНТЕГРАЦИЯСЫ (RU/EN үшін)
        amount = "2.5" if t_type == "std" else "5.5"
        url = "https://pay.crypt.bot/api/createInvoice"
        headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
        payload = {"asset": "USDT", "amount": amount, "description": f"DelayedCall {t_type}"}
        res = requests.post(url, headers=headers, json=payload).json()
        if res['ok']:
            pay_url = res['result']['pay_url']
            inv_id = res['result']['invoice_id']
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("💸 CryptoBot Pay", url=pay_url))
            await bot.send_message(user_id, f"💳 Total: {amount} USDT", reply_markup=kb)
            asyncio.create_task(check_crypto(user_id, inv_id))

async def check_crypto(user_id, inv_id):
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    for _ in range(30):
        await asyncio.sleep(20)
        res = requests.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={inv_id}", headers=headers).json()
        if res['ok'] and res['result']['items'][0]['status'] == 'paid':
            cur.execute("UPDATE orders SET paid=1, state=1 WHERE user_id=?", (user_id,))
            conn.commit()
            await bot.send_message(user_id, "✅ Төлем расталды! Датаны жазыңыз (хх.хх.хххх):")
            break

# --- ЖЕКЕ КАБИНЕТ (ТАРИФКЕ БАЙЛАНЫСТЫ ШЕКТЕУ) ---
@dp.callback_query_handler(lambda c: c.data == "cabinet")
async def show_cabinet(c: types.CallbackQuery):
    u = cur.execute("SELECT phone, delivery_date, to_name, from_name, tariff, lang FROM orders WHERE user_id=?", (c.from_user.id,)).fetchone()
    phone, date, to_n, from_n, tariff, lang = u
    
    kb = InlineKeyboardMarkup(row_width=1)
    if tariff == "vip":
        kb.add(InlineKeyboardButton("📅 Күнді өзгерту", callback_data="edit_date"),
               InlineKeyboardButton("👥 Есімдерді өзгерту", callback_data="edit_names"))
    
    kb.add(InlineKeyboardButton("✍️ Хатты өзгерту", callback_data="edit_content"),
           InlineKeyboardButton("📞 Номерді өзгерту", callback_data="edit_phone"))
    
    txt = f"👤 **Жеке кабинет ({tariff.upper()})**\n\n📅 Күні: `{date}`\n👥 Кімге: {to_n}\n👤 Кімнен: {from_n}\n📞 Номер: `{phone}`"
    await bot.send_message(c.from_user.id, txt, reply_markup=kb, parse_mode="Markdown")

# --- ӨЗГЕРТУ ЖӘНЕ ДЕРЕКТЕРДІ ҚАБЫЛДАУ ---
@dp.callback_query_handler(lambda c: c.data.startswith('edit_'))
async def edit_routing(c: types.CallbackQuery):
    action = c.data.split('_')[1]
    states = {"date": 1, "names": 2, "phone": 4, "content": 5}
    cur.execute("UPDATE orders SET state=? WHERE user_id=?", (states[action], c.from_user.id))
    conn.commit()
    await bot.send_message(c.from_user.id, "Жаңа мәліметті енгізіңіз:")

@dp.message_handler(content_types=['photo', 'text', 'voice'])
async def handle_all(message: types.Message):
    u = cur.execute("SELECT state, paid, lang, tariff FROM orders WHERE user_id=?", (message.from_user.id,)).fetchone()
    if not u: return
    state, paid, lang, tariff = u

    if message.photo and paid == 0:
        await bot.send_message(ADMIN_ID, f"💰 Чек: @{message.from_user.username}")
        await message.forward(ADMIN_ID)
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ РАСТАУ", callback_data=f"admok_{message.from_user.id}"))
        await bot.send_message(ADMIN_ID, "Төлемді растайсыз ба?", reply_markup=kb)

    elif state > 0:
        if state == 1: cur.execute("UPDATE orders SET delivery_date=? WHERE user_id=?", (message.text, message.from_user.id))
        elif state == 2: cur.execute("UPDATE orders SET to_name=? WHERE user_id=?", (message.text, message.from_user.id))
        elif state == 4: cur.execute("UPDATE orders SET phone=? WHERE user_id=?", (message.text, message.from_user.id))
        elif state == 5:
            cont = message.text if message.text else "Media/Voice"
            cur.execute("UPDATE orders SET content=? WHERE user_id=?", (cont, message.from_user.id))
        
        cur.execute("UPDATE orders SET state=0 WHERE user_id=?", (message.from_user.id,))
        conn.commit()
        await message.answer("✅ Сақталды!", reply_markup=get_main_menu(lang, 1))

@dp.callback_query_handler(lambda c: c.data.startswith('admok_'))
async def admin_ok(c: types.CallbackQuery):
    uid = c.data.split('_')[1]
    cur.execute("UPDATE orders SET paid=1, state=1 WHERE user_id=?", (uid,))
    conn.commit()
    await bot.send_message(uid, "✅ Төлем расталды! Жеткізу күнін жазыңыз (хх.хх.хххх):")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
