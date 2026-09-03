from telebot import types

from config import CLAN_CREATE_COST
from database import create_clan, update_coins, update_task_progress
from database import get_clan_info, get_clan_members_paginated, get_public_profile
from database import get_user_data, leave_clan, join_clan, search_clans, is_user_banned
from loader import bot
from utils import safe_edit_message, safe_send_message, register_next_step_handler_for_user


# --- ГЛАВНОЕ МЕНЮ КЛАНОВ (Вход) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("back_clan_"))
def back_to_clan_menu(call):
    """Возвращает в меню конкретного клана"""
    parts = call.data.split("_")
    clan_id = int(parts[2])  # back_clan_123

    clan = get_clan_info(clan_id)
    if not clan:
        bot.send_message(call.message.chat.id, "Клан не найден")
        return

    txt = f"🏰 <b>Клан: {clan['name']}</b>\n💰 Казна: {clan['coins']}"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📜 Участники", callback_data=f"clan_mem_{clan_id}_0"))
    markup.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_game_menu"))

    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt, reply_markup=markup, parse_mode="HTML")


# --- СПИСОК УЧАСТНИКОВ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("clan_mem_"))
def show_members(call):
    parts = call.data.split("_")
    clan_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0

    members, total = get_clan_members_paginated(clan_id, page)

    markup = types.InlineKeyboardMarkup(row_width=1)

    for m in members:
        user_in_clan = m['users']
        role_emoji = "👑" if m['role'] == 'leader' else "👤"
        btn_text = f"{role_emoji} {user_in_clan['first_name']}"
        # Ведем на просмотр профиля
        markup.add(types.InlineKeyboardButton(btn_text,
                                              callback_data=f"clan_user:{user_in_clan['telegram_id']}:{clan_id}:{page}"))

    # Навигация
    nav_row = []
    if page > 0:
        nav_row.append(types.InlineKeyboardButton("⬅️", callback_data=f"clan_mem_{clan_id}_{page - 1}"))

    max_pages = (total - 1) // 5
    nav_row.append(types.InlineKeyboardButton(f"{page + 1}/{max_pages + 1}", callback_data="ignore"))

    if page < max_pages:
        nav_row.append(types.InlineKeyboardButton("➡️", callback_data=f"clan_mem_{clan_id}_{page + 1}"))

    markup.row(*nav_row)
    # Кнопка НАЗАД, которая теперь работает
    markup.add(types.InlineKeyboardButton("🔙 Назад в меню клана", callback_data=f"back_clan_{clan_id}"))

    txt = f"📜 <b>Участники клана</b> (Всего: {total})"
    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt, reply_markup=markup, parse_mode="HTML")


# --- ПРОСМОТР ЧУЖОГО ПРОФИЛЯ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("clan_user:"))
def view_public_profile(call):
    parts = call.data.split(":")
    target_id = int(parts[1])
    clan_id = parts[2]
    page = parts[3]

    p = get_public_profile(target_id)
    if not p:
        bot.send_message(call.message.chat.id, "Ошибка профиля")
        return

    txt = (f"👤 <b>Профиль игрока</b>\n"
           f"📛 Ник: {p['first_name']}\n"
           f"🎴 Карт: {p['total_cards']}\n"
           f"⚔️ Побед: {p['battles_won']} / {p['battles_total']}")

    markup = types.InlineKeyboardMarkup()
    # Возвращаем именно на ту страницу списка, откуда пришли
    markup.add(types.InlineKeyboardButton("🔙 Назад к списку", callback_data=f"clan_mem_{clan_id}_{page}"))

    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt, reply_markup=markup, parse_mode="HTML")


@bot.message_handler(func=lambda m: m.text == "👥 Кланы")
def clan_main_menu(message, user_id=None):
    # user_id передаётся явно при вызове из callback'ов (там message — чужое/бото
    # сообщение, и message.from_user в нём — не тот, кто реально нажал кнопку)
    user_id = user_id or message.from_user.id

    if is_user_banned(user_id):
        bot.send_message(message.chat.id, "⛔️ Вы заблокированы в этом боте.")
        return

    user = get_user_data(user_id)

    if user['clan_id']:
        clan = get_clan_info(user['clan_id'])
        is_leader = clan and clan['owner_id'] == user_id
        txt = (f"🏰 <b>Клан: {clan['name']}</b>\n"
               f"💰 Казна: {clan['coins']}\n"
               f"👑 Роль: {'Лидер' if is_leader else 'Участник'}")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📜 Участники", callback_data=f"clan_mem_{user['clan_id']}_0"))
        if not is_leader:
            markup.add(types.InlineKeyboardButton("🚪 Выйти из клана", callback_data="clan_leave_confirm"))
        bot.send_message(message.chat.id, txt, reply_markup=markup, parse_mode="HTML")
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ Создать клан", callback_data="clan_create"))
        markup.add(types.InlineKeyboardButton("🔍 Найти клан", callback_data="clan_search"))
        txt = (f"👥 <b>Кланы</b>\n\n"
               f"Вы не состоите ни в одном клане.\n"
               f"Создайте свой или найдите существующий!")
        bot.send_message(message.chat.id, txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "clan_menu_back")
