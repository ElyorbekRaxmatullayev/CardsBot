from telebot import types

from config import RARITY_CONFIG
from database import (get_user_data, get_user_inventory,
                      get_incoming_trades, get_outgoing_trades,
                      create_trade_offer, accept_trade, decline_trade)
from loader import bot
from utils import safe_edit_message, safe_send_message, register_next_step_handler_for_user

# Временное хранилище для выбранных карт при создании обмена
_trade_state = {}  # user_id -> {'step': ..., 'card_id': ..., 'target_id': ...}

TRADE_PAGE_SIZE = 10


# --- ГЛАВНОЕ МЕНЮ ОБМЕНА ---

def get_trade_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📬 Входящие предложения", callback_data="trade_incoming"))
    markup.add(types.InlineKeyboardButton("📤 Исходящие предложения", callback_data="trade_outgoing"))
    markup.add(types.InlineKeyboardButton("➕ Предложить обмен", callback_data="trade_new_step1"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_game_menu"))
    return markup


@bot.callback_query_handler(func=lambda call: call.data == "menu_trade")
def trade_menu(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    incoming = get_incoming_trades(user_id)

    badge = f" ({len(incoming)})" if incoming else ""
    txt = (f"🤝 <b>Обмен картами</b>\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"Входящих предложений: <b>{len(incoming)}</b>\n\n"
           f"Выберите действие:")
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=get_trade_markup(), parse_mode="HTML")


# --- ВХОДЯЩИЕ ---

def _paginate(items, page):
    total = len(items)
    max_page = max(0, (total - 1) // TRADE_PAGE_SIZE)
    page = max(0, min(page, max_page))
    start = page * TRADE_PAGE_SIZE
    return items[start:start + TRADE_PAGE_SIZE], page, max_page, total


def _page_nav_row(callback_prefix, page, max_page):
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"{callback_prefix}:{page - 1}"))
    nav.append(types.InlineKeyboardButton(f"{page + 1}/{max_page + 1}", callback_data="ignore"))
    if page < max_page:
        nav.append(types.InlineKeyboardButton("➡️", callback_data=f"{callback_prefix}:{page + 1}"))
    return nav


@bot.callback_query_handler(func=lambda call: call.data == "trade_incoming" or call.data.startswith("trade_incoming:"))
def trade_incoming(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    page = int(call.data.split(":")[1]) if ":" in call.data else 0
    offers = get_incoming_trades(user_id)

    if not offers:
        txt = "📬 <b>Входящие предложения</b>\n\nУ вас нет входящих предложений."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="menu_trade"))
        safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                          txt, reply_markup=markup, parse_mode="HTML")
        return

    page_items, page, max_page, total = _paginate(offers, page)

    txt = (f"📬 <b>Входящие предложения обмена</b> (всего: {total})\n"
           f"➖➖➖➖➖➖➖➖\n\n")
    markup = types.InlineKeyboardMarkup()
    for offer in page_items:
        card = offer.get('cards') or {}
        from_name = (offer.get('users') or {}).get('first_name', 'Неизвестно')
        emoji = RARITY_CONFIG.get(card.get('rarity', ''), {}).get('emoji', '🃏')
        txt += f"От: <b>{from_name}</b>\nКарта: {emoji} <b>{card.get('name', '?')}</b>\n\n"
        markup.row(
            types.InlineKeyboardButton(f"✅ Принять #{offer['id']}", callback_data=f"trade_accept:{offer['id']}:{page}"),
            types.InlineKeyboardButton(f"❌ Отклонить", callback_data=f"trade_decline:{offer['id']}:{page}"),
        )

    markup.row(*_page_nav_row("trade_incoming", page, max_page))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="menu_trade"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup, parse_mode="HTML")


# --- ИСХОДЯЩИЕ ---

@bot.callback_query_handler(func=lambda call: call.data == "trade_outgoing" or call.data.startswith("trade_outgoing:"))
def trade_outgoing(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    page = int(call.data.split(":")[1]) if ":" in call.data else 0
    offers = get_outgoing_trades(user_id)

    markup = types.InlineKeyboardMarkup()
    if not offers:
        txt = "📤 <b>Исходящие предложения</b>\n\nУ вас нет исходящих предложений."
    else:
        page_items, page, max_page, total = _paginate(offers, page)
        txt = (f"📤 <b>Ваши предложения обмена</b> (всего: {total})\n"
               f"➖➖➖➖➖➖➖➖\n\n")
        for offer in page_items:
            card = offer.get('cards') or {}
            to_name = (offer.get('users') or {}).get('first_name', 'Неизвестно')
            emoji = RARITY_CONFIG.get(card.get('rarity', ''), {}).get('emoji', '🃏')
            txt += f"Кому: <b>{to_name}</b>\nКарта: {emoji} <b>{card.get('name', '?')}</b>\nСтатус: ⏳ Ожидание\n\n"
        markup.row(*_page_nav_row("trade_outgoing", page, max_page))

    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="menu_trade"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup, parse_mode="HTML")


