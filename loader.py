import telebot
from supabase import create_client, Client
from config import BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY

bot = telebot.TeleBot(BOT_TOKEN, use_class_middlewares=True)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)