import time
import logging
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from config import CONFIG
from data_manager import load_player_data
from handlers import handle_message, handle_callback

def main():
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    # Устанавливаем более строгий уровень для urllib3, чтобы не захламлять логи
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    vk_session = vk_api.VkApi(token=CONFIG["TOKEN"])
    vk = vk_session.get_api()
    player_data = load_player_data()

    longpoll = VkBotLongPoll(vk_session, CONFIG["GROUP_ID"])
    logger.debug("Бот запущен и ожидает сообщений...")

    while True:
        try:
            for event in longpoll.listen():
                if event.type == VkBotEventType.MESSAGE_NEW:
                    handle_message(event, player_data, vk)
                elif event.type == VkBotEventType.MESSAGE_EVENT:
                    handle_callback(event, player_data, vk)
        except Exception as e:
            logger.error(f"Ошибка в прослушивании событий: {e}", exc_info=True)
            time.sleep(3)  # Задержка перед повторной попыткой подключения

if __name__ == "__main__":
    main()