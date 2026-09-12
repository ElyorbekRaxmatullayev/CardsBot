import random
import time

from telebot import types

from config import BATTLE_WEIGHTS, EVENT_TEXTS, FUSE_LEVEL_BONUS_PERCENT
from database import (get_user_data, get_clan_info, get_user_squad, join_queue,
                      leave_queue, find_opponent, update_battle_stats, update_task_progress)
from loader import bot
from utils import safe_edit_message, safe_send_message


# --- МЕНЮ АРЕНЫ ---
@bot.callback_query_handler(func=lambda call: call.data == "menu_arena")
def arena_main_menu(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    user = get_user_data(user_id)

    if user['clan_id']:
        clan = get_clan_info(user['clan_id'])
        if clan and clan['owner_id'] == user_id:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⚔️ Дуэль", callback_data="arena_duel_mode"))
            markup.add(types.InlineKeyboardButton("🏰 Клановая война", callback_data="arena_clan_war"))
            markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_game_menu"))
            safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                              "👑 <b>Приветствую, Лидер!</b>\nВыберите тип сражения:",
                              reply_markup=markup, parse_mode="HTML")
            return

    show_duel_menu(call.message, user_id)


@bot.callback_query_handler(func=lambda call: call.data == "arena_clan_war")
def clan_war_stub(call):
    bot.answer_callback_query(call.id, "Скоро...", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == "arena_duel_mode")
def duel_mode_callback(call):
    bot.answer_callback_query(call.id)
    show_duel_menu(call.message, call.from_user.id)


