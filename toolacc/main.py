import ctypes
import ctypes.wintypes
ctypes.windll.user32.SetProcessDPIAware()

import tkinter as tk
from tkinter import ttk
import time

import win32gui
import win32api
import win32con

from pynput import mouse

# =========================================================
# GLOBALS
# =========================================================

MASTER_HWND = None
SLAVE_WINDOWS = []

SELECTING_MODE = None

SYNC_ENABLED = False
SYNC_RUNNING = False

LAST_CLICK_TIME = 0

# =========================================================
# UTILS
# =========================================================

def log(msg):
    print(msg)


def is_valid_window(hwnd):

    if not hwnd:
        return False

    if not win32gui.IsWindow(hwnd):
        return False

    if not win32gui.IsWindowVisible(hwnd):
        return False

    title = win32gui.GetWindowText(hwnd).strip()

    if not title:
        return False

    blacklist = [
        "Program Manager",
        "Windows Input Experience",
        "Default IME"
    ]

    if title in blacklist:
        return False

    return True


def get_window_title(hwnd):

    try:
        return win32gui.GetWindowText(hwnd)

    except:
        return "Unknown"


def client_to_screen(hwnd):

    x, y = win32gui.ClientToScreen(hwnd, (0, 0))

    rect = win32gui.GetClientRect(hwnd)

    w = rect[2]
    h = rect[3]

    return x, y, w, h


def get_relative_pos(hwnd, screen_x, screen_y):

    cx, cy, _, _ = client_to_screen(hwnd)

    return (
        screen_x - cx,
        screen_y - cy
    )


def do_click(hwnd, x, y):

    try:

        lp = win32api.MAKELONG(
            int(x),
            int(y)
        )

        win32gui.PostMessage(
            hwnd,
            win32con.WM_LBUTTONDOWN,
            win32con.MK_LBUTTON,
            lp
        )

        time.sleep(0.01)

        win32gui.PostMessage(
            hwnd,
            win32con.WM_LBUTTONUP,
            0,
            lp
        )

    except Exception as e:

        log(f"[click] lỗi: {e}")


# =========================================================
# SYNC ENGINE
# =========================================================

class SyncEngine:

    def __init__(self):

        self.listener = None

    def start(self):

        global SYNC_RUNNING

        if SYNC_RUNNING:
            return

        SYNC_RUNNING = True

        self.listener = mouse.Listener(
            on_click=self.on_click
        )

        self.listener.start()

        log("[sync] started")

    def stop(self):

        global SYNC_RUNNING

        SYNC_RUNNING = False

        if self.listener:
            self.listener.stop()
            self.listener = None

        log("[sync] stopped")

    def on_click(self, x, y, button, pressed):

        global LAST_CLICK_TIME

        if not pressed:
            return

        if not SYNC_ENABLED:
            return

        if not MASTER_HWND:
            return

        now = time.time()

        if now - LAST_CLICK_TIME < 0.03:
            return

        LAST_CLICK_TIME = now

        fg = win32gui.GetForegroundWindow()

        if fg != MASTER_HWND:
            return

        try:

            rx, ry = get_relative_pos(
                MASTER_HWND,
                x,
                y
            )

            _, _, mw, mh = client_to_screen(MASTER_HWND)

            if rx < 0 or ry < 0:
                return

            if rx > mw or ry > mh:
                return

            for hwnd in SLAVE_WINDOWS:

                if not is_valid_window(hwnd):
                    continue

                _, _, sw, sh = client_to_screen(hwnd)

                if rx > sw or ry > sh:
                    continue

                do_click(hwnd, rx, ry)

        except Exception as e:

            log(f"[sync] lỗi: {e}")


# =========================================================
# APP
# =========================================================

