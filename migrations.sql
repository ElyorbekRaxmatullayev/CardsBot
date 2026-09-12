-- =============================================
-- CardsBot — Полная миграция базы данных
-- Запустить в Supabase SQL Editor
-- =============================================

-- 1. USERS — основные пользователи
CREATE TABLE IF NOT EXISTS users (
    telegram_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT NOT NULL DEFAULT '',
    coins INTEGER DEFAULT 100,
    gems INTEGER DEFAULT 0,
    packs_opened INTEGER DEFAULT 0,
    rating INTEGER DEFAULT 1000,
    premium_until TIMESTAMPTZ,
    last_daily_bonus TIMESTAMPTZ,
    notification_settings JSONB DEFAULT '{"drop": true}'::jsonb,
    referrer_id BIGINT,
    battles_won INTEGER DEFAULT 0,
    battles_total INTEGER DEFAULT 0,
    clan_id INTEGER,
    last_timed_drop TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. CARDS — все карточки
CREATE TABLE IF NOT EXISTS cards (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    dunhua TEXT,
    description TEXT,
    rarity TEXT NOT NULL DEFAULT 'Common',
    attack INTEGER DEFAULT 100,
    hp INTEGER DEFAULT 200,
    value INTEGER DEFAULT 10,
    image_file_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. USER_CARDS — коллекция карточек пользователя
CREATE TABLE IF NOT EXISTS user_cards (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    card_id BIGINT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    count INTEGER DEFAULT 1,
    card_level INTEGER DEFAULT 1,
    obtained_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, card_id)
);

-- 4. CLANS — кланы
CREATE TABLE IF NOT EXISTS clans (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    owner_id BIGINT REFERENCES users(telegram_id) ON DELETE SET NULL,
    coins INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. CLAN_MEMBERS — участники кланов
CREATE TABLE IF NOT EXISTS clan_members (
    id BIGSERIAL PRIMARY KEY,
    clan_id INTEGER NOT NULL REFERENCES clans(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    role TEXT DEFAULT 'member',
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(clan_id, user_id)
);

-- 6. USER_SQUADS — отряды для арены
CREATE TABLE IF NOT EXISTS user_squads (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    card_id BIGINT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    UNIQUE(user_id, card_id)
);

-- 7. ARENA_QUEUE — очередь поиска боя
CREATE TABLE IF NOT EXISTS arena_queue (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE UNIQUE,
    rating INTEGER DEFAULT 1000,
    joined_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. USER_PACKS — инвентарь паков
CREATE TABLE IF NOT EXISTS user_packs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    pack_type TEXT NOT NULL,
    count INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, pack_type)
);

-- 9. USER_TASKS — прогресс заданий
CREATE TABLE IF NOT EXISTS user_tasks (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    task_id TEXT NOT NULL,
    period TEXT DEFAULT 'daily',
    progress INTEGER DEFAULT 0,
    claimed BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, task_id, period)
);

-- 10. USER_ACHIEVEMENTS — достижения
CREATE TABLE IF NOT EXISTS user_achievements (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    achievement_id TEXT NOT NULL,
    earned_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, achievement_id)
);

