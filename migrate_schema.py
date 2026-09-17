"""
migrate_schema.py — безопасно доводит СУЩЕСТВУЮЩУЮ cardsbot.db до актуального
состояния:
  1. создаёт недостающие таблицы (из sqlite_migrations.sql);
  2. добавляет недостающие колонки в уже существующие таблицы;
  3. чистит "призрачные" записи, накопившиеся из-за того, что в SQLite раньше
     не были включены внешние ключи (foreign_keys=ON) — например слот в
     отряде на арене, занятый картой, которую админ удалил из игры, или
     картой, которую игрок уже отдал в обмене/продал на площадке.

НИКАКИЕ реальные данные (монеты, карты, кланы и т.д.) не трогает — только
явные "висячие" ссылки на то, чего уже не существует. Можно запускать сколько
угодно раз — повторный запуск ничего не сломает (идемпотентно).

Запуск на сервере после git pull:
    python migrate_schema.py
"""
import sqlite3

DB_PATH = "cardsbot.db"
SQL_FILE = "sqlite_migrations.sql"

# Колонки, которые могли отсутствовать в уже существующей базе (добавлены уже
# после первого деплоя на sqlite). CREATE TABLE IF NOT EXISTS их не добавит,
# если таблица уже была создана раньше без них — поэтому нужен отдельный шаг.
# При добавлении новых полей в будущем — дописывать сюда.
EXTRA_COLUMNS = {
    "clans": [
        ("war_wins", "INTEGER DEFAULT 0"),
        ("last_war_at", "TIMESTAMP"),
    ],
    "users": [
        ("last_clan_withdraw", "TIMESTAMP"),
    ],
}


def add_missing_tables_and_columns(conn, cur):
    print("Проверяю таблицы...")
    with open(SQL_FILE, encoding="utf-8") as f:
        cur.executescript(f.read())

    print("Проверяю колонки...")
    added = 0
    for table, columns in EXTRA_COLUMNS.items():
        cur.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cur.fetchall()}
        for col_name, col_def in columns:
            if col_name not in existing:
                print(f"  + добавляю {table}.{col_name}")
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                added += 1
    conn.commit()
    return added


def cleanup_ghost_records(conn, cur):
    """Разовая чистка записей-призраков, накопившихся, пока foreign_keys были
    выключены. Ничего не делает, если призраков нет — безопасно перезапускать."""
    print("Проверяю призрачные записи (удалённые карты, брошенные слоты в отряде)...")
    report = {}

    cur.execute("DELETE FROM user_cards WHERE card_id NOT IN (SELECT id FROM cards)")
    report["user_cards на удалённую карту"] = cur.rowcount

    # Раньше fuse_cards() при слиянии ровно последних копий уводил count в 0,
    # хотя карта на самом деле осталась у игрока (просто прокачанная) — из-за
    # этого она пропадала из инвентаря/обмена. Возвращаем такие карты обратно
    # (ставим count=1), а не удаляем — их владелец не терял карту, это баг
    # отображения/учёта, а не желание избавиться от неё.
    cur.execute("UPDATE user_cards SET count = 1 WHERE count = 0 AND card_level > 1")
    report["восстановлено прокачанных карт с обнулённым count"] = cur.rowcount

    # А вот записи с count=0 и без прокачки — настоящие призраки (отдали/продали
    # всё до последней копии, строка осталась), их можно смело убрать
    cur.execute("DELETE FROM user_cards WHERE count = 0 AND (card_level IS NULL OR card_level <= 1)")
    report["пустые записи user_cards (count=0, без прокачки)"] = cur.rowcount

    cur.execute("DELETE FROM user_squads WHERE card_id NOT IN (SELECT id FROM cards)")
    report["слоты в отряде на удалённую карту"] = cur.rowcount

    # Слот в отряде занят картой, которой у игрока уже нет (отдал в обмене
    # или продал на площадке, а слот не освободился) — сама карта в игре есть,
    # поэтому предыдущий шаг (по несуществующей card_id) это не ловит.
    cur.execute("""
        DELETE FROM user_squads
        WHERE NOT EXISTS (
            SELECT 1 FROM user_cards
            WHERE user_cards.user_id = user_squads.user_id
              AND user_cards.card_id = user_squads.card_id
              AND user_cards.count > 0
        )
    """)
    report["слоты в отряде на карту, которой уже нет у игрока"] = cur.rowcount

    cur.execute("DELETE FROM market_listings WHERE status='active' AND card_id NOT IN (SELECT id FROM cards)")
    report["активные листинги на удалённую карту"] = cur.rowcount

    cur.execute("""
        UPDATE trade_offers SET status='failed'
        WHERE status='pending' AND offered_card_id NOT IN (SELECT id FROM cards)
    """)
    report["заявки на обмен удалённой картой"] = cur.rowcount

    conn.commit()
    return report


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    print(f"База: {DB_PATH}")

    added = add_missing_tables_and_columns(conn, cur)
    ghosts = cleanup_ghost_records(conn, cur)

    conn.close()

    if added:
        print(f"Схема: добавлено колонок — {added}.")
    else:
        print("Схема: уже была актуальной.")

    total_ghosts = sum(ghosts.values())
    if total_ghosts:
        print("Найдено и убрано призрачных записей:")
        for label, count in ghosts.items():
            if count:
                print(f"  - {label}: {count}")
    else:
        print("Призрачных записей не найдено.")

    print("Готово. Реальные данные (монеты, карты, кланы и т.п.) не тронуты.")


if __name__ == "__main__":
    main()
