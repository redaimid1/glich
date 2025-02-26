import json
import random
import logging
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from data_manager import (
    load_player_data, save_player_data, add_click_to_data,
    update_user_name, add_user, auto_adjust_balance,
    add_winning_to_data, add_transfer_to_data, load_games, save_games
)
from games.coinflip import show_games_keyboard, start_coinflip, process_coinflip_choice, coinflip_sessions
from games.mines import (
    start_mines,
    process_mines_field,
    process_mines_option, 
    process_mines_text,
    process_mines_choice,
    mines_sessions,
    handle_mines_move
)
from games.transfers import initiate_transfer, process_transfer_confirmation, process_transfer, transfer_sessions
from config import CONFIG
from utils import format_user_tag

# Словари для отслеживания состояний вне игровых сессий
awaiting_name_change = {}
awaiting_bet = {}

def is_group_chat(peer_id):
    return peer_id >= 2000000000

def answer_callback(vk, event, text="\u200b"):
    """
    Отвечает на callback-запрос, чтобы скрыть индикатор загрузки.
    Используется невидимый символ (zero-width space) по умолчанию.
    """
    try:
        if not text or len(text.strip()) == 0:
            text = "\u200b"
        event_data = json.dumps({"type": "show_snackbar", "text": text})
        event_obj = event.obj
        vk.messages.sendMessageEventAnswer(
            event_id=event_obj.event_id,
            user_id=event_obj.user_id,
            peer_id=event_obj.peer_id,
            event_data=event_data
        )
    except Exception as e:
        logging.error(f"Ошибка при ответе на callback: {e}")

def get_inline_keyboard(buttons):
    """
    Вспомогательная функция для создания inline клавиатуры.
    buttons: Список списков кортежей (текст, словарь payload, цвет кнопки)
    """
    kb = VkKeyboard(inline=True)
    for row in buttons:
        for text, payload, color in row:
            kb.add_callback_button(text, color=color, payload=payload)
        kb.add_line()
    return kb.get_keyboard()

