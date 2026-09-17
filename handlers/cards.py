import random
from datetime import datetime, timedelta, timezone
from telebot import types
from loader import bot
from config import RARITY_CONFIG, RARITY_ORDER, FUSE_REQUIRED_COPIES, FUSE_LEVEL_BONUS_PERCENT, \
    DROP_COOLDOWN, DROP_COOLDOWN_PREMIUM
from database import get_all_cards, get_user_data, add_card_to_user, update_last_drop, get_user_inventory, \
    get_user_squad, toggle_squad_member, fuse_cards, is_premium, is_user_banned, update_task_progress, \
    on_card_obtained, consume_free_draw


def drop_random_card_logic():
    cards = get_all_cards()
    if not cards: return None
    population = []
    weights = []
    for card in cards:
        w = RARITY_CONFIG.get(card['rarity'], {}).get('chance', 1)
        population.append(card)
        weights.append(w)
    return random.choices(population, weights=weights, k=1)[0]


@bot.message_handler(func=lambda m: m.text == "🎴 Получить карту")
def handler_get_card(message):
    if is_user_banned(message.from_user.id):
        bot.send_message(message.chat.id, "⛔️ Вы заблокированы в этом боте.")
        return

    user = get_user_data(message.from_user.id)
    now = datetime.now(timezone.utc)

    # 5 стартовых бесплатных получений — отдельный одноразовый пул на аккаунт
    # (выдаётся один раз при первой регистрации, см. get_or_create_user), не
    # связан с обычным таймером и не сбрасывает/тратит его
    used_free_draw = (user.get('free_draws_remaining') or 0) > 0 and consume_free_draw(message.from_user.id)

    if not used_free_draw:
        cooldown_hours = DROP_COOLDOWN_PREMIUM if is_premium(user) else DROP_COOLDOWN

        # Проверка таймера
        if user['last_timed_drop']:
            last_drop = datetime.fromisoformat(user['last_timed_drop'])
            if last_drop.tzinfo is None:
                last_drop = last_drop.replace(tzinfo=timezone.utc)
            if now - last_drop < timedelta(hours=cooldown_hours):
                diff = timedelta(hours=cooldown_hours) - (now - last_drop)
                total_seconds = int(diff.total_seconds())
                hours, rem = divmod(total_seconds, 3600)
                minutes, _ = divmod(rem, 60)
                bot.send_message(message.chat.id, f"⏳ Жди еще: {hours}ч {minutes}мин")
                return

    card = drop_random_card_logic()
    if not card:
        bot.send_message(message.chat.id, "Карты кончились или не добавлены.")
        return

    is_dup, count = add_card_to_user(message.from_user.id, card['id'])
    if not used_free_draw:
        update_last_drop(message.from_user.id, now.isoformat())
    on_card_obtained(message.from_user.id, card, is_dup)
    update_task_progress(message.from_user.id, "get_card", "daily")

    emoji = RARITY_CONFIG.get(card['rarity'], {}).get('emoji', '')
    # Формируем упоминание игрока
    user_mention = f"@{message.from_user.username}" if message.from_user.username else f"<b>{message.from_user.first_name}</b>"
    caption = (f"👤 {user_mention} получил карту:\n"
               f"{emoji} <b>{card['name']}</b>\n"
               f"⭐️ {card['rarity']}\n"
               f"⚔️ {card['attack']} | ❤️ {card['hp']}")
    if is_dup: caption += f"\n♻️ Дубликат (x{count})"
    if used_free_draw:
        remaining = (user.get('free_draws_remaining') or 0) - 1
        caption += f"\n🎁 Бесплатное получение (осталось: {remaining})"

    if card['image_file_id']:
        bot.send_photo(message.chat.id, card['image_file_id'], caption=caption, parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, caption, parse_mode="HTML")


@bot.message_handler(func=lambda m: m.text == "🗂 Мои карты")
def inventory_menu(message, user_id=None):
    # user_id передаётся явно, когда сюда заходят из другого раздела через callback
    # (например, "Мой отряд" на арене) — там message это сообщение БОТА, и
    # message.from_user внутри него указывает на самого бота, а не на игрока
    user_id = user_id or message.from_user.id

    if is_user_banned(user_id):
        bot.send_message(message.chat.id, "⛔️ Вы заблокированы в этом боте.")
        return

    # Запрос в БД
    res = get_user_inventory(user_id)
    inv_data = res.data if res.data else []

    counts = {r: 0 for r in RARITY_CONFIG}

    for item in inv_data:
        if item.get('cards'):
            r = item['cards'].get('rarity')
            c = item.get('count', 1)

            if r in counts:
                counts[r] += 1  # Считаем +1 за каждую УНИКАЛЬНУЮ карту
                # Если хочешь считать дубликаты, пиши: counts[r] += c

    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = []
    for r in RARITY_ORDER:
        # Безопасное получение данных
        cfg = RARITY_CONFIG.get(r, {"emoji": "❓", "ru": r})
        cnt = counts.get(r, 0)

        text = f"{cfg['emoji']} {cfg['ru']} ({cnt})"
        btns.append(types.InlineKeyboardButton(text, callback_data=f"inv_open:{r}"))
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_game_menu"))

    bot.send_message(message.chat.id, "📂 <b>Коллекция карт:</b>\nВыбери редкость:", reply_markup=markup,
                     parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("inv_"))