class App:

    def __init__(self):

        self.root = tk.Tk()

        self.root.title("KNHT Multi Window Controller")

        self.root.geometry("640x720")

        self.root.minsize(640, 720)

        self.root.maxsize(640, 720)

        self.root.configure(bg="#f4f4f4")

        self.sync_engine = SyncEngine()

        self.build_ui()

        self.update_ui()

    # =====================================================
    # UI
    # =====================================================

    def build_ui(self):

        # =================================================
        # TITLE
        # =================================================

        title = tk.Label(
            self.root,
            text="KNHT Multi Window Controller",
            font=("Segoe UI", 16, "bold"),
            bg="#f4f4f4",
            fg="#222222"
        )

        title.pack(pady=12)

        # =================================================
        # MASTER
        # =================================================

        master_frame = tk.LabelFrame(
            self.root,
            text="Cửa sổ gốc",
            bg="white",
            fg="#222222",
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=10
        )

        master_frame.pack(
            fill="x",
            padx=15,
            pady=8
        )

        self.master_info = tk.Label(
            master_frame,
            text="Chưa chọn cửa sổ",
            bg="white",
            fg="#666666",
            justify="left",
            anchor="w",
            font=("Segoe UI", 10)
        )

        self.master_info.pack(
            fill="x",
            pady=(0, 10)
        )

        self.pick_master_btn = tk.Button(
            master_frame,
            text="+ Chọn cửa sổ gốc",
            width=22,
            command=self.pick_master
        )

        self.pick_master_btn.pack()

        # =================================================
        # SLAVE
        # =================================================

        slave_frame = tk.LabelFrame(
            self.root,
            text="Cửa sổ con",
            bg="white",
            fg="#222222",
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=10
        )

        slave_frame.pack(
            fill="x",
            padx=15,
            pady=8
        )

        topbar = tk.Frame(
            slave_frame,
            bg="white"
        )

        topbar.pack(fill="x")

        tk.Button(
            topbar,
            text="+ Thêm cửa sổ",
            width=18,
            command=self.pick_slave
        ).pack(side="left")

        tk.Button(
            topbar,
            text="Xóa tất cả",
            width=12,
            command=self.clear_slaves
        ).pack(side="right")

        # =================================================
        # SCROLL LIST
        # =================================================

        list_container = tk.Frame(
            slave_frame,
            bg="white",
            height=260
        )

        list_container.pack(
            fill="x",
            pady=(10, 0)
        )

        list_container.pack_propagate(False)

        self.canvas = tk.Canvas(
            list_container,
            bg="white",
            highlightthickness=0
        )

        scrollbar = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.canvas.yview
        )

        self.canvas.configure(
            yscrollcommand=scrollbar.set
        )

        scrollbar.pack(
            side="right",
            fill="y"
        )

        self.canvas.pack(
            side="left",
            fill="both",
            expand=True
        )

        self.scroll_frame = tk.Frame(
            self.canvas,
            bg="white"
        )

        self.canvas.create_window(
            (0, 0),
            window=self.scroll_frame,
            anchor="nw",
            width=585
        )

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        # =================================================
        # CONTROL
        # =================================================

        control = tk.LabelFrame(
            self.root,
            text="Điều khiển",
            bg="white",
            fg="#222222",
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=10
        )

        control.pack(
            fill="x",
            padx=15,
            pady=8
        )

        btns = tk.Frame(
            control,
            bg="white"
        )

        btns.pack(pady=5)

        self.start_btn = tk.Button(
            btns,
            text="Start",
            width=12,
            command=self.start_sync
        )

        self.start_btn.pack(
            side="left",
            padx=5
        )

        self.pause_btn = tk.Button(
            btns,
            text="Pause",
            width=12,
            command=self.pause_sync
        )

        self.pause_btn.pack(
            side="left",
            padx=5
        )

        self.stop_btn = tk.Button(
            btns,
            text="Stop",
            width=12,
            command=self.stop_sync
        )

        self.stop_btn.pack(
            side="left",
            padx=5
        )

        # =================================================
        # STATUS
        # =================================================

        self.status_label = tk.Label(
            control,
            text="STATUS: STOPPED",
            font=("Segoe UI", 10, "bold"),
            bg="white",
            fg="#dc3545"
        )

        self.status_label.pack(
            pady=(10, 4)
        )

        self.info_label = tk.Label(
            control,
            text="Synchronization Disabled",
            font=("Segoe UI", 9),
            bg="white",
            fg="#666666"
        )

        self.info_label.pack(
            pady=(0, 6)
        )

    # =====================================================
    # PICK WINDOW
    # =====================================================

    def pick_master(self):

        global SELECTING_MODE

        SELECTING_MODE = "master"

        self.status_label.config(
            text="STATUS: SELECT MASTER",
            fg="#cc8800"
        )

        self.root.after(
            100,
            self.wait_window_pick
        )

    def pick_slave(self):

        global SELECTING_MODE

        SELECTING_MODE = "slave"

        self.status_label.config(
            text="STATUS: SELECT SLAVE",
            fg="#cc8800"
        )

        self.root.after(
            100,
            self.wait_window_pick
        )

    def wait_window_pick(self):

        global SELECTING_MODE
        global MASTER_HWND

        if not SELECTING_MODE:
            return

        if win32api.GetAsyncKeyState(0x01) & 0x8000:

            pt = win32api.GetCursorPos()

            hwnd = win32gui.WindowFromPoint(pt)

            if not is_valid_window(hwnd):

                self.status_label.config(
                    text="STATUS: INVALID WINDOW",
                    fg="#dc3545"
                )

                SELECTING_MODE = None

                return

            if SELECTING_MODE == "master":

                MASTER_HWND = hwnd

            elif SELECTING_MODE == "slave":

                if hwnd != MASTER_HWND:

                    if hwnd not in SLAVE_WINDOWS:

                        SLAVE_WINDOWS.append(hwnd)

            SELECTING_MODE = None

            self.refresh_slave_list()

            self.status_label.config(
                text="STATUS: WINDOW ADDED",
                fg="#28a745"
            )

        else:

            self.root.after(
                50,
                self.wait_window_pick
            )

    # =====================================================
    # SLAVE LIST
    # =====================================================

    def refresh_slave_list(self):

        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        for hwnd in SLAVE_WINDOWS:

            row = tk.Frame(
                self.scroll_frame,
                bg="#f8f8f8",
                bd=1,
                relief="solid"
            )

            row.pack(
                fill="x",
                padx=5,
                pady=4
            )

            title = get_window_title(hwnd)

            txt = f"{title} | HWND={hwnd}"

            tk.Label(
                row,
                text=txt,
                bg="#f8f8f8",
                fg="#222222",
                anchor="w",
                justify="left",
                font=("Segoe UI", 9)
            ).pack(
                side="left",
                fill="x",
                expand=True,
                padx=8,
                pady=8
            )

            tk.Button(
                row,
                text="Xóa",
                width=8,
                command=lambda h=hwnd: self.remove_slave(h)
            ).pack(
                side="right",
                padx=6
            )

    def remove_slave(self, hwnd):

        if hwnd in SLAVE_WINDOWS:

            SLAVE_WINDOWS.remove(hwnd)

        self.refresh_slave_list()

    def clear_slaves(self):

        SLAVE_WINDOWS.clear()

        self.refresh_slave_list()

    # =====================================================
    # CONTROL
    # =====================================================

    def start_sync(self):

        global SYNC_ENABLED

        if not MASTER_HWND:

            self.status_label.config(
                text="STATUS: NO MASTER",
                fg="#dc3545"
            )

            return

        if not SLAVE_WINDOWS:

            self.status_label.config(
                text="STATUS: NO SLAVE WINDOWS",
                fg="#dc3545"
            )

            return

        SYNC_ENABLED = True

        self.sync_engine.start()

        self.status_label.config(
            text="STATUS: ACTIVE",
            fg="#28a745"
        )

        self.info_label.config(
            text=f"Master: Connected | Slave Windows: {len(SLAVE_WINDOWS)}",
            fg="#222222"
        )

    def pause_sync(self):

        global SYNC_ENABLED

        SYNC_ENABLED = False

        self.status_label.config(
            text="STATUS: PAUSED",
            fg="#cc8800"
        )

        self.info_label.config(
            text=f"Master: Connected | Slave Windows: {len(SLAVE_WINDOWS)}",
            fg="#222222"
        )

    def stop_sync(self):

        global SYNC_ENABLED

        SYNC_ENABLED = False

        self.sync_engine.stop()

        self.status_label.config(
            text="STATUS: STOPPED",
            fg="#dc3545"
        )

        self.info_label.config(
            text="Synchronization Disabled",
            fg="#666666"
        )

    # =====================================================
    # UPDATE UI
    # =====================================================

    def update_ui(self):

        if MASTER_HWND and is_valid_window(MASTER_HWND):

            title = get_window_title(MASTER_HWND)

            self.master_info.config(
                text=f"{title}\nHWND = {MASTER_HWND}",
                fg="#222222"
            )

        else:

            self.master_info.config(
                text="Chưa chọn cửa sổ",
                fg="#666666"
            )

        self.root.after(
            200,
            self.update_ui
        )

    # =====================================================
    # RUN
    # =====================================================

    def run(self):

        self.root.mainloop()


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    App().run()