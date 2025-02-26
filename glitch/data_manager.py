import json
import logging
from datetime import datetime
from secondary_data_manager import update_secondary_data

# Файлы баз данных
PLAYER_DATA_FILE = "player_data.json"
GAMES_FILE = "games.json"
TOP_DATA_FILE = "data.json"

def load_player_data():
    try:
        with open(PLAYER_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Инициализация отсутствующих ключей для всех пользователей
            for user_id, user_data in data.items():
                user_data.setdefault("vk_id", user_id)
                user_data.setdefault("nickname", f"Пользователь {user_id}")
                user_data.setdefault("balance", 0)
                user_data.setdefault("clicked_balance", 0)
                user_data.setdefault("won_balance", 0)
                user_data.setdefault("transferred_amount", 0)
                user_data.setdefault("total_balance", 0)
                user_data.setdefault("start_date", str(datetime.now().date()))
                user_data.setdefault("clicks", 0)  # Добавляем количество кликов
            return data
    except (UnicodeDecodeError, FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Ошибка чтения файла данных: {e}")
        return {}

def save_player_data(data):
    with open(PLAYER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_vk_name(user_id, vk):
    """
    Получает имя пользователя из ВКонтакте.
    """
    try:
        response = vk.users.get(user_ids=user_id)
        if response and isinstance(response, list) and response[0].get("first_name"):
            return f"{response[0]['first_name']} {response[0]['last_name']}"
    except Exception as e:
        logging.error(f"Ошибка при получении имени пользователя {user_id} из ВК: {e}")
    return f"Пользователь {user_id}"

def add_user(user_id, data, vk):
    if str(user_id) not in data:
        vk_name = get_vk_name(user_id, vk)
        user_info = {
            "vk_id": user_id,
            "nickname": vk_name,
            "balance": 0,
            "clicked_balance": 0,
            "won_balance": 0,
            "transferred_amount": 0,
            "total_balance": 0,
            "start_date": str(datetime.now().date()),
            "clicks": 0  # Добавляем количество кликов
        }
        data[str(user_id)] = user_info
        save_player_data(data)
        update_secondary_data(user_id, user_info)

def update_user_name(user_id, new_name, data):
    if str(user_id) in data:
        data[str(user_id)]["nickname"] = new_name
        save_player_data(data)
        update_secondary_data(user_id, data[str(user_id)])

def add_click_to_data(user_id, amount, data):
    if str(user_id) in data:
        data[str(user_id)]["clicked_balance"] += amount
        data[str(user_id)]["balance"] += amount
        data[str(user_id)]["total_balance"] += amount
        data[str(user_id)]["clicks"] += 1  # Увеличиваем количество кликов
        save_player_data(data)
        update_secondary_data(user_id, data[str(user_id)])

def add_winning_to_data(user_id, amount, data):
    if str(user_id) in data:
        data[str(user_id)]["won_balance"] += amount
        data[str(user_id)]["balance"] += amount
        data[str(user_id)]["total_balance"] += amount
        save_player_data(data)
        update_secondary_data(user_id, data[str(user_id)])

def add_transfer_to_data(user_id, amount, data):
    if str(user_id) in data:
        data[str(user_id)]["transferred_amount"] += amount
        save_player_data(data)
        update_secondary_data(user_id, data[str(user_id)])

def auto_adjust_balance(user_id, data):
    if str(user_id) in data:
        data[str(user_id)]["balance"] = int(data[str(user_id)]["balance"])
        save_player_data(data)
        update_secondary_data(user_id, data[str(user_id)])

def load_games():
    try:
        with open(GAMES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Ошибка чтения файла игр: Файл не найден. Создание нового файла.")
        save_games({})
        return {}
    except json.JSONDecodeError as e_json:
        logging.error(f"Ошибка декодирования JSON: {e_json}")
        return {}

def save_games(games):
    with open(GAMES_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, indent=4, ensure_ascii=False)

def add_game(game_info):
    games = load_games()
    games[str(game_info["user_id"])] = game_info
    save_games(games)

def remove_game(user_id):
    games = load_games()
    key = str(user_id)
    if key in games:
        del games[key]
    save_games(games)

def load_top_data():
    try:
        with open(TOP_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Ошибка чтения файла топ данных: {e}")
        return {"top_balances": {}, "top_miners": {}}

def save_top_data(top_data):
    with open(TOP_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(top_data, f, indent=4, ensure_ascii=False)

def get_user_nickname(user_id, vk):
    """
    Возвращает никнейм пользователя.
    Если никнейм не установлен, возвращает имя пользователя из ВК.
    """
    player_data = load_player_data()
    user_id_str = str(user_id)
    if user_id_str in player_data:
        return player_data[user_id_str].get("nickname", f"Player {user_id}")
    else:
        # Если пользователя нет в базе данных, пытаемся получить имя из ВК
        return get_vk_name(user_id, vk)