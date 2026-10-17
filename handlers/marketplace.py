from telebot import types

from config import RARITY_CONFIG, RARITY_ORDER
from database import (get_market_listings, list_card_on_market,
                      buy_from_market, cancel_market_listing,
                      get_my_market_listings, get_user_inventory, get_user_data)
from loader import bot
from utils import safe_edit_message, safe_send_message, register_next_step_handler_for_user

# Временное состояние для листинга
_listing_state = {}  # user_id -> {'card_id': ...}


# --- ГЛАВНОЕ МЕНЮ ---

def get_market_menu_markup():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🔍 Все карты", callback_data="mkt_browse:all"),
        types.InlineKeyboardButton("🎴 Мои листинги", callback_data="mkt_my")
    )
    markup.add(types.InlineKeyboardButton("➕ Выставить карту", callback_data="mkt_sell_start"))
    # Фильтры по редкости
    row1 = [types.InlineKeyboardButton(RARITY_CONFIG[r]['emoji'], callback_data=f"mkt_browse:{r}")
            for r in ["Rare", "Epic", "Legendary"]]
    row2 = [types.InlineKeyboardButton(RARITY_CONFIG[r]['emoji'], callback_data=f"mkt_browse:{r}")
            for r in ["Mythic", "Divine", "Secret"]]
    markup.row(*row1)
    markup.row(*row2)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_game_menu"))
    return markup


@bot.callback_query_handler(func=lambda call: call.data == "menu_market")
def market_menu(call):
    bot.answer_callback_query(call.id)
    listings = get_market_listings(limit=5)
    txt = (f"🏪 <b>Торговая площадка</b>\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"Активных предложений: <b>{len(listings)}</b>\n\n"
           f"Фильтруй по редкости или смотри все:")
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=get_market_menu_markup(), parse_mode="HTML")


# --- ПРОСМОТР ЛИСТИНГОВ ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("mkt_browse:"))
def market_browse(call):
    bot.answer_callback_query(call.id)
    rarity_filter = call.data.split(":")[1]
    rarity_filter = None if rarity_filter == "all" else rarity_filter

    listings = get_market_listings(rarity_filter=rarity_filter, limit=20)

    if not listings:
        filter_name = RARITY_CONFIG.get(rarity_filter, {}).get('ru', 'все') if rarity_filter else "все"
        txt = f"🏪 <b>Торговая площадка</b>\n\nНет предложений ({filter_name})."
    else:
        filter_name = RARITY_CONFIG.get(rarity_filter, {}).get('ru', 'все') if rarity_filter else "все"
        txt = f"🏪 <b>Торговая площадка</b> [{filter_name}]\n➖➖➖➖➖➖➖➖\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        for listing in listings:
            card = listing.get('cards') or {}
            seller_name = (listing.get('users') or {}).get('first_name', '?')
            emoji = RARITY_CONFIG.get(card.get('rarity', ''), {}).get('emoji', '🃏')
            rarity_ru = RARITY_CONFIG.get(card.get('rarity', ''), {}).get('ru', '?')
            txt += (f"{emoji} <b>{card.get('name', '?')}</b> [{rarity_ru}]\n"
                    f"   💰 {listing['price']} монет | Продавец: {seller_name}\n\n")
            markup.add(types.InlineKeyboardButton(
                f"💰 Купить «{card.get('name', '?')}» за {listing['price']}",
                callback_data=f"mkt_buy:{listing['id']}"
            ))
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="menu_market"))
        safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                          txt, reply_markup=markup, parse_mode="HTML")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="menu_market"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup, parse_mode="HTML")


# --- КУПИТЬ ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("mkt_buy:"))
def market_buy(call):
    listing_id = int(call.data.split(":")[1])
    user_id = call.from_user.id
    success, msg = buy_from_market(user_id, listing_id)
    bot.answer_callback_query(call.id, msg, show_alert=True)
    if success:
        call.data = "mkt_browse:all"
        market_browse(call)


# --- МОИ ЛИСТИНГИ ---

