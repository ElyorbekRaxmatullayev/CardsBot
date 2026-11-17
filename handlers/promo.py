from telebot import types

from config import PACK_CONFIG
from database import redeem_promo_code, is_user_banned
from loader import bot
from utils import safe_send_message, register_next_step_handler_for_user, reply_match


def _reward_summary(promo):
    parts = []
    if promo.get('reward_coins'):
        parts.append(f"💰{promo['reward_coins']} монет")
    if promo.get('reward_gems'):
        parts.append(f"💎{promo['reward_gems']} гемов")
    if promo.get('reward_fragments'):
        parts.append(f"💠{promo['reward_fragments']} фрагментов")
    if promo.get('reward_pack_type') and promo.get('reward_pack_count'):
        pack_name = PACK_CONFIG.get(promo['reward_pack_type'], {}).get('name', promo['reward_pack_type'])
        parts.append(f"{pack_name} x{promo['reward_pack_count']}")
    return "\n".join(parts) if parts else "—"


@bot.message_handler(commands=['promo'])
@bot.message_handler(func=reply_match("🎟 Промокод", "Промокод"))
def promo_start(message, user_id=None):
    user_id = user_id or message.from_user.id
    if is_user_banned(user_id):
        bot.send_message(message.chat.id, "⛔️ Вы заблокированы в этом боте.")
        return
    msg = safe_send_message(bot, message.chat.id,
                            "🎟 Введите промокод:", owner_id=user_id)
    if msg:
        register_next_step_handler_for_user(bot, msg, user_id, _promo_code_step)


def _promo_code_step(message):
    user_id = message.from_user.id
    code = (message.text or "").strip()
    if not code:
        bot.send_message(message.chat.id, "❌ Промокод не может быть пустым.")
        return

    success, result = redeem_promo_code(user_id, code)
    if not success:
        bot.send_message(message.chat.id, f"❌ {result}")
        return

    promo = result
    bot.send_message(message.chat.id,
                     f"✅ <b>Промокод активирован!</b>\n\nВы получили:\n{_reward_summary(promo)}",
                     parse_mode="HTML")
