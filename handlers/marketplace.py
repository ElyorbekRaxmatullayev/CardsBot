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


# --- ВЫСТАВИТЬ КАРТУ НА ПРОДАЖУ ---

@bot.callback_query_handler(func=lambda call: call.data == "mkt_sell_start")
def market_sell_start(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    inv_res = get_user_inventory(user_id)
    inv_data = inv_res.data if inv_res.data else []

    if not inv_data:
        bot.answer_callback_query(call.id, "У вас нет карт для продажи.", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for item in inv_data[:15]:
        card = item.get('cards', {})
        if not card:
            continue
        emoji = RARITY_CONFIG.get(card.get('rarity', ''), {}).get('emoji', '🃏')
        value = RARITY_CONFIG.get(card.get('rarity', ''), {}).get('value', 0)
        markup.add(types.InlineKeyboardButton(
            f"{emoji} {card['name']} (x{item['count']}) | базовая цена {value}",
            callback_data=f"mkt_sell_card:{card['id']}"
        ))

    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="menu_market"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      "🏷 <b>Выберите карту для продажи:</b>",
                      reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("mkt_sell_card:"))
def market_sell_card(call):
    card_id = int(call.data.split(":")[1])
    user_id = call.from_user.id
    _listing_state[user_id] = {'card_id': card_id}

    msg = bot.send_message(call.message.chat.id,
                           "💰 Введите цену продажи в монетах (целое число):\n\nОтмена — /cancel")
    register_next_step_handler_for_user(bot, msg, user_id, _market_sell_set_price)


def _market_sell_set_price(message):
    user_id = message.from_user.id
    if message.text == '/cancel':
        _listing_state.pop(user_id, None)
        bot.send_message(message.chat.id, "Отменено.")
        return

    try:
        price = int(message.text.strip())
        if price < 1:
            raise ValueError
    except:
        msg = bot.send_message(message.chat.id, "❌ Введите корректную цену (число > 0):")
        register_next_step_handler_for_user(bot, msg, user_id, _market_sell_set_price)
        return

    state = _listing_state.get(user_id, {})
    card_id = state.get('card_id')
    if not card_id:
        bot.send_message(message.chat.id, "Ошибка. Начните заново.")
        return

    success, result = list_card_on_market(user_id, card_id, price)
    if success:
        bot.send_message(message.chat.id, f"✅ Карта выставлена на продажу за 💰 {price} монет!")
    else:
        bot.send_message(message.chat.id, f"❌ Ошибка: {result}")

    _listing_state.pop(user_id, None)
