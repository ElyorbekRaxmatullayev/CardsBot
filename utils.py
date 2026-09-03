import telebot


def safe_edit_message(bot, chat_id, message_id, text, reply_markup=None, parse_mode=None,
                      disable_web_page_preview=True):
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview
        )
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" in str(e):
            pass
        else:
            print(f"Error editing message: {e}")


def safe_send_message(bot, chat_id, text, reply_markup=None, parse_mode=None):
    try:
        return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        print(f"Error sending message: {e}")
        return None


def register_next_step_handler_for_user(bot, message, user_id, callback, *args, **kwargs):
    def _wrapper(m):
        if m.from_user.id != user_id:
            bot.register_next_step_handler(message, _wrapper)
            return
        callback(m, *args, **kwargs)

    bot.register_next_step_handler(message, _wrapper)
