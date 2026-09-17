import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

RARITY_CONFIG = {
    "Common":    {"chance": 55,   "emoji": "⚪️", "ru": "Обычная",      "value": 10,    "color": "grey"},
    "Uncommon":  {"chance": 25,   "emoji": "🟢", "ru": "Необычная",    "value": 25,    "color": "green"},
    "Rare":      {"chance": 12,   "emoji": "🔵", "ru": "Редкая",       "value": 60,    "color": "blue"},
    "Epic":      {"chance": 5,    "emoji": "🟣", "ru": "Эпическая",    "value": 200,   "color": "purple"},
    "Legendary": {"chance": 2,    "emoji": "🟡", "ru": "Легендарная",  "value": 600,   "color": "gold"},
    "Mythic":    {"chance": 0.7,  "emoji": "🔴", "ru": "Мифическая",   "value": 1500,  "color": "red"},
    "Divine":    {"chance": 0.25, "emoji": "🌟", "ru": "Божественная", "value": 5000,  "color": "white"},
    "Secret":    {"chance": 0.05, "emoji": "💎", "ru": "Секретная",    "value": 15000, "color": "diamond"},
    "Limited":   {"chance": 0,    "emoji": "🎴", "ru": "Лимитная",     "value": 10000, "color": "limited"},
}

RARITY_ORDER = ["Common", "Uncommon", "Rare", "Epic", "Legendary", "Mythic", "Divine", "Secret", "Limited"]

# --- ПАКИ ---
PACK_CONFIG = {
    "standard": {
        "name": "📦 Стандартный пак",
        "price_coins": 400,
        "price_gems": 0,
        "cards_count": 3,
        "rarity_weights": {
            "Common": 55, "Uncommon": 25, "Rare": 12, "Epic": 5,
            "Legendary": 2, "Mythic": 0.7, "Divine": 0.25, "Secret": 0.05,
        },
        "description": "3 случайные карты"
    },
    "rare": {
        "name": "🔵 Редкий пак",
        "price_coins": 700,
        "price_gems": 0,
        "cards_count": 3,
        "rarity_weights": {
            "Common": 20, "Uncommon": 30, "Rare": 30, "Epic": 12,
            "Legendary": 5, "Mythic": 2, "Divine": 0.8, "Secret": 0.2,
        },
        "description": "3 карты с шансом Rare+"
    },
    "epic": {
        "name": "🟣 Эпический пак",
        "price_coins": 1200,
        "price_gems": 10,
        "cards_count": 5,
        "rarity_weights": {
            "Common": 5, "Uncommon": 15, "Rare": 30, "Epic": 30,
            "Legendary": 12, "Mythic": 5, "Divine": 2, "Secret": 1,
        },
        "description": "5 карт — гарант Epic+"
    },
    "legendary": {
        "name": "🟡 Легендарный пак",
        "price_coins": 0,
        "price_gems": 25,
        "cards_count": 5,
        "rarity_weights": {
            "Common": 0, "Uncommon": 5, "Rare": 15, "Epic": 30,
            "Legendary": 30, "Mythic": 12, "Divine": 5, "Secret": 3,
        },
        "description": "5 карт — гарант Legendary+"
    },
    "mythic": {
        "name": "🔴 Мифический пак",
        "price_coins": 0,
        "price_gems": 55,
        "cards_count": 5,
        "rarity_weights": {
            "Common": 0, "Uncommon": 0, "Rare": 5, "Epic": 20,
            "Legendary": 35, "Mythic": 25, "Divine": 10, "Secret": 5,
        },
        "description": "5 карт — гарант Mythic+"
    },
    "event": {
        "name": "🎉 Событийный пак",
        "price_coins": 500,
        "price_gems": 0,
        "cards_count": 3,
        "rarity_weights": {
            "Common": 30, "Uncommon": 25, "Rare": 20, "Epic": 12,
            "Legendary": 7, "Mythic": 3, "Divine": 1.5, "Secret": 0.5, "Limited": 1,
        },
        "description": "3 карты с шансом Limited"
    },
}

# --- МАГАЗИН: ПАКЕТЫ GEMS ---
SHOP_GEMS_PACKAGES = [
    {"gems": 10,  "price_coins": 500,  "label": "💎 10 Gems  — 500 монет"},
    {"gems": 30,  "price_coins": 1200, "label": "💎 30 Gems  — 1 200 монет"},
    {"gems": 100, "price_coins": 3500, "label": "💎 100 Gems — 3 500 монет"},
]

