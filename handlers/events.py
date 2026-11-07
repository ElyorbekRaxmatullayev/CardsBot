from telebot import types

from database import get_active_events, get_event_task, get_event_task_progress, claim_event_task_reward, \
    update_coins, update_gems
from loader import bot
from utils import safe_edit_message
from datetime import datetime, timezone


def _progress_bar(current, target, length=8):
    filled = min(int(current / max(target, 1) * length), length)
    return "█" * filled + "░" * (length - filled)


def format_event_time_left(end_at_str):
    """Сколько времени осталось до конца события"""
    try:
        end_at = datetime.fromisoformat(end_at_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        diff = end_at - now
        if diff.total_seconds() <= 0:
            return "завершено"
        days = diff.days
        hours = diff.seconds // 3600
        if days > 0:
            return f"{days}д {hours}ч"
        return f"{hours}ч {(diff.seconds % 3600) // 60}мин"
    except:
        return "?"


@bot.callback_query_handler(func=lambda call: call.data == "menu_events")
def events_menu(call):
    bot.answer_callback_query(call.id)
    events = get_active_events()

    markup = types.InlineKeyboardMarkup()

    if not events:
        txt = (f"🎉 <b>Испытания бессмертных</b>\n"
               f"➖➖➖➖➖➖➖➖\n\n"
               f"😴 Сейчас нет активных испытаний.\n\n"
               f"Следите за обновлениями! Во время испытаний:\n"
               f"• Доступны лимитированные карты 🎴\n"
               f"• Специальные паки 📦\n"
               f"• Уникальные достижения 🏆\n"
               f"• Бонусные награды 🎁")
    else:
        txt = (f"🎉 <b>Активные испытания</b>\n"
               f"➖➖➖➖➖➖➖➖\n\n")
        for event in events:
            time_left = format_event_time_left(event.get('end_at', ''))
            txt += (f"⚡️ <b>{event.get('name', 'Испытание')}</b>\n"
                    f"   📋 {event.get('description', '')}\n"
                    f"   ⏳ До конца: {time_left}\n\n")
            markup.add(types.InlineKeyboardButton(
                f"🎴 {event.get('name', 'Испытание')}",
                callback_data=f"event_detail:{event['id']}"
            ))

    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_game_menu"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("event_detail:"))
def event_detail(call):
    bot.answer_callback_query(call.id)
    event_id = call.data.split(":")[1]
    events = get_active_events()
    event = next((e for e in events if str(e.get('id')) == event_id), None)

    if not event:
        bot.answer_callback_query(call.id, "Испытание завершено", show_alert=True)
        return

    time_left = format_event_time_left(event.get('end_at', ''))
    txt = (f"⚡️ <b>{event.get('name', 'Испытание')}</b>\n"
           f"➖➖➖➖➖➖➖➖\n\n"
           f"📋 {event.get('description', 'Нет описания')}\n\n"
           f"⏳ До конца: <b>{time_left}</b>\n\n"
           f"🎁 Во время испытания доступны:\n"
           f"• Паки испытаний 🎉\n"
           f"• Лимитированные карточки 🎴\n"
           f"• Особые шаги пути культивации 🎯")

    markup = types.InlineKeyboardMarkup()

    # Задание испытания с наградой (этап E ТЗ), если админ его добавил
    task = get_event_task(event['id'])
    if task:
        prog = get_event_task_progress(call.from_user.id, event['id'], task['task_id'])
        current, claimed = prog['progress'], prog['claimed']
        target = task['target']
        bar = _progress_bar(current, target)
        reward_parts = []
        if task['reward_coins']: reward_parts.append(f"💰{task['reward_coins']}")
        if task['reward_gems']: reward_parts.append(f"💎{task['reward_gems']}")
        reward_str = " + ".join(reward_parts) if reward_parts else "—"

        txt += (f"\n\n➖➖➖➖➖➖➖➖\n"
               f"🎯 <b>Задание:</b> {task['name']}\n"
               f"[{bar}] {min(current, target)}/{target}  →  {reward_str}")
        if claimed:
            txt += "\n✅ Награда получена"
        elif current >= target:
            markup.add(types.InlineKeyboardButton("🎁 Получить награду", callback_data=f"event_claim:{event['id']}"))

    markup.add(types.InlineKeyboardButton("📦 Открыть пак испытания", callback_data="pack_view:event"))
    markup.add(types.InlineKeyboardButton("🔙 К испытаниям", callback_data="menu_events"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("event_claim:"))
def event_claim(call):
    event_id = int(call.data.split(":")[1])
    task = get_event_task(event_id)
    if not task:
        bot.answer_callback_query(call.id, "Задание не найдено", show_alert=True)
        return

    if not claim_event_task_reward(call.from_user.id, event_id, task['task_id']):
        bot.answer_callback_query(call.id, "Награда уже получена или задание ещё не выполнено", show_alert=True)
        return

    if task['reward_coins']:
        update_coins(call.from_user.id, task['reward_coins'])
    if task['reward_gems']:
        update_gems(call.from_user.id, task['reward_gems'])

    bot.answer_callback_query(call.id, "🎉 Награда получена!", show_alert=True)
    call.data = f"event_detail:{event_id}"
    event_detail(call)
