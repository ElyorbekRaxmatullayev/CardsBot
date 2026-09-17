import threading
import time
from datetime import datetime, timezone

from telebot import types

from config import RARITY_ORDER, RARITY_CONFIG
from database import (add_new_card_to_db, get_user_data, update_coins, update_gems, get_all_users_count,
                      update_card, delete_card, get_cards_paginated, count_card_owners, add_card_to_user,
                      create_event, end_event, get_events_admin,
                      search_users, set_user_banned, get_public_profile,
                      is_admin, is_head_admin, get_admin_role, get_admins_list, add_admin, remove_admin,
                      get_required_channels, add_required_channel, delete_required_channel,
                      toggle_channel_mandatory, get_all_marriages, admin_divorce_marriage, get_all_user_ids,
                      set_card_stars_price)
from loader import bot
from utils import safe_edit_message, register_next_step_handler_for_user

CARDS_PAGE_SIZE = 10


def _adm_back_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 В админку", callback_data="adm_back"))
    return markup


def admin_only(func):
    """Декоратор — только для администратора"""
    def wrapper(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "⛔️ Нет доступа.")
            return
        return func(message)
    return wrapper


# --- ПАНЕЛЬ АДМИНИСТРАТОРА ---

@bot.message_handler(commands=['admin'])
def admin_start(message, user_id=None):
    # user_id передаётся явно при возврате из вложенных экранов (там message — это
    # сообщение бота, и message.from_user внутри него — это сам бот, а не админ)
    user_id = user_id or message.from_user.id
    if not is_admin(user_id):
        return

    users_count = get_all_users_count()
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🃏 Добавить карту", callback_data="adm_add_card"),
        types.InlineKeyboardButton("📚 Карты", callback_data="adm_cards:0"),
    )
    markup.row(
        types.InlineKeyboardButton("💰 Выдать монеты", callback_data="adm_give_coins"),
        types.InlineKeyboardButton("💎 Выдать Gems", callback_data="adm_give_gems"),
    )
    markup.row(
        types.InlineKeyboardButton("🎴 Выдать карту", callback_data="adm_give_card"),
        types.InlineKeyboardButton("👤 Игроки", callback_data="adm_users"),
    )
    markup.row(
        types.InlineKeyboardButton("🎉 События", callback_data="adm_events"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="adm_stats"),
    )
    markup.row(
        types.InlineKeyboardButton("💍 Браки", callback_data="adm_marriages:0"),
        types.InlineKeyboardButton("📣 Рассылка", callback_data="adm_broadcast"),
    )
    row = [types.InlineKeyboardButton("📢 Каналы", callback_data="adm_channels")]
    if is_head_admin(user_id):
        row.insert(0, types.InlineKeyboardButton("👑 Админы", callback_data="adm_admins"))
    markup.row(*row)

    role = get_admin_role(user_id)
    role_txt = "👑 Гл. Администратор" if role == 'head' else "🛡 Админ"
    txt = (f"⚙️ <b>Панель администратора</b>\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"Ваша роль: <b>{role_txt}</b>\n"
           f"👥 Пользователей: <b>{users_count}</b>\n\n"
           f"Выберите действие:")
    bot.send_message(message.chat.id, txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "adm_stats")
def adm_stats(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    from database import get_all_cards
    cards_count = len(get_all_cards() or [])
    users_count = get_all_users_count()
    txt = (f"📊 <b>Статистика бота</b>\n\n"
           f"👥 Пользователей: {users_count}\n"
           f"🃏 Карточек в базе: {cards_count}")
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="adm_back"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt,
                      reply_markup=markup, parse_mode="HTML")


MARRIAGES_PAGE_SIZE = 10
_marriage_search = {}  # admin_id -> текущий поисковый запрос (или None)


def _marriage_user_disp(u):
    u = u or {}
    username = u.get('username')
    return f"@{username}" if username else (u.get('first_name') or '?')


def _marriage_duration_txt(m):
    ts = m.get('married_at') or m.get('created_at')
    if not ts:
        return "?"
    try:
        started = datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except ValueError:
        return "?"
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    diff = datetime.now(timezone.utc) - started
    days = diff.days
    hours = diff.seconds // 3600
    return f"{days} дней, {hours} часов"


