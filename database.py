from datetime import datetime, timedelta, timezone

from loader import supabase


def ping_database():
    supabase.table("users").select("telegram_id").limit(1).execute()


def get_or_create_user(user_id, username, first_name, referrer_id=None):
    res = supabase.table("users").select("*").eq("telegram_id", user_id).execute()

    if not res.data:
        data = {
            "telegram_id": user_id,
            "username": username,
            "first_name": first_name,
            "referrer_id": referrer_id,
            "coins": 100
        }
        try:
            supabase.table("users").insert(data).execute()
        except Exception as e:
            if "23505" not in str(e) and "duplicate key" not in str(e):
                raise

        if referrer_id:
            try:
                current_ref = supabase.table("users").select("coins").eq("telegram_id", referrer_id).execute()
                if current_ref.data:
                    new_coins = current_ref.data[0]['coins'] + 500
                    supabase.table("users").update({"coins": new_coins}).eq("telegram_id", referrer_id).execute()
                    return True
            except:
                pass
        return False
    return None


def get_all_cards():
    res = supabase.table("cards").select("*").execute()
    return res.data


def get_user_inventory(user_id):
    """
    Получает все карты пользователя.
    Возвращает список объектов: [{'count': 1, 'cards': {...data...}}, ...]
    """
    res = supabase.table("user_cards").select("count, card_level, cards(*)").eq("user_id", user_id).execute()
    return res


def add_card_to_user(user_id, card_id):
    existing = supabase.table("user_cards").select("*").eq("user_id", user_id).eq("card_id", card_id).execute()

    if existing.data:
        new_count = existing.data[0]['count'] + 1
        supabase.table("user_cards").update({"count": new_count}).eq("id", existing.data[0]['id']).execute()
        return True, new_count
    else:
        supabase.table("user_cards").insert({"user_id": user_id, "card_id": card_id}).execute()
        return False, 1


def on_card_obtained(user_id, card, is_dup):
    rarity = card.get('rarity')
    rarity_task_id = {
        'Rare': 'get_rare', 'Epic': 'get_epic',
        'Legendary': 'get_legendary', 'Mythic': 'get_mythic',
    }.get(rarity)

    for period in ("daily", "weekly"):
        update_task_progress(user_id, "get_card", period)
        if not is_dup:
            update_task_progress(user_id, "new_card", period)
        if rarity_task_id:
            update_task_progress(user_id, rarity_task_id, period)

    updates = {}
    user = get_user_data(user_id)
    if not user:
        return
    updates["total_cards_obtained"] = (user.get('total_cards_obtained') or 0) + 1
    if rarity == 'Legendary':
        updates["total_legendary_obtained"] = (user.get('total_legendary_obtained') or 0) + 1
    elif rarity == 'Mythic':
        updates["total_mythic_obtained"] = (user.get('total_mythic_obtained') or 0) + 1
    elif rarity == 'Epic':
        updates["total_epic_obtained"] = (user.get('total_epic_obtained') or 0) + 1
    supabase.table("users").update(updates).eq("telegram_id", user_id).execute()


def update_last_drop(user_id, timestamp):
    supabase.table("users").update({"last_timed_drop": timestamp}).eq("telegram_id", user_id).execute()


def get_top_users(limit=10):
    res = supabase.table("users").select("first_name, coins").order("coins", desc=True).limit(limit).execute()
    return res.data


def add_new_card_to_db(data):
    supabase.table("cards").insert(data).execute()


def get_user_data(user_id):
    res = supabase.table("users").select("*").eq("telegram_id", user_id).execute()
    return res.data[0] if res.data else None


def is_premium(user):
    if not user.get('premium_until'): return False
    until = datetime.fromisoformat(user['premium_until'].replace('Z', '+00:00'))
    return until > datetime.now(timezone.utc)


def update_coins(user_id, amount):
    user = get_user_data(user_id)
    new_balance = user['coins'] + amount
    if new_balance < 0: return False
    supabase.table("users").update({"coins": new_balance}).eq("telegram_id", user_id).execute()
    return True


def get_user_team(user_id):
    res = supabase.table("user_teams").select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None


def set_user_team(user_id, c1, c2, c3):
    data = {"user_id": user_id, "card_1": c1, "card_2": c2, "card_3": c3}
    supabase.table("user_teams").upsert(data).execute()


def get_card_by_id(card_id):
    res = supabase.table("cards").select("*").eq("id", card_id).execute()
    return res.data[0] if res.data else None


def create_clan(owner_id, name):
    try:
        res = supabase.table("clans").insert({"owner_id": owner_id, "name": name}).execute()
        clan_id = res.data[0]['id']
        supabase.table("clan_members").insert({"clan_id": clan_id, "user_id": owner_id, "role": "leader"}).execute()
        supabase.table("users").update({"clan_id": clan_id}).eq("telegram_id", owner_id).execute()
        return True, "Клан создан!"
    except Exception as e:
        return False, f"Ошибка (возможно имя занято): {e}"


def get_clan_info(clan_id):
    res = supabase.table("clans").select("*").eq("id", clan_id).execute()
    return res.data[0] if res.data else None


def get_clan_name(clan_id):
    if not clan_id:
        return "Нет"

    res = supabase.table("clans").select("name").eq("id", clan_id).execute()
    if res.data:
        return res.data[0]['name']
    return "Неизвестно"


def get_clan_members(clan_id):
    res = supabase.table("clan_members").select("role, users(first_name, telegram_id)").eq("clan_id", clan_id).execute()
    return res.data


def get_top_by_coins(limit=10):
    res = supabase.table("users").select("first_name, coins").order("coins", desc=True).limit(limit).execute()
    return res.data


def get_top_by_referrals(limit=10):
    res = supabase.table("users").select("referrer_id").execute()

    counts = {}
    if res.data:
        for row in res.data:
            rid = row.get('referrer_id')
            if rid is not None:
                counts[rid] = counts.get(rid, 0) + 1

    sorted_ids = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]

    result = []
    for uid, count in sorted_ids:
        u = get_user_data(uid)
        if u:
            result.append({"first_name": u['first_name'], "count": count})
    return result


def get_top_by_cards_count(limit=10):
    """Топ по суммарному количеству карт (с учётом дублей)"""
    res = supabase.table("user_cards").select("user_id, count").execute()
    totals = {}
    for row in (res.data or []):
        uid = row['user_id']
        totals[uid] = totals.get(uid, 0) + (row.get('count') or 0)

    sorted_ids = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:limit]
    result = []
    for uid, total in sorted_ids:
        u = get_user_data(uid)
        if u:
            result.append({"first_name": u['first_name'], "count": total})
    return result


