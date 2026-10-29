"""Loyiha sozlamalari. .env faylidan o'qiladi."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Telegram
    bot_token: str
    admin_ids: str = ""  # "111,222"

    # Narx
    price_per_star: int = 200
    min_stars: int = 50
    max_stars: int = 100_000

    # Referal
    referral_bonus_percent: int = 5

    # Click
    click_service_id: str = ""
    click_merchant_id: str = ""
    click_secret_key: str = ""
    click_merchant_user_id: str = ""

    # Payme
    payme_merchant_id: str = ""
    payme_key: str = ""

    # Webhook server
    webhook_port: int = 8080

    # Fragment / Stars yetkazish
    ton_wallet_mnemonic: str = ""      # TON hamyon seed (12/24 so'z) — to'lov shundan
    ton_api_key: str = ""
    fragment_mode: str = "manual"      # manual | fragment

    # Fragment cookie'lari (fragment.com'ga login qilgach brauzerdan olinadi)
    fragment_stel_token: str = ""
    fragment_stel_ssid: str = ""
    fragment_stel_dt: str = ""
    fragment_stel_ton_token: str = ""

    # Fragment to'lov valyutasi: ton | usdt (hamyondan nima yechiladi)
    fragment_pay_currency: str = "ton"

    # TON to'lov (qabul qilish)
    ton_wallet_address: str = ""      # to'lovlar keladigan hamyon manzili
    usd_uzs_rate: float = 12800.0     # 1 USD = ? so'm (TON kursini hisoblash uchun)
    ton_uzs_fallback: float = 42000.0 # API ishlamasa, 1 TON = ? so'm
    ton_check_minutes: int = 30       # TON to'lovni kutish vaqti (daqiqa)

    @property
    def admin_id_list(self) -> list[int]:
        return [int(x) for x in self.admin_ids.split(",") if x.strip()]


settings = Settings()
