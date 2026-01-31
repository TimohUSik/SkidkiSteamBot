"""
Steam Discount Bot - Модуль работы со Steam API
Получение информации о скидках на игры
"""

import requests
import json
import os
from typing import Optional
import config


# Путь к файлу watchlist
WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "watchlist.json")

# Заголовки для запросов (чтобы Steam не блокировал)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


def get_game_details(app_id: int) -> Optional[dict]:
    """
    Получает детальную информацию об игре из Steam Store API
    Получает цены в UAH и RUB
    """
    url = "https://store.steampowered.com/api/appdetails"
    
    result = None
    
    # Получаем цены в гривнах (UAH)
    try:
        params_ua = {"appids": app_id, "cc": "ua", "l": "russian"}
        response_ua = requests.get(url, params=params_ua, headers=HEADERS, timeout=10)
        data_ua = response_ua.json()
        
        if str(app_id) in data_ua and data_ua[str(app_id)]["success"]:
            game_data = data_ua[str(app_id)]["data"]
            
            if "price_overview" not in game_data:
                return None
                
            price_ua = game_data["price_overview"]
            content_type = game_data.get("type", "game")
            
            # Базовые цены в гривнах
            original_uah = price_ua.get("initial", 0) / 100
            final_uah = price_ua.get("final", 0) / 100
            
            result = {
                "app_id": app_id,
                "name": game_data.get("name", "Неизвестно"),
                "original_price": original_uah,  # Временно UAH, заменим на RUB ниже если есть
                "final_price": final_uah,
                "discount_percent": price_ua.get("discount_percent", 0),
                "url": f"https://store.steampowered.com/app/{app_id}/",
                "type": content_type,
                "uah_original": original_uah,
                "uah_final": final_uah,
                "currency": "UAH"
            }
    except Exception as e:
        print(f"Ошибка UAH для app_id {app_id}: {e}")
        return None
    
    # Получаем цены в рублях (RUB) + наценка
    try:
        params_ru = {"appids": app_id, "cc": "ru", "l": "russian"}
        response_ru = requests.get(url, params=params_ru, headers=HEADERS, timeout=10)
        data_ru = response_ru.json()
        
        if str(app_id) in data_ru and data_ru[str(app_id)]["success"]:
            game_data_ru = data_ru[str(app_id)]["data"]
            if "price_overview" in game_data_ru:
                price_ru = game_data_ru["price_overview"]
                markup = getattr(config, 'PRICE_MARKUP', 1.10)
                
                rub_orig = price_ru.get("initial", 0) / 100 * markup
                rub_final = price_ru.get("final", 0) / 100 * markup
                
                result["rub_original"] = rub_orig
                result["rub_final"] = rub_final
                
                # Обновляем основные поля для фильтра (т.к. лимит 500 в конфиге - это рубли)
                result["original_price"] = rub_orig
                result["final_price"] = rub_final
                result["currency"] = "₽"
    except Exception as e:
        print(f"Ошибка RUB для app_id {app_id}: {e}")
        # Продолжаем без рублей (но тогда фильтр 500 отсечет дешевые игры в гривнах)
    
    return result