# --- ЗАДАНИЯ ---
# ежедневные и еженедельные задания используют одни и те же id (например
# "get_rare" встречается в обоих списках) — прогресс хранится по паре
# (task_id, period), поэтому дневной и недельный счётчики не пересекаются

DAILY_TASKS = [
    {"id": "login",        "name": "🌟 Войти в игру",              "target": 1, "reward_coins": 30,  "reward_gems": 0},
    {"id": "get_card",     "name": "🎴 Получить 5 карт",            "target": 5, "reward_coins": 60,  "reward_gems": 0},
    {"id": "open_pack",    "name": "📦 Открыть 1 пак",              "target": 1, "reward_coins": 80,  "reward_gems": 0},
    {"id": "open_packs_3", "name": "📦 Открыть 3 пака",             "target": 3, "reward_coins": 220, "reward_gems": 0},
    {"id": "arena_battle", "name": "⚔️ Провести 1 бой",             "target": 1, "reward_coins": 70,  "reward_gems": 1},
    {"id": "get_rare",     "name": "🔵 Получить 2 карты Rare",      "target": 2, "reward_coins": 90,  "reward_gems": 0},
    {"id": "get_epic",     "name": "🟣 Получить 2 карты Epic",      "target": 2, "reward_coins": 180, "reward_gems": 1},
    {"id": "get_legendary","name": "🟡 Получить 1 карту Legendary", "target": 1, "reward_coins": 350, "reward_gems": 3},
    {"id": "fuse_card",    "name": "🔀 Улучшить 1 карту",           "target": 1, "reward_coins": 120, "reward_gems": 0},
    {"id": "claim_bonus",  "name": "🎁 Забрать ежедневный бонус",   "target": 1, "reward_coins": 50,  "reward_gems": 0},
]

WEEKLY_TASKS = [
    {"id": "open_packs_10", "name": "📦 Открыть 10 паков",         "target": 10,   "reward_coins": 500,  "reward_gems": 5},
    {"id": "battles_5",     "name": "⚔️ Выиграть 5 боёв",          "target": 5,    "reward_coins": 300,  "reward_gems": 3},
    {"id": "get_rare",      "name": "🔵 Получить 10 карт Rare",     "target": 10,   "reward_coins": 400,  "reward_gems": 3},
    {"id": "get_epic",      "name": "🟣 Получить 5 карт Epic",      "target": 5,    "reward_coins": 500,  "reward_gems": 5},
    {"id": "get_mythic",    "name": "🔴 Получить 1 карту Mythic",   "target": 1,    "reward_coins": 900,  "reward_gems": 10},
    {"id": "new_card",      "name": "🔥 Получить 15 новых карт",    "target": 15,   "reward_coins": 350,  "reward_gems": 0},
    {"id": "spend_coins",   "name": "💰 Потратить 2000 монет",      "target": 2000, "reward_coins": 250,  "reward_gems": 2},
    {"id": "trade_complete","name": "🔁 Совершить 2 обмена",        "target": 2,    "reward_coins": 200,  "reward_gems": 0},
]

