import random

from telebot import types

from database import (get_or_create_user, get_user_data, get_top_by_coins,
                      get_top_by_referrals, get_top_by_cards_count, get_top_by_value,
                      check_daily_bonus, set_daily_bonus_taken,
                      add_card_to_user, get_all_cards, get_user_gems, get_user_rank,
                      get_top_by_damage, check_farm_available, do_farm_coins,
                      get_user_marriage, get_top_clans_by_treasury, get_top_clans_by_war_wins)
from database import is_premium, get_clan_name, is_user_banned, update_task_progress, on_card_obtained
from loader import bot
from utils import safe_send_message, safe_edit_message


# ─────────────────────────────────────────────
# КЛАВИАТУРЫ
# ─────────────────────────────────────────────

def get_main_reply_markup(selective=False):
    # selective=True — клавиатура показывается только тому, кто её вызвал
    # (важно в группах: иначе она "переключает" интерфейс всем участникам чата)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=selective)
    markup.row(types.KeyboardButton("🎴 Получить карту"), types.KeyboardButton("🗂 Мои карты"))
    markup.row(types.KeyboardButton("👥 Кланы"), types.KeyboardButton("🎮 Играть"), types.KeyboardButton("ℹ️ О нас"))
    markup.row(types.KeyboardButton("⛏️ Фарм"), types.KeyboardButton("❤️ Брак"), types.KeyboardButton("⚙️ Настройки"))
    markup.row(types.KeyboardButton("👑 Premium"))
    return markup


def get_game_inline_markup():
    """Главное игровое меню — разбито на логические категории"""
    markup = types.InlineKeyboardMarkup()
    # Профиль и коллекция
    markup.row(
        types.InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
        types.InlineKeyboardButton("🎒 Коллекция", callback_data="menu_collection"),
    )
    # Бой
    markup.row(
        types.InlineKeyboardButton("🏟 Арена", callback_data="menu_arena"),
        types.InlineKeyboardButton("🏆 Рейтинг", callback_data="menu_rating"),
    )
    # Паки и магазин
    markup.row(
        types.InlineKeyboardButton("📦 Паки", callback_data="menu_packs"),
        types.InlineKeyboardButton("🛒 Магазин", callback_data="menu_shop"),
    )
    # Социальное
    markup.row(
        types.InlineKeyboardButton("🤝 Обмен", callback_data="menu_trade"),
        types.InlineKeyboardButton("🏪 Площадка", callback_data="menu_market"),
    )
    # Прогресс
    markup.row(
        types.InlineKeyboardButton("🎯 Задания", callback_data="menu_tasks"),
        types.InlineKeyboardButton("🏅 Достижения", callback_data="menu_achievements"),
    )
    # Прочее
    markup.row(
        types.InlineKeyboardButton("🎉 События", callback_data="menu_events"),
        types.InlineKeyboardButton("🔗 Рефералка", callback_data="menu_ref"),
        types.InlineKeyboardButton("🎁 Бонус", callback_data="menu_bonus"),
    )
    return markup


def get_rating_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👥 По рефералам", callback_data="top_refs"),
        types.InlineKeyboardButton("💰 По коинам", callback_data="top_coins"),
        types.InlineKeyboardButton("🃏 По кол-ву карт", callback_data="top_count"),
        types.InlineKeyboardButton("💎 По ценности", callback_data="top_value"),
        types.InlineKeyboardButton("⚔️ По урону (Арена)", callback_data="top_damage"),
        types.InlineKeyboardButton("🏰 Казна клана", callback_data="top_treasury"),
        types.InlineKeyboardButton("🏰 Победы в войнах", callback_data="top_warwins"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_game_menu")
    )
    return markup


def get_back_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_game_menu"))
    return markup


