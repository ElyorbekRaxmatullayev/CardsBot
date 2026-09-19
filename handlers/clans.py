from telebot import types

from config import CLAN_CREATE_COST
from database import create_clan, update_coins, update_task_progress
from database import get_clan_info, get_clan_members_paginated, get_public_profile
from database import get_user_data, leave_clan, join_clan, search_clans, is_user_banned
from database import get_all_clans_list, request_join_clan, get_pending_clan_requests, accept_clan_request, reject_clan_request
from database import withdraw_from_clan_treasury
from loader import bot
from utils import safe_edit_message, safe_send_message, register_next_step_handler_for_user, reply_match


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
    markup.add(types.InlineKeyboardButton("💸 Забрать из казны", callback_data="clan_withdraw"))
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


@bot.message_handler(func=reply_match("👥 Кланы", "Кланы"))
def clan_main_menu(message, user_id=None, page=0):
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
        markup.add(types.InlineKeyboardButton("💸 Забрать из казны", callback_data="clan_withdraw"))
        if is_leader:
            markup.add(types.InlineKeyboardButton("📩 Заявки на вступление", callback_data=f"clan_reqs_{user['clan_id']}"))
            markup.add(types.InlineKeyboardButton("🗑️ Удалить клан", callback_data=f"clan_delete_confirm_{user['clan_id']}"))
        else:
            markup.add(types.InlineKeyboardButton("🚪 Выйти из клана", callback_data="clan_leave_confirm"))
        bot.send_message(message.chat.id, txt, reply_markup=markup, parse_mode="HTML")
    else:
        clans, total = get_all_clans_list(page)
        
        txt = (f"👥 <b>Кланы</b>\n\n"
               f"Вы не состоите ни в одном клане.\n"
               f"Выберите клан для вступления (заявка требует подтверждения лидера) или создайте свой!\n\n")
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        for clan in clans:
            markup.add(types.InlineKeyboardButton(f"🏰 {clan['name']} ({clan['members_count']} чел.)", callback_data=f"clan_join_req:{clan['id']}"))
        
        nav_row = []
        if page > 0:
            nav_row.append(types.InlineKeyboardButton("⬅️", callback_data=f"clan_list_page:{page - 1}"))
        
        max_pages = max(0, (total - 1) // 8)
        nav_row.append(types.InlineKeyboardButton(f"{page + 1}/{max_pages + 1}", callback_data="ignore"))
        
        if page < max_pages:
            nav_row.append(types.InlineKeyboardButton("➡️", callback_data=f"clan_list_page:{page + 1}"))
            
        markup.row(*nav_row)

        markup.add(types.InlineKeyboardButton("➕ Создать клан (1000 💰)", callback_data="clan_create"))
        markup.add(types.InlineKeyboardButton("🔍 Найти клан", callback_data="clan_search"))
        bot.send_message(message.chat.id, txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("clan_list_page:"))
def clan_list_page_cb(call):
    bot.answer_callback_query(call.id)
    page = int(call.data.split(":")[1])
    
    # Чтобы не дублировать код, вызовем основную логику (нужно удалить старое сообщение и прислать новое, или отредактировать)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    clan_main_menu(call.message, user_id=call.from_user.id, page=page)


@bot.callback_query_handler(func=lambda call: call.data == "clan_menu_back")
def clan_menu_back_cb(call):
    bot.answer_callback_query(call.id)
    clan_main_menu(call.message, user_id=call.from_user.id)


# --- ВЫХОД ИЗ КЛАНА ---

@bot.callback_query_handler(func=lambda call: call.data == "clan_withdraw")
def clan_withdraw_cb(call):
    success, result = withdraw_from_clan_treasury(call.from_user.id)
    if success:
        bot.answer_callback_query(call.id, f"✅ Вы получили {result} 💰 из казны клана!", show_alert=True)
    else:
        bot.answer_callback_query(call.id, f"❌ {result}", show_alert=True)


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


# --- УДАЛЕНИЕ КЛАНА ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("clan_delete_confirm_"))
def clan_delete_confirm(call):
    bot.answer_callback_query(call.id)
    clan_id = int(call.data.split("_")[3])
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Да, удалить", callback_data=f"clan_delete_do_{clan_id}"),
        types.InlineKeyboardButton("❌ Отмена", callback_data=f"back_clan_{clan_id}"),
    )
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      "⚠️ <b>ВЫ УВЕРЕНЫ?</b>\nЭто действие необратимо. Клан будет удален навсегда, а все участники исключены.",
                      reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("clan_delete_do_"))
def clan_delete_do(call):
    bot.answer_callback_query(call.id)
    clan_id = int(call.data.split("_")[3])
    from database import delete_clan
    success, msg = delete_clan(clan_id, call.from_user.id)
    txt = f"✅ {msg}" if success else f"❌ {msg}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_game_menu"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup)


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


@bot.callback_query_handler(func=lambda call: call.data.startswith("clan_join_req:"))
def clan_join_req_cb(call):
    clan_id = int(call.data.split(":")[1])
    user_id = call.from_user.id
    success, msg = request_join_clan(user_id, clan_id)
    bot.answer_callback_query(call.id, msg, show_alert=True)


# --- УПРАВЛЕНИЕ ЗАЯВКАМИ (ДЛЯ ЛИДЕРА) ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("clan_reqs_"))
def view_clan_requests(call):
    clan_id = int(call.data.split("_")[2])
    user_id = call.from_user.id
    clan = get_clan_info(clan_id)
    
    if not clan or clan['owner_id'] != user_id:
        bot.answer_callback_query(call.id, "У вас нет прав!", show_alert=True)
        return
        
    reqs = get_pending_clan_requests(clan_id)
    
    if not reqs:
        bot.answer_callback_query(call.id, "Нет активных заявок.", show_alert=True)
        return
        
    txt = f"📩 <b>Заявки в клан {clan['name']}</b>\n\n"
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for req in reqs:
        user_name = req['users'].get('first_name', '?')
        username = req['users'].get('username')
        display_name = f"@{username}" if username else user_name
        
        txt += f"👤 {display_name}\n"
        markup.add(
            types.InlineKeyboardButton(f"✅ Принять", callback_data=f"clan_acc_req:{req['id']}"),
            types.InlineKeyboardButton(f"❌ Отклонить", callback_data=f"clan_rej_req:{req['id']}")
        )
        
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=f"back_clan_{clan_id}"))
    safe_edit_message(bot, call.message.chat.id, call.message.message_id, txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("clan_acc_req:"))
def accept_request_cb(call):
    req_id = int(call.data.split(":")[1])
    leader_id = call.from_user.id
    success, msg = accept_clan_request(req_id, leader_id)
    bot.answer_callback_query(call.id, msg, show_alert=True)
    # Возвращаемся в главное меню кланов, чтобы обновить
    bot.delete_message(call.message.chat.id, call.message.message_id)
    clan_main_menu(call.message, user_id=leader_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("clan_rej_req:"))
def reject_request_cb(call):
    req_id = int(call.data.split(":")[1])
    leader_id = call.from_user.id
    success, msg = reject_clan_request(req_id, leader_id)
    bot.answer_callback_query(call.id, msg, show_alert=True)
    # Возвращаемся в главное меню кланов
    bot.delete_message(call.message.chat.id, call.message.message_id)
    clan_main_menu(call.message, user_id=leader_id)


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
