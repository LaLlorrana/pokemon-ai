# Run this and press your side mouse buttons to see which is which.
# Ctrl+C to exit.

from pynput import mouse

def on_click(x, y, button, pressed):
    if pressed:
        print(f"  Button pressed: {button}  (name: {button.name if hasattr(button, 'name') else button})")

print("Press your side mouse buttons to identify them. Ctrl+C to exit.\n")
with mouse.Listener(on_click=on_click) as l:
    try:
        l.join()
    except KeyboardInterrupt:
        print("Done.")
