"""
one_time_referral_payout_2026_10.py — РАЗОВАЯ доплата за рефералов.

Контекст: one_time_reset_2026_10.py сбросил монеты топ-5 игрокам (там
скопилась часть монет из-за найденного и исправленного дублирования).
Среди них могли быть игроки, которые честно пригласили много реальных
людей по реферальной ссылке — их награда за рефералов (500 монет за
каждого приглашённого) могла уйти под сброс вместе с остальным балансом.

Этот скрипт доначисляет ВСЕМ пользователям, у кого есть рефералы,
ПО 500 МОНЕТ ЗА КАЖДОГО приглашённого — считая по текущему количеству
аккаунтов с их referrer_id (это поле ничем не затронуто багом
дублирования монет — дублировалась сама выплата, а не количество
приглашённых).

В ОТЛИЧИЕ от migrate_schema.py это НЕ идемпотентный скрипт — повторный
запуск доплатит ещё раз без всякой причины (двойная оплата). Запускать
один раз.

Запуск на сервере (один раз!):
    python one_time_referral_payout_2026_10.py
"""
import sqlite3

DB_PATH = "cardsbot.db"
REFERRAL_BONUS_PER_INVITE = 500


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    print(f"База: {DB_PATH}")

    cur.execute(
        "SELECT referrer_id, COUNT(*) as cnt FROM users "
        "WHERE referrer_id IS NOT NULL GROUP BY referrer_id ORDER BY cnt DESC"
    )
    rows = cur.fetchall()

    if not rows:
        print("Рефералов не найдено, доплачивать некому.")
        conn.close()
        return

    print(f"Найдено {len(rows)} рефереров. Предпросмотр (топ-15):")
    preview_total = 0
    for referrer_id, cnt in rows[:15]:
        cur.execute("SELECT first_name FROM users WHERE telegram_id = ?", (referrer_id,))
        r = cur.fetchone()
        name = r[0] if r else "?"
        amount = cnt * REFERRAL_BONUS_PER_INVITE
        preview_total += amount
        print(f"  {name} ({referrer_id}): {cnt} рефералов -> +{amount} 💰")
    if len(rows) > 15:
        print(f"  ...и ещё {len(rows) - 15} рефереров")

    answer = input(
        "\nЭто РАЗОВАЯ доплата — каждому из списка выше начислится 500 монет "
        "ЗА КАЖДОГО приглашённого (добавится к текущему балансу, не заменит его). "
        "Запускать можно только один раз. Продолжить? (yes/no): "
    )
    if answer.strip().lower() != "yes":
        print("Отменено.")
        conn.close()
        return

    total_paid = 0
    paid_count = 0
    for referrer_id, cnt in rows:
        amount = cnt * REFERRAL_BONUS_PER_INVITE
        cur.execute("SELECT first_name, coins FROM users WHERE telegram_id = ?", (referrer_id,))
        user_row = cur.fetchone()
        if not user_row:
            print(f"  Пропущен {referrer_id}: аккаунт не найден (удалён?)")
            continue
        name, coins = user_row
        new_coins = coins + amount
        cur.execute("UPDATE users SET coins = ? WHERE telegram_id = ?", (new_coins, referrer_id))
        total_paid += amount
        paid_count += 1
        print(f"  {name} ({referrer_id}): {coins} -> {new_coins} (+{amount} за {cnt} рефералов)")

    conn.commit()
    conn.close()
    print(f"\nГотово. Выплачено {total_paid} монет {paid_count} игрокам.")
    print("Этот скрипт больше запускать не нужно — можно удалить файл.")


if __name__ == "__main__":
    main()
