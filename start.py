import subprocess
import webbrowser
import time
import os

# Путь к твоему Python-скрипту
script = os.path.join(os.path.dirname(__file__), "app.py")

# Запускаем main.py
process = subprocess.Popen(["python", script])

# Немного ждём, чтобы Flask успел запуститься
time.sleep(2)

# Открываем Firefox
firefox_path = r"C:\Program Files\Mozilla Firefox\firefox.exe"

webbrowser.register(
    "firefox",
    None,
    webbrowser.BackgroundBrowser(firefox_path)
)

webbrowser.get("firefox").open("http://127.0.0.1:5000")

# Ждём завершения main.py
process.wait()