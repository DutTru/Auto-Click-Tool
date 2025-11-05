import pygame
import asyncio
import platform
import random
import pyautogui
import json
import time
import tkinter as tk
from tkinter import filedialog

# Khởi tạo Pygame
pygame.init()

# Kích thước "thế giới" chuẩn
WORLD_WIDTH, WORLD_HEIGHT = 1920, 1080

# Tạo cửa sổ toàn màn hình, không thanh tiêu đề
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.NOFRAME)
pygame.display.set_caption("AutoClick Program")
FPS = 60

# Màu sắc
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GRAY = (200, 200, 200)
GREEN = (0, 255, 0)


# Lớp Point để quản lý tọa độ
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y


# Danh sách các ô vuông và lịch sử
squares = []
history = []
dragging_point = None
dragging_square = None
selected_square_idx = None
input_mode = None
input_square_idx = None
input_text = ""
input_is_hotkey = False
slider_state = False
slider_rect = pygame.Rect(70, 70, 50, 30)
timer_seconds = 0
timer_running = False
timer_repeat = False
timer_rect = pygame.Rect(310, 70, 50, 30)
timer_slider_rect = pygame.Rect(310, 110, 50, 30)
last_update_time = time.time()
auto_click_triggered = False
original_timer_seconds = 0
countdown_square_idx = None
current_square_time = 0
running_coroutine = None

# Font chữ
font = pygame.font.SysFont("arial", 24)

# Tọa độ và kích thước nút chức năng
buttons = {
    "E": pygame.Rect(10, 10, 50, 50),
    "A": pygame.Rect(70, 10, 50, 50),
    "S": pygame.Rect(130, 10, 50, 50),
    "U": pygame.Rect(190, 10, 50, 50),
    "X": pygame.Rect(250, 10, 50, 50),
    "T": pygame.Rect(310, 10, 50, 50),
    "I": pygame.Rect(370, 10, 50, 50),
    "Start": pygame.Rect(WORLD_WIDTH - 160, 10, 70, 50),
    "Stop": pygame.Rect(WORLD_WIDTH - 80, 10, 70, 50),
}


# Hàm lưu trạng thái vào lịch sử
def save_state():
    state = json.loads(json.dumps([{
        "points": [[p.x, p.y] for p in square["points"]],
        "index": square["index"],
        "click_count": square["click_count"],
        "key": square["key"],
        "time_seconds": square["time_seconds"]
    } for square in squares]))
    history.append(state)
    if len(history) > 50:
        history.pop(0)


# Hàm hoàn tác (undo)
def undo():
    global selected_square_idx
    if history:
        prev_state = history.pop()
        global squares
        squares = []
        for square_data in prev_state:
            points = [Point(x, y) for x, y in square_data["points"]]
            squares.append({
                "points": points,
                "index": square_data["index"],
                "click_count": square_data["click_count"],
                "key": square_data["key"],
                "time_seconds": square_data["time_seconds"]
            })
        if selected_square_idx is not None and selected_square_idx >= len(squares):
            selected_square_idx = None


# Hàm thêm ô vuông mới tại vị trí chuột
def add_square():
    # Lấy vị trí chuột
    mouse_x, mouse_y = pygame.mouse.get_pos()
    # Chuyển sang không gian thế giới
    window_width, window_height = pygame.display.get_surface().get_size()
    scale_x = window_width / WORLD_WIDTH
    scale_y = window_height / WORLD_HEIGHT
    center_x = mouse_x / scale_x
    center_y = mouse_y / scale_y
    # Kích thước ô vuông
    size = 50
    half_size = size / 2
    # Giới hạn để ô vuông không vượt ra ngoài
    center_x = max(half_size, min(WORLD_WIDTH - half_size, center_x))
    center_y = max(half_size, min(WORLD_HEIGHT - half_size, center_y))
    # Tạo các điểm của ô vuông
    square_points = [
        Point(center_x - half_size, center_y - half_size),
        Point(center_x + half_size, center_y - half_size),
        Point(center_x + half_size, center_y + half_size),
        Point(center_x - half_size, center_y + half_size)
    ]
    # Tạo chỉ số N duy nhất
    used_indices = [square["index"] for square in squares]
    index = 1
    while index in used_indices:
        index += 1
    squares.append({
        "points": square_points,
        "index": index,
        "click_count": 0,
        "key": None,
        "time_seconds": 0
    })
    save_state()