def inventory_nav(call):
    parts = call.data.split(":")
    action = parts[0]

    if action == "inv_back_main":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        inventory_menu(call.message, user_id=call.from_user.id)
        return

    rarity = parts[1]
    inv_data = get_user_inventory(call.from_user.id).data
    # Фильтруем
    filtered = [i for i in inv_data if i['cards']['rarity'] == rarity]

    if not filtered:
        bot.answer_callback_query(call.id, "Пусто!", show_alert=True)
        return

    index = int(parts[2]) if len(parts) > 2 else 0
    if index >= len(filtered): index = 0
    if index < 0: index = len(filtered) - 1

    item = filtered[index]
    card = item['cards']
    level = item.get('card_level', 1) or 1
    bonus_mult = 1 + (FUSE_LEVEL_BONUS_PERCENT / 100) * (level - 1)
    eff_attack = int(card['attack'] * bonus_mult)
    eff_hp = int(card['hp'] * bonus_mult)
    stars = " " + "⭐" * (level - 1) if level > 1 else ""

    caption = (f"{RARITY_CONFIG[rarity]['emoji']} <b>{card['name']}</b>{stars}\n"
               f"⚔️ {eff_attack} | ❤️ {eff_hp}\n"
               f"🔺 Уровень: {level}\n"
               f"📦 В наличии: {item['count']}\n"
               f"📄 {index + 1} из {len(filtered)}")

    # ПРОВЕРЯЕМ, ЕСТЬ ЛИ КАРТА В ОТРЯДЕ
    squad = get_user_squad(call.from_user.id)
    is_in_squad = any(c['id'] == card['id'] for c in squad)
    squad_count = len(squad)

    markup = types.InlineKeyboardMarkup()

    # КНОПКА УПРАВЛЕНИЯ ОТРЯДОМ
    if is_in_squad:
        squad_btn = types.InlineKeyboardButton("❌ Убрать из отряда",
                                               callback_data=f"squad_toggle:{card['id']}:{rarity}:{index}")
    else:
        if squad_count < 5:
            squad_btn = types.InlineKeyboardButton("⚔️ Выбрать как воина",
                                                   callback_data=f"squad_toggle:{card['id']}:{rarity}:{index}")
        else:
            squad_btn = types.InlineKeyboardButton("⛔️ Отряд полон (5/5)", callback_data="ignore")

    markup.row(squad_btn)  # Добавляем кнопку отряда первой строкой

    # КНОПКА УЛУЧШЕНИЯ (слияние дублей)
    if item['count'] >= FUSE_REQUIRED_COPIES:
        fuse_btn = types.InlineKeyboardButton(f"🔀 Улучшить ({item['count']}/{FUSE_REQUIRED_COPIES})",
                                              callback_data=f"fuse_card:{card['id']}:{rarity}:{index}")
    else:
        fuse_btn = types.InlineKeyboardButton(f"🔀 Улучшить ({item['count']}/{FUSE_REQUIRED_COPIES})",
                                              callback_data="ignore")
    markup.row(fuse_btn)

    # Стандартные кнопки навигации
    markup.row(
        types.InlineKeyboardButton("⬅️", callback_data=f"inv_nav:{rarity}:{index - 1}"),
        types.InlineKeyboardButton(f"{index + 1}/{len(filtered)}", callback_data="ignore"),
        types.InlineKeyboardButton("➡️", callback_data=f"inv_nav:{rarity}:{index + 1}")
    )
    markup.row(types.InlineKeyboardButton("🔙 Назад", callback_data="inv_back_main"))

    media = types.InputMediaPhoto(card['image_file_id'], caption=caption, parse_mode="HTML")

    try:
        if action == "inv_nav":
            bot.edit_message_media(media=media, chat_id=call.message.chat.id, message_id=call.message.message_id,
                                   reply_markup=markup)
        else:
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_photo(call.message.chat.id, card['image_file_id'], caption=caption, reply_markup=markup,
                           parse_mode="HTML")
    except:
        bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("squad_toggle:"))
def handler_squad_toggle(call):
    # squad_toggle:CARD_ID:RARITY:INDEX
    parts = call.data.split(":")
    card_id = int(parts[1])
    rarity = parts[2]
    index = parts[3]

    success, status = toggle_squad_member(call.from_user.id, card_id)

    if status == "full":
        bot.answer_callback_query(call.id, "Отряд переполнен! Максимум 5 карт.", show_alert=True)
        return

    msg = "Карта добавлена в отряд!" if status == "added" else "Карта убрана из отряда!"
    bot.answer_callback_query(call.id, msg)

    call.data = f"inv_nav:{rarity}:{index}"
    inventory_nav(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("fuse_card:"))
def handler_fuse_card(call):
    # fuse_card:CARD_ID:RARITY:INDEX
    parts = call.data.split(":")
    card_id = int(parts[1])
    rarity = parts[2]
    index = parts[3]

    success, result = fuse_cards(call.from_user.id, card_id, FUSE_REQUIRED_COPIES)

    if success:
        update_task_progress(call.from_user.id, "fuse_card", "daily")
        bot.answer_callback_query(call.id, f"✨ Карта улучшена до уровня {result}!", show_alert=True)
    else:
        bot.answer_callback_query(call.id, result, show_alert=True)
        return

    call.data = f"inv_nav:{rarity}:{index}"
    inventory_nav(call)