def get_top_by_value(limit=10):
    """Топ по суммарной стоимости коллекции (value карты * количество).
    Джойн card(value) делаем вручную в Python — мок supabase поверх sqlite
    не умеет произвольные embedded-select'ы вида cards(value), только
    захардкоженные cards(*) в паре мест, поэтому полагаться на него тут нельзя."""
    card_values = {c['id']: (c.get('value') or 0) for c in (get_all_cards() or [])}

    res = supabase.table("user_cards").select("user_id, card_id, count").execute()
    totals = {}
    for row in (res.data or []):
        uid = row['user_id']
        value = card_values.get(row['card_id'], 0) * (row.get('count') or 0)
        totals[uid] = totals.get(uid, 0) + value

    sorted_ids = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:limit]
    result = []
    for uid, total in sorted_ids:
        u = get_user_data(uid)
        if u:
            result.append({"first_name": u['first_name'], "value": total})
    return result


# --- ЕЖЕДНЕВНЫЙ БОНУС ---
def check_daily_bonus(user_id):
    user = get_user_data(user_id)
    now = datetime.now(timezone.utc)

    if not user['last_daily_bonus']:
        return True

    last = datetime.fromisoformat(user['last_daily_bonus'].replace('Z', '+00:00'))
    return (now - last).days >= 1


def set_daily_bonus_taken(user_id):
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("users").update({"last_daily_bonus": now}).eq("telegram_id", user_id).execute()


# --- КЛАНЫ: ПАГИНАЦИЯ И ПРОФИЛЬ ---
def get_clan_members_paginated(clan_id, page=0, page_size=5):
    start = page * page_size
    end = start + page_size - 1  # Supabase range is inclusive

    # Получаем общее кол-во
    count_res = supabase.table("clan_members").select("*", count="exact").eq("clan_id", clan_id).execute()
    total_count = count_res.count

    # Получаем срез
    res = supabase.table("clan_members").select("role, users(first_name, telegram_id)").eq("clan_id", clan_id).range(
        start, end).execute()

    return res.data, total_count


def get_public_profile(user_id):
    """Данные для просмотра чужого профиля"""
    res = supabase.table("users").select("first_name, battles_won, battles_total").eq("telegram_id", user_id).execute()
    if not res.data: return None
    user = res.data[0]

    # Считаем карты
    cards_res = supabase.table("user_cards").select("*", count="exact").eq("user_id", user_id).execute()
    total_cards = cards_res.count

    user['total_cards'] = total_cards
    return user


def get_users_for_notification():
    res = supabase.table("users").select("telegram_id, last_timed_drop, notification_settings").execute()
    return res.data


# --- ОТРЯД (SQUAD) ---

def get_user_squad(user_id):
    """Получает список карт в отряде (максимум 5), с учётом уровня после слияния"""
    # Join с таблицей cards, чтобы сразу получить статы
    res = supabase.table("user_squads").select("card_id, cards(*)").eq("user_id", user_id).execute()
    # Преобразуем в чистый список карт
    cards = [dict(item['cards']) for item in (res.data or []) if item.get('cards')]
    if not cards:
        return []

    # Подтягиваем card_level из user_cards, чтобы слияние карт реально влияло на статы в бою
    card_ids = [c['id'] for c in cards]
    levels_res = supabase.table("user_cards").select("card_id, card_level").eq("user_id", user_id).in_("card_id", card_ids).execute()
    level_map = {row['card_id']: (row.get('card_level') or 1) for row in (levels_res.data or [])}
    for c in cards:
        c['card_level'] = level_map.get(c['id'], 1)
    return cards


def toggle_squad_member(user_id, card_id):
    """Добавляет или убирает карту из отряда"""
    # 1. Проверяем, есть ли уже карта
    existing = supabase.table("user_squads").select("*").eq("user_id", user_id).eq("card_id", card_id).execute()

    if existing.data:
        # УБИРАЕМ (если есть)
        supabase.table("user_squads").delete().eq("id", existing.data[0]['id']).execute()
        return False, "removed"  # Возвращаем статус
    else:
        # ДОБАВЛЯЕМ (сначала проверяем лимит 5)
        current = supabase.table("user_squads").select("*", count="exact").eq("user_id", user_id).execute()
        if current.count >= 5:
            return False, "full"

        # Проверяем, владеет ли он этой картой вообще (на всякий случай)
        # (в данном коде пропустим для скорости, т.к. кнопка только под картой)

        supabase.table("user_squads").insert({"user_id": user_id, "card_id": card_id}).execute()
        return True, "added"


# --- ПОИСК БОЯ (MATCHMAKING) ---

def join_queue(user_id, chat_id=None):
    """Добавляет игрока в очередь. chat_id — где игрок нажал 'Найти противника'
    (ЛС или группа), чтобы потом прислать результат боя туда же, а не всегда в ЛС."""
    user = supabase.table("users").select("rating").eq("telegram_id", user_id).execute()
    rating = user.data[0]['rating'] if user.data else 1000

    data = {"user_id": user_id, "rating": rating}
    if chat_id is not None:
        data["chat_id"] = chat_id

    # Upsert (если уже там - обновит время)
    supabase.table("arena_queue").upsert(data).execute()


def leave_queue(user_id):
    """Удаляет из очереди (отмена)"""
    supabase.table("arena_queue").delete().eq("user_id", user_id).execute()


def find_opponent(user_id):
    """
    Ищет противника в очереди.
    Логика: рейтинг +/- 200, не сам юзер.
    """
    # 1. Получаем свой рейтинг
    me = supabase.table("users").select("rating").eq("telegram_id", user_id).execute()
    my_rating = me.data[0]['rating'] if me.data else 1000

    min_r = my_rating - 200
    max_r = my_rating + 200

    # 2. Ищем в базе
    # .neq("user_id", user_id) -> не я
    # .gte("rating", min_r) -> больше или равно мин
    # .lte("rating", max_r) -> меньше или равно макс
    # .order("joined_at") -> кто дольше ждет, того берем первым
    # .limit(1)

    res = supabase.table("arena_queue") \
        .select("*") \
        .neq("user_id", user_id) \
        .gte("rating", min_r) \
        .lte("rating", max_r) \
        .order("joined_at") \
        .limit(1) \
        .execute()

    if res.data:
        opponent = res.data[0]
        # Удаляем противника из очереди, чтобы его не забрал кто-то еще
        supabase.table("arena_queue").delete().eq("user_id", opponent['user_id']).execute()
        return opponent['user_id'], opponent.get('chat_id')

    return None, None


