from telebot import types

from config import ACHIEVEMENTS
from database import (get_user_achievements, award_achievement,
                      get_user_stats_for_achievements, update_coins, update_gems)
from loader import bot
from utils import safe_edit_message


def check_and_award_achievements(user_id, notify=True):
    """Проверяет и выдаёт новые достижения. При notify=True — отправляет сообщение"""
    stats = get_user_stats_for_achievements(user_id)
    owned = set(get_user_achievements(user_id))
    new_ones = []

    for ach in ACHIEVEMENTS:
        if ach['id'] in owned:
            continue
        field_val = stats.get(ach['field'], 0)
        if field_val >= ach['target']:
            if award_achievement(user_id, ach['id']):
                # Выдаём награду
                if ach['reward_coins']:
                    update_coins(user_id, ach['reward_coins'])
                if ach['reward_gems']:
                    update_gems(user_id, ach['reward_gems'])
                new_ones.append(ach)

    if notify and new_ones:
        for ach in new_ones:
            reward_parts = []
            if ach['reward_coins']:
                reward_parts.append(f"💰{ach['reward_coins']}")
            if ach['reward_gems']:
                reward_parts.append(f"💎{ach['reward_gems']}")
            reward_str = " + ".join(reward_parts)
            try:
                from loader import bot as _bot
                _bot.send_message(user_id,
                                  f"🏆 <b>Достижение разблокировано!</b>\n\n"
                                  f"{ach['name']}\n"
                                  f"<i>{ach['desc']}</i>\n\n"
                                  f"Награда: {reward_str}",
                                  parse_mode="HTML")
            except:
                pass
    return new_ones


ACHIEVEMENTS_PAGE_SIZE = 8


def _build_achievements_text(user_id, page=0):
    stats = get_user_stats_for_achievements(user_id)
    owned = set(get_user_achievements(user_id))
    total = len(ACHIEVEMENTS)
    done = len(owned)

    max_page = max((total - 1) // ACHIEVEMENTS_PAGE_SIZE, 0)
    start = page * ACHIEVEMENTS_PAGE_SIZE
    page_items = ACHIEVEMENTS[start:start + ACHIEVEMENTS_PAGE_SIZE]

    txt = (f"🏆 <b>Достижения</b>\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"Получено: <b>{done}/{total}</b>  |  Стр. {page + 1}/{max_page + 1}\n\n")

    for ach in page_items:
        field_val = stats.get(ach['field'], 0)
        is_done = ach['id'] in owned
        progress = min(field_val, ach['target'])

        if is_done:
            status = "✅"
        elif progress > 0:
            status = "🔓"
        else:
            status = "🔒"

        reward_parts = []
        if ach['reward_coins']:
            reward_parts.append(f"💰{ach['reward_coins']}")
        if ach['reward_gems']:
            reward_parts.append(f"💎{ach['reward_gems']}")
        reward_str = " + ".join(reward_parts)

        txt += (f"{status} <b>{ach['name']}</b>\n"
                f"  <i>{ach['desc']}</i>\n"
                f"  [{progress}/{ach['target']}]  {reward_str}\n\n")
    return txt


def _achievements_markup(page):
    max_page = max((len(ACHIEVEMENTS) - 1) // ACHIEVEMENTS_PAGE_SIZE, 0)
    markup = types.InlineKeyboardMarkup()
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"ach_page:{page - 1}"))
    nav.append(types.InlineKeyboardButton(f"{page + 1}/{max_page + 1}", callback_data="ignore"))
    if page < max_page:
        nav.append(types.InlineKeyboardButton("➡️", callback_data=f"ach_page:{page + 1}"))
    markup.row(*nav)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_game_menu"))
    return markup


@bot.callback_query_handler(func=lambda call: call.data == "menu_achievements")
def achievements_menu(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id

    # Автоматически проверяем достижения при открытии
    check_and_award_achievements(user_id, notify=False)

    txt = _build_achievements_text(user_id, page=0)
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=_achievements_markup(0), parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("ach_page:"))
def achievements_page(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    page = int(call.data.split(":")[1])
    txt = _build_achievements_text(user_id, page=page)
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=_achievements_markup(page), parse_mode="HTML")
