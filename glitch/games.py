# games.py

import random
import logging
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from data_manager import save_data

def show_games_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_callback_button("Орел-Решка", color=VkKeyboardColor.PRIMARY, payload={"command": "coinflip"})
    keyboard.add_callback_button("Бонус", color=VkKeyboardColor.POSITIVE, payload={"command": "get_glitch"})
    keyboard.add_callback_button("Баланс", color=VkKeyboardColor.SECONDARY, payload={"command": "баланс"})
    return keyboard.get_keyboard()

def start_coinflip(user_id, amount, vk, peer_id):
    if amount <= 0:
        vk.messages.send(
            peer_id=peer_id,
            message="Ставка должна быть больше нуля.",
            random_id=random.randint(1, 1000)
        )
        return

    keyboard = VkKeyboard(inline=True)
    keyboard.add_callback_button("Орел", color=VkKeyboardColor.PRIMARY, payload={"command": "coinflip_choice", "choice": "heads", "amount": amount})
    keyboard.add_callback_button("Решка", color=VkKeyboardColor.PRIMARY, payload={"command": "coinflip_choice", "choice": "tails", "amount": amount})
    vk.messages.send(
        peer_id=peer_id,
        message=f"Вы выбрали ставку {amount}. Выберите на что ставите:",
        keyboard=keyboard.get_keyboard(),
        random_id=random.randint(1, 1000)
    )

def process_coinflip_choice(user_id, choice, amount, player_data, vk, peer_id):
    if player_data[user_id]["balance"] < amount:
        vk.messages.send(
            peer_id=peer_id,
            message="Недостаточно средств на балансе для этой ставки.",
            random_id=random.randint(1, 1000)
        )
        return

    player_data[user_id]["balance"] -= amount

    result = "heads" if random.randint(0, 1) == 0 else "tails"
    if choice == result:
        winnings = amount * 2
        player_data[user_id]["balance"] += winnings
        message = f"Поздравляем! Вы выиграли {winnings}. Баланс: {player_data[user_id]['balance']} Glitch⚡."
    else:
        message = f"Вы проиграли. Выпало {result}. Баланс: {player_data[user_id]['balance']} Glitch⚡."

    vk.messages.send(
        peer_id=peer_id,
        message=message,
        random_id=random.randint(1, 1000)
    )
    save_data(player_data)