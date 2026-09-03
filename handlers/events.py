from telebot import types

from database import get_active_events
from loader import bot
from utils import safe_edit_message
from datetime import datetime, timezone


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
        txt = (f"🎉 <b>События</b>\n"
               f"➖➖➖➖➖➖➖➖\n\n"
               f"😴 Сейчас нет активных событий.\n\n"
               f"Следите за обновлениями! Во время событий:\n"
               f"• Доступны лимитированные карты 🎴\n"
               f"• Специальные паки 📦\n"
               f"• Уникальные достижения 🏆\n"
               f"• Бонусные награды 🎁")
    else:
        txt = (f"🎉 <b>Активные события</b>\n"
               f"➖➖➖➖➖➖➖➖\n\n")
        for event in events:
            time_left = format_event_time_left(event.get('end_at', ''))
            txt += (f"⚡️ <b>{event.get('name', 'Событие')}</b>\n"
                    f"   📋 {event.get('description', '')}\n"
                    f"   ⏳ До конца: {time_left}\n\n")
            markup.add(types.InlineKeyboardButton(
                f"🎴 {event.get('name', 'Событие')}",
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
        bot.answer_callback_query(call.id, "Событие завершено", show_alert=True)
        return

    time_left = format_event_time_left(event.get('end_at', ''))
    txt = (f"⚡️ <b>{event.get('name', 'Событие')}</b>\n"
           f"➖➖➖➖➖➖➖➖\n\n"
           f"📋 {event.get('description', 'Нет описания')}\n\n"
           f"⏳ До конца: <b>{time_left}</b>\n\n"
           f"🎁 Во время события доступны:\n"
           f"• Событийные паки 🎉\n"
           f"• Лимитированные карточки 🎴\n"
           f"• Специальные задания 🎯")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📦 Открыть событийный пак", callback_data="pack_view:event"))
    markup.add(types.InlineKeyboardButton("🔙 К событиям", callback_data="menu_events"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup, parse_mode="HTML")
