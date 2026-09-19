import telebot
from config import BOT_TOKEN

# num_threads по умолчанию (2) обрабатывает апдейты ИЗ ВСЕХ ЧАТОВ разом —
# при всплеске сообщений в одном активном чате оба потока забиваются его
# очередью (усугубляется сетевыми вызовами вроде getChatMember в мидлварях),
# и остальные чаты вместе с ним начинают тормозить. Увеличиваем запас потоков.
bot = telebot.TeleBot(BOT_TOKEN, use_class_middlewares=True, num_threads=20)

from mock_supabase import create_client
supabase = create_client()