# ─────────────────────────────────────────────
# ХЕНДЛЕРЫ REPLY
# ─────────────────────────────────────────────
# (middleware для авто-создания юзера и гейта подписки — в handlers/middlewares.py)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    result = get_or_create_user(message.from_user.id, message.from_user.username,
                                message.from_user.first_name, referrer_id)

    if is_user_banned(message.from_user.id):
        bot.send_message(message.chat.id, "⛔️ Вы заблокированы в этом боте.")
        return

    update_task_progress(message.from_user.id, "login", "daily")

    if result is True and referrer_id:
        try:
            bot.send_message(referrer_id,
                             f"🎉 По вашей реферальной ссылке зарегистрировался новый игрок!\n"
                             f"Вам начислено <b>500 монет</b>! 💰",
                             parse_mode="HTML")
        except:
            pass

    from handlers.subscription import get_unsubscribed_mandatory, build_subscription_text, build_subscription_markup
    missing = get_unsubscribed_mandatory(message.from_user.id)
    if missing:
        bot.send_message(message.chat.id, build_subscription_text(missing),
                         reply_markup=build_subscription_markup(), parse_mode="HTML")
        return

    is_group = message.chat.type in ("group", "supergroup")
    txt = (f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
           f"🎴 Добро пожаловать в мир карточек дунхуа!\n"
           f"Собирай коллекции, сражайся на арене и обменивайся с игроками.\n\n"
           f"Выбери действие в меню ниже:")
    try:
        bot.send_message(message.chat.id, txt, reply_markup=get_main_reply_markup(selective=is_group),
                         parse_mode="HTML",
                         reply_to_message_id=message.message_id if is_group else None)
    except Exception as e:
        print(f"Error sending message: {e}")


@bot.message_handler(func=lambda m: m.text == "🎮 Играть")
def game_menu_handler(message):
    if is_user_banned(message.from_user.id):
        bot.send_message(message.chat.id, "⛔️ Вы заблокированы в этом боте.")
        return
    txt = "🔽 <b>Выберите раздел:</b>"
    safe_send_message(bot, message.chat.id, txt, reply_markup=get_game_inline_markup(), parse_mode="HTML", owner_id=message.from_user.id)


@bot.message_handler(func=lambda m: m.text == "ℹ️ О нас")
def about_handler(message):
    txt = ("‼️ <b>Информация о нас.</b>\n"
           "➖➖➖➖➖➖\n"
           "❓ Аккаунты поддержки: @Devils_Time, @angeL_870\n\n"
           "<a href='https://telegra.ph/Politika-konfidencialnosti-Telegram-bota-12-24'>Политика конфиденциальности</a>\n"
           "<a href='https://telegra.ph/Polzovatelskoe-soglashenie'>Пользовательское соглашение</a>")
    safe_send_message(bot, message.chat.id, txt, reply_markup=get_back_markup(), parse_mode="HTML")


@bot.message_handler(func=lambda m: m.text == "⚙️ Настройки")
def settings_handler(message):
    user = get_user_data(message.from_user.id)
    notif = user.get('notification_settings', {}).get('drop', True) if user.get('notification_settings') else True
    status = "🔔 Включены" if notif else "🔕 Выключены"

    markup = types.InlineKeyboardMarkup()
    new_state = not notif
    markup.add(types.InlineKeyboardButton(
        f"{'🔕 Выключить' if notif else '🔔 Включить'} уведомления",
        callback_data=f"toggle_notif:{int(new_state)}"
    ))
    markup.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_game_menu"))

    txt = (f"⚙️ <b>Настройки</b>\n\n"
           f"Уведомления о картах: {status}")
    safe_send_message(bot, message.chat.id, txt, reply_markup=markup, parse_mode="HTML")


# ─────────────────────────────────────────────
# ХЕНДЛЕРЫ INLINE
# ─────────────────────────────────────────────

