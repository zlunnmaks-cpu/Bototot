import asyncio
import sqlite3
import time
import datetime
import sys
import logging
import os

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    FSInputFile, InputMediaPhoto
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiocryptopay import AioCryptoPay
from aiogram.dispatcher.middlewares.base import BaseMiddleware

TOKEN = os.getenv("TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")

OWNER_USER = "@ilushasigma888"
TECH_SUPPORT = "@sotk4a"

ADMIN_IDS = [8111563993]

LOG_CHANNEL_ID = -1003856306124
CHECK_CHANNEL_ID = -1003137750140
CHANNEL_LINK = "https://t.me/ilyashpatel"

STICKER_WELCOME = "CAACAgIAAxkBAAIPzmmm_paZcEbBjbuD_T6t7PB9-T9-AAI6jgACEpx4SS37qz8QpA9SOgQ"

ST_HI = "5350301517234586704"
ST_GOODS_BTN = "5348203150832583752"
ST_STAR = "5895770017458294953"
ST_IND = "5307594204984140413"
ST_PROFILE = "5350763436672305153"
ST_SUPPORT = "5350790271627968474"
ST_BACK = "5256247952564825322"
ST_CHECK = "5350572310627632617"
ST_WARN = "5904692292324692386"
ST_MONEY = "5348418461838098123"
ST_CARD = "5902056028513505203"
ST_EXCL = "5345814569195421891"
ST_PIN = "5348498060466996739"
ST_LINK = "5350695039318114023"
ST_PROMO = "5893382531037794941"
ST_N_CLIENT = "5238118569190908612"
ST_CEL = "5237784145857373350"
ST_CFG_BTN = "5348412779596365405"

