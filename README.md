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
- Quantity-based promo: minimal son, bepul delivery, bonus item
- Alembic migratsiyalar va Docker infra

## Run

1. `.env.example` dan `.env` yarating.
2. Servislarni ishga tushiring:

```bash
docker compose up --build
```

3. Migratsiyani qo'llang:

```bash
docker compose exec bot alembic upgrade head
```

4. Bot polling container ichida avtomatik ishga tushadi.

## Important Notes

- `ADMIN_IDS` ga admin Telegram ID larini kiriting.
- `ADMIN_GROUP_ID` ga buyurtmalar tushadigan guruh ID sini kiriting.
- Yangi schema `payments` jadvalini ishlatadi. Agar eski DB bo'lsa, clean database bilan qayta ko'tarish yoki alohida migration yozish kerak.
- `USE_REDIS=true` qilinsa FSM storage Redis orqali ishlaydi.
