# ============================================================
#  main.py — PokeBot entry point
# ============================================================
#
#  Run with:  python main.py
# ============================================================

import tkinter as tk
from chat_window import ChatWindow


def main():
    # Create the virtual gamepad immediately so RetroArch can detect it at launch.
    try:
        from controller import _get_gamepad
        _get_gamepad()
        print("[PokeBot] Virtual gamepad ready.")
    except Exception as e:
        print(f"[PokeBot] Gamepad init failed: {e}")
    root = tk.Tk()
    root.resizable(True, True)

    # Make PokeBot window non-activating so it never steals focus from RetroArch.
    # WS_EX_NOACTIVATE (0x08000000) + WS_EX_TOPMOST (0x00000008) —
    # the window stays on top but clicking it or updating it won't pull
    # keyboard focus away from RetroArch.
    import ctypes
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    GWL_EXSTYLE      = -20
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOPMOST    = 0x00000008
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                        style | WS_EX_NOACTIVATE | WS_EX_TOPMOST)

    app = ChatWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
