import re
import json
import random
import logging
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from data_manager import save_player_data, load_player_data, add_user, get_user_nickname

# Глобальный словарь для отслеживания сессий перевода
transfer_sessions = {}

def lookup_vk_user(username, vk):
    """
    Пытается получить ID пользователя по его юзернейму через VK API.
    Если найдено, возвращает строковый ID и никнейм, иначе None.
    """
    try:
        logging.debug(f"Ищем VK пользователя по юзернейму: {username}")
        response = vk.users.get(user_ids=username, fields="screen_name")
        if response and isinstance(response, list) and response[0].get("id"):
            user_id = str(response[0]["id"])
            screen_name = response[0].get("screen_name", username)
            logging.debug(f"Найден пользователь: {username} с id={user_id}")
            return user_id, screen_name
        else:
            logging.debug(f"Пользователь с юзернеймом {username} не найден.")
    except Exception as e:
        logging.error(f"Ошибка при поиске пользователя по юзернейму {username}: {e}")
    return None, None

def parse_recipient(text, event, sender_id, vk):
    """
    Определяет ID получателя по тексту сообщения или через пересланное/ответное сообщение.
    Сначала проверяются поля fwd_messages и reply_message.
    Затем производится поиск по шаблонам:
      vk.com/id12345, /id12345, @id12345, @username, vk.com/username, https://vk.com/username.
    Если найдено числовое значение, оно считается id, если буквенное – ищем через VK API.
    Если полученный id совпадает с sender_id, возвращается None.
    """
    message = event.obj.message or {}
    
    # Проверка пересланного сообщения
    fwd_msgs = message.get("fwd_messages", [])
    if fwd_msgs:
        recipient_id = fwd_msgs[0].get("from_id")
        if recipient_id and str(recipient_id) != str(sender_id):
            logging.debug(f"Получатель определен по пересланному сообщению: {recipient_id}")
            return str(recipient_id), f"vk.com/id{recipient_id}"
    # Проверка ответного сообщения
    reply = message.get("reply_message")
    if reply:
        recipient_id = reply.get("from_id")
        if recipient_id and str(recipient_id) != str(sender_id):
            logging.debug(f"Получатель определен по ответу на сообщение: {recipient_id}")
            return str(recipient_id), f"vk.com/id{recipient_id}"
    
    # Поиск по тексту
    logging.debug(f"Попытка определить получателя из текста: '{text}'")
    patterns = [
        r"vk\.com/id(\d+)",           # vk.com/id12345
        r"/id(\d+)",                  # /id12345
        r"\bid(\d+)\b",               # standalone id12345
        r"@id(\d+)",                  # @id12345
        r"@([A-Za-z_]+\w*)",          # @username (с буквами, цифрами и символами _)
        r"vk\.com/([A-Za-z_]+\w*)",    # vk.com/username
        r"https?://vk\.com/([A-Za-z_]+\w*)"  # https://vk.com/username
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            candidate = match.group(1)
            logging.debug(f"Найден кандидат '{candidate}' по шаблону '{pattern}'")
            if candidate.isdigit():
                if candidate != str(sender_id):
                    logging.debug(f"Кандидат '{candidate}' интерпретирован как id.")
                    return candidate, f"vk.com/id{candidate}"
            else:
                # Если найден не цифровой юзернейм, ищем его ID через VK API
                user_id, screen_name = lookup_vk_user(candidate, vk)
                if user_id and user_id != str(sender_id):
                    return user_id, screen_name
    return None, None

def initiate_transfer(sender_id, event, vk):
    """
    Инициирует сессию перевода.
    Если в event.obj.message присутствует reply_message, получатель определяется сразу,
    и сессия переходит на этап ввода суммы.
    Если в тексте присутствует сумма, устанавливается соответствующий этап.
    Иначе запрашивается ввод получателя.
    """
    message = event.obj.message or {}
    transfer_sessions[str(sender_id)] = {"stage": "recipient", "sender_id": str(sender_id)}
    reply = message.get("reply_message")
    text = message.get("text", "")
    
    sum_in_text = None
    for part in text.split():
        try:
            sum_in_text = int(part)
            break
        except:
            continue

    peer_id = message.get("peer_id") or sender_id
    if reply and reply.get("from_id"):
        if str(reply.get("from_id")) == str(sender_id):
            vk.messages.send(
                peer_id=peer_id,
                message="Нельзя переводить самому себе.",
                random_id=random.randint(1, 1000)
            )
            del transfer_sessions[str(sender_id)]
            return
        transfer_sessions[str(sender_id)]["recipient"] = str(reply.get("from_id"))
        transfer_sessions[str(sender_id)]["recipient_name"] = get_user_nickname(reply.get("from_id"), vk)
        if sum_in_text is not None:
            transfer_sessions[str(sender_id)]["amount"] = sum_in_text
            transfer_sessions[str(sender_id)]["stage"] = "confirm"
            send_transfer_confirmation(sender_id, vk, peer_id)
        else:
            transfer_sessions[str(sender_id)]["stage"] = "amount"
            vk.messages.send(
                peer_id=peer_id,
                message="Введите сумму Glitch для перевода:",
                random_id=random.randint(1, 1000)
            )
    else:
        recipient, recipient_name = parse_recipient(text, event, sender_id, vk)
        if recipient:
            transfer_sessions[str(sender_id)]["recipient"] = recipient
            transfer_sessions[str(sender_id)]["recipient_name"] = get_user_nickname(recipient, vk)
            if sum_in_text is not None:
                transfer_sessions[str(sender_id)]["amount"] = sum_in_text
                transfer_sessions[str(sender_id)]["stage"] = "confirm"
                send_transfer_confirmation(sender_id, vk, peer_id)
            else:
                transfer_sessions[str(sender_id)]["stage"] = "amount"
                vk.messages.send(
                    peer_id=peer_id,
                    message="Введите сумму Glitch для перевода:",
                    random_id=random.randint(1, 1000)
                )
        else:
            vk.messages.send(
                peer_id=peer_id,
                message="Введите ссылку или тег игрока, которому нужно перевести Glitch. Либо ответьте на сообщение этого игрока.",
                random_id=random.randint(1, 1000)
            )

def send_transfer_confirmation(sender_id, vk, peer_id):
    """
    Отправляет сообщение с подтверждением перевода.
    Отправляется inline-клавиатура с кнопками подтверждения/отмены.
    Уведомление получателю отправляется только после успешного подтверждения перевода.
    """
    session = transfer_sessions.get(str(sender_id))
    if not session:
        return
    amount = session.get("amount")
    recipient = session.get("recipient")
    recipient_name = session.get("recipient_name")
    sender_nickname = get_user_nickname(sender_id, vk)
    recipient_nickname = get_user_nickname(recipient, vk)
    keyboard = VkKeyboard(inline=True)
    keyboard.add_callback_button("Подтвердить", color=VkKeyboardColor.POSITIVE,
                                 payload={"command": "transfer_confirm", "action": "confirm"})
    keyboard.add_callback_button("Отменить", color=VkKeyboardColor.NEGATIVE,
                                 payload={"command": "transfer_confirm", "action": "cancel"})
    confirmation_msg = (f"Подтвердите перевод: вы [vk.com/id{sender_id}|{sender_nickname}] хотите отправить {amount} Glitch игроку [vk.com/id{recipient}|{recipient_nickname}].")
    vk.messages.send(
        peer_id=peer_id,
        message=confirmation_msg,
        keyboard=keyboard.get_keyboard(),
        random_id=random.randint(1, 1000)
    )

def process_transfer(bot_event, sender_id, text, player_data, vk):
    """
    Обрабатывает входящее сообщение для перевода:
      1. На этапе "recipient" – пытается определить получателя из текста (если reply отсутствует).
      2. На этапе "amount" – проверяет корректность введенной суммы и переходит к подтверждению.
    Возвращает True, если сообщение обработано сессией перевода.
    """
    session = transfer_sessions.get(str(sender_id))
    if not session:
        return False
    stage = session.get("stage")
    peer_id = None
    if hasattr(bot_event.obj, "message") and bot_event.obj.message:
        peer_id = bot_event.obj.message.get("peer_id")
    else:
        peer_id = getattr(bot_event.obj, "peer_id", None)
    if not peer_id:
        peer_id = sender_id

    if stage == "recipient":
        recipient, recipient_name = parse_recipient(text, bot_event, sender_id, vk)
        if not recipient:
            vk.messages.send(
                peer_id=peer_id,
                message="Не удалось определить получателя. Укажите ссылку/тег или ответьте на сообщение игрока.",
                random_id=random.randint(1, 1000)
            )
            return True
        session["recipient"] = recipient
        session["recipient_name"] = recipient_name
        session["stage"] = "amount"
        vk.messages.send(
            peer_id=peer_id,
            message="Введите сумму Glitch для перевода:",
            random_id=random.randint(1, 1000)
        )
        return True
    elif stage == "amount":
        try:
            amount = int(text)
            if amount <= 0:
                raise ValueError()
        except ValueError:
            vk.messages.send(
                peer_id=peer_id,
                message="Введите корректное число для суммы перевода.",
                random_id=random.randint(1, 1000)
            )
            return True
        sender_balance = int(player_data.get(str(sender_id), {}).get("balance", 0))
        if sender_balance < amount:
            vk.messages.send(
                peer_id=peer_id,
                message="Недостаточно средств для перевода.",
                random_id=random.randint(1, 1000)
            )
            del transfer_sessions[str(sender_id)]
            return True
        session["amount"] = amount
        session["stage"] = "confirm"
        send_transfer_confirmation(sender_id, vk, peer_id)
        return True
    return False

def process_transfer_confirmation(event, player_data, vk, peer_id, sender_id, action):
    """
    Обрабатывает callback подтверждения перевода.
    Если подтверждено, списывает средства у отправителя, добавляет их получателю и отправляет уведомление.
    При отмене – завершает сессию перевода.
    """
    session = transfer_sessions.get(str(sender_id))
    if not session or session.get("stage") != "confirm":
        vk.messages.send(
            peer_id=peer_id,
            message="Сессия перевода не найдена или уже завершена.",
            random_id=random.randint(1, 1000)
        )
        return

    if action == "cancel":
        vk.messages.send(
            peer_id=peer_id,
            message="Перевод отменён.",
            random_id=random.randint(1, 1000)
        )
        del transfer_sessions[str(sender_id)]
        return

    if action == "confirm":
        amount = session.get("amount")
        recipient = session.get("recipient")
        recipient_name = session.get("recipient_name")
        sender_balance = int(player_data.get(str(sender_id), {}).get("balance", 0))
        if sender_balance < amount:
            vk.messages.send(
                peer_id=peer_id,
                message="Недостаточно средств для перевода.",
                random_id=random.randint(1, 1000)
            )
            del transfer_sessions[str(sender_id)]
            return
        # Списание средств у отправителя и зачисление получателю
        player_data[str(sender_id)]["balance"] -= amount
        if recipient.isdigit():
            recipient_id = recipient
        else:
            recipient_id = str(player_data.get(recipient, {}).get("vk_id"))
        if recipient_id not in player_data:
            add_user(recipient_id, player_data, vk_name=f"Пользователь {recipient_id}")
        player_data[recipient_id]["balance"] += amount
        save_player_data(player_data)
        sender_nickname = get_user_nickname(sender_id, vk)
        recipient_nickname = get_user_nickname(recipient_id, vk)
        vk.messages.send(
            peer_id=peer_id,
            message=(f"Перевод между [vk.com/id{sender_id}|{sender_nickname}] и [vk.com/id{recipient_id}|{recipient_nickname}] выполнен успешно! С вашего счета списано {amount} Glitch. Новый баланс: {player_data[str(sender_id)]['balance']} Glitch."),
            random_id=random.randint(1, 1000)
        )
        vk.messages.send(
            peer_id=int(recipient_id),
            message=f"Вам переведен {amount} Glitch от [vk.com/id{sender_id}|{sender_nickname}].",
            random_id=random.randint(1, 1000)
        )
        del transfer_sessions[str(sender_id)]
        return