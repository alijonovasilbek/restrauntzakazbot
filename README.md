# Restaurant Telegram Bot

Production-ready Telegram food ordering bot built with `aiogram`, `SQLAlchemy Core`, `PostgreSQL`, `Alembic`, and Docker.

## Features

- `/start` orqali foydalanuvchini ro'yxatdan o'tkazish
- Bugungi menyu, stock rezervi va pagination
- Savat, checkout, telefon va lokatsiya oqimi
- Karta raqamiga to'lov va chekni rasm/PDF yuborish
- Receipt fayllarini alohida `payments` jadvalida saqlash
- Admin group orqali accept/reject moderation
- Admin panel orqali ovqatlar, aksiyalar va broadcast
- Mijoz va admin uchun FastAPI asosidagi webapp
- Quantity-based promo: minimal son, bepul delivery, bonus item
- Alembic migratsiyalar va Docker infra

## Run

1. `.env.example` dan `.env` yarating.
2. Servislarni ishga tushiring:

```bash
docker compose up --build
```

3. Bot container start paytida migratsiyani avtomatik qo'llaydi va keyin polling boshlanadi.
4. Webapp quyidagi URL larda ochiladi:

```text
http://localhost:8000/web/user
http://localhost:8000/web/admin
```

## Important Notes

- `ADMIN_IDS` ga admin Telegram ID larini kiriting.
- `ADMIN_GROUP_ID` ga buyurtmalar tushadigan guruh ID sini kiriting.
- Webapp hozir minimal `telegram_id` asosida ishlaydi. Production uchun Telegram WebApp `initData` verifikatsiyasini qo'shish tavsiya qilinadi.
- Telegram ichida `WebApp` tugma chiqishi uchun `.env` da `WEBAPP_BASE_URL` ni public `https` URL ga sozlash kerak.
- Yangi schema `payments` jadvalini ishlatadi. Agar eski DB bo'lsa, clean database bilan qayta ko'tarish yoki alohida migration yozish kerak.
- `USE_REDIS=true` qilinsa FSM storage Redis orqali ishlaydi.