def _render_marriages_list(chat_id, message_id, admin_id, page):
    query = _marriage_search.get(admin_id)
    marriages, total = get_all_marriages(page, MARRIAGES_PAGE_SIZE, username_query=query)
    max_page = max(0, (total - 1) // MARRIAGES_PAGE_SIZE)

    header = f"🔍 по запросу «{query}» " if query else ""
    txt = f"💍 <b>Зарегистрированные браки</b> {header}(всего: {total})\n➖➖➖➖➖➖➖➖\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)

    if not marriages:
        txt += "Ничего не найдено." if query else "Пока нет ни одного брака."
    else:
        for m in marriages:
            u1_disp = _marriage_user_disp(m.get('u1'))
            u2_disp = _marriage_user_disp(m.get('u2'))
            txt += f"❤️ <b>{u1_disp} + {u2_disp}</b> — Вместе: {_marriage_duration_txt(m)}\n"
            markup.add(types.InlineKeyboardButton(
                f"💔 Расторгнуть {u1_disp} + {u2_disp}",
                callback_data=f"adm_marriage_confirm:{m['id']}:{page}"
            ))

    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"adm_marriages:{page - 1}"))
    nav.append(types.InlineKeyboardButton(f"{page + 1}/{max_page + 1}", callback_data="ignore"))
    if page < max_page:
        nav.append(types.InlineKeyboardButton("➡️", callback_data=f"adm_marriages:{page + 1}"))
    if len(nav) > 1:
        markup.row(*nav)

    search_row = [types.InlineKeyboardButton("🔍 Поиск по @username", callback_data="adm_marriage_search")]
    if query:
        search_row.append(types.InlineKeyboardButton("❌ Сбросить поиск", callback_data="adm_marriage_search_clear"))
    markup.row(*search_row)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="adm_back"))
    safe_edit_message(bot, chat_id, message_id, txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_marriages:"))
def adm_marriages_list(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    page = int(call.data.split(":")[1])
    _render_marriages_list(call.message.chat.id, call.message.message_id, call.from_user.id, page)


@bot.callback_query_handler(func=lambda call: call.data == "adm_marriage_search")
def adm_marriage_search_start(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
                           "🔍 Введите @username (или часть имени) одного из партнёров:\n\n(Отмена — /cancel)")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, _marriage_search_step)


def _marriage_search_step(message):
    admin_id = message.from_user.id
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "Отменено.")
        return
    _marriage_search[admin_id] = message.text.strip()
    msg = bot.send_message(message.chat.id, "💍 Результаты поиска:")
    _render_marriages_list(message.chat.id, msg.message_id, admin_id, 0)


@bot.callback_query_handler(func=lambda call: call.data == "adm_marriage_search_clear")
def adm_marriage_search_clear(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id, "Поиск сброшен")
    _marriage_search.pop(call.from_user.id, None)
    _render_marriages_list(call.message.chat.id, call.message.message_id, call.from_user.id, 0)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_marriage_confirm:"))
def adm_marriage_confirm(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    _, marriage_id, page = call.data.split(":")
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Да, расторгнуть", callback_data=f"adm_marriage_do:{marriage_id}:{page}"),
        types.InlineKeyboardButton("❌ Отмена", callback_data=f"adm_marriages:{page}"),
    )
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      "⚠️ Расторгнуть этот брак принудительно?", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_marriage_do:"))
def adm_marriage_do(call):
    if not is_admin(call.from_user.id):
        return
    _, marriage_id, page = call.data.split(":")
    ok = admin_divorce_marriage(int(marriage_id))
    bot.answer_callback_query(call.id, "✅ Брак расторгнут" if ok else "❌ Брак уже не активен", show_alert=True)
    _render_marriages_list(call.message.chat.id, call.message.message_id, call.from_user.id, int(page))