# Hàm xóa ô vuông
def delete_square(pos, window_width, window_height):
    global selected_square_idx
    if selected_square_idx is not None and selected_square_idx < len(squares):
        save_state()
        squares.pop(selected_square_idx)
        selected_square_idx = None
    else:
        square_idx = find_nearest_square_center(pos, window_width, window_height)
        if square_idx is not None:
            save_state()
            squares.pop(square_idx)
            selected_square_idx = None


# Hàm kiểm tra click vào nút chức năng
def check_button_click(pos, window_width, window_height):
    scale_x = window_width / WORLD_WIDTH
    scale_y = window_height / WORLD_HEIGHT
    world_pos = (pos[0] / scale_x, pos[1] / scale_y)
    for key, rect in buttons.items():
        scaled_rect = pygame.Rect(rect.x * scale_x, rect.y * scale_y, rect.width * scale_x, rect.height * scale_y)
        if scaled_rect.collidepoint(pos):
            return key
    return None


# Hàm kiểm tra click vào thanh trượt A
def check_slider_click(pos, window_width, window_height):
    scale_x = window_width / WORLD_WIDTH
    scale_y = window_height / WORLD_HEIGHT
    scaled_slider_rect = pygame.Rect(slider_rect.x * scale_x, slider_rect.y * scale_y, slider_rect.width * scale_x,
                                     slider_rect.height * scale_y)
    return scaled_slider_rect.collidepoint(pos)


# Hàm kiểm tra click vào thanh trượt Timer
def check_timer_slider_click(pos, window_width, window_height):
    scale_x = window_width / WORLD_WIDTH
    scale_y = window_height / WORLD_HEIGHT
    scaled_timer_slider_rect = pygame.Rect(timer_slider_rect.x * scale_x, timer_slider_rect.y * scale_y,
                                           timer_slider_rect.width * scale_x, timer_slider_rect.height * scale_y)
    return scaled_timer_slider_rect.collidepoint(pos)


# Hàm kiểm tra click vào khung nhập liệu Timer
def check_timer_input_click(pos, window_width, window_height):
    scale_x = window_width / WORLD_WIDTH
    scale_y = window_height / WORLD_HEIGHT
    scaled_timer_rect = pygame.Rect(timer_rect.x * scale_x, timer_rect.y * scale_y, timer_rect.width * scale_x,
                                    timer_rect.height * scale_y)
    return scaled_timer_rect.collidepoint(pos)


# Hàm tìm điểm gần nhất
def find_nearest_point(pos, window_width, window_height):
    scale_x = window_width / WORLD_WIDTH
    scale_y = window_height / WORLD_HEIGHT
    world_pos = (pos[0] / scale_x, pos[1] / scale_y)
    for i, square in enumerate(squares):
        for j, point in enumerate(square["points"]):
            if ((world_pos[0] - point.x) ** 2 + (world_pos[1] - point.y) ** 2) ** 0.5 < 10:
                return i, j
    return None


# Hàm tìm ô vuông khi nhấp vào dấu "+"
def find_nearest_square_center(pos, window_width, window_height):
    scale_x = window_width / WORLD_WIDTH
    scale_y = window_height / WORLD_HEIGHT
    world_pos = (pos[0] / scale_x, pos[1] / scale_y)
    for i, square in enumerate(squares):
        center_x = sum(p.x for p in square["points"]) / 4
        center_y = sum(p.y for p in square["points"]) / 4
        if ((world_pos[0] - center_x) ** 2 + (world_pos[1] - center_y) ** 2) ** 0.5 < 10:
            return i
    return None