def clan_menu_back_cb(call):
    bot.answer_callback_query(call.id)
    clan_main_menu(call.message, user_id=call.from_user.id)


# --- ВЫХОД ИЗ КЛАНА ---

@bot.callback_query_handler(func=lambda call: call.data == "clan_leave_confirm")
def clan_leave_confirm(call):
    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Да, выйти", callback_data="clan_leave_do"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="clan_leave_cancel"),
    )
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      "⚠️ Вы уверены, что хотите покинуть клан?",
                      reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "clan_leave_do")
def clan_leave_do(call):
    bot.answer_callback_query(call.id)
    success, msg = leave_clan(call.from_user.id)
    txt = f"✅ {msg}" if success else f"❌ {msg}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_game_menu"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "clan_leave_cancel")
def clan_leave_cancel(call):
    bot.answer_callback_query(call.id, "Отменено")
    bot.delete_message(call.message.chat.id, call.message.message_id)


# --- ПОИСК КЛАНА ---

@bot.callback_query_handler(func=lambda call: call.data == "clan_search")
def clan_search_cb(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
                           "🔍 Введите название клана для поиска:\n(Отмена — /cancel)")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, _clan_search_step)


def _clan_search_step(message):
    back_markup = types.InlineKeyboardMarkup()
    back_markup.add(types.InlineKeyboardButton("🔙 Кланы", callback_data="clan_menu_back"))

    if message.text == '/cancel':
        bot.send_message(message.chat.id, "Поиск отменён.", reply_markup=back_markup)
        return
    results = search_clans(message.text.strip())
    if not results:
        bot.send_message(message.chat.id, "❌ Кланы не найдены. Попробуйте другое название.",
                         reply_markup=back_markup)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    txt = "🔍 <b>Результаты поиска:</b>\n\n"
    for clan in results:
        txt += f"🏰 <b>{clan['name']}</b>\n"
        markup.add(types.InlineKeyboardButton(
            f"➡️ Вступить в {clan['name']}",
            callback_data=f"clan_join:{clan['id']}"
        ))
    markup.add(types.InlineKeyboardButton("🔙 Кланы", callback_data="clan_menu_back"))
    bot.send_message(message.chat.id, txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("clan_join:"))
def clan_join_cb(call):
    clan_id = int(call.data.split(":")[1])
    user_id = call.from_user.id
    success, msg = join_clan(user_id, clan_id)
    bot.answer_callback_query(call.id, msg, show_alert=True)
    if success:
        bot.delete_message(call.message.chat.id, call.message.message_id)


# --- СОЗДАНИЕ КЛАНА ---

@bot.callback_query_handler(func=lambda call: call.data == "clan_create")
def start_create_clan(call):
    user = get_user_data(call.from_user.id)

    if user['coins'] < CLAN_CREATE_COST:
        bot.answer_callback_query(call.id, f"Нужно {CLAN_CREATE_COST} монет!", show_alert=True)
        return

    msg = bot.send_message(call.message.chat.id,
                           f"🏰 Введите название клана:\n"
                           f"(3–15 символов, цена: 💰{CLAN_CREATE_COST})\n\nОтмена — /cancel")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, process_clan_creation)


def process_clan_creation(message):
    back_markup = types.InlineKeyboardMarkup()
    back_markup.add(types.InlineKeyboardButton("🔙 Кланы", callback_data="clan_menu_back"))

    if message.text == '/cancel':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=back_markup)
        return

    name = message.text.strip()
    user_id = message.from_user.id

    if len(name) < 3 or len(name) > 15:
        bot.send_message(message.chat.id, "❌ Название должно быть от 3 до 15 символов.")
        return

    if update_coins(user_id, -CLAN_CREATE_COST):
        success, res = create_clan(user_id, name)
        if success:
            update_task_progress(user_id, "spend_coins", "weekly", increment=CLAN_CREATE_COST)
            bot.send_message(message.chat.id, f"✅ Клан <b>{name}</b> создан!",
                             reply_markup=back_markup, parse_mode="HTML")
        else:
            update_coins(user_id, CLAN_CREATE_COST)
            bot.send_message(message.chat.id, f"❌ Ошибка: {res}", reply_markup=back_markup)
    else:
        bot.send_message(message.chat.id, "❌ Недостаточно средств.", reply_markup=back_markup)