@bot.callback_query_handler(func=lambda call: call.data == "adm_back")
def adm_back(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    admin_start(call.message, user_id=call.from_user.id)


# --- ДОБАВЛЕНИЕ КАРТЫ ---

@bot.callback_query_handler(func=lambda call: call.data == "adm_add_card")
def adm_add_card(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "🃏 Введи <b>название</b> новой карты:", parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, step_name)


def step_name(message):
    data = {'name': message.text.strip()}
    msg = bot.send_message(message.chat.id, "Введи название <b>дунхуа</b> (или напиши своё):", parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, message.from_user.id, step_dunhua, data)


def step_dunhua(message, data):
    data['dunhua'] = message.text.strip()
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for r in RARITY_ORDER:
        markup.add(r)
    msg = bot.send_message(message.chat.id, "Выбери <b>редкость</b>:", reply_markup=markup, parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, message.from_user.id, step_rarity, data)


def step_rarity(message, data):
    if message.text not in RARITY_ORDER:
        msg = bot.send_message(message.chat.id, "❌ Неверная редкость. Выбери из списка:")
        register_next_step_handler_for_user(bot, msg, message.from_user.id, step_rarity, data)
        return
    data['rarity'] = message.text
    # value карты определяется редкостью (используется в рейтинге "По ценности"
    # и при продаже) — раньше этот шаг не спрашивали, и value молча оставалось
    # дефолтом схемы (10) для ЛЮБОЙ редкости, отсюда рейтинг "по ценности"
    # у всех совпадал с количеством карт *10
    data['value'] = RARITY_CONFIG.get(data['rarity'], {}).get('value', 10)
    msg = bot.send_message(message.chat.id, "Введи <b>Атаку и Здоровье</b> через пробел (например: 100 200):",
                           reply_markup=types.ReplyKeyboardRemove(), parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, message.from_user.id, step_stats, data)


def step_stats(message, data):
    try:
        a, h = map(int, message.text.strip().split())
        data['attack'] = a
        data['hp'] = h
        msg = bot.send_message(message.chat.id, "Введи <b>краткое описание</b> персонажа:", parse_mode="HTML")
        register_next_step_handler_for_user(bot, msg, message.from_user.id, step_description, data)
    except:
        msg = bot.send_message(message.chat.id, "❌ Ошибка. Введи два числа через пробел:")
        register_next_step_handler_for_user(bot, msg, message.from_user.id, step_stats, data)


def step_description(message, data):
    data['description'] = message.text.strip()
    msg = bot.send_message(message.chat.id, "📷 Пришли <b>фото</b> карты:", parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, message.from_user.id, step_photo, data)


def step_photo(message, data):
    if message.photo:
        data['image_file_id'] = message.photo[-1].file_id
        add_new_card_to_db(data)
        bot.send_message(message.chat.id,
                         f"✅ <b>Карта сохранена!</b>\n\n"
                         f"🃏 {data['name']} ({data.get('dunhua', '?')})\n"
                         f"⭐️ {data['rarity']} | ⚔️{data['attack']} ❤️{data['hp']}",
                         reply_markup=_adm_back_markup(), parse_mode="HTML")
    else:
        msg = bot.send_message(message.chat.id, "❌ Нужно отправить фото!")
        register_next_step_handler_for_user(bot, msg, message.from_user.id, step_photo, data)


# --- СПИСОК / ПРОСМОТР / РЕДАКТИРОВАНИЕ / УДАЛЕНИЕ КАРТ ---

def _card_short_line(card):
    emoji = RARITY_CONFIG.get(card['rarity'], {}).get('emoji', '❓')
    return f"{emoji} {card['name']} (#{card['id']})"


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_cards:"))
def adm_cards_list(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    page = int(call.data.split(":")[1])
    cards, total = get_cards_paginated(page, CARDS_PAGE_SIZE)

    markup = types.InlineKeyboardMarkup(row_width=1)
    if not cards and page > 0:
        page = 0
        cards, total = get_cards_paginated(page, CARDS_PAGE_SIZE)

    for card in cards:
        markup.add(types.InlineKeyboardButton(_card_short_line(card),
                                              callback_data=f"adm_card_view:{card['id']}:{page}"))

    max_page = max((total - 1) // CARDS_PAGE_SIZE, 0)
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"adm_cards:{page - 1}"))
    nav.append(types.InlineKeyboardButton(f"{page + 1}/{max_page + 1}", callback_data="ignore"))
    if page < max_page:
        nav.append(types.InlineKeyboardButton("➡️", callback_data=f"adm_cards:{page + 1}"))
    markup.row(*nav)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="adm_back"))

    txt = f"📚 <b>Карты в базе</b> (всего: {total})"
    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt,
                      reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_card_view:"))
def adm_card_view(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    parts = call.data.split(":")
    card_id, page = int(parts[1]), int(parts[2])

    from database import get_card_by_id
    card = get_card_by_id(card_id)
    if not card:
        bot.answer_callback_query(call.id, "Карта не найдена", show_alert=True)
        return

    owners = count_card_owners(card_id)
    emoji = RARITY_CONFIG.get(card['rarity'], {}).get('emoji', '❓')
    txt = (f"{emoji} <b>{card['name']}</b> (#{card['id']})\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"📖 Дунхуа: {card.get('dunhua') or '—'}\n"
           f"⭐️ Редкость: {card['rarity']}\n"
           f"⚔️ Атака: {card.get('attack', 0)} | ❤️ HP: {card.get('hp', 0)}\n"
           f"💰 Стоимость: {card.get('value', 0)}\n"
           f"📝 {card.get('description') or '—'}\n"
           f"👥 У игроков: {owners}")
    if card['rarity'] == 'Limited':
        stars_price = card.get('stars_price')
        txt += f"\n⭐️ Цена в Stars: {stars_price if stars_price else 'не задана — не продаётся'}"

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✏️ Изменить", callback_data=f"adm_card_edit:{card_id}:{page}"),
        types.InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_card_del:{card_id}:{page}"),
    )
    if card['rarity'] == 'Limited':
        markup.add(types.InlineKeyboardButton("⭐ Задать цену в Stars",
                                              callback_data=f"adm_card_stars_price:{card_id}:{page}"))
    markup.add(types.InlineKeyboardButton("🎁 Выдать эту карту", callback_data=f"adm_card_give_one:{card_id}"))
    markup.add(types.InlineKeyboardButton("🔙 К списку", callback_data=f"adm_cards:{page}"))

    if card.get('image_file_id'):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_photo(call.message.chat.id, card['image_file_id'], caption=txt, reply_markup=markup, parse_mode="HTML")
    else:
        safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt,
                          reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_card_stars_price:"))
def adm_card_stars_price_start(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    parts = call.data.split(":")
    card_id, page = int(parts[1]), int(parts[2])
    msg = bot.send_message(call.message.chat.id,
                           "⭐ Введи цену в Stars для этой лимитной карты (целое число):")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, _adm_card_stars_price_step, card_id, page)