def show_duel_menu(message, user_id):
    # user_id передаётся явно: message тут — это сообщение БОТА (мы его редактируем),
    # а message.chat.id в группе — это ID группы, а не игрока (в ЛС они случайно совпадают)
    user = get_user_data(user_id)
    squad = get_user_squad(user_id)
    rating = user.get('rating', 1000)

    txt = (f"🏟 <b>Арена: Дуэли</b>\n\n"
           f"🏆 Твой рейтинг: {rating}\n"
           f"🛡 Войнов в отряде: {len(squad)}/5\n\n"
           f"Готов сразиться за славу?")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⚔️ Найти противника", callback_data="arena_find"))
    markup.add(types.InlineKeyboardButton("🛡 Мой отряд (Карты)", callback_data="arena_my_squad"))
    markup.add(types.InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_game_menu"))

    safe_edit_message(bot, message.chat.id, message.message_id, txt, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "arena_my_squad")
def redirect_to_cards(call):
    bot.answer_callback_query(call.id)
    from handlers.cards import inventory_menu
    bot.delete_message(call.message.chat.id, call.message.message_id)
    call.message.text = "🗂 Мои карты"
    inventory_menu(call.message, user_id=call.from_user.id)


# --- ПОИСК И БОЙ ---

@bot.callback_query_handler(func=lambda call: call.data == "arena_find")
def start_search(call):
    user_id = call.from_user.id
    my_chat_id = call.message.chat.id

    squad = get_user_squad(user_id)
    if not squad:
        bot.answer_callback_query(call.id, "Твой отряд пуст! Выбери хотя бы 1 карту.", show_alert=True)
        return

    opponent_id, opponent_chat_id = find_opponent(user_id)

    if opponent_id:
        bot.answer_callback_query(call.id, "Противник найден!")
        # ЗАПУСК БОЯ С АНИМАЦИЕЙ — результат шлём туда, откуда каждый игрок реально зашёл
        # в поиск (ЛС или группа), а не всегда в личку (там могло не быть диалога с ботом)
        start_battle_animated(user_id, my_chat_id, opponent_id, opponent_chat_id)
    else:
        join_queue(user_id, my_chat_id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Отменить поиск", callback_data="arena_cancel"))
        safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                          "🔍 <b>Поиск противника...</b>\n\nПодбираем равного по силе...",
                          reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "arena_cancel")
def cancel_search(call):
    leave_queue(call.from_user.id)
    bot.answer_callback_query(call.id, "Поиск отменен")
    show_duel_menu(call.message, call.from_user.id)


def start_battle_animated(player1_id, player1_chat_id, player2_id, player2_chat_id):
    # chat_id может отсутствовать (старые записи в очереди до миграции) —
    # тогда просто шлём в ЛС, как раньше
    player1_chat_id = player1_chat_id or player1_id
    player2_chat_id = player2_chat_id or player2_id

    # 1. Загрузка данных
    p1_user = get_user_data(player1_id)
    p2_user = get_user_data(player2_id)
    p1_squad = get_user_squad(player1_id)
    p2_squad = get_user_squad(player2_id)

    def calc_stats(squad):
        # Уровень карты после слияния дублей даёт бонус к atk/hp (см. fuse_cards)
        hp = 0
        atk = 0
        for c in squad:
            level = c.get('card_level', 1) or 1
            mult = 1 + (FUSE_LEVEL_BONUS_PERCENT / 100) * (level - 1)
            hp += int(c['hp'] * mult)
            atk += int(c['attack'] * mult)
        return hp, atk

    p1_hp_max, p1_atk = calc_stats(p1_squad)
    p2_hp_max, p2_atk = calc_stats(p2_squad)

    p1_curr = p1_hp_max
    p2_curr = p2_hp_max

    p1_dmg_total = 0
    p2_dmg_total = 0

    # Стартовое сообщение
    msg_text = (f"⚔️ <b>БОЙ НАЧАЛСЯ!</b>\n\n"
                f"🔵 {p1_user['first_name']} (HP: {p1_curr})\n"
                f"🔴 {p2_user['first_name']} (HP: {p2_curr})\n\n"
                f"⏳ <i>Бойцы встают в стойку...</i>")

    msg1 = safe_send_message(bot, player1_chat_id, msg_text, parse_mode="HTML")
    msg2 = safe_send_message(bot, player2_chat_id, msg_text, parse_mode="HTML")

    time.sleep(2)

    # --- ГЛАВНЫЙ ЦИКЛ БОЯ ---
    rounds = 0

    # ВОТ ЗДЕСЬ ИСПРАВЛЕНИЕ:
    # Цикл работает ПОКА у обоих есть жизни.
    # rounds < 100 - это просто защита от зависания (если бой затянется на 10 минут)
    while p1_curr > 0 and p2_curr > 0 and rounds < 100:
        rounds += 1

        # Генерация действий
        act1, val1, txt1 = generate_turn_action(p1_atk, p1_user['first_name'])
        act2, val2, txt2 = generate_turn_action(p2_atk, p2_user['first_name'])

        p1_take = 0
        p2_take = 0

        # Логика P1
        if act1 == "heal":
            p1_curr = min(p1_hp_max, p1_curr + val1)
        elif act1 == "counter":
            p2_take += val1
        elif act1 in ["attack", "crit", "artifact"]:
            p2_take += val1

        # Логика P2
        if act2 == "heal":
            p2_curr = min(p2_hp_max, p2_curr + val2)
        elif act2 == "counter":
            p1_take += val2
        elif act2 in ["attack", "crit", "artifact"]:
            p1_take += val2

        # Увороты и промахи
        if act1 == "dodge" or act2 == "miss" or act2 == "focus":
            p1_take = 0
            if act1 == "dodge": txt1 = f"💨 {p1_user['first_name']} ушел в тень!"

        if act2 == "dodge" or act1 == "miss" or act1 == "focus":
            p2_take = 0
            if act2 == "dodge": txt2 = f"💨 {p2_user['first_name']} ушел в тень!"

        # Применяем урон
        p1_curr -= p1_take
        p2_curr -= p2_take

        p1_dmg_total += p2_take
        p2_dmg_total += p1_take

        # Формирование текста (Без "Раунд Х")
        def fmt_eff(act, val, taken):
            if act == "heal": return f"💚 +{val}"
            if taken > 0: return f"💥 -{taken}"
            if act in ["miss", "focus", "dodge"]: return "💫"
            return ""

        eff1 = fmt_eff(act1, val1, p2_take)
        eff2 = fmt_eff(act2, val2, p1_take)

        # Случайный заголовок
        header = random.choice([
            "⚔️ ОБМЕН УДАРАМИ...", "🔥 БИТВА НАКАЛЯЕТСЯ!",
            "⚡️ СКОРОСТЬ ЗАПРЕДЕЛЬНАЯ!", "🩸 ТЕХНИКИ СТОЛКНУЛИСЬ!",
            "🌪 ЗЕМЛЯ ДРОЖИТ!", "💥 МОЩНЫЙ ВЗРЫВ!"
        ])

        log = (f"{header}\n\n"
               f"🔵 {txt1} <b>({eff1})</b>\n\n"
               f"🔴 {txt2} <b>({eff2})</b>\n"
               f"➖➖➖➖➖➖➖➖\n"
               f"🔵 {p1_user['first_name']}: {max(0, p1_curr)} HP\n"
               f"🔴 {p2_user['first_name']}: {max(0, p2_curr)} HP")

        if msg1: safe_edit_message(bot, player1_chat_id, msg1.message_id, log, parse_mode="HTML")
        if msg2: safe_edit_message(bot, player2_chat_id, msg2.message_id, log, parse_mode="HTML")

        time.sleep(3.5)  # Пауза для чтения

    # --- ИТОГИ ---

    if p1_curr > p2_curr:
        winner_id, loser_id = player1_id, player2_id
        w_dmg, l_dmg = p1_dmg_total, p2_dmg_total
        w_hp_left = p1_curr
        loser_max = p2_hp_max
        enemy_name_w = p2_user['first_name']
        enemy_name_l = p1_user['first_name']
    else:
        winner_id, loser_id = player2_id, player1_id
        w_dmg, l_dmg = p2_dmg_total, p1_dmg_total
        w_hp_left = p2_curr
        loser_max = p1_hp_max
        enemy_name_w = p1_user['first_name']
        enemy_name_l = p2_user['first_name']

    update_battle_stats(winner_id, loser_id, w_dmg=w_dmg, l_dmg=l_dmg)

    # Обновляем счётчики заданий: "провести бой" — обоим, "выиграть бой" — только победителю
    update_task_progress(player1_id, "arena_battle", "daily")
    update_task_progress(player2_id, "arena_battle", "daily")
    update_task_progress(winner_id, "battles_5", "weekly")

    res_win = (f"🏆 <b>ПОБЕДА!</b>\n\n"
               f"Противник: <b>{enemy_name_w}</b> повержен!\n"
               f"Ваше здоровье: {w_hp_left}\n"
               f"Урон нанесен: {w_dmg}\n\n"
               f"💰 Награда: +10 монет, +25 рейтинга")

    res_lose = (f"💀 <b>ПОРАЖЕНИЕ...</b>\n\n"
                f"Противник: <b>{enemy_name_l}</b> оказался сильнее.\n"
                f"Здоровье врага: 0/{loser_max}\n"
                f"Урон нанесен: {l_dmg}\n\n"
                f"📉 -15 рейтинга")

    result_markup = types.InlineKeyboardMarkup()
    result_markup.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_game_menu"))

    if msg1:
        fin = res_win if winner_id == player1_id else res_lose
        safe_edit_message(bot, player1_chat_id, msg1.message_id, fin,
                          reply_markup=result_markup, parse_mode="HTML")

    if msg2:
        fin = res_win if winner_id == player2_id else res_lose
        safe_edit_message(bot, player2_chat_id, msg2.message_id, fin,
                          reply_markup=result_markup, parse_mode="HTML")


# --- ГЕНЕРАТОР ---
def generate_turn_action(atk_power, name):
    events = list(BATTLE_WEIGHTS.keys())
    weights = list(BATTLE_WEIGHTS.values())
    action = random.choices(events, weights=weights, k=1)[0]

    # Берем текст из конфига (Убедись что config.py обновлен!)
    try:
        text = random.choice(EVENT_TEXTS[action]).format(name=name)
    except:
        text = f"{name} атакует!"  # На случай ошибок конфига

    value = 0
    if action == "attack":
        value = int(atk_power * random.uniform(0.8, 1.2))
    elif action == "crit":
        value = int(atk_power * random.uniform(1.6, 2.2))
    elif action == "artifact":
        value = int(atk_power * 3.0)
    elif action == "counter":
        value = int(atk_power * 0.6)
    elif action == "heal":
        value = int(atk_power * 1.5)

    return action, value, text
