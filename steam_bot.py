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
    Получает цены в UAH и RUB
    """
    url = "https://store.steampowered.com/api/appdetails"
    
    result = None
    
    # Получаем цены в гривнах (UAH)
    try:
        params_ua = {"appids": app_id, "cc": "ua", "l": "russian"}
        response_ua = requests.get(url, params=params_ua, timeout=10)
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
        response_ru = requests.get(url, params=params_ru, timeout=10)
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
        response = requests.get(url, params=params, timeout=15)
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
        response = requests.get(url, params=params, timeout=15)
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
        response = requests.get(url, params=params, timeout=15)
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
        # Если не удалось получить детальную инфо (например, нет цены или блок региона),
        # пробуем получить хотя бы название через нейтральный регион (US)
        try:
            url = f"https://store.steampowered.com/api/appdetails"
            params = {"appids": app_id, "cc": "us"}  # Используем US чтобы обойти блокировки
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if str(app_id) in data and data[str(app_id)]["success"]:
                game_data = data[str(app_id)]["data"]
                name = game_data.get("name", f"App {app_id}")
            else:
                return False, f"Игра с ID {app_id} не найдена в Steam"
        except Exception as e:
            print(f"Ошибка при добавлении {app_id}: {e}")
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