@bot.callback_query_handler(func=lambda call: call.data.startswith("toggle_notif:"))
def toggle_notification(call):
    bot.answer_callback_query(call.id)
    new_state = bool(int(call.data.split(":")[1]))
    user_id = call.from_user.id
    from loader import supabase
    supabase.table("users").update({
        "notification_settings": {"drop": new_state}
    }).eq("telegram_id", user_id).execute()
    status = "🔔 Включены" if new_state else "🔕 Выключены"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        f"{'🔕 Выключить' if new_state else '🔔 Включить'} уведомления",
        callback_data=f"toggle_notif:{int(not new_state)}"
    ))
    markup.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_game_menu"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      f"⚙️ <b>Настройки</b>\n\nУведомления о картах: {status}",
                      reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "menu_profile")
def callback_profile(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user = get_user_data(user_id)

    clan_name = get_clan_name(user.get('clan_id'))
    is_prem = is_premium(user)
    prem_text = "✅ Активен" if is_prem else "❌ Нет"
    wins = user.get('battles_won', 0)
    total = user.get('battles_total', 0)
    gems = get_user_gems(user_id)
    rank = get_user_rank(user_id)
    packs_opened = user.get('packs_opened', 0) or 0
    winrate = f"{int(wins / total * 100)}%" if total > 0 else "—"

    # Брак
    marriage = get_user_marriage(user_id)
    if marriage:
        partner_data = marriage.get('u2') if marriage['user1_id'] == user_id else marriage.get('u1')
        partner_name = partner_data.get('first_name', '?') if partner_data else '?'
        partner_username = partner_data.get('username') if partner_data else None
        marriage_txt = f"❤️ @{partner_username}" if partner_username else f"❤️ {partner_name}"
    else:
        marriage_txt = "❌ Нет"

    txt = (f"👤 <b>Профиль игрока</b>\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"📛 <b>Ник:</b> {user['first_name']}\n"
           f"🏰 <b>Клан:</b> {clan_name}\n"
           f"❤️ <b>Брак:</b> {marriage_txt}\n"
           f"🏆 <b>Место в рейтинге:</b> #{rank}\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"💰 <b>Монеты:</b> {user['coins']}\n"
           f"💎 <b>Gems:</b> {gems}\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"⚔️ <b>Побед:</b> {wins} / {total}  ({winrate})\n"
           f"📦 <b>Открыто паков:</b> {packs_opened}\n"
           f"🌟 <b>Premium:</b> {prem_text}")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_game_menu"))

    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      text=txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "menu_collection")
def collection_redirect(call):
    """Перенаправляет в инвентарь карт"""
    bot.answer_callback_query(call.id)
    from handlers.cards import inventory_menu
    bot.delete_message(call.message.chat.id, call.message.message_id)
    call.message.text = "🗂 Мои карты"
    inventory_menu(call.message, user_id=call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_game_menu")
def callback_back(call):
    bot.answer_callback_query(call.id)
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      text="🔽 <b>Выберите раздел:</b>",
                      reply_markup=get_game_inline_markup(), parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "menu_rating")
def rating_menu(call):
    bot.answer_callback_query(call.id)
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      "🏆 <b>Выберите категорию рейтинга:</b>", reply_markup=get_rating_markup(), parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("top_"))
def show_top(call):
    bot.answer_callback_query(call.id)
    category = call.data.split("_")[1]
    txt = "🏆 <b>Топ игроков</b>\n\n"

    if category == "refs":
        data = get_top_by_referrals()
        metric, field = "👥", "count"
    elif category == "count":
        data = get_top_by_cards_count()
        metric, field = "🃏", "count"
    elif category == "value":
        data = get_top_by_value()
        metric, field = "💎", "value"
    elif category == "damage":
        data = get_top_by_damage()
        metric, field = "⚔️", "value"
        txt = "⚔️ <b>Топ по урону (Арена)</b>\n\n"
    elif category == "treasury":
        data = get_top_clans_by_treasury()
        metric, field = "💰", "coins"
        txt = "🏰 <b>Топ кланов по казне</b>\n\n"
    elif category == "warwins":
        data = get_top_clans_by_war_wins()
        metric, field = "🏆", "war_wins"
        txt = "🏰 <b>Топ кланов по победам в войнах</b>\n\n"
    else:
        data = get_top_by_coins()
        metric, field = "💰", "coins"

    medals = ["🥇", "🥈", "🥉"]
    if not data:
        txt += "Пока пусто..."
    else:
        for i, u in enumerate(data):
            val = u.get(field, 0)
            # Клановые категории отдают {"name": ...}, а не {"first_name": ...}
            label = u.get('first_name') or u.get('name', '?')
            medal = medals[i] if i < 3 else f"{i + 1}."
            txt += f"{medal} <b>{label}</b> — {val} {metric}\n"

    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt,
                      reply_markup=get_rating_markup(), parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "menu_ref")
