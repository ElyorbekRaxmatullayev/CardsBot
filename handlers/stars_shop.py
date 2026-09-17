import random

from telebot import types
from telebot.types import LabeledPrice

from config import (STARS_GEMS_PACKAGES, STARS_COINS_PACKAGES, STARS_CARD_PRICES,
                    STARS_VIP_PACKAGES, RARITY_CONFIG)
from database import (get_all_cards, add_card_to_user, on_card_obtained, get_card_by_id,
                      update_gems, update_coins, grant_premium, grant_premium_bonus_packs,
                      record_star_payment, get_limited_cards_with_price)
from loader import bot, supabase
from utils import safe_edit_message

LIMITED_PAGE_SIZE = 8


# --- ГЛАВНОЕ МЕНЮ ---

def get_stars_shop_markup():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("💎 Алмазы", callback_data="stars_gems"),
        types.InlineKeyboardButton("🪙 Монеты", callback_data="stars_coins"),
    )
    markup.row(
        types.InlineKeyboardButton("🃏 Карты", callback_data="stars_cards"),
        types.InlineKeyboardButton("🎴 Лимитные", callback_data="stars_limited:0"),
    )
    markup.add(types.InlineKeyboardButton("👑 Premium (VIP)", callback_data="stars_vip"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="menu_shop"))
    return markup


@bot.callback_query_handler(func=lambda call: call.data == "stars_shop_menu")
def stars_shop_menu(call):
    bot.answer_callback_query(call.id)
    txt = ("⭐ <b>Магазин за Telegram Stars</b>\n"
           "➖➖➖➖➖➖➖➖\n"
           "Оплата прямо внутри Telegram — без сторонних сайтов и карт.\n\n"
           "Выберите категорию:")
    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt,
                      reply_markup=get_stars_shop_markup(), parse_mode="HTML")


# --- АЛМАЗЫ ---

@bot.callback_query_handler(func=lambda call: call.data == "stars_gems")
def stars_gems_menu(call):
    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup()
    for gems, stars in STARS_GEMS_PACKAGES:
        markup.add(types.InlineKeyboardButton(f"💎 {gems} — {stars} ⭐",
                                              callback_data=f"stars_buy_gems:{gems}:{stars}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="stars_shop_menu"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      "💎 <b>Алмазы за Stars</b>\n\nВыберите пакет:", reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("stars_buy_gems:"))
def stars_buy_gems(call):
    bot.answer_callback_query(call.id)
    _, gems, stars = call.data.split(":")
    bot.send_invoice(
        call.message.chat.id,
        title=f"{gems} 💎 Gems",
        description=f"Пополнение баланса на {gems} Gems в CardsBot",
        invoice_payload=f"gems:{gems}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{gems} Gems", amount=int(stars))],
    )


# --- МОНЕТЫ ---

@bot.callback_query_handler(func=lambda call: call.data == "stars_coins")
def stars_coins_menu(call):
    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup()
    for coins, stars in STARS_COINS_PACKAGES:
        markup.add(types.InlineKeyboardButton(f"🪙 {coins} — {stars} ⭐",
                                              callback_data=f"stars_buy_coins:{coins}:{stars}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="stars_shop_menu"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      "🪙 <b>Монеты за Stars</b>\n\nВыберите пакет:", reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("stars_buy_coins:"))
def stars_buy_coins(call):
    bot.answer_callback_query(call.id)
    _, coins, stars = call.data.split(":")
    bot.send_invoice(
        call.message.chat.id,
        title=f"{coins} 🪙 монет",
        description=f"Пополнение баланса на {coins} монет в CardsBot",
        invoice_payload=f"coins:{coins}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{coins} монет", amount=int(stars))],
    )


# --- КАРТЫ ПО РЕДКОСТИ (случайная карта, как обычный дроп) ---

