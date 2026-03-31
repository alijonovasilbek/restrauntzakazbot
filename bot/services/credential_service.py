from __future__ import annotations

from bot.repositories.credential_repository import CredentialRepository


class CredentialService:
    def __init__(self, repo: CredentialRepository) -> None:
        self.repo = repo

    async def get_credentials(self) -> dict:
        record = await self.repo.get()
        return {
            "payment_card_number": str(record["payment_card_number"]),
            "payment_card_owner": str(record["payment_card_owner"]),
            "order_accept_until": str(record["order_accept_until"]),
            "delivery_start_time": str(record["delivery_start_time"]),
            "delivery_end_time": str(record["delivery_end_time"]),
        }
