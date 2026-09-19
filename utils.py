import telebot
from cachetools import TTLCache

# Кеш владельцев сообщений (живет 24 часа, до 10000 записей)
_msg_owners = TTLCache(maxsize=10000, ttl=86400)


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


def safe_send_message(bot, chat_id, text, reply_markup=None, parse_mode=None, owner_id=None):
    try:
        msg = bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
        if msg and owner_id:
            _msg_owners[f"{chat_id}_{msg.message_id}"] = owner_id
        return msg
    except Exception as e:
        print(f"Error sending message: {e}")
        return None


def reply_match(*labels):
    """Фильтр для reply-кнопок, который срабатывает на любой из переданных
    вариантов текста — передавай и версию с эмодзи (как на самой кнопке), и
    простой текст без него, чтобы бот реагировал и когда пользователь в чате
    сам набрал команду текстом (например "Получить карту" вместо "🎴 Получить
    карту"). Сравнение без учёта регистра — в чате не все аккуратно набирают
    заглавные буквы."""
    variants = {label.casefold() for label in labels}
    return lambda m: bool(m.text) and m.text.strip().casefold() in variants


def register_next_step_handler_for_user(bot, message, user_id, callback, *args, **kwargs):
    def _wrapper(m):
        if m.from_user.id != user_id:
            bot.register_next_step_handler(message, _wrapper)
            return
        callback(m, *args, **kwargs)

    bot.register_next_step_handler(message, _wrapper)
