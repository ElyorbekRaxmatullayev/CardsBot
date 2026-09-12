import sqlite3
import os

def init_db():
    db_path = "cardsbot.db"
    sql_file = "sqlite_migrations.sql"
    
    print("Инициализация SQLite базы данных...")
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    if os.path.exists(sql_file):
        with open(sql_file, "r", encoding="utf-8") as f:
            script = f.read()
            cur.executescript(script)
            print("Миграции успешно применены!")
    else:
        print(f"Файл {sql_file} не найден!")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
