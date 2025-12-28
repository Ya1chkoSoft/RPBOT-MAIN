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
    """
    Генерирует множители и веса для слотов на основе заданных параметров.
    """
    multipliers = {}
    weights = []
    
    # Применяем коэффициенты к каждому символу по порядку
    for i, sym in enumerate(symbols):
        # Множитель растет: base + step * index
        multipliers[sym] = base_mult + mult_step * i
        
        # Вес падает (реже выпадает): base + step * index
        # Используем max(1, ...) чтобы вес всегда был минимум 1.
        weight = max(1, base_weight + weight_step * i) 
        weights.append(weight)
        
    return multipliers, weights

def read_config_txt(path="config.txt"):
    """Читает конфигурационные переменные из файла config.txt."""
    config = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                # Удаляем часть строки, которая является комментарием
                if '#' in line:
                    line = line.split('#', 1)[0].strip()
                    if not line: # Если остался только комментарий, пропускаем
                        continue
                        
                if "=" in line:
                    key, value = line.split("=", 1)
                    # Убедимся, что значение также очищено от лишних пробелов
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

        # 🔥 НОВАЯ КОНСТАНТА: Бонус за Влияние
        "DAILY_BONUS_RATIO": 100, 

        # --- Настройки Казино (Параметры для 1x3) ---
        "SLOT_SYMBOLS": '["🍒", "🍋", "🦷", "⭐", "👼🏿"]', # Храним как строку, чтобы легко читать из TXT
        "CASINO_BASE_MULT": 2.0,
        "CASINO_MULT_STEP": 1.0,
        "CASINO_BASE_WEIGHT": 30,
        "CASINO_WEIGHT_STEP": -5,
        
        # 🔥 НОВЫЙ БЛОК: Настройки Казино (Параметры для 3x3)
        "SLOT3X3_SYMBOLS": '["🟡", "🟢", "🔴", "💎"]',
        "SLOT3X3_BASE_MULT": 1.0,                    
        "SLOT3X3_MULT_STEP": 2.0,                    
        "SLOT3X3_BASE_WEIGHT": 40,                   
        "SLOT3X3_WEIGHT_STEP": -15,                  
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
# 🔥 НОВАЯ КОНСТАНТА
DAILY_BONUS_RATIO = int(CONFIG["DAILY_BONUS_RATIO"])
REVIEW_COOLDOWN_DAYS = int(CONFIG.get("REVIEW_COOLDOWN_DAYS", 7))  # Новая константа для оценки страны

# 3. Казино 1x3: Парсинг и Генерация
SLOT_SYMBOLS_RAW = CONFIG["SLOT_SYMBOLS"]
try:
    # Безопасное чтение списка
    SLOT_SYMBOLS = ast.literal_eval(SLOT_SYMBOLS_RAW)
except:
    # Используем дефолтный список, если не удалось распарсить
    SLOT_SYMBOLS = ast.literal_eval(STANDARD["SLOT_SYMBOLS"])

# Генерация финальных констант для 1x3:
SYMBOL_MULTIPLIERS, SYMBOL_WEIGHTS = generate_symbols_data(
    SLOT_SYMBOLS,
    base_mult=float(CONFIG["CASINO_BASE_MULT"]),
    mult_step=float(CONFIG["CASINO_MULT_STEP"]),
    base_weight=int(CONFIG["CASINO_BASE_WEIGHT"]),
    weight_step=int(CONFIG["CASINO_WEIGHT_STEP"])
)

# 4. 🔥 НОВЫЙ БЛОК: Казино 3x3: Парсинг и Генерация
SLOT3X3_SYMBOLS_RAW = CONFIG["SLOT3X3_SYMBOLS"]
try:
    SLOT3X3_SYMBOLS = ast.literal_eval(SLOT3X3_SYMBOLS_RAW)
except:
    SLOT3X3_SYMBOLS = ast.literal_eval(STANDARD["SLOT3X3_SYMBOLS"])

SLOT3X3_MULTIPLIERS, SLOT3X3_WEIGHTS = generate_symbols_data(
    SLOT3X3_SYMBOLS,
    base_mult=float(CONFIG["SLOT3X3_BASE_MULT"]),
    mult_step=float(CONFIG["SLOT3X3_MULT_STEP"]),
    base_weight=int(CONFIG["SLOT3X3_BASE_WEIGHT"]),
    weight_step=int(CONFIG["SLOT3X3_WEIGHT_STEP"])
)