# Hàm kiểm tra click vào vùng N, A, L, T
def check_label_click(pos, window_width, window_height):
    scale_x = window_width / WORLD_WIDTH
    scale_y = window_height / WORLD_HEIGHT
    for i, square in enumerate(squares):
        min_x = min(p.x for p in square["points"])
        min_y = min(p.y for p in square["points"])
        n_rect = pygame.Rect((min_x - 60) * scale_x, (min_y - 80) * scale_y, 50 * scale_x, 50 * scale_y)
        a_rect = pygame.Rect((min_x - 60) * scale_x, (min_y - 120) * scale_y, 50 * scale_x, 50 * scale_y)
        l_rect = pygame.Rect(min_x * scale_x, (min_y - 80) * scale_y, 50 * scale_x, 50 * scale_y)
        t_rect = pygame.Rect(min_x * scale_x, (min_y - 120) * scale_y, 50 * scale_x, 50 * scale_y)
        if n_rect.collidepoint(pos):
            return i, "N"
        elif a_rect.collidepoint(pos):
            return i, "A"
        elif l_rect.collidepoint(pos):
            return i, "L"
        elif t_rect.collidepoint(pos):
            return i, "T"
    return None, None


# Hàm kiểm tra điểm có nằm trong đa giác
def point_in_polygon(x, y, polygon):
    n = len(polygon)
    inside = False
    px, py = x, y
    j = n - 1
    for i in range(n):
        if ((polygon[i].y > py) != (polygon[j].y > py)) and \
                (px < (polygon[j].x - polygon[i].x) * (py - polygon[i].y) / (polygon[j].y - polygon[i].y + 0.0001) +
                 polygon[i].x):
            inside = not inside
        j = i
    return inside


# Hàm tạo điểm ngẫu nhiên trong ô vuông
def random_point_in_square(square, window_width, window_height):
    points = square["points"]
    min_x = min(p.x for p in points)
    max_x = max(p.x for p in points)
    min_y = min(p.y for p in points)
    max_y = max(p.y for p in points)
    for _ in range(100):
        x = random.uniform(min_x, max_x)
        y = random.uniform(min_y, max_y)
        if point_in_polygon(x, y, points):
            return x * window_width / WORLD_WIDTH, y * window_height / WORLD_HEIGHT
    center_x = sum(p.x for p in points) / 4
    center_y = sum(p.y for p in points) / 4
    return center_x * window_width / WORLD_WIDTH, center_y * window_height / WORLD_HEIGHT


# Hàm lấy tâm ô vuông
def get_square_center(square, window_width, window_height):
    points = square["points"]
    center_x = sum(p.x for p in points) / 4
    center_y = sum(p.y for p in points) / 4
    return center_x * window_width / WORLD_WIDTH, center_y * window_height / WORLD_HEIGHT


# Hàm lưu dữ liệu vào file JSON
def save_data():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        title="Save AutoClick State"
    )
    root.destroy()
    if file_path:
        data = {
            "squares": [
                {
                    "points": [[p.x, p.y] for p in square["points"]],
                    "index": square["index"],
                    "click_count": square["click_count"],
                    "key": square["key"],
                    "time_seconds": square["time_seconds"]
                } for square in squares
            ],
            "timer_seconds": timer_seconds,
            "original_timer_seconds": original_timer_seconds,
            "timer_repeat": timer_repeat,
            "slider_state": slider_state
        }
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"Saved to {file_path}")
        except Exception as e:
            print(f"Error saving file: {e}")


# Hàm tải dữ liệu từ file JSON
def load_data():
    global squares, timer_seconds, original_timer_seconds, timer_repeat, slider_state, selected_square_idx
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        title="Load AutoClick State"
    )
    root.destroy()
    if file_path:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            squares = []
            for square_data in data.get("squares", []):
                points = [Point(x, y) for x, y in square_data["points"]]
                squares.append({
                    "points": points,
                    "index": square_data["index"],
                    "click_count": square_data["click_count"],
                    "key": square_data["key"],
                    "time_seconds": square_data.get("time_seconds", 0)
                })
            timer_seconds = data.get("timer_seconds", 0)
            original_timer_seconds = data.get("original_timer_seconds", 0)
            timer_repeat = data.get("timer_repeat", False)
            slider_state = data.get("slider_state", False)
            selected_square_idx = None
            save_state()
            print(f"Loaded from {file_path}")
        except Exception as e:
            print(f"Error loading file: {e}")