def _adm_card_stars_price_step(message, card_id, page):
    try:
        price = int(message.text.strip())
        if price < 1:
            raise ValueError
    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ Введи целое положительное число:")
        register_next_step_handler_for_user(bot, msg, message.from_user.id, _adm_card_stars_price_step, card_id, page)
        return
    set_card_stars_price(card_id, price)
    bot.send_message(message.chat.id, f"✅ Цена установлена: {price} ⭐", reply_markup=_adm_back_markup())


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_card_edit:"))
def adm_card_edit_start(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    parts = call.data.split(":")
    card_id, page = int(parts[1]), int(parts[2])
    msg = bot.send_message(call.message.chat.id,
                           "✏️ <b>Изменение карты</b>\n"
                           "На каждом шаге можно прислать «-», чтобы оставить значение как есть.\n\n"
                           "Новое <b>название</b>:",
                           parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, edit_step_name, card_id, page, {})


def edit_step_name(message, card_id, page, data):
    if message.text.strip() != '-':
        data['name'] = message.text.strip()
    msg = bot.send_message(message.chat.id, "Название <b>дунхуа</b> (или «-»):", parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, message.from_user.id, edit_step_dunhua, card_id, page, data)


def edit_step_dunhua(message, card_id, page, data):
    if message.text.strip() != '-':
        data['dunhua'] = message.text.strip()
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add('-')
    for r in RARITY_ORDER:
        markup.add(r)
    msg = bot.send_message(message.chat.id, "Новая <b>редкость</b> (или «-»):", reply_markup=markup, parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, message.from_user.id, edit_step_rarity, card_id, page, data)


def edit_step_rarity(message, card_id, page, data):
    text = message.text.strip()
    if text != '-':
        if text not in RARITY_ORDER:
            msg = bot.send_message(message.chat.id, "❌ Неверная редкость. Введи из списка или «-»:")
            register_next_step_handler_for_user(bot, msg, message.from_user.id, edit_step_rarity, card_id, page, data)
            return
        data['rarity'] = text
        data['value'] = RARITY_CONFIG.get(text, {}).get('value', 10)
    msg = bot.send_message(message.chat.id, "Новые <b>Атака и Здоровье</b> через пробел (или «-»):",
                           reply_markup=types.ReplyKeyboardRemove(), parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, message.from_user.id, edit_step_stats, card_id, page, data)


def edit_step_stats(message, card_id, page, data):
    text = message.text.strip()
    if text != '-':
        try:
            a, h = map(int, text.split())
            data['attack'] = a
            data['hp'] = h
        except:
            msg = bot.send_message(message.chat.id, "❌ Ошибка. Введи два числа через пробел или «-»:")
            register_next_step_handler_for_user(bot, msg, message.from_user.id, edit_step_stats, card_id, page, data)
            return
    msg = bot.send_message(message.chat.id, "Новое <b>описание</b> (или «-»):", parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, message.from_user.id, edit_step_description, card_id, page, data)


def edit_step_description(message, card_id, page, data):
    if message.text.strip() != '-':
        data['description'] = message.text.strip()
    msg = bot.send_message(message.chat.id, "📷 Новое <b>фото</b> (или «-», чтобы оставить прежнее):", parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, message.from_user.id, edit_step_photo, card_id, page, data)


def edit_step_photo(message, card_id, page, data):
    if message.photo:
        data['image_file_id'] = message.photo[-1].file_id
    elif not (message.text and message.text.strip() == '-'):
        msg = bot.send_message(message.chat.id, "❌ Пришли фото или «-»:")
        register_next_step_handler_for_user(bot, msg, message.from_user.id, edit_step_photo, card_id, page, data)
        return

    if data:
        update_card(card_id, data)
        bot.send_message(message.chat.id, f"✅ Карта #{card_id} обновлена!",
                         reply_markup=_adm_back_markup(), parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "Ничего не изменено.", reply_markup=_adm_back_markup())


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_card_del:"))
def adm_card_del_confirm(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    parts = call.data.split(":")
    card_id, page = int(parts[1]), int(parts[2])
    owners = count_card_owners(card_id)

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Да, удалить", callback_data=f"adm_card_del_do:{card_id}:{page}"),
        types.InlineKeyboardButton("❌ Отмена", callback_data=f"adm_card_view:{card_id}:{page}"),
    )
    txt = (f"⚠️ <b>Удалить карту #{card_id}?</b>\n\n"
           f"👥 У {owners} игроков есть эта карта — она пропадёт из их коллекций.\n"
           f"Действие необратимо.")
    bot.send_message(call.message.chat.id, txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_card_del_do:"))
def adm_card_del_do(call):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split(":")
    card_id, page = int(parts[1]), int(parts[2])
    delete_card(card_id)
    bot.answer_callback_query(call.id, "🗑 Карта удалена", show_alert=True)
    call.data = f"adm_cards:{page}"
    adm_cards_list(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_card_give_one:"))
def adm_card_give_one_start(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    card_id = int(call.data.split(":")[1])
    msg = bot.send_message(call.message.chat.id, f"🎁 Введи <b>USER_ID</b>, кому выдать карту #{card_id}:",
                           parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, _adm_card_give_one_step, card_id)


def _adm_card_give_one_step(message, card_id):
    try:
        uid = int(message.text.strip())
    except:
        bot.send_message(message.chat.id, "❌ Введи числовой USER_ID.", reply_markup=_adm_back_markup())
        return
    user = get_user_data(uid)
    if not user:
        bot.send_message(message.chat.id, "❌ Пользователь не найден.", reply_markup=_adm_back_markup())
        return
    add_card_to_user(uid, card_id)
    bot.send_message(message.chat.id, f"✅ Карта #{card_id} выдана <b>{user['first_name']}</b>",
                     reply_markup=_adm_back_markup(), parse_mode="HTML")


# --- ВЫДАЧА МОНЕТ ---

@bot.callback_query_handler(func=lambda call: call.data == "adm_give_coins")
def adm_give_coins_start(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
                           "💰 Введи: <b>USER_ID КОЛИЧЕСТВО</b>\nПример: <code>123456789 500</code>",
                           parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, _give_coins_step)


def _give_coins_step(message):
    try:
        parts = message.text.strip().split()
        uid, amount = int(parts[0]), int(parts[1])
        user = get_user_data(uid)
        if not user:
            bot.send_message(message.chat.id, "❌ Пользователь не найден.", reply_markup=_adm_back_markup())
            return
        update_coins(uid, amount)
        bot.send_message(message.chat.id,
                         f"✅ Начислено <b>{amount} 💰 монет</b> пользователю <b>{user['first_name']}</b>",
                         reply_markup=_adm_back_markup(), parse_mode="HTML")
    except:
        bot.send_message(message.chat.id, "❌ Ошибка. Формат: USER_ID КОЛИЧЕСТВО",
                         reply_markup=_adm_back_markup())


# --- ВЫДАЧА GEMS ---

@bot.callback_query_handler(func=lambda call: call.data == "adm_give_gems")
def adm_give_gems_start(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
                           "💎 Введи: <b>USER_ID КОЛИЧЕСТВО</b>\nПример: <code>123456789 10</code>",
                           parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, _give_gems_step)


def _give_gems_step(message):
    try:
        parts = message.text.strip().split()
        uid, amount = int(parts[0]), int(parts[1])
        user = get_user_data(uid)
        if not user:
            bot.send_message(message.chat.id, "❌ Пользователь не найден.", reply_markup=_adm_back_markup())
            return
        update_gems(uid, amount)
        bot.send_message(message.chat.id,
                         f"✅ Начислено <b>{amount} 💎 Gems</b> пользователю <b>{user['first_name']}</b>",
                         reply_markup=_adm_back_markup(), parse_mode="HTML")
    except:
        bot.send_message(message.chat.id, "❌ Ошибка. Формат: USER_ID КОЛИЧЕСТВО",
                         reply_markup=_adm_back_markup())


# --- ВЫДАЧА КАРТЫ (по голому ID) ---

@bot.callback_query_handler(func=lambda call: call.data == "adm_give_card")
def adm_give_card_start(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
                           "🃏 Введи: <b>USER_ID CARD_ID</b>\nПример: <code>123456789 5</code>",
                           parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, _give_card_step)


def _give_card_step(message):
    try:
        parts = message.text.strip().split()
        uid, card_id = int(parts[0]), int(parts[1])
        user = get_user_data(uid)
        if not user:
            bot.send_message(message.chat.id, "❌ Пользователь не найден.", reply_markup=_adm_back_markup())
            return
        add_card_to_user(uid, card_id)
        bot.send_message(message.chat.id,
                         f"✅ Карта #{card_id} выдана пользователю <b>{user['first_name']}</b>",
                         reply_markup=_adm_back_markup(), parse_mode="HTML")
    except:
        bot.send_message(message.chat.id, "❌ Ошибка. Формат: USER_ID CARD_ID", reply_markup=_adm_back_markup())


# --- СОБЫТИЯ ---

@bot.callback_query_handler(func=lambda call: call.data == "adm_events")
def adm_events_menu(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    events = get_events_admin(10)
    now = datetime.now(timezone.utc)

    txt = "🎉 <b>События</b>\n➖➖➖➖➖➖➖➖\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)

    if not events:
        txt += "Событий пока нет."
    else:
        for e in events:
            try:
                end_at = datetime.fromisoformat(e['end_at'].replace('Z', '+00:00'))
                active = end_at > now
            except:
                active = False
            status = "🟢 активно" if active else "🔴 завершено"
            txt += f"<b>{e['name']}</b> — {status}\n"
            if active:
                markup.add(types.InlineKeyboardButton(f"🛑 Завершить «{e['name']}»",
                                                       callback_data=f"adm_event_end:{e['id']}"))

    markup.add(types.InlineKeyboardButton("➕ Создать событие", callback_data="adm_event_create"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="adm_back"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt,
                      reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "adm_event_create")
def adm_event_create_start(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "🎉 Введи <b>название</b> события:", parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, _event_step_name, {})


def _event_step_name(message, data):
    data['name'] = message.text.strip()
    msg = bot.send_message(message.chat.id, "Введи <b>описание</b> события:", parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, message.from_user.id, _event_step_desc, data)


def _event_step_desc(message, data):
    data['description'] = message.text.strip()
    msg = bot.send_message(message.chat.id, "На сколько <b>дней</b> запустить событие? (число)", parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, message.from_user.id, _event_step_days, data)


def _event_step_days(message, data):
    try:
        days = int(message.text.strip())
        if days < 1:
            raise ValueError
    except:
        msg = bot.send_message(message.chat.id, "❌ Введи целое число дней (например: 7):")
        register_next_step_handler_for_user(bot, msg, message.from_user.id, _event_step_days, data)
        return
    create_event(data['name'], data['description'], days)
    bot.send_message(message.chat.id, f"✅ Событие «<b>{data['name']}</b>» запущено на {days} дн.!",
                     reply_markup=_adm_back_markup(), parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_event_end:"))
def adm_event_end_cb(call):
    if not is_admin(call.from_user.id):
        return
    event_id = int(call.data.split(":")[1])
    end_event(event_id)
    bot.answer_callback_query(call.id, "🛑 Событие завершено", show_alert=True)
    adm_events_menu(call)


# --- ИГРОКИ И БАН ---

@bot.callback_query_handler(func=lambda call: call.data == "adm_users")
def adm_users_start(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "👤 Введи <b>ID</b> или <b>@username</b> игрока для поиска:",
                           parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, _adm_users_search_step)


def _adm_users_search_step(message):
    results = search_users(message.text.strip())
    if not results:
        bot.send_message(message.chat.id, "❌ Игроки не найдены.", reply_markup=_adm_back_markup())
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for u in results:
        label = f"{u['first_name']} (@{u['username']})" if u.get('username') else f"{u['first_name']} ({u['telegram_id']})"
        markup.add(types.InlineKeyboardButton(label, callback_data=f"adm_user_view:{u['telegram_id']}"))
    markup.add(types.InlineKeyboardButton("🔙 В админку", callback_data="adm_back"))
    bot.send_message(message.chat.id, "🔍 <b>Результаты поиска:</b>", reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_user_view:"))
def adm_user_view(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    uid = int(call.data.split(":")[1])
    user = get_user_data(uid)
    if not user:
        bot.answer_callback_query(call.id, "Пользователь не найден", show_alert=True)
        return

    profile = get_public_profile(uid)
    banned = bool(user.get('banned'))
    txt = (f"👤 <b>{user['first_name']}</b> (@{user.get('username') or '—'})\n"
           f"ID: <code>{uid}</code>\n"
           f"💰 {user['coins']} | 💎 {user.get('gems', 0) or 0}\n"
           f"🎴 Карт: {profile.get('total_cards', 0) if profile else 0}\n"
           f"🚫 Забанен: {'Да' if banned else 'Нет'}")

    markup = types.InlineKeyboardMarkup()
    if banned:
        markup.add(types.InlineKeyboardButton("✅ Разбанить", callback_data=f"adm_user_ban:{uid}:0"))
    else:
        markup.add(types.InlineKeyboardButton("🚫 Забанить", callback_data=f"adm_user_ban:{uid}:1"))
    markup.add(types.InlineKeyboardButton("🔙 В админку", callback_data="adm_back"))

    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt,
                      reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_user_ban:"))
def adm_user_ban_toggle(call):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split(":")
    uid, flag = int(parts[1]), bool(int(parts[2]))
    set_user_banned(uid, flag)
    bot.answer_callback_query(call.id, "🚫 Игрок забанен" if flag else "✅ Игрок разбанен", show_alert=True)
    call.data = f"adm_user_view:{uid}"
    adm_user_view(call)


# --- АДМИНЫ (только для Гл. Администратора) ---

_pending_admin_add = {}  # user_id (кто добавляет) -> target_id, до выбора роли


def _role_label(role):
    return "👑 Гл. Администратор" if role == 'head' else "🛡 Админ"


@bot.callback_query_handler(func=lambda call: call.data == "adm_admins")
def adm_admins_menu(call):
    if not is_head_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    from config import ADMIN_ID
    admins = get_admins_list()
    admin_ids = {a['telegram_id'] for a in admins}

    txt = "👑 <b>Администраторы</b>\n➖➖➖➖➖➖➖➖\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)

    for a in admins:
        uid = a['telegram_id']
        role = a.get('role') or 'admin'
        user = get_user_data(uid)
        name = user['first_name'] if user else str(uid)
        note = " <i>(из .env)</i>" if uid == ADMIN_ID else ""
        txt += f"• {name} (<code>{uid}</code>) — {_role_label(role)}{note}\n"
        # Гл. Администратора снять нельзя — ни другим, ни даже самим собой
        if role != 'head':
            markup.add(types.InlineKeyboardButton(f"🗑 Убрать {name}", callback_data=f"adm_admin_del:{uid}"))

    if ADMIN_ID not in admin_ids:
        user = get_user_data(ADMIN_ID)
        name = user['first_name'] if user else str(ADMIN_ID)
        txt += f"• {name} (<code>{ADMIN_ID}</code>) — {_role_label('head')} <i>(из .env)</i>\n"

    markup.add(types.InlineKeyboardButton("➕ Добавить админа", callback_data="adm_admin_add"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="adm_back"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt,
                      reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "adm_admin_add")
def adm_admin_add_start(call):
    if not is_head_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
                           "➕ Введи <b>Telegram ID</b> или <b>@username</b> нового админа\n"
                           "(по @username сработает, только если этот человек уже писал боту):",
                           parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, _adm_admin_add_step)


def _adm_admin_add_step(message):
    text = message.text.strip().lstrip('@')
    target_id = None
    if text.isdigit():
        target_id = int(text)
    else:
        found = search_users(text)
        if found:
            target_id = found[0]['telegram_id']

    if not target_id:
        bot.send_message(message.chat.id, "❌ Пользователь не найден. Введи числовой Telegram ID.",
                         reply_markup=_adm_back_markup())
        return

    if get_admin_role(target_id) is not None:
        bot.send_message(message.chat.id, "Этот пользователь уже админ.", reply_markup=_adm_back_markup())
        return

    _pending_admin_add[message.from_user.id] = target_id
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("👑 Гл. Администратор", callback_data="adm_admin_role:head"),
        types.InlineKeyboardButton("🛡 Админ", callback_data="adm_admin_role:admin"),
    )
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="adm_back"))
    bot.send_message(message.chat.id, f"Назначить <code>{target_id}</code> какой ролью?",
                     reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_admin_role:"))
def adm_admin_role_pick(call):
    if not is_head_admin(call.from_user.id):
        return
    target_id = _pending_admin_add.pop(call.from_user.id, None)
    if not target_id:
        bot.answer_callback_query(call.id, "Сессия истекла, начните заново.", show_alert=True)
        return
    role = call.data.split(":")[1]
    add_admin(target_id, role=role, added_by=call.from_user.id)
    bot.answer_callback_query(call.id, f"✅ Назначен как {_role_label(role)}", show_alert=True)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    admin_start(call.message, user_id=call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_admin_del:"))
def adm_admin_del(call):
    if not is_head_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[1])
    success, msg = remove_admin(uid)
    bot.answer_callback_query(call.id, ("🗑 " if success else "❌ ") + msg, show_alert=True)
    adm_admins_menu(call)


# --- ОБЯЗАТЕЛЬНАЯ ПОДПИСКА: КАНАЛЫ ---

_pending_channel = {}  # user_id -> {'title':.., 'url':.., 'chat_id':..} — до выбора обязательности


@bot.callback_query_handler(func=lambda call: call.data == "adm_channels")
def adm_channels_menu(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    channels = get_required_channels()

    txt = "📢 <b>Каналы для подписки</b>\n➖➖➖➖➖➖➖➖\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)

    if not channels:
        txt += "Каналов пока нет."
    for ch in channels:
        badge = "🔴 обязательный" if ch.get('is_mandatory') else "🟢 необязательный"
        txt += f"{badge} — <b>{ch['title']}</b>\n   ID/чат: <code>{ch['chat_id']}</code>\n\n"
        markup.row(
            types.InlineKeyboardButton(
                "➡️ Сделать необязательным" if ch.get('is_mandatory') else "➡️ Сделать обязательным",
                callback_data=f"adm_channel_toggle:{ch['id']}:{0 if ch.get('is_mandatory') else 1}"
            ),
            types.InlineKeyboardButton("🗑", callback_data=f"adm_channel_del:{ch['id']}"),
        )

    markup.add(types.InlineKeyboardButton("➕ Добавить канал", callback_data="adm_channel_add"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="adm_back"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt,
                      reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "adm_channel_add")
def adm_channel_add_start(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
                           "📢 <b>Добавление канала</b>\n\n"
                           "Введи <b>название кнопки</b> (то, что увидит игрок):",
                           parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, _channel_step_title, {})


def _channel_step_title(message, data):
    data['title'] = message.text.strip()
    msg = bot.send_message(message.chat.id,
                           "🔗 Введи <b>пригласительную ссылку</b> на канал/группу (её увидит игрок):",
                           parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, message.from_user.id, _channel_step_url, data)


def _channel_step_url(message, data):
    data['url'] = message.text.strip()
    msg = bot.send_message(message.chat.id,
                           "🆔 Введи <b>ID чата</b> (например <code>-1001234567890</code>) или "
                           "<b>@username</b> канала/группы — по нему бот проверяет подписку.\n\n"
                           "⚠️ <b>Важно:</b> бот должен быть заранее добавлен в этот канал/группу "
                           "как <b>администратор</b> (с правом видеть участников) — иначе проверка "
                           "подписки работать не будет.",
                           parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, message.from_user.id, _channel_step_chatid, data)


def _channel_step_chatid(message, data):
    raw = message.text.strip()
    chat_id = raw if raw.startswith('@') else raw

    try:
        chat = bot.get_chat(chat_id)
    except Exception:
        msg = bot.send_message(message.chat.id,
                               "❌ Не удалось найти этот чат, или бот в нём не состоит.\n"
                               "Добавь бота в канал/группу администратором и пришли ID/@username ещё раз:")
        register_next_step_handler_for_user(bot, msg, message.from_user.id, _channel_step_chatid, data)
        return

    data['chat_id'] = chat_id
    _pending_channel[message.from_user.id] = data

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🔴 Обязательная", callback_data="adm_channel_mode:mandatory"),
        types.InlineKeyboardButton("🟢 Необязательная", callback_data="adm_channel_mode:optional"),
    )
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="adm_channel_mode_cancel"))
    bot.send_message(message.chat.id,
                     f"✅ Чат найден: <b>{chat.title or chat.username or chat_id}</b>\n\n"
                     f"Тип подписки:",
                     reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "adm_channel_mode_cancel")
def adm_channel_mode_cancel(call):
    _pending_channel.pop(call.from_user.id, None)
    bot.answer_callback_query(call.id, "Отменено")
    bot.delete_message(call.message.chat.id, call.message.message_id)
    admin_start(call.message, user_id=call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_channel_mode:"))
def adm_channel_save(call):
    if not is_admin(call.from_user.id):
        return
    data = _pending_channel.pop(call.from_user.id, None)
    if not data:
        bot.answer_callback_query(call.id, "Сессия истекла, начните заново через 📢 Каналы.", show_alert=True)
        return
    is_mandatory = call.data.split(":")[1] == 'mandatory'
    add_required_channel(data['title'], data['url'], data['chat_id'], is_mandatory)
    bot.answer_callback_query(call.id, "✅ Канал добавлен!", show_alert=True)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    admin_start(call.message, user_id=call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_channel_toggle:"))
def adm_channel_toggle(call):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split(":")
    channel_id, new_mandatory = int(parts[1]), bool(int(parts[2]))
    toggle_channel_mandatory(channel_id, new_mandatory)
    bot.answer_callback_query(call.id, "✅ Изменено")
    adm_channels_menu(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_channel_del:"))
def adm_channel_del(call):
    if not is_admin(call.from_user.id):
        return
    channel_id = int(call.data.split(":")[1])
    delete_required_channel(channel_id)
    bot.answer_callback_query(call.id, "🗑 Канал удалён", show_alert=True)
    adm_channels_menu(call)


# --- РАССЫЛКА ВСЕМ ПОЛЬЗОВАТЕЛЯМ ---

_broadcast_pending = {}  # admin_id -> (from_chat_id, message_id) сообщения-образца


@bot.callback_query_handler(func=lambda call: call.data == "adm_broadcast")
def adm_broadcast_start(call):
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
                           "📣 <b>Рассылка всем пользователям</b>\n\n"
                           "Отправьте сообщение, которое нужно разослать — текст, "
                           "видео с подписью или без, фото и т.п. Оно будет отправлено "
                           "как есть каждому пользователю бота.\n\n"
                           "Отмена — /cancel", parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, _broadcast_step_content)


def _broadcast_step_content(message):
    admin_id = message.from_user.id
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "Отменено.")
        return

    _broadcast_pending[admin_id] = (message.chat.id, message.message_id)
    total = get_all_users_count()

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Отправить всем", callback_data="adm_broadcast_confirm"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="adm_broadcast_cancel"),
    )
    bot.send_message(message.chat.id,
                     f"⚠️ Разослать это сообщение <b>{total}</b> пользователям?",
                     reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "adm_broadcast_cancel")
def adm_broadcast_cancel(call):
    bot.answer_callback_query(call.id, "Отменено")
    _broadcast_pending.pop(call.from_user.id, None)
    bot.delete_message(call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == "adm_broadcast_confirm")
def adm_broadcast_confirm(call):
    admin_id = call.from_user.id
    if not is_admin(admin_id):
        return
    pending = _broadcast_pending.pop(admin_id, None)
    if not pending:
        bot.answer_callback_query(call.id, "❌ Сообщение для рассылки не найдено, попробуйте заново", show_alert=True)
        return
    bot.answer_callback_query(call.id, "🚀 Рассылка запущена, отчёт придёт по завершении")
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      "🚀 Рассылка запущена в фоне, отчёт придёт отдельным сообщением по завершении.")

    from_chat_id, message_id = pending
    threading.Thread(
        target=_run_broadcast,
        args=(admin_id, call.message.chat.id, from_chat_id, message_id),
        daemon=True,
    ).start()


def _run_broadcast(admin_id, report_chat_id, from_chat_id, message_id):
    user_ids = get_all_user_ids()
    sent, failed = 0, 0
    for uid in user_ids:
        try:
            bot.copy_message(uid, from_chat_id, message_id)
            sent += 1
        except Exception:
            failed += 1
        # небольшая пауза, чтобы не улетать за лимиты Telegram на массовую отправку
        time.sleep(0.05)

    try:
        bot.send_message(report_chat_id,
                         f"📣 <b>Рассылка завершена</b>\n\n"
                         f"✅ Доставлено: {sent}\n"
                         f"❌ Не доставлено: {failed}\n"
                         f"👥 Всего: {len(user_ids)}",
                         parse_mode="HTML")
    except Exception:
        pass
