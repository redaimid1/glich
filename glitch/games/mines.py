import json
import random
import logging
import hashlib
import string
import math
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from data_manager import save_player_data
from mines_visual import generate_field_image
from vk_api import VkUpload

# Константы для состояний ячеек
MINE = "\u041c"  # Кириллическая "М"
SAFE = "0"

# Глобальный словарь для активных сессий игры "Мины"
mines_sessions = {}

# Фиксированные настройки поля: размер 5x5
BOARD_SIZE = 5
TOTAL_CELLS = BOARD_SIZE * BOARD_SIZE
COEFF_FILE = "coefficients.json"

def load_coefficients():
    try:
        with open(COEFF_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Возвращаем коэффициенты для поля 5x5
        return data.get("5", {})
    except Exception as e:
        logging.error(f"Ошибка загрузки коэффициентов: {e}")
        return {
            "default": [1.0, 1.25, 1.50, 1.75, 2.00, 2.25, 2.50],
            "custom": {}
        }

COEFFICIENTS = load_coefficients()

def build_grid_plain_with_random(grid_plain):
    """
    Формирует расширенное строковое представление поля.
    К исходной строке (где безопасная ячейка = '0', а мина = MINE)
    добавляется символ '|' и 10 случайных букво-цифровых символов.
    Пример: "0000М00000М0000|jCNUIjnjnHUun"
    """
    random_chars = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    return f"{grid_plain}|{random_chars}"

def encrypt_hash(plain_text):
    """
    Шифрует переданную строку с помощью MD5 и возвращает хеш в шестнадцатеричном виде.
    """
    return hashlib.md5(plain_text.encode("utf-8")).hexdigest()

def send_field_image(peer_id, vk, board_state, game_over=False, keyboard=None, message_text="Обновлённое игровое поле:"):
    """
    Генерирует изображение игрового поля с помощью generate_field_image,
    выгружает его на VK, и отправляет сообщение с прикрепленным изображением.
    Если передан параметр keyboard, то кнопки отображаются в том же сообщении.
    
    Параметры:
      - board_state: словарь состояний ячеек.
      - game_over: если True, поле считается раскрытым.
      - keyboard: объект VkKeyboard (или None).
      - message_text: текст сообщения.
    """
    image_path = generate_field_image(board_state, board_size=BOARD_SIZE, game_over=game_over)
    upload = VkUpload(vk)
    photo = upload.photo_messages(image_path)[0]
    attachment = f"photo{photo['owner_id']}_{photo['id']}"
    vk.messages.send(
        peer_id=peer_id,
        message=message_text,
        attachment=attachment,
        keyboard=keyboard.get_keyboard() if keyboard else None,
        random_id=random.randint(1, 1000)
    )

def build_final_board_state(grid, chosen_cells, board_size):
    """
    Формирует итоговое состояние поля для финального раскрытия.
    Для каждой ячейки:
      - Если в клетке находится мина: статус "bomb"
      - Если клетка безопасна и была выбрана: статус "press"
      - Иначе: статус "empty"
    """
    state = {}
    cell = 1
    for i in range(board_size):
        for j in range(board_size):
            if grid[i][j] == MINE:
                state[cell] = "bomb"
            else:
                if cell in chosen_cells:
                    state[cell] = "press"
                else:
                    state[cell] = "empty"
            cell += 1
    return state

def start_mines(user_id, stake, player_data, vk, peer_id):
    # Проверяем, что ставка не меньше 1
    if stake < 1:
        vk.messages.send(
            peer_id=peer_id,
            message="Ставка должна быть не меньше 1.",
            random_id=random.randint(1, 1000)
        )
        return

    # Проверяем баланс игрока
    current_balance = int(player_data.get(str(user_id), {}).get("balance", 0))
    if current_balance < stake:
        vk.messages.send(
            peer_id=peer_id,
            message="Недостаточно средств для игры 'Мины'.",
            random_id=random.randint(1, 1000)
        )
        return

    logging.debug(f"start_mines: пользователь {user_id} начинает игру 'Мины' со ставкой {stake}.")
    player_data[str(user_id)]["balance"] -= stake
    logging.debug(f"start_mines: новый баланс пользователя {user_id}: {player_data[str(user_id)]['balance']}")

    # Поле фиксированное 5x5, сразу запрашиваем количество мин.
    mines_sessions[str(user_id)] = {
        "stake": stake,
        "state": "choose_mine_count",
        "board_size": BOARD_SIZE
    }
    vk.messages.send(
        peer_id=peer_id,
        message=(f"Ставка {stake} принята. Игра проводится на поле {BOARD_SIZE}x{BOARD_SIZE}.\n"
                 f"Введите количество мин (от 1 до {TOTAL_CELLS - 1}):"),
        random_id=random.randint(1, 1000)
    )
    logging.debug(f"start_mines: сессия для пользователя {user_id} -> {mines_sessions[str(user_id)]}")

def process_mines_field(event, user_id, size, player_data, vk, peer_id):
    """
    Функция для выбора размера поля (для совместимости).
    Поскольку поле фиксированное 5x5, данная функция не используется для логики игры.
    """
    try:
        size = int(size)
    except ValueError:
        vk.messages.send(
            peer_id=peer_id,
            message="Ошибка: неверный размер поля.",
            random_id=random.randint(1, 1000)
        )
        return
    vk.messages.sendMessageEventAnswer(
        event_id=event.obj.event_id,
        user_id=user_id,
        peer_id=peer_id,
        event_data=json.dumps({"type": "show_snackbar", "text": f"Размер {size}x{size} выбран."})
    )
    session = mines_sessions.get(str(user_id))
    if not session or session.get("state") != "choose_field":
        vk.messages.send(
            peer_id=peer_id,
            message="Сессия игры не найдена. Начните игру заново.",
            random_id=random.randint(1, 1000)
        )
        logging.error(f"process_mines_field: сессия не найдена или неправильное состояние для пользователя {user_id}")
        return

    session["board_size"] = size
    session["state"] = "choose_option"
    logging.debug(f"process_mines_field: обновлена сессия для пользователя {user_id}: {session}")

    keyboard = VkKeyboard(inline=True)
    keyboard.add_callback_button("Начать с 2 минами", color=VkKeyboardColor.PRIMARY,
                                 payload={"command": "mines_option", "option": "default"})
    keyboard.add_callback_button("Выбрать количество мин", color=VkKeyboardColor.SECONDARY,
                                 payload={"command": "mines_option", "option": "custom"})
    vk.messages.send(
        peer_id=peer_id,
        message=f"Вы выбрали поле {size}x{size}. Выберите опцию:",
        keyboard=keyboard.get_keyboard(),
        random_id=random.randint(1, 1000)
    )

def process_mines_option(event, user_id, option, player_data, vk, peer_id):
    logging.debug(f"process_mines_option: пользователь {user_id} выбрал опцию {option}")
    vk.messages.sendMessageEventAnswer(
        event_id=event.obj.event_id,
        user_id=user_id,
        peer_id=peer_id,
        event_data=json.dumps({"type": "show_snackbar", "text": "Опция выбрана."})
    )
    session = mines_sessions.get(str(user_id))
    if not session or session.get("state") not in ["choose_option", "choose_mine_count"]:
        vk.messages.send(
            peer_id=peer_id,
            message="Сессия игры не найдена. Начните игру заново.",
            random_id=random.randint(1, 1000)
        )
        logging.error(f"process_mines_option: сессия не найдена или неправильное состояние для пользователя {user_id}")
        return
    board_size = session.get("board_size", BOARD_SIZE)
    total_cells = board_size * board_size
    if option == "default":
        mine_count = 2
        if total_cells - mine_count < 1:
            vk.messages.send(
                peer_id=peer_id,
                message="Невозможно разместить столько мин на поле.",
                random_id=random.randint(1, 1000)
            )
            logging.error(f"process_mines_option: недопустимое количество мин для поля {board_size}x{board_size}")
            return
        session["mine_count"] = mine_count
        session["state"] = "choose_cell"
        session["safe_moves"] = 0
        session["coef"] = 1.0
        session["chosen_cells"] = []
        grid, grid_plain = generate_mines_grid(board_size, mine_count)
        grid_plain_ext = build_grid_plain_with_random(grid_plain)
        encrypted_hash = encrypt_hash(grid_plain_ext)
        session["grid"] = grid
        session["grid_hash"] = encrypted_hash
        session["grid_plain"] = grid_plain_ext
        # Начальное состояние поля: все ячейки "empty"
        board_state = {cell: "empty" for cell in range(1, total_cells + 1)}
        # Отправляем сообщение с картинкой поля и хешем в одном сообщении
        initial_message = (f"Игра началась с {board_size}x{board_size} и {mine_count} минами.\n"
                           f"Хеш (MD5): {encrypted_hash}\n"
                           f"Введите номер ячейки (от 1 до {total_cells}):")
        send_field_image(peer_id, vk, board_state, message_text=initial_message)
    elif option == "custom":
        session["state"] = "choose_mine_count"
        vk.messages.send(
            peer_id=peer_id,
            message=f"Введите количество мин (от 1 до {total_cells - 1}):",
            random_id=random.randint(1, 1000)
        )
    else:
        vk.messages.send(
            peer_id=peer_id,
            message="Неверная опция.",
            random_id=random.randint(1, 1000)
        )
    logging.debug(f"process_mines_option: обновлена сессия для пользователя {user_id}: {session}")

def process_mines_text(user_id, text, player_data, vk, peer_id):
    logging.debug(f"process_mines_text: получен текст '{text}' от пользователя {user_id}")
    session = mines_sessions.get(str(user_id))
    if not session:
        logging.debug(f"process_mines_text: сессия не найдена для пользователя {user_id}")
        return False
    state = session.get("state")
    board_size = session.get("board_size", BOARD_SIZE)
    total_cells = board_size * board_size
    logging.debug(f"process_mines_text: состояние для пользователя {user_id} = {state}, поле: {board_size}x{board_size}")

    # Фаза: ввод количества мин
    if state == "choose_mine_count":
        try:
            mine_count = int(text)
        except ValueError:
            vk.messages.send(
                peer_id=peer_id,
                message="Введите корректное число для количества мин.",
                random_id=random.randint(1, 1000)
            )
            return True
        if mine_count < 1 or mine_count >= total_cells:
            vk.messages.send(
                peer_id=peer_id,
                message=f"Количество мин должно быть от 1 до {total_cells - 1}.",
                random_id=random.randint(1, 1000)
            )
            return True
        session["mine_count"] = mine_count
        session["state"] = "choose_cell"
        session["safe_moves"] = 0
        session["coef"] = 1.0
        session["chosen_cells"] = []
        grid, grid_plain = generate_mines_grid(board_size, mine_count)
        grid_plain_ext = build_grid_plain_with_random(grid_plain)
        encrypted_hash = encrypt_hash(grid_plain_ext)
        session["grid"] = grid
        session["grid_hash"] = encrypted_hash
        session["grid_plain"] = grid_plain_ext
        board_state = {cell: "empty" for cell in range(1, total_cells + 1)}
        send_field_image(peer_id, vk, board_state)
        vk.messages.send(
            peer_id=peer_id,
            message=(f"Игра началась на поле {board_size}x{board_size} с {mine_count} минами.\n"
                     f"Хеш (MD5): {encrypted_hash}\n"
                     f"Введите номер ячейки (от 1 до {total_cells}):"),
            random_id=random.randint(1, 1000)
        )
        return True

    # Фаза: выбор ячейки
    elif state == "choose_cell":
        if text.lower() == "забрать":
            coef = session.get("coef", 1.0)
            stake = session.get("stake")
            # Округляем выигрыш до целого числа (в меньшую сторону)
            win = math.floor(stake * coef)
            player_data[str(user_id)]["balance"] += win
            final_board_state = build_final_board_state(session["grid"], session.get("chosen_cells", []), board_size)
            send_field_image(peer_id, vk, final_board_state, game_over=True)
            vk.messages.send(
                peer_id=peer_id,
                message=(f"Поздравляем! Вы забрали выигрыш {win} Glitch⚡.\n"
                         f"Ваш баланс: {player_data[str(user_id)]['balance']} Glitch⚡.\n"
                         f"Хеш (MD5): {session.get('grid_hash')}\n"
                         f"Расшифровка: {session.get('grid_plain')}"),
                random_id=random.randint(1, 1000)
            )
            del mines_sessions[str(user_id)]
            return True
        else:
            try:
                cell_number = int(text)
                logging.debug(f"process_mines_text: распознано число ячейки {cell_number} для пользователя {user_id}")
            except ValueError:
                vk.messages.send(
                    peer_id=peer_id,
                    message="Введите корректный номер ячейки или 'забрать', чтобы завершить игру.",
                    random_id=random.randint(1, 1000)
                )
                return True
            if cell_number < 1 or cell_number > total_cells:
                vk.messages.send(
                    peer_id=peer_id,
                    message=f"Номер ячейки должен быть от 1 до {total_cells}.",
                    random_id=random.randint(1, 1000)
                )
                return True
            if cell_number in session.get("chosen_cells", []):
                vk.messages.send(
                    peer_id=peer_id,
                    message="Эта ячейка уже была выбрана. Выберите другую.",
                    random_id=random.randint(1, 1000)
                )
                return True
            row = (cell_number - 1) // board_size
            col = (cell_number - 1) % board_size
            grid = session.get("grid")
            if grid[row][col] == MINE:
                # Если игрок нажал на мину, формируем финальное состояние поля:
                # Все мины раскрыты, а для ячейки, в которую нажали, статус "explosion"
                board_state = build_final_board_state(session["grid"], session.get("chosen_cells", []), board_size)
                board_state[cell_number] = "explosion"
                send_field_image(peer_id, vk, board_state, game_over=True)
                vk.messages.send(
                    peer_id=peer_id,
                    message=(f"Вы проиграли! Вы попали на мину в ячейке {cell_number}.\n"
                             f"Хеш (MD5): {session.get('grid_hash')}\n"
                             f"Расшифровка: {session.get('grid_plain')}"),
                    random_id=random.randint(1, 1000)
                )
                del mines_sessions[str(user_id)]
                return True
            else:
                session["chosen_cells"].append(cell_number)
                session["safe_moves"] = session.get("safe_moves", 0) + 1
                mine_count = session.get("mine_count")
                coef = get_current_coefficient(mine_count, session["safe_moves"])
                session["coef"] = coef
                board_state = {cell: "empty" for cell in range(1, total_cells + 1)}
                for cell in session.get("chosen_cells", []):
                    board_state[cell] = "press"
                # Создаем клавиатуру с кнопкой "Забрать"
                keyboard = VkKeyboard(inline=True)
                keyboard.add_callback_button("Забрать", color=VkKeyboardColor.POSITIVE,
                                             payload={"command": "mines_move", "option": "take"})
                send_field_image(
                    peer_id, vk, board_state,
                    keyboard=keyboard,
                    message_text=(f"В ячейке {cell_number} мины нет.\n"
                                  f"Текущий коэффициент: {coef:.2f}\n"
                                  f"Хеш (MD5): {session.get('grid_hash')}\n"
                                  "Нажмите 'Забрать', чтобы забрать выигрыш.")
                )
                return True
    else:
        logging.debug(f"process_mines_text: необрабатываемое состояние {state} для пользователя {user_id}")
        return False

def handle_mines_move(event, user_id, player_data, vk, peer_id):
    """
    Обрабатывает callback, когда игрок нажимает кнопку "Забрать".
    """
    session = mines_sessions.get(str(user_id))
    if not session or session.get("state") != "choose_cell":
        vk.messages.send(
            peer_id=peer_id,
            message="Сессия игры не найдена. Начните игру заново.",
            random_id=random.randint(1, 1000)
        )
        return
    option = event.obj.payload.get("option")
    if option == "take":
        coef = session.get("coef", 1.0)
        stake = session.get("stake")
        # Округляем выигрыш до целого числа (в меньшую сторону)
        win = math.floor(stake * coef)
        player_data[str(user_id)]["balance"] += win
        total_cells = BOARD_SIZE * BOARD_SIZE
        board_state = build_final_board_state(session["grid"], session.get("chosen_cells", []), BOARD_SIZE)
        send_field_image(peer_id, vk, board_state, game_over=True)
        vk.messages.send(
            peer_id=peer_id,
            message=(f"Поздравляем! Вы забрали выигрыш {win} Glitch⚡.\n"
                     f"Ваш баланс: {player_data[str(user_id)]['balance']} Glitch⚡.\n"
                     f"Хеш (MD5): {session.get('grid_hash')}\n"
                     f"Расшифровка: {session.get('grid_plain')}"),
            random_id=random.randint(1, 1000)
        )
        del mines_sessions[str(user_id)]
    else:
        vk.messages.send(
            peer_id=peer_id,
            message="Неверный выбор. Попробуйте снова.",
            random_id=random.randint(1, 1000)
        )

def get_current_coefficient(mine_count, safe_moves):
    """
    Возвращает текущий коэффициент на основе количества безопасных ходов.
    Если для заданного числа мин есть свой список коэффициентов, используется он,
    иначе возвращается список по умолчанию.
    """
    if str(mine_count) in COEFFICIENTS.get("custom", {}):
        coeff_list = COEFFICIENTS["custom"][str(mine_count)]
    else:
        coeff_list = COEFFICIENTS.get("default", [1.0])
    index = safe_moves - 1
    if index < 0:
        index = 0
    if index >= len(coeff_list):
        index = len(coeff_list) - 1
    return coeff_list[index]

def generate_mines_grid(board_size, mine_count):
    """
    Генерирует игровое поле для "Мины" с заданным числом мин.
    Возвращает:
      - grid: двумерный список, представляющий поле;
      - grid_str: строковое представление поля, где безопасная ячейка = SAFE, а мина = MINE.
    """
    grid = [[SAFE for _ in range(board_size)] for _ in range(board_size)]
    placed = 0
    while placed < mine_count:
        r = random.randint(0, board_size - 1)
        c = random.randint(0, board_size - 1)
        if grid[r][c] != MINE:
            grid[r][c] = MINE
            placed += 1
    grid_str = ''.join([''.join(row) for row in grid])
    return grid, grid_str

def format_full_board(board_size, chosen_cells):
    """
    Форматирует текущее состояние поля для текстового отображения.
    Для каждой ячейки:
      - Если ячейка не выбрана, отображается как [номер]
      - Если ячейка выбрана (без мины), отображается как [✔]
    (Для обратной совместимости.)
    """
    lines = []
    cell = 1
    for _ in range(board_size):
        row = []
        for _ in range(board_size):
            if cell in chosen_cells:
                row.append("[✔]")
            else:
                row.append(f"[{cell}]")
            cell += 1
        lines.append(" ".join(row))
    return "\n".join(lines)

def reveal_board_on_loss(grid, chosen_cells, failed_cell):
    """
    Раскрывает поле при проигрыше.
    Для каждой ячейки:
      - Если в ячейке мина:
            * Если именно эта ячейка стала причиной проигрыша: [✖]
            * Иначе: [💣]
      - Если безопасная:
            * Если выбрана: [✔]
            * Если не выбрана: [0]
    (Для обратной совместимости.)
    """
    board_size = len(grid)
    lines = []
    cell = 1
    for i in range(board_size):
        row = []
        for j in range(board_size):
            if grid[i][j] == MINE:
                if cell == failed_cell:
                    row.append("[✖]")
                else:
                    row.append("[💣]")
            else:
                if cell in chosen_cells:
                    row.append("[✔]")
                else:
                    row.append("[0]")
            cell += 1
        lines.append(" ".join(row))
    return "\n".join(lines)

def reveal_board_on_complete(grid, chosen_cells):
    """
    Раскрывает поле при выигрыше.
    Для безопасных ячеек:
      - Если выбраны: [✔]
      - Иначе: [0]
    Для ячеек с минами всегда [💣]
    (Для обратной совместимости.)
    """
    board_size = len(grid)
    lines = []
    cell = 1
    for i in range(board_size):
        row = []
        for j in range(board_size):
            if grid[i][j] == MINE:
                row.append("[💣]")
            else:
                if cell in chosen_cells:
                    row.append("[✔]")
                else:
                    row.append("[0]")
            cell += 1
        lines.append(" ".join(row))
    return "\n".join(lines)

# Для обратной совместимости
process_mines_choice = process_mines_text