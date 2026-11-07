import random

from telebot import types

from database import (get_or_create_user, get_user_data, get_top_by_coins,
                      get_top_by_referrals, get_top_by_cards_count, get_top_by_gems,
                      check_daily_bonus, set_daily_bonus_taken,
                      add_card_to_user, get_all_cards, get_user_gems, get_user_rank,
                      get_top_by_damage, check_farm_available, do_farm_coins,
                      get_user_marriage, get_top_clans_by_treasury, get_top_clans_by_war_wins,
                      get_cultivation_info, get_squad_power, get_top_cultivators)
from database import is_premium, get_clan_name, is_user_banned, update_task_progress, on_card_obtained
from loader import bot
from utils import safe_send_message, safe_edit_message, safe_delete_message, reply_match


# ─────────────────────────────────────────────
# КЛАВИАТУРЫ
# ─────────────────────────────────────────────

def get_main_reply_markup(selective=False):
    # selective=True — клавиатура показывается только тому, кто её вызвал
    # (важно в группах: иначе она "переключает" интерфейс всем участникам чата)
    # Главный экран упрощён до 4 кнопок (этап A ТЗ) — всё остальное (кланы,
    # фарм, брак, настройки, premium, о нас) переехало в инлайн-меню "📜 Меню".
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=selective)
    markup.row(types.KeyboardButton("🎴 Получить карту"), types.KeyboardButton("🗂 Мои карты"))
    markup.row(types.KeyboardButton("👤 Профиль"), types.KeyboardButton("📜 Меню"))
    return markup


def get_game_inline_markup():
    """Главное игровое меню — разбито на логические категории. "Профиль" и
    "Коллекция" (= Мои карты) сюда не входят — это теперь отдельные кнопки
    на главном экране (этап A ТЗ), дублировать их здесь незачем."""
    markup = types.InlineKeyboardMarkup()
    # Бой
    markup.row(
        types.InlineKeyboardButton("🏟 Битва бессмертных", callback_data="menu_arena"),
        types.InlineKeyboardButton("🏆 Рейтинг", callback_data="menu_rating"),
    )
    # Паки и магазин
    markup.row(
        types.InlineKeyboardButton("📦 Сокровища небес", callback_data="menu_packs"),
        types.InlineKeyboardButton("🛒 Небесная лавка", callback_data="menu_shop"),
    )
    # Социальное
    markup.row(
        types.InlineKeyboardButton("🤝 Обмен духовными сокровищами", callback_data="menu_trade"),
    )
    markup.row(
        types.InlineKeyboardButton("🏪 Мир культивации", callback_data="menu_market"),
    )
    # Прогресс
    markup.row(
        types.InlineKeyboardButton("🎯 Путь культивации", callback_data="menu_tasks"),
        types.InlineKeyboardButton("🏅 Достижения", callback_data="menu_achievements"),
    )
    # Прочее
    markup.row(
        types.InlineKeyboardButton("🎉 Испытания бессмертных", callback_data="menu_events"),
        types.InlineKeyboardButton("🔗 Рефералка", callback_data="menu_ref"),
    )
    markup.row(
        types.InlineKeyboardButton("🎁 Дары небес", callback_data="menu_bonus"),
    )
    # Соцфункции и настройки — раньше отдельные кнопки на главном экране,
    # теперь здесь (этап A ТЗ: главный экран упрощён до 4 кнопок)
    markup.row(
        types.InlineKeyboardButton("👥 Кланы", callback_data="menu_clans"),
        types.InlineKeyboardButton("❤️ Даосская пара", callback_data="menu_marriage"),
    )
    markup.row(
        types.InlineKeyboardButton("⛏️ Фарм", callback_data="menu_farm"),
        types.InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings"),
    )
    markup.row(
        types.InlineKeyboardButton("👑 Premium", callback_data="menu_premium"),
        types.InlineKeyboardButton("ℹ️ О нас", callback_data="menu_about"),
    )
    return markup


def get_rating_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👥 По рефералам", callback_data="top_refs"),
        types.InlineKeyboardButton("💰 По коинам", callback_data="top_coins"),
        types.InlineKeyboardButton("🃏 По кол-ву карт", callback_data="top_count"),
        types.InlineKeyboardButton("💎 По гемам", callback_data="top_gems"),
        types.InlineKeyboardButton("⚔️ По урону (Битва бессмертных)", callback_data="top_damage"),
        types.InlineKeyboardButton("🧘 Культиваторы", callback_data="top_cult"),
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


@bot.message_handler(func=reply_match("📜 Меню", "Меню", "🎮 Играть", "Играть"))
def game_menu_handler(message):
    if is_user_banned(message.from_user.id):
        bot.send_message(message.chat.id, "⛔️ Вы заблокированы в этом боте.")
        return
    txt = "🔽 <b>Выберите раздел:</b>"
    safe_send_message(bot, message.chat.id, txt, reply_markup=get_game_inline_markup(), parse_mode="HTML", owner_id=message.from_user.id)


