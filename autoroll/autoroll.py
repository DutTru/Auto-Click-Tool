import os
import threading
import time
import tkinter as tk
from tkinter import messagebox
import pyautogui

# === THƯ MỤC ẢNH ===
CLICK_IMAGES_DIR = "click_images"
PRIORITY_IMAGES_DIR = "priority_images"
STOP_IMAGES_DIR = "stop_images"

for d in [CLICK_IMAGES_DIR, PRIORITY_IMAGES_DIR, STOP_IMAGES_DIR]:
    os.makedirs(d, exist_ok=True)

# === CÀI ĐẶT ===
click_interval = 2.5      # thời gian giữa 2 lần click ảnh chính (giây)
scan_interval = 0.3       # tốc độ quét ảnh stop / priority
confidence_level = 0.85
running = False

# === GIAO DIỆN ===
root = tk.Tk()
root.title("Smart Auto Clicker v3.1")
root.geometry("620x440")
root.configure(bg="#1e1e1e")

status_label = tk.Label(root, text="Trạng thái: Đang chờ...", fg="white", bg="#1e1e1e", font=("Consolas", 12))
status_label.pack(pady=10)

current_target_label = tk.Label(root, text="Ảnh đang click: None", fg="lightgreen", bg="#1e1e1e", font=("Consolas", 12))
current_target_label.pack(pady=5)

priority_label = tk.Label(root, text="Ảnh ưu tiên: None", fg="yellow", bg="#1e1e1e", font=("Consolas", 12))
priority_label.pack(pady=5)

stop_label = tk.Label(root, text="Ảnh dừng: None", fg="red", bg="#1e1e1e", font=("Consolas", 12))
stop_label.pack(pady=5)

# === HÀM HỖ TRỢ ===
def load_images(folder):
    return [os.path.join(folder, f) for f in os.listdir(folder)
            if f.lower().endswith((".png", ".jpg", ".jpeg"))]

def find_image(image_path):
    try:
        return pyautogui.locateCenterOnScreen(image_path, confidence=confidence_level)
    except Exception:
        return None

def find_and_click(image_path):
    pos = find_image(image_path)
    if pos:
        pyautogui.click(pos)
        return True
    return False

# === HÀM CHÍNH ===
def auto_click():
    global running
    click_imgs = load_images(CLICK_IMAGES_DIR)
    priority_imgs = load_images(PRIORITY_IMAGES_DIR)
    stop_imgs = load_images(STOP_IMAGES_DIR)

    if not click_imgs:
        messagebox.showerror("Lỗi", f"Không có ảnh trong {CLICK_IMAGES_DIR}")
        running = False
        return

    last_click_time = 0  # thời gian lần click ảnh chính gần nhất

    while running:
        now = time.time()

        # 1️⃣ Kiểm tra ảnh dừng
        for s_img in stop_imgs:
            if find_image(s_img):
                stop_label.config(text=f"Ảnh dừng: {os.path.basename(s_img)}", fg="red")
                status_label.config(text="Trạng thái: ĐÃ DỪNG (phát hiện ảnh dừng)", fg="red")
                running = False
                return

        # 2️⃣ Kiểm tra ảnh ưu tiên
        for p_img in priority_imgs:
            if not running:
                break
            result = find_image(p_img)
            if result:
                priority_label.config(text=f"Ảnh ưu tiên: {os.path.basename(p_img)}", fg="yellow")
                current_target_label.config(text="Tạm dừng ảnh chính (đang click ảnh ưu tiên)", fg="gray")
                pyautogui.click(result)
                time.sleep(scan_interval)  # giữ nhịp quét mượt
                break
        else:
            # 3️⃣ Click ảnh chính (chỉ khi đủ thời gian)
            if now - last_click_time >= click_interval:
                for c_img in click_imgs:
                    if not running:
                        break
                    if find_and_click(c_img):
                        current_target_label.config(text=f"Ảnh đang click: {os.path.basename(c_img)}", fg="lightgreen")
                        last_click_time = time.time()
                        break
                else:
                    current_target_label.config(text="Không tìm thấy ảnh nào", fg="red")

        time.sleep(scan_interval)  # quét ảnh stop/priority liên tục, mượt hơn

def start_clicking():
    global running
    if running:
        return
    running = True
    status_label.config(text="Trạng thái: ĐANG CHẠY", fg="lightgreen")
    threading.Thread(target=auto_click, daemon=True).start()

def stop_clicking():
    global running
    running = False
    status_label.config(text="Trạng thái: ĐÃ DỪNG", fg="orange")

def open_folder(folder):
    os.startfile(folder)

# === NÚT GIAO DIỆN ===
btn_frame = tk.Frame(root, bg="#1e1e1e")
btn_frame.pack(pady=15)

tk.Button(btn_frame, text="Bắt đầu", command=start_clicking, width=12, bg="#2e8b57", fg="white").grid(row=0, column=0, padx=10)
tk.Button(btn_frame, text="Dừng lại", command=stop_clicking, width=12, bg="#8b0000", fg="white").grid(row=0, column=1, padx=10)

tk.Button(btn_frame, text="Mở thư mục ảnh click", command=lambda: open_folder(CLICK_IMAGES_DIR), width=25).grid(row=1, column=0, columnspan=2, pady=5)
tk.Button(btn_frame, text="Mở thư mục ảnh ưu tiên", command=lambda: open_folder(PRIORITY_IMAGES_DIR), width=25).grid(row=2, column=0, columnspan=2, pady=5)
tk.Button(btn_frame, text="Mở thư mục ảnh dừng", command=lambda: open_folder(STOP_IMAGES_DIR), width=25).grid(row=3, column=0, columnspan=2, pady=5)

root.mainloop()

