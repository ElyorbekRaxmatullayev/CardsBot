from telebot import types

from config import DAILY_TASKS, WEEKLY_TASKS
from database import (get_user_task_progress, claim_task_reward,
                      update_coins, update_gems, update_task_progress,
                      get_user_data)
from loader import bot
from utils import safe_edit_message


def _progress_bar(current, target, length=8):
    """Текстовый прогресс-бар"""
    filled = min(int(current / max(target, 1) * length), length)
    return "█" * filled + "░" * (length - filled)


def _task_line(task, progress_data):
    """Форматирует одну задачу: ✅/❌ перед названием — выполнено или нет"""
    task_id = task['id']
    prog = progress_data.get(task_id, {})
    current = prog.get('progress', 0)
    claimed = prog.get('claimed', False)
    target = task['target']
    done = current >= target

    bar = _progress_bar(current, target)
    status = "✅" if done else "❌"

    reward_parts = []
    if task['reward_coins'] > 0:
        reward_parts.append(f"💰{task['reward_coins']}")
    if task['reward_gems'] > 0:
        reward_parts.append(f"💎{task['reward_gems']}")
    reward_str = " + ".join(reward_parts)
    if claimed:
        reward_str += " (получено)"

    return f"{status} {task['name']}\n   [{bar}] {min(current, target)}/{target}  →  {reward_str}"


# --- МЕНЮ ЗАДАНИЙ ---

def tasks_markup(period):
    markup = types.InlineKeyboardMarkup()
    if period == "daily":
        markup.add(types.InlineKeyboardButton("📅 Ежедневные ✓", callback_data="tasks_daily"),
                   types.InlineKeyboardButton("📆 Еженедельные", callback_data="tasks_weekly"))
    else:
        markup.add(types.InlineKeyboardButton("📅 Ежедневные", callback_data="tasks_daily"),
                   types.InlineKeyboardButton("📆 Еженедельные ✓", callback_data="tasks_weekly"))
    markup.add(types.InlineKeyboardButton("🎁 Получить награды", callback_data=f"tasks_claim:{period}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_game_menu"))
    return markup


def _build_tasks_text(user_id, period):
    tasks = DAILY_TASKS if period == "daily" else WEEKLY_TASKS
    progress = get_user_task_progress(user_id, period)
    period_name = "📅 Ежедневные задания" if period == "daily" else "📆 Еженедельные задания"

    txt = f"🎯 <b>{period_name}</b>\n➖➖➖➖➖➖➖➖\n\n"
    for task in tasks:
        txt += _task_line(task, progress) + "\n\n"
    return txt


@bot.callback_query_handler(func=lambda call: call.data == "menu_tasks")
def tasks_menu(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    txt = _build_tasks_text(user_id, "daily")
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=tasks_markup("daily"), parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data in ["tasks_daily", "tasks_weekly"])
def switch_tasks(call):
    bot.answer_callback_query(call.id)
    period = "daily" if call.data == "tasks_daily" else "weekly"
    user_id = call.from_user.id
    txt = _build_tasks_text(user_id, period)
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=tasks_markup(period), parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("tasks_claim:"))
def claim_tasks(call):
    period = call.data.split(":")[1]
    user_id = call.from_user.id
    tasks = DAILY_TASKS if period == "daily" else WEEKLY_TASKS
    progress = get_user_task_progress(user_id, period)

    total_coins = 0
    total_gems = 0
    claimed_names = []

    for task in tasks:
        task_id = task['id']
        prog = progress.get(task_id, {})
        current = prog.get('progress', 0)
        already_claimed = prog.get('claimed', False)
        done = current >= task['target']

        if done and not already_claimed:
            if claim_task_reward(user_id, task_id, period):
                total_coins += task['reward_coins']
                total_gems += task['reward_gems']
                claimed_names.append(task['name'])

    if not claimed_names:
        bot.answer_callback_query(call.id, "Нет выполненных заданий для получения наград!", show_alert=True)
        return

    if total_coins > 0:
        update_coins(user_id, total_coins)
    if total_gems > 0:
        update_gems(user_id, total_gems)

    bot.answer_callback_query(call.id,
                              f"🎉 Получено: 💰{total_coins}" + (f" + 💎{total_gems}" if total_gems else ""),
                              show_alert=True)
    # Обновить экран
    txt = _build_tasks_text(user_id, period)
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=tasks_markup(period), parse_mode="HTML")


def award_task_on_event(user_id, event_key, period="daily"):
    """Вызывается из других хендлеров для обновления прогресса задания"""
    update_task_progress(user_id, event_key, period)
