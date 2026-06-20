#!/usr/bin/env python3
import os
import subprocess
import sys

SRC = "/app/static/images/navbarlogo.png"
DEST = "/app/static/favicon.ico"


def ensure_pillow():
    try:
        return True
    except Exception:
        print("Pillow not found, attempting to install via pip...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
            import importlib

            importlib.invalidate_caches()
            return True
        except Exception as e:
            print("Failed to install Pillow:", e)
            return False


def make_favicon():
    from PIL import Image

    if not os.path.exists(SRC):
        print("Source image not found at", SRC)
        return False
    try:
        img = Image.open(SRC)
        img.save(DEST, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
        print("Wrote", DEST)
        return True
    except Exception as e:
        print("Failed to create favicon:", e)
        return False


def collectstatic():
    try:
        subprocess.check_call(
            [sys.executable, "manage.py", "collectstatic", "--noinput"]
        )
        return True
    except Exception as e:
        print("collectstatic failed:", e)
        return False


def ls_staticfiles():
    try:
        print("\n/staticfiles root listing:")
        subprocess.check_call(["ls", "-l", "/app/staticfiles"])
    except Exception:
        pass


if __name__ == "__main__":
    ok = ensure_pillow()
    if not ok:
        sys.exit(2)
    ok = make_favicon()
    if not ok:
        sys.exit(3)
    collectstatic()
    ls_staticfiles()
