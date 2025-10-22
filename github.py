import asyncio
import os
import threading
import time
import subprocess
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# ----------------- CONFIG -----------------
BOT_TOKEN = ""
CHECK_URL = ""        # IP or domain to ping if no proxy
PROXY_URL = ""                       # Leave empty ("") to disable proxy
PING_INTERVAL = 10                   # seconds
GROUPS_FILE = "../groups.txt"
# ------------------------------------------

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

light_on = None
group_ids = set()
loop = None  # main asyncio loop reference

# ----- Create requests session -----
session = requests.Session()
if PROXY_URL.strip():
    session.proxies = {"http": PROXY_URL, "https": PROXY_URL}
    print(f"[INFO] Using proxy: {PROXY_URL}")
else:
    print("[INFO] No proxy configured — will use system ping.")
session.timeout = 5


# =============== GROUP FILE HANDLING ===============
def load_groups():
    """Load group IDs from file into set."""
    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    group_ids.add(int(line))


def save_groups():
    """Save current group IDs to file."""
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        for gid in group_ids:
            f.write(f"{gid}\n")
# ==================================================


# =============== CONNECTION CHECKS ===============
def http_check() -> bool:
    """Check site via HTTP request through proxy."""
    try:
        r = session.get("https://1.1.1.1", timeout=5)
        print(f"[HTTP] Status: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"[HTTP ERROR] {e}")
        return False


def ping_check() -> bool:
    """Ping the IP or domain directly (no proxy)."""
    try:
        param = "-n" if os.name == "nt" else "-c"
        result = subprocess.run(
            ["ping", param, "1", CHECK_URL],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        success = result.returncode == 0 or "TTL expired" in result.stdout
        print(f"[PING] {CHECK_URL} → {'OK' if success else 'FAIL'}")
        return success
    except Exception as e:
        print(f"[PING ERROR] {e}")
        return False
# ==================================================


async def notify_groups(status: bool):
    """Notify all registered groups about current status."""
    text = "💡 Світло з'явилось!" if status else "⚫ Світло зникло!"
    for gid in group_ids.copy():
        try:
            await bot.send_message(gid, text)
        except Exception as e:
            print(f"[WARN] Failed to send to {gid}: {e}")


def ping_loop():
    """Background loop checking connection periodically."""
    global light_on

    while True:
        if PROXY_URL.strip():
            new_status = http_check()
        else:
            new_status = ping_check()

        if light_on is None:
            light_on = new_status
            asyncio.run_coroutine_threadsafe(notify_groups(light_on), loop)
        elif new_status != light_on:
            light_on = new_status
            asyncio.run_coroutine_threadsafe(notify_groups(light_on), loop)

        time.sleep(PING_INTERVAL)


# =============== BOT COMMANDS ===============
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    chat_id = message.chat.id
    if chat_id not in group_ids:
        group_ids.add(chat_id)
        save_groups()
    await message.reply("👋 Бот активний! Буду повідомляти про стан світла.")


@dp.message(Command("light"))
async def light_status(message: types.Message):
    if light_on is None:
        await message.reply("⏳ Перевіряю стан...")
    elif light_on:
        await message.reply("💡 Світло Є.")
    else:
        await message.reply("⚫ Світла Немає.")
# ===========================================


async def main():
    global loop
    loop = asyncio.get_running_loop()
    load_groups()
    threading.Thread(target=ping_loop, daemon=True).start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
