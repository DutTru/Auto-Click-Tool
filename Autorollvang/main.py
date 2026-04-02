import ctypes, ctypes.wintypes
ctypes.windll.user32.SetProcessDPIAware()

import win32gui, win32con, win32api, win32ui
import numpy as np, cv2, threading, time, tkinter as tk
import os, glob, json
from PIL import Image, ImageTk
from tkinter import filedialog

# ───────────────────────── GLOBALS ─────────────────────────
hwnd      = None
selecting = False

IMG_DIR = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(IMG_DIR, exist_ok=True)

preview_img = None
match_val   = 0.0
templates   = []          # [(name_str, gray_ndarray)]

_last_log = ""
rois = {"scan": None, "refresh": None, "confirm": None}

SWP_NOSIZE     = 0x0001
SWP_NOMOVE     = 0x0002
SWP_NOACTIVATE = 0x0010
HWND_TOPMOST   = -1
HWND_NOTOPMOST = -2


# ───────────────────────── UTILS ───────────────────────────
def log(msg):
    global _last_log
    _last_log = msg
    print(msg)


def client_screen_rect(h):
    """Trả về (screen_x, screen_y, width, height) của vùng CLIENT."""
    cx, cy = win32gui.ClientToScreen(h, (0, 0))
    r = win32gui.GetClientRect(h)          # (0,0,w,h) — luôn bắt đầu từ 0
    return cx, cy, r[2], r[3]


# ───────────────────────── CAPTURE ─────────────────────────
def capture_window(h):
    try:
        _, _, w, h_px = client_screen_rect(h)
        if w <= 0 or h_px <= 0:
            return None

        hdc    = win32gui.GetDC(h)
        mfc_dc = win32ui.CreateDCFromHandle(hdc)
        mem_dc = mfc_dc.CreateCompatibleDC()
        bmp    = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfc_dc, w, h_px)
        mem_dc.SelectObject(bmp)

        ok = False
        for flag in (2, 0, 1):
            if ctypes.windll.user32.PrintWindow(h, mem_dc.GetSafeHdc(), flag):
                ok = True; break
        if not ok:
            mem_dc.BitBlt((0, 0), (w, h_px), mfc_dc, (0, 0), win32con.SRCCOPY)

        info = bmp.GetInfo()
        data = bmp.GetBitmapBits(True)
        img  = np.frombuffer(data, dtype=np.uint8).reshape(
                   (info["bmHeight"], info["bmWidth"], 4))[:, :, :3].copy()

        win32gui.DeleteObject(bmp.GetHandle())
        mem_dc.DeleteDC(); mfc_dc.DeleteDC()
        win32gui.ReleaseDC(h, hdc)

        if img.mean() < 3:
            log("[capture] WARNING: ảnh đen — PrintWindow không hỗ trợ window này")
        return img

    except Exception as e:
        log(f"[capture] lỗi: {e}"); return None


