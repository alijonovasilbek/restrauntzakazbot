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
