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
        qty = offer.get('offered_card_quantity') or 1
        qty_txt = f" x{qty}" if qty > 1 else ""
        txt += f"От: <b>{from_name}</b>\nКарта: {emoji} <b>{card.get('name', '?')}</b>{qty_txt}\n\n"
        markup.row(
            types.InlineKeyboardButton(f"✅ Принять #{offer['id']}", callback_data=f"trade_accept:{offer['id']}:{page}"),
            types.InlineKeyboardButton(f"❌ Отклонить", callback_data=f"trade_decline:{offer['id']}:{page}"),
        )

    if total > 1:
        markup.add(types.InlineKeyboardButton(f"✅ Принять все ({total})", callback_data="trade_accept_all"))
    markup.row(*_page_nav_row("trade_incoming", page, max_page))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="menu_trade"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "trade_accept_all")
def trade_accept_all(call):
    # answer_callback_query можно вызвать только один раз на call.id — не
    # шлём промежуточный ответ, сразу обрабатываем (локальный sqlite, без
    # сетевых задержек) и отвечаем один раз с итогом
    user_id = call.from_user.id
    offers = get_incoming_trades(user_id)

    accepted, failed = 0, 0
    for offer in offers:
        success, _ = accept_trade(offer['id'], user_id)
        if success:
            accepted += 1
        else:
            failed += 1

    bot.answer_callback_query(call.id, f"✅ Принято: {accepted}" + (f", не удалось: {failed}" if failed else ""),
                              show_alert=True)
    call.data = "trade_incoming:0"
    trade_incoming(call)


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
            qty = offer.get('offered_card_quantity') or 1
            qty_txt = f" x{qty}" if qty > 1 else ""
            txt += f"Кому: <b>{to_name}</b>\nКарта: {emoji} <b>{card.get('name', '?')}</b>{qty_txt}\nСтатус: ⏳ Ожидание\n\n"
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

    _send_trade_card_picker(message.chat.id, user_id, target['telegram_id'], target['first_name'], page=0)


# --- ВЫБОР КАРТ (мультивыбор) ---
# Можно отметить сразу несколько РАЗНЫХ карт (любых редкостей) галочками,
# затем бот по очереди спрашивает количество для каждой отмеченной и
# отправляет отдельное предложение обмена тому же игроку.

def _render_trade_picker(user_id, target_name, page=0):
    """Строит (txt, markup, page) для экрана выбора карт — используется и
    для первой отправки, и для последующего редактирования при toggle/
    листании. Возвращает (None, None, 0), если отдавать нечего."""
    inv_data = [item for item in (get_user_inventory(user_id).data or [])
               if item.get('count', 0) > 0 and item.get('cards')]
    if not inv_data:
        return None, None, 0

    selected = _trade_state.get(user_id, {}).get('selected', set())
    page_items, page, max_page, total = _paginate(inv_data, page)

    markup = types.InlineKeyboardMarkup(row_width=1)
    for item in page_items:
        card = item['cards']
        emoji = RARITY_CONFIG.get(card.get('rarity', ''), {}).get('emoji', '🃏')
        mark = "✅ " if card['id'] in selected else ""
        markup.add(types.InlineKeyboardButton(
            f"{mark}{emoji} {card['name']} (x{item['count']})",
            callback_data=f"trade_toggle:{card['id']}:{page}"
        ))

    if max_page > 0:
        markup.row(*_page_nav_row("trade_pick_page", page, max_page))

    if selected:
        markup.add(types.InlineKeyboardButton(f"✅ Готово ({len(selected)} выбрано)", callback_data="trade_select_confirm"))
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="menu_trade"))

    txt = (f"Выберите карты для предложения игроку <b>{target_name}</b> "
           f"(всего карт: {total}) — отмечайте ✅, можно сразу несколько:")
    return txt, markup, page


def _send_trade_card_picker(chat_id, user_id, target_id, target_name, page=0):
    _trade_state[user_id] = {'target_id': target_id, 'target_name': target_name, 'selected': set()}
    txt, markup, page = _render_trade_picker(user_id, target_name, page)
    if txt is None:
        bot.send_message(chat_id, "У вас нет карт для обмена.")
        _trade_state.pop(user_id, None)
        return
    bot.send_message(chat_id, txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("trade_toggle:"))
def trade_toggle_cb(call):
    bot.answer_callback_query(call.id)
    _, card_id, page = call.data.split(":")
    card_id = int(card_id)
    user_id = call.from_user.id
    state = _trade_state.setdefault(user_id, {})
    selected = state.setdefault('selected', set())
    if card_id in selected:
        selected.discard(card_id)
    else:
        selected.add(card_id)
    txt, markup, _ = _render_trade_picker(user_id, state.get('target_name', '?'), page=int(page))
    if txt:
        safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("trade_pick_page:"))
