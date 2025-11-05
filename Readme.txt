# Chương trình AutoClick

## Tóm tắt
AutoClick là công cụ tự động hóa click chuột và nhập phím tại các vị trí cụ thể trên màn hình. Nó hữu ích cho các tác vụ lặp lại như điền form, chơi game, hoặc kiểm tra giao diện.

## Hướng dẫn sử dụng

### Các nút và chức năng

| Tên nút | Phím tắt | Chức năng                                      |
|---------|----------|------------------------------------------------|
| E       | E        | Thêm ô vuông mới tại vị trí chuột hiện tại.    |
| A       | A        | Bắt đầu tự động hóa (giống Start).             |
| S       | S        | Lưu cài đặt hiện tại vào file JSON.            |
| I       | I        | Tải cài đặt từ file JSON.                      |
| U       | U        | Hoàn tác hành động cuối (hoặc Ctrl+Z).         |
| X       | X        | Xóa ô vuông đã chọn (hoặc Delete/Backspace).   |
| T       | T        | Dừng tự động hóa (giống Stop).                |
| Start   | R        | Bắt đầu trình tự tự động hóa.                  |
| Stop    | T        | Dừng trình tự tự động hóa.                     |

### Cách dùng
1. Nhấn `E` để tạo ô vuông tại vị trí chuột.
2. Chỉnh các thông số:  
   - **N**: Thứ tự thực hiện (1, 2, 3, ...).  
   - **A**: Số lần click chuột.  
   - **L**: Phím/chuỗi để nhập (ví dụ: `alo`, `F5`).  
   - **T**: Thời gian chờ (MM:SS).  
3. Nhấn `Start` hoặc `A` để chạy tự động hóa.
4. Nhấn `Stop` hoặc `T` để dừng.

##############################################################################

# AutoClick Program

## Summary
AutoClick is a tool that automates mouse clicks and keystrokes at specific locations on the screen. It is useful for repetitive tasks such as filling out forms, playing games, or testing interfaces.

## How to use

### Buttons and functions

| Button name | Shortcut key | Function |
|---------|----------|------------------------------------------------|
| E | E | Adds a new square at the current mouse position. |
| A | A | Starts automation (similar to Start). |
| S | S | Saves current settings to a JSON file. |
| I | I | Loads settings from a JSON file. |
| U | U | Undo last action (or Ctrl+Z). |
| X | X | Deletes selected square (or Delete/Backspace). |
| T | T | Stops automation (similar to Stop). |
| Start | R | Starts automation sequence. |
| Stop | T | Stop the automation sequence. |

### How to use
1. Press `E` to create a square at the mouse position.
2. Adjust the parameters:

- **N**: Execution order (1, 2, 3, ...).

- **A**: Number of mouse clicks.

- **L**: Key/sequence to enter (eg: `alo`, `F5`).

- **T**: Waiting time (MM:SS).
3. Press `Start` or `A` to run the automation.
4. Press `Stop` or `T` to stop.
