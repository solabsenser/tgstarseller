from fastapi import FastAPI, Request
from pydantic import BaseModel
import hashlib
import time
import os
app = FastAPI()

# ===== НАСТРОЙКИ =====
CLICK_SECRET_KEY = os.environ.get("CLICK_SECRET_KEY")
CLICK_SERVICE_ID = os.environ.get("SERVICE_ID")
# =====================

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

    order = data.dict()
    order["id"] = order_id_counter
    order["status"] = "pending"

    orders.append(order)
    order_id_counter += 1

    return {"order_id": order["id"]}


@app.get("/order/{order_id}")
def get_order(order_id: int):
    for o in orders:
        if o["id"] == order_id:
            return o


@app.post("/order/{order_id}/confirm")
def confirm(order_id: int):
    for o in orders:
        if o["id"] == order_id:
            o["status"] = "confirmed"
            return {"ok": True}


@app.post("/order/{order_id}/decline")
def decline(order_id: int):
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

    if not check_signature(data):
        return {"error": -1, "error_note": "SIGN ERROR"}

    order_id = int(data["merchant_trans_id"])

    order = None
    for o in orders:
        if o["id"] == order_id:
            order = o
            break

    if not order:
        return {"error": -5, "error_note": "ORDER NOT FOUND"}

    action = int(data["action"])

    # 0 = prepare, 1 = complete
    if action == 0:
        return {
            "error": 0,
            "error_note": "Success",
            "click_trans_id": data["click_trans_id"],
            "merchant_trans_id": order_id,
            "merchant_prepare_id": order_id
        }

    elif action == 1:
        order["status"] = "paid"

        return {
            "error": 0,
            "error_note": "Success",
            "click_trans_id": data["click_trans_id"],
            "merchant_trans_id": order_id,
            "merchant_confirm_id": order_id
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