def get_featured_deals() -> list:
    """
    Получает список игр со скидками из нескольких источников
    
    Returns:
        Список игр со скидками
    """
    games = []
    app_ids = set()
    
    # === Источник 1: Featured Categories ===
    try:
        url = "https://store.steampowered.com/api/featuredcategories"
        params = {"cc": config.COUNTRY_CODE, "l": "russian"}
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Specials (распродажи)
        if "specials" in data and "items" in data["specials"]:
            for item in data["specials"]["items"]:
                if "id" in item:
                    app_ids.add(item["id"])
        
        # Top sellers со скидками
        if "top_sellers" in data and "items" in data["top_sellers"]:
            for item in data["top_sellers"]["items"]:
                if "id" in item and item.get("discount_percent", 0) > 0:
                    app_ids.add(item["id"])
                    
    except Exception as e:
        print(f"Ошибка featuredcategories: {e}")
    
    # === Источник 2: Search API с фильтром по скидкам ===
    try:
        url = "https://store.steampowered.com/api/storesearch/"
        params = {
            "term": "*",
            "l": "russian",
            "cc": config.COUNTRY_CODE,
        }
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if "items" in data:
                for item in data["items"]:
                    if "id" in item:
                        app_ids.add(item["id"])
    except Exception as e:
        print(f"Ошибка storesearch: {e}")
    
    # === Источник 3: Топ продаж ===
    try:
        # Популярные новинки
        url = "https://store.steampowered.com/api/featured"
        params = {"cc": config.COUNTRY_CODE, "l": "russian"}
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            
            for key in ["large_capsules", "featured_win"]:
                if key in data:
                    for item in data[key]:
                        if item.get("discount_percent", 0) > 0 and "id" in item:
                            app_ids.add(item["id"])
    except Exception as e:
        print(f"Ошибка featured: {e}")
    
    print(f"📊 Найдено {len(app_ids)} игр для анализа...")
    
    # Получаем детали для каждой игры
    count = 0
    for app_id in list(app_ids)[:100]:  # Лимит 100 игр
        game = get_game_details(app_id)
        if game and game["discount_percent"] > 0:
            games.append(game)
            count += 1
            if count % 10 == 0:
                print(f"  Обработано {count} игр...")
    
    print(f"✅ Получено {len(games)} игр со скидками")
    
    return games



def filter_games(games: list) -> tuple[list, list]:
    """
    Фильтрует игры по критериям из конфига
    
    Args:
        games: Список игр для фильтрации
        
    Returns:
        Кортеж (список игр, список DLC)
    """
    filtered_games = []
    filtered_dlc = []
    
    for game in games:
        # Проверяем оригинальную цену >= MIN_ORIGINAL_PRICE
        if game["original_price"] < config.MIN_ORIGINAL_PRICE:
            continue
            
        # Проверяем скидку >= MIN_DISCOUNT
        if game["discount_percent"] < config.MIN_DISCOUNT:
            continue
        
        # Разделяем игры и DLC
        if game.get("type", "game") == "game":
            filtered_games.append(game)
        elif game.get("type") == "dlc":
            filtered_dlc.append(game)
    
    # Сортируем по скидке (от большей к меньшей)
    filtered_games.sort(key=lambda x: x["discount_percent"], reverse=True)
    filtered_dlc.sort(key=lambda x: x["discount_percent"], reverse=True)
    
    return filtered_games, filtered_dlc


# === WATCHLIST ===

def load_data() -> dict:
    """Загружает весь файл данных"""
    if not os.path.exists(WATCHLIST_PATH):
        return {}
    try:
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_data(data: dict):
    """Сохраняет данные в файл"""
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user_watchlist(user_id: int) -> list:
    """Возвращает watchlist конкретного пользователя"""
    data = load_data()
    str_id = str(user_id)
    
    # Миграция старого формата (если есть)
    if "games" in data:
        # Если это старый формат, переносим данные текущему пользователю (первому, кто обратился)
        # или лучше привязать к config.CHAT_ID, если он задан
        old_games = data.pop("games")
        
        # Если ID совпадает с владельцем (из конфига) или просто переносим
        target_id = str(config.CHAT_ID) if config.CHAT_ID != "YOUR_CHAT_ID_HERE" else str_id
        
        if target_id not in data:
             data[target_id] = old_games
        else:
             data[target_id].extend(old_games)
             
        save_data(data)
        
        # Перезагружаем после миграции
        return data.get(str_id, [])
        
    return data.get(str_id, [])


def add_to_watchlist(user_id: int, app_id: int) -> tuple[bool, str]:
    """
    Добавляет игру в watchlist пользователя
    """
    data = load_data()
    str_id = str(user_id)
    
    if str_id not in data:
        data[str_id] = []
        
    user_list = data[str_id]
    
    # Проверяем, не добавлена ли уже
    for game in user_list:
        if game["app_id"] == app_id:
            return False, f"Игра уже в вашем списке: {game['name']}"
    
    # Получаем информацию об игре
    game_info = get_game_details(app_id)
    
    if not game_info:
        try:
            url = f"https://store.steampowered.com/api/appdetails"
            params = {"appids": app_id, "cc": "us"}
            response = requests.get(url, params=params, headers=HEADERS, timeout=10)
            json_data = response.json()
            
            if str(app_id) in json_data and json_data[str(app_id)]["success"]:
                game_data = json_data[str(app_id)]["data"]
                name = game_data.get("name", f"App {app_id}")
            else:
                return False, f"Игра с ID {app_id} не найдена в Steam"
        except Exception as e:
            print(f"Ошибка при добавлении {app_id}: {e}")
            return False, f"Не удалось получить информацию об игре {app_id}"
    else:
        name = game_info["name"]
    
    user_list.append({"app_id": app_id, "name": name})
    data[str_id] = user_list
    save_data(data)
    
    return True, f"✅ Добавлено: {name}"