@bot.callback_query_handler(func=lambda call: call.data == "stars_cards")
def stars_cards_menu(call):
    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup()
    for rarity, stars in STARS_CARD_PRICES.items():
        r_cfg = RARITY_CONFIG.get(rarity, {})
        markup.add(types.InlineKeyboardButton(
            f"{r_cfg.get('emoji', '🃏')} {r_cfg.get('ru', rarity)} — {stars} ⭐",
            callback_data=f"stars_buy_card:{rarity}:{stars}"
        ))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="stars_shop_menu"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      "🃏 <b>Карта за Stars</b>\n\nВыпадает случайная карта выбранной редкости "
                      "(как обычный дроп/пак). Выберите редкость:",
                      reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("stars_buy_card:"))
def stars_buy_card(call):
    bot.answer_callback_query(call.id)
    _, rarity, stars = call.data.split(":")
    r_cfg = RARITY_CONFIG.get(rarity, {})
    bot.send_invoice(
        call.message.chat.id,
        title=f"{r_cfg.get('emoji', '🃏')} Карта: {r_cfg.get('ru', rarity)}",
        description="Случайная карта выбранной редкости",
        invoice_payload=f"card:{rarity}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"Карта {rarity}", amount=int(stars))],
    )


# --- ЛИМИТНЫЕ КАРТЫ (цена задаётся админом индивидуально на каждую) ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("stars_limited:"))
def stars_limited_menu(call):
    bot.answer_callback_query(call.id)
    page = int(call.data.split(":")[1])
    cards = get_limited_cards_with_price()

    markup = types.InlineKeyboardMarkup(row_width=1)
    if not cards:
        txt = "🎴 <b>Лимитные карты</b>\n\nПока нет лимитных карт в продаже."
    else:
        total = len(cards)
        max_page = max(0, (total - 1) // LIMITED_PAGE_SIZE)
        page = max(0, min(page, max_page))
        start = page * LIMITED_PAGE_SIZE
        page_items = cards[start:start + LIMITED_PAGE_SIZE]

        txt = f"🎴 <b>Лимитные карты</b> (всего: {total})\n\nВыберите карту:"
        for c in page_items:
            markup.add(types.InlineKeyboardButton(
                f"🎴 {c['name']} — {c['stars_price']} ⭐",
                callback_data=f"stars_buy_limited:{c['id']}"
            ))

        nav = []
        if page > 0:
            nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"stars_limited:{page - 1}"))
        nav.append(types.InlineKeyboardButton(f"{page + 1}/{max_page + 1}", callback_data="ignore"))
        if page < max_page:
            nav.append(types.InlineKeyboardButton("➡️", callback_data=f"stars_limited:{page + 1}"))
        if len(nav) > 1:
            markup.row(*nav)

    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="stars_shop_menu"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt,
                      reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("stars_buy_limited:"))
