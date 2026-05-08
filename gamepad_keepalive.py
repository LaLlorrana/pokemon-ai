# gamepad_keepalive.py
# Keeps the virtual Xbox 360 controller connected so you can configure RetroArch.
# Run this, then go configure RetroArch, then Ctrl+C to stop.

import time
import vgamepad as vg

print("[KeepAlive] Creating virtual Xbox 360 gamepad...")
pad = vg.VX360Gamepad()
time.sleep(1)
print("[KeepAlive] Controller is CONNECTED. You'll hear the Windows sound.")
print("[KeepAlive] Now go to RetroArch and reassign Port 1 to this controller.")
print("[KeepAlive] Press Ctrl+C here when done.\n")

try:
    while True:
        pad.update()
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\n[KeepAlive] Done — controller disconnecting.")