# Hàm vẽ giao diện
def draw(window_width, window_height):
    screen.fill(WHITE)
    scale_x = window_width / WORLD_WIDTH
    scale_y = window_height / WORLD_HEIGHT

    # Vẽ lưới như trang giấy
    grid_step = 20
    for x in range(0, WORLD_WIDTH, grid_step):
        scaled_x = x * scale_x
        pygame.draw.line(screen, GRAY, (scaled_x, 0), (scaled_x, window_height))
    for y in range(0, WORLD_HEIGHT, grid_step):
        scaled_y = y * scale_y
        pygame.draw.line(screen, GRAY, (0, scaled_y), (window_width, scaled_y))

    # Vẽ các ô vuông autoclick
    for i, square in enumerate(squares):
        points = [(p.x * scale_x, p.y * scale_y) for p in square["points"]]
        color = GREEN if i == selected_square_idx else BLUE
        pygame.draw.polygon(screen, color, points, 2)
        for point in square["points"]:
            pygame.draw.circle(screen, RED, (point.x * scale_x, point.y * scale_y), 5)

        center_x = sum(p.x for p in square["points"]) / 4 * scale_x
        center_y = sum(p.y for p in square["points"]) / 4 * scale_y
        pygame.draw.line(screen, BLACK, (center_x - 8, center_y), (center_x + 8, center_y), 2)
        pygame.draw.line(screen, BLACK, (center_x, center_y - 8), (center_x, center_y + 8), 2)

        # Vẽ 4 ô vuông cho N, A, L, T
        min_x = min(p.x for p in square["points"])
        min_y = min(p.y for p in square["points"])
        n_rect = pygame.Rect((min_x - 60) * scale_x, (min_y - 80) * scale_y, 50 * scale_x, 50 * scale_y)
        a_rect = pygame.Rect((min_x - 60) * scale_x, (min_y - 120) * scale_y, 50 * scale_x, 50 * scale_y)
        l_rect = pygame.Rect(min_x * scale_x, (min_y - 80) * scale_y, 50 * scale_x, 50 * scale_y)
        t_rect = pygame.Rect(min_x * scale_x, (min_y - 120) * scale_y, 50 * scale_x, 50 * scale_y)

        # Vẽ ô N
        pygame.draw.rect(screen, WHITE, n_rect)
        pygame.draw.rect(screen, BLACK, n_rect, 1)
        text = font.render(f"N:{square['index']}", True, BLACK)
        text = pygame.transform.scale(text,
                                      (int(text.get_width() * scale_x * 0.8), int(text.get_height() * scale_y * 0.8)))
        text_rect = text.get_rect(center=n_rect.center)
        screen.blit(text, text_rect)

        # Vẽ ô A
        pygame.draw.rect(screen, WHITE, a_rect)
        pygame.draw.rect(screen, BLACK, a_rect, 1)
        text = font.render(f"A:{square['click_count']}", True, BLACK)
        text = pygame.transform.scale(text,
                                      (int(text.get_width() * scale_x * 0.8), int(text.get_height() * scale_y * 0.8)))
        text_rect = text.get_rect(center=a_rect.center)
        screen.blit(text, text_rect)

        # Vẽ ô L
        pygame.draw.rect(screen, WHITE, l_rect)
        pygame.draw.rect(screen, BLACK, l_rect, 1)
        key_display = "-"
        if square["key"]:
            if isinstance(square["key"], list):
                key_display = "+".join(square["key"]).title()
            else:
                key_display = square["key"]
        text = font.render(f"L:{key_display}", True, BLACK)
        text = pygame.transform.scale(text,
                                      (int(text.get_width() * scale_x * 0.8), int(text.get_height() * scale_y * 0.8)))
        text_rect = text.get_rect(center=l_rect.center)
        screen.blit(text, text_rect)

        # Vẽ ô T
        pygame.draw.rect(screen, WHITE, t_rect)
        pygame.draw.rect(screen, BLACK, t_rect, 1)
        time_display = "-"
        if i == countdown_square_idx and current_square_time > 0:
            minutes = current_square_time // 60
            seconds = current_square_time % 60
            time_display = f"{minutes:02d}:{seconds:02d}"
        elif square["time_seconds"] > 0:
            minutes = square["time_seconds"] // 60
            seconds = square["time_seconds"] % 60
            time_display = f"{minutes:02d}:{seconds:02d}"
        text = font.render(f"T:{time_display}", True, BLACK)
        text = pygame.transform.scale(text,
                                      (int(text.get_width() * scale_x * 0.8), int(text.get_height() * scale_y * 0.8)))
        text_rect = text.get_rect(center=t_rect.center)
        screen.blit(text, text_rect)

    # Vẽ các nút chức năng
    for key, rect in buttons.items():
        scaled_rect = pygame.Rect(rect.x * scale_x, rect.y * scale_y, rect.width * scale_x, rect.height * scale_y)
        pygame.draw.rect(screen, WHITE, scaled_rect)
        pygame.draw.rect(screen, BLACK, scaled_rect, 2)
        text = font.render(key, True, BLACK)
        text_rect = text.get_rect(center=scaled_rect.center)
        screen.blit(text, text_rect)

    # Vẽ thanh trượt A
    scaled_slider_rect = pygame.Rect(slider_rect.x * scale_x, slider_rect.y * scale_y, slider_rect.width * scale_x,
                                     slider_rect.height * scale_y)
    pygame.draw.rect(screen, WHITE, scaled_slider_rect)
    pygame.draw.rect(screen, BLACK, scaled_slider_rect, 2)
    slider_pos = scaled_slider_rect.x + 10 if not slider_state else scaled_slider_rect.x + scaled_slider_rect.width - 30
    pygame.draw.circle(screen, GREEN, (slider_pos + 10, scaled_slider_rect.y + scaled_slider_rect.height / 2), 10)
    text = font.render("ON" if slider_state else "OFF", True, BLACK)
    text = pygame.transform.scale(text, (int(text.get_width() * scale_x), int(text.get_height() * scale_y)))
    screen.blit(text, (scaled_slider_rect.x + 15 * scale_x, scaled_slider_rect.y + 5 * scale_y))

    # Vẽ khung nhập liệu Timer
    scaled_timer_rect = pygame.Rect(timer_rect.x * scale_x, timer_rect.y * scale_y, timer_rect.width * scale_x,
                                    timer_rect.height * scale_y)
    pygame.draw.rect(screen, WHITE, scaled_timer_rect)
    pygame.draw.rect(screen, BLACK, scaled_timer_rect, 2)
    if timer_running and timer_seconds > 0:
        minutes = timer_seconds // 60
        seconds = timer_seconds % 60
        timer_text = f"{minutes:02d}:{seconds:02d}"
    elif timer_seconds > 0:
        minutes = timer_seconds // 60
        seconds = timer_seconds % 60
        timer_text = f"{minutes:02d}:{seconds:02d}"
    else:
        timer_text = "00:00"
    text = font.render(timer_text, True, BLACK)
    text = pygame.transform.scale(text, (int(text.get_width() * scale_x), int(text.get_height() * scale_y)))
    screen.blit(text, (scaled_timer_rect.x + 5 * scale_x, scaled_timer_rect.y + 5 * scale_y))

    # Vẽ thanh trượt Timer
    scaled_timer_slider_rect = pygame.Rect(timer_slider_rect.x * scale_x, timer_slider_rect.y * scale_y,
                                           timer_slider_rect.width * scale_x, timer_slider_rect.height * scale_y)
    pygame.draw.rect(screen, WHITE, scaled_timer_slider_rect)
    pygame.draw.rect(screen, BLACK, scaled_timer_slider_rect, 2)
    timer_slider_pos = scaled_timer_slider_rect.x + 10 if not timer_repeat else scaled_timer_slider_rect.x + scaled_timer_slider_rect.width - 30
    pygame.draw.circle(screen, GREEN,
                       (timer_slider_pos + 10, scaled_timer_slider_rect.y + scaled_timer_rect.height / 2), 10)
    text = font.render("ON" if timer_repeat else "OFF", True, BLACK)
    text = pygame.transform.scale(text, (int(text.get_width() * scale_x), int(text.get_height() * scale_y)))
    screen.blit(text, (scaled_timer_slider_rect.x + 15 * scale_x, scaled_timer_slider_rect.y + 5 * scale_y))

    # Vẽ ô nhập liệu nếu đang ở chế độ nhập
    if input_mode:
        input_rect = pygame.Rect(window_width / 2 - 100, window_height / 2 - 20, 200, 40)
        pygame.draw.rect(screen, WHITE, input_rect)
        pygame.draw.rect(screen, BLACK, input_rect, 2)
        text = font.render(input_text, True, BLACK)
        screen.blit(text, (input_rect.x + 10, input_rect.y + 10))

    pygame.display.flip()


