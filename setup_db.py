import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Не найдены SUPABASE_URL или SUPABASE_KEY в .env")
    sys.exit(1)

SQL_FILE = os.path.join(os.path.dirname(__file__), "migrations.sql")

with open(SQL_FILE, encoding="utf-8") as f:
    SQL = f.read()

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

print(f"🔗 Подключение к: {SUPABASE_URL}")
print("📦 Запуск миграции...\n")

# Разбиваем SQL на отдельные команды
statements = []
current = []
for line in SQL.splitlines():
    stripped = line.strip()
    if stripped.startswith("--") or not stripped:
        continue
    current.append(line)
    if stripped.endswith(";"):
        stmt = "\n".join(current).strip()
        if stmt:
            statements.append(stmt)
        current = []

# Пробуем через rpc exec_sql (если функция уже создана)
def try_rpc(sql_stmt):
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
        headers=HEADERS,
        json={"query": sql_stmt},
        timeout=10
    )
    return r.status_code in (200, 201, 204)

# Пробуем создать базовые таблицы через REST API
success_count = 0
failed = []

# Сначала проверим соединение
try:
    test = requests.get(
        f"{SUPABASE_URL}/rest/v1/",
        headers=HEADERS,
        timeout=10
    )
    if test.status_code == 200:
        print("✅ Подключение к Supabase успешно!\n")
    else:
        print(f"⚠️  Статус соединения: {test.status_code}\n")
except Exception as e:
    print(f"❌ Не удалось подключиться: {e}")
    sys.exit(1)

# Пробуем каждый SQL запрос через RPC
print("🔄 Попытка выполнить миграцию через RPC...\n")

rpc_available = False
test_rpc = requests.post(
    f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
    headers=HEADERS,
    json={"query": "SELECT 1"},
    timeout=10
)

if test_rpc.status_code in (200, 201):
    rpc_available = True
    print("✅ RPC exec_sql функция доступна!\n")
    for stmt in statements:
        if try_rpc(stmt):
            success_count += 1
        else:
            # Тихо пропускаем ошибки (таблица уже существует и т.д.)
            pass
    print(f"✅ Миграция через RPC завершена!\n")
else:
    print("⚠️  RPC exec_sql не доступна. Пробуем альтернативный метод...\n")

# Проверяем, что основные таблицы существуют
print("🔍 Проверка существующих таблиц...\n")

tables_to_check = [
    "users", "cards", "user_cards", "user_packs", "user_tasks",
    "user_achievements", "trade_offers", "market_listings",
    "events", "arena_queue", "clans", "clan_members", "user_squads"
]

existing = []
missing = []

for table in tables_to_check:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}?limit=0",
        headers=HEADERS,
        timeout=10
    )
    if r.status_code == 200:
        existing.append(table)
        print(f"  ✅ {table}")
    else:
        missing.append(table)
        print(f"  ❌ {table} — НЕ НАЙДЕНА (код {r.status_code})")

print()

