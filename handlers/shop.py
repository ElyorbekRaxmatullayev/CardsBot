from telebot import types

from config import PACK_CONFIG, SHOP_GEMS_PACKAGES, PREMIUM_COST, PREMIUM_DAYS, DROP_COOLDOWN, DROP_COOLDOWN_PREMIUM
from database import (get_user_data, update_coins, update_gems, add_pack_to_user, grant_premium, is_premium,
                      update_task_progress)
from loader import bot
from utils import safe_edit_message


# --- МАГАЗИН: ГЛАВНОЕ МЕНЮ ---

def get_shop_menu_markup():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📦 Паки", callback_data="shop_packs"),
        types.InlineKeyboardButton("💎 Gems", callback_data="shop_gems"),
    )
    markup.add(types.InlineKeyboardButton("🌟 Premium", callback_data="shop_premium"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_game_menu"))
    return markup


@bot.callback_query_handler(func=lambda call: call.data == "menu_shop")
def shop_main(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user = get_user_data(user_id)
    gems = user.get('gems', 0) or 0

    txt = (f"🏪 <b>Магазин</b>\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"💰 Монеты: <b>{user['coins']}</b>\n"
           f"💎 Gems: <b>{gems}</b>\n\n"
           f"Выберите категорию:")
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=get_shop_menu_markup(), parse_mode="HTML")


# --- МАГАЗИН: ПАКИ ---

@bot.callback_query_handler(func=lambda call: call.data == "shop_packs")
def shop_packs(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user = get_user_data(user_id)
    gems = user.get('gems', 0) or 0

    txt = (f"📦 <b>Паки в магазине</b>\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"💰 {user['coins']} монет | 💎 {gems} Gems\n\n")

    markup = types.InlineKeyboardMarkup()
    for pack_key, cfg in PACK_CONFIG.items():
        price_parts = []
        if cfg['price_coins'] > 0:
            price_parts.append(f"💰{cfg['price_coins']}")
        if cfg['price_gems'] > 0:
            price_parts.append(f"💎{cfg['price_gems']}")
        price_str = " / ".join(price_parts) if price_parts else "🎁 Бесплатно"
        markup.add(types.InlineKeyboardButton(
            f"{cfg['name']} — {price_str}",
            callback_data=f"shop_buy_pack:{pack_key}"
        ))

    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="menu_shop"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("shop_buy_pack:"))
def shop_buy_pack(call):
    pack_type = call.data.split(":")[1]
    cfg = PACK_CONFIG.get(pack_type)
    if not cfg:
        return
    user_id = call.from_user.id
    user = get_user_data(user_id)
    gems = user.get('gems', 0) or 0

    # Приоритет: сначала Gems, потом Coins
    if cfg['price_gems'] > 0:
        if gems < cfg['price_gems']:
            bot.answer_callback_query(call.id,
                                      f"Недостаточно Gems! Нужно {cfg['price_gems']} 💎\n"
                                      f"У вас: {gems} Gems", show_alert=True)
            return
        update_gems(user_id, -cfg['price_gems'])
    elif cfg['price_coins'] > 0:
        if user['coins'] < cfg['price_coins']:
            bot.answer_callback_query(call.id,
                                      f"Недостаточно монет! Нужно {cfg['price_coins']} 💰\n"
                                      f"У вас: {user['coins']}", show_alert=True)
            return
        update_coins(user_id, -cfg['price_coins'])
        update_task_progress(user_id, "spend_coins", "weekly", increment=cfg['price_coins'])
    else:
        bot.answer_callback_query(call.id, "Этот пак нельзя купить здесь", show_alert=True)
        return

    add_pack_to_user(user_id, pack_type)
    bot.answer_callback_query(call.id, f"✅ {cfg['name']} добавлен в инвентарь!")
    # Обновляем экран
    shop_packs(call)


# --- МАГАЗИН: GEMS ---

@bot.callback_query_handler(func=lambda call: call.data == "shop_gems")
def shop_gems_menu(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user = get_user_data(user_id)
    gems = user.get('gems', 0) or 0

    txt = (f"💎 <b>Купить Gems</b>\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"💰 Ваши монеты: <b>{user['coins']}</b>\n"
           f"💎 Ваши Gems: <b>{gems}</b>\n\n"
           f"Gems — редкая премиум-валюта.\n"
           f"Используется для покупки Legendary и Mythic паков.\n\n"
           f"Выберите пакет:")

    markup = types.InlineKeyboardMarkup()
    for i, pkg in enumerate(SHOP_GEMS_PACKAGES):
        markup.add(types.InlineKeyboardButton(pkg['label'], callback_data=f"shop_buy_gems:{i}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="menu_shop"))

    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("shop_buy_gems:"))
def shop_buy_gems(call):
    idx = int(call.data.split(":")[1])
    if idx >= len(SHOP_GEMS_PACKAGES):
        return
    pkg = SHOP_GEMS_PACKAGES[idx]
    user_id = call.from_user.id
    user = get_user_data(user_id)

    if user['coins'] < pkg['price_coins']:
        bot.answer_callback_query(call.id,
                                  f"Недостаточно монет! Нужно {pkg['price_coins']} 💰", show_alert=True)
        return

    update_coins(user_id, -pkg['price_coins'])
    update_task_progress(user_id, "spend_coins", "weekly", increment=pkg['price_coins'])
    update_gems(user_id, pkg['gems'])
    bot.answer_callback_query(call.id, f"✅ Получено {pkg['gems']} 💎 Gems!")
    shop_gems_menu(call)


# --- МАГАЗИН: PREMIUM ---

@bot.callback_query_handler(func=lambda call: call.data == "shop_premium")
def shop_premium_menu(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user = get_user_data(user_id)

    if is_premium(user):
        until = user['premium_until'].replace('T', ' ').split('.')[0].split('+')[0]
        status_txt = f"✅ Активен до {until} UTC"
    else:
        status_txt = "❌ Не активен"

    txt = (f"🌟 <b>Premium-подписка</b>\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"Статус: {status_txt}\n\n"
           f"Что даёт Premium:\n"
           f"• Кулдаун получения карты сокращён до {DROP_COOLDOWN_PREMIUM}ч (вместо {DROP_COOLDOWN}ч)\n\n"
           f"💰 Ваши монеты: <b>{user['coins']}</b>")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        f"🌟 Купить на {PREMIUM_DAYS} дн. — {PREMIUM_COST} 💰",
        callback_data="shop_buy_premium"
    ))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="menu_shop"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "shop_buy_premium")
def shop_buy_premium(call):
    user_id = call.from_user.id
    user = get_user_data(user_id)

    if user['coins'] < PREMIUM_COST:
        bot.answer_callback_query(call.id, f"Недостаточно монет! Нужно {PREMIUM_COST} 💰", show_alert=True)
        return

    update_coins(user_id, -PREMIUM_COST)
    update_task_progress(user_id, "spend_coins", "weekly", increment=PREMIUM_COST)
    grant_premium(user_id, PREMIUM_DAYS)
    bot.answer_callback_query(call.id, f"✅ Premium активирован на {PREMIUM_DAYS} дней!", show_alert=True)
    shop_premium_menu(call)
