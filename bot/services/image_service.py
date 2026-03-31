from __future__ import annotations

from io import BytesIO

from aiogram import Bot
from aiogram.types import BufferedInputFile
from PIL import Image, ImageFilter, ImageOps


class ImageService:
    SIZE = (1080, 1080)

    async def normalize_from_file_id(self, bot: Bot, file_id: str) -> BufferedInputFile:
        telegram_file = await bot.get_file(file_id)
        source = BytesIO()
        await bot.download_file(telegram_file.file_path, destination=source)
        source.seek(0)
        image_bytes = self._normalize_image_bytes(source.read())
        return BufferedInputFile(image_bytes, filename="food.jpg")

    async def normalize_and_store(self, bot: Bot, chat_id: int, file_id: str) -> str:
        normalized = await self.normalize_from_file_id(bot, file_id)
        temp_message = await bot.send_photo(chat_id=chat_id, photo=normalized)
        normalized_file_id = temp_message.photo[-1].file_id
        await bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
        return normalized_file_id

    def _normalize_image_bytes(self, payload: bytes) -> bytes:
        with Image.open(BytesIO(payload)) as original:
            image = ImageOps.exif_transpose(original).convert("RGB")
            background = ImageOps.fit(image, self.SIZE, method=Image.Resampling.LANCZOS)
            background = background.filter(ImageFilter.GaussianBlur(radius=24))
            foreground = ImageOps.contain(image, self.SIZE, method=Image.Resampling.LANCZOS)

            canvas = background.copy()
            offset = (
                (self.SIZE[0] - foreground.width) // 2,
                (self.SIZE[1] - foreground.height) // 2,
            )
            canvas.paste(foreground, offset)

            output = BytesIO()
            canvas.save(output, format="JPEG", quality=92, optimize=True)
            return output.getvalue()