# --- ДОСТИЖЕНИЯ ---
# Пожизненные (не сбрасываются). Счётчики total_* растут ТОЛЬКО от настоящей
# генерации карты (бесплатный дроп / паки / ежедневный бонус) — обмен, покупка
# на площадке и выдача админом их не трогают, поэтому накрутить нельзя.
ACHIEVEMENTS = [
    {"id": "first_pack",      "name": "🎉 Первый пак",         "desc": "Открыть первый пак",              "target": 1,   "field": "packs_opened",    "reward_coins": 100,  "reward_gems": 1},
    {"id": "packs_10",        "name": "📦 Начинающий",         "desc": "Открыть 10 паков",                "target": 10,  "field": "packs_opened",    "reward_coins": 300,  "reward_gems": 3},
    {"id": "packs_100",       "name": "📦 Опытный",            "desc": "Открыть 100 паков",               "target": 100, "field": "packs_opened",    "reward_coins": 1000, "reward_gems": 10},
    {"id": "first_divine",    "name": "🌟 Прикосновение бога", "desc": "Получить первую Divine карту",    "target": 1,   "field": "divine_count",    "reward_coins": 5000, "reward_gems": 50},
    {"id": "first_secret",    "name": "💎 Хранитель тайны",    "desc": "Получить первую Secret карту",    "target": 1,   "field": "secret_count",    "reward_coins": 10000,"reward_gems": 100},
    {"id": "battles_win_10",  "name": "⚔️ Воитель",            "desc": "Выиграть 10 боёв",                "target": 10,  "field": "battles_won",     "reward_coins": 400,  "reward_gems": 4},
    {"id": "battles_win_100", "name": "⚔️ Непобедимый",        "desc": "Выиграть 100 боёв",               "target": 100, "field": "battles_won",     "reward_coins": 2000, "reward_gems": 20},
    {"id": "cards_50",        "name": "🎴 Коллекционер",       "desc": "Собрать 50 уникальных карт",      "target": 50,  "field": "unique_cards",    "reward_coins": 600,  "reward_gems": 6},
    {"id": "cards_200",       "name": "🎴 Мастер коллекций",   "desc": "Собрать 200 уникальных карт",     "target": 200, "field": "unique_cards",    "reward_coins": 3000, "reward_gems": 30},

    # Получить карт всего (пожизненно, с учётом дублей)
    {"id": "total_10",    "name": "🎴 Новичок коллекции",  "desc": "Получить 10 карт",    "target": 10,    "field": "total_cards_obtained", "reward_coins": 100,   "reward_gems": 0},
    {"id": "total_20",    "name": "🎴 Первые шаги",        "desc": "Получить 20 карт",    "target": 20,    "field": "total_cards_obtained", "reward_coins": 150,   "reward_gems": 0},
    {"id": "total_50",    "name": "🎴 Уверенный старт",    "desc": "Получить 50 карт",    "target": 50,    "field": "total_cards_obtained", "reward_coins": 300,   "reward_gems": 0},
    {"id": "total_80",    "name": "🎴 Растущий архив",     "desc": "Получить 80 карт",    "target": 80,    "field": "total_cards_obtained", "reward_coins": 450,   "reward_gems": 0},
    {"id": "total_120",   "name": "🎴 Стабильный поток",   "desc": "Получить 120 карт",   "target": 120,   "field": "total_cards_obtained", "reward_coins": 650,   "reward_gems": 1},
    {"id": "total_200",   "name": "🎴 Опытный собиратель", "desc": "Получить 200 карт",   "target": 200,   "field": "total_cards_obtained", "reward_coins": 1000,  "reward_gems": 2},
    {"id": "total_350",   "name": "🎴 Большая коллекция",  "desc": "Получить 350 карт",   "target": 350,   "field": "total_cards_obtained", "reward_coins": 1600,  "reward_gems": 4},
    {"id": "total_600",   "name": "🎴 Знаток архивов",     "desc": "Получить 600 карт",   "target": 600,   "field": "total_cards_obtained", "reward_coins": 2600,  "reward_gems": 8},
    {"id": "total_1000",  "name": "🎴 Тысяча карт",        "desc": "Получить 1000 карт",  "target": 1000,  "field": "total_cards_obtained", "reward_coins": 4200,  "reward_gems": 15},
    {"id": "total_2000",  "name": "🎴 Легенда коллекций",  "desc": "Получить 2000 карт",  "target": 2000,  "field": "total_cards_obtained", "reward_coins": 7500,  "reward_gems": 30},
    {"id": "total_5000",  "name": "🎴 Хранитель архива",   "desc": "Получить 5000 карт",  "target": 5000,  "field": "total_cards_obtained", "reward_coins": 15000, "reward_gems": 70},
    {"id": "total_10000", "name": "🎴 Бессмертный коллекционер", "desc": "Получить 10000 карт", "target": 10000, "field": "total_cards_obtained", "reward_coins": 30000, "reward_gems": 150},

    # Получить Legendary всего (пожизненно)
    {"id": "leg_1",   "name": "🟡 Легенда родилась",   "desc": "Получить 1 карту Legendary",   "target": 1,   "field": "total_legendary_obtained", "reward_coins": 400,   "reward_gems": 3},
    {"id": "leg_5",   "name": "🟡 Охотник за легендами", "desc": "Получить 5 карт Legendary",   "target": 5,   "field": "total_legendary_obtained", "reward_coins": 1200,  "reward_gems": 8},
    {"id": "leg_15",  "name": "🟡 Собиратель легенд",   "desc": "Получить 15 карт Legendary",  "target": 15,  "field": "total_legendary_obtained", "reward_coins": 3000,  "reward_gems": 18},
    {"id": "leg_35",  "name": "🟡 Повелитель легенд",   "desc": "Получить 35 карт Legendary",  "target": 35,  "field": "total_legendary_obtained", "reward_coins": 6500,  "reward_gems": 35},
    {"id": "leg_75",  "name": "🟡 Мастер легенд",       "desc": "Получить 75 карт Legendary",  "target": 75,  "field": "total_legendary_obtained", "reward_coins": 12000, "reward_gems": 65},
    {"id": "leg_150", "name": "🟡 Живая легенда",       "desc": "Получить 150 карт Legendary", "target": 150, "field": "total_legendary_obtained", "reward_coins": 22000, "reward_gems": 120},

    # Получить Mythic всего (пожизненно)
    {"id": "myth_1",   "name": "🔴 Мифический охотник",  "desc": "Получить 1 карту Mythic",   "target": 1,   "field": "total_mythic_obtained", "reward_coins": 1200,  "reward_gems": 10},
    {"id": "myth_3",   "name": "🔴 Заклинатель мифов",   "desc": "Получить 3 карты Mythic",   "target": 3,   "field": "total_mythic_obtained", "reward_coins": 3000,  "reward_gems": 22},
    {"id": "myth_8",   "name": "🔴 Повелитель мифов",    "desc": "Получить 8 карт Mythic",    "target": 8,   "field": "total_mythic_obtained", "reward_coins": 6500,  "reward_gems": 40},
    {"id": "myth_20",  "name": "🔴 Мифический владыка",  "desc": "Получить 20 карт Mythic",   "target": 20,  "field": "total_mythic_obtained", "reward_coins": 12000, "reward_gems": 70},
    {"id": "myth_50",  "name": "🔴 Хранитель мифов",     "desc": "Получить 50 карт Mythic",   "target": 50,  "field": "total_mythic_obtained", "reward_coins": 22000, "reward_gems": 130},
    {"id": "myth_100", "name": "🔴 Мифическое божество", "desc": "Получить 100 карт Mythic",  "target": 100, "field": "total_mythic_obtained", "reward_coins": 40000, "reward_gems": 250},

    # Получить Epic всего (пожизненно)
    {"id": "epic_5",   "name": "🟣 Знакомство с эпикой",  "desc": "Получить 5 карт Epic",   "target": 5,   "field": "total_epic_obtained", "reward_coins": 200,  "reward_gems": 0},
    {"id": "epic_20",  "name": "🟣 Ценитель эпики",       "desc": "Получить 20 карт Epic",  "target": 20,  "field": "total_epic_obtained", "reward_coins": 600,  "reward_gems": 3},
    {"id": "epic_50",  "name": "🟣 Мастер эпики",         "desc": "Получить 50 карт Epic",  "target": 50,  "field": "total_epic_obtained", "reward_coins": 1400, "reward_gems": 8},
    {"id": "epic_120", "name": "🟣 Коллекционер эпики",   "desc": "Получить 120 карт Epic", "target": 120, "field": "total_epic_obtained", "reward_coins": 3200, "reward_gems": 18},
    {"id": "epic_250", "name": "🟣 Легенда эпики",        "desc": "Получить 250 карт Epic", "target": 250, "field": "total_epic_obtained", "reward_coins": 6500, "reward_gems": 35},
]

