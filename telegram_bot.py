import json
import logging
import os

from telegram import Update
from telegram.ext import ContextTypes, CallbackContext, Application, CommandHandler

import price_tracker

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

BOT_TOKEN = ""
STATE_FILE = "bot_state.json"
SUPPORTED_DOMAINS = ["ozon.ru", "wildberries.ru", "market.yandex.ru"]


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "parsing_active": False,
        "tracked_urls": [],
        "job": None
    }


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=4)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "👋 Привет! Я бот для мониторинга цен на маркетплейсах.\n\n"
        "🔍 Я поддерживаю работу с: \n"
        "- Ozon\n"
        "- Wildberries\n"
        "- Яндекс.Маркет\n\n"
        "📜 Доступные команды:\n"
        "/add_url — добавить ссылку на товар\n"
        "/start_parsing — запустить проверку цен\n"
        "/stop_parsing — остановить проверку"
    )

    await update.message.reply_text(text)


async def cmd_add_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажи ссылку после команды. Пример: /add_url https://ozon.ru/...")
        return

    url = " ".join(context.args)

    if not any(domain in url for domain in SUPPORTED_DOMAINS):
        await update.message.reply_text(
            "Ошибка: поддерживаются только ссылки с Ozon, Wildberries и Яндекс.Маркета."
        )
        return

    state = load_state()

    if url in state["tracked_urls"]:
        await update.message.reply_text("Эта ссылка уже есть в списке отслеживания.")
        return

    state["tracked_urls"].append(url)
    save_state(state)

    await update.message.reply_text("Ссылка успешно добавлена в список отслеживания.")


async def cmd_start_parsing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = load_state()

    if state["parsing_active"]:
        await update.message.reply_text("Парсинг уже запущен.")
        return

    if not state["tracked_urls"]:
        await update.message.reply_text("Сначала добавь хотя бы одну ссылку через /add_url.")
        return

    chat_id = update.message.chat_id

    job = context.job_queue.run_repeating(
        callback=task_check_prices,
        interval=86400,
        first=10,
        data=chat_id,
        name=str(chat_id),
    )
    state["parsing_active"] = True
    state["job"] = job.name
    save_state(state)

    await update.message.reply_text("Автоматическая проверка цен запущена. Первая проверка будет через 10 секунд.")


async def cmd_stop_parsing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = load_state()

    if not state["parsing_active"]:
        await update.message.reply_text("Парсинг сейчас не запущен.")
        return

    for job in context.job_queue.jobs():
        if job.name == state["job"]:
            job.schedule_removal()
            break

    state["parsing_active"] = False
    state["job"] = None
    save_state(state)

    await update.message.reply_text("Автоматическая проверка цен остановлена.")


async def task_check_prices(context: CallbackContext) -> None:
    state = load_state()
    chat_id = context.job.data

    if not state["tracked_urls"]:
        await context.bot.send_message(chat_id=chat_id, text="🔄 Нет товаров для проверки...")
        return

    await context.bot.send_message(chat_id=chat_id, text="🔄 Проверяю цены...")

    lines = []

    for url in state["tracked_urls"]:
        try:
            success, message, _ = price_tracker.get_price(url)

            lines.append(f"{'✅' if success else '❌'} {url}\n     {message}")
        except Exception as e:
            lines.append(f"⛔️ {url}\n    Ошибка: {e}")

    result_text = "\n\n".join(lines)

    await context.bot.send_message(chat_id=chat_id, text=f"📊 Результаты:\n\n{result_text}")


def main() -> None:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(60.0)
        .read_timeout(60.0)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("add_url", cmd_add_url))
    app.add_handler(CommandHandler("start_parsing", cmd_start_parsing))
    app.add_handler(CommandHandler("stop_parsing", cmd_stop_parsing))

    app.run_polling()


if __name__ == "__main__":
    main()
