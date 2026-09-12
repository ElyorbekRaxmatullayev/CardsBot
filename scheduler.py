import threading
import time
from datetime import datetime, timedelta, timezone

from database import get_users_for_notification, ping_database, get_premium_auto_renew_candidates, disable_premium_auto_renew, update_gems, grant_premium
from loader import bot
from config import PREMIUM_COST

KEEPALIVE_INTERVAL_SECONDS = 6 * 60 * 60


def notification_loop():
    print("⏰ Планировщик уведомлений запущен")
    while True:
        try:
            now = datetime.now()
            current_hour = now.hour
            users = get_users_for_notification()

            for u in users:
                settings = u.get('notification_settings', {})
                if not settings.get('drop', True):
                    continue
                if u['last_timed_drop']:
                    last = datetime.fromisoformat(u['last_timed_drop'].replace('Z', '+00:00'))
                    diff = datetime.now(timezone.utc) - last

                    if diff > timedelta(hours=3):
                        pass
            if current_hour in [9, 14, 20] and now.minute == 0:
                send_bulk_notification()
                time.sleep(70)

            process_premium_renewals()

            time.sleep(30)

        except Exception as e:
            print(f"Error in scheduler: {e}")
            time.sleep(60)


def send_bulk_notification():
    users = get_users_for_notification()
    count = 0
    for u in users:
        if u['last_timed_drop']:
            last = datetime.fromisoformat(u['last_timed_drop'].replace('Z', '+00:00'))
            diff = datetime.now(timezone.utc) - last

            if diff > timedelta(hours=3):
                try:
                    bot.send_message(u['telegram_id'], "🔔 <b>У тебя есть карта!</b>\nПора открывать.",
                                     parse_mode="HTML")
                    count += 1
                    time.sleep(0.05)
                except:
                    pass
    print(f"⏰ Уведомления отправлены: {count} шт.")


def process_premium_renewals():
    candidates = get_premium_auto_renew_candidates()
    for c in candidates:
        user_id = c['telegram_id']
        gems = c['gems'] or 0
        if gems >= PREMIUM_COST:
            # Продлеваем
            success = update_gems(user_id, -PREMIUM_COST)
            if success:
                grant_premium(user_id, 30)
                try:
                    bot.send_message(user_id, "🌟 <b>Ваш Premium был автоматически продлён на 30 дней!</b> (Списано 100 Gems)", parse_mode="HTML")
                except:
                    pass
            else:
                disable_premium_auto_renew(user_id)
        else:
            disable_premium_auto_renew(user_id)
            try:
                bot.send_message(user_id, "⚠️ <b>Не удалось продлить Premium.</b>\nНедостаточно Gems (нужно 100). Автопродление отключено.", parse_mode="HTML")
            except:
                pass


def keepalive_loop():
    print("💓 Keep-alive для Supabase запущен")
    while True:
        try:
            ping_database()
        except Exception as e:
            print(f"Error in keepalive: {e}")
        time.sleep(KEEPALIVE_INTERVAL_SECONDS)


def start_scheduler():
    t = threading.Thread(target=notification_loop)
    t.daemon = True
    t.start()

    t2 = threading.Thread(target=keepalive_loop)
    t2.daemon = True
    t2.start()