def trade_pick_page_cb(call):
    bot.answer_callback_query(call.id)
    page = int(call.data.split(":")[1])
    user_id = call.from_user.id
    state = _trade_state.get(user_id) or {}
    txt, markup, _ = _render_trade_picker(user_id, state.get('target_name', '?'), page=page)
    if txt:
        safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "trade_select_confirm")
def trade_select_confirm(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    state = _trade_state.get(user_id, {})
    selected = list(state.get('selected', set()))
    target_id = state.get('target_id')
    target_name = state.get('target_name', '?')
    if not selected or not target_id:
        bot.answer_callback_query(call.id, "Ничего не выбрано", show_alert=True)
        return

    _trade_state[user_id] = {'target_id': target_id, 'target_name': target_name,
                             'queue': selected, 'results': []}
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    _start_next_trade_item(call.message.chat.id, user_id)


# --- ОЧЕРЕДЬ: КОЛИЧЕСТВО ПО КАЖДОЙ ВЫБРАННОЙ КАРТЕ ---

def _start_next_trade_item(chat_id, user_id):
    state = _trade_state.get(user_id)
    if not state:
        return
    queue = state.get('queue', [])
    if not queue:
        _finish_trade_queue(chat_id, user_id)
        return

    card_id = queue[0]
    inv_res = get_user_inventory(user_id)
    item = next((i for i in (inv_res.data or [])
                if i.get('cards') and i['cards'].get('id') == card_id), None)
    have = item['count'] if item else 0
    card_name = item['cards']['name'] if item else f"#{card_id}"

    if have < 1:
        # Копии этой карты уже нет (отдали/продали в другом месте, пока шёл выбор)
        state['results'].append((card_name, 0))
        state['queue'] = queue[1:]
        _start_next_trade_item(chat_id, user_id)
        return

    state['current_card_id'] = card_id
    state['current_card_name'] = card_name
    state['current_have'] = have

    if have == 1:
        # Нечего выбирать — сразу отдаём единственную копию
        _create_trade_for_queue_item(chat_id, user_id, 1)
        return

    msg = bot.send_message(chat_id,
                           f"🔢 «{card_name}» (у вас {have} шт) — сколько копий отдать?\n"
                           f"Введите число от 1 до {have}.\n\nПропустить эту карту — /skip")
    register_next_step_handler_for_user(bot, msg, user_id, _trade_queue_qty_step)


def _trade_queue_qty_step(message):
    user_id = message.from_user.id
    state = _trade_state.get(user_id)
    if not state:
        return
    if message.text and message.text.strip() == '/skip':
        state['results'].append((state.get('current_card_name', '?'), 0))
        state['queue'] = state['queue'][1:]
        _start_next_trade_item(message.chat.id, user_id)
        return
    try:
        qty = int(message.text.strip())
        have = state.get('current_have', 1)
        if qty < 1 or qty > have:
            raise ValueError
    except (ValueError, AttributeError):
        msg = bot.send_message(message.chat.id, f"❌ Введите число от 1 до {state.get('current_have', 1)}, либо /skip:")
        register_next_step_handler_for_user(bot, msg, user_id, _trade_queue_qty_step)
        return
    _create_trade_for_queue_item(message.chat.id, user_id, qty)


def _create_trade_for_queue_item(chat_id, user_id, quantity):
    state = _trade_state.get(user_id)
    if not state:
        return
    card_id = state['current_card_id']
    card_name = state.get('current_card_name', '?')
    target_id = state.get('target_id')

    trade_id, err = create_trade_offer(user_id, target_id, card_id, quantity=quantity)
    if trade_id:
        state['results'].append((card_name, quantity))
    else:
        state['results'].append((f"{card_name} ({err})", 0))

    state['queue'] = state['queue'][1:]
    _start_next_trade_item(chat_id, user_id)


def _finish_trade_queue(chat_id, user_id):
    state = _trade_state.pop(user_id, {})
    results = state.get('results', [])
    target_id = state.get('target_id')

    ok_lines = [f"• {name} x{qty}" for name, qty in results if qty]
    failed_names = [name for name, qty in results if not qty]

    txt = ("✅ <b>Предложения отправлены!</b>\n\n" if ok_lines else "Ничего не отправлено.\n\n")
    txt += "\n".join(ok_lines)
    if failed_names:
        txt += f"\n\n⏭ Не отправлено: {', '.join(failed_names)}"
    bot.send_message(chat_id, txt, parse_mode="HTML")

    if ok_lines and target_id:
        try:
            bot.send_message(target_id,
                             f"🤝 <b>Новые предложения обмена!</b>\n\n"
                             f"Игрок предложил вам {len(ok_lines)} карт(ы).\n"
                             f"Откройте раздел 🤝 Обмен → Входящие предложения.",
                             parse_mode="HTML")
        except Exception:
            pass
