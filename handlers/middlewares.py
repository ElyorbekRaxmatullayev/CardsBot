from telebot import BaseMiddleware, CancelUpdate
from telebot.types import CallbackQuery

from database import get_or_create_user, is_admin
from loader import bot


class EnsureUserMiddleware(BaseMiddleware):
    """
    Гарантирует, что у отправителя есть запись в БД до входа в любой хендлер.
    Без этого любой хендлер, читающий get_user_data(), падает на None, если
    человек ни разу не жал /start — а в группах кнопки/текст главного меню
    видят все участники чата, а не только тот, кто запускал бота.

    /start сам создаёт пользователя с учётом реферальной ссылки — не мешаем.
    """

    def __init__(self):
        super().__init__()
        self.update_types = ['message', 'callback_query']

    def pre_process(self, update, data):
        from_user = update.from_user
        if not from_user:
            return
        if not isinstance(update, CallbackQuery):
            if update.text and update.text.startswith('/start'):
                return
        get_or_create_user(from_user.id, from_user.username, from_user.first_name)

    def post_process(self, update, data, exception):
        pass


class SubscriptionGateMiddleware(BaseMiddleware):
    """
    Перед любым сообщением/callback'ом проверяет подписку на обязательные каналы.
    Если чего-то не хватает — блокирует апдейт (CancelUpdate), обычные хендлеры
    не выполняются. Админы не гейтятся — иначе неверно настроенный канал может
    заблокировать доступ вообще всем, включая тех, кто должен это починить.
    """

    def __init__(self):
        super().__init__()
        self.update_types = ['message', 'callback_query']

    def pre_process(self, update, data):
        from_user = update.from_user
        if not from_user:
            return

        is_callback = isinstance(update, CallbackQuery)

        if is_callback:
            if update.data == 'sub_check':
                return
        else:
            if update.text and update.text.startswith('/start'):
                # /start сам показывает экран подписки после создания юзера
                return

        if is_admin(from_user.id):
            return

        from handlers.subscription import get_unsubscribed_mandatory, build_subscription_text, build_subscription_markup
        missing = get_unsubscribed_mandatory(from_user.id)
        if not missing:
            return

        if is_callback:
            names = ", ".join(ch['title'] for ch in missing)
            bot.answer_callback_query(update.id, f"🔒 Сначала подпишись: {names}", show_alert=True)
        else:
            bot.send_message(update.chat.id, build_subscription_text(missing),
                             reply_markup=build_subscription_markup(), parse_mode="HTML")

        return CancelUpdate()

    def post_process(self, update, data, exception):
        pass


def register_middlewares():
    bot.setup_middleware(EnsureUserMiddleware())
    bot.setup_middleware(SubscriptionGateMiddleware())
