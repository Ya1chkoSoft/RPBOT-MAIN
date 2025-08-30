import os
from dotenv import load_dotenv

def read_config_txt(path="config.txt"):
    config = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    return config

load_dotenv()

if os.getenv("OWNER_ID") and os.getenv("BOT_ID") and os.getenv("BOT"):
    OWNER_ID = int(os.getenv("OWNER_ID"))
    BOT_ID = int(os.getenv("BOT_ID"))
    BOT = os.getenv("BOT")
    LOG_ALL_MESSAGES = os.getenv("LOG_ALL_MESSAGES", "False").lower() == "true"
else:
    config_txt = read_config_txt()
    OWNER_ID = int(config_txt.get("OWNER_ID", 0))
    BOT_ID = int(config_txt.get("BOT_ID", 0))
    BOT = config_txt.get("BOT", "")
    LOG_ALL_MESSAGES = config_txt.get("LOG_ALL_MESSAGES", "False").lower() == "true"