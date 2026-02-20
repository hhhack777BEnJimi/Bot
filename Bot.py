import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- БАПТАУЛАР ---
API_TOKEN = '8285487433:AAHYPgB_wsoRtoDpM1GwdyNPoAZG6Fj05Ug'  # BotFather-ден алған токен
ADMIN_ID =8145949506                  # Өзіңнің Telegram ID-ің
CARD_NUMBER = "4400430073664069" # Картаңның нөмірі
CARD_HOLDER = "BAKDAULET O."        # Карта иесінің аты

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- БАЗАНЫ ДАЙЫНДАУ ---
def init_db():
    conn = sqlite3.connect('virt_akikaty.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders 
                      (user_id INTEGER PRIMARY KEY, lang TEXT, option TEXT, 
                       content TEXT, phone TEXT, paid INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# --- МӘТІНДЕР (3 ТІЛ) ---
STRINGS = {
    'kz': {
        'start': "👋 'Вирт Ақиқаты' сервисіне қош келдіңіз.\n\n",
        'rules': "🚫 **ЕРЕЖЕЛЕР:**\n1. Сватингке, террорлық хабарламаларға тыйым салынған.\n2. Төлем қайтарылмайды (No Refund).\n3. Деректерді (мәтін/номер) кез келген уақытта өзгерте аласыз.",
        'opt1': "🗓 Тура 1 жылдан кейін",
        'opt2': "⏳ 4 ай желіде болмасам",
        'pay': f"💳 **ТӨЛЕМ:** 1000 ₸\nКарта: `{CARD_NUMBER}`\nИесі: {CARD_HOLDER}\n\nАударып болған соң, чектің **скриншотын** жіберіңіз.",
        'edit_info': "✍️ Енді кімге звондау керек (номер) және хабарламаңызды жазып жіберіңіз (мәтін немесе аудио).",
        'status': "📊 Менің аманатым",
        'success': "🚀 Төлем расталды! Мәліметтеріңіз сақталды."
    },
    'ru': {
        'start': "👋 Добро пожаловать в сервис 'Вирт Ақиқаты'.\n\n",
        'rules': "🚫 **ПРАВИЛА:**\n1. Сватинг и угрозы запрещены. Данные будут переданы органам.\n2. Возврата средств нет (No Refund).\n3. Вы можете редактировать свое сообщение и номер в любое время.",
        'opt1': "🗓 Ровно через 1 год",
        'opt2': "⏳ Если не буду в сети 4 месяца",
        'pay': f"💳 **ОПЛАТА:** 1100 ₸ (2.5$)\nКарта: `{CARD_NUMBER}`\nПолучатель: {CARD_HOLDER}\n\nПосле оплаты пришлите **скриншот** чека.",
        'edit_info': "✍️ Теперь напишите номер телефона получателя и ваше сообщение (текст или аудио).",
        'status': "📊 Мое послание",
        'success': "🚀 Оплата подтверждена! Ваши данные активны."
    },
    'en': {
        'start': "👋 Welcome to 'Virt Akikaty' service.\n\n",
        'rules': "🚫 **TERMS:**\n1. No swatting or illegal activities. Data will be reported to law enforcement.\n2. No refunds.\n3. You can edit your message and phone number anytime.",
        'opt1': "🗓 In exactly 1 year",
        'opt2': "⏳ If offline for 4 months",
        'pay': "💳 **PAYMENT:** $4 (CryptoBot / USDT)\nPlease send a **screenshot** of the transaction after payment.",
        'edit_info': "✍️ Now send the recipient's phone number and your message (text or audio).",
        'status': "📊 My Order",
        'success': "🚀 Payment confirmed! Your message is stored."
    }
}

# --- КНОПКАЛАР ---
def main_menu(lang):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(STRINGS[lang]['opt1'], callback_data=f"opt_1y_{lang}"),
           InlineKeyboardButton(STRINGS[lang]['opt2'], callback_data=f"opt_4m_{lang}"),
           InlineKeyboardButton(STRINGS[lang]['status'], callback_data=f"view_{lang}"))
    return kb

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🇰🇿 Қазақша", callback_data="lang_kz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
    )
    await message.answer("Tildi tandaniz / Выберите язык / Choose language:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('lang_'))
async def set_language(c: types.CallbackQuery):
    lang = c.data.split('_')[1]
    conn = sqlite3.connect('virt_akikaty.db')
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO orders (user_id, lang, paid) VALUES (?, ?, 0)", (c.from_user.id, lang))
    conn.commit()
    conn.close()
    await bot.edit_message_text(STRINGS[lang]['start'] + STRINGS[lang]['rules'], 
                                c.from_user.id, c.message.message_id, 
                                reply_markup=main_menu(lang), parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith('opt_'))
async def process_option(c: types.CallbackQuery):
    _, opt, lang = c.data.split('_')
    conn = sqlite3.connect('virt_akikaty.db')
    cur = conn.cursor()
    cur.execute("UPDATE orders SET option = ? WHERE user_id = ?", (opt, c.from_user.id))
    conn.commit()
    conn.close()
    await bot.send_message(c.from_user.id, STRINGS[lang]['pay'], parse_mode="Markdown")

# --- КІРІС ХАБАРЛАМАЛАРДЫ ӨҢДЕУ ---
@dp.message_handler(content_types=['photo', 'text', 'voice', 'audio'])
async def handle_input(message: types.Message):
    conn = sqlite3.connect('virt_akikaty.db')
    cur = conn.cursor()
    user = cur.execute("SELECT paid, lang FROM orders WHERE user_id = ?", (message.from_user.id,)).fetchone()
    
    if not user:
        return

    paid, lang = user

    if message.photo: # Төлем чегі келсе
        await message.answer("⌛ Checking... / Тексерілуде...")
        await bot.send_message(ADMIN_ID, f"🔔 **ЖАҢА ТӨЛЕМ!**\nКімнен: @{message.from_user.username}\nID: `{message.from_user.id}`", parse_mode="Markdown")
        await message.forward(ADMIN_ID)
        
        adm_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ РАСТАУ (Confirm)", callback_data=f"confirm_{message.from_user.id}"))
        await bot.send_message(ADMIN_ID, "Төлемді растайсыз ба?", reply_markup=adm_kb)
    
    else: # Мәтін немесе аудио (аманат) келсе
        content = message.text if message.text else message.voice.file_id if message.voice else message.audio.file_id
        cur.execute("UPDATE orders SET content = ? WHERE user_id = ?", (content, message.from_user.id))
        conn.commit()
        await message.answer("✅ Saved! / Сақталды! / Сохранено!\n(You can edit this any time / Кез келген уақытта өзгерте аласыз)")

    conn.close()

# --- АДМИН ТӨЛЕМДІ РАСТАУЫ ---
@dp.callback_query_handler(lambda c: c.data.startswith('confirm_'))
async def admin_pay_ok(c: types.CallbackQuery):
    user_id = c.data.split('_')[1]
    conn = sqlite3.connect('virt_akikaty.db')
    cur = conn.cursor()
    cur.execute("UPDATE orders SET paid = 1 WHERE user_id = ?", (user_id,))
    lang_res = cur.execute("SELECT lang FROM orders WHERE user_id = ?", (user_id,)).fetchone()
    conn.commit()
    conn.close()
    
    lang = lang_res[0] if lang_res else 'kz'
    await bot.send_message(user_id, STRINGS[lang]['success'] + "\n\n" + STRINGS[lang]['edit_info'])
    await bot.answer_callback_query(c.id, "Пайдаланушыға рұқсат берілді!")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