@bot.message_handler(func=reply_match("👤 Профиль", "Профиль"))
def profile_handler(message, user_id=None):
    user_id = user_id or message.from_user.id
    if is_user_banned(user_id):
        bot.send_message(message.chat.id, "⛔️ Вы заблокированы в этом боте.")
        return
    txt = build_profile_text(user_id)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_game_menu"))
    safe_send_message(bot, message.chat.id, txt, reply_markup=markup, parse_mode="HTML", owner_id=user_id)


@bot.message_handler(func=reply_match("ℹ️ О нас", "О нас"))
def about_handler(message, user_id=None):
    user_id = user_id or message.from_user.id
    txt = ("‼️ <b>Информация о нас.</b>\n"
           "➖➖➖➖➖➖\n"
           "<a href='https://telegra.ph/Politika-konfidencialnosti-Telegram-bota-12-24'>Политика конфиденциальности</a>\n"
           "<a href='https://telegra.ph/Polzovatelskoe-soglashenie'>Пользовательское соглашение</a>")
    safe_send_message(bot, message.chat.id, txt, reply_markup=get_back_markup(), parse_mode="HTML", owner_id=user_id)


@bot.message_handler(func=reply_match("⚙️ Настройки", "Настройки"))
def settings_handler(message, user_id=None):
    user_id = user_id or message.from_user.id
    user = get_user_data(user_id)
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
    safe_send_message(bot, message.chat.id, txt, reply_markup=markup, parse_mode="HTML", owner_id=user_id)


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


def build_profile_text(user_id):
    """Общий текст профиля культиватора — используется и реплай-кнопкой
    "👤 Профиль", и инлайн-коллбэком menu_profile."""
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

    # Культивация
    cult = get_cultivation_info(user.get('cultivation_xp'))
    power = get_squad_power(user_id)
    if cult['next_stage_name']:
        cult_progress_txt = (f"🧘 <b>Опыт:</b> {cult['xp']} / {cult['next_stage_xp']} ({cult['progress_percent']}%)\n"
                             f"⏳ <b>До след. стадии:</b> {cult['xp_remaining']} опыта\n")
    else:
        cult_progress_txt = f"🧘 <b>Опыт:</b> {cult['xp']} (максимальная стадия)\n"

    return (f"👤 <b>Профиль культиватора</b>\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"📛 <b>Ник:</b> {user['first_name']}\n"
           f"🏰 <b>Клан:</b> {clan_name}\n"
           f"❤️ <b>Даосская пара:</b> {marriage_txt}\n"
           f"🏆 <b>Место в рейтинге:</b> #{rank}\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"🔺 <b>Уровень:</b> {cult['level']}\n"
           f"🌀 <b>Стадия:</b> {cult['stage_name']}\n"
           f"{cult_progress_txt}"
           f"🔥 <b>Сила культиватора:</b> {power}\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"💰 <b>Монеты:</b> {user['coins']}\n"
           f"💎 <b>Gems:</b> {gems}\n"
           f"💠 <b>Фрагменты:</b> {user.get('fragments') or 0}\n"
           f"🔀 <b>Попыток улучшения:</b> {user.get('fuse_charges') or 0}\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"⚔️ <b>Побед:</b> {wins} / {total}  ({winrate})\n"
           f"📦 <b>Открыто паков:</b> {packs_opened}\n"
           f"🌟 <b>Premium:</b> {prem_text}")


@bot.callback_query_handler(func=lambda call: call.data == "menu_profile")
def callback_profile(call):
    bot.answer_callback_query(call.id)
    txt = build_profile_text(call.from_user.id)

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_game_menu"))

    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      text=txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "menu_collection")
def collection_redirect(call):
    """Перенаправляет в инвентарь карт"""
    bot.answer_callback_query(call.id)
    from handlers.cards import inventory_menu
    safe_delete_message(bot, call.message.chat.id, call.message.message_id)
    call.message.text = "🗂 Мои карты"
    inventory_menu(call.message, user_id=call.from_user.id)


# --- РАЗДЕЛЫ, ПЕРЕЕХАВШИЕ С ГЛАВНОГО ЭКРАНА В ИНЛАЙН-МЕНЮ (этап A ТЗ) ---
# Тот же паттерн, что у collection_redirect выше: удаляем сообщение меню и
# вызываем функцию соответствующей реплай-кнопки напрямую, с user_id — она
# сама шлёт новое сообщение.

@bot.callback_query_handler(func=lambda call: call.data == "menu_clans")
def clans_redirect(call):
    bot.answer_callback_query(call.id)
    from handlers.clans import clan_main_menu
    safe_delete_message(bot, call.message.chat.id, call.message.message_id)
    clan_main_menu(call.message, user_id=call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "menu_marriage")