# Фразы для анимации боя
BATTLE_MOVES = [
    "☄️ Техника: Раскат грома!",
    "⚔️ Удар: Рассечение небес!",
    "🛡 Защита: Небесный щит!",
    "🐉 Секретный прием: Дыхание дракона!",
    "🌪 Магия: Вихрь пустоты!",
    "👊 Обычный удар в челюсть!",
    "🔥 Техника: Огненный лотос!",
    "👻 Иллюзия: Теневой шаг!",
    "🩸 Кровавая техника: Жатва!",
    "✨ Божественное вмешательство!"
]

# Шансы событий
BATTLE_WEIGHTS = {
    "attack":   50,
    "crit":     15,
    "miss":     10,
    "dodge":    10,
    "heal":     10,
    "artifact":  5,
    "counter":   5,
    "focus":     3,
}

# Тексты событий
EVENT_TEXTS = {
    "miss": [
        "😓 {name} запыхался и промахнулся!",
        "👀 {name} отвлекся на бабочку и пропустил момент.",
        "🌀 {name} споткнулся на ровном месте."
    ],
    "dodge": [
        "💨 {name} использует 'Призрачный шаг' и уходит от удара!",
        "👻 {name} растворился в тумане, атака прошла сквозь!",
        "🛡 {name} блокировал удар духовной аурой."
    ],
    "heal": [
        "💊 {name} быстро проглотил 'Пилюлю Бессмертия'!",
        "✨ {name} использовал технику регенерации крови.",
        "🧘‍♂️ {name} открыл второе дыхание!"
    ],
    "artifact": [
        "🔮 {name} активировал скрытый артефакт 'Зеркало Небес'!",
        "⚡️ {name} достал талисман 'Гром Девяти Облаков'!",
        "🔥 {name} высвободил силу Древнего Дракона!"
    ],
    "crit": [
        "☄️ КРИТ! {name} пробил защиту врага!",
        "🩸 {name} попал в болевую точку!",
        "⚔️ {name} вложил всю душу в этот удар!"
    ],
    "attack": [
        "👊 {name} наносит прямой удар.",
        "🗡 {name} атакует с фланга.",
        "🌊 {name} использует технику волны."
    ],
    "counter": [
        "🔄 {name} отражает атаку и наносит контрудар!",
        "⚡ {name} использует технику контратаки!",
        "🛡 {name} парирует и бьет в ответ!"
    ],
    "focus": [
        "🧘 {name} сосредотачивает духовную энергию...",
        "💫 {name} входит в состояние транса.",
        "🌀 {name} накапливает ци для следующего удара."
    ]
}

