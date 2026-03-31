from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminFoodStates(StatesGroup):
    waiting_name = State()
    waiting_image = State()
    waiting_price = State()
    waiting_quantity = State()
    waiting_description = State()
    waiting_edit_value = State()


class AdminPromotionStates(StatesGroup):
    waiting_name = State()
    waiting_type = State()
    waiting_min_quantity = State()
    waiting_free_delivery = State()
    waiting_bonus_item = State()
    waiting_min_total = State()
    waiting_config = State()


class AdminCredentialStates(StatesGroup):
    waiting_value = State()


class CheckoutStates(StatesGroup):
    waiting_phone = State()
    waiting_location = State()
    waiting_receipt = State()
