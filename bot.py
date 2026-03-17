import asyncio
import requests

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "ТВОЙ_ТОКЕН"
ADMIN_ID = 123456789
BACKEND_URL = "http://localhost:8080"
CLICK_PAY_URL = "https://my.click.uz/services/pay"  # ссылка оплаты
SERVICE_ID = "12345"
MERCHANT_ID = "12345"
PRICE_PER_STAR = 300
# =====================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_data = {}

# ===== UI =====

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Купить Stars", callback_data="buy")],
        [InlineKeyboardButton(text="📦 Мои заказы", callback_data="orders")]
    ])


def stars_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="50 ⭐", callback_data="stars_50")],
        [InlineKeyboardButton(text="100 ⭐", callback_data="stars_100")],
        [InlineKeyboardButton(text="500 ⭐", callback_data="stars_500")],
        [InlineKeyboardButton(text="1000 ⭐", callback_data="stars_1000")]
    ])


# ===== СТАРТ =====
@dp.message(Command("start"))
async def start(msg: Message):
    text = (
        "💎 Добро пожаловать в магазин Stars\n\n"
        "⚡ Быстро\n"
        "🔒 Надёжно\n"
        "💰 Выгодно"
    )
    await msg.answer(text, reply_markup=main_menu())


# ===== ПОКУПКА =====
@dp.callback_query(F.data == "buy")
async def buy(callback):
    await callback.message.answer("Введи username (без @):")
    user_data[callback.from_user.id] = {}


@dp.message()
async def get_username(msg: Message):
    user_data[msg.from_user.id]["username"] = msg.text
    await msg.answer("Выбери пакет:", reply_markup=stars_menu())


# ===== ВЫБОР ПАКЕТА =====
@dp.callback_query(F.data.startswith("stars_"))
async def stars(callback):
    amount = int(callback.data.split("_")[1])
    username = user_data[callback.from_user.id]["username"]

    price = amount * PRICE_PER_STAR

    res = requests.post(f"{BACKEND_URL}/order", json={
        "user_id": callback.from_user.id,
        "username": username,
        "amount": amount,
        "price": price
    })

    order_id = res.json()["order_id"]

    pay_url = (
        f"{CLICK_PAY_URL}"
        f"?service_id={SERVICE_ID}"
        f"&merchant_id={MERCHANT_ID}"
        f"&amount={price}"
        f"&transaction_param={order_id}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=pay_url)],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_{order_id}")]
    ])

    await callback.message.answer(
        f"💰 Сумма: {price} сум\n\nПосле оплаты нажми кнопку ниже",
        reply_markup=kb
    )


# ===== ПРОВЕРКА ОПЛАТЫ =====
@dp.callback_query(F.data.startswith("check_"))
async def check_payment(callback):
    order_id = int(callback.data.split("_")[1])

    order = requests.get(f"{BACKEND_URL}/order/{order_id}").json()

    if order["status"] != "paid":
        await callback.message.answer("❌ Оплата не найдена")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправил", callback_data=f"ok_{order_id}"),
            InlineKeyboardButton(text="❌ Проблема", callback_data=f"no_{order_id}")
        ]
    ])

    await bot.send_message(
        ADMIN_ID,
        f"""
💸 Оплата получена!

@{order['username']}
{order['amount']} ⭐
{order['price']} сум
        """,
        reply_markup=kb
    )

    await callback.message.answer("✅ Оплата найдена, ожидайте выдачи")


# ===== АДМИН =====
@dp.callback_query(F.data.startswith("ok_"))
async def confirm(callback):
    order_id = int(callback.data.split("_")[1])

    requests.post(f"{BACKEND_URL}/order/{order_id}/confirm")

    await callback.message.answer("✅ Отправь stars вручную")


@dp.callback_query(F.data.startswith("no_"))
async def decline(callback):
    order_id = int(callback.data.split("_")[1])

    requests.post(f"{BACKEND_URL}/order/{order_id}/decline")

    await callback.message.answer("❌ Отменено")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
