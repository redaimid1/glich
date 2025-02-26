from PIL import Image
import os

def generate_field_image(game_state, board_size=5, field_width=1440, field_height=1440, padding=10, images_path="images", output_path="updated_field.png", game_over=False):
    """
    Генерирует изображение игрового поля для игры "Мины".
    
    Параметры:
      game_state  — словарь, где ключ — номер ячейки (от 1 до board_size*board_size),
                    а значение — статус ячейки:
                      "press"      – ячейка нажата (без мины);
                      "explosion"  – ячейка с миной, на которую нажали;
                      "bomb"       – ячейка с миной, которую не нажали;
                      "empty"      – пустая ячейка.
      board_size  — число ячеек по строке/столбцу (например, 5 для поля 5x5).
      field_width — ширина поля в пикселях (1440 по умолчанию).
      field_height— высота поля в пикселях (1440 по умолчанию).
      padding     — отступ между ячейками.
      images_path — путь к папке с изображениями, где должны находиться:
                      field.png    – фон игрового поля;
                      press.png    – изображение для нажатой ячейки (без мины);
                      explosion.png– изображение для ячейки с миной, на которую нажали;
                      bomb.png     – изображение для не взорвавшейся мины;
                      empty.png    – изображение для безопасной (пустой) ячейки;
      output_path — путь для сохранения итогового изображения;
      game_over   — если True, для ячеек со статусом "empty" накладывается изображение empty.png, что позволяет полностью раскрыть поле.
    
    Возвращает:
      Путь к сгенерированному изображению.
    """
    # Определяем размер ячейки так, чтобы с учетом отступов заполнить поле заданного размера
    cell_size = int((field_width - (board_size + 1) * padding) / board_size)
    
    # Загружаем фон и изменяем его размер
    field_path = os.path.join(images_path, "field.png")
    field_img = Image.open(field_path).convert("RGBA")
    field_img = field_img.resize((field_width, field_height))
    
    # Загружаем изображения ячеек и меняем их размер, конвертируя в RGBA
    press_img = Image.open(os.path.join(images_path, "press.png")).convert("RGBA").resize((cell_size, cell_size))
    explosion_img = Image.open(os.path.join(images_path, "explosion.png")).convert("RGBA").resize((cell_size, cell_size))
    bomb_img = Image.open(os.path.join(images_path, "bomb.png")).convert("RGBA").resize((cell_size, cell_size))
    empty_img = Image.open(os.path.join(images_path, "empty.png")).convert("RGBA").resize((cell_size, cell_size))
    
    # Генерируем координаты для каждой ячейки
    cell_positions = {}
    for row in range(board_size):
        for col in range(board_size):
            cell_number = row * board_size + col + 1
            x = col * (cell_size + padding) + padding
            y = row * (cell_size + padding) + padding
            cell_positions[cell_number] = (x, y)
            
    updated_field = field_img.copy()
    
    for cell in range(1, board_size * board_size + 1):
        x, y = cell_positions[cell]
        status = game_state.get(cell, "empty")
        if status == "press":
            mask = press_img.split()[3]
            updated_field.paste(press_img, (x, y), mask)
        elif status == "explosion":
            mask = explosion_img.split()[3]
            updated_field.paste(explosion_img, (x, y), mask)
        elif status == "bomb":
            mask = bomb_img.split()[3]
            updated_field.paste(bomb_img, (x, y), mask)
        elif status == "empty":
            # При завершении игры накладываем изображение пустой ячейки
            if game_over:
                mask = empty_img.split()[3]
                updated_field.paste(empty_img, (x, y), mask)
            # Если игра не завершена, для пустых ячеек оставляем фон без изменений.
    
    updated_field.save(output_path)
    return output_path

if __name__ == "__main__":
    # Пример финального состояния поля (раскрытое поле, game_over=True)
    game_state = {}
    board_size = 5
    # Допустим, ячейка 12 – взорванная (explosion), несколько мин скрыты (bomb), выбранные безопасные ячейки (press)
    for cell in range(1, board_size * board_size + 1):
        if cell == 12:
            game_state[cell] = "explosion"
        elif cell in [3, 8, 17]:
            game_state[cell] = "bomb"
        elif cell in [7, 11]:
            game_state[cell] = "press"
        else:
            game_state[cell] = "empty"
    print(generate_field_image(game_state, board_size=board_size, game_over=True))