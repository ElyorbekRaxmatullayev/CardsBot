from telebot import types

from database import (get_user_marriage, get_pending_marriage_request, get_sent_marriage_request,
                      propose_marriage, accept_marriage, reject_marriage, divorce, find_user_by_username,
                      get_user_data, is_user_banned, get_chat_marriages)
from loader import bot
from utils import safe_edit_message, safe_send_message, safe_delete_message, register_next_step_handler_for_user, reply_match


@bot.message_handler(func=reply_match("❤️ Даосская пара", "Даосская пара", "❤️ Брак", "Брак"))
def marriage_main_menu(message, user_id=None):
    user_id = user_id or message.from_user.id

    if is_user_banned(user_id):
        bot.send_message(message.chat.id, "⛔️ Вы заблокированы в этом боте.")
        return

    marriage = get_user_marriage(user_id)

    if marriage:
        partner_data = marriage['u2'] if marriage['user1_id'] == user_id else marriage['u1']
        partner_name = partner_data.get('first_name', '?')
        partner_username = partner_data.get('username')
        display_name = f"@{partner_username}" if partner_username else partner_name

        txt = (f"💍 <b>Ваша даосская пара</b>\n\n"
               f"❤️ Ваш партнёр: {display_name}\n\n"
               f"Вы — счастливая даосская пара! 🎉")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💔 Развестись", callback_data="marriage_divorce_confirm"))
        safe_send_message(bot, message.chat.id, txt, reply_markup=markup, parse_mode="HTML", owner_id=user_id)
        return

    pending_in = get_pending_marriage_request(user_id)
    if pending_in:
        sender = pending_in.get('u1') or {}
        sender_name = sender.get('first_name', '?')
        sender_username = sender.get('username')
        display_name = f"@{sender_username}" if sender_username else sender_name

        txt = (f"💌 <b>Входящее предложение</b>\n\n"
               f"{display_name} предлагает вам стать даосской парой! 💍")
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Принять", callback_data=f"marriage_accept:{pending_in['id']}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"marriage_reject:{pending_in['id']}")
        )
        safe_send_message(bot, message.chat.id, txt, reply_markup=markup, parse_mode="HTML", owner_id=user_id)
        return

    pending_out = get_sent_marriage_request(user_id)
    if pending_out:
        txt = "⏳ Вы уже отправили предложение о даосской паре. Ожидайте ответа партнёра!"
        bot.send_message(message.chat.id, txt)
        return

    txt = (f"💍 <b>Даосская пара</b>\n\n"
           f"Вы одиноки. Вы можете предложить союз другому игроку, и его ник появится в вашем профиле!")
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💍 Предложить союз", callback_data="marriage_propose"))
    safe_send_message(bot, message.chat.id, txt, reply_markup=markup, parse_mode="HTML", owner_id=user_id)


@bot.message_handler(func=reply_match("браки", "Браки"))
def chat_marriages_list(message):
    """Этап C (п.5 ТЗ): список даосских пар ИМЕННО этого чата — у бота нет
    доступа к полному списку участников группы через Bot API, поэтому
    показываем пары, подтвердившие предложение в этом же чате (см.
    accept_marriage/chat_id)."""
    pairs = get_chat_marriages(message.chat.id)
    if not pairs:
        txt = "💍 <b>Даосские пары этого чата</b>\n\n😔 Пока никто не нашёл свою пару здесь."
    else:
        txt = f"💍 <b>Даосские пары этого чата</b> (всего: {len(pairs)})\n➖➖➖➖➖➖➖➖\n\n"
        for m in pairs:
            u1 = get_user_data(m['user1_id'])
            u2 = get_user_data(m['user2_id'])
            n1 = f"@{u1['username']}" if u1 and u1.get('username') else (u1['first_name'] if u1 else '?')
            n2 = f"@{u2['username']}" if u2 and u2.get('username') else (u2['first_name'] if u2 else '?')
            txt += f"❤️ <b>{n1} + {n2}</b>\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💍 Позвать даосскую пару", callback_data="marriage_propose"))
    safe_send_message(bot, message.chat.id, txt, reply_markup=markup, parse_mode="HTML", owner_id=message.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "marriage_propose")
def marriage_propose_start(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
                           "💍 <b>Кому вы хотите сделать предложение?</b>\n"
                           "Введите <b>Telegram ID</b> или <b>@username</b> партнёра:\n\n"
                           "(Отмена — /cancel)", parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, process_marriage_proposal)


def process_marriage_proposal(message):
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "Действие отменено.")
        return

    raw = message.text.strip().lstrip('@')
    target_user = get_user_data(int(raw)) if raw.isdigit() else find_user_by_username(raw)

    if not target_user:
        bot.send_message(message.chat.id, "❌ Пользователь не найден. Убедитесь, что он писал боту и ID/username верны.")
        return

    target_id = target_user['telegram_id']
    success, err_msg = propose_marriage(message.from_user.id, target_id)

    if success:
        target_label = f"@{target_user['username']}" if target_user.get('username') else target_user.get('first_name', target_id)
        bot.send_message(message.chat.id, f"✅ Предложение отправлено {target_label}! Ждите ответа.")
        # Оповещаем партнёра
        try:
            bot.send_message(target_id, f"💌 <b>У вас новое предложение о даосской паре!</b>\nЗайдите в раздел ❤️ Даосская пара.", parse_mode="HTML")
        except:
            pass
    else:
        bot.send_message(message.chat.id, f"❌ Ошибка: {err_msg}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("marriage_accept:"))
def marriage_accept_cb(call):
    req_id = int(call.data.split(":")[1])
    success, msg = accept_marriage(req_id, call.from_user.id, chat_id=call.message.chat.id)
    if success:
        bot.answer_callback_query(call.id, "Поздравляем со свадьбой! 🎉", show_alert=True)
    else:
        bot.answer_callback_query(call.id, msg, show_alert=True)
    safe_delete_message(bot, call.message.chat.id, call.message.message_id)
    marriage_main_menu(call.message, user_id=call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("marriage_reject:"))
def marriage_reject_cb(call):
    req_id = int(call.data.split(":")[1])
    success, msg = reject_marriage(req_id, call.from_user.id)
    bot.answer_callback_query(call.id, "Предложение отклонено.")
    safe_delete_message(bot, call.message.chat.id, call.message.message_id)
    marriage_main_menu(call.message, user_id=call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "marriage_divorce_confirm")
def marriage_divorce_confirm(call):
    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Да, развод", callback_data="marriage_divorce_do"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="marriage_divorce_cancel")
    )
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      "💔 Вы уверены, что хотите развестись?", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "marriage_divorce_do")
def marriage_divorce_do(call):
    bot.answer_callback_query(call.id)
    divorce(call.from_user.id)
    safe_delete_message(bot, call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "💔 Вы развелись.")
    marriage_main_menu(call.message, user_id=call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "marriage_divorce_cancel")
def marriage_divorce_cancel(call):
    bot.answer_callback_query(call.id, "Отменено")
    safe_delete_message(bot, call.message.chat.id, call.message.message_id)
    marriage_main_menu(call.message, user_id=call.from_user.id)
