"""The computer's own window for choosing a folder, for the page: a browser does not give a page the path of a folder it picks.

The window is opened by a small separate Python process with tkinter, so it works from any thread of the server and on Windows, macOS and Linux
(macOS lets a window open only from the main thread of a process).
"""
import subprocess
import sys

_SCRIPT = """
import sys, tkinter as tk
from tkinter import filedialog
root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
path = filedialog.askdirectory(parent=root, initialdir=sys.argv[1] or None, title=sys.argv[2], mustexist=False)
print(path or "")
"""


def choose_folder(start: str = "", title: str = "Choose a folder") -> str:
    """The folder chosen in the window (a new one can be made there), or ``""`` when it was closed without one. `ValueError` when this
    Python cannot open the window (no tkinter, no display): the path can still be typed."""
    try:
        done = subprocess.run([sys.executable, "-c", _SCRIPT, start or "", title], capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ValueError(f"the folder window did not open ({e}); type the path instead") from None
    if done.returncode != 0:
        why = (done.stderr.strip().splitlines() or ["unknown error"])[-1]
        raise ValueError(f"this computer cannot open a folder window ({why}); type the path instead")
    return done.stdout.strip()
