from loader import bot
from scheduler import start_scheduler

# Импортируем хендлеры, чтобы они зарегистрировались
import handlers.users
import handlers.cards
import handlers.admin
import handlers.clans
import handlers.arena
import handlers.packs
import handlers.shop
import handlers.tasks
import handlers.achievements
import handlers.trade
import handlers.marketplace
import handlers.events
import handlers.subscription
import handlers.marriage
from handlers.middlewares import register_middlewares

if __name__ == '__main__':
    register_middlewares()
    start_scheduler()
    print("🤖 Бот запущен и готов к работе!")
    bot.infinity_polling()
