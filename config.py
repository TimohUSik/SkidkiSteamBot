# Конфигурация Steam Discount Bot
import os

# === TELEGRAM ===
# На Railway используйте переменные окружения!
# Локально можно вписать значения напрямую

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7830591298:AAH_fCh0HamT7dbG5bFcvyTJOfz6jTa81vI")
CHAT_ID = os.getenv("CHAT_ID", "5294292729")

# === ФИЛЬТРЫ ===
# Минимальная оригинальная цена игры (в рублях)
MIN_ORIGINAL_PRICE = int(os.getenv("MIN_ORIGINAL_PRICE", "500"))

# Минимальный процент скидки
MIN_DISCOUNT = int(os.getenv("MIN_DISCOUNT", "50"))

# === STEAM ===
# Код страны для получения цен в рублях
COUNTRY_CODE = os.getenv("COUNTRY_CODE", "ru")

# Наценка Steam для России (1.10 = +10%)
PRICE_MARKUP = float(os.getenv("PRICE_MARKUP", "1.10"))

# Интервал проверки скидок (в секундах)
# 3600 = 1 час
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "3600"))
