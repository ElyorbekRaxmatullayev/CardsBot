"""
one_time_reset_2026_10.py — РАЗОВЫЙ сброс экономии после обнаружения и
починки дублирования монет (гонки в реферальном бонусе/фарме/заданиях,
см. коммит про фикс дублирования монет).

В ОТЛИЧИЕ от migrate_schema.py это НЕ идемпотентный скрипт — его нельзя
запускать больше одного раза! Повторный запуск обнулит гемы и прогресс
заданий/достижений ещё раз, уже без всякой причины.

Делает ровно четыре вещи:
  1. gems = 0 у ВСЕХ пользователей.
  2. Удаляет ВСЕ строки user_tasks и user_achievements у ВСЕХ пользователей
     (прогресс и полученные награды по заданиям/достижениям обнуляются).
  3. card_level = 1 у ВСЕХ строк user_cards (count — сколько карт у игрока —
     НЕ трогается, сами карты у игроков не отнимаются).
  4. coins = 10000 у топ-5 игроков по текущему балансу монет (только если
     у них сейчас БОЛЬШЕ 10000 — вниз, никогда не поднимает баланс).

Карты (cards, user_cards.count), кланы, браки, паки, маркет и т.д. не
трогает вообще.

Запуск на сервере (один раз!):
    python one_time_reset_2026_10.py
"""
import sqlite3

DB_PATH = "cardsbot.db"
TOP_COINS_RESET_COUNT = 5
TOP_COINS_RESET_TO = 10000


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    print(f"База: {DB_PATH}")

    answer = input(
        "Это РАЗОВЫЙ необратимый сброс: у ВСЕХ игроков обнулятся Gems, "
        "сбросится прогресс/награды заданий и достижений, все карты "
        "вернутся к 1 уровню прокачки (сами карты не теряются).\n"
        "Запускать можно только один раз. Продолжить? (yes/no): "
    )
    if answer.strip().lower() != "yes":
        print("Отменено.")
        conn.close()
        return

    cur.execute("UPDATE users SET gems = 0")
    gems_reset = cur.rowcount
    print(f"Gems обнулены у {gems_reset} пользователей.")

    cur.execute("DELETE FROM user_tasks")
    tasks_deleted = cur.rowcount
    print(f"Удалено записей прогресса заданий: {tasks_deleted}")

    cur.execute("DELETE FROM user_achievements")
    ach_deleted = cur.rowcount
    print(f"Удалено записей полученных достижений: {ach_deleted}")

    cur.execute("UPDATE user_cards SET card_level = 1 WHERE card_level > 1")
    levels_reset = cur.rowcount
    print(f"Сброшено уровней прокачки карт: {levels_reset} (count карт не менялся)")

    cur.execute(
        "SELECT telegram_id, first_name, coins FROM users WHERE coins > ? "
        "ORDER BY coins DESC LIMIT ?",
        (TOP_COINS_RESET_TO, TOP_COINS_RESET_COUNT),
    )
    top_rows = cur.fetchall()
    for telegram_id, first_name, coins in top_rows:
        cur.execute("UPDATE users SET coins = ? WHERE telegram_id = ?", (TOP_COINS_RESET_TO, telegram_id))
        print(f"  {first_name} ({telegram_id}): {coins} -> {TOP_COINS_RESET_TO}")
    print(f"Монеты сброшены до {TOP_COINS_RESET_TO} у {len(top_rows)} игроков из топа.")

    conn.commit()
    conn.close()
    print("\nГотово. Этот скрипт больше запускать не нужно — можно удалить файл.")


if __name__ == "__main__":
    main()