if missing:
    print("=" * 60)
    print("⚠️  ТРЕБУЕТСЯ РУЧНАЯ МИГРАЦИЯ")
    print("=" * 60)
    print()
    print("Следующие таблицы отсутствуют:")
    for t in missing:
        print(f"  • {t}")
    print()
    print("Пожалуйста, выполните следующие шаги:")
    print()
    print("1. Открой: https://supabase.com/dashboard")
    print("2. Выбери проект: jrsweqlbfztrjyftwlif")
    print("3. Перейди в: SQL Editor")
    print("4. Вставь содержимое файла: migrations.sql")
    print("5. Нажми 'Run'")
    print()
    print(f"📄 Файл миграции: {SQL_FILE}")
    print()

    # Показываем краткий SQL для быстрого копирования
    print("=" * 60)
    print("БЫСТРЫЙ SQL (только новые таблицы):")
    print("=" * 60)

    quick_sql_parts = [
        """ALTER TABLE users ADD COLUMN IF NOT EXISTS gems INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS packs_opened INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS rating INTEGER DEFAULT 1000;
ALTER TABLE users ADD COLUMN IF NOT EXISTS premium_until TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_daily_bonus TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notification_settings JSONB DEFAULT '{\"drop\": true}';
ALTER TABLE users ADD COLUMN IF NOT EXISTS referrer_id BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS battles_won INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS battles_total INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS clan_id INTEGER;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_timed_drop TIMESTAMPTZ;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS dunhua TEXT;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS value INTEGER DEFAULT 10;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS attack INTEGER DEFAULT 100;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS hp INTEGER DEFAULT 200;
ALTER TABLE user_cards ADD COLUMN IF NOT EXISTS card_level INTEGER DEFAULT 1;""",
    ]

    for t in missing:
        if t == "user_packs":
            quick_sql_parts.append("""CREATE TABLE IF NOT EXISTS user_packs (id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, pack_type TEXT NOT NULL, count INTEGER DEFAULT 1, UNIQUE(user_id, pack_type));""")
        elif t == "user_tasks":
            quick_sql_parts.append("""CREATE TABLE IF NOT EXISTS user_tasks (id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, task_id TEXT NOT NULL, period TEXT DEFAULT 'daily', progress INTEGER DEFAULT 0, claimed BOOLEAN DEFAULT FALSE, UNIQUE(user_id, task_id, period));""")
        elif t == "user_achievements":
            quick_sql_parts.append("""CREATE TABLE IF NOT EXISTS user_achievements (id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, achievement_id TEXT NOT NULL, earned_at TIMESTAMPTZ DEFAULT NOW(), UNIQUE(user_id, achievement_id));""")
        elif t == "trade_offers":
            quick_sql_parts.append("""CREATE TABLE IF NOT EXISTS trade_offers (id BIGSERIAL PRIMARY KEY, from_user_id BIGINT NOT NULL, to_user_id BIGINT NOT NULL, offered_card_id BIGINT, wanted_card_id BIGINT, status TEXT DEFAULT 'pending', created_at TIMESTAMPTZ DEFAULT NOW());""")
        elif t == "market_listings":
            quick_sql_parts.append("""CREATE TABLE IF NOT EXISTS market_listings (id BIGSERIAL PRIMARY KEY, seller_id BIGINT NOT NULL, card_id BIGINT NOT NULL, price INTEGER NOT NULL, status TEXT DEFAULT 'active', created_at TIMESTAMPTZ DEFAULT NOW());""")
        elif t == "events":
            quick_sql_parts.append("""CREATE TABLE IF NOT EXISTS events (id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, description TEXT, start_at TIMESTAMPTZ NOT NULL, end_at TIMESTAMPTZ NOT NULL, pack_type TEXT DEFAULT 'event');""")
        elif t == "arena_queue":
            quick_sql_parts.append("""CREATE TABLE IF NOT EXISTS arena_queue (id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL UNIQUE, rating INTEGER DEFAULT 1000, joined_at TIMESTAMPTZ DEFAULT NOW());""")
        elif t == "clans":
            quick_sql_parts.append("""CREATE TABLE IF NOT EXISTS clans (id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, owner_id BIGINT, coins INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW());""")
        elif t == "clan_members":
            quick_sql_parts.append("""CREATE TABLE IF NOT EXISTS clan_members (id BIGSERIAL PRIMARY KEY, clan_id INTEGER NOT NULL, user_id BIGINT NOT NULL, role TEXT DEFAULT 'member', UNIQUE(clan_id, user_id));""")
        elif t == "user_squads":
            quick_sql_parts.append("""CREATE TABLE IF NOT EXISTS user_squads (id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, card_id BIGINT NOT NULL, UNIQUE(user_id, card_id));""")

    print("\n".join(quick_sql_parts))
else:
    print("🎉 Все таблицы существуют! Бот готов к запуску.")
    print()
    print("Запусти бота командой:")
    print("  python main.py")