def stars_buy_limited(call):
    card_id = int(call.data.split(":")[1])
    card = get_card_by_id(card_id)
    if not card or not card.get('stars_price'):
        bot.answer_callback_query(call.id, "❌ Эта карта больше не продаётся", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    bot.send_invoice(
        call.message.chat.id,
        title=f"🎴 {card['name']}",
        description=card.get('description') or "Лимитная карта",
        invoice_payload=f"limited:{card_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=card['name'], amount=card['stars_price'])],
    )


# --- PREMIUM (VIP) ---

@bot.callback_query_handler(func=lambda call: call.data == "stars_vip")
def stars_vip_menu(call):
    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup()
    for days, stars in STARS_VIP_PACKAGES:
        markup.add(types.InlineKeyboardButton(f"👑 Premium {days} дн. — {stars} ⭐",
                                              callback_data=f"stars_buy_vip:{days}:{stars}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="stars_shop_menu"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      "👑 <b>Premium за Stars</b>\n\n"
                      "Ускоряет получение карт и даёт одноразовый бонус паков при первой покупке.\n\n"
                      "Выберите срок:", reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("stars_buy_vip:"))
def stars_buy_vip(call):
    bot.answer_callback_query(call.id)
    _, days, stars = call.data.split(":")
    bot.send_invoice(
        call.message.chat.id,
        title=f"👑 Premium на {days} дней",
        description="Ускоренное получение карт + бонус паков при первой покупке",
        invoice_payload=f"vip:{days}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"Premium {days} дней", amount=int(stars))],
    )


# --- ОПЛАТА: ПОДТВЕРЖДЕНИЕ И ЗАЧИСЛЕНИЕ ---

@bot.pre_checkout_query_handler(func=lambda q: True)
def handle_pre_checkout(pre_checkout_query):
    """Последняя проверка перед списанием звёзд у пользователя — сюда важно
    не пускать заведомо невалидные/устаревшие покупки (например лимитную
    карту, у которой админ успел убрать цену)."""
    parts = pre_checkout_query.invoice_payload.split(":")
    ok = False
    try:
        if parts[0] in ("gems", "coins", "vip") and len(parts) == 2:
            ok = int(parts[1]) > 0
        elif parts[0] == "card" and len(parts) == 2:
            ok = parts[1] in STARS_CARD_PRICES
        elif parts[0] == "limited" and len(parts) == 2:
            card = get_card_by_id(int(parts[1]))
            ok = bool(card and card.get('stars_price'))
    except (ValueError, IndexError):
        ok = False
    bot.answer_pre_checkout_query(
        pre_checkout_query.id, ok=ok,
        error_message=None if ok else "Этот товар недоступен — попробуйте выбрать его снова в магазине.")


@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    """Звёзды списаны Telegram'ом ДО этого хендлера — здесь только начисляем
    покупку. record_star_payment — защита от повторного зачисления, если
    Telegram по какой-то причине пришлёт это уведомление дважды."""
    sp = message.successful_payment
    user_id = message.from_user.id
    charge_id = sp.telegram_payment_charge_id
    payload = sp.invoice_payload
    stars = sp.total_amount

    if not record_star_payment(charge_id, user_id, payload, stars):
        return

    parts = payload.split(":")
    kind = parts[0]

    if kind == "gems":
        amount = int(parts[1])
        update_gems(user_id, amount)
        bot.send_message(message.chat.id, f"✅ Спасибо за покупку! Начислено {amount} 💎 Gems.")

    elif kind == "coins":
        amount = int(parts[1])
        update_coins(user_id, amount)
        bot.send_message(message.chat.id, f"✅ Спасибо за покупку! Начислено {amount} 🪙 монет.")

    elif kind == "card":
        rarity = parts[1]
        pool = [c for c in (get_all_cards() or []) if c['rarity'] == rarity]
        if pool:
            card = random.choice(pool)
            is_dup, count = add_card_to_user(user_id, card['id'])
            on_card_obtained(user_id, card, is_dup)
            emoji = RARITY_CONFIG.get(rarity, {}).get('emoji', '🃏')
            dup_txt = f" (дубликат, x{count})" if is_dup else ""
            bot.send_message(message.chat.id,
                             f"✅ Спасибо за покупку! Получена карта: {emoji} <b>{card['name']}</b>{dup_txt}",
                             parse_mode="HTML")

    elif kind == "limited":
        card_id = int(parts[1])
        card = get_card_by_id(card_id)
        if card:
            is_dup, count = add_card_to_user(user_id, card_id)
            on_card_obtained(user_id, card, is_dup)
            dup_txt = f" (дубликат, x{count})" if is_dup else ""
            bot.send_message(message.chat.id,
                             f"✅ Спасибо за покупку! Получена лимитная карта: 🎴 <b>{card['name']}</b>{dup_txt}",
                             parse_mode="HTML")

    elif kind == "vip":
        days = int(parts[1])
        grant_premium(user_id, days)
        # Автопродление за Gems выключаем по умолчанию для покупки за Stars —
        # иначе через месяц у пользователя молча списались бы Gems, хотя он
        # платил звёздами и мог их вообще не копить
        supabase.table("users").update({"premium_auto_renew": False}).eq("telegram_id", user_id).execute()
        bonus_granted = grant_premium_bonus_packs(user_id)
        bonus_txt = "\n🎁 Плюс бонус паков за первую покупку Premium!" if bonus_granted else ""
        bot.send_message(message.chat.id,
                         f"✅ Спасибо за покупку! Premium активирован на {days} дней.{bonus_txt}",
                         parse_mode="HTML")
