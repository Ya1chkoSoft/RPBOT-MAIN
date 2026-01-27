import os
import sys
import ast # Для безопасного чтения списков из текстового файла
from dotenv import load_dotenv
# 1. FIX PATH (добавление пути, как вы просили)
# Это нужно для корректных относительных импортов
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ------------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ------------------------------------------------------------
def generate_symbols_data(symbols, base_mult, mult_step, base_weight, weight_step):
    multipliers = {}
    weights = []
    
    # Берем модуль, чтобы если ты ночью впишешь -1.8, всё не взорвалось
    div = max(1.05, abs(weight_step))

    for i, sym in enumerate(symbols):
        # Множители делаем красивые: 0.8, 1.4, 2.0...
        m = base_mult + (mult_step * i)
        multipliers[sym] = round(m, 2)
        
        # Веса падают мягко: 100, 55, 30, 17, 9, 5
        w = base_weight / (div ** i)
        weights.append(round(max(0.1, w), 2))
        
    return multipliers, weights

def read_config_txt(path="config.txt"):
    """Читает конфигурационные переменные из файла config.txt."""
    config = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(script_dir, path)
    
    try:
        with open(full_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                if '#' in line:
                    line = line.split('#', 1)[0].strip()
                    if not line:
                        continue
                        
                if "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip() 
    except FileNotFoundError:
        pass
    return config

def get_standard_settings() -> dict:
    """Стандартные настройки по умолчанию для всех констант."""
    return {
        # --- Основные настройки ---
        "OWNER_ID": 0,
        "BOT_ID": 0,
        "BOT": "", 
        "LOG_ALL_MESSAGES": "False",
        
        # --- Игровые константы (Общие) ---
        "FUZZY_MATCH_THRESHOLD": 75,
        "RP_TO_INFLUENCE_RATIO": 1000,
        "MIN_POINTS_TO_CREATE_COUNTRY": 500,
        "COUNTRY_CREATION_COOLDOWN_HOURS": 72,

        #Бонус за Влияние
        "DAILY_BONUS_RATIO": 100, 

        # --- Настройки Казино (Параметры для 1x3) ---
        "SLOT_SYMBOLS": '["🍒", "🍋", "🦷", "⭐", "👼🏿"]', # Храним как строку, чтобы легко читать из TXT
        "CASINO_BASE_MULT": 1.2,
        "CASINO_MULT_STEP": 1.5,
        "CASINO_BASE_WEIGHT": 50,
        "CASINO_WEIGHT_DIVISOR": 2.8,
        
        #Настройки Казино (Параметры для 3x3)
        "SLOT3X3_SYMBOLS": ["🎸", "👼🏿", "🐸", "✅", "🚹"],
        "SLOT3X3_BASE_MULT": 0.8,                    
        "SLOT3X3_MULT_STEP": 2.0,                    
        "SLOT3X3_BASE_WEIGHT": 100,                   
        "SLOT3X3_WEIGHT_STEP": 3.5,                  
    }

# ------------------------------------------------------------
# ОСНОВНАЯ ЛОГИКА ЗАГРУЗКИ КОНФИГА
# ------------------------------------------------------------
load_dotenv()

STANDARD = get_standard_settings()
TXT_CONF = read_config_txt()

# 1. Объединяем STANDARD -> CONFIG.TXT. 
# В этом словаре будут все параметры в строковом виде.
CONFIG = STANDARD.copy()
for k, v in TXT_CONF.items():
    CONFIG[k] = v

# 2. Перезапись из .env (если есть)
CONFIG["OWNER_ID"] = os.getenv("OWNER_ID", CONFIG["OWNER_ID"])
CONFIG["BOT"] = os.getenv("BOT", CONFIG["BOT"])
# ... (и другие настройки, которые вы хотите взять из .env)

# ------------------------------------------------------------
# ФИНАЛЬНАЯ ИНИЦИАЛИЗАЦИЯ (ПРЕОБРАЗОВАНИЕ ТИПОВ)
# ------------------------------------------------------------

# 1. Основные константы
OWNER_ID = int(CONFIG["OWNER_ID"])
BOT_ID = int(CONFIG.get("BOT_ID", 0)) # Используем .get для большей безопасности
BOT_TOKEN = CONFIG["BOT"]
LOG_ALL_MESSAGES = str(CONFIG["LOG_ALL_MESSAGES"]).lower() == "true"

# 2. Игровые константы
FUZZY_MATCH_THRESHOLD = int(CONFIG["FUZZY_MATCH_THRESHOLD"])
RP_TO_INFLUENCE_RATIO = int(CONFIG["RP_TO_INFLUENCE_RATIO"])
MIN_POINTS_TO_CREATE_COUNTRY = int(CONFIG["MIN_POINTS_TO_CREATE_COUNTRY"])
COUNTRY_CREATION_COOLDOWN_HOURS = int(CONFIG["COUNTRY_CREATION_COOLDOWN_HOURS"])
DAILY_BONUS_RATIO = int(CONFIG["DAILY_BONUS_RATIO"])
REVIEW_COOLDOWN_DAYS = int(CONFIG.get("REVIEW_COOLDOWN_DAYS", 7))  # Новая константа для оценки страны

def parse_emoji_list(s):
    """
    Парсит список эмодзи из строки, например:
    '["🌚", "⚡", "💎"]' -> ['🌚', '⚡', '💎']
    """
    s = s.strip()
    if not s.startswith('[') or not s.endswith(']'):
        return []
    
    # Удаляем квадратные скобки
    s = s[1:-1]
    
    # Разделяем по запятым
    items = [item.strip() for item in s.split(',')]
    
    # Убираем кавычки (если есть)
    result = []
    for item in items:
        item = item.strip()
        if item.startswith('"') and item.endswith('"'):
            item = item[1:-1]
        elif item.startswith("'") and item.endswith("'"):
            item = item[1:-1]
        if item:
            result.append(item)
    
    return result

# 3. Казино 1x3: Парсинг и Генерация
SLOT_SYMBOLS_RAW = CONFIG["SLOT_SYMBOLS"]
try:
    SLOT_SYMBOLS = parse_emoji_list(SLOT_SYMBOLS_RAW)
except:
    SLOT_SYMBOLS = parse_emoji_list(STANDARD["SLOT_SYMBOLS"])

# Генерация финальных констант для 1x3:
SYMBOL_MULTIPLIERS, SYMBOL_WEIGHTS = generate_symbols_data(
    SLOT_SYMBOLS,
    base_mult=float(CONFIG["CASINO_BASE_MULT"]),
    mult_step=float(CONFIG["CASINO_MULT_STEP"]),
    base_weight=int(CONFIG["CASINO_BASE_WEIGHT"]),
    weight_step=float(CONFIG["CASINO_WEIGHT_DIVISOR"])
)

# 4. Казино 3x3: Парсинг и Генерация
SLOT3X3_SYMBOLS_RAW = CONFIG["SLOT3X3_SYMBOLS"]
try:
    SLOT3X3_SYMBOLS = parse_emoji_list(SLOT3X3_SYMBOLS_RAW)
except:
    SLOT3X3_SYMBOLS = parse_emoji_list(STANDARD["SLOT3X3_SYMBOLS"])

SLOT3X3_MULTIPLIERS, SLOT3X3_WEIGHTS = generate_symbols_data(
    SLOT3X3_SYMBOLS,
    base_mult=float(CONFIG["SLOT3X3_BASE_MULT"]),
    mult_step=float(CONFIG["SLOT3X3_MULT_STEP"]),
    base_weight=int(CONFIG["SLOT3X3_BASE_WEIGHT"]),
    weight_step=float(CONFIG["SLOT3X3_WEIGHT_STEP"])
)