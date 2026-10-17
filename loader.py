import traceback

import telebot
from config import BOT_TOKEN


class _LoggingExceptionHandler(telebot.ExceptionHandler):
    """Без этого любое исключение внутри хендлера/next_step_handler'а,
    выполняющееся в worker-потоке (а это почти всё при threaded=True),
    логируется pyTelegramBotAPI на уровне DEBUG — по умолчанию это НИГДЕ
    не видно (ни в консоли, ни в journalctl). Снаружи это выглядело как
    "бот просто ничего не ответил", хотя на деле где-то падало исключение
    (например — забыли прогнать migrate_schema.py после добавления новой
    колонки, и UPDATE/INSERT падал на "no such column"). Теперь печатаем
    полный traceback явно, чтобы такие случаи сразу было видно в логах."""
    def handle(self, exception):
        traceback.print_exc()
        return True  # считаем обработанным — не роняем поллинг из-за этого

# num_threads по умолчанию (2) обрабатывает апдейты ИЗ ВСЕХ ЧАТОВ разом —
# при всплеске сообщений в одном активном чате оба потока забиваются его
# очередью (усугубляется сетевыми вызовами вроде getChatMember в мидлварях),
# и остальные чаты вместе с ним начинают тормозить. Увеличиваем запас потоков.
bot = telebot.TeleBot(BOT_TOKEN, use_class_middlewares=True, num_threads=20,
                      exception_handler=_LoggingExceptionHandler())

from mock_supabase import create_client
supabase = create_client()