def update_battle_stats(winner_id, loser_id, w_dmg=0, l_dmg=0):
    # Победитель
    w = supabase.table("users").select("coins, rating, battles_won, battles_total, total_damage_dealt").eq("telegram_id",
                                                                                       winner_id).execute().data[0]
    w_dmg_prev = w.get('total_damage_dealt', 0) or 0
    supabase.table("users").update({
        "coins": w['coins'] + 10,  # Награда
        "rating": w['rating'] + 25,
        "battles_won": w['battles_won'] + 1,
        "battles_total": w['battles_total'] + 1,
        "total_damage_dealt": w_dmg_prev + w_dmg
    }).eq("telegram_id", winner_id).execute()

    # Проигравший
    l = supabase.table("users").select("rating, battles_total, total_damage_dealt").eq("telegram_id", loser_id).execute().data[0]
    new_rating = l['rating'] - 15
    if new_rating < 0: new_rating = 0
    l_dmg_prev = l.get('total_damage_dealt', 0) or 0

    supabase.table("users").update({
        "rating": new_rating,
        "battles_total": l['battles_total'] + 1,
        "total_damage_dealt": l_dmg_prev + l_dmg
    }).eq("telegram_id", loser_id).execute()



# --- GEMS (ВТОРАЯ ВАЛЮТА) ---

def get_user_gems(user_id):
    """Возвращает количество gems у пользователя"""
    res = supabase.table("users").select("gems").eq("telegram_id", user_id).execute()
    if res.data:
        return res.data[0].get('gems', 0) or 0
    return 0


def update_gems(user_id, amount):
    """Изменяет gems. amount может быть отрицательным"""
    user = get_user_data(user_id)
    if not user:
        return False
    new_balance = (user.get('gems') or 0) + amount
    if new_balance < 0:
        return False
    supabase.table("users").update({"gems": new_balance}).eq("telegram_id", user_id).execute()
    return True


# --- ПАКИ ---

def add_pack_to_user(user_id, pack_type, count=1):
    """Добавляет пак(и) пользователю"""
    existing = supabase.table("user_packs").select("*").eq("user_id", user_id).eq("pack_type", pack_type).execute()
    if existing.data:
        new_count = existing.data[0]['count'] + count
        supabase.table("user_packs").update({"count": new_count}).eq("id", existing.data[0]['id']).execute()
    else:
        supabase.table("user_packs").insert({"user_id": user_id, "pack_type": pack_type, "count": count}).execute()


def get_user_packs(user_id):
    """Возвращает все паки пользователя"""
    res = supabase.table("user_packs").select("*").eq("user_id", user_id).gt("count", 0).execute()
    return res.data or []


def use_pack(user_id, pack_type):
    """Тратит 1 пак из инвентаря. Возвращает True если успешно"""
    existing = supabase.table("user_packs").select("*").eq("user_id", user_id).eq("pack_type", pack_type).execute()
    if not existing.data or existing.data[0]['count'] < 1:
        return False
    new_count = existing.data[0]['count'] - 1
    supabase.table("user_packs").update({"count": new_count}).eq("id", existing.data[0]['id']).execute()
    return True


def increment_packs_opened(user_id):
    """Увеличивает счётчик открытых паков"""
    user = get_user_data(user_id)
    if not user:
        return
    new_val = (user.get('packs_opened') or 0) + 1
    supabase.table("users").update({"packs_opened": new_val}).eq("telegram_id", user_id).execute()


# --- ЗАДАНИЯ ---

def get_user_task_progress(user_id, period="daily"):
    """Получает прогресс заданий (daily/weekly)"""
    res = supabase.table("user_tasks").select("*").eq("user_id", user_id).eq("period", period).execute()
    
    now = datetime.now(timezone.utc)
    need_reset = False
    result = {}
    
    if res.data:
        for row in res.data:
            if row.get('updated_at'):
                updated_at = datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00'))
                if period == "daily" and updated_at.date() < now.date():
                    need_reset = True
                    break
                elif period == "weekly" and updated_at.isocalendar()[1] < now.isocalendar()[1]:
                    need_reset = True
                    break
            result[row['task_id']] = {"progress": row.get('progress', 0), "claimed": row.get('claimed', False)}
            
    if need_reset:
        supabase.table("user_tasks").delete().eq("user_id", user_id).eq("period", period).execute()
        return {}
        
    return result


def update_task_progress(user_id, task_id, period, increment=1):
    """Обновляет прогресс задания"""
    # Auto-reset old tasks before updating
    get_user_task_progress(user_id, period)
    
    existing = supabase.table("user_tasks").select("*").eq("user_id", user_id).eq("task_id", task_id).eq("period", period).execute()
    now_str = datetime.now(timezone.utc).isoformat()
    if existing.data:
        row = existing.data[0]
        if row.get('claimed'):
            return  # уже получена награда
        new_progress = row.get('progress', 0) + increment
        supabase.table("user_tasks").update({"progress": new_progress, "updated_at": now_str}).eq("id", row['id']).execute()
    else:
        supabase.table("user_tasks").insert({
            "user_id": user_id, "task_id": task_id, "period": period, "progress": increment, "claimed": False, "updated_at": now_str
        }).execute()


def claim_task_reward(user_id, task_id, period):
    """Помечает задание как полученное. Возвращает True если успешно"""
    res = supabase.table("user_tasks").select("*").eq("user_id", user_id).eq("task_id", task_id).eq("period", period).execute()
    if res.data and not res.data[0].get('claimed'):
        supabase.table("user_tasks").update({"claimed": True}).eq("id", res.data[0]['id']).execute()
        return True
    return False


def reset_daily_tasks(user_id):
    """Сбрасывает ежедневные задания"""
    supabase.table("user_tasks").delete().eq("user_id", user_id).eq("period", "daily").execute()


# --- ДОСТИЖЕНИЯ ---

def get_user_achievements(user_id):
    """Возвращает список полученных достижений"""
    res = supabase.table("user_achievements").select("achievement_id").eq("user_id", user_id).execute()
    return [row['achievement_id'] for row in (res.data or [])]


def award_achievement(user_id, achievement_id):
    """Выдаёт достижение. Возвращает True если выдано впервые"""
    existing = supabase.table("user_achievements").select("*").eq("user_id", user_id).eq("achievement_id", achievement_id).execute()
    if existing.data:
        return False
    supabase.table("user_achievements").insert({"user_id": user_id, "achievement_id": achievement_id}).execute()
    return True


# --- ОБМЕН (TRADE) ---

def create_trade_offer(from_user_id, to_user_id, offered_card_id, wanted_card_id=None):
    """Создаёт предложение обмена. Возвращает (trade_id, error_message) — ровно
    один из них не None. Ограничиваем число одновременных исходящих заявок
    одного игрока: без этого спамом (в т.ч. автокликером) можно закинуть сотни
    заявок на одну и ту же карту — см. фикс дублирования в _transfer_card."""
    from config import MAX_PENDING_TRADE_OFFERS
    pending = supabase.table("trade_offers").select("id", count="exact").eq(
        "from_user_id", from_user_id).eq("status", "pending").execute()
    if (pending.count or 0) >= MAX_PENDING_TRADE_OFFERS:
        return None, f"Слишком много активных предложений (максимум {MAX_PENDING_TRADE_OFFERS}). Дождитесь ответа или отклоните часть."

    data = {
        "from_user_id": from_user_id,
        "to_user_id": to_user_id,
        "offered_card_id": offered_card_id,
        "wanted_card_id": wanted_card_id,
        "status": "pending"
    }
    res = supabase.table("trade_offers").insert(data).execute()
    if res.data:
        return res.data[0]['id'], None
    return None, "Ошибка создания обмена"