# ───────────────────────── CLICK ───────────────────────────
def do_click(h, cx, cy):
    lp = win32api.MAKELONG(int(cx), int(cy))
    win32gui.PostMessage(h, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
    time.sleep(0.05)
    win32gui.PostMessage(h, win32con.WM_LBUTTONUP, 0, lp)
    log(f"[click] ({int(cx)}, {int(cy)})")


# ───────────────────────── TEMPLATES ───────────────────────
def load_templates():
    global templates
    templates = []
    for p in glob.glob(os.path.join(IMG_DIR, "*.png")):
        g = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if g is not None:
            templates.append((os.path.basename(p), g))
            log(f"[tpl] {os.path.basename(p)}  {g.shape[1]}x{g.shape[0]}")
        else:
            log(f"[tpl] lỗi đọc: {p}")
    log(f"[tpl] tổng {len(templates)} ảnh" if templates
        else f"[tpl] KHÔNG có ảnh trong: {IMG_DIR}")


# ───────────────────────── MULTI-SCALE MATCH ───────────────
def multiscale_match(crop_gray: np.ndarray, tpl_gray: np.ndarray,
                     tname: str = "") -> float:
    """
    So sánh template với crop ở nhiều tỉ lệ.
    - Nếu template lớn hơn crop: scale template xuống vừa crop rồi match.
    - Thử nhiều tỉ lệ scale của template (0.4x → 1.6x) với bước 5%,
      giới hạn template không được lớn hơn crop.
    - Trả về val cao nhất tìm được (0.0 → 1.0).
    """
    ch, cw = crop_gray.shape[:2]
    th, tw = tpl_gray.shape[:2]

    if ch < 4 or cw < 4:
        return 0.0

    best = 0.0

    # Tính dải scale: từ 40% đến 160% kích thước gốc, bước 5%
    scales = [round(s * 0.05, 2) for s in range(8, 33)]   # 0.40 … 1.60

    for scale in scales:
        new_w = int(tw * scale)
        new_h = int(th * scale)

        # Template phải nhỏ hơn crop ít nhất 1px mỗi chiều
        if new_w >= cw or new_h >= ch:
            continue
        if new_w < 4 or new_h < 4:
            continue

        resized = cv2.resize(tpl_gray, (new_w, new_h),
                             interpolation=cv2.INTER_AREA
                             if scale < 1.0 else cv2.INTER_LINEAR)

        res = cv2.matchTemplate(crop_gray, resized, cv2.TM_CCOEFF_NORMED)
        _, val, _, _ = cv2.minMaxLoc(res)
        if val > best:
            best = val
            if best > 0.95:   # đủ tốt, dừng sớm
                break

    return best


# ───────────────────────── SCAN WORKER ─────────────────────
class ScanWorker:
    def __init__(self):
        self._ev  = threading.Event()
        self._thr = threading.Thread(target=self._run, daemon=True)

    def start(self): self._thr.start()
    def stop(self):  self._ev.set(); self._thr.join(2.0)

    @property
    def alive(self): return self._thr.is_alive()

    def _run(self):
        global preview_img, match_val
        last_refresh = 0

        while not self._ev.is_set():
            if not hwnd:
                self._ev.wait(0.5); continue

            img = capture_window(hwnd)
            if img is None:
                self._ev.wait(0.5); continue

            # SCAN
            roi = rois.get("scan")
            if roi:
                x, y, w, h = (int(v) for v in roi)
                ih, iw = img.shape[:2]
                crop = img[max(0,y):min(ih,y+h), max(0,x):min(iw,x+w)]
                log(f"[scan] roi=({x},{y},{w},{h}) game=({iw}x{ih}) crop=({crop.shape[1]}x{crop.shape[0]})")

                if crop.size == 0:
                    log("[scan] crop rỗng"); self._ev.wait(0.3); continue

                preview_img = crop.copy()
                gc = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

                if not templates:
                    log("[scan] không có template"); match_val = 0.0
                else:
                    best = 0.0
                    for tname, tg in templates:
                        val = multiscale_match(gc, tg, tname)
                        log(f"[scan] '{tname}' val={val:.3f}")
                        best = max(best, val)
                        if val > 0.9:
                            log(f"[MATCH] '{tname}' {val:.2f} → CONFIRM")
                            c = rois.get("confirm")
                            if c:
                                cx2, cy2, cw2, ch2 = (int(v) for v in c)
                                do_click(hwnd, cx2+cw2//2, cy2+ch2//2)
                            break
                    match_val = best

            # REFRESH
            rr = rois.get("refresh")
            if rr and time.time() - last_refresh > 10:
                rx, ry, rw, rh = (int(v) for v in rr)
                do_click(hwnd, rx+rw//2, ry+rh//2)
                log("[refresh] click"); last_refresh = time.time()

            self._ev.wait(0.3)


# ───────────────────────── BOX ─────────────────────────────
class Box:
    _C = {"scan":"#00bb44","refresh":"#cc8800","confirm":"#cc1111"}

    def __init__(self, parent, mode):
        self.mode = mode; self.resizing = False
        c = self._C.get(mode, "#444")
        self.f = tk.Frame(parent, bg=c, cursor="fleur",
                          highlightthickness=2, highlightbackground="white")
        self.f.place(x=50, y=50, width=140, height=70)
        tk.Label(self.f, text=mode.upper(), bg=c,
                 font=("Consolas",9,"bold"), fg="white").place(
            relx=.5, rely=.38, anchor="center")
        tk.Label(self.f, text="drag  |  RC=resize", bg=c,
                 font=("Arial",6), fg="white").place(
            relx=.5, rely=.80, anchor="center")
        for w in list(self.f.winfo_children())+[self.f]:
            w.bind("<Button-1>",        self._ds)
            w.bind("<B1-Motion>",       self._dm)
            w.bind("<Button-3>",        self._rs)
            w.bind("<B3-Motion>",       self._rm)
            w.bind("<ButtonRelease-3>", self._re)
        self.f.after(80, self._save)

    def _ds(self, e):
        self._ox,self._oy = e.x_root,e.y_root
        self._fx,self._fy = self.f.winfo_x(),self.f.winfo_y()
    def _dm(self, e):
        self.f.place(x=self._fx+e.x_root-self._ox,
                     y=self._fy+e.y_root-self._oy); self._save()
    def _rs(self, e):
        fw,fh = self.f.winfo_width(),self.f.winfo_height()
        if e.x>fw-20 and e.y>fh-20:
            self.resizing=True
            self._sw,self._sh = fw,fh
            self._sx,self._sy = e.x_root,e.y_root
    def _rm(self, e):
        if not self.resizing: return
        self.f.place(width=max(50,self._sw+e.x_root-self._sx),
                     height=max(30,self._sh+e.y_root-self._sy)); self._save()
    def _re(self, e): self.resizing=False
    def _save(self):
        rois[self.mode]=(int(self.f.winfo_x()),int(self.f.winfo_y()),
                         int(self.f.winfo_width()),int(self.f.winfo_height()))


# ───────────────────────── OVERLAY ─────────────────────────
class Overlay:
    """
    Overlay bám theo game window.
    Z-order: topmost CHỈ KHI game đang là foreground window.
    Khi user chuyển sang cửa sổ khác → overlay tự hạ xuống cùng game.
    """
    def __init__(self, game_hwnd):
        self.game_hwnd  = game_hwnd
        self.boxes      = {}
        self._last_pos  = None
        self._topmost   = None      # trạng thái topmost hiện tại

        self.root = tk.Toplevel()
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0.35)
        self.root.withdraw()        # ẩn trước, hiện sau khi có HWND

        self.root.update_idletasks()

        # ── Lấy HWND thật qua winfo_id() — CÁCH DUY NHẤT ĐÁng TIN ──
        # winfo_id() trả về handle của Tk window (kiểu int)
        self._ov_hwnd = int(self.root.winfo_id())

        # Nếu Toplevel có parent khác, cần lấy HWND cấp cao nhất
        # GetAncestor(hwnd, GA_ROOT=2) → root window trong Win32 tree
        GA_ROOT = 2
        self._ov_hwnd = ctypes.windll.user32.GetAncestor(self._ov_hwnd, GA_ROOT)

        self.root.deiconify()
        self._follow()

    def _set_topmost(self, on: bool):
        if self._topmost == on:
            return
        flag = HWND_TOPMOST if on else HWND_NOTOPMOST
        ctypes.windll.user32.SetWindowPos(
            self._ov_hwnd, flag, 0, 0, 0, 0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
        self._topmost = on

    def _follow(self):
        try:
            cx, cy, w, h = client_screen_rect(self.game_hwnd)
            pos = (cx, cy, w, h)
            if pos != self._last_pos:
                self.root.geometry(f"{w}x{h}+{cx}+{cy}")
                self._last_pos = pos

            # Topmost chỉ khi game đang focus
            fg = win32gui.GetForegroundWindow()
            self._set_topmost(fg == self.game_hwnd)

        except Exception as e:
            log(f"[overlay] follow lỗi: {e}")

        self.root.after(150, self._follow)

    def add(self, mode):
        if mode not in self.boxes:
            self.boxes[mode] = Box(self.root, mode)

    def remove(self, mode):
        if mode in self.boxes:
            self.boxes[mode].f.destroy()
            del self.boxes[mode]
            rois[mode] = None

    def load_boxes(self):
        for mode, roi in rois.items():
            if roi:
                self.add(mode)
                x, y, w, h = (int(v) for v in roi)
                self.boxes[mode].f.place(x=x, y=y, width=w, height=h)
                self.boxes[mode].f.after(80, self.boxes[mode]._save)


# ───────────────────────── APP ──────────────────────────────
class App:
    def __init__(self):
        self.root    = tk.Tk()
        self.root.title("Auto Scan Tool")
        self.root.geometry("430x650")
        self.root.resizable(False, False)
        self.overlay = None
        self._worker: ScanWorker | None = None
        self._build_ui()
        self._update_ui()

    # ── UI ──────────────────────────────────────────────────
    def _build_ui(self):
        r = self.root

        self.win_lbl = tk.Label(r, text="— chưa chọn cửa sổ —",
                                font=("Consolas",9), fg="#666")
        self.win_lbl.pack(pady=(10,2))

        top = tk.Frame(r); top.pack()
        tk.Button(top, text="🖱 Chọn cửa sổ",
                  command=self.pick_window).pack(side="left", padx=4)
        tk.Button(top, text="🗂 Chọn thư mục ảnh",
                  command=self.pick_img_dir).pack(side="left", padx=4)

        tk.Frame(r, height=1, bg="#ccc").pack(fill="x", padx=12, pady=8)

        for label, mode in [("SCAN  (xanh lá)","scan"),
                             ("REFRESH  (vàng)","refresh"),
                             ("CONFIRM  (đỏ)",  "confirm")]:
            f = tk.Frame(r); f.pack(pady=3)
            tk.Label(f, text=label, width=20, anchor="w").pack(side="left")
            tk.Button(f, text="+ Box", width=7,
                      command=lambda m=mode: self.add_box(m)).pack(side="left",padx=2)
            tk.Button(f, text="− Box", width=7,
                      command=lambda m=mode: self.rem_box(m)).pack(side="left",padx=2)

        tk.Frame(r, height=1, bg="#ccc").pack(fill="x", padx=12, pady=8)

        ctrl = tk.Frame(r); ctrl.pack(pady=2)
        tk.Button(ctrl,text="▶ START",width=8,bg="#28a745",fg="white",
                  command=self.start).pack(side="left",padx=3)
        tk.Button(ctrl,text="■ STOP", width=8,bg="#dc3545",fg="white",
                  command=self.stop).pack(side="left",padx=3)
        tk.Button(ctrl,text="💾 SAVE",width=8,
                  command=self.save).pack(side="left",padx=3)
        tk.Button(ctrl,text="📂 LOAD",width=8,
                  command=self.load).pack(side="left",padx=3)

        self.match_lbl = tk.Label(r, text="Match: 0.000",
                                  font=("Consolas",14,"bold"), fg="#333")
        self.match_lbl.pack(pady=(10,2))

        bw = tk.Frame(r, bd=1, relief="sunken", width=390, height=16)
        bw.pack(); bw.pack_propagate(False)
        self.bar = tk.Frame(bw, bg="#17a2b8", height=16)
        self.bar.place(x=0, y=0, height=16, width=0)

        self.preview_lbl = tk.Label(r, bg="#111", width=390, height=160)
        self.preview_lbl.pack(pady=8)

        self.status_lbl = tk.Label(r, text="● Đã dừng", fg="#888",
                                   font=("Arial",9,"bold"))
        self.status_lbl.pack()

        self.log_lbl = tk.Label(r, text="", fg="#555",
                                font=("Consolas",8), wraplength=415, justify="left")
        self.log_lbl.pack(pady=(2,8))

    # ── ACTIONS ─────────────────────────────────────────────
    def pick_window(self):
        global selecting
        selecting = True
        self.status_lbl.config(text="● Click vào cửa sổ game...", fg="#cc8800")
        self.root.after(120, self._wait_click)

    def _wait_click(self):
        global selecting, hwnd
        if selecting:
            if win32api.GetAsyncKeyState(0x01) & 0x8000:
                pt   = win32api.GetCursorPos()
                hwnd = win32gui.WindowFromPoint(pt)
                name = win32gui.GetWindowText(hwnd)
                self.win_lbl.config(text=f"Cửa sổ: {name}  (hwnd={hwnd})")
                selecting = False
                self.status_lbl.config(text="● Đã chọn cửa sổ", fg="#28a745")
                log(f"[pick] hwnd={hwnd}  '{name}'")
            else:
                self.root.after(60, self._wait_click)

    def pick_img_dir(self):
        global IMG_DIR
        d = filedialog.askdirectory()
        if d: IMG_DIR = d; load_templates()

    def add_box(self, mode):
        if not hwnd: log("[ui] chưa chọn cửa sổ"); return
        if not self.overlay: self.overlay = Overlay(hwnd)
        self.overlay.add(mode)

    def rem_box(self, mode):
        if self.overlay: self.overlay.remove(mode)

    def start(self):
        if not hwnd: log("[start] chưa chọn cửa sổ!"); return
        if self._worker and self._worker.alive: self._worker.stop()
        load_templates()
        self._worker = ScanWorker()
        self._worker.start()
        self.status_lbl.config(text="● Đang chạy", fg="#28a745")
        log("[start] OK")

    def stop(self):
        if self._worker and self._worker.alive:
            self._worker.stop(); log("[stop] OK")
        self.status_lbl.config(text="● Đã dừng", fg="#888")

    def save(self):
        with open("config.json","w") as f: json.dump(rois,f,indent=2)
        log("[save] config.json")

    def load(self):
        global rois
        if not os.path.exists("config.json"):
            log("[load] không thấy config.json"); return
        with open("config.json") as f: data = json.load(f)
        for k, v in data.items():
            rois[k] = tuple(int(x) for x in v) if v else None
        if hwnd:
            if not self.overlay: self.overlay = Overlay(hwnd)
            self.overlay.load_boxes()
        log("[load] OK")

    # ── UI UPDATE ────────────────────────────────────────────
    def _update_ui(self):
        global preview_img, match_val, _last_log

        if preview_img is not None:
            try:
                rgb = cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB)
                rgb = cv2.resize(rgb,(390,160))
                imgtk = ImageTk.PhotoImage(Image.fromarray(rgb))
                self.preview_lbl.config(image=imgtk)
                self.preview_lbl.imgtk = imgtk
            except Exception: pass

        self.match_lbl.config(text=f"Match: {match_val:.3f}")
        bw    = int(match_val*390)
        color = ("#28a745" if match_val>0.6 else "#ffc107" if match_val>0.4 else "#17a2b8")
        self.bar.config(width=bw, bg=color)
        self.log_lbl.config(text=_last_log)
        self.root.after(120, self._update_ui)

    def run(self): self.root.mainloop()


if __name__ == "__main__":
    App().run()