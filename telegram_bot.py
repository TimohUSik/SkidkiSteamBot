"""
Steam Discount Bot - Telegram бот
Уведомления о скидках в Steam
"""

import asyncio
import logging
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from telegram.constants import ParseMode

import config
import steam_bot

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Храним уже отправленные уведомления (чтобы не спамить)
notified_deals = set()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    welcome_text = (
        "🎮 *Steam Discount Bot*\n\n"
        "Я помогу найти выгодные скидки в Steam!\n\n"
        f"📋 *Текущие фильтры:*\n"
        f"• Базовая цена: ≥{config.MIN_ORIGINAL_PRICE} грн\n"
        f"• Скидка: ≥{config.MIN_DISCOUNT}%\n\n"
        "Воспользуйтесь меню ниже 👇"
    )
    
    # Создаем клавиатуру меню
    keyboard = [
        [KeyboardButton("🔍 Проверить скидки"), KeyboardButton("📋 Мой список")],
        [KeyboardButton("ℹ️ Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = (
        "📖 *Как пользоваться ботом:*\n\n"
        "*1. Найти App ID игры:*\n"
        "Откройте игру в Steam, в URL будет:\n"
        "`store.steampowered.com/app/1245620/`\n"
        "App ID = `1245620`\n\n"
        "*2. Добавить в отслеживание:*\n"
        "`/add 1245620`\n\n"
        "*3. Проверить скидки:*\n"
        "`/check` - покажет все выгодные скидки\n\n"
        "*4. Автоуведомления:*\n"
        "Бот сам пришлёт уведомление, когда на игру из вашего списка будет скидка!"
    )
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def check_deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /check - проверить скидки"""
    await update.message.reply_text("🔍 Ищу выгодные скидки...")
    
    loop = asyncio.get_running_loop()
    
    try:
        # Выполняем тяжелые запросы в отдельном потоке
        games = await loop.run_in_executor(None, steam_bot.get_featured_deals)
        filtered_games, filtered_dlc = await loop.run_in_executor(None, steam_bot.filter_games, games)
        
        total = len(filtered_games) + len(filtered_dlc)
        
        if total == 0:
            await update.message.reply_text(
                f"😔 Не найдено игр с:\n"
                f"• Ценой ≥{config.MIN_ORIGINAL_PRICE} ₽\n"
                f"• Скидкой ≥{config.MIN_DISCOUNT}%"
            )
            return
        
        # === ИГРЫ ===
        if filtered_games:
            header = f"🎮 *ИГРЫ ({len(filtered_games)}):*\n"
            await update.message.reply_text(header, parse_mode=ParseMode.MARKDOWN)
            
            for game in filtered_games[:8]:  # Максимум 8 игр
                msg = steam_bot.format_game_message(game)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Добавить", callback_data=f"add_{game['app_id']}")]
                ])
                await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
                await asyncio.sleep(0.3)
            
            if len(filtered_games) > 8:
                await update.message.reply_text(f"... и ещё {len(filtered_games) - 8} игр")
        
        # === DLC ===
        if filtered_dlc:
            header = f"\n📦 *DLC ({len(filtered_dlc)}):*\n"
            await update.message.reply_text(header, parse_mode=ParseMode.MARKDOWN)
            
            for dlc in filtered_dlc[:5]:  # Максимум 5 DLC
                msg = steam_bot.format_game_message(dlc)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Добавить", callback_data=f"add_{dlc['app_id']}")]
                ])
                await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
                await asyncio.sleep(0.3)
            
            if len(filtered_dlc) > 5:
                await update.message.reply_text(f"... и ещё {len(filtered_dlc) - 5} DLC")
        
        # Проверяем watchlist (тоже в executor)
        watchlist_deals = await loop.run_in_executor(None, steam_bot.check_watchlist_deals)
        if watchlist_deals:
            await update.message.reply_text(
                "⭐ *Из вашего списка отслеживания:*",
                parse_mode=ParseMode.MARKDOWN
            )
            for game in watchlist_deals:
                msg = steam_bot.format_game_message(game)
                await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Ошибка в check_deals: {e}")
        await update.message.reply_text("❌ Ошибка при поиске скидок.")


async def show_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /watchlist - показать список отслеживания"""
    watchlist = steam_bot.load_watchlist()
    
    if not watchlist:
        await update.message.reply_text(
            "📋 Ваш список отслеживания пуст.\n\n"
            "Добавьте игру командой:\n"
            "`/add <app_id>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    await update.message.reply_text("📋 *Ваш список отслеживания:*", parse_mode=ParseMode.MARKDOWN)
    
    loop = asyncio.get_running_loop()
    
    for i, game in enumerate(watchlist, 1):
        # Получаем данные асинхронно
        info = await loop.run_in_executor(None, steam_bot.get_game_details, game["app_id"])
        
        if info and info["discount_percent"] > 0:
            price_info = f"🔥 -{info['discount_percent']}% ({info['final_price']:.0f} {info.get('currency', 'rub')})"
        elif info:
            price_info = f"{info['original_price']:.0f} {info.get('currency', 'rub')}"
        else:
            price_info = "цена неизвестна"
            
        text = f"{i}. *{game['name']}*\nID: `{game['app_id']}` | {price_info}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Удалить", callback_data=f"del_{game['app_id']}")]
        ])
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


