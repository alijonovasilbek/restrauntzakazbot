from __future__ import annotations

from typing import TypedDict

from aiogram.fsm.context import FSMContext


class CartItem(TypedDict):
    food_id: int
    name: str
    price: int
    quantity: int


class CartService:
    STATE_KEY = "cart"
    MESSAGE_ID_KEY = "cart_message_id"
    CHAT_ID_KEY = "cart_chat_id"

    async def get_cart(self, state: FSMContext) -> dict[str, CartItem]:
        data = await state.get_data()
        return data.get(self.STATE_KEY, {})

    async def save_cart(self, state: FSMContext, cart: dict[str, CartItem]) -> None:
        await state.update_data(**{self.STATE_KEY: cart})

    async def add_item(self, state: FSMContext, food_id: int, name: str, price: int, quantity: int = 1) -> None:
        cart = await self.get_cart(state)
        key = str(food_id)
        existing = cart.get(key)
        if existing:
            existing["quantity"] += quantity
        else:
            cart[key] = {"food_id": food_id, "name": name, "price": price, "quantity": quantity}
        await self.save_cart(state, cart)

    async def change_quantity(self, state: FSMContext, food_id: int, delta: int) -> None:
        cart = await self.get_cart(state)
        key = str(food_id)
        if key not in cart:
            return
        cart[key]["quantity"] += delta
        if cart[key]["quantity"] <= 0:
            cart.pop(key, None)
        await self.save_cart(state, cart)

    async def clear(self, state: FSMContext) -> None:
        await state.update_data(**{self.STATE_KEY: {}})

    async def get_cart_message_meta(self, state: FSMContext) -> tuple[int | None, int | None]:
        data = await state.get_data()
        return data.get(self.CHAT_ID_KEY), data.get(self.MESSAGE_ID_KEY)

    async def set_cart_message_meta(self, state: FSMContext, chat_id: int, message_id: int) -> None:
        await state.update_data(**{self.CHAT_ID_KEY: chat_id, self.MESSAGE_ID_KEY: message_id})

    async def clear_cart_message_meta(self, state: FSMContext) -> None:
        await state.update_data(**{self.CHAT_ID_KEY: None, self.MESSAGE_ID_KEY: None})
