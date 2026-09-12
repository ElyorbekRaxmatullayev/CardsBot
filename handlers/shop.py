from telebot import types

from config import PACK_CONFIG, SHOP_GEMS_PACKAGES, PREMIUM_COST_GEMS, PREMIUM_DAYS, DROP_COOLDOWN, DROP_COOLDOWN_PREMIUM
from database import (get_user_data, update_coins, update_gems, add_pack_to_user, grant_premium, is_premium,
                      update_task_progress, get_all_cards, add_card_to_user, on_card_obtained)
from loader import bot, supabase
from utils import safe_edit_message
import random


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

def _get_auto_renew_status(user):
    """Возвращает статус автопродления из данных пользователя"""
    val = user.get('premium_auto_renew')
    return val if val is not None else True  # по умолчанию включено


@bot.callback_query_handler(func=lambda call: call.data == "shop_premium")
def shop_premium_menu(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user = get_user_data(user_id)
    gems = user.get('gems', 0) or 0
    auto_renew = _get_auto_renew_status(user)

    if is_premium(user):
        until = user['premium_until'].replace('T', ' ').split('.')[0].split('+')[0]
        status_txt = f"✅ Активен до {until} UTC"
        renew_txt = "🔄 Автопродление: ✅ Вкл" if auto_renew else "🔄 Автопродление: ❌ Выкл"
    else:
        status_txt = "❌ Не активен"
        renew_txt = ""

    cooldown_min = int(DROP_COOLDOWN_PREMIUM * 60)
    h, m = divmod(cooldown_min, 60)
    cooldown_str = f"{h}ч {m}мин" if h > 0 else f"{m}мин"

    txt = (f"🌟 <b>Premium-подписка</b>\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"Статус: {status_txt}\n"
           f"{renew_txt}\n\n"
           f"Что даёт Premium:\n"
           f"• Кулдаун карты: {cooldown_str} (вместо {DROP_COOLDOWN}ч)\n"
           f"• 🎁 5 бесплатных карт при покупке\n\n"
           f"💎 Ваши Gems: <b>{gems}</b>\n"
           f"💰 Цена: <b>{PREMIUM_COST_GEMS} 💎 / {PREMIUM_DAYS} дней</b>")

    markup = types.InlineKeyboardMarkup()
    if not is_premium(user):
        markup.add(types.InlineKeyboardButton(
            f"🌟 Купить Premium — {PREMIUM_COST_GEMS} 💎",
            callback_data="shop_buy_premium"
        ))
    else:
        # Кнопка переключения автопродления
        toggle_label = "🔕 Отключить автопродление" if auto_renew else "🔔 Включить автопродление"
        markup.add(types.InlineKeyboardButton(toggle_label, callback_data="shop_toggle_autorenew"))

    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="menu_shop"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "shop_buy_premium")
def shop_buy_premium(call):
    user_id = call.from_user.id
    user = get_user_data(user_id)
    gems = user.get('gems', 0) or 0

    if gems < PREMIUM_COST_GEMS:
        bot.answer_callback_query(call.id,
                                  f"Недостаточно Gems! Нужно {PREMIUM_COST_GEMS} 💎\n"
                                  f"У вас: {gems} 💎", show_alert=True)
        return

    # Списываем gems
    update_gems(user_id, -PREMIUM_COST_GEMS)
    # Выдаём Premium
    grant_premium(user_id, PREMIUM_DAYS)
    # Включаем автопродление по умолчанию
    supabase.table("users").update({"premium_auto_renew": True}).eq("telegram_id", user_id).execute()

    # 🎁 Дарим 5 бесплатных карт
    cards_all = get_all_cards()
    gift_names = []
    if cards_all:
        for _ in range(5):
            card = random.choice(cards_all)
            is_dup, _ = add_card_to_user(user_id, card['id'])
            on_card_obtained(user_id, card, is_dup)
            gift_names.append(card['name'])

    gift_txt = "\n".join(f"🎴 {n}" for n in gift_names) if gift_names else "—"

    bot.answer_callback_query(call.id, f"✅ Premium активирован на {PREMIUM_DAYS} дней!", show_alert=True)

    # Показываем подтверждение
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔕 Отключить автопродление", callback_data="shop_toggle_autorenew"))
    markup.add(types.InlineKeyboardButton("🔙 В магазин", callback_data="menu_shop"))

    txt = (f"🌟 <b>Premium активирован!</b>\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"📅 Срок: {PREMIUM_DAYS} дней\n\n"
           f"🎁 Подарок — 5 бесплатных карт:\n{gift_txt}\n\n"
           f"🔄 <b>Автопродление включено.</b>\n"
           f"Каждый месяц будет списываться {PREMIUM_COST_GEMS} 💎 автоматически.\n"
           f"Вы можете отключить это кнопкой ниже.")

    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "shop_toggle_autorenew")
def toggle_autorenew(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user = get_user_data(user_id)
    current = _get_auto_renew_status(user)
    new_val = not current
    supabase.table("users").update({"premium_auto_renew": new_val}).eq("telegram_id", user_id).execute()
    status = "✅ включено" if new_val else "❌ выключено"
    bot.answer_callback_query(call.id, f"Автопродление {status}", show_alert=True)
    # Обновляем экран
    shop_premium_menu(call)
