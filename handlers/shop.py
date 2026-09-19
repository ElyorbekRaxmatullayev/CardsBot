from telebot import types

from config import PACK_CONFIG, DROP_COOLDOWN, DROP_COOLDOWN_PREMIUM, STARS_VIP_PACKAGES
from database import get_user_data, update_coins, update_gems, add_pack_to_user, is_premium, update_task_progress
from loader import bot, supabase
from utils import safe_edit_message, safe_send_message, reply_match


# --- МАГАЗИН: ГЛАВНОЕ МЕНЮ ---
# Обмен Gems<->монеты и покупка Premium за Gems убраны — теперь всё, что
# продаётся за реальные деньги (Gems, монеты, карты, Premium), продаётся
# ТОЛЬКО за Telegram Stars (см. handlers/stars_shop.py и кнопку "👑 Premium"
# в основной reply-клавиатуре). Здесь остаётся только покупка паков за
# внутриигровые монеты/Gems, добытые в самой игре.

def get_shop_menu_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📦 Паки", callback_data="shop_packs"))
    markup.add(types.InlineKeyboardButton("⭐ Магазин Stars", callback_data="stars_shop_menu"))
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


# --- PREMIUM: ОТДЕЛЬНАЯ КНОПКА В REPLY-КЛАВИАТУРЕ, ОПЛАТА ТОЛЬКО ЗА STARS ---
# Покупка за Gems убрана целиком — единственный способ купить/продлить
# Premium теперь Telegram Stars (см. handlers/stars_shop.py, stars_buy_vip).
# Автопродление за Gems оставлено только как переключатель для тех, у кого
# оно ещё включено с прошлых покупок — новых включений через эту кнопку нет.

def _get_auto_renew_status(user):
    """Возвращает статус автопродления из данных пользователя"""
    val = user.get('premium_auto_renew')
    return val if val is not None else True  # по умолчанию включено


@bot.message_handler(func=reply_match("👑 Premium", "Premium"))
def premium_menu_reply(message, user_id=None):
    # user_id передаётся явно при возврате сюда из callback (там message —
    # сообщение БОТА, и message.from_user внутри него — это сам бот, а не игрок)
    user_id = user_id or message.from_user.id
    user = get_user_data(user_id)
    auto_renew = _get_auto_renew_status(user)

    if is_premium(user):
        until = user['premium_until'].replace('T', ' ').split('.')[0].split('+')[0]
        status_txt = f"✅ Активен до {until} UTC"
    else:
        status_txt = "❌ Не активен"

    cooldown_min = int(DROP_COOLDOWN_PREMIUM * 60)
    h, m = divmod(cooldown_min, 60)
    cooldown_str = f"{h}ч {m}мин" if h > 0 else f"{m}мин"

    txt = (f"👑 <b>Premium-подписка</b>\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"Статус: {status_txt}\n\n"
           f"Что даёт Premium:\n"
           f"• Кулдаун карты: {cooldown_str} (вместо {DROP_COOLDOWN}ч)\n"
           f"• 🎁 Бонус-паки при ПЕРВОЙ покупке (один раз навсегда)\n\n"
           f"Оплата — Telegram Stars ⭐:")

    markup = types.InlineKeyboardMarkup()
    for days, stars in STARS_VIP_PACKAGES:
        markup.add(types.InlineKeyboardButton(f"👑 {days} дней — {stars} ⭐",
                                              callback_data=f"stars_buy_vip:{days}:{stars}"))
    if is_premium(user) and auto_renew:
        markup.add(types.InlineKeyboardButton("🔕 Отключить автопродление (Gems)", callback_data="shop_toggle_autorenew"))

    safe_send_message(bot, message.chat.id, txt, reply_markup=markup, parse_mode="HTML", owner_id=user_id)


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
    bot.delete_message(call.message.chat.id, call.message.message_id)
    premium_menu_reply(call.message, user_id=user_id)
