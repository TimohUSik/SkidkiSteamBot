# Конфигурация Steam Discount Bot
import os

# === TELEGRAM ===
# На Railway используйте переменные окружения!
# Локально можно вписать значения напрямую

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8433499477:AAFbv5nNgCNETSiX1ur8wQBAr6b2GK6sP3s")
CHAT_ID = os.getenv("CHAT_ID", "5294292729")

# === ФИЛЬТРЫ ===
# Минимальная оригинальная цена игры (в гривнах)
MIN_ORIGINAL_PRICE = int(os.getenv("MIN_ORIGINAL_PRICE", "100"))

# Минимальный процент скидки
MIN_DISCOUNT = int(os.getenv("MIN_DISCOUNT", "60"))

# === STEAM ===
# Код страны для получения цен в гривнах
COUNTRY_CODE = os.getenv("COUNTRY_CODE", "ua")

# Интервал проверки скидок (в секундах)
# 3600 = 1 час
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "3600"))