-- 11. TRADE_OFFERS — предложения обмена
CREATE TABLE IF NOT EXISTS trade_offers (
    id BIGSERIAL PRIMARY KEY,
    from_user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    to_user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    offered_card_id BIGINT REFERENCES cards(id) ON DELETE SET NULL,
    wanted_card_id BIGINT REFERENCES cards(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 12. MARKET_LISTINGS — торговая площадка
CREATE TABLE IF NOT EXISTS market_listings (
    id BIGSERIAL PRIMARY KEY,
    seller_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    card_id BIGINT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    price INTEGER NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 13. EVENTS — игровые события
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    pack_type TEXT DEFAULT 'event',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- ИНДЕКСЫ
-- =============================================
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

-- =============================================
-- ОТКЛЮЧИТЬ RLS (для простоты)
-- =============================================
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE cards DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_cards DISABLE ROW LEVEL SECURITY;
ALTER TABLE clans DISABLE ROW LEVEL SECURITY;
ALTER TABLE clan_members DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_squads DISABLE ROW LEVEL SECURITY;
ALTER TABLE arena_queue DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_packs DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_tasks DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_achievements DISABLE ROW LEVEL SECURITY;
ALTER TABLE trade_offers DISABLE ROW LEVEL SECURITY;
ALTER TABLE market_listings DISABLE ROW LEVEL SECURITY;
ALTER TABLE events DISABLE ROW LEVEL SECURITY;

-- =============================================
-- HELPER FUNCTION для API вызовов
-- =============================================
CREATE OR REPLACE FUNCTION exec_sql(query TEXT)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    EXECUTE query;
    RETURN 'OK';
EXCEPTION WHEN OTHERS THEN
    RETURN SQLERRM;
END;
$$;

-- =============================================
-- ДОПОЛНЕНИЕ: админка, улучшение карт, групповые чаты
-- =============================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS banned BOOLEAN DEFAULT FALSE;
ALTER TABLE arena_queue ADD COLUMN IF NOT EXISTS chat_id BIGINT;

-- =============================================
-- ДОПОЛНЕНИЕ: таблица администраторов
-- =============================================
CREATE TABLE IF NOT EXISTS admins (
    telegram_id BIGINT PRIMARY KEY,
    added_by BIGINT,
    added_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE admins DISABLE ROW LEVEL SECURITY;
INSERT INTO admins (telegram_id) VALUES (5884034743) ON CONFLICT (telegram_id) DO NOTHING;

-- =============================================
-- ДОПОЛНЕНИЕ: обязательная подписка на каналы
-- =============================================
CREATE TABLE IF NOT EXISTS required_channels (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    is_mandatory BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE required_channels DISABLE ROW LEVEL SECURITY;

-- =============================================
-- ДОПОЛНЕНИЕ: пожизненные счётчики для ачивок (не сбрасываются, в отличие от
-- заданий; растут только от реальной генерации карты — дроп/паки/бонус,
-- НЕ от обмена/площадки/выдачи админом, чтобы их нельзя было накрутить)
-- =============================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_cards_obtained INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_legendary_obtained INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_mythic_obtained INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_epic_obtained INTEGER DEFAULT 0;

-- =============================================
-- ДОПОЛНЕНИЕ: роли админов (head = Гл. Администратор, admin = Админ)
-- =============================================
ALTER TABLE admins ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'admin';
UPDATE admins SET role = 'head' WHERE telegram_id = 5884034743;

-- =============================================
-- ДОПОЛНЕНИЕ: Фарм монет, автопродление Premium,
--             рейтинг арены по урону, браки, заявки в кланы
-- =============================================

-- Фарм монет (каждые 4 часа)
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_farm_at TIMESTAMPTZ;

-- Автопродление Premium (включено по умолчанию)
ALTER TABLE users ADD COLUMN IF NOT EXISTS premium_auto_renew BOOLEAN DEFAULT TRUE;

-- Накопленный урон в бою (рейтинг арены)
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_damage_dealt INTEGER DEFAULT 0;

-- Браки между пользователями
CREATE TABLE IF NOT EXISTS marriages (
    id BIGSERIAL PRIMARY KEY,
    user1_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    user2_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',  -- pending / active / rejected
    created_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE marriages DISABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS idx_marriages_user1 ON marriages(user1_id);
CREATE INDEX IF NOT EXISTS idx_marriages_user2 ON marriages(user2_id);

-- Заявки на вступление в кланы (требует подтверждения лидера)
CREATE TABLE IF NOT EXISTS clan_join_requests (
    id BIGSERIAL PRIMARY KEY,
    clan_id BIGINT NOT NULL REFERENCES clans(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',  -- pending / accepted / rejected
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(clan_id, user_id)
);
ALTER TABLE clan_join_requests DISABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS idx_clan_requests_clan ON clan_join_requests(clan_id);

SELECT 'All tables created successfully!' AS result;
