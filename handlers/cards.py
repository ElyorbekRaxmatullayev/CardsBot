import random
from datetime import datetime, timedelta, timezone
from telebot import types
from loader import bot
from config import RARITY_CONFIG, RARITY_ORDER, DROP_COOLDOWN, DROP_COOLDOWN_PREMIUM
from database import get_all_cards, get_user_data, add_card_to_user, update_last_drop, get_user_inventory, \
    get_user_squad, toggle_squad_member, fuse_cards, is_premium, is_user_banned, update_task_progress, \
    on_card_obtained, consume_free_draw, get_fuse_requirements, get_effective_stats
from utils import reply_match


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


@bot.message_handler(func=reply_match("🎴 Получить карту", "Получить карту"))
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
               f"{emoji} <b>{card['name']}</b>\n")
    if card.get('dunhua'):
        caption += f"Мир: {card['dunhua']}\n"
    caption += (f"⭐️ {card['rarity']}\n"
               f"⚔️ {card['attack']} | ❤️ {card['hp']}")
    if is_dup: caption += f"\n♻️ Дубликат (x{count})"
    if used_free_draw:
        remaining = (user.get('free_draws_remaining') or 0) - 1
        caption += f"\n🎁 Бесплатное получение (осталось: {remaining})"

    if card['image_file_id']:
        if card.get('media_type') == 'video':
            bot.send_video(message.chat.id, card['image_file_id'], caption=caption, parse_mode="HTML")
        else:
            bot.send_photo(message.chat.id, card['image_file_id'], caption=caption, parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, caption, parse_mode="HTML")


@bot.message_handler(func=reply_match("🗂 Мои карты", "Мои карты"))
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

    # Сначала показываем уже выбранный отряд арены, и только ниже — полный
    # каталог по редкостям. Раньше тут сразу открывалась вся коллекция, и
    # чтобы понять, кто уже в отряде, нужно было листать карты по одной.
    squad = get_user_squad(user_id)
    if squad:
        squad_lines = []
        for c in squad:
            emoji = RARITY_CONFIG.get(c.get('rarity', ''), {}).get('emoji', '🃏')
            level = c.get('card_level', 1) or 1
            lvl_txt = f" (ур. {level})" if level > 1 else ""
            squad_lines.append(f"{emoji} {c['name']}{lvl_txt}")
        squad_txt = "\n".join(squad_lines)
    else:
        squad_txt = "Пусто — выбери воинов ниже в коллекции."

    txt = (f"🛡 <b>Твой отряд арены</b> ({len(squad)}/5)\n{squad_txt}\n\n"
           f"📂 <b>Коллекция карт:</b>\nВыбери редкость:")

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

    bot.send_message(message.chat.id, txt, reply_markup=markup, parse_mode="HTML")


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
    # Фильтруем. i.get('cards') может быть пустым — "призрачная" строка
    # user_cards на уже удалённую карту (если миграция чистки призраков ещё
    # не прогонялась на этой базе); без проверки i['cards']['rarity'] падало
    # необработанным исключением, и экран редкости просто не открывался.
    filtered = [i for i in inv_data if i.get('cards') and i['cards'].get('rarity') == rarity]

    if not filtered:
        bot.answer_callback_query(call.id, "Пусто!", show_alert=True)
        return

    index = int(parts[2]) if len(parts) > 2 else 0
    if index >= len(filtered): index = 0
    if index < 0: index = len(filtered) - 1

    item = filtered[index]
    card = item['cards']
    level = item.get('card_level', 1) or 1
    eff_attack, eff_hp = get_effective_stats(card['attack'], card['hp'], level)

    universe_line = f"\n\nМир: {card['dunhua']}\n" if card.get('dunhua') else "\n"
    caption = (f"{RARITY_CONFIG[rarity]['emoji']} <b>{card['name']}</b>"
               f"{universe_line}\n"
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

    # КНОПКА УЛУЧШЕНИЯ (слияние дублей) — требование доп. копий и цена по
    # таблице уровней (см. get_fuse_requirements), одинаковой для всех
    # редкостей. Сама карта в счёт дополнительных копий не идёт.
    extra_needed, fuse_cost = get_fuse_requirements(level)
    have_extra = max(item['count'] - 1, 0)
    if extra_needed is None:
        fuse_btn = types.InlineKeyboardButton("🔀 Максимальный уровень", callback_data="ignore")
    elif have_extra >= extra_needed:
        fuse_btn = types.InlineKeyboardButton(
            f"🔀 Улучшить (+{extra_needed} карт, {fuse_cost}💰)",
            callback_data=f"fuse_card:{card['id']}:{rarity}:{index}")
    else:
        fuse_btn = types.InlineKeyboardButton(
            f"🔀 Улучшить ({have_extra}/{extra_needed} доп. карт, {fuse_cost}💰)",
            callback_data="ignore")
    markup.row(fuse_btn)

    # Стандартные кнопки навигации
    markup.row(
        types.InlineKeyboardButton("⬅️", callback_data=f"inv_nav:{rarity}:{index - 1}"),
        types.InlineKeyboardButton(f"{index + 1}/{len(filtered)}", callback_data="ignore"),
        types.InlineKeyboardButton("➡️", callback_data=f"inv_nav:{rarity}:{index + 1}")
    )
    markup.row(types.InlineKeyboardButton("🔙 Назад", callback_data="inv_back_main"))

    try:
        if not card.get('image_file_id'):
            raise ValueError("card has no image_file_id")
        is_video = card.get('media_type') == 'video'
        # edit_message_media умеет менять фото на видео и обратно, НО только
        # если ему передать InputMedia правильного типа под НОВУЮ карту —
        # раньше тут всегда строился InputMediaPhoto, и переключение со
        # следующей/предыдущей карты на видео падало с ошибкой API.
        media = (types.InputMediaVideo(card['image_file_id'], caption=caption, parse_mode="HTML") if is_video
                else types.InputMediaPhoto(card['image_file_id'], caption=caption, parse_mode="HTML"))
        if action == "inv_nav":
            bot.edit_message_media(media=media, chat_id=call.message.chat.id, message_id=call.message.message_id,
                                   reply_markup=markup)
        else:
            bot.delete_message(call.message.chat.id, call.message.message_id)
            if is_video:
                bot.send_video(call.message.chat.id, card['image_file_id'], caption=caption, reply_markup=markup,
                               parse_mode="HTML")
            else:
                bot.send_photo(call.message.chat.id, card['image_file_id'], caption=caption, reply_markup=markup,
                               parse_mode="HTML")
    except Exception as e:
        # Раньше тут было голое except: bot.answer_callback_query(call.id) —
        # при любой ошибке (например у карты нет/битый image_file_id) экран
        # просто молча не открывался, без единой подсказки, что пошло не так.
        # Теперь логируем и гарантированно показываем карту хотя бы текстом.
        print(f"Error showing card in inventory (card_id={card.get('id')}): {e}")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, caption, reply_markup=markup, parse_mode="HTML")


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

    success, result = fuse_cards(call.from_user.id, card_id)

    if success:
        update_task_progress(call.from_user.id, "fuse_card", "daily")
        bot.answer_callback_query(call.id, f"✨ Карта улучшена до уровня {result}!", show_alert=True)
    else:
        bot.answer_callback_query(call.id, result, show_alert=True)
        return

    call.data = f"inv_nav:{rarity}:{index}"
    inventory_nav(call)