def get_incoming_trades(user_id):
    """Входящие предложения обмена"""
    res = supabase.table("trade_offers").select("*, cards!offered_card_id(*), users!from_user_id(first_name)").eq("to_user_id", user_id).eq("status", "pending").execute()
    return res.data or []


def get_outgoing_trades(user_id):
    """Исходящие предложения обмена"""
    res = supabase.table("trade_offers").select("*, cards!offered_card_id(*), users!to_user_id(first_name)").eq("from_user_id", user_id).eq("status", "pending").execute()
    return res.data or []


def accept_trade(trade_id, user_id):
    """Принимает обмен — меняет карты между игроками"""
    # Атомарный клейм заявки (условие по status="pending" в самом UPDATE):
    # если её уже обработали параллельным запросом/повторным кликом,
    # rowcount будет 0 — не даём провести перевод карт дважды по одной заявке.
    claim = supabase.table("trade_offers").update({"status": "accepted"}).eq(
        "id", trade_id).eq("status", "pending").eq("to_user_id", user_id).execute()
    if not claim.count:
        return False, "Обмен не найден или уже обработан"

    trade = supabase.table("trade_offers").select("*").eq("id", trade_id).execute().data[0]
    from_id = trade['from_user_id']
    to_id = trade['to_user_id']
    off_card = trade['offered_card_id']
    want_card = trade.get('wanted_card_id')

    # Перемещаем предложенную карту: from -> to
    ok1 = _transfer_card(from_id, to_id, off_card)
    if not ok1:
        supabase.table("trade_offers").update({"status": "failed"}).eq("id", trade_id).execute()
        return False, "У отправителя больше нет этой карты — обмен невозможен"

    # Перемещаем запрошенную карту: to -> from (если указана)
    if want_card:
        ok2 = _transfer_card(to_id, from_id, want_card)
        if not ok2:
            # Откатываем уже переданную карту — обмен не должен завершиться наполовину
            _transfer_card(to_id, from_id, off_card)
            supabase.table("trade_offers").update({"status": "failed"}).eq("id", trade_id).execute()
            return False, "У вас больше нет запрошенной карты — обмен невозможен"

    update_task_progress(user_id, "trade_complete", "weekly")
    return True, "Обмен выполнен!"


def decline_trade(trade_id, user_id):
    """Отклоняет обмен"""
    supabase.table("trade_offers").update({"status": "declined"}).eq(
        "id", trade_id).eq("to_user_id", user_id).eq("status", "pending").execute()


def _transfer_card(from_user_id, to_user_id, card_id):
    """Перемещает 1 карту между пользователями. Возвращает True, только если
    карта реально была у отправителя и была атомарно списана.

    Раньше, если у отправителя карты уже не было (например, её забрала ранее
    принятая заявка), получатель всё равно получал карту — это позволяло
    бесконечно дублировать её, приняв несколько заявок на обмен одной и той же
    карты подряд (см. отчёт про дублирование через несколько сотен заявок).
    Условие в WHERE ниже — атомарный "клейм", защищающий от такого же дубля
    при параллельных/повторных запросах (двойной клик, автокликер)."""
    existing = supabase.table("user_cards").select("*").eq("user_id", from_user_id).eq("card_id", card_id).execute()
    if not existing.data or existing.data[0]['count'] < 1:
        return False
    row = existing.data[0]

    if row['count'] > 1:
        claim = supabase.table("user_cards").update({"count": row['count'] - 1}).eq(
            "id", row['id']).eq("count", row['count']).execute()
    else:
        claim = supabase.table("user_cards").delete().eq("id", row['id']).execute()

    if not claim.count:
        return False

    if row['count'] <= 1:
        # Отдали последнюю копию — освобождаем слот в отряде на арене, если она
        # там стояла. Иначе карты у игрока уже нет, а слот всё ещё "занят".
        _remove_from_squad(from_user_id, card_id)

    add_card_to_user(to_user_id, card_id)
    return True


def _remove_from_squad(user_id, card_id):
    """Убирает карту из боевого отряда, если она там есть. Вызывается, когда
    у игрока не осталось ни одной копии карты (отдал в обмене/продал на
    площадке) — иначе слот в отряде остаётся занят несуществующей у него картой."""
    supabase.table("user_squads").delete().eq("user_id", user_id).eq("card_id", card_id).execute()


# --- ТОРГОВАЯ ПЛОЩАДКА ---

def list_card_on_market(user_id, card_id, price):
    """Выставляет карту на продажу"""
    existing = supabase.table("user_cards").select("*").eq("user_id", user_id).eq("card_id", card_id).execute()
    if not existing.data or existing.data[0]['count'] < 1:
        return False, "У вас нет этой карты"
    row = existing.data[0]

    # Резервируем карту АТОМАРНО (клейм по count, который только что прочитали)
    # ДО создания листинга — иначе двойной клик/автокликер мог бы выставить
    # на продажу больше копий карты, чем реально есть.
    if row['count'] > 1:
        claim = supabase.table("user_cards").update({"count": row['count'] - 1}).eq(
            "id", row['id']).eq("count", row['count']).execute()
    else:
        claim = supabase.table("user_cards").delete().eq("id", row['id']).execute()
    if not claim.count:
        return False, "У вас нет этой карты"

    if row['count'] <= 1:
        # Выставили последнюю копию — освобождаем слот в отряде, если она там стояла
        _remove_from_squad(user_id, card_id)

    data = {"seller_id": user_id, "card_id": card_id, "price": price, "status": "active"}
    res = supabase.table("market_listings").insert(data).execute()
    if res.data:
        return True, res.data[0]['id']

    # Листинг не создался — возвращаем зарезервированную карту обратно
    add_card_to_user(user_id, card_id)
    return False, "Ошибка создания листинга"


def get_market_listings(rarity_filter=None, sort_by="price", limit=20):
    """Получает активные листинги"""
    query = supabase.table("market_listings").select("*, cards(*), users!seller_id(first_name)").eq("status", "active")
    if sort_by == "price":
        query = query.order("price")
    res = query.limit(limit).execute()
    listings = res.data or []
    if rarity_filter:
        listings = [l for l in listings if l.get('cards', {}).get('rarity') == rarity_filter]
    return listings


