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


def get_game_details(app_id: int) -> Optional[dict]:
    """
    Получает детальную информацию об игре из Steam Store API
    
    Args:
        app_id: Steam App ID игры
        
    Returns:
        Словарь с информацией об игре или None при ошибке
    """
    url = f"https://store.steampowered.com/api/appdetails"
    params = {
        "appids": app_id,
        "cc": config.COUNTRY_CODE,
        "l": "russian"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if str(app_id) in data and data[str(app_id)]["success"]:
            game_data = data[str(app_id)]["data"]
            
            # Проверяем наличие информации о цене
            if "price_overview" not in game_data:
                return None
                
            price_info = game_data["price_overview"]
            
            return {
                "app_id": app_id,
                "name": game_data.get("name", "Неизвестно"),
                "original_price": price_info.get("initial", 0) / 100,  # Конвертируем копейки в гривны
                "final_price": price_info.get("final", 0) / 100,
                "discount_percent": price_info.get("discount_percent", 0),
                "currency": price_info.get("currency", "UAH"),
                "url": f"https://store.steampowered.com/app/{app_id}/"
            }
    except Exception as e:
        print(f"Ошибка при получении данных для app_id {app_id}: {e}")
    
    return None


def get_featured_deals() -> list:
    """
    Получает список рекомендуемых игр со скидками
    
    Returns:
        Список игр со скидками
    """
    url = "https://store.steampowered.com/api/featuredcategories"
    params = {
        "cc": config.COUNTRY_CODE,
        "l": "russian"
    }
    
    games = []
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Собираем app_ids из разных категорий
        app_ids = set()
        
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
                    
        print(f"Найдено {len(app_ids)} игр со скидками для анализа...")
        
        # Получаем детали для каждой игры
        for app_id in app_ids:
            game = get_game_details(app_id)
            if game:
                games.append(game)
                
    except Exception as e:
        print(f"Ошибка при получении списка скидок: {e}")
    
    return games


def filter_games(games: list) -> list:
    """
    Фильтрует игры по критериям из конфига
    
    Args:
        games: Список игр для фильтрации
        
    Returns:
        Отфильтрованный список игр
    """
    filtered = []
    
    for game in games:
        # Проверяем оригинальную цену >= MIN_ORIGINAL_PRICE
        if game["original_price"] < config.MIN_ORIGINAL_PRICE:
            continue
            
        # Проверяем скидку >= MIN_DISCOUNT
        if game["discount_percent"] < config.MIN_DISCOUNT:
            continue
            
        filtered.append(game)
    
    # Сортируем по скидке (от большей к меньшей)
    filtered.sort(key=lambda x: x["discount_percent"], reverse=True)
    
    return filtered


# === WATCHLIST ===

def load_watchlist() -> list:
    """Загружает список отслеживаемых игр"""
    try:
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("games", [])
    except:
        return []


def save_watchlist(games: list):
    """Сохраняет список отслеживаемых игр"""
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump({"games": games}, f, ensure_ascii=False, indent=2)


def add_to_watchlist(app_id: int) -> tuple[bool, str]:
    """
    Добавляет игру в watchlist
    
    Returns:
        (успех, сообщение)
    """
    watchlist = load_watchlist()
    
    # Проверяем, не добавлена ли уже
    for game in watchlist:
        if game["app_id"] == app_id:
            return False, f"Игра уже в списке: {game['name']}"
    
    # Получаем информацию об игре
    game_info = get_game_details(app_id)
    
    if not game_info:
        # Пробуем получить хотя бы название
        try:
            url = f"https://store.steampowered.com/api/appdetails"
            params = {"appids": app_id, "cc": config.COUNTRY_CODE}
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if str(app_id) in data and data[str(app_id)]["success"]:
                name = data[str(app_id)]["data"].get("name", f"App {app_id}")
            else:
                return False, f"Игра с ID {app_id} не найдена в Steam"
        except:
            return False, f"Не удалось получить информацию об игре {app_id}"
    else:
        name = game_info["name"]
    
    watchlist.append({"app_id": app_id, "name": name})
    save_watchlist(watchlist)
    
    return True, f"✅ Добавлено: {name}"


def remove_from_watchlist(app_id: int) -> tuple[bool, str]:
    """Удаляет игру из watchlist"""
    watchlist = load_watchlist()
    
    for i, game in enumerate(watchlist):
        if game["app_id"] == app_id:
            removed = watchlist.pop(i)
            save_watchlist(watchlist)
            return True, f"❌ Удалено: {removed['name']}"
    
    return False, f"Игра с ID {app_id} не найдена в списке"


def check_watchlist_deals() -> list:
    """
    Проверяет скидки на игры из watchlist
    
    Returns:
        Список игр из watchlist со скидками, соответствующими критериям
    """
    watchlist = load_watchlist()
    deals = []
    
    for game in watchlist:
        info = get_game_details(game["app_id"])
        if info and info["discount_percent"] >= config.MIN_DISCOUNT:
            deals.append(info)
    
    return deals


def format_game_message(game: dict) -> str:
    """Форматирует информацию об игре для вывода"""
    return (
        f"🎮 *{game['name']}*\n"
        f"💰 ~~{game['original_price']:.0f}~~ → *{game['final_price']:.0f} {game['currency']}*\n"
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
