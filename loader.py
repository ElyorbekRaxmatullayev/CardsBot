import telebot
from config import BOT_TOKEN

bot = telebot.TeleBot(BOT_TOKEN, use_class_middlewares=True)

from mock_supabase import create_client
supabase = create_client()