def handle_message(event, player_data, vk):
    # Получаем и очищаем текст сообщения
    raw_text = event.obj.message.get('text', '')
    message_text = raw_text.replace("\xa0", " ").replace("\u200b", "").replace("\uFEFF", "").strip()
    user_id = event.obj.message.get('from_id')
    peer_id = event.obj.message.get('peer_id')
    
    # Если активна сессия перевода, передаём управление модулю переводов
    if str(user_id) in transfer_sessions:
        if process_transfer(event, user_id, message_text, player_data, vk):
            return

    # Инициируем перевод, если сообщение начинается с "перевод" или "send"
    if message_text.lower().startswith(("перевод", "send")):
        initiate_transfer(user_id, event, vk)
        return

    # Если активна сессия игры "Мины", передаём сообщение в обработку
    if str(user_id) in mines_sessions:
        if process_mines_text(user_id, message_text, player_data, vk, peer_id):
            return

    # Генерируем тег пользователя (используем никнейм, если указан)
    tag = format_user_tag(user_id, player_data.get(str(user_id), {}))
    logging.debug(f"Получено сообщение от {user_id} {tag}: raw='{raw_text}' -> processed='{message_text}' (repr: {repr(message_text)})")
    
    # Обработка смены имени
    if str(user_id) in awaiting_name_change:
        if message_text.lower() == "отмена":
            vk.messages.send(
                peer_id=peer_id,
                message=f"{tag}\nСмена имени отменена.",
                random_id=random.randint(1, 1000)
            )
        else:
            update_user_name(user_id, message_text, player_data)
            tag = format_user_tag(user_id, player_data.get(str(user_id), {}))
            vk.messages.send(
                peer_id=peer_id,
                message=f"{tag}\nИмя изменено на {message_text}.",
                random_id=random.randint(1, 1000)
            )
        del awaiting_name_change[str(user_id)]
        add_click_to_data(user_id, 0, player_data)
        auto_adjust_balance(user_id, player_data)
        return

    # Обработка ввода суммы ставки для игр
    if str(user_id) in awaiting_bet:
        try:
            logging.debug(f"Преобразование ставки для {user_id} {tag}: '{message_text}'")
            amount = int(message_text)
            game_type = awaiting_bet[str(user_id)]
            del awaiting_bet[str(user_id)]
            current_balance = int(player_data.get(str(user_id), {}).get("balance", 0))
            if current_balance < amount:
                vk.messages.send(
                    peer_id=peer_id,
                    message=f"{tag}\nНедостаточно средств для ставки.",
                    random_id=random.randint(1, 1000)
                )
                return
            if game_type == "coinflip":
                start_coinflip(user_id, amount, player_data, vk, peer_id)
            elif game_type == "mines":
                start_mines(user_id, amount, player_data, vk, peer_id)
            auto_adjust_balance(user_id, player_data)
        except ValueError as e:
            logging.error(f"Ошибка преобразования ставки '{message_text}' для {user_id} {tag}: {e}")
            vk.messages.send(
                peer_id=peer_id,
                message=f"{tag}\nПожалуйста, введите корректную ставку.",
                random_id=random.randint(1, 1000)
            )
        return

    # Обработка сообщений из группового чата
    if is_group_chat(peer_id):
        lower_text = message_text.lower()
        if lower_text == "начать":
            if bot_has_admin_permissions(peer_id, vk):
                start_games_in_chat(vk, peer_id)
            else:
                vk.messages.send(
                    peer_id=peer_id,
                    message=f"{tag}\nБот требует администраторские права для управления чатом и запуска игр.",
                    random_id=random.randint(1, 1000)
                )
            return
        elif lower_text in ["игры", "бонус"]:
            return
    else:
        # Обработка команд в личном чате
        lower_text = message_text.lower()
        if lower_text in ["начать", "меню"]:
            start_game(user_id, player_data, vk, peer_id)
        elif lower_text == "клики":
            farm_clicks(user_id, player_data, vk, peer_id)
        elif lower_text == "баланс":
            show_balance(user_id, player_data, vk, peer_id)
        elif lower_text == "профиль":
            show_profile(user_id, player_data, vk, peer_id)
        elif lower_text == "топ балансов":
            show_top_balances(user_id, player_data, vk, peer_id)
        elif lower_text == "топ майнеров":
            show_top_miners(user_id, player_data, vk, peer_id)
        else:
            return
    add_click_to_data(user_id, 0, player_data)

def start_game(user_id, player_data, vk, peer_id):
    if str(user_id) not in player_data:
        add_user(user_id, player_data, vk)  # Передаем vk при вызове add_user
    tag = format_user_tag(user_id, player_data.get(str(user_id), {}))
    if not is_group_chat(peer_id):
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_callback_button("Glitch⚡", color=VkKeyboardColor.PRIMARY, payload={"command": "get_glitch"})
        keyboard.add_line()
        keyboard.add_callback_button("Играть🎰", color=VkKeyboardColor.PRIMARY, payload={"command": "join_chat", "link": CONFIG["CHAT_LINK"]})
        keyboard.add_line()
        keyboard.add_callback_button("Профиль👤", color=VkKeyboardColor.SECONDARY, payload={"command": "профиль"})
        keyboard.add_callback_button("Переводы", color=VkKeyboardColor.SECONDARY, payload={"command": "transfer"})
        keyboard.add_line()
        keyboard.add_callback_button("Топ балансов💸", color=VkKeyboardColor.POSITIVE, payload={"command": "топ балансов"})
        keyboard.add_callback_button("Топ майнеров⛏️", color=VkKeyboardColor.POSITIVE, payload={"command": "топ майнеров"})
        menu_keyboard = keyboard.get_keyboard()
    else:
        menu_keyboard = None
    vk.messages.send(
        peer_id=peer_id,
        message=f"{tag}\nПривет! Я Glitch – майнить или не майнить? Твое решение.",
        keyboard=menu_keyboard,
        random_id=random.randint(1, 1000)
    )
    logging.info(f"Отправлено стартовое сообщение пользователю {user_id} {tag}.")
    auto_adjust_balance(user_id, player_data)