# --- ПРИНЯТЬ / ОТКЛОНИТЬ ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("trade_accept:"))
def trade_accept(call):
    parts = call.data.split(":")
    trade_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0
    user_id = call.from_user.id
    success, msg = accept_trade(trade_id, user_id)
    bot.answer_callback_query(call.id, msg, show_alert=True)
    call.data = f"trade_incoming:{page}"
    trade_incoming(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("trade_decline:"))
def trade_decline_cb(call):
    parts = call.data.split(":")
    trade_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0
    user_id = call.from_user.id
    decline_trade(trade_id, user_id)
    bot.answer_callback_query(call.id, "❌ Предложение отклонено")
    call.data = f"trade_incoming:{page}"
    trade_incoming(call)


# --- НОВОЕ ПРЕДЛОЖЕНИЕ (по Username) ---

@bot.callback_query_handler(func=lambda call: call.data == "trade_new_step1")
def trade_new_step1(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
                           "➕ <b>Новое предложение обмена</b>\n\n"
                           "Введите <b>Telegram ID</b> или <b>@username</b> игрока, "
                           "которому хотите предложить обмен:\n\n"
                           "Отмена — /cancel",
                           parse_mode="HTML")
    _trade_state[call.from_user.id] = {'step': 'waiting_target'}
    register_next_step_handler_for_user(bot, msg, call.from_user.id, _trade_step_get_target)


def _trade_step_get_target(message):
    user_id = message.from_user.id
    if message.text == '/cancel':
        _trade_state.pop(user_id, None)
        bot.send_message(message.chat.id, "Отменено.")
        return

    from database import supabase
    target_input = message.text.strip().lstrip('@')
    # Ищем по username или ID
    res = supabase.table("users").select("telegram_id, first_name").eq("username", target_input).execute()
    if not res.data:
        try:
            tid = int(target_input)
            res = supabase.table("users").select("telegram_id, first_name").eq("telegram_id", tid).execute()
        except:
            pass

    if not res.data:
        msg = bot.send_message(message.chat.id, "❌ Игрок не найден. Попробуйте ещё раз или /cancel:")
        register_next_step_handler_for_user(bot, msg, user_id, _trade_step_get_target)
        return

    target = res.data[0]
    if target['telegram_id'] == user_id:
        msg = bot.send_message(message.chat.id, "❌ Нельзя обмениваться с собой!")
        register_next_step_handler_for_user(bot, msg, user_id, _trade_step_get_target)
        return

    _trade_state[user_id]['target_id'] = target['telegram_id']
    _trade_state[user_id]['target_name'] = target['first_name']

    # Показываем карты пользователя для выбора
    inv_res = get_user_inventory(user_id)
    inv_data = inv_res.data if inv_res.data else []

    if not inv_data:
        bot.send_message(message.chat.id, "У вас нет карт для обмена.")
        _trade_state.pop(user_id, None)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    shown = 0
    for item in inv_data[:15]:  # Максимум 15 карт в списке
        card = item.get('cards', {})
        if not card:
            continue
        emoji = RARITY_CONFIG.get(card.get('rarity', ''), {}).get('emoji', '🃏')
        markup.add(types.InlineKeyboardButton(
            f"{emoji} {card['name']} (x{item['count']})",
            callback_data=f"trade_select_card:{card['id']}:{target['telegram_id']}"
        ))
        shown += 1

    if not shown:
        bot.send_message(message.chat.id, "У вас нет карт для обмена.")
        _trade_state.pop(user_id, None)
        return

    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="menu_trade"))
    bot.send_message(message.chat.id,
                     f"Выберите карту для предложения игроку <b>{target['first_name']}</b>:",
                     reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("trade_select_card:"))
def trade_select_card(call):
    parts = call.data.split(":")
    card_id = int(parts[1])
    target_id = int(parts[2])
    user_id = call.from_user.id

    trade_id, err = create_trade_offer(user_id, target_id, card_id)
    if trade_id:
        bot.answer_callback_query(call.id, "✅ Предложение отправлено!", show_alert=True)
        # Уведомляем получателя
        try:
            bot.send_message(target_id,
                             f"🤝 <b>Новое предложение обмена!</b>\n\n"
                             f"Игрок предлагает вам обмен картой.\n"
                             f"Откройте раздел 🤝 Обмен → Входящие предложения.",
                             parse_mode="HTML")
        except:
            pass
    else:
        bot.answer_callback_query(call.id, err or "❌ Ошибка создания обмена", show_alert=True)

    _trade_state.pop(user_id, None)
    trade_menu(call)