def remove_from_watchlist(user_id: int, app_id: int) -> tuple[bool, str]:
    """Удаляет игру из watchlist пользователя"""
    data = load_data()
    str_id = str(user_id)
    
    if str_id not in data:
         return False, "Ваш список пуст"
         
    user_list = data[str_id]
    
    for i, game in enumerate(user_list):
        if game["app_id"] == app_id:
            removed = user_list.pop(i)
            data[str_id] = user_list
            save_data(data)
            return True, f"❌ Удалено: {removed['name']}"
    
    return False, f"Игра с ID {app_id} не найдена в списке"


def check_user_deals(user_id: int) -> list:
    """Проверяет скидки для конкретного пользователя"""
    user_list = get_user_watchlist(user_id)
    deals = []
    
    for game in user_list:
        info = get_game_details(game["app_id"])
        if info and info["discount_percent"] >= config.MIN_DISCOUNT:
            deals.append(info)
            
    return deals


def check_all_users_deals() -> dict:
    """
    Проверяет скидки для ВСЕХ пользователей.
    Возвращает словарь {user_id: [deals]}
    """
    data = load_data()
    all_deals = {}
    
    # Чтобы не делать одинаковые запросы для одинаковых игр разных юзеров,
    # можно сначала собрать все уникальные app_id, но пока сделаем просто.
    # Оптимизация: кэшировать результаты get_game_details
    
    game_cache = {} # app_id -> info
    
    for user_id, games in data.items():
        if user_id == "games": continue # Skip legacy key if exists
        
        user_deals = []
        for game in games:
            app_id = game["app_id"]
            
            if app_id in game_cache:
                info = game_cache[app_id]
            else:
                info = get_game_details(app_id)
                if info:
                    game_cache[app_id] = info
            
            if info and info["discount_percent"] >= config.MIN_DISCOUNT:
                user_deals.append(info)
        
        if user_deals:
            all_deals[user_id] = user_deals
            
    return all_deals


def format_game_message(game: dict) -> str:
    """Форматирует информацию об игре для вывода"""
    
    # Формируем строку с ценами
    prices = ""
    
    # Гривны
    if "uah_original" in game:
        prices += f"🇺🇦 ~~{game['uah_original']:.0f}~~ → *{game['uah_final']:.0f} UAH*\n"
    elif config.COUNTRY_CODE == "ua":
        prices += f"🇺🇦 ~~{game['original_price']:.0f}~~ → *{game['final_price']:.0f} UAH*\n"
        
    # Рубли (если есть)
    if "rub_original" in game:
        prices += f"🇷🇺 ~~{game['rub_original']:.0f}~~ → *{game['rub_final']:.0f} ₽*\n"
    elif config.COUNTRY_CODE == "ru":
         prices += f"🇷🇺 ~~{game['original_price']:.0f}~~ → *{game['final_price']:.0f} ₽*\n"

    return (
        f"🎮 *{game['name']}*\n"
        f"{prices}"
        f"🔥 Скидка: *-{game['discount_percent']}%*\n"
        f"🔗 {game['url']}"
    )


if __name__ == "__main__":
    # Тест модуля
    print("=== Steam Discount Bot - Тест ===\n")
    
    print("Получение списка скидок...")
    games = get_featured_deals()
    filtered = filter_games(games)
    
    print(f"\nНайдено {len(filtered)} игр по критериям:")
    print(f"(Цена ≥{config.MIN_ORIGINAL_PRICE} грн, Скидка ≥{config.MIN_DISCOUNT}%)\n")
    
    for game in filtered[:10]:  # Показываем первые 10
        print(f"🎮 {game['name']}")
        print(f"   {game['original_price']:.0f} → {game['final_price']:.0f} грн (-{game['discount_percent']}%)")
        print(f"   {game['url']}\n")