def farm_clicks(user_id, player_data, vk, peer_id):
    if str(user_id) not in player_data:
        return
    earned_glitch = random.randint(5, 17)
    add_click_to_data(user_id, earned_glitch, player_data)
    tag = format_user_tag(user_id, player_data.get(str(user_id), {}))
    logging.info(f"Пользователь {user_id} {tag} нашёл {earned_glitch} Glitch⚡. Новый баланс: {player_data[str(user_id)]['balance']}")
    vk.messages.send(
        peer_id=peer_id,
        message=f"{tag}\nВы нашли {earned_glitch} Glitch⚡! Новый баланс: {player_data[str(user_id)]['balance']} Glitch⚡.",
        random_id=random.randint(1, 1000)
    )
    auto_adjust_balance(user_id, player_data)

def show_balance(user_id, player_data, vk, peer_id):
    tag = format_user_tag(user_id, player_data.get(str(user_id), {}))
    if str(user_id) in player_data:
        balance = player_data[str(user_id)]["balance"]
        vk.messages.send(
            peer_id=peer_id,
            message=f"{tag}\nВаш баланс: {balance} Glitch⚡.",
            random_id=random.randint(1, 1000)
        )
    else:
        vk.messages.send(
            peer_id=peer_id,
            message=f"{tag}\nВы ещё не начали игру. Напишите 'начать', чтобы начать!",
            random_id=random.randint(1, 1000)
        )
    auto_adjust_balance(user_id, player_data)

def show_profile(user_id, player_data, vk, peer_id):
    tag = format_user_tag(user_id, player_data.get(str(user_id), {}))
    if str(user_id) in player_data:
        profile = (
            f"{tag}\nПрофиль:\n"
            f"Баланс: {player_data[str(user_id)]['balance']} Glitch⚡\n"
            f"Баланс за всё время: {player_data[str(user_id)]['total_balance']} Glitch⚡\n"
            f"Кликов: {player_data[str(user_id)]['clicks']}\n"
            f"Дата начала игры: {player_data[str(user_id)]['start_date']}\n\n"
            "Ты можешь сменить никнейм нажав на кнопку ниже"
        )
        keyboard = VkKeyboard(inline=True)
        keyboard.add_callback_button("Сменить имя", color=VkKeyboardColor.PRIMARY, payload={"command": "change_name"})
        inline_menu = keyboard.get_keyboard()
        vk.messages.send(
            peer_id=peer_id,
            message=profile,
            keyboard=inline_menu,
            random_id=random.randint(1, 1000)
        )
    else:
        vk.messages.send(
            peer_id=peer_id,
            message=f"{tag}\nВы ещё не начали игру. Напишите 'начать', чтобы начать!",
            random_id=random.randint(1, 1000)
        )

def show_top_balances(user_id, player_data, vk, peer_id):
    top = sorted(player_data.items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:5]
    message = "Топ 5 балансов:\n"
    for i, (uid, data) in enumerate(top, 1):
        tag_user = format_user_tag(uid, data)
        message += f"{i}. {tag_user}: {data.get('balance', 0)} Glitch⚡\n"
    vk.messages.send(
        peer_id=peer_id,
        message=message,
        random_id=random.randint(1, 1000)
    )

def show_top_miners(user_id, player_data, vk, peer_id):
    message = "Топ майнеров пока не доступен, но скоро будет!"
    vk.messages.send(
        peer_id=peer_id,
        message=message,
        random_id=random.randint(1, 1000)
    )

def bot_has_admin_permissions(peer_id, vk):
    # Здесь можно реализовать проверку прав администратора.
    return True

