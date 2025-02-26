import json
import logging

# Файл дублирующей базы данных
SECONDARY_DATA_FILE = "secondary_player_data.json"

def load_secondary_data():
    try:
        with open(SECONDARY_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Ошибка чтения файла дублирующих данных: Файл не найден.")
        return {}
    except json.JSONDecodeError as e_json:
        logging.error(f"Ошибка декодирования JSON: {e_json}")
        return {}

def save_secondary_data(data):
    with open(SECONDARY_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def update_secondary_data(user_id, data):
    secondary_data = load_secondary_data()
    secondary_data[str(user_id)] = {
        "vk_id": data.get("vk_id"),
        "nickname": data.get("nickname"),
        "balance": data.get("balance"),
        "clicked_balance": data.get("clicked_balance"),
        "won_balance": data.get("won_balance"),
        "transferred_amount": data.get("transferred_amount"),
        "total_balance": data.get("total_balance"),
        "clicks": data.get("clicks")  # Добавляем количество кликов
    }
    save_secondary_data(secondary_data)