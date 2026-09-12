import sqlite3
import math
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

def migrate_data():
    print("Start migration from Supabase to SQLite...")
    
    # 1. Подключаемся к Supabase (настоящему)
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # 2. Подключаемся к локальной базе
    conn = sqlite3.connect("cardsbot.db")
    cur = conn.cursor()
    
    # Отключаем проверку внешних ключей на время импорта, чтобы порядок таблиц не вызывал ошибок
    cur.execute("PRAGMA foreign_keys = OFF")
    
    tables_to_migrate = [
        "users", "cards", "user_cards", "clans", "clan_members", 
        "user_squads", "arena_queue", "user_packs", "user_tasks", 
        "user_achievements", "trade_offers", "market_listings", 
        "events", "admins", "required_channels", "marriages", "clan_join_requests"
    ]
    
    for table in tables_to_migrate:
        print(f"Loading table {table}...")
        
        # Сначала очистим таблицу в SQLite, чтобы не было дублей
        cur.execute(f"DELETE FROM {table}")
        
        start = 0
        limit = 1000
        total_inserted = 0
        
        while True:
            try:
                res = supabase.table(table).select("*").range(start, start + limit - 1).execute()
                data = res.data
                
                if not data:
                    break
                    
                # Получаем названия колонок из первого элемента Supabase
                supabase_cols = list(data[0].keys())
                
                # Узнаём, какие колонки реально существуют в SQLite
                cur.execute(f"PRAGMA table_info({table})")
                sqlite_cols = [row[1] for row in cur.fetchall()]
                
                # Оставляем только те колонки, которые есть в SQLite (например, отсеиваем 'level')
                cols = [c for c in supabase_cols if c in sqlite_cols]
                
                placeholders = ",".join(["?"] * len(cols))
                col_names = ",".join(cols)
                
                insert_query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
                
                import json
                
                # Подготавливаем данные
                values_to_insert = []
                for row in data:
                    row_vals = []
                    for col in cols:
                        val = row.get(col)
                        if isinstance(val, (dict, list)):
                            val = json.dumps(val)
                        row_vals.append(val)
                    values_to_insert.append(tuple(row_vals))
                    
                cur.executemany(insert_query, values_to_insert)
                total_inserted += len(data)
                
                if len(data) < limit:
                    break
                    
                start += limit
            except Exception as e:
                # Если таблицы нет в Supabase или другая ошибка - просто пропускаем
                print(f"Error loading {table}: {e}")
                break
                
        print(f"Inserted {total_inserted} rows into {table}.")
        
    # Включаем внешние ключи обратно
    cur.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    conn.close()
    
    print("\nMigration completed! All data transferred to cardsbot.db")

if __name__ == "__main__":
    migrate_data()
