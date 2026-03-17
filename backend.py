from fastapi import FastAPI, Request
from pydantic import BaseModel
import hashlib
import os
import psycopg2

app = FastAPI()

# ===== НАСТРОЙКИ =====
CLICK_SECRET_KEY = os.environ.get("CLICK_SECRET_KEY")
CLICK_SERVICE_ID = os.environ.get("SERVICE_ID")
DATABASE_URL = os.environ.get("DATABASE_URL")
# =====================

# ===== DB INIT =====
conn = None
cur = None

if DATABASE_URL:
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            username TEXT,
            amount INT,
            price INT,
            status TEXT
        )
        """)
        conn.commit()

        print("✅ PostgreSQL подключен")

    except Exception as e:
        print("❌ Ошибка подключения к БД:", e)
        conn = None
        cur = None

# ===== FALLBACK (если нет БД) =====
orders = []
order_id_counter = 1


class OrderCreate(BaseModel):
    user_id: int
    username: str
    amount: int
    price: int


# ===================== ЗАКАЗЫ =====================

@app.post("/order")
def create_order(data: OrderCreate):
    global order_id_counter

    # ===== если есть БД =====
    if cur:
        cur.execute(
            "INSERT INTO orders (user_id, username, amount, price, status) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (data.user_id, data.username, data.amount, data.price, "pending")
        )
        order_id = cur.fetchone()[0]
        conn.commit()

        return {"order_id": order_id}

    # ===== fallback =====
    order = data.dict()
    order["id"] = order_id_counter
    order["status"] = "pending"

    orders.append(order)
    order_id_counter += 1

    return {"order_id": order["id"]}


@app.get("/order/{order_id}")
def get_order(order_id: int):

    if cur:
        cur.execute("SELECT * FROM orders WHERE id=%s", (order_id,))
        row = cur.fetchone()

        if not row:
            return {}

        return {
            "id": row[0],
            "user_id": row[1],
            "username": row[2],
            "amount": row[3],
            "price": row[4],
            "status": row[5]
        }

    # fallback
    for o in orders:
        if o["id"] == order_id:
            return o


@app.post("/order/{order_id}/confirm")
def confirm(order_id: int):

    if cur:
        cur.execute("UPDATE orders SET status='confirmed' WHERE id=%s", (order_id,))
        conn.commit()
        return {"ok": True}

    for o in orders:
        if o["id"] == order_id:
            o["status"] = "confirmed"
            return {"ok": True}


@app.post("/order/{order_id}/decline")
def decline(order_id: int):

    if cur:
        cur.execute("UPDATE orders SET status='declined' WHERE id=%s", (order_id,))
        conn.commit()
        return {"ok": True}

    for o in orders:
        if o["id"] == order_id:
            o["status"] = "declined"
            return {"ok": True}


# ===================== CLICK API =====================

def check_signature(data: dict):
    sign_string = (
        str(data.get("click_trans_id", "")) +
        str(data.get("service_id", "")) +
        str(CLICK_SECRET_KEY) +
        str(data.get("merchant_trans_id", "")) +
        str(data.get("amount", "")) +
        str(data.get("action", "")) +
        str(data.get("sign_time", ""))
    )

    sign = hashlib.md5(sign_string.encode()).hexdigest()
    return sign == data.get("sign_string")


@app.post("/click")
async def click_webhook(request: Request):
    data = await request.json()

    # 👉 для теста можно временно отключить
    # if not check_signature(data):
    #     return {"error": -1, "error_note": "SIGN ERROR"}

    order_id = int(data["merchant_trans_id"])
    action = int(data["action"])

    # ===== если БД =====
    if cur:
        if action == 0:
            return {
                "error": 0,
                "merchant_prepare_id": order_id
            }

        elif action == 1:
            cur.execute("UPDATE orders SET status='paid' WHERE id=%s", (order_id,))
            conn.commit()

            return {
                "error": 0,
                "merchant_confirm_id": order_id
            }

    # ===== fallback =====
    order = None
    for o in orders:
        if o["id"] == order_id:
            order = o
            break

    if not order:
        return {"error": -5, "error_note": "ORDER NOT FOUND"}

    if action == 0:
        return {
            "error": 0,
            "merchant_prepare_id": order_id
        }

    elif action == 1:
        order["status"] = "paid"

        return {
            "error": 0,
            "merchant_confirm_id": order_id
        }


# ===================== СТАТИСТИКА (задел) =====================

@app.get("/stats")
def stats():
    if cur:
        cur.execute("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders WHERE status='confirmed'")
        count, total = cur.fetchone()

        return {
            "orders": count,
            "revenue": total
        }

    return {"orders": len(orders), "revenue": 0}


# ===================== RUN =====================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