# Hàm tự động click và nhấn phím theo thứ tự N
async def auto_click(slider_state, window_width, window_height):
    global auto_click_triggered, countdown_square_idx, current_square_time
    if not auto_click_triggered:
        return
    sorted_squares = sorted(squares, key=lambda x: x["index"])
    for i, square in enumerate(sorted_squares):
        if not auto_click_triggered:
            break
        # Đếm ngược thời gian T nếu có
        if square["time_seconds"] > 0:
            countdown_square_idx = i
            current_square_time = square["time_seconds"]
            while current_square_time > 0 and auto_click_triggered:
                draw(window_width, window_height)
                await asyncio.sleep(1)
                current_square_time -= 1
            countdown_square_idx = None
            current_square_time = 0
            if not auto_click_triggered:
                break
        # Thực hiện click chuột A lần
        for _ in range(square["click_count"]):
            if not auto_click_triggered:
                break
            if slider_state:
                x, y = random_point_in_square(square, window_width, window_height)
            else:
                x, y = get_square_center(square, window_width, window_height)
            pyautogui.click(x, y)
            await asyncio.sleep(0.5)
        # Thực hiện phím/chuỗi L một lần
        if auto_click_triggered and square["key"]:
            if isinstance(square["key"], list):
                pyautogui.hotkey(*square["key"])
            else:
                pyautogui.typewrite(square["key"])


