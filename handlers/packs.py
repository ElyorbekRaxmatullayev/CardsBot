import random

from telebot import types

from config import PACK_CONFIG, RARITY_CONFIG
from database import (get_user_data, update_coins, update_gems,
                      add_card_to_user, get_all_cards, add_pack_to_user,
                      get_user_packs, use_pack, increment_packs_opened,
                      update_task_progress, on_card_obtained)
from loader import bot
from utils import safe_send_message, safe_edit_message


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def drop_card_by_weights(weights: dict):
    """Выбирает карту с учётом весов редкости пака"""
    all_cards = get_all_cards()
    if not all_cards:
        return None
    filtered = {r: [c for c in all_cards if c['rarity'] == r] for r in weights if weights[r] > 0}
    rarities = [r for r in filtered if filtered[r]]
    w = [weights[r] for r in rarities]
    if not rarities:
        return None
    chosen_rarity = random.choices(rarities, weights=w, k=1)[0]
    return random.choice(filtered[chosen_rarity])


def format_card_line(card):
    """Формирует строку с инфо о карте для показа"""
    emoji = RARITY_CONFIG.get(card['rarity'], {}).get('emoji', '❓')
    rarity_ru = RARITY_CONFIG.get(card['rarity'], {}).get('ru', card['rarity'])
    return f"{emoji} <b>{card['name']}</b> — {rarity_ru}"


# --- МЕНЮ ПАКОВ ---

def get_packs_menu_markup(user_id):
    """Главное меню паков"""
    markup = types.InlineKeyboardMarkup()
    packs = get_user_packs(user_id)
    pack_counts = {p['pack_type']: p['count'] for p in packs}

    for pack_key, cfg in PACK_CONFIG.items():
        count = pack_counts.get(pack_key, 0)
        label = f"{cfg['name']} [{count}шт]" if count > 0 else cfg['name']
        markup.add(types.InlineKeyboardButton(label, callback_data=f"pack_view:{pack_key}"))

    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_game_menu"))
    return markup


@bot.callback_query_handler(func=lambda call: call.data == "menu_packs")
def packs_menu(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    packs = get_user_packs(user_id)
    total = sum(p['count'] for p in packs)

    txt = (f"🎴 <b>Мои паки</b>\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"У вас всего паков: <b>{total}</b>\n\n"
           f"Выберите пак, чтобы открыть:")
    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=get_packs_menu_markup(user_id), parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith("pack_view:"))
def pack_view(call):
    bot.answer_callback_query(call.id)
    pack_type = call.data.split(":")[1]
    cfg = PACK_CONFIG.get(pack_type)
    if not cfg:
        return

    user_id = call.from_user.id
    packs = get_user_packs(user_id)
    pack_counts = {p['pack_type']: p['count'] for p in packs}
    count = pack_counts.get(pack_type, 0)

    user = get_user_data(user_id)
    gems = user.get('gems', 0) or 0

    price_txt = ""
    if cfg['price_coins'] > 0:
        price_txt += f"💰 {cfg['price_coins']} монет"
    if cfg['price_gems'] > 0:
        if price_txt:
            price_txt += f" / 💎 {cfg['price_gems']} Gems"
        else:
            price_txt = f"💎 {cfg['price_gems']} Gems"

    txt = (f"{cfg['name']}\n"
           f"➖➖➖➖➖➖➖➖\n"
           f"📋 {cfg['description']}\n"
           f"🃏 Карт в паке: {cfg['cards_count']}\n"
           f"💵 Цена: {price_txt}\n\n"
           f"У вас: <b>{count} пак(а)</b>\n"
           f"Баланс: 💰 {user['coins']} | 💎 {gems}")

    markup = types.InlineKeyboardMarkup()
    if count > 0:
        markup.add(types.InlineKeyboardButton(f"🎴 Открыть пак [{count}шт]",
                                              callback_data=f"pack_open:{pack_type}"))
    if cfg['price_coins'] > 0:
        markup.add(types.InlineKeyboardButton(f"💰 Купить за {cfg['price_coins']} монет",
                                              callback_data=f"pack_buy_coins:{pack_type}"))
    if cfg['price_gems'] > 0:
        markup.add(types.InlineKeyboardButton(f"💎 Купить за {cfg['price_gems']} Gems",
                                              callback_data=f"pack_buy_gems:{pack_type}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="menu_packs"))

    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup, parse_mode="HTML")


# --- ПОКУПКА ПАКОВ ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("pack_buy_coins:"))
def pack_buy_coins(call):
    pack_type = call.data.split(":")[1]
    cfg = PACK_CONFIG.get(pack_type)
    user_id = call.from_user.id
    user = get_user_data(user_id)

    if user['coins'] < cfg['price_coins']:
        bot.answer_callback_query(call.id, f"Недостаточно монет! Нужно {cfg['price_coins']} 💰", show_alert=True)
        return

    update_coins(user_id, -cfg['price_coins'])
    update_task_progress(user_id, "spend_coins", "weekly", increment=cfg['price_coins'])
    add_pack_to_user(user_id, pack_type)
    bot.answer_callback_query(call.id, f"✅ Куплен {cfg['name']}!")
    # Обновляем меню
    call.data = f"pack_view:{pack_type}"
    pack_view(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("pack_buy_gems:"))
def pack_buy_gems(call):
    pack_type = call.data.split(":")[1]
    cfg = PACK_CONFIG.get(pack_type)
    user_id = call.from_user.id

    if not update_gems(user_id, -cfg['price_gems']):
        bot.answer_callback_query(call.id, f"Недостаточно Gems! Нужно {cfg['price_gems']} 💎", show_alert=True)
        return

    add_pack_to_user(user_id, pack_type)
    bot.answer_callback_query(call.id, f"✅ Куплен {cfg['name']}!")
    call.data = f"pack_view:{pack_type}"
    pack_view(call)


# --- ОТКРЫТИЕ ПАКА ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("pack_open:"))
def pack_open(call):
    bot.answer_callback_query(call.id)
    pack_type = call.data.split(":")[1]
    user_id = call.from_user.id
    cfg = PACK_CONFIG.get(pack_type)
    if not cfg:
        return

    if not use_pack(user_id, pack_type):
        bot.answer_callback_query(call.id, "У вас нет этого пака!", show_alert=True)
        return

    # Открываем
    cards = []
    weights = cfg.get('rarity_weights', {})
    for _ in range(cfg['cards_count']):
        card = drop_card_by_weights(weights)
        if card:
            is_dup, _ = add_card_to_user(user_id, card['id'])
            on_card_obtained(user_id, card, is_dup)
            cards.append(card)

    # Обновляем счётчики заданий
    increment_packs_opened(user_id)
    update_task_progress(user_id, "open_pack", "daily")
    update_task_progress(user_id, "open_packs_3", "daily")
    update_task_progress(user_id, "open_packs_10", "weekly")

    # Формируем текст
    txt = f"🎴 <b>{cfg['name']} открыт!</b>\n➖➖➖➖➖➖➖➖\n\nВы получили:\n\n"
    for card in cards:
        txt += format_card_line(card) + "\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎴 Открыть ещё", callback_data=f"pack_view:{pack_type}"))
    markup.add(types.InlineKeyboardButton("📦 К пакам", callback_data="menu_packs"))
    markup.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_game_menu"))

    safe_edit_message(bot, call.message.chat.id, call.message.message_id,
                      txt, reply_markup=markup, parse_mode="HTML")
