from telebot import types

from database import (get_user_marriage, get_pending_marriage_request, get_sent_marriage_request,
                      propose_marriage, accept_marriage, reject_marriage, divorce, find_user_by_username,
                      get_user_data, is_user_banned)
from loader import bot
from utils import safe_edit_message, register_next_step_handler_for_user


@bot.message_handler(func=lambda m: m.text == "❤️ Брак")
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

        txt = (f"💍 <b>Ваш брак</b>\n\n"
               f"❤️ Ваш партнёр: {display_name}\n\n"
               f"Вы состоите в счастливом браке! 🎉")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💔 Развестись", callback_data="marriage_divorce_confirm"))
        bot.send_message(message.chat.id, txt, reply_markup=markup, parse_mode="HTML")
        return

    pending_in = get_pending_marriage_request(user_id)
    if pending_in:
        sender_name = pending_in['users'].get('first_name', '?')
        sender_username = pending_in['users'].get('username')
        display_name = f"@{sender_username}" if sender_username else sender_name

        txt = (f"💌 <b>Входящее предложение</b>\n\n"
               f"{display_name} предлагает вам вступить в брак! 💍")
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Принять", callback_data=f"marriage_accept:{pending_in['id']}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"marriage_reject:{pending_in['id']}")
        )
        bot.send_message(message.chat.id, txt, reply_markup=markup, parse_mode="HTML")
        return

    pending_out = get_sent_marriage_request(user_id)
    if pending_out:
        txt = "⏳ Вы уже отправили предложение о браке. Ожидайте ответа партнёра!"
        bot.send_message(message.chat.id, txt)
        return

    txt = (f"💍 <b>Бракосочетание</b>\n\n"
           f"Вы одиноки. Вы можете предложить брак другому игроку, и его ник появится в вашем профиле!")
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💍 Предложить брак", callback_data="marriage_propose"))
    bot.send_message(message.chat.id, txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "marriage_propose")
def marriage_propose_start(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
                           "💍 <b>Кому вы хотите сделать предложение?</b>\n"
                           "Введите @username партнёра (например: @durov):\n\n"
                           "(Отмена — /cancel)", parse_mode="HTML")
    register_next_step_handler_for_user(bot, msg, call.from_user.id, process_marriage_proposal)


def process_marriage_proposal(message):
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "Действие отменено.")
        return

    target_username = message.text.strip()
    target_user = find_user_by_username(target_username)

    if not target_user:
        bot.send_message(message.chat.id, "❌ Пользователь не найден. Убедитесь, что он зарегистрирован в боте и имеет @username.")
        return

    target_id = target_user['telegram_id']
    success, err_msg = propose_marriage(message.from_user.id, target_id)

    if success:
        bot.send_message(message.chat.id, f"✅ Предложение отправлено {target_username}! Ждите ответа.")
        # Оповещаем партнёра
        try:
            bot.send_message(target_id, f"💌 <b>У вас новое предложение о браке!</b>\nЗайдите в раздел ❤️ Брак.", parse_mode="HTML")
        except:
            pass
    else:
        bot.send_message(message.chat.id, f"❌ Ошибка: {err_msg}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("marriage_accept:"))
def marriage_accept_cb(call):
    req_id = int(call.data.split(":")[1])
    success, msg = accept_marriage(req_id, call.from_user.id)
    if success:
        bot.answer_callback_query(call.id, "Поздравляем со свадьбой! 🎉", show_alert=True)
    else:
        bot.answer_callback_query(call.id, msg, show_alert=True)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    marriage_main_menu(call.message, user_id=call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("marriage_reject:"))
def marriage_reject_cb(call):
    req_id = int(call.data.split(":")[1])
    success, msg = reject_marriage(req_id, call.from_user.id)
    bot.answer_callback_query(call.id, "Предложение отклонено.")
    bot.delete_message(call.message.chat.id, call.message.message_id)
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
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "💔 Вы развелись.")
    marriage_main_menu(call.message, user_id=call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "marriage_divorce_cancel")
def marriage_divorce_cancel(call):
    bot.answer_callback_query(call.id, "Отменено")
    bot.delete_message(call.message.chat.id, call.message.message_id)
    marriage_main_menu(call.message, user_id=call.from_user.id)