def buy_from_market(buyer_id, listing_id):
    """Покупает карту с торговой площадки"""
    from config import MARKET_FEE_PERCENT
    listing_res = supabase.table("market_listings").select("*").eq("id", listing_id).eq("status", "active").execute()
    if not listing_res.data:
        return False, "Листинг не найден"
    listing = listing_res.data[0]
    if listing['seller_id'] == buyer_id:
        return False, "Нельзя покупать у себя"

    price = listing['price']
    buyer = get_user_data(buyer_id)
    if not buyer or buyer['coins'] < price:
        return False, "Недостаточно монет"

    # Атомарный клейм листинга ДО начисления денег/карты: если его уже купили
    # или сняли между select выше и этим update (двойной клик, два покупателя
    # одновременно) — rowcount будет 0, и мы не продублируем карту/деньги.
    claim = supabase.table("market_listings").update({"status": "sold"}).eq(
        "id", listing_id).eq("status", "active").execute()
    if not claim.count:
        return False, "Этот листинг уже куплен или снят с продажи"

    fee = max(1, price * MARKET_FEE_PERCENT // 100)
    seller_gets = price - fee

    # Списываем у покупателя
    supabase.table("users").update({"coins": buyer['coins'] - price}).eq("telegram_id", buyer_id).execute()
    update_task_progress(buyer_id, "spend_coins", "weekly", increment=price)
    # Начисляем продавцу
    seller = get_user_data(listing['seller_id'])
    if seller:
        supabase.table("users").update({"coins": seller['coins'] + seller_gets}).eq("telegram_id", listing['seller_id']).execute()

    # Выдаём карту покупателю
    add_card_to_user(buyer_id, listing['card_id'])
    return True, "Покупка успешна!"


def cancel_market_listing(user_id, listing_id):
    """Отменяет листинг и возвращает карту продавцу"""
    listing_res = supabase.table("market_listings").select("*").eq("id", listing_id).eq("seller_id", user_id).eq("status", "active").execute()
    if not listing_res.data:
        return False, "Листинг не найден"
    listing = listing_res.data[0]

    # Атомарный клейм — та же защита, что и в buy_from_market
    claim = supabase.table("market_listings").update({"status": "cancelled"}).eq(
        "id", listing_id).eq("status", "active").execute()
    if not claim.count:
        return False, "Этот листинг уже куплен или снят с продажи"

    add_card_to_user(user_id, listing['card_id'])
    return True, "Карта возвращена"


def get_my_market_listings(user_id):
    """Получает активные листинги пользователя"""
    res = supabase.table("market_listings").select("*").eq("seller_id", user_id).eq("status", "active").execute()
    listings = res.data or []
    if not listings:
        return []
    cards_by_id = {c['id']: c for c in (get_all_cards() or [])}
    for listing in listings:
        listing['cards'] = cards_by_id.get(listing['card_id'], {})
    return listings


# --- СОБЫТИЯ ---

def get_active_events():
    """Возвращает активные события"""
    now = datetime.now(timezone.utc).isoformat()
    res = supabase.table("events").select("*").lte("start_at", now).gte("end_at", now).execute()
    return res.data or []


# --- СТАТИСТИКА ДЛЯ ДОСТИЖЕНИЙ ---

def get_user_stats_for_achievements(user_id):
    """Возвращает статы пользователя для проверки достижений"""
    user = get_user_data(user_id)
    if not user:
        return {}

    # Считаем уникальные карты и по редкостям — джойн делаем вручную в Python
    # (мок supabase поверх sqlite не поддерживает произвольные embedded-select
    # вида cards(rarity), только несколько захардкоженных cards(*) веток)
    cards_res = supabase.table("user_cards").select("card_id", count="exact").eq("user_id", user_id).execute()
    unique_cards = cards_res.count or 0
    rarity_by_id = {c['id']: c.get('rarity') for c in (get_all_cards() or [])}

    legendary_count = 0
    mythic_count = 0
    divine_count = 0
    secret_count = 0
    for item in (cards_res.data or []):
        rarity = rarity_by_id.get(item['card_id'], '')
        if rarity == 'Legendary': legendary_count += 1
        elif rarity == 'Mythic': mythic_count += 1
        elif rarity == 'Divine': divine_count += 1
        elif rarity == 'Secret': secret_count += 1

    return {
        "packs_opened": user.get('packs_opened', 0) or 0,
        "battles_won": user.get('battles_won', 0) or 0,
        "unique_cards": unique_cards,
        "legendary_count": legendary_count,
        "mythic_count": mythic_count,
        "divine_count": divine_count,
        "secret_count": secret_count,
        "total_cards_obtained": user.get('total_cards_obtained', 0) or 0,
        "total_legendary_obtained": user.get('total_legendary_obtained', 0) or 0,
        "total_mythic_obtained": user.get('total_mythic_obtained', 0) or 0,
        "total_epic_obtained": user.get('total_epic_obtained', 0) or 0,
    }


def get_user_rank(user_id):
    """Возвращает место пользователя в рейтинге по монетам"""
    user = get_user_data(user_id)
    if not user:
        return 0
    res = supabase.table("users").select("telegram_id", count="exact").gt("coins", user['coins']).execute()
    return (res.count or 0) + 1


# --- УЛУЧШЕНИЕ КАРТ (FUSION) ---

def fuse_cards(user_id, card_id, count_required=3):
    """Объединяет N копий карты для повышения уровня"""
    existing = supabase.table("user_cards").select("*").eq("user_id", user_id).eq("card_id", card_id).execute()
    if not existing.data or existing.data[0]['count'] < count_required:
        return False, f"Нужно минимум {count_required} копии"
    row = existing.data[0]
    new_count = row['count'] - count_required
    current_level = row.get('card_level', 1) or 1
    new_level = current_level + 1

    # Атомарный клейм по count, который только что прочитали — иначе двойной
    # клик/автокликер мог бы улучшить карту дважды за одни и те же копии
    # (списались бы одни и те же 3 копии, но уровень вырос бы на 2).
    claim = supabase.table("user_cards").update({"count": new_count, "card_level": new_level}).eq(
        "id", row['id']).eq("count", row['count']).execute()
    if not claim.count:
        return False, "Не удалось улучшить — попробуйте ещё раз"
    return True, new_level


# --- КЛАН: ВЫХОД И ВСТУПЛЕНИЕ ---

def leave_clan(user_id):
    """Выходит из клана"""
    user = get_user_data(user_id)
    if not user or not user.get('clan_id'):
        return False, "Вы не в клане"
    clan_id = user['clan_id']
    clan = get_clan_info(clan_id)
    if clan and clan['owner_id'] == user_id:
        return False, "Лидер не может выйти из клана"
    supabase.table("clan_members").delete().eq("clan_id", clan_id).eq("user_id", user_id).execute()
    supabase.table("users").update({"clan_id": None}).eq("telegram_id", user_id).execute()
    return True, "Вы покинули клан"


def join_clan(user_id, clan_id):
    """Вступает в клан"""
    user = get_user_data(user_id)
    if not user:
        return False, "Ошибка"
    if user.get('clan_id'):
        return False, "Сначала покиньте текущий клан"
    clan = get_clan_info(clan_id)
    if not clan:
        return False, "Клан не найден"
    supabase.table("clan_members").insert({"clan_id": clan_id, "user_id": user_id, "role": "member"}).execute()
    supabase.table("users").update({"clan_id": clan_id}).eq("telegram_id", user_id).execute()
    return True, f"Вы вступили в клан {clan['name']}!"


def search_clans(query):
    """Ищет кланы по названию"""
    res = supabase.table("clans").select("id, name, owner_id").ilike("name", f"%{query}%").limit(10).execute()
    return res.data or []


def delete_clan(clan_id, owner_id):
    """Удаляет клан (только для лидера)"""
    clan = get_clan_info(clan_id)
    if not clan or clan['owner_id'] != owner_id:
        return False, "Нет прав на удаление клана"
    
    supabase.table("users").update({"clan_id": None}).eq("clan_id", clan_id).execute()
    supabase.table("clans").delete().eq("id", clan_id).execute()
    return True, "Клан успешно удален"


def get_all_users_count():
    """Общее количество пользователей"""
    res = supabase.table("users").select("telegram_id", count="exact").execute()
    return res.count or 0


# --- АДМИНЫ ---

def get_admin_ids():
    """ID всех админов: таблица admins + бутстрап-админ из .env (чтобы нельзя было
    случайно потерять доступ ко всей панели, полностью очистив таблицу)"""
    from config import ADMIN_ID
    res = supabase.table("admins").select("telegram_id").execute()
    ids = {row['telegram_id'] for row in (res.data or [])}
    ids.add(ADMIN_ID)
    return ids


def is_admin(user_id):
    """Проверяет права администратора (любая роль)"""
    return user_id in get_admin_ids()


def get_admin_role(user_id):
    """Возвращает роль: 'head' (Гл. Администратор), 'admin' или None, если не админ.
    Бутстрап-админ из .env всегда 'head' — даже если его вдруг убрали из таблицы,
    чтобы нельзя было потерять доступ к управлению админами вообще."""
    from config import ADMIN_ID
    if user_id == ADMIN_ID:
        return 'head'
    res = supabase.table("admins").select("role").eq("telegram_id", user_id).execute()
    if res.data:
        return res.data[0].get('role') or 'admin'
    return None


def is_head_admin(user_id):
    """Гл. Администратор — единственный, кто может назначать/снимать админов"""
    return get_admin_role(user_id) == 'head'


def get_admins_list():
    """Список админов из таблицы (без учёта бутстрап-админа из .env)"""
    res = supabase.table("admins").select("*").order("added_at").execute()
    return res.data or []


def add_admin(user_id, role='admin', added_by=None):
    """Назначает админа с ролью 'head' или 'admin'. Возвращает False, если он уже админ"""
    existing = supabase.table("admins").select("*").eq("telegram_id", user_id).execute()
    if existing.data:
        return False
    supabase.table("admins").insert({"telegram_id": user_id, "role": role, "added_by": added_by}).execute()
    return True


def remove_admin(user_id):
    """Снимает права админа. Гл. Администратора снять нельзя (в том числе другим
    Гл. Администратором) — только обычного 'admin'."""
    role = get_admin_role(user_id)
    if role is None:
        return False, "Этот пользователь не админ"
    if role == 'head':
        return False, "Нельзя снять Гл. Администратора"
    supabase.table("admins").delete().eq("telegram_id", user_id).execute()
    return True, "Права админа сняты"


# --- ОБЯЗАТЕЛЬНАЯ ПОДПИСКА НА КАНАЛЫ ---

def get_required_channels():
    """Все настроенные каналы/чаты (обязательные и необязательные)"""
    res = supabase.table("required_channels").select("*").order("id").execute()
    return res.data or []


def add_required_channel(title, url, chat_id, is_mandatory=True):
    supabase.table("required_channels").insert({
        "title": title, "url": url, "chat_id": chat_id, "is_mandatory": is_mandatory
    }).execute()


def delete_required_channel(channel_id):
    supabase.table("required_channels").delete().eq("id", channel_id).execute()


def toggle_channel_mandatory(channel_id, is_mandatory):
    supabase.table("required_channels").update({"is_mandatory": is_mandatory}).eq("id", channel_id).execute()


# --- АДМИНКА: КАРТЫ (CRUD) ---

def update_card(card_id, data):
    """Изменяет карту (частичный набор полей)"""
    supabase.table("cards").update(data).eq("id", card_id).execute()


def delete_card(card_id):
    """Удаляет карту из базы (у игроков удалится каскадно по FK)"""
    supabase.table("cards").delete().eq("id", card_id).execute()


def get_cards_paginated(page=0, page_size=10):
    """Список карт с пагинацией для админки"""
    start = page * page_size
    end = start + page_size - 1

    count_res = supabase.table("cards").select("id", count="exact").execute()
    total = count_res.count or 0

    res = supabase.table("cards").select("*").order("id").range(start, end).execute()
    return res.data or [], total


def count_card_owners(card_id):
    """Сколько игроков держат эту карту (для подтверждения удаления)"""
    res = supabase.table("user_cards").select("user_id", count="exact").eq("card_id", card_id).execute()
    return res.count or 0


# --- АДМИНКА: СОБЫТИЯ ---

def create_event(name, description, days):
    """Создаёт событие на N дней от текущего момента"""
    now = datetime.now(timezone.utc)
    end_at = now + timedelta(days=days)
    data = {
        "name": name, "description": description,
        "start_at": now.isoformat(), "end_at": end_at.isoformat(),
        "pack_type": "event",
    }
    res = supabase.table("events").insert(data).execute()
    return res.data[0]['id'] if res.data else None


def end_event(event_id):
    """Досрочно завершает событие"""
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("events").update({"end_at": now}).eq("id", event_id).execute()


def get_events_admin(limit=10):
    """Последние события (для админки — активные и уже завершённые)"""
    res = supabase.table("events").select("*").order("id", desc=True).limit(limit).execute()
    return res.data or []


# --- АДМИНКА: ИГРОКИ И БАН ---

def search_users(query):
    """Ищет игроков по @username или Telegram ID"""
    q = query.strip().lstrip('@')
    res = supabase.table("users").select("*").ilike("username", f"%{q}%").limit(10).execute()
    if not res.data:
        try:
            uid = int(q)
            res = supabase.table("users").select("*").eq("telegram_id", uid).execute()
        except ValueError:
            pass
    return res.data or []


def set_user_banned(user_id, banned):
    """Банит/разбанивает игрока"""
    supabase.table("users").update({"banned": banned}).eq("telegram_id", user_id).execute()


def is_user_banned(user_id):
    """Проверяет, забанен ли игрок"""
    user = get_user_data(user_id)
    return bool(user and user.get('banned'))


# --- PREMIUM ---

def grant_premium(user_id, days):
    """Выдаёт/продлевает Premium. Если он уже активен — продлевает от текущей даты окончания."""
    user = get_user_data(user_id)
    if not user:
        return False
    now = datetime.now(timezone.utc)
    current = user.get('premium_until')
    base = now
    if current:
        current_dt = datetime.fromisoformat(current.replace('Z', '+00:00'))
        if current_dt > now:
            base = current_dt
    new_until = base + timedelta(days=days)
    supabase.table("users").update({"premium_until": new_until.isoformat()}).eq("telegram_id", user_id).execute()
    return True


def get_premium_auto_renew_candidates():
    """Получает пользователей, у которых истёк премиум, но включено автопродление"""
    now = datetime.now(timezone.utc).isoformat()
    res = supabase.table("users").select("telegram_id, gems").eq("premium_auto_renew", True).lte("premium_until", now).execute()
    return res.data or []


def disable_premium_auto_renew(user_id):
    """Отключает автопродление (например, при нехватке Gems)"""
    supabase.table("users").update({"premium_auto_renew": False}).eq("telegram_id", user_id).execute()


# --- ФАРМ МОНЕТ ---

def check_farm_available(user_id):
    """Проверяет, доступен ли фарм монет (кулдаун 4 часа). Возвращает (available: bool, seconds_left: int)"""
    from config import FARM_COOLDOWN_HOURS
    user = get_user_data(user_id)
    if not user:
        return False, 0
    last_farm = user.get('last_farm_at')
    if not last_farm:
        return True, 0
    now = datetime.now(timezone.utc)
    last = datetime.fromisoformat(last_farm.replace('Z', '+00:00'))
    diff = now - last
    cooldown = timedelta(hours=FARM_COOLDOWN_HOURS)
    if diff >= cooldown:
        return True, 0
    seconds_left = int((cooldown - diff).total_seconds())
    return False, seconds_left


def do_farm_coins(user_id):
    """Выполняет фарм монет — начисляет рандомно 1–100 монет. Возвращает (amount: int)"""
    import random
    from config import FARM_MAX_COINS
    amount = random.randint(1, FARM_MAX_COINS)
    now = datetime.now(timezone.utc).isoformat()
    user = get_user_data(user_id)
    if not user:
        return 0
    supabase.table("users").update({
        "coins": user['coins'] + amount,
        "last_farm_at": now
    }).eq("telegram_id", user_id).execute()
    return amount


# --- РЕЙТИНГ АРЕНЫ ПО УРОНУ ---

def get_top_by_damage(limit=10):
    """Топ игроков по суммарному нанесённому урону"""
    res = supabase.table("users").select("first_name, total_damage_dealt").order(
        "total_damage_dealt", desc=True).limit(limit).execute()
    return [{"first_name": u['first_name'], "value": u.get('total_damage_dealt') or 0} for u in (res.data or [])]


# --- БРАКИ ---

def get_user_marriage(user_id):
    """Возвращает активный брак пользователя или None"""
    res = supabase.table("marriages").select("*, u1:users!marriages_user1_id_fkey(first_name, username), u2:users!marriages_user2_id_fkey(first_name, username)").eq("status", "active").or_(
        f"user1_id.eq.{user_id},user2_id.eq.{user_id}"
    ).execute()
    return res.data[0] if res.data else None


def get_pending_marriage_request(user_id):
    """Возвращает входящую заявку на брак (status=pending, user2_id=user_id)"""
    res = supabase.table("marriages").select("*, users!marriages_user1_id_fkey(first_name, username)").eq(
        "user2_id", user_id).eq("status", "pending").execute()
    return res.data[0] if res.data else None


def get_sent_marriage_request(user_id):
    """Возвращает исходящую заявку (status=pending, user1_id=user_id)"""
    res = supabase.table("marriages").select("*").eq("user1_id", user_id).eq("status", "pending").execute()
    return res.data[0] if res.data else None


def propose_marriage(from_user_id, to_user_id):
    """Отправляет заявку на брак. Возвращает (success, message)"""
    # Проверяем, уже в браке
    if get_user_marriage(from_user_id):
        return False, "Вы уже в браке!"
    if get_user_marriage(to_user_id):
        return False, "Этот игрок уже в браке!"
    # Уже отправляли заявку?
    if get_sent_marriage_request(from_user_id):
        return False, "Вы уже отправили заявку на брак!"
    # Нельзя самому себе
    if from_user_id == to_user_id:
        return False, "Нельзя предложить брак самому себе!"
    try:
        supabase.table("marriages").insert({
            "user1_id": from_user_id,
            "user2_id": to_user_id,
            "status": "pending"
        }).execute()
        return True, "ok"
    except Exception as e:
        return False, f"Ошибка: {e}"


def accept_marriage(marriage_id, user_id):
    """Принимает заявку на брак"""
    res = supabase.table("marriages").select("*").eq("id", marriage_id).eq("user2_id", user_id).eq("status", "pending").execute()
    if not res.data:
        return False, "Заявка не найдена"
    supabase.table("marriages").update({"status": "active"}).eq("id", marriage_id).execute()
    return True, "ok"


def reject_marriage(marriage_id, user_id):
    """Отклоняет заявку на брак"""
    supabase.table("marriages").update({"status": "rejected"}).eq("id", marriage_id).eq(
        "user2_id", user_id).eq("status", "pending").execute()
    return True, "ok"


def divorce(user_id):
    """Разводит пользователя (устанавливает статус 'divorced')"""
    supabase.table("marriages").update({"status": "divorced"}).eq("status", "active").or_(
        f"user1_id.eq.{user_id},user2_id.eq.{user_id}"
    ).execute()
    return True


def find_user_by_username(username):
    """Ищет пользователя по username (без @)"""
    q = username.lstrip('@').strip()
    res = supabase.table("users").select("telegram_id, first_name, username").ilike("username", q).limit(1).execute()
    return res.data[0] if res.data else None


# --- ВСЕ КЛАНЫ ---

def get_all_clans_list(page=0, page_size=8):
    """Список всех кланов с количеством участников для отображения"""
    start = page * page_size
    end = start + page_size - 1

    count_res = supabase.table("clans").select("id", count="exact").execute()
    total = count_res.count or 0

    res = supabase.table("clans").select("id, name, owner_id").order("id").range(start, end).execute()
    clans = res.data or []

    # Подсчёт участников для каждого клана
    result = []
    for clan in clans:
        mem_res = supabase.table("clan_members").select("user_id", count="exact").eq("clan_id", clan['id']).execute()
        clan['members_count'] = mem_res.count or 0
        result.append(clan)
    return result, total


# --- КЛАНОВЫЕ ВОЙНЫ ---

def get_clan_war_status(clan_id):
    """Проверяет, доступна ли война для клана (общий кулдаун — и как атакующий,
    и как цель, чтобы клан нельзя было закликать войнами без передышки).
    Возвращает (available: bool, seconds_left: int)"""
    from config import CLAN_WAR_COOLDOWN_HOURS
    clan = get_clan_info(clan_id)
    if not clan:
        return False, 0
    last_war = clan.get('last_war_at')
    if not last_war:
        return True, 0
    now = datetime.now(timezone.utc)
    last = datetime.fromisoformat(last_war.replace('Z', '+00:00'))
    diff = now - last
    cooldown = timedelta(hours=CLAN_WAR_COOLDOWN_HOURS)
    if diff >= cooldown:
        return True, 0
    return False, int((cooldown - diff).total_seconds())


def get_clans_for_war(exclude_clan_id, page=0, page_size=8):
    """Список кланов-целей для объявления войны (кроме своего)"""
    start = page * page_size
    end = start + page_size - 1

    count_res = supabase.table("clans").select("id", count="exact").neq("id", exclude_clan_id).execute()
    total = count_res.count or 0

    res = supabase.table("clans").select("id, name, owner_id, coins, war_wins").neq(
        "id", exclude_clan_id).order("id").range(start, end).execute()
    clans = res.data or []
    for clan in clans:
        mem_res = supabase.table("clan_members").select("user_id", count="exact").eq("clan_id", clan['id']).execute()
        clan['members_count'] = mem_res.count or 0
    return clans, total


def start_clan_war(challenger_clan_id, target_clan_id):
    """Проверяет условия и списывает ставку с обоих лидеров лично (не из казны —
    иначе только что созданный клан с пустой казной не смог бы воевать вообще).
    Возвращает (success, message, challenger_id, target_id, challenger_clan, target_clan)"""
    from config import CLAN_WAR_STAKE

    if challenger_clan_id == target_clan_id:
        return False, "Нельзя воевать со своим кланом", None, None, None, None

    challenger_clan = get_clan_info(challenger_clan_id)
    target_clan = get_clan_info(target_clan_id)
    if not challenger_clan or not target_clan:
        return False, "Клан не найден", None, None, None, None

    can_attack, _ = get_clan_war_status(challenger_clan_id)
    if not can_attack:
        return False, "Ваш клан ещё не отдохнул после последней войны", None, None, None, None

    can_defend, _ = get_clan_war_status(target_clan_id)
    if not can_defend:
        return False, "Этот клан недавно уже воевал — сейчас его нельзя атаковать", None, None, None, None

    challenger_id = challenger_clan['owner_id']
    target_id = target_clan['owner_id']

    if not update_coins(challenger_id, -CLAN_WAR_STAKE):
        return False, f"Недостаточно личных монет на ставку ({CLAN_WAR_STAKE} 💰)", None, None, None, None
    if not update_coins(target_id, -CLAN_WAR_STAKE):
        update_coins(challenger_id, CLAN_WAR_STAKE)  # возвращаем ставку — война не состоялась
        return False, "У лидера клана-цели недостаточно личных монет на ставку", None, None, None, None

    return True, "ok", challenger_id, target_id, challenger_clan, target_clan


def apply_clan_war_result(winner_clan_id, loser_clan_id):
    """Зачисляет в казну победителя обе ставки + системный бонус, ставит
    кулдаун обоим кланам и увеличивает счётчик побед в войнах"""
    from config import CLAN_WAR_STAKE, CLAN_WAR_BONUS
    now = datetime.now(timezone.utc).isoformat()

    winner = get_clan_info(winner_clan_id)
    if winner:
        supabase.table("clans").update({
            "coins": (winner.get('coins') or 0) + CLAN_WAR_STAKE * 2 + CLAN_WAR_BONUS,
            "war_wins": (winner.get('war_wins') or 0) + 1,
            "last_war_at": now,
        }).eq("id", winner_clan_id).execute()

    supabase.table("clans").update({"last_war_at": now}).eq("id", loser_clan_id).execute()


def get_top_clans_by_treasury(limit=10):
    """Топ кланов по казне"""
    res = supabase.table("clans").select("name, coins").order("coins", desc=True).limit(limit).execute()
    return res.data or []


def get_top_clans_by_war_wins(limit=10):
    """Топ кланов по победам в клановых войнах"""
    res = supabase.table("clans").select("name, war_wins").order("war_wins", desc=True).limit(limit).execute()
    return res.data or []


# --- ЗАЯВКИ В КЛАНЫ ---

def request_join_clan(user_id, clan_id):
    """Создаёт заявку на вступление в клан. Возвращает (success, message)"""
    user = get_user_data(user_id)
    if not user:
        return False, "Ошибка"
    if user.get('clan_id'):
        return False, "Вы уже в клане"
    # Проверить уже существующую заявку
    existing = supabase.table("clan_join_requests").select("*").eq("clan_id", clan_id).eq("user_id", user_id).eq("status", "pending").execute()
    if existing.data:
        return False, "Вы уже отправили заявку в этот клан"
    try:
        supabase.table("clan_join_requests").insert({
            "clan_id": clan_id, "user_id": user_id, "status": "pending"
        }).execute()
        return True, "ok"
    except Exception as e:
        return False, f"Ошибка: {e}"


def get_pending_clan_requests(clan_id):
    """Получает список ожидающих заявок для лидера"""
    # Джойн с users делаем вручную: мок supabase поверх sqlite ломается на
    # embedded-select с запятой внутри скобок вроде users(first_name, username) —
    # наивный split(",") режет прямо по этой внутренней запятой и превращает
    # запрос в синтаксически неверный SQL (крашится при просмотре заявок).
    res = supabase.table("clan_join_requests").select("id, user_id").eq(
        "clan_id", clan_id).eq("status", "pending").execute()
    requests = res.data or []
    for req in requests:
        u = get_user_data(req['user_id'])
        req['users'] = {"first_name": u['first_name'], "username": u.get('username')} if u else {}
    return requests


def accept_clan_request(request_id, leader_id):
    """Лидер принимает заявку"""
    req_res = supabase.table("clan_join_requests").select("*").eq("id", request_id).eq("status", "pending").execute()
    if not req_res.data:
        return False, "Заявка не найдена"
    req = req_res.data[0]

    # Проверяем, что leader_id — лидер этого клана
    clan = get_clan_info(req['clan_id'])
    if not clan or clan['owner_id'] != leader_id:
        return False, "Нет прав"

    # Вступаем
    success, msg = join_clan(req['user_id'], req['clan_id'])
    if success:
        supabase.table("clan_join_requests").update({"status": "accepted"}).eq("id", request_id).execute()
    return success, msg


def reject_clan_request(request_id, leader_id):
    """Лидер отклоняет заявку"""
    req_res = supabase.table("clan_join_requests").select("*").eq("id", request_id).eq("status", "pending").execute()
    if not req_res.data:
        return False, "Заявка не найдена"
    req = req_res.data[0]
    clan = get_clan_info(req['clan_id'])
    if not clan or clan['owner_id'] != leader_id:
        return False, "Нет прав"
    supabase.table("clan_join_requests").update({"status": "rejected"}).eq("id", request_id).execute()
    return True, "Заявка отклонена"

