import telebot
from telebot import types

from database import get_required_channels
from loader import bot


def _is_subscribed(user_id, chat_id):
    """Проверяет подписку через getChatMember. При любой ошибке (бот не добавлен
    в чат, неверный chat_id и т.п.) считаем, что юзер прошёл проверку — плохая
    настройка канала админом не должна ронять доступ к боту для всех."""
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ('member', 'administrator', 'creator')
    except telebot.apihelper.ApiTelegramException:
        return True
    except Exception:
        return True


def get_unsubscribed_mandatory(user_id):
    """Список обязательных каналов, на которые юзер ещё не подписан"""
    missing = []
    for ch in get_required_channels():
        if not ch.get('is_mandatory'):
            continue
        if not _is_subscribed(user_id, ch['chat_id']):
            missing.append(ch)
    return missing


def build_subscription_markup():
    """Кнопки-ссылки на ВСЕ каналы (и обязательные, и необязательные) + Проверить"""
    channels = get_required_channels()
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch in channels:
        label = ch['title'] if ch.get('is_mandatory') else f"{ch['title']} (необязательно)"
        markup.add(types.InlineKeyboardButton(label, url=ch['url']))
    markup.add(types.InlineKeyboardButton("✅ Проверить", callback_data="sub_check"))
    return markup


def build_subscription_text(missing):
    txt = "🔒 <b>Чтобы пользоваться ботом, подпишись на каналы:</b>\n\n"
    for ch in missing:
        txt += f"• {ch['title']}\n"
    txt += "\nПодпишись и нажми «✅ Проверить»."
    return txt


@bot.callback_query_handler(func=lambda call: call.data == "sub_check")
def sub_check_callback(call):
    user_id = call.from_user.id
    missing = get_unsubscribed_mandatory(user_id)

    if missing:
        names = ", ".join(ch['title'] for ch in missing)
        # Не редактируем сообщение (текст не меняется — Telegram вернёт "message is
        # not modified"), просто отвечаем алертом, что подписки не хватает
        bot.answer_callback_query(call.id, f"❌ Вы ещё не подписались: {names}", show_alert=True)
        return

    bot.answer_callback_query(call.id, "✅ Подписка подтверждена!")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

    from handlers.users import get_main_reply_markup
    txt = (f"👋 Отлично, <b>{call.from_user.first_name}</b>!\n\n"
           f"🎴 Добро пожаловать в мир карточек дунхуа!\n"
           f"Собирай коллекции, сражайся на арене и обменивайся с игроками.\n\n"
           f"Выбери действие в меню ниже:")
    bot.send_message(call.message.chat.id, txt, reply_markup=get_main_reply_markup(), parse_mode="HTML")
