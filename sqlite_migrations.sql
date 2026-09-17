-- 1. USERS
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT NOT NULL DEFAULT '',
    coins INTEGER DEFAULT 100,
    gems INTEGER DEFAULT 0,
    packs_opened INTEGER DEFAULT 0,
    rating INTEGER DEFAULT 1000,
    premium_until TIMESTAMP,
    last_daily_bonus TIMESTAMP,
    notification_settings TEXT DEFAULT '{"drop": true}',
    referrer_id INTEGER,
    battles_won INTEGER DEFAULT 0,
    battles_total INTEGER DEFAULT 0,
    clan_id INTEGER,
    last_timed_drop TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    banned INTEGER DEFAULT 0,
    total_cards_obtained INTEGER DEFAULT 0,
    total_legendary_obtained INTEGER DEFAULT 0,
    total_mythic_obtained INTEGER DEFAULT 0,
    total_epic_obtained INTEGER DEFAULT 0,
    last_farm_at TIMESTAMP,
    premium_auto_renew INTEGER DEFAULT 1,
    total_damage_dealt INTEGER DEFAULT 0,
    last_clan_withdraw TIMESTAMP,
    free_draws_remaining INTEGER DEFAULT 0,
    premium_bonus_claimed INTEGER DEFAULT 0
);

-- 2. CARDS
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    dunhua TEXT,
    description TEXT,
    rarity TEXT NOT NULL DEFAULT 'Common',
    attack INTEGER DEFAULT 100,
    hp INTEGER DEFAULT 200,
    value INTEGER DEFAULT 10,
    image_file_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    stars_price INTEGER
);

-- 3. USER_CARDS
CREATE TABLE IF NOT EXISTS user_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    count INTEGER DEFAULT 1,
    card_level INTEGER DEFAULT 1,
    obtained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, card_id)
);

-- 4. CLANS
CREATE TABLE IF NOT EXISTS clans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    owner_id INTEGER REFERENCES users(telegram_id) ON DELETE SET NULL,
    coins INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    war_wins INTEGER DEFAULT 0,
    last_war_at TIMESTAMP
);

-- 5. CLAN_MEMBERS
CREATE TABLE IF NOT EXISTS clan_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clan_id INTEGER NOT NULL REFERENCES clans(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    role TEXT DEFAULT 'member',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(clan_id, user_id)
);

-- 6. USER_SQUADS
CREATE TABLE IF NOT EXISTS user_squads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(user_id, card_id)
);

-- 7. ARENA_QUEUE
CREATE TABLE IF NOT EXISTS arena_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE UNIQUE,
    rating INTEGER DEFAULT 1000,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    chat_id INTEGER
);

-- 8. USER_PACKS
CREATE TABLE IF NOT EXISTS user_packs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    pack_type TEXT NOT NULL,
    count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, pack_type)
);

-- 9. USER_TASKS
CREATE TABLE IF NOT EXISTS user_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    task_id TEXT NOT NULL,
    period TEXT DEFAULT 'daily',
    progress INTEGER DEFAULT 0,
    claimed INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, task_id, period)
);

-- 10. USER_ACHIEVEMENTS
CREATE TABLE IF NOT EXISTS user_achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    achievement_id TEXT NOT NULL,
    earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, achievement_id)
);

-- 11. TRADE_OFFERS
CREATE TABLE IF NOT EXISTS trade_offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    to_user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    offered_card_id INTEGER REFERENCES cards(id) ON DELETE SET NULL,
    wanted_card_id INTEGER REFERENCES cards(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 12. MARKET_LISTINGS
CREATE TABLE IF NOT EXISTS market_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    price INTEGER NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 13. EVENTS
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    start_at TIMESTAMP NOT NULL,
    end_at TIMESTAMP NOT NULL,
    pack_type TEXT DEFAULT 'event',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 14. ADMINS
CREATE TABLE IF NOT EXISTS admins (
    telegram_id INTEGER PRIMARY KEY,
    added_by INTEGER,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    role TEXT DEFAULT 'admin'
);
INSERT OR IGNORE INTO admins (telegram_id, role) VALUES (5884034743, 'head');

-- 15. REQUIRED_CHANNELS
CREATE TABLE IF NOT EXISTS required_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    is_mandatory INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 16. MARRIAGES
CREATE TABLE IF NOT EXISTS marriages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user1_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    user2_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    married_at TIMESTAMP
);

-- 17. CLAN_JOIN_REQUESTS
CREATE TABLE IF NOT EXISTS clan_join_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clan_id INTEGER NOT NULL REFERENCES clans(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(clan_id, user_id)
);

-- 18. STAR_PAYMENTS (журнал успешных оплат Telegram Stars — защита от
-- повторного зачисления, если successful_payment почему-то придёт дважды)
CREATE TABLE IF NOT EXISTS star_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_payment_charge_id TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    payload TEXT NOT NULL,
    stars_amount INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ИНДЕКСЫ
CREATE INDEX IF NOT EXISTS idx_user_cards_user ON user_cards(user_id);
CREATE INDEX IF NOT EXISTS idx_user_packs_user ON user_packs(user_id);
CREATE INDEX IF NOT EXISTS idx_user_tasks_user ON user_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_user_achievements_user ON user_achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_trade_offers_to ON trade_offers(to_user_id);
CREATE INDEX IF NOT EXISTS idx_trade_offers_from ON trade_offers(from_user_id);
CREATE INDEX IF NOT EXISTS idx_market_listings_status ON market_listings(status);
CREATE INDEX IF NOT EXISTS idx_market_listings_seller ON market_listings(seller_id);
CREATE INDEX IF NOT EXISTS idx_events_dates ON events(start_at, end_at);
CREATE INDEX IF NOT EXISTS idx_clans_name ON clans(name);
CREATE INDEX IF NOT EXISTS idx_clan_members_clan ON clan_members(clan_id);
CREATE INDEX IF NOT EXISTS idx_user_squads_user ON user_squads(user_id);
CREATE INDEX IF NOT EXISTS idx_marriages_user1 ON marriages(user1_id);
CREATE INDEX IF NOT EXISTS idx_marriages_user2 ON marriages(user2_id);
CREATE INDEX IF NOT EXISTS idx_clan_requests_clan ON clan_join_requests(clan_id);