def show_referral(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    bot_name = bot.get_me().username
    link = f"https://t.me/{bot_name}?start={user_id}"

    txt = (f"🔗 <b>Реферальная система</b>\n\n"
           f"Твоя ссылка:\n<code>{link}</code>\n\n"
           f"📋 Как это работает:\n"
           f"• Друг регистрируется по ссылке\n"
           f"• Вам обоим начисляется <b>500 монет</b> 💰\n\n"
           f"Чем больше друзей — тем больше монет!")
    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt,
                      reply_markup=get_back_markup(), parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "menu_bonus")
def get_daily_bonus(call):
    user_id = call.from_user.id

    if not check_daily_bonus(user_id):
        bot.answer_callback_query(call.id, "⏳ Бонус уже получен! Приходи завтра.", show_alert=True)
        return

    bot.answer_callback_query(call.id)

    cards_all = get_all_cards()
    if not cards_all:
        bot.answer_callback_query(call.id, "Ошибка: карты не найдены.", show_alert=True)
        return

    received = []
    for _ in range(3):
        card = random.choice(cards_all)
        is_dup, _ = add_card_to_user(user_id, card['id'])
        on_card_obtained(user_id, card, is_dup)
        received.append(card['name'])

    update_task_progress(user_id, "claim_bonus", "daily")
    set_daily_bonus_taken(user_id)

    # Показываем ник получателя бонуса в чате
    user_tg = call.from_user
    user_mention = f"@{user_tg.username}" if user_tg.username else f"<b>{user_tg.first_name}</b>"
    txt = (f"🎁 {user_mention} получил ежедневный бонус!\n\n"
           f"Вы получили 3 карты:\n"
           f"1. {received[0]}\n2. {received[1]}\n3. {received[2]}\n\n"
           f"Возвращайся завтра за новым бонусом!")
    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt,
                      reply_markup=get_back_markup(), parse_mode="HTML")


# --- ФАРМ МОНЕТ ---

@bot.message_handler(func=lambda m: m.text == "⛏️ Фарм")
def farm_handler(message):
    if is_user_banned(message.from_user.id):
        bot.send_message(message.chat.id, "⛔️ Вы заблокированы в этом боте.")
        return

    user_id = message.from_user.id
    available, seconds_left = check_farm_available(user_id)

    if not available:
        hours_left = seconds_left // 3600
        minutes_left = (seconds_left % 3600) // 60
        bot.send_message(
            message.chat.id,
            f"⏳ Фарм ещё не готов!\n"
            f"Ожидай: {hours_left}ч {minutes_left}мин",
            reply_to_message_id=message.message_id if message.chat.type != 'private' else None
        )
        return

    amount = do_farm_coins(user_id)
    user_mention = f"@{message.from_user.username}" if message.from_user.username else f"<b>{message.from_user.first_name}</b>"
    bot.send_message(
        message.chat.id,
        f"⛏️ {user_mention} собрал монеты на ферме!\n"
        f"💰 +<b>{amount}</b> монет\n\n"
        f"⏳ Следующий фарм через 4 часа.",
        parse_mode="HTML",
        reply_to_message_id=message.message_id if message.chat.type != 'private' else None
    )


@bot.callback_query_handler(func=lambda call: call.data == "ignore")
def callback_ignore(call):
    """Кнопки-разделители (счётчики страниц и т.п.) — просто гасим спиннер"""
    bot.answer_callback_query(call.id)