# Hàm chạy auto_click với Timer
async def run_auto_click_with_timer(window_width, window_height):
    global auto_click_triggered, timer_running, timer_seconds, running_coroutine
    while auto_click_triggered:
        # Chạy autoclick một lần
        await auto_click(slider_state, window_width, window_height)
        # Đếm ngược Timer toàn cục sau khi autoclick hoàn tất
        if timer_seconds > 0 and timer_running:
            while timer_seconds > 0 and auto_click_triggered:
                draw(window_width, window_height)
                await asyncio.sleep(1)
                timer_seconds -= 1
            if not auto_click_triggered:
                break
        # Nếu lặp, đặt lại timer_seconds
        if timer_repeat and auto_click_triggered:
            timer_seconds = original_timer_seconds
        else:
            timer_running = False
            timer_seconds = 0
            break
    running_coroutine = None


# Hàm khởi tạo
def setup():
    pass


# Hàm cập nhật vòng lặp
def update_loop():
    global dragging_point, dragging_square, input_mode, input_square_idx, input_text, input_is_hotkey, slider_state, timer_seconds, timer_running, timer_repeat, selected_square_idx, last_update_time, auto_click_triggered, original_timer_seconds, countdown_square_idx, current_square_time, running_coroutine
    window_width, window_height = pygame.display.get_surface().get_size()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            return False, window_width, window_height
        elif event.type == pygame.KEYDOWN:
            if input_mode:
                if event.key == pygame.K_RETURN:
                    if input_mode == "N":
                        try:
                            value = int(input_text)
                            used_indices = [square["index"] for square in squares if
                                            square != squares[input_square_idx]]
                            if value > 0 and value not in used_indices:
                                squares[input_square_idx]["index"] = value
                                save_state()
                        except ValueError:
                            pass
                    elif input_mode == "A":
                        try:
                            value = int(input_text)
                            if value >= 0:
                                squares[input_square_idx]["click_count"] = value
                                save_state()
                        except ValueError:
                            pass
                    elif input_mode == "L":
                        if input_text:
                            if input_is_hotkey:
                                keys = [k.strip().lower() for k in input_text.split("+")]
                                squares[input_square_idx]["key"] = keys
                            else:
                                squares[input_square_idx]["key"] = input_text.lower()
                            save_state()
                        else:
                            squares[input_square_idx]["key"] = None
                            save_state()
                    elif input_mode == "T":
                        try:
                            if ":" in input_text:
                                minutes_str, seconds_str = input_text.split(":")
                                minutes = int(minutes_str)
                                seconds = int(seconds_str)
                                if 0 <= minutes <= 59 and 0 <= seconds <= 59:
                                    total_seconds = minutes * 60 + seconds
                                    if input_square_idx is not None:
                                        squares[input_square_idx]["time_seconds"] = total_seconds
                                    else:
                                        timer_seconds = total_seconds
                                        original_timer_seconds = total_seconds
                                        timer_running = False
                                    save_state()
                        except (ValueError, IndexError):
                            pass
                    input_mode = None
                    input_square_idx = None
                    input_text = ""
                    input_is_hotkey = False
                elif event.key == pygame.K_ESCAPE:
                    input_mode = None
                    input_square_idx = None
                    input_text = ""
                    input_is_hotkey = False
                elif event.key == pygame.K_BACKSPACE:
                    input_text = input_text[:-1]
                elif input_mode == "L":
                    if event.key in (
                    pygame.K_LCTRL, pygame.K_RCTRL, pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_LALT, pygame.K_RALT):
                        input_is_hotkey = True
                        modifier = pygame.key.name(event.key).replace("left ", "").replace("right ", "")
                        if input_text:
                            input_text += "+" + modifier
                        else:
                            input_text = modifier
                    elif input_is_hotkey:
                        key_name = pygame.key.name(event.key)
                        input_text += "+" + key_name
                    elif event.unicode:
                        input_text += event.unicode
                elif input_mode in ["N", "A"] and event.unicode.isdigit():
                    input_text += event.unicode
                elif input_mode == "T" and len(input_text) < 5:
                    if event.unicode.isdigit():
                        input_text += event.unicode
                    elif event.unicode == ":" and ":" not in input_text:
                        input_text += event.unicode
            else:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return False, window_width, window_height
                elif event.key == pygame.K_e:
                    add_square()
                elif event.key == pygame.K_a:
                    if running_coroutine is None:
                        auto_click_triggered = True
                        timer_running = timer_seconds > 0
                        running_coroutine = asyncio.ensure_future(
                            run_auto_click_with_timer(window_width, window_height))
                elif event.key == pygame.K_s:
                    save_data()
                elif event.key == pygame.K_i:
                    load_data()
                elif event.key == pygame.K_u or (event.key == pygame.K_z and pygame.key.get_mods() & pygame.KMOD_CTRL):
                    undo()
                elif event.key in [pygame.K_x, pygame.K_BACKSPACE, pygame.K_DELETE]:
                    mouse_pos = pygame.mouse.get_pos()
                    delete_square(mouse_pos, window_width, window_height)
                elif event.key == pygame.K_r:
                    if running_coroutine is None:
                        auto_click_triggered = True
                        timer_running = timer_seconds > 0
                        running_coroutine = asyncio.ensure_future(
                            run_auto_click_with_timer(window_width, window_height))
                elif event.key == pygame.K_t:
                    auto_click_triggered = False
                    timer_running = False
                    timer_seconds = 0
                    countdown_square_idx = None
                    current_square_time = 0
                    running_coroutine = None
        elif event.type == pygame.MOUSEBUTTONDOWN:
            pos = event.pos
            if input_mode:
                continue
            square_idx, label = check_label_click(pos, window_width, window_height)
            if square_idx is not None and label:
                input_mode = label
                input_square_idx = square_idx
                selected_square_idx = square_idx
                if label == "N":
                    input_text = str(squares[square_idx]["index"])
                elif label == "A":
                    input_text = str(squares[square_idx]["click_count"])
                elif label == "L":
                    if squares[square_idx]["key"]:
                        if isinstance(squares[square_idx]["key"], list):
                            input_text = "+".join(squares[square_idx]["key"])
                            input_is_hotkey = True
                        else:
                            input_text = squares[square_idx]["key"]
                            input_is_hotkey = False
                    else:
                        input_text = ""
                        input_is_hotkey = False
                elif label == "T":
                    if squares[square_idx]["time_seconds"] > 0:
                        minutes = squares[square_idx]["time_seconds"] // 60
                        seconds = squares[square_idx]["time_seconds"] % 60
                        input_text = f"{minutes:02d}:{seconds:02d}"
                    else:
                        input_text = ""
                continue
            if check_slider_click(pos, window_width, window_height):
                slider_state = not slider_state
                continue
            if check_timer_slider_click(pos, window_width, window_height):
                timer_repeat = not timer_repeat
                continue
            if check_timer_input_click(pos, window_width, window_height):
                input_mode = "T"
                input_square_idx = None
                minutes = timer_seconds // 60
                seconds = timer_seconds % 60
                input_text = f"{minutes:02d}:{seconds:02d}"
                continue
            button = check_button_click(pos, window_width, window_height)
            if button == "E":
                add_square()
            elif button == "A":
                if running_coroutine is None:
                    auto_click_triggered = True
                    timer_running = timer_seconds > 0
                    running_coroutine = asyncio.ensure_future(run_auto_click_with_timer(window_width, window_height))
            elif button == "S":
                save_data()
            elif button == "I":
                load_data()
            elif button == "U":
                undo()
            elif button == "X":
                delete_square(pos, window_width, window_height)
            elif button == "T":
                auto_click_triggered = False
                timer_running = False
                timer_seconds = 0
                countdown_square_idx = None
                current_square_time = 0
                running_coroutine = None
            elif button == "Start":
                if running_coroutine is None:
                    auto_click_triggered = True
                    timer_running = timer_seconds > 0
                    running_coroutine = asyncio.ensure_future(run_auto_click_with_timer(window_width, window_height))
            elif button == "Stop":
                auto_click_triggered = False
                timer_running = False
                timer_seconds = 0
                countdown_square_idx = None
                current_square_time = 0
                running_coroutine = None
            else:
                square_idx = find_nearest_square_center(pos, window_width, window_height)
                if square_idx is not None:
                    dragging_square = square_idx
                    selected_square_idx = square_idx
                else:
                    point_idx = find_nearest_point(pos, window_width, window_height)
                    if point_idx is not None:
                        dragging_point = point_idx
                        selected_square_idx = point_idx[0]
                    else:
                        selected_square_idx = None
        elif event.type == pygame.MOUSEBUTTONUP:
            if dragging_point is not None or dragging_square is not None:
                save_state()
            dragging_point = None
            dragging_square = None
        elif event.type == pygame.MOUSEMOTION:
            if dragging_point is not None:
                scale_x = window_width / WORLD_WIDTH
                scale_y = window_height / WORLD_HEIGHT
                square_idx, point_idx = dragging_point
                squares[square_idx]["points"][point_idx].x = event.pos[0] / scale_x
                squares[square_idx]["points"][point_idx].y = event.pos[1] / scale_y
            elif dragging_square is not None:
                scale_x = window_width / WORLD_WIDTH
                scale_y = window_height / WORLD_HEIGHT
                square_idx = dragging_square
                square = squares[square_idx]
                old_center_x = sum(p.x for p in square["points"]) / 4
                old_center_y = sum(p.y for p in square["points"]) / 4
                dx = event.pos[0] / scale_x - old_center_x
                dy = event.pos[1] / scale_y - old_center_y
                for point in square["points"]:
                    point.x += dx
                    point.y += dy
    draw(window_width, window_height)
    return True, window_width, window_height


# Vòng lặp chính
async def main():
    setup()
    running = True
    while running:
        running, window_width, window_height = update_loop()
        await asyncio.sleep(1.0 / FPS)

if platform.system() == "Emscripten":
    asyncio.ensure_future(main())
else:
    if __name__ == "__main__":
        asyncio.run(main())