# --- ЭКОНОМИКА ---
PREMIUM_COST = 5000          # устарело, оставлено для совместимости
PREMIUM_COST_GEMS = 100      # Цена премиума в Gems (в месяц)
PREMIUM_DAYS = 30
CLAN_CREATE_COST = 1000
DROP_COOLDOWN = 3
DROP_COOLDOWN_PREMIUM = 1.5  # 1 час 30 минут
FARM_COOLDOWN_HOURS = 4      # Кулдаун фарма монет
FARM_MAX_COINS = 100         # Максимум монет за фарм
MARKET_FEE_PERCENT = 5       # комиссия торговой площадки %
MAX_PENDING_TRADE_OFFERS = 20  # лимит одновременных исходящих заявок на обмен у одного игрока

# --- УЛУЧШЕНИЕ КАРТ (FUSION) ---
FUSE_REQUIRED_COPIES = 3       # сколько дублей нужно слить для +1 уровня
FUSE_LEVEL_BONUS_PERCENT = 20  # бонус к atk/hp за каждый уровень выше 1

# --- КЛАНОВЫЕ ВОЙНЫ ---
# Ставку платит лично лидер (из своих монет, не из казны — иначе только что
# созданный клан с пустой казной не смог бы воевать вообще). Победа зачисляет
# в казну победителя обе ставки + системный бонус — так казна реально растёт,
# а не просто "переливается" между кланами.
CLAN_WAR_STAKE = 250           # ставка с каждого лидера (личные монеты)
CLAN_WAR_BONUS = 150           # системный бонус в казну победителя сверх ставок
CLAN_WAR_COOLDOWN_HOURS = 6    # кулдаун на клан между войнами (и как атакующий, и как цель)

# --- КАЗНА КЛАНА: ЛИЧНОЕ ПОЛУЧЕНИЕ ---
# Любой участник клана раз в сутки может забрать себе немного монет из казны,
# но казна не должна уходить ниже неприкосновенного минимума — иначе казну
# можно было бы быстро растащить всем составом клана после войны.
CLAN_WITHDRAW_AMOUNT = 150          # сколько монет можно забрать за раз (раз в сутки)
CLAN_WITHDRAW_MIN_TREASURY = 1000   # неприкосновенный минимум, который должен остаться в казне
CLAN_WITHDRAW_COOLDOWN_HOURS = 24   # раз в сутки на каждого участника

# --- ДУНХУА ---
DUNHUA_LIST = [
    "Путешествие к бессмертию",
    "Противостояние святого",
    "Идеальный мир",
    "Боевой континент",
    "Расколотая битвой синева небес",
    "Пожиратель звёзд",
    "Великий правитель",
    "Мир бессмертных",
    "Дорога звёзд",
    "Безупречный мир",
    "Истинный бог",
    "Небесный шёлк",
    "Властелин духов",
    "Бесконечный дракон",
    "Эпоха духовных мечей",
]