def start_games_in_chat(vk, peer_id):
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_callback_button("Орел-Решка", color=VkKeyboardColor.PRIMARY, payload={"command": "coinflip"})
    keyboard.add_callback_button("Мины", color=VkKeyboardColor.PRIMARY, payload={"command": "mines"})
    keyboard.add_callback_button("Баланс", color=VkKeyboardColor.SECONDARY, payload={"command": "баланс"})
    vk.messages.send(
        peer_id=peer_id,
        message="Выберите игру:",
        keyboard=keyboard.get_keyboard(),
        random_id=random.randint(1, 1000)
    )

def handle_callback(event, player_data, vk):
    user_id = event.obj.user_id
    payload = event.obj.payload
    peer_id = event.obj.peer_id
    command = payload.get("command")
    action = payload.get("action")
    tag = format_user_tag(user_id, player_data.get(str(user_id), {}))
    
    if command == "transfer_confirm":
        # Получаем candidate_id для подтверждения перевода из сессии переводов
        candidate = transfer_sessions.get(str(user_id), {}).get("candidate_id")
        process_transfer_confirmation(event, player_data, vk, peer_id, user_id, action)
        answer_callback(vk, event, "Перевод подтверждён" if action == "confirm" else "Перевод отменён")
    elif command == "get_glitch":
        farm_clicks(user_id, player_data, vk, peer_id)
        answer_callback(vk, event, f"{tag} Вы получили Glitch⚡!")
    elif command == "баланс":
        show_balance(user_id, player_data, vk, peer_id)
        answer_callback(vk, event, f"{tag} Ваш баланс!")
    elif command == "профиль":
        show_profile(user_id, player_data, vk, peer_id)
        answer_callback(vk, event, f"{tag} Ваш профиль!")
    elif command == "топ балансов":
        show_top_balances(user_id, player_data, vk, peer_id)
        answer_callback(vk, event, f"{tag} Топ балансов!")
    elif command == "топ майнеров":
        show_top_miners(user_id, player_data, vk, peer_id)
        answer_callback(vk, event, f"{tag} Топ майнеров!")
    elif command == "change_name":
        awaiting_name_change[str(user_id)] = True
        vk.messages.send(
            peer_id=peer_id,
            message=f"{tag}\nВведите новое имя или 'отмена' для отказа.",
            random_id=random.randint(1, 1000)
        )
        answer_callback(vk, event, "Смена имени")
    elif command == "coinflip":
        awaiting_bet[str(user_id)] = "coinflip"
        vk.messages.send(
            peer_id=peer_id,
            message=f"{tag}\nВведите вашу ставку для 'Орел-Решка':",
            random_id=random.randint(1, 1000)
        )
        answer_callback(vk, event, "Ставка для Орел-Решка")
    elif command == "coinflip_choice":
        choice = payload.get("choice")
        if choice:
            process_coinflip_choice(user_id, choice, player_data, vk, peer_id)
        answer_callback(vk, event, "Выбор принят")
    elif command == "mines":
        awaiting_bet[str(user_id)] = "mines"
        vk.messages.send(
            peer_id=peer_id,
            message=f"{tag}\nВведите вашу ставку для игры 'Мины':",
            random_id=random.randint(1, 1000)
        )
        answer_callback(vk, event, "Ставка для Мины")
    elif command == "mines_field":
        size = payload.get("size")
        from games.mines import process_mines_field
        process_mines_field(event, user_id, size, player_data, vk, peer_id)
    elif command == "mines_option":
        option = payload.get("option")
        from games.mines import process_mines_option
        process_mines_option(event, user_id, option, player_data, vk, peer_id)
    elif command == "mines_move":
        from games.mines import handle_mines_move
        handle_mines_move(event, user_id, player_data, vk, peer_id)
    elif command == "join_chat":
        link = payload.get("link", CONFIG.get("CHAT_LINK", ""))
        vk.messages.send(
            peer_id=peer_id,
            message=f"Присоединяйтесь к игровому чату по ссылке:\n{link}",
            random_id=random.randint(1, 1000)
        )
        answer_callback(vk, event, "Чат открыт")
    elif command == "transfer":
        initiate_transfer(user_id, event, vk)
        answer_callback(vk, event, "Перевод запущен")