PRODUCTS_DEFAULT = {
    "ns_s": {
        "name": "N-Client [Spookytime]",
        "st": ST_N_CLIENT,
        "desc": "N-Client",
        "p_rub": 50,
        "p_st": 45,
        "link": "<b><a href='https://t.me/ilushasigma888'>Товар</a></b>"
    },
    "cl_f": {
        "name": "Celestial [Funtime]",
        "st": ST_CEL,
        "desc": "Celestial Client",
        "p_rub": 50,
        "p_st": 45,
        "link": "<b><a href='https://t.me/ilushasigma888'>Товар</a></b>"
    },
    "free_ind": {
        "name": "Индикация талисманов",
        "st": ST_IND,
        "desc": "Free",
        "p_rub": 0,
        "p_st": 0,
        "link": "https://drive.google.com/file/d/1InROezrlYVPyy5ka3UnbHOPpsR49auGj/view"
    },
    "free_rp": {
        "name": "Ресурс-пак Оникса",
        "st": ST_STAR,
        "desc": "Free",
        "p_rub": 0,
        "p_st": 0,
        "link": "https://drive.google.com/file/d/1CIWbvH75bh3V2Wh3sQe0pRGqzgAsvZ2X/view"
    },
    "free_rp_pvp": {
        "name": "PvP Ресурс-пак",
        "st": ST_STAR,
        "desc": "Free",
        "p_rub": 0,
        "p_st": 0,
        "link": "https://drive.google.com/file/d/1ygEB3Mwqe4zd1EEHHjkiAdH72GO0wgIc/view?usp=drive_link"
    }
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()
crypto: AioCryptoPay = None


class AdminEditProduct(StatesGroup):
    item_code = State()
    price = State()
    link = State()
    desc = State()


class AdminPromo(StatesGroup):
    item_code = State()
    code = State()
    discount = State()
    max_uses = State()
    uses_per_user = State()


class UserPromo(StatesGroup):
    code = State()


class Deposit(StatesGroup):
    amount = State()


def db_query(sql, params=(), fetch=False):
    with sqlite3.connect("onyx.db") as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        if fetch:
            return cur.fetchall()
        conn.commit()


def init_db():
    db_query("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            username TEXT, 
            reg_ts REAL, 
            balance REAL DEFAULT 0, 
            has_sub INTEGER DEFAULT 0, 
            is_banned INTEGER DEFAULT 0, 
            ban_reason TEXT,
            is_admin INTEGER DEFAULT 0
        )
    """)
    db_query("CREATE TABLE IF NOT EXISTS product_data (id TEXT PRIMARY KEY, price_rub INTEGER, price_st INTEGER, link TEXT, desc TEXT)")
    db_query("CREATE TABLE IF NOT EXISTS promocodes (code TEXT PRIMARY KEY, item_id TEXT, discount INTEGER, max_uses INTEGER, uses_per_user INTEGER, current_uses INTEGER DEFAULT 0)")
    db_query("CREATE TABLE IF NOT EXISTS user_promos (user_id INTEGER, promo_code TEXT, uses INTEGER DEFAULT 0, PRIMARY KEY (user_id, promo_code))")
    db_query("CREATE TABLE IF NOT EXISTS user_active_promos (user_id INTEGER, item_id TEXT, promo_code TEXT, discount INTEGER, PRIMARY KEY (user_id, item_id))")

    try:
        db_query("SELECT is_admin FROM users LIMIT 1")
    except sqlite3.OperationalError:
        db_query("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")

    for code, data in PRODUCTS_DEFAULT.items():
        db_query("INSERT OR IGNORE INTO product_data (id, price_rub, price_st, link, desc) VALUES (?, ?, ?, ?, ?)",
                 (code, data['p_rub'], data['p_st'], data['link'], data['desc']))


def get_item(item_code):
    res = db_query("SELECT price_rub, price_st, link, desc FROM product_data WHERE id = ?", (item_code,), fetch=True)
    base = PRODUCTS_DEFAULT.get(item_code)

    if not res:
        if base:
            return {"name": base["name"], "st": base["st"], "p_rub": base["p_rub"], "p_st": base["p_st"], "link": base["link"], "desc": base["desc"]}
        return None

    return {"name": base["name"], "st": base["st"], "p_rub": res[0][0], "p_st": res[0][1], "link": res[0][2], "desc": res[0][3]}


def is_admin(user_id):
    if user_id in ADMIN_IDS:
        return True
    try:
        res = db_query("SELECT is_admin FROM users WHERE user_id = ?", (user_id,), fetch=True)
        if res and res[0][0] == 1:
            return True
    except Exception:
        pass
    return False


class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        u = db_query("SELECT is_banned, ban_reason, is_admin FROM users WHERE user_id = ?", (user_id,), fetch=True)

        if u:
            is_banned, ban_reason, is_admin_db = u[0]
            if is_banned == 1:
                if user_id in ADMIN_IDS or is_admin_db == 1:
                    return await handler(event, data)

                if isinstance(event, types.Message):
                    await event.answer(f"<tg-emoji emoji-id='{ST_WARN}'>⚠️</tg-emoji> <b>Вы заблокированы.</b>\nПричина: {ban_reason}", parse_mode="HTML")
                return

        return await handler(event, data)


dp.message.middleware(BanMiddleware())
dp.callback_query.middleware(BanMiddleware())


def main_reply_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Меню"), KeyboardButton(text="Профиль")]
        ],
        resize_keyboard=True
    )


def main_inline_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выберите товары", callback_data="shop_main", icon_custom_emoji_id=ST_GOODS_BTN)],
        [
            InlineKeyboardButton(text="Профиль", callback_data="profile", icon_custom_emoji_id=ST_PROFILE),
            InlineKeyboardButton(text="Поддержка", callback_data="support", icon_custom_emoji_id=ST_SUPPORT)
        ]
    ])


def shop_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Платные", callback_data="paid_menu", icon_custom_emoji_id=ST_MONEY),
            InlineKeyboardButton(text="Бесплатные", callback_data="free_menu", icon_custom_emoji_id=ST_STAR)
        ],
        [InlineKeyboardButton(text="Назад", callback_data="to_main", icon_custom_emoji_id=ST_BACK)]
    ])


def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отменить", callback_data="cancel_state", icon_custom_emoji_id=ST_WARN)]
    ])


def get_start_text():
    return (
        f"<tg-emoji emoji-id='{ST_HI}'>👋</tg-emoji> <b>Привет кент, ты в боте Оникса.\n\n"
        "Тут ты найдёшь самые пиздатые конфиги и самые красивые ресурс-паки для игры в майнкрафт.</b>"
    )


async def force_media(call: types.CallbackQuery, photo_path: str, caption: str, kb: InlineKeyboardMarkup):
    try:
        media = InputMediaPhoto(type='photo', media=FSInputFile(photo_path), caption=caption, parse_mode="HTML")
        await call.message.edit_media(media=media, reply_markup=kb)
    except Exception as e:
        if "not modified" in str(e).lower():
            return
        await call.message.answer_photo(FSInputFile(photo_path), caption=caption, reply_markup=kb, parse_mode="HTML")


@dp.message(Command("start"))
@dp.message(F.text == "Меню")
async def cmd_start(msg: types.Message):
    db_query("INSERT OR IGNORE INTO users (user_id, username, reg_ts, is_admin) VALUES (?, ?, ?, 0)",
             (msg.from_user.id, msg.from_user.username, time.time()))

    await msg.answer_sticker(sticker=STICKER_WELCOME, reply_markup=main_reply_kb())
    try:
        await msg.answer_photo(FSInputFile("logo.jpg"), caption=get_start_text(), reply_markup=main_inline_kb(), parse_mode="HTML")
    except Exception:
        await msg.answer(get_start_text(), reply_markup=main_inline_kb(), parse_mode="HTML")


@dp.callback_query(F.data == "to_main")
async def back_to_main(call: types.CallbackQuery):
    await force_media(call, "logo.jpg", get_start_text(), main_inline_kb())


@dp.message(F.text == "Профиль")
async def btn_profile(msg: types.Message):
    await show_profile(msg, is_callback=False)


@dp.callback_query(F.data == "profile")
async def profile_handler(call: types.CallbackQuery):
    await show_profile(call, is_callback=True)


async def show_profile(event, is_callback):
    user = event.from_user
    res = db_query("SELECT reg_ts, balance, is_admin FROM users WHERE user_id = ?", (user.id,), fetch=True)

    if not res:
        db_query("INSERT OR IGNORE INTO users (user_id, username, reg_ts, is_admin) VALUES (?, ?, ?, 0)",
                 (user.id, user.username, time.time()))
        res = [[time.time(), 0, 0]]

    dt = datetime.datetime.fromtimestamp(res[0][0])
    uname = f"@{user.username}" if user.username else "Пользователь"
    admin_tag = " (Admin)" if res[0][2] == 1 or user.id in ADMIN_IDS else ""

    text = (
        f"<tg-emoji emoji-id='{ST_PROFILE}'>👤</tg-emoji> <b>Профиль {uname}{admin_tag}</b>\n\n"
        f"<tg-emoji emoji-id='{ST_PIN}'>📌</tg-emoji> <b>ID:</b> <code>{user.id}</code>\n"
        f"<tg-emoji emoji-id='{ST_MONEY}'>💲</tg-emoji> <b>Баланс:</b> <b>{res[0][1]} ₽</b>\n"
        f"<tg-emoji emoji-id='{ST_CHECK}'>✅</tg-emoji> <b>Регистрация:</b> {dt.strftime('%d.%m.%Y')}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пополнить баланс", callback_data="deposit_menu", icon_custom_emoji_id=ST_CARD)],
        [InlineKeyboardButton(text="Ввести промокод", callback_data="promo_activate", icon_custom_emoji_id=ST_PROMO)],
        [InlineKeyboardButton(text="Назад", callback_data="to_main", icon_custom_emoji_id=ST_BACK)]
    ])

    if not is_callback:
        await event.answer_photo(FSInputFile("logo.jpg"), caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        await force_media(event, "logo.jpg", text, kb)


@dp.callback_query(F.data == "support")
async def support_menu(call: types.CallbackQuery):
    text = (
        f"<tg-emoji emoji-id='{ST_SUPPORT}'>📞</tg-emoji> <b>Поддержка</b>\n\n"
        f"<tg-emoji emoji-id='{ST_PIN}'>📌</tg-emoji> <b>Владелец:</b> {OWNER_USER}\n"
        f"<tg-emoji emoji-id='{ST_PIN}'>📌</tg-emoji> <b>Тех. поддержка:</b> {TECH_SUPPORT}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="to_main", icon_custom_emoji_id=ST_BACK)]
    ])
    await force_media(call, "logo.jpg", text, kb)


@dp.callback_query(F.data == "shop_main")
async def shop_main_menu(call: types.CallbackQuery):
    text = f"<tg-emoji emoji-id='{ST_PIN}'>📌</tg-emoji> <b>Выберите категорию товаров:</b>"
    await force_media(call, "logo.jpg", text, shop_kb())


@dp.callback_query(F.data == "free_menu")
@dp.callback_query(F.data == "check_sub")
async def free_menu_handler(call: types.CallbackQuery):
    try:
        member = await bot.get_chat_member(CHECK_CHANNEL_ID, call.from_user.id)
        has_sub = 1 if member.status in ['member', 'administrator', 'creator'] else 0
    except Exception:
        has_sub = 0

    if has_sub == 0:
        txt = f"<tg-emoji emoji-id='{ST_WARN}'>⚠️</tg-emoji> <b>Для доступа к бесплатным товарам подпишитесь на канал!</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подписаться", url=CHANNEL_LINK)],
            [InlineKeyboardButton(text="Подтвердить", callback_data="check_sub", icon_custom_emoji_id=ST_CHECK)],
            [InlineKeyboardButton(text="Назад", callback_data="shop_main", icon_custom_emoji_id=ST_BACK)]
        ])
        await force_media(call, "logo.jpg", txt, kb)

        if call.data == "check_sub":
            await call.answer("❌ Вы всё ещё не подписались!", show_alert=True)
    else:
        if call.data == "check_sub":
            await call.answer("✅ Подписка активна!")

        txt = f"<tg-emoji emoji-id='{ST_CHECK}'>✅</tg-emoji> <b>Бесплатные товары:</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Индикация талисманов", callback_data="show_free_ind", icon_custom_emoji_id=ST_IND)],
            [InlineKeyboardButton(text="Ресурс-паки", callback_data="show_free_rp", icon_custom_emoji_id=ST_STAR)],
            [InlineKeyboardButton(text="Назад", callback_data="shop_main", icon_custom_emoji_id=ST_BACK)]
        ])
        await force_media(call, "logo.jpg", txt, kb)


@dp.callback_query(F.data == "show_free_ind")
async def show_free_ind(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Забрать", callback_data="get_free_ind_link", icon_custom_emoji_id=ST_CHECK)],
        [InlineKeyboardButton(text="Назад", callback_data="free_menu", icon_custom_emoji_id=ST_BACK)]
    ])
    await force_media(call, "freeind.jpg", "", kb)


@dp.callback_query(F.data == "show_free_rp")
async def show_free_rp_selection(call: types.CallbackQuery):
    txt = f"<tg-emoji emoji-id='{ST_STAR}'>⭐️</tg-emoji> <b>Выберите версию РП:</b>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Рп Оникса", callback_data="sel_rp_onyx"),
            InlineKeyboardButton(text="Пвп Рп", callback_data="sel_rp_pvp")
        ],
        [InlineKeyboardButton(text="Назад", callback_data="free_menu", icon_custom_emoji_id=ST_BACK)]
    ])
    await force_media(call, "logo.jpg", txt, kb)


@dp.callback_query(F.data == "sel_rp_onyx")
async def show_onyx_rp(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Забрать", callback_data="get_free_rp_link", icon_custom_emoji_id=ST_CHECK)],
        [InlineKeyboardButton(text="Назад", callback_data="show_free_rp", icon_custom_emoji_id=ST_BACK)]
    ])
    await force_media(call, "freerp.jpg", "", kb)


@dp.callback_query(F.data == "sel_rp_pvp")
async def show_pvp_rp(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Забрать", callback_data="get_free_rp_pvp_link", icon_custom_emoji_id=ST_CHECK)],
        [InlineKeyboardButton(text="Назад", callback_data="show_free_rp", icon_custom_emoji_id=ST_BACK)]
    ])
    await force_media(call, "freerp1.jpg", "", kb)


@dp.callback_query(F.data.in_(["get_free_ind_link", "get_free_rp_link", "get_free_rp_pvp_link"]))
async def give_free_link_text(call: types.CallbackQuery):
    if call.data == "get_free_ind_link":
        code = "free_ind"
    elif call.data == "get_free_rp_link":
        code = "free_rp"
    else:
        code = "free_rp_pvp"

    item = get_item(code)
    if not item:
        return await call.answer("Ошибка базы.", show_alert=True)

    txt = (
        f"<tg-emoji emoji-id='{ST_CHECK}'>✅</tg-emoji> <b>Успешная выдача!</b>\n\n"
        f"<tg-emoji emoji-id='{item['st']}'>📦</tg-emoji> <b>Товар:</b> {item['name']}\n"
        f"<tg-emoji emoji-id='{ST_LINK}'>🔗</tg-emoji> <b>Ссылка:</b> <a href='{item['link']}'>Скачать</a>"
    )
    await call.message.answer(txt, parse_mode="HTML", disable_web_page_preview=True)
    await call.answer()


@dp.callback_query(F.data == "paid_menu")
async def paid_menu_handler(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Конфиги", callback_data="cat_cfgs", icon_custom_emoji_id=ST_CFG_BTN)],
        [InlineKeyboardButton(text="Назад", callback_data="shop_main", icon_custom_emoji_id=ST_BACK)]
    ])
    await force_media(call, "logo.jpg", f"<tg-emoji emoji-id='{ST_MONEY}'>💲</tg-emoji> <b>Выберите категорию:</b>", kb)


@dp.callback_query(F.data == "cat_cfgs")
async def cfgs_list(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="N-Client", callback_data="cat_nurs", icon_custom_emoji_id=ST_N_CLIENT)],
        [InlineKeyboardButton(text="Celestial", callback_data="cat_cel", icon_custom_emoji_id=ST_CEL)],
        [InlineKeyboardButton(text="Назад", callback_data="paid_menu", icon_custom_emoji_id=ST_BACK)]
    ])
    await force_media(call, "logo.jpg", f"<tg-emoji emoji-id='{ST_PIN}'>📌</tg-emoji> <b>Выберите чит:</b>", kb)


@dp.callback_query(F.data == "cat_nurs")
async def cat_nurs_handler(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Spookytime", callback_data="buy_item_ns_s")],
        [InlineKeyboardButton(text="Назад", callback_data="cat_cfgs", icon_custom_emoji_id=ST_BACK)]
    ])
    await force_media(call, "logo.jpg", f"<tg-emoji emoji-id='{ST_N_CLIENT}'>⚡️</tg-emoji> <b>N-Client</b>", kb)


@dp.callback_query(F.data == "cat_cel")
async def cat_cel_handler(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Funtime", callback_data="buy_item_cl_f")],
        [InlineKeyboardButton(text="Назад", callback_data="cat_cfgs", icon_custom_emoji_id=ST_BACK)]
    ])
    await force_media(call, "logo.jpg", f"<tg-emoji emoji-id='{ST_CEL}'>❄️</tg-emoji> <b>Celestial</b>", kb)


@dp.callback_query(F.data.startswith("buy_item_"))
async def item_payment_menu(call: types.CallbackQuery):
    item_code = call.data.replace("buy_item_", "")
    item = get_item(item_code)

    p_rub, p_st = item['p_rub'], item['p_st']
    promo = db_query("SELECT discount FROM user_active_promos WHERE user_id = ? AND item_id = ?", (call.from_user.id, item_code), fetch=True)
    promo_text = ""

    if promo:
        disc = promo[0][0]
        p_rub = int(p_rub * (1 - disc / 100))
        p_st = int(p_st * (1 - disc / 100))
        promo_text = f"\n<tg-emoji emoji-id='{ST_STAR}'>⭐️</tg-emoji> <b>Скидка {disc}%!</b>"

    txt = (
        f"<tg-emoji emoji-id='{item['st']}'>⚡️</tg-emoji> <b>Товар:</b> <b>{item['name']}</b>\n\n"
        f"<tg-emoji emoji-id='{ST_MONEY}'>💲</tg-emoji> <b>Цена: {p_rub} ₽ / {p_st} Звезд</b>{promo_text}\n\n"
        f"Выберите способ оплаты:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Crypto Bot", callback_data=f"pay_cry_{item_code}_{p_rub}"),
            InlineKeyboardButton(text="Звезды", callback_data=f"pay_str_{item_code}_{p_st}")
        ],
        [InlineKeyboardButton(text="Баланс бота", callback_data=f"pay_bal_{item_code}_{p_rub}")],
        [InlineKeyboardButton(text="Назад", callback_data="cat_cfgs", icon_custom_emoji_id=ST_BACK)]
    ])
    await force_media(call, "logo.jpg", txt, kb)


async def finalize_purchase(user_id, item_code):
    db_query("DELETE FROM user_active_promos WHERE user_id = ? AND item_id = ?", (user_id, item_code))


@dp.callback_query(F.data.startswith("pay_bal_"))
async def pay_balance(call: types.CallbackQuery):
    parts = call.data.split("_")
    item_code, price = f"{parts[2]}_{parts[3]}", int(parts[4])
    item = get_item(item_code)

    res = db_query("SELECT balance FROM users WHERE user_id = ?", (call.from_user.id,), fetch=True)

    if res[0][0] >= price:
        db_query("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, call.from_user.id))
        await finalize_purchase(call.from_user.id, item_code)

        txt = (
            f"<tg-emoji emoji-id='{ST_CHECK}'>✅</tg-emoji> <b>Покупка успешна!</b>\n\n"
            f"<tg-emoji emoji-id='{item['st']}'>📦</tg-emoji> <b>Товар:</b> {item['name']}\n"
            f"<tg-emoji emoji-id='{ST_LINK}'>🔗</tg-emoji> <b>Ссылка:</b> <a href='{item['link']}'>Скачать</a>"
        )
        await call.message.answer(txt, parse_mode="HTML", disable_web_page_preview=True)
        await bot.send_message(LOG_CHANNEL_ID, f"🛒 <b>Покупка (Баланс)</b>\nЮзер: @{call.from_user.username}\nТовар: {item['name']}", parse_mode="HTML")
    else:
        await call.answer("⚠️ Недостаточно средств!", show_alert=True)


@dp.callback_query(F.data.startswith("pay_cry_"))
async def pay_crypto(call: types.CallbackQuery):
    parts = call.data.split("_")
    item_code, price = f"{parts[2]}_{parts[3]}", int(parts[4])

    inv = await crypto.create_invoice(amount=price, fiat="RUB", currency_type="fiat")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {price} ₽", url=inv.bot_invoice_url)],
        [InlineKeyboardButton(text="Проверить", callback_data=f"chk_cry_{inv.invoice_id}_{item_code}")],
        [InlineKeyboardButton(text="Назад", callback_data=f"buy_item_{item_code}", icon_custom_emoji_id=ST_BACK)]
    ])
    await force_media(call, "logo.jpg", f"<b>Оплата через Crypto Bot</b>\nСумма: {price} ₽", kb)


@dp.callback_query(F.data.startswith("chk_cry_"))
async def check_crypto_pay(call: types.CallbackQuery):
    parts = call.data.split("_")
    inv_id, item_code = int(parts[2]), f"{parts[3]}_{parts[4]}"
    item = get_item(item_code)

    invs = await crypto.get_invoices(invoice_ids=[inv_id])
    if invs and invs[0].status == 'paid':
        await finalize_purchase(call.from_user.id, item_code)
        txt = (
            f"<tg-emoji emoji-id='{ST_CHECK}'>✅</tg-emoji> <b>Оплата прошла!</b>\n\n"
            f"<tg-emoji emoji-id='{item['st']}'>📦</tg-emoji> <b>Товар:</b> {item['name']}\n"
            f"<tg-emoji emoji-id='{ST_LINK}'>🔗</tg-emoji> <b>Ссылка:</b> <a href='{item['link']}'>Скачать</a>"
        )
        await call.message.answer(txt, parse_mode="HTML", disable_web_page_preview=True)
        await bot.send_message(LOG_CHANNEL_ID, f"🛒 <b>Покупка (Crypto)</b>\nЮзер: @{call.from_user.username}\nТовар: {item['name']}", parse_mode="HTML")
        await call.message.delete()
    else:
        await call.answer("⚠️ Оплата не найдена.", show_alert=True)


@dp.callback_query(F.data.startswith("pay_str_"))
async def pay_stars_init(call: types.CallbackQuery):
    parts = call.data.split("_")
    item_code, price = f"{parts[2]}_{parts[3]}", int(parts[4])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Я оплатил", callback_data=f"str_cnf_{item_code}", icon_custom_emoji_id=ST_CHECK)],
        [InlineKeyboardButton(text="Назад", callback_data=f"buy_item_{item_code}", icon_custom_emoji_id=ST_BACK)]
    ])
    txt = (
        f"<tg-emoji emoji-id='{ST_STAR}'>⭐️</tg-emoji> <b>Оплата Звездами</b>\n\n"
        f"Переведите <b>{price} звезд</b> пользователю <b>{OWNER_USER}</b>.\n"
        f"После перевода нажмите кнопку подтверждения."
    )
    await force_media(call, "logo.jpg", txt, kb)


@dp.callback_query(F.data.startswith("str_cnf_"))
async def stars_confirm_request(call: types.CallbackQuery):
    item_code = call.data.replace("str_cnf_", "")
    item = get_item(item_code)

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Выдать", callback_data=f"adm_gv_{call.from_user.id}_{item_code}"),
        InlineKeyboardButton(text="Отказать", callback_data=f"adm_dn_{call.from_user.id}")
    ]])
    await bot.send_message(
        LOG_CHANNEL_ID,
        f"<tg-emoji emoji-id='{ST_STAR}'>⭐️</tg-emoji> <b>Запрос Звезд!</b>\n"
        f"Юзер: @{call.from_user.username} (ID: <code>{call.from_user.id}</code>)\n"
        f"Товар: <b>{item['name']}</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await call.message.edit_caption(caption="<tg-emoji emoji-id='{ST_CHECK}'>✅</tg-emoji> <b>Заявка отправлена!</b>\nОжидайте выдачи.", parse_mode="HTML")


@dp.callback_query(F.data == "deposit_menu")
async def deposit_menu(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Crypto Bot", callback_data="dep_cry_start")],
        [InlineKeyboardButton(text="Назад", callback_data="profile", icon_custom_emoji_id=ST_BACK)]
    ])
    await force_media(call, "logo.jpg", "Выберите способ пополнения:", kb)


@dp.callback_query(F.data == "dep_cry_start")
async def dep_cry_input(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(Deposit.amount)
    await call.message.answer("Введите сумму пополнения (RUB):", reply_markup=cancel_kb())
    await call.answer()


@dp.message(Deposit.amount)
async def dep_cry_process(msg: types.Message, state: FSMContext):
    try:
        am = int(msg.text)
    except ValueError:
        return await msg.answer("Введите число.")

    await state.clear()
    inv = await crypto.create_invoice(amount=am, fiat="RUB", currency_type="fiat")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить", url=inv.bot_invoice_url)],
        [InlineKeyboardButton(text="Проверить", callback_data=f"dep_chk_{inv.invoice_id}_{am}")]
    ])
    await msg.answer(f"Пополнение на {am} ₽", reply_markup=kb)


@dp.callback_query(F.data.startswith("dep_chk_"))
async def dep_check(call: types.CallbackQuery):
    _, _, inv_id, am = call.data.split("_")
    invs = await crypto.get_invoices(invoice_ids=[int(inv_id)])

    if invs and invs[0].status == 'paid':
        db_query("UPDATE users SET balance = balance + ? WHERE user_id = ?", (float(am), call.from_user.id))
        await call.message.answer(f"✅ Баланс пополнен на {am} ₽")
        await call.message.delete()
    else:
        await call.answer("Не оплачено.", show_alert=True)


@dp.callback_query(F.data == "promo_activate")
async def promo_input(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserPromo.code)
    await call.message.answer("Введите промокод:", reply_markup=cancel_kb())


@dp.message(UserPromo.code)
async def promo_process(msg: types.Message, state: FSMContext):
    code = msg.text.strip()
    await state.clear()

    promo = db_query("SELECT item_id, discount, max_uses, uses_per_user, current_uses FROM promocodes WHERE code = ?", (code,), fetch=True)
    if not promo:
        return await msg.answer("⚠️ Промокод не найден.")

    item_id, discount, max_uses, uses_per_user, current_uses = promo[0]
    if current_uses >= max_uses:
        return await msg.answer("⚠️ Лимит исчерпан.")

    if item_id == 'balance':
        db_query("UPDATE promocodes SET current_uses = current_uses + 1 WHERE code = ?", (code,))
        db_query("UPDATE users SET balance = balance + ? WHERE user_id = ?", (discount, msg.from_user.id))
        await msg.answer(f"✅ Баланс пополнен на {discount} ₽")
    else:
        db_query("INSERT OR REPLACE INTO user_active_promos (user_id, item_id, promo_code, discount) VALUES (?, ?, ?, ?)",
                 (msg.from_user.id, item_id, code, discount))
        await msg.answer(f"✅ Скидка {discount}% активирована!")


@dp.callback_query(F.data == "cancel_state")
async def cancel_state(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Отменено.")


@dp.message(Command("op"))
async def cmd_op(msg: types.Message, command: CommandObject):
    if msg.from_user.id not in ADMIN_IDS:
        return
    if not command.args:
        return await msg.answer("Укажите @username")

    uname = command.args.replace("@", "")
    res = db_query("SELECT user_id FROM users WHERE username = ?", (uname,), fetch=True)

    if res:
        db_query("UPDATE users SET is_admin = 1 WHERE username = ?", (uname,))
        await msg.answer(f"✅ Пользователь @{uname} теперь админ.")
    else:
        await msg.answer("⚠️ Пользователь не найден в боте.")


@dp.message(Command("deop"))
async def cmd_deop(msg: types.Message, command: CommandObject):
    if msg.from_user.id not in ADMIN_IDS:
        return
    if not command.args:
        return await msg.answer("Укажите @username")

    uname = command.args.replace("@", "")
    db_query("UPDATE users SET is_admin = 0 WHERE username = ?", (uname,))
    await msg.answer(f"✅ Пользователь @{uname} больше не админ.")


@dp.message(Command("ban"))
async def cmd_ban(msg: types.Message, command: CommandObject):
    if not is_admin(msg.from_user.id):
        return
    if not command.args:
        return await msg.answer("Формат: /ban @username причина")

    args = command.args.split(" ", 1)
    uname = args[0].replace("@", "")

    res = db_query("SELECT is_admin, user_id FROM users WHERE username = ?", (uname,), fetch=True)
    if res:
        target_is_admin = res[0][0]
        target_id = res[0][1]
        if target_is_admin == 1 or target_id in ADMIN_IDS:
            return await msg.answer("⚠️ Нельзя забанить администратора.")

    reason = args[1] if len(args) > 1 else "Нарушение правил"
    db_query("UPDATE users SET is_banned = 1, ban_reason = ? WHERE username = ?", (reason, uname))
    await msg.answer(f"🚫 Пользователь @{uname} забанен.")


@dp.message(Command("razban"))
async def cmd_razban(msg: types.Message, command: CommandObject):
    if not is_admin(msg.from_user.id):
        return
    if not command.args:
        return await msg.answer("Формат: /razban @username")

    uname = command.args.replace("@", "")
    db_query("UPDATE users SET is_banned = 0 WHERE username = ?", (uname,))
    await msg.answer(f"✅ Пользователь @{uname} разбанен.")


@dp.message(Command("setbal"))
async def cmd_setbal(msg: types.Message, command: CommandObject):
    if not is_admin(msg.from_user.id):
        return
    try:
        args = command.args.split()
        target, amount = args[0], float(args[1])
        if target.isdigit():
            db_query("UPDATE users SET balance = ? WHERE user_id = ?", (amount, int(target)))
            await msg.answer(f"💰 Баланс ID <code>{target}</code> установлен: {amount}₽", parse_mode="HTML")
        else:
            uname = target.replace("@", "")
            db_query("UPDATE users SET balance = ? WHERE username = ?", (amount, uname))
            await msg.answer(f"💰 Баланс @{uname} установлен: {amount}₽")
    except Exception:
        await msg.answer("Формат: /setbal @username/ID сумма")


@dp.message(Command("setnur"))
async def cmd_setnur(msg: types.Message, command: CommandObject):
    if not is_admin(msg.from_user.id):
        return
    if not command.args:
        return await msg.answer("Формат: /setnur ссылка")

    link = command.args.strip()
    if not link.startswith("<"):
        final_link = f"<b><a href='{link}'>Товар</a></b>"
    else:
        final_link = link

    db_query("UPDATE product_data SET link = ? WHERE id = 'ns_s'", (final_link,))
    await msg.answer(f"✅ Ссылка на N-Client обновлена:\n{final_link}", parse_mode="HTML", disable_web_page_preview=True)


@dp.message(Command("setcel"))
async def cmd_setcel(msg: types.Message, command: CommandObject):
    if not is_admin(msg.from_user.id):
        return
    if not command.args:
        return await msg.answer("Формат: /setcel ссылка")

    link = command.args.strip()
    if not link.startswith("<"):
        final_link = f"<b><a href='{link}'>Товар</a></b>"
    else:
        final_link = link

    db_query("UPDATE product_data SET link = ? WHERE id = 'cl_f'", (final_link,))
    await msg.answer(f"✅ Ссылка на Celestial обновлена:\n{final_link}", parse_mode="HTML", disable_web_page_preview=True)


@dp.message(Command("list"))
async def cmd_list(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    total = db_query("SELECT COUNT(*) FROM users", fetch=True)[0][0]
    banned = db_query("SELECT COUNT(*) FROM users WHERE is_banned=1", fetch=True)[0][0]
    admins = db_query("SELECT COUNT(*) FROM users WHERE is_admin=1", fetch=True)[0][0]
    await msg.answer(f"📊 <b>Статистика:</b>\nВсего юзеров: {total}\nАдминов: {admins}\nЗабаненных: {banned}", parse_mode="HTML")


@dp.message(Command("kill"))
async def cmd_kill(msg: types.Message):
    if msg.from_user.id in ADMIN_IDS:
        await msg.answer("😵 Бот выключается...")
        sys.exit()


@dp.message(Command("panel"))
async def cmd_panel(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Товары", callback_data="adm_cat_main"),
            InlineKeyboardButton(text="Промокоды", callback_data="adm_promo_cat_main")
        ],
        [InlineKeyboardButton(text="Рассылка", callback_data="adm_say_info")]
    ])
    await msg.answer("Админ Панель:", reply_markup=kb)


@dp.callback_query(F.data == "adm_cat_main")
@dp.callback_query(F.data == "adm_promo_cat_main")
async def adm_cat_main(call: types.CallbackQuery):
    is_promo = "promo" in call.data
    prefix = "admpromo_" if is_promo else "adm_"

    buttons = [
        [InlineKeyboardButton(text="N-Client Spooky", callback_data=f"{prefix}item_ns_s")],
        [InlineKeyboardButton(text="Celestial Funtime", callback_data=f"{prefix}item_cl_f")]
    ]

    if not is_promo:
        buttons.append([
            InlineKeyboardButton(text="Беспл. Индикация", callback_data=f"{prefix}item_free_ind"),
            InlineKeyboardButton(text="Беспл. РП", callback_data=f"{prefix}item_free_rp")
        ])
        buttons.append([InlineKeyboardButton(text="Беспл. Пвп РП", callback_data=f"{prefix}item_free_rp_pvp")])

    if is_promo:
        buttons.append([InlineKeyboardButton(text="На баланс", callback_data="admpromo_item_balance")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await call.message.edit_text("Выберите товар:", reply_markup=kb)


@dp.callback_query(F.data.startswith("adm_item_"))
async def adm_edit_item(call: types.CallbackQuery):
    item_code = call.data.replace("adm_item_", "")
    item = get_item(item_code)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить цену", callback_data=f"edit_price_{item_code}")],
        [InlineKeyboardButton(text="Изменить ссылку", callback_data=f"edit_link_{item_code}")],
        [InlineKeyboardButton(text="Назад", callback_data="adm_cat_main")]
    ])
    txt = f"Товар: {item['name']}\nЦена: {item['p_rub']}р / {item['p_st']} звезд\nСсылка: {item['link']}"
    await call.message.edit_text(txt, reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data.startswith("edit_price_"))
async def adm_eprice(call: types.CallbackQuery, state: FSMContext):
    code = call.data.replace("edit_price_", "")
    await state.update_data(item_code=code)
    await call.message.answer("Введите цену RUB:STARS (пример: 50:45):", reply_markup=cancel_kb())
    await state.set_state(AdminEditProduct.price)


@dp.message(AdminEditProduct.price)
async def adm_save_price(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        r, s = map(int, msg.text.split(":"))
    except ValueError:
        return await msg.answer("Ошибка формата. Попробуйте еще раз.")

    db_query("UPDATE product_data SET price_rub = ?, price_st = ? WHERE id = ?", (r, s, data['item_code']))
    await msg.answer("Цена обновлена.")
    await state.clear()


@dp.callback_query(F.data.startswith("edit_link_"))
async def adm_elink(call: types.CallbackQuery, state: FSMContext):
    code = call.data.replace("edit_link_", "")
    await state.update_data(item_code=code)
    await call.message.answer("Введите новую ссылку:", reply_markup=cancel_kb())
    await state.set_state(AdminEditProduct.link)


@dp.message(AdminEditProduct.link)
async def adm_save_link(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    link = msg.text.strip()

    if data['item_code'].startswith("free_"):
        final_link = link
    else:
        if not link.startswith("<b>"):
            final_link = f"<b><a href='{link}'>Товар</a></b>"
        else:
            final_link = link

    db_query("UPDATE product_data SET link = ? WHERE id = ?", (final_link, data['item_code']))
    await msg.answer("Ссылка обновлена.")
    await state.clear()


@dp.callback_query(F.data.startswith("admpromo_item_"))
async def adm_promo_item(call: types.CallbackQuery, state: FSMContext):
    item_code = call.data.replace("admpromo_item_", "")
    await state.update_data(item_code=item_code)
    await call.message.answer("Введите код (название):", reply_markup=cancel_kb())
    await state.set_state(AdminPromo.code)


@dp.message(AdminPromo.code)
async def adm_promo_c(msg: types.Message, state: FSMContext):
    await state.update_data(code=msg.text)
    data = await state.get_data()
    txt = "Сумма пополнения (RUB):" if data['item_code'] == 'balance' else "Скидка (%):"
    await msg.answer(txt, reply_markup=cancel_kb())
    await state.set_state(AdminPromo.discount)


@dp.message(AdminPromo.discount)
async def adm_promo_d(msg: types.Message, state: FSMContext):
    await state.update_data(discount=int(msg.text))
    await msg.answer("Макс. кол-во использований всего:", reply_markup=cancel_kb())
    await state.set_state(AdminPromo.max_uses)


@dp.message(AdminPromo.max_uses)
async def adm_promo_m(msg: types.Message, state: FSMContext):
    await state.update_data(max_uses=int(msg.text))
    await msg.answer("Макс. использований на юзера:", reply_markup=cancel_kb())
    await state.set_state(AdminPromo.uses_per_user)


@dp.message(AdminPromo.uses_per_user)
async def adm_promo_u(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    db_query(
        "INSERT OR REPLACE INTO promocodes (code, item_id, discount, max_uses, uses_per_user) VALUES (?, ?, ?, ?, ?)",
        (data['code'], data['item_code'], data['discount'], data['max_uses'], int(msg.text))
    )
    await msg.answer(f"Промокод {data['code']} создан.")
    await state.clear()


@dp.callback_query(F.data == "adm_say_info")
async def adm_say_info(call: types.CallbackQuery):
    await call.message.answer("Используйте /say [текст/html] для рассылки всем юзерам. Прем. стикеры поддерживаются.")


@dp.message(Command("say"))
async def broadcast(msg: types.Message, command: CommandObject):
    if not is_admin(msg.from_user.id):
        return

    users = db_query("SELECT user_id FROM users", fetch=True)
    count = 0
    for u in users:
        try:
            await bot.send_message(u[0], command.args, parse_mode="HTML")
            count += 1
        except Exception:
            pass

    await msg.answer(f"Отправлено {count} юзерам.")


@dp.message(Command("tgk"))
async def cmd_tgk(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return

    html_text = msg.html_text
    if not html_text:
        return await msg.answer("⚠️ Ошибка! Введите текст.")

    content = html_text.replace("/tgk", "", 1).strip()
    if not content and not msg.photo and not msg.video and not msg.document and not msg.animation:
        return await msg.answer("⚠️ Ошибка! Пустое сообщение.")

    try:
        if msg.photo:
            await bot.send_photo(CHECK_CHANNEL_ID, photo=msg.photo[-1].file_id, caption=content, parse_mode="HTML")
        elif msg.video:
            await bot.send_video(CHECK_CHANNEL_ID, video=msg.video.file_id, caption=content, parse_mode="HTML")
        elif msg.document:
            await bot.send_document(CHECK_CHANNEL_ID, document=msg.document.file_id, caption=content, parse_mode="HTML")
        elif msg.animation:
            await bot.send_animation(CHECK_CHANNEL_ID, animation=msg.animation.file_id, caption=content, parse_mode="HTML")
        else:
            await bot.send_message(CHECK_CHANNEL_ID, text=content, parse_mode="HTML")

        await msg.answer("✅ Сообщение успешно отправлено в канал.")
    except Exception as e:
        await msg.answer(f"❌ Ошибка отправки: {e}")


@dp.callback_query(F.data.startswith("adm_gv_"))
async def adm_gv(call: types.CallbackQuery):
    parts = call.data.split("_")
    user_id = int(parts[2])
    item_code = f"{parts[3]}_{parts[4]}"
    item = get_item(item_code)

    await finalize_purchase(user_id, item_code)
    txt = (
        f"<tg-emoji emoji-id='{ST_CHECK}'>✅</tg-emoji> <b>Оплата звездами подтверждена!</b>\n\n"
        f"<tg-emoji emoji-id='{item['st']}'>📦</tg-emoji> <b>Товар:</b> {item['name']}\n"
        f"<tg-emoji emoji-id='{ST_LINK}'>🔗</tg-emoji> <b>Ссылка:</b> <a href='{item['link']}'>Скачать</a>"
    )
    await bot.send_message(user_id, txt, parse_mode="HTML", disable_web_page_preview=True)
    await call.message.edit_caption(caption="✅ Выдано", parse_mode="HTML")


@dp.callback_query(F.data.startswith("adm_dn_"))
async def adm_dn(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[2])
    await bot.send_message(user_id, "❌ <b>Оплата звездами отклонена.</b>", parse_mode="HTML")
    await call.message.edit_caption(caption="❌ Отказано", parse_mode="HTML")


async def main():
    global crypto
    init_db()
    crypto = AioCryptoPay(token=CRYPTO_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())