@bot.callback_query_handler(func=lambda call: call.data == "mkt_my")
def market_my(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    listings = get_my_market_listings(user_id)

    if not listings:
        txt = "🎴 <b>Мои листинги</b>\n\nУ вас нет активных предложений."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="menu_market"))
        safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                          txt, reply_markup=markup, parse_mode="HTML")
        return

    txt = "🎴 <b>Мои листинги</b>\n➖➖➖➖➖➖➖➖\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)
    for listing in listings:
        card = listing.get('cards') or {}
        emoji = RARITY_CONFIG.get(card.get('rarity', ''), {}).get('emoji', '🃏')
        txt += f"{emoji} <b>{card.get('name', '?')}</b> — 💰 {listing['price']}\n"
        markup.add(types.InlineKeyboardButton(
            f"❌ Снять «{card.get('name', '?')}»",
            callback_data=f"mkt_cancel:{listing['id']}"
        ))

    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="menu_market"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("mkt_cancel:"))
def market_cancel(call):
    listing_id = int(call.data.split(":")[1])
    user_id = call.from_user.id
    success, msg = cancel_market_listing(user_id, listing_id)
    bot.answer_callback_query(call.id, msg, show_alert=True)
    market_my(call)


# --- ВЫСТАВИТЬ КАРТЫ НА ПРОДАЖУ (мультивыбор) ---
# Можно отметить сразу несколько РАЗНЫХ карт (любых редкостей) галочками,
# затем бот по очереди спрашивает количество и цену для каждой отмеченной —
# не нужно каждый раз заново заходить в раздел продажи.

MKT_SELECT_PAGE_SIZE = 10


def _get_sellable_inventory(user_id):
    inv_res = get_user_inventory(user_id)
    return [i for i in (inv_res.data or []) if i.get('cards') and i.get('count', 0) > 0]


@bot.callback_query_handler(func=lambda call: call.data == "mkt_sell_start")
def market_sell_start(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    _listing_state[user_id] = {'selected': set()}
    _render_sell_select(call.message.chat.id, call.message.message_id, user_id, page=0)


def _render_sell_select(chat_id, message_id, user_id, page=0):
    inv_data = _get_sellable_inventory(user_id)
    if not inv_data:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="menu_market"))
        safe_edit_message(bot, chat_id, message_id, "У вас нет карт для продажи.",
                          reply_markup=markup, parse_mode="HTML")
        return

    selected = _listing_state.get(user_id, {}).get('selected', set())
    total = len(inv_data)
    max_page = max(0, (total - 1) // MKT_SELECT_PAGE_SIZE)
    page = max(0, min(page, max_page))
    start = page * MKT_SELECT_PAGE_SIZE
    page_items = inv_data[start:start + MKT_SELECT_PAGE_SIZE]

    markup = types.InlineKeyboardMarkup(row_width=1)
    for item in page_items:
        card = item['cards']
        emoji = RARITY_CONFIG.get(card.get('rarity', ''), {}).get('emoji', '🃏')
        mark = "✅ " if card['id'] in selected else ""
        markup.add(types.InlineKeyboardButton(
            f"{mark}{emoji} {card['name']} (x{item['count']})",
            callback_data=f"mkt_toggle:{card['id']}:{page}"
        ))

    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"mkt_sellpage:{page - 1}"))
    nav.append(types.InlineKeyboardButton(f"{page + 1}/{max_page + 1}", callback_data="ignore"))
    if page < max_page:
        nav.append(types.InlineKeyboardButton("➡️", callback_data=f"mkt_sellpage:{page + 1}"))
    if len(nav) > 1:
        markup.row(*nav)

    if selected:
        markup.add(types.InlineKeyboardButton(f"✅ Готово ({len(selected)} выбрано)", callback_data="mkt_sell_confirm"))
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="menu_market"))

    txt = (f"🏷 <b>Выберите карты для продажи</b> (всего карт: {total})\n"
           f"Нажимайте на карты, чтобы отметить ✅ — можно выбрать сразу несколько разных карт.")
    safe_edit_message(bot, chat_id, message_id, txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("mkt_toggle:"))
def market_toggle_cb(call):
    bot.answer_callback_query(call.id)
    _, card_id, page = call.data.split(":")
    card_id = int(card_id)
    user_id = call.from_user.id
    state = _listing_state.setdefault(user_id, {'selected': set()})
    selected = state.setdefault('selected', set())
    if card_id in selected:
        selected.discard(card_id)
    else:
        selected.add(card_id)
    _render_sell_select(call.message.chat.id, call.message.message_id, user_id, page=int(page))