def marriage_redirect(call):
    bot.answer_callback_query(call.id)
    from handlers.marriage import marriage_main_menu
    safe_delete_message(bot, call.message.chat.id, call.message.message_id)
    marriage_main_menu(call.message, user_id=call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "menu_farm")
def farm_redirect(call):
    bot.answer_callback_query(call.id)
    safe_delete_message(bot, call.message.chat.id, call.message.message_id)
    farm_handler(call.message, user_id=call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "menu_settings")
def settings_redirect(call):
    bot.answer_callback_query(call.id)
    safe_delete_message(bot, call.message.chat.id, call.message.message_id)
    settings_handler(call.message, user_id=call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "menu_premium")
def premium_redirect(call):
    bot.answer_callback_query(call.id)
    from handlers.shop import premium_menu_reply
    safe_delete_message(bot, call.message.chat.id, call.message.message_id)
    premium_menu_reply(call.message, user_id=call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "menu_about")
def about_redirect(call):
    bot.answer_callback_query(call.id)
    safe_delete_message(bot, call.message.chat.id, call.message.message_id)
    about_handler(call.message, user_id=call.from_user.id)


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

    if category == "cult":
        rows = get_top_cultivators()
        medals = ["🥇", "🥈", "🥉"]
        txt = "🧘 <b>Топ культиваторов</b>\n\n"
        if not rows:
            txt += "Пока пусто..."
        else:
            for i, u in enumerate(rows):
                info = get_cultivation_info(u.get('cultivation_xp'))
                medal = medals[i] if i < 3 else f"{i + 1}."
                txt += f"{medal} <b>{u.get('first_name', '?')}</b> — {info['stage_name']} (ур. {info['level']})\n"
        safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt,
                          reply_markup=get_rating_markup(), parse_mode="HTML")
        return

    if category == "refs":
        data = get_top_by_referrals()
        metric, field = "👥", "count"
    elif category == "count":
        data = get_top_by_cards_count()
        metric, field = "🃏", "count"
    elif category == "gems":
        data = get_top_by_gems()
        metric, field = "💎", "gems"
        txt = "💎 <b>Топ по гемам</b>\n\n"
    elif category == "damage":
        data = get_top_by_damage()
        metric, field = "⚔️", "value"
        txt = "⚔️ <b>Топ по урону (Битва бессмертных)</b>\n\n"
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
        bot.answer_callback_query(call.id, "⏳ Дар небес уже получен! Приходи завтра.", show_alert=True)
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
    txt = (f"🎁 {user_mention} получил дар небес!\n\n"
           f"Вы получили 3 карты:\n"
           f"1. {received[0]}\n2. {received[1]}\n3. {received[2]}\n\n"
           f"Возвращайся завтра за новым даром!")
    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt,
                      reply_markup=get_back_markup(), parse_mode="HTML")


# --- ФАРМ МОНЕТ ---

@bot.message_handler(func=reply_match("⛏️ Фарм", "Фарм"))
def farm_handler(message, user_id=None):
    # is_override=True — вызвано из инлайн-меню (message — старое сообщение
    # БОТА, а не свежее сообщение игрока), значит отвечать на него не нужно
    is_override = user_id is not None
    user_id = user_id or message.from_user.id
    reply_id = message.message_id if (not is_override and message.chat.type != 'private') else None

    if is_user_banned(user_id):
        bot.send_message(message.chat.id, "⛔️ Вы заблокированы в этом боте.")
        return

    available, seconds_left = check_farm_available(user_id)

    if not available:
        hours_left = seconds_left // 3600
        minutes_left = (seconds_left % 3600) // 60
        bot.send_message(
            message.chat.id,
            f"⏳ Фарм ещё не готов!\n"
            f"Ожидай: {hours_left}ч {minutes_left}мин",
            reply_to_message_id=reply_id
        )
        return

    # do_farm_coins сам атомарно перепроверяет кулдаун при записи — amount=0
    # значит либо кулдаун и правда не прошёл, либо это гонка из нескольких
    # быстрых нажатий, и фарм уже выполнил другой из параллельных запросов
    amount = do_farm_coins(user_id)
    if not amount:
        bot.send_message(message.chat.id, "⏳ Фарм ещё не готов!", reply_to_message_id=reply_id)
        return

    user_data = get_user_data(user_id)
    uname = user_data.get('username') if user_data else None
    fname = user_data.get('first_name') if user_data else 'Игрок'
    user_mention = f"@{uname}" if uname else f"<b>{fname}</b>"
    bot.send_message(
        message.chat.id,
        f"⛏️ {user_mention} собрал монеты на ферме!\n"
        f"💰 +<b>{amount}</b> монет\n\n"
        f"⏳ Следующий фарм через 4 часа.",
        parse_mode="HTML",
        reply_to_message_id=reply_id
    )


@bot.callback_query_handler(func=lambda call: call.data == "ignore")
def callback_ignore(call):
    """Кнопки-разделители (счётчики страниц и т.п.) — просто гасим спиннер"""
    bot.answer_callback_query(call.id)
