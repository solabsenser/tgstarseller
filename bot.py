import asyncio
import requests
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
BACKEND_URL = os.environ.get("BACKEND_URL")

CLICK_PAY_URL = os.environ.get("CLICK_PAY_URL")
SERVICE_ID = os.environ.get("SERVICE_ID")
MERCHANT_ID = os.environ.get("MERCHANT_ID")

PRICE_PER_STAR = int(os.environ.get("PRICE_PER_STAR", 300))
# =====================

# защита от пустых env
if not BACKEND_URL:
    raise ValueError("BACKEND_URL не задан")

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
        "💎 <b>Магазин Telegram Stars</b>\n\n"
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


# ===== ВЫБОР ПАКЕТА (ПОДТВЕРЖДЕНИЕ) =====
@dp.callback_query(F.data.startswith("stars_"))
async def stars(callback):
    amount = int(callback.data.split("_")[1])
    username = user_data[callback.from_user.id]["username"]

    price = amount * PRICE_PER_STAR

    # сохраняем
    user_data[callback.from_user.id]["amount"] = amount
    user_data[callback.from_user.id]["price"] = price

    text = (
        f"💎 <b>Подтверждение заказа</b>\n\n"
        f"👤 Username: @{username}\n"
        f"⭐ Stars: {amount}\n"
        f"💰 Сумма: {price} сум\n\n"
        f"Выберите способ оплаты:"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Click", callback_data="pay_click")],
        [InlineKeyboardButton(text="💳 Payme", callback_data="pay_payme")],
        [InlineKeyboardButton(text="💳 Uzum", callback_data="pay_uzum")]
    ])

    await callback.message.answer(text, reply_markup=kb)


# ===== CLICK =====
@dp.callback_query(F.data == "pay_click")
async def pay_click(callback):
    data = user_data.get(callback.from_user.id)

    if not data:
        await callback.message.answer("Ошибка данных")
        return

    try:
        res = requests.post(f"{BACKEND_URL}/order", json={
            "user_id": callback.from_user.id,
            "username": data["username"],
            "amount": data["amount"],
            "price": data["price"]
        })

        if res.status_code != 200:
            await callback.message.answer("❌ Ошибка сервера")
            return

        order_id = res.json()["order_id"]

    except Exception:
        await callback.message.answer("❌ Ошибка подключения")
        return

    pay_url = (
        f"{CLICK_PAY_URL}"
        f"?service_id={SERVICE_ID}"
        f"&merchant_id={MERCHANT_ID}"
        f"&amount={data['price']}"
        f"&transaction_param={order_id}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", url=pay_url)],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_{order_id}")]
    ])

    await callback.message.answer(
        "Нажмите кнопку ниже для оплаты:",
        reply_markup=kb
    )


# ===== PAYME =====
@dp.callback_query(F.data == "pay_payme")
async def pay_payme(callback):
    await callback.message.answer(
        "💳 Payme\n\nПереведите на карту:\n8600 **** **** 1234\n\nПосле оплаты нажмите 'Проверить'"
    )


# ===== UZUM =====
@dp.callback_query(F.data == "pay_uzum")
async def pay_uzum(callback):
    await callback.message.answer(
        "💳 Uzum\n\nПереведите по номеру:\n+99890XXXXXXX\n\nПосле оплаты нажмите 'Проверить'"
    )


# ===== ПРОВЕРКА ОПЛАТЫ =====
@dp.callback_query(F.data.startswith("check_"))
async def check_payment(callback):
    order_id = int(callback.data.split("_")[1])

    try:
        res = requests.get(f"{BACKEND_URL}/order/{order_id}")

        if res.status_code != 200:
            await callback.message.answer("❌ Ошибка сервера")
            return

        order = res.json()

    except:
        await callback.message.answer("❌ Ошибка подключения")
        return

    if order.get("status") != "paid":
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
💸 ОПЛАТА ПОЛУЧЕНА

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


# ===== RUN =====
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
