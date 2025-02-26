import hashlib
import random
import string

def generate_result():
    result = "heads" if random.randint(0, 1) == 0 else "tails"
    result_hash = hashlib.md5(result.encode()).hexdigest()
    return result, result_hash

def generate_mines_grid(size=6, mines=2):
    grid = [['0' for _ in range(size)] for _ in range(size)]
    mine_positions = random.sample(range(size * size), mines)
    for pos in mine_positions:
        row, col = divmod(pos, size)
        grid[row][col] = 'M'
        for r in range(max(0, row-1), min(size, row+2)):
            for c in range(max(0, col-1), min(size, col+2)):
                if grid[r][c] != 'M':
                    grid[r][c] = str(int(grid[r][c]) + 1)
    grid_str = ''.join([''.join(row) for row in grid])
    grid_hash = hashlib.md5(grid_str.encode()).hexdigest()
    return grid, grid_hash

def generate_random_string(length=16):
    letters_and_digits = string.ascii_letters + string.digits
    return ''.join(random.choice(letters_and_digits) for _ in range(length))

def format_user_tag(user_id, user_data):
    # Если у пользователя есть ник, используем его, иначе используем "Пользователь {id}"
    nickname = user_data.get("nickname", f"Пользователь {user_id}")
    return f"[vk.com/id{user_id}|{nickname}]"