@bot.callback_query_handler(func=lambda call: call.data.startswith("mkt_sellpage:"))
def market_sellpage_cb(call):
    bot.answer_callback_query(call.id)
    page = int(call.data.split(":")[1])
    _render_sell_select(call.message.chat.id, call.message.message_id, call.from_user.id, page=page)


@bot.callback_query_handler(func=lambda call: call.data == "mkt_sell_confirm")
def market_sell_confirm(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    state = _listing_state.get(user_id, {})
    selected = list(state.get('selected', set()))
    if not selected:
        bot.answer_callback_query(call.id, "Ничего не выбрано", show_alert=True)
        return

    _listing_state[user_id] = {'queue': selected, 'results': []}
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    _start_next_sell_item(call.message.chat.id, user_id)


def _start_next_sell_item(chat_id, user_id):
    state = _listing_state.get(user_id)
    if not state:
        return
    queue = state.get('queue', [])
    if not queue:
        _finish_sell_queue(chat_id, user_id)
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
        _start_next_sell_item(chat_id, user_id)
        return

    state['current_card_id'] = card_id
    state['current_card_name'] = card_name
    state['current_have'] = have

    msg = bot.send_message(chat_id,
                           f"🔢 «{card_name}» (у вас {have} шт) — сколько копий выставить на продажу?\n"
                           f"Введите число от 1 до {have}.\n\nПропустить эту карту — /skip")
    register_next_step_handler_for_user(bot, msg, user_id, _queue_qty_step)


def _queue_qty_step(message):
    user_id = message.from_user.id
    state = _listing_state.get(user_id)
    if not state:
        return
    if message.text and message.text.strip() == '/skip':
        state['results'].append((state.get('current_card_name', '?'), 0))
        state['queue'] = state['queue'][1:]
        _start_next_sell_item(message.chat.id, user_id)
        return
    try:
        qty = int(message.text.strip())
        have = state.get('current_have', 1)
        if qty < 1 or qty > have:
            raise ValueError
    except (ValueError, AttributeError):
        msg = bot.send_message(message.chat.id, f"❌ Введите число от 1 до {state.get('current_have', 1)}, либо /skip:")
        register_next_step_handler_for_user(bot, msg, user_id, _queue_qty_step)
        return

    state['current_qty'] = qty
    msg = bot.send_message(message.chat.id, "💰 Цена за штуку в монетах (целое число), либо /skip:")
    register_next_step_handler_for_user(bot, msg, user_id, _queue_price_step)


def _queue_price_step(message):
    user_id = message.from_user.id
    state = _listing_state.get(user_id)
    if not state:
        return
    if message.text and message.text.strip() == '/skip':
        state['results'].append((state.get('current_card_name', '?'), 0))
        state['queue'] = state['queue'][1:]
        _start_next_sell_item(message.chat.id, user_id)
        return
    try:
        price = int(message.text.strip())
        if price < 1:
            raise ValueError
    except (ValueError, AttributeError):
        msg = bot.send_message(message.chat.id, "❌ Введите корректную цену (> 0), либо /skip:")
        register_next_step_handler_for_user(bot, msg, user_id, _queue_price_step)
        return

    card_id = state['current_card_id']
    qty = state.get('current_qty', 1)
    listed = 0
    for _ in range(qty):
        success, _result = list_card_on_market(user_id, card_id, price)
        if success:
            listed += 1
        else:
            break  # копии кончились (или гонка с другим действием) — не пытаемся дальше

    state['results'].append((state.get('current_card_name', '?'), listed))
    state['queue'] = state['queue'][1:]
    _start_next_sell_item(message.chat.id, user_id)


def _finish_sell_queue(chat_id, user_id):
    state = _listing_state.pop(user_id, {})
    results = state.get('results', [])
    listed_lines = [f"• {name}: {cnt} шт" for name, cnt in results if cnt]
    skipped_names = [name for name, cnt in results if not cnt]

    txt = "✅ <b>Выставление на продажу завершено!</b>\n\n"
    txt += ("\n".join(listed_lines) if listed_lines else "Ничего не выставлено.")
    if skipped_names:
        txt += f"\n\n⏭ Пропущено: {', '.join(skipped_names)}"

    bot.send_message(chat_id, txt, parse_mode="HTML")
