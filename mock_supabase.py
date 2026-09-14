import sqlite3
import json

class Response:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count

class QueryBuilder:
    def __init__(self, conn, table):
        self.conn = conn
        self.table = table
        self._select = "*"
        self._count = None
        self._where = []
        self._params = []
        self._order = None
        self._limit = None
        self._data = None
        self._action = "select"
        self._offset = None

    def select(self, cols="*", count=None):
        self._select = cols
        self._count = count
        self._action = "select"
        return self

    def insert(self, data):
        self._data = data
        self._action = "insert"
        return self

    def upsert(self, data):
        self._data = data
        self._action = "upsert"
        return self

    def update(self, data):
        self._data = data
        self._action = "update"
        return self

    def delete(self):
        self._action = "delete"
        return self

    def eq(self, col, val):
        prefix = "" if "." in col else f"{self.table}."
        self._where.append(f"{prefix}{col} = ?")
        self._params.append(val)
        return self

    def neq(self, col, val):
        prefix = "" if "." in col else f"{self.table}."
        self._where.append(f"{prefix}{col} != ?")
        self._params.append(val)
        return self

    def gt(self, col, val):
        prefix = "" if "." in col else f"{self.table}."
        self._where.append(f"{prefix}{col} > ?")
        self._params.append(val)
        return self

    def gte(self, col, val):
        prefix = "" if "." in col else f"{self.table}."
        self._where.append(f"{prefix}{col} >= ?")
        self._params.append(val)
        return self

    def lte(self, col, val):
        prefix = "" if "." in col else f"{self.table}."
        self._where.append(f"{prefix}{col} <= ?")
        self._params.append(val)
        return self

    def ilike(self, col, val):
        prefix = "" if "." in col else f"{self.table}."
        self._where.append(f"{prefix}{col} LIKE ?")
        self._params.append(val.replace("*", "%"))
        return self

    def in_(self, col, vals):
        if not vals:
            self._where.append("1=0")
            return self
        prefix = "" if "." in col else f"{self.table}."
        placeholders = ",".join(["?"] * len(vals))
        self._where.append(f"{prefix}{col} IN ({placeholders})")
        self._params.extend(vals)
        return self

    def order(self, col, desc=False):
        self._order = f"{col} {'DESC' if desc else 'ASC'}"
        return self

    def limit(self, val):
        self._limit = val
        return self

    def range(self, start, end):
        self._limit = end - start + 1
        self._offset = start
        return self

    def execute(self):
        cur = self.conn.cursor()
        
        try:
            if self._action == "select":
                return self._execute_select(cur)
            elif self._action == "insert":
                return self._execute_insert(cur)
            elif self._action == "update":
                return self._execute_update(cur)
            elif self._action == "delete":
                return self._execute_delete(cur)
            elif self._action == "upsert":
                return self._execute_upsert(cur)
        finally:
            self.conn.commit()

    def or_(self, val):
        # e.g., "user1_id.eq.123,user2_id.eq.123"
        conditions = val.split(',')
        or_clauses = []
        for cond in conditions:
            parts = cond.split('.')
            if len(parts) == 3 and parts[1] == 'eq':
                col, op, value = parts
                or_clauses.append(f"{self.table}.{col} = ?")
                self._params.append(value)
        if or_clauses:
            self._where.append("(" + " OR ".join(or_clauses) + ")")
        return self

    def _execute_select(self, cur):
        # HARDCODED JOINS for specific Supabase queries
        join_clause = ""
        select_cols = f"{self.table}.*" if self._select == "*" else self._select

        if self.table == "user_cards" and "cards(*)" in self._select:
            join_clause = "JOIN cards ON user_cards.card_id = cards.id"
            select_cols = "user_cards.count, user_cards.card_level, cards.id as c_id, cards.name as c_name, cards.dunhua as c_dunhua, cards.description as c_description, cards.rarity as c_rarity, cards.attack as c_attack, cards.hp as c_hp, cards.value as c_value, cards.image_file_id as c_image_file_id, cards.created_at as c_created_at"
        
        elif self.table == "user_squads" and "cards(*)" in self._select:
            join_clause = "JOIN cards ON user_squads.card_id = cards.id"
            select_cols = "user_squads.card_id, cards.id as c_id, cards.name as c_name, cards.dunhua as c_dunhua, cards.description as c_description, cards.rarity as c_rarity, cards.attack as c_attack, cards.hp as c_hp, cards.value as c_value, cards.image_file_id as c_image_file_id, cards.created_at as c_created_at"
        
        elif self.table == "clan_members" and "users(" in self._select:
            join_clause = "JOIN users ON clan_members.user_id = users.telegram_id"
            select_cols = "clan_members.role, users.first_name as u_first_name, users.telegram_id as u_telegram_id"
        
        elif self.table == "market_listings" and "cards(*)" in self._select and "users!seller_id(first_name)" in self._select:
            join_clause = "JOIN cards ON market_listings.card_id = cards.id JOIN users ON market_listings.seller_id = users.telegram_id"
            select_cols = "market_listings.*, cards.id as c_id, cards.name as c_name, cards.rarity as c_rarity, cards.dunhua as c_dunhua, cards.description as c_description, cards.attack as c_attack, cards.hp as c_hp, cards.value as c_value, cards.image_file_id as c_image_file_id, cards.created_at as c_created_at, users.first_name as u_first_name"

        elif self.table == "trade_offers" and "cards!offered_card_id(*)" in self._select and "users!from_user_id(first_name)" in self._select:
            join_clause = "LEFT JOIN cards ON trade_offers.offered_card_id = cards.id JOIN users ON trade_offers.from_user_id = users.telegram_id"
            select_cols = "trade_offers.*, cards.id as c_id, cards.name as c_name, cards.rarity as c_rarity, cards.dunhua as c_dunhua, cards.description as c_description, cards.attack as c_attack, cards.hp as c_hp, cards.value as c_value, cards.image_file_id as c_image_file_id, cards.created_at as c_created_at, users.first_name as u_first_name"
            
        elif self.table == "trade_offers" and "cards!offered_card_id(*)" in self._select and "users!to_user_id(first_name)" in self._select:
            join_clause = "LEFT JOIN cards ON trade_offers.offered_card_id = cards.id JOIN users ON trade_offers.to_user_id = users.telegram_id"
            select_cols = "trade_offers.*, cards.id as c_id, cards.name as c_name, cards.rarity as c_rarity, cards.dunhua as c_dunhua, cards.description as c_description, cards.attack as c_attack, cards.hp as c_hp, cards.value as c_value, cards.image_file_id as c_image_file_id, cards.created_at as c_created_at, users.first_name as u_first_name"
            
        elif self.table == "users" and self._select == "first_name, battles_won, battles_total":
             select_cols = "first_name, battles_won, battles_total"
             
        elif self.table == "cards" and self._select == "rarity":
            select_cols = "cards.rarity"
            
        elif self.table == "marriages":
            join_clause = "LEFT JOIN users as u1 ON marriages.user1_id = u1.telegram_id LEFT JOIN users as u2 ON marriages.user2_id = u2.telegram_id"
            select_cols = "marriages.*, u1.first_name as u1_first_name, u1.username as u1_username, u2.first_name as u2_first_name, u2.username as u2_username"
            
        elif self._select != "*":
            # For simple comma separated columns
            cols = [c.strip() for c in self._select.split(",")]
            valid_cols = [c for c in cols if "(" not in c and "count=" not in c]
            if valid_cols:
                select_cols = ", ".join([f"{self.table}.{c}" for c in valid_cols])

        q = f"SELECT {select_cols} FROM {self.table} {join_clause}"
        if self._where:
            q += " WHERE " + " AND ".join(self._where)
        if self._order:
            q += f" ORDER BY {self._order}"
        if self._limit:
            q += f" LIMIT {self._limit}"
        if self._offset is not None:
            q += f" OFFSET {self._offset}"

        if self._count == "exact":
            count_q = f"SELECT COUNT(*) FROM {self.table}"
            if self._where: count_q += " WHERE " + " AND ".join(self._where)
            cur.execute(count_q, self._params)
            count_val = cur.fetchone()[0]
            
            if self._select == "*" or "count=" in self._select:
                if "count=" in self._select and len(self._select.split(",")) == 1:
                    return Response([], count_val)
                cur.execute(q, self._params)
                return Response(self._format_results(cur.fetchall()), count_val)
            else:
                cur.execute(q, self._params)
                return Response(self._format_results(cur.fetchall()), count_val)
                
        cur.execute(q, self._params)
        return Response(self._format_results(cur.fetchall()))

    def _format_results(self, rows):
        res = []
        for row in rows:
            d = dict(row)
            formatted = {}
            cards_obj = {}
            users_obj = {}
            u1_obj = {}
            u2_obj = {}
            for k, v in d.items():
                if isinstance(v, str) and (v.startswith('{') or v.startswith('[')):
                    try:
                        v = json.loads(v)
                    except json.JSONDecodeError:
                        pass
                
                if k.startswith("c_"):
                    cards_obj[k[2:]] = v
                elif k.startswith("u1_"):
                    u1_obj[k[3:]] = v
                elif k.startswith("u2_"):
                    u2_obj[k[3:]] = v
                elif k.startswith("u_"):
                    users_obj[k[2:]] = v
                else:
                    formatted[k] = v
            if cards_obj and "id" in cards_obj:
                formatted['cards'] = cards_obj
            elif cards_obj and "c_id" in d:
                cards_obj['id'] = cards_obj.pop('id', d.get('c_id'))
                formatted['cards'] = cards_obj
            if users_obj:
                formatted['users'] = users_obj
            if u1_obj:
                formatted['u1'] = u1_obj
            if u2_obj:
                formatted['u2'] = u2_obj
            res.append(formatted)
        return res

    @staticmethod
    def _serialize(vals):
        # Симметрично _format_results, который парсит JSON-строки обратно в
        # dict/list при чтении: тут сериализуем dict/list в JSON-текст перед
        # записью, иначе sqlite3 падает с "type 'dict' is not supported"
        # (например при записи notification_settings как обычного dict).
        return [json.dumps(v) if isinstance(v, (dict, list)) else v for v in vals]

    def _execute_insert(self, cur):
        cols = list(self._data.keys())
        vals = self._serialize(self._data.values())
        phs = ",".join(["?"] * len(vals))
        q = f"INSERT INTO {self.table} ({','.join(cols)}) VALUES ({phs}) RETURNING *"
        try:
            cur.execute(q, vals)
            return Response([dict(r) for r in cur.fetchall()])
        except sqlite3.IntegrityError as e:
            if "UNIQUE" in str(e):
                raise Exception("23505 duplicate key")
            raise e

    def _execute_update(self, cur):
        cols = list(self._data.keys())
        vals = self._serialize(self._data.values())
        set_clause = ", ".join([f"{c} = ?" for c in cols])
        q = f"UPDATE {self.table} SET {set_clause}"
        if self._where:
            q += " WHERE " + " AND ".join(self._where)
        cur.execute(q, vals + self._params)
        # cur.rowcount = сколько строк реально затронуло — используем это как
        # атомарный "клейм" (WHERE со старым статусом), чтобы гонка из двух
        # параллельных запросов (двойной клик/автокликер) не могла провести
        # одну и ту же операцию (покупку, обмен, улучшение) дважды.
        return Response([], count=cur.rowcount)

    def _execute_delete(self, cur):
        q = f"DELETE FROM {self.table}"
        if self._where:
            q += " WHERE " + " AND ".join(self._where)
        cur.execute(q, self._params)
        return Response([], count=cur.rowcount)

    def _execute_upsert(self, cur):
        # sqlite replace into
        cols = list(self._data.keys())
        vals = self._serialize(self._data.values())
        phs = ",".join(["?"] * len(vals))
        q = f"REPLACE INTO {self.table} ({','.join(cols)}) VALUES ({phs})"
        cur.execute(q, vals)
        return Response([self._data])

class MockSupabaseClient:
    def __init__(self, db_path="cardsbot.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # SQLite по умолчанию НЕ проверяет внешние ключи — это per-connection
        # настройка, а не свойство файла БД. Без неё все ON DELETE CASCADE в
        # схеме (например cards -> user_cards/user_squads) были мёртвой буквой:
        # при удалении карты админом записи в user_squads/user_cards оставались
        # висеть "призраками" — карты нет, а слот в отряде всё ещё занят.
        self.conn.execute("PRAGMA foreign_keys = ON")

    def table(self, name):
        return QueryBuilder(self.conn, name)

def create_client():
    return MockSupabaseClient()