async def add_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /add <app_id> - добавить игру"""
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите App ID игры.\n"
            "Пример: `/add 1245620`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        app_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ App ID должен быть числом")
        return
    
    await update.message.reply_text("🔍 Ищу игру...")
    
    # Запускаем блокирующую функцию в отдельном потоке
    loop = asyncio.get_running_loop()
    
    try:
        success, message = await loop.run_in_executor(None, steam_bot.add_to_watchlist, app_id)
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Ошибка при добавлении игры: {e}")
        await update.message.reply_text("❌ Внутренняя ошибка при добавлении игры.")


async def remove_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /remove <app_id> - удалить игру"""
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите App ID игры.\n"
            "Пример: `/remove 1245620`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        app_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ App ID должен быть числом")
        return
    
    success, message = steam_bot.remove_from_watchlist(app_id)
    await update.message.reply_text(message)


async def auto_check_deals(context: ContextTypes.DEFAULT_TYPE):
    """Автоматическая проверка скидок на игры из watchlist"""
    global notified_deals
    
    watchlist_deals = steam_bot.check_watchlist_deals()
    
    for game in watchlist_deals:
        deal_key = f"{game['app_id']}_{game['discount_percent']}"
        
        if deal_key not in notified_deals:
            notified_deals.add(deal_key)
            
            msg = (
                "🎉 *Новая скидка на игру из вашего списка!*\n\n" +
                steam_bot.format_game_message(game)
            )
            
            try:
                await context.bot.send_message(
                    chat_id=config.CHAT_ID,
                    text=msg,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления: {e}")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатий на инлайн-кнопки"""
    query = update.callback_query
    await query.answer()  # Отвечаем, чтобы убрать часики
    
    data = query.data
    
    if data.startswith("add_"):
        app_id = int(data.split("_")[1])
        # Используем executor для асинхронности
        loop = asyncio.get_running_loop()
        try:
            success, message = await loop.run_in_executor(None, steam_bot.add_to_watchlist, app_id)
            if success:
                new_text = query.message.text + f"\n\n✅ Добавлено!"
                await query.edit_message_text(text=new_text, parse_mode=ParseMode.MARKDOWN)
            else:
                 await query.message.reply_text(message)
        except Exception as e:
            logger.error(f"Ошибка кнопки add: {e}")
            await query.message.reply_text("❌ Ошибка при добавлении.")
            
    elif data.startswith("del_"):
        app_id = int(data.split("_")[1])
        loop = asyncio.get_running_loop()
        try:
            success, message = await loop.run_in_executor(None, steam_bot.remove_from_watchlist, app_id)
            if success:
                # Обновляем список или сообщение
                new_text = query.message.text + f"\n\n❌ Удалено!"
                await query.edit_message_text(text=new_text, parse_mode=ParseMode.MARKDOWN)
            else:
                await query.message.reply_text(message)
        except Exception as e:
            logger.error(f"Ошибка кнопки del: {e}")
            await query.message.reply_text("❌ Ошибка при удалении.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений (меню)"""
    text = update.message.text
    
    if text == "🔍 Проверить скидки":
        await check_deals(update, context)
    elif text == "📋 Мой список":
        await show_watchlist(update, context)
    elif text == "ℹ️ Помощь":
        await help_command(update, context)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логирует ошибки при обработке обновлений."""
    logger.error(Exception(context.error), exc_info=context.error)
    
    if isinstance(update, Update) and update.effective_message:
        text = "❌ Произошла ошибка при обработке запроса. Попробуйте позже."
        await update.effective_message.reply_text(text)


def main():
    """Запуск бота"""
    print("=" * 50)
    print("🎮 Steam Discount Bot")
    print("=" * 50)
    
    if config.TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("\n❌ ОШИБКА: Укажите токен бота в config.py!")
        return
    
    # Создаём приложение
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()
    
    # Добавляем обработчик ошибок
    app.add_error_handler(error_handler)
    
    # Добавляем обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("check", check_deals))
    app.add_handler(CommandHandler("watchlist", show_watchlist))
    app.add_handler(CommandHandler("list", show_watchlist))  # Алиас
    app.add_handler(CommandHandler("add", add_game))
    app.add_handler(CommandHandler("remove", remove_game))
    
    # Обработчик кнопок меню (текст)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработчик инлайн-кнопок
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Добавляем автоматическую проверку
    if config.CHAT_ID != "YOUR_CHAT_ID_HERE":
        job_queue = app.job_queue
        job_queue.run_repeating(
            auto_check_deals, 
            interval=config.CHECK_INTERVAL,
            first=60
        )
        print(f"\n✅ Автопроверка включена (каждые {config.CHECK_INTERVAL // 60} мин)")
    
    print("\n🚀 Бот запущен! Нажмите Ctrl+C для остановки.\n")
    
    # Запускаем бота
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
