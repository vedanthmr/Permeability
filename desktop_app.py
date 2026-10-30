"""
desktop_app.py
==============
Native Windows Desktop Application Launcher for AdaptShield.
Starts the backend security server in a background thread and presents
the full AdaptShield interface in a native desktop window via pywebview.
Includes graceful fallback to the default browser if pywebview is unavailable.
"""

import os
import sys
import time
import socket
import threading
import webbrowser
from pathlib import Path

# Path resolution for standalone PyInstaller bundle & regular Python
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)).resolve()
RUN_DIR = Path(sys.executable).parent.resolve() if getattr(sys, "frozen", False) else BASE_DIR

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import requests


def find_free_port(default_port: int = 8000) -> int:
    """Find an available TCP port for the local server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", default_port)) != 0:
            return default_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def run_server_thread(host: str, port: int):
    """Run uvicorn server in background thread."""
    # pyrefly: ignore[missing-import]
    import uvicorn
    from server import app
    uvicorn.run(app, host=host, port=port, log_level="warning")


def main():
    os.environ["ADAPTSHIELD_MODE"] = "desktop"
    host = "127.0.0.1"
    port = find_free_port(int(os.environ.get("PORT", "8000")))
    url = f"http://{host}:{port}"

    print("=" * 60)
    print("  AdaptShield v2.0 — Dual-Layer AI Security Console")
    print("  Mode: Native Windows Desktop")
    print(f"  Local Endpoint: {url}")
    print("=" * 60)

    # Start server daemon thread
    server_thread = threading.Thread(target=run_server_thread, args=(host, port), daemon=True)
    server_thread.start()

    # Wait for server health endpoint
    print("[Desktop] Waiting for security pipeline to initialize...")
    ready = False
    for _ in range(40):
        try:
            resp = requests.get(f"{url}/status", timeout=1)
            if resp.status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.25)

    if not ready:
        print("[!] Server failed to respond within timeout. Retrying...")

    # Launch PyWebView window
    opened_webview = False
    try:
        import webview
        print("[Desktop] Opening native window via pywebview...")
        window = webview.create_window(
            title="AdaptShield — AI Prompt & Document Security",
            url=url,
            width=1280,
            height=820,
            min_size=(960, 640),
            text_select=True,
            zoomable=True
        )
        opened_webview = True
        webview.start()
    except Exception as e:
        print(f"[Desktop] pywebview window could not be opened: {e}")

    # Fallback to web browser if pywebview fails
    if not opened_webview:
        print("[Desktop] Falling back to default web browser...")
        webbrowser.open(url)
        print(f"AdaptShield is active at {url}. Keep this window open.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nExiting AdaptShield Desktop.")


if __name__ == "__main__":
    main()
