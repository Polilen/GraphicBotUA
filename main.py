import telebot
from telebot import types
from datetime import datetime, timedelta
import threading
import time
import json
import os
from collections import Counter
import base64
import requests

# Токен твого бота (отримай у @BotFather)
BOT_TOKEN = "7820077415:AAG7yXnwfwlNyQXQ6AWjwin7eTPuczoj4LY"

bot = telebot.TeleBot(BOT_TOKEN)

# GitHub налаштування
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "твій_username/твій_репозиторій").strip()
# Сховище зустрічей, станів користувачів та налаштувань
meetings = {}
user_states = {}
user_settings = {}
meetings_history = {}
DATA_FILE = "meetings_data.json"
SETTINGS_FILE = "user_settings.json"
HISTORY_FILE = "meetings_history.json"


# --- Функції для GitHub ---
def save_file_to_github(file_path):
    """
    Зберігає конкретний JSON файл у GitHub
    """
    token = GITHUB_TOKEN
    repo = GITHUB_REPO
    
    if not token:
        return
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
        headers = {"Authorization": f"Bearer {token}"}
        
        # Отримуємо SHA поточного файлу
        r = requests.get(url, headers=headers)
        sha = r.json().get("sha") if r.status_code == 200 else None
        
        # Кодуємо файл у Base64
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        
        data = {
            "message": f"update {file_path}",
            "content": encoded_content,
            "sha": sha
        }
        
        response = requests.put(url, headers=headers, json=data)
        if response.status_code in (200, 201):
            print(f"✅ {file_path} успішно оновлено у GitHub")
        else:
            print(f"❌ Не вдалося оновити {file_path} у GitHub: {response.text}")
    except Exception as e:
        print(f"❌ Помилка при збереженні {file_path} в GitHub: {e}")

def load_file_from_github(file_path):
    """
    Завантажує конкретний JSON файл з GitHub
    """
    token = GITHUB_TOKEN
    repo = GITHUB_REPO
    
    if not token:
        return None
    
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            content = response.json()
            decoded = base64.b64decode(content["content"]).decode("utf-8")
            print(f"✅ {file_path} завантажено з GitHub")
            return json.loads(decoded)
        else:
            return None
    except Exception as e:
        print(f"❌ Помилка при завантаженні {file_path} з GitHub: {e}")
        return None
# Предвизначені теги з емодзі
TAGS = {
    'робота': '💼',
    'особисте': '👤',
    'спорт': '⚽',
    'навчання': '📚',
    'здоров\'я': '🏥',
    'сім\'я': '👨‍👩‍👧',
    'покупки': '🛒',
    'важливе': '⭐'
}

# Функція для визначення чи діє літній час в Європі/Україні
def is_dst_active_europe():
    """
    Літній час в Європі: останнє воскресення березня (03:00) - останнє воскресення жовтня (04:00)
    """
    now = datetime.utcnow()
    year = now.year
    
    # Знаходимо останнє воскресення березня
    march_last_day = datetime(year, 3, 31)
    while march_last_day.weekday() != 6:  # 6 = неділя
        march_last_day -= timedelta(days=1)
    dst_start = march_last_day.replace(hour=1, minute=0, second=0, microsecond=0)
    
    # Знаходимо останнє воскресення жовтня
    october_last_day = datetime(year, 10, 31)
    while october_last_day.weekday() != 6:
        october_last_day -= timedelta(days=1)
    dst_end = october_last_day.replace(hour=1, minute=0, second=0, microsecond=0)
    
    return dst_start <= now < dst_end

# Функція для визначення чи діє літній час в США/Канаді
def is_dst_active_north_america():
    """
    Літній час в Північній Америці: друге воскресення березня - перше воскресення листопада
    """
    now = datetime.utcnow()
    year = now.year
    
    # Знаходимо друге воскресення березня
    march_first = datetime(year, 3, 1)
    days_until_sunday = (6 - march_first.weekday()) % 7
    first_sunday = march_first + timedelta(days=days_until_sunday)
    dst_start = first_sunday + timedelta(days=7, hours=2)
    
    # Знаходимо перше воскресення листопада
    november_first = datetime(year, 11, 1)
    days_until_sunday = (6 - november_first.weekday()) % 7
    first_sunday_nov = november_first + timedelta(days=days_until_sunday)
    dst_end = first_sunday_nov.replace(hour=2, minute=0, second=0, microsecond=0)
    
    return dst_start <= now < dst_end

# Функція для визначення чи діє літній час в Австралії/Новій Зеландії
def is_dst_active_australia():
    """
    Літній час в Австралії: перше воскресення жовтня - перше воскресення квітня
    """
    now = datetime.utcnow()
    year = now.year
    
    # Знаходимо перше воскресення жовтня
    october_first = datetime(year, 10, 1)
    days_until_sunday = (6 - october_first.weekday()) % 7
    first_sunday_oct = october_first + timedelta(days=days_until_sunday)
    dst_start = first_sunday_oct.replace(hour=2, minute=0, second=0, microsecond=0)
    
    # Знаходимо перше воскресення квітня наступного року
    april_first = datetime(year + 1, 4, 1)
    days_until_sunday = (6 - april_first.weekday()) % 7
    first_sunday_apr = april_first + timedelta(days=days_until_sunday)
    dst_end = first_sunday_apr.replace(hour=2, minute=0, second=0, microsecond=0)
    
    # Австралійський літній час працює "навпаки" (жовтень-квітень)
    return now >= dst_start or now < dst_end

# Функція для отримання популярних часових поясів з урахуванням DST
def get_popular_timezones():
    europe_dst = is_dst_active_europe()
    na_dst = is_dst_active_north_america()
    aus_dst = is_dst_active_australia()
    
    timezones = []
    
    # Північна Америка
    if na_dst:
        timezones.extend([
            (-7, "UTC-7 (Лос-Анджелес) ⏰"),
            (-6, "UTC-6 (Денвер) ⏰"),
            (-5, "UTC-5 (Нью-Йорк, Мехіко) ⏰"),
            (-4, "UTC-4 (Каракас)")
        ])
    else:
        timezones.extend([
            (-8, "UTC-8 (Лос-Анджелес) ❄️"),
            (-7, "UTC-7 (Денвер) ❄️"),
            (-6, "UTC-6 (Нью-Йорк, Мехіко) ❄️"),  
            (-5, "UTC-5 (Каракас)")
        ])
    
    # Південна Америка
    timezones.append((-3, "UTC-3 (Буенос-Айрес, Сан-Паулу)"))
    
    # Європа
    if europe_dst:
        timezones.extend([
            (1, "UTC+1 (Лондон, Дублін) ⏰"),
            (2, "UTC+2 (Париж, Берлін, Рим) ⏰"),
            (3, "UTC+3 (Київ, Афіни) ⏰")
        ])
    else:
        timezones.extend([
            (0, "UTC (Лондон, Дублін) ❄️"),
            (1, "UTC+1 (Париж, Берлін, Рим) ❄️"),
            (2, "UTC+2 (Київ, Афіни) ❄️")
        ])
    
    # Близький Схід та Азія (без DST)
    timezones.extend([
        (3, "UTC+3 (Ер-Ріяд)"),
        (4, "UTC+4 (Дубай, Баку)"),
        (5, "UTC+5 (Ташкент, Карачі)"),
        (6, "UTC+6 (Алмати, Дакка)"),
        (7, "UTC+7 (Бангкок, Ханой)"),
        (8, "UTC+8 (Пекін, Сінгапур, Гонконг)"),
        (9, "UTC+9 (Токіо, Сеул)")
    ])
    
    # Австралія та Океанія
    if aus_dst:
        timezones.extend([
            (11, "UTC+11 (Сідней, Мельбурн) ⏰"),
            (13, "UTC+13 (Окленд) ⏰")
        ])
    else:
        timezones.extend([
            (10, "UTC+10 (Сідней, Мельбурн) ❄️"),
            (12, "UTC+12 (Окленд) ❄️")
        ])
    
    return timezones

# Функція для отримання рядка часового поясу
def get_timezone_string(tz_offset):
    europe_dst = is_dst_active_europe()
    na_dst = is_dst_active_north_america()
    aus_dst = is_dst_active_australia()
    
    # Європа
    if tz_offset == 0 and not europe_dst:
        return "UTC (Лондон) ❄️"
    elif tz_offset == 1 and europe_dst:
        return "UTC+1 (Лондон) ⏰"
    elif tz_offset == 1 and not europe_dst:
        return "UTC+1 (Париж, Берлін) ❄️"
    elif tz_offset == 2 and europe_dst:
        return "UTC+2 (Париж, Берлін) ⏰"
    elif tz_offset == 2 and not europe_dst:
        return "UTC+2 (Київ, Афіни) ❄️"
    elif tz_offset == 3 and europe_dst:
        return "UTC+3 (Київ, Афіни) ⏰"
    
    # Північна Америка
    elif tz_offset == -8 and not na_dst:
        return "UTC-8 (Лос-Анджелес) ❄️"
    elif tz_offset == -7 and na_dst:
        return "UTC-7 (Лос-Анджелес) ⏰"
    elif tz_offset == -7 and not na_dst:
        return "UTC-7 (Денвер) ❄️"
    elif tz_offset == -6 and na_dst:
        return "UTC-6 (Денвер) ⏰"
    elif tz_offset == -6 and not na_dst:
        return "UTC-6 (Мехіко) ❄️"
    elif tz_offset == -5 and na_dst:
        return "UTC-5 (Нью-Йорк) ⏰"
    elif tz_offset == -5 and not na_dst:
        return "UTC-5 (Нью-Йорк, Богота) ❄️"
    
    # Австралія
    elif tz_offset == 10 and not aus_dst:
        return "UTC+10 (Сідней) ❄️"
    elif tz_offset == 11 and aus_dst:
        return "UTC+11 (Сідней) ⏰"
    elif tz_offset == 12 and not aus_dst:
        return "UTC+12 (Окленд) ❄️"
    elif tz_offset == 13 and aus_dst:
        return "UTC+13 (Окленд) ⏰"
    
    # Інші часові пояси (без DST)
    else:
        timezones_static = {
            -12: "UTC-12",
            -11: "UTC-11",
            -10: "UTC-10 (Гонолулу)",
            -9: "UTC-9 (Анкоридж)",
            -4: "UTC-4 (Каракас)",
            -3: "UTC-3 (Буенос-Айрес)",
            -2: "UTC-2",
            -1: "UTC-1",
            3: "UTC+3 (Ер-Ріяд)",
            4: "UTC+4 (Дубай, Баку)",
            5: "UTC+5 (Ташкент)",
            6: "UTC+6 (Алмати)",
            7: "UTC+7 (Бангкок)",
            8: "UTC+8 (Пекін, Сінгапур)",
            9: "UTC+9 (Токіо, Сеул)",
            11: "UTC+11",
            14: "UTC+14"
        }
        return timezones_static.get(tz_offset, f"UTC{tz_offset:+d}")

# Завантаження даних при старті
def load_meetings():
    global meetings
    # Спочатку пробуємо завантажити з GitHub
    github_data = load_file_from_github(DATA_FILE)
    if github_data is not None:
        meetings = github_data
        return
    
    # Якщо GitHub недоступний, працюємо з локальним файлом
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            meetings = json.load(f)

def load_settings():
    global user_settings
    # Спочатку пробуємо завантажити з GitHub
    github_data = load_file_from_github(SETTINGS_FILE)
    if github_data is not None:
        user_settings = github_data
        return
    
    # Якщо GitHub недоступний, працюємо з локальним файлом
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            user_settings = json.load(f)

def load_history():
    global meetings_history
    # Спочатку пробуємо завантажити з GitHub
    github_data = load_file_from_github(HISTORY_FILE)
    if github_data is not None:
        meetings_history = github_data
        return
    
    # Якщо GitHub недоступний, працюємо з локальним файлом
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    meetings_history = json.loads(content)  
                else:
                    meetings_history = {}
        except json.JSONDecodeError:
            meetings_history = {}
            save_history()
    else:
        meetings_history = {}
# Збереження даних
def save_meetings():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(meetings, f, ensure_ascii=False, indent=2)
    save_file_to_github(DATA_FILE)

def save_settings():
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_settings, f, ensure_ascii=False, indent=2)
    save_file_to_github(SETTINGS_FILE)

def save_history():
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(meetings_history, f, ensure_ascii=False, indent=2)
    save_file_to_github(HISTORY_FILE)

# Отримати часовий пояс користувача
def get_user_timezone(user_id):
    return user_settings.get(str(user_id), {}).get('timezone', 0)

# Отримати поточний час користувача
def get_user_time(user_id):
    tz_offset = get_user_timezone(user_id)
    return datetime.utcnow() + timedelta(hours=tz_offset)

# Функція для очищення минулих зустрічей
def clean_old_meetings():
    for user_id in list(meetings.keys()):
        if user_id in meetings:
            user_now = get_user_time(user_id)
            
            if user_id not in meetings_history:
                meetings_history[user_id] = []
            
            for m in meetings[user_id]:
                meeting_time = datetime.strptime(m['datetime'], "%d.%m.%Y %H:%M")
                if meeting_time <= user_now - timedelta(minutes=1):
                    m['auto_completed'] = True
                    meetings_history[user_id].append(m)
            
            save_history()
            
            meetings[user_id] = [
                m for m in meetings[user_id]
                if datetime.strptime(m['datetime'], "%d.%m.%Y %H:%M") > user_now - timedelta(minutes=1)
            ]
            
            if not meetings[user_id]:
                del meetings[user_id]
    save_meetings()

# Команда /start
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = str(message.chat.id)
    tz = get_user_timezone(user_id)
    tz_str = get_timezone_string(tz)
    
    welcome_text = f"""
👋 Привіт! Я твій бот-асистент для нагадувань про зустрічі.

📋 Що я вмію:
/add - Додати зустріч (покроковий діалог)
/list - Показати всі зустрічі
/listbytag - Фільтр зустрічей за тегами
/edit - Редагувати зустріч
/delete - Видалити зустріч
/deleteall - Масове видалення зустрічей
/repeat - Налаштувати повторювані зустрічі
/stats - Статистика зустрічей
/timezone - Налаштувати часовий пояс
/help - Допомога

🏷️ Доступні теги:
💼 Робота | 👤 Особисте | ⚽ Спорт | 📚 Навчання
🏥 Здоров'я | 👨‍👩‍👧 Сім'я | 🛒 Покупки | ⭐ Важливе

⏰ Нагадування приходять:
- За обраний час (5/10/30/60 хвилин/1 день)
- Рівно у вказаний час зустрічі

🌍 Твій часовий пояс: {tz_str}
💡 Бот автоматично враховує літній/зимовий час

───────────────────────
🆕 /updates - Що нового в боті
"""
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['help'])
def help_command(message):
    europe_dst = is_dst_active_europe()
    dst_status = "⏰ Зараз діє літній час в Європі" if europe_dst else "❄️ Зараз діє зимовий час в Європі"
    
    help_text = f"""
ℹ️ **Як користуватися ботом:**

📝 **Додати зустріч (покроково):**
/add - бот задасть питання по порядку

📋 **Переглянути зустрічі:**
/list - всі заплановані зустрічі
/listbytag - фільтр зустрічей за тегами

✏️ **Редагувати зустріч:**
/edit - змінити будь-які параметри зустрічі 
(дату, час, опис, тег, нагадування, повторення)

🗑 **Видалити зустріч:**
/delete - видалити одну зустріч
/deleteall - масове видалення зустрічей
(за датою, словом, тегом, за період або всі)

🔁 **Повторювані зустрічі:**
/repeat - налаштувати щоденні/щотижневі/щомісячні

📊 **Статистика:**
/stats - переглянути статистику по зустрічах

🌍 **Налаштувати часовий пояс:**
/timezone - простий вибір зі списку
або /timezone (+/-)n
Приклади:
- /timezone +3 (для UTC+3)
- /timezone -5 (для UTC-5)

🏷️ **Доступні теги:**
💼 Робота | 👤 Особисте | ⚽ Спорт | 📚 Навчання
🏥 Здоров'я | 👨‍👩‍👧 Сім'я | 🛒 Покупки | ⭐ Важливе

ℹ️ {dst_status}
💡 Часові пояси автоматично оновлюються при зміні сезону
⏰ = літній час | ❄️ = зимовий час

───────────────────────
🆕 /updates - Дивись останні оновлення бота!
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

# Команда /timezone
@bot.message_handler(commands=['timezone'])
def timezone_command(message):
    user_id = str(message.chat.id)
    
    try:
        parts = message.text.split()
        
        if len(parts) == 1:
            current_tz = get_user_timezone(user_id)
            tz_str = get_timezone_string(current_tz)
            
            europe_dst = is_dst_active_europe()
            na_dst = is_dst_active_north_america()
            aus_dst = is_dst_active_australia()
            
            dst_info = "\n\n📍 Поточний стан:\n"
            dst_info += f"• Європа: {'⏰ літній час' if europe_dst else '❄️ зимовий час'}\n"
            dst_info += f"• Північна Америка: {'⏰ літній час' if na_dst else '❄️ зимовий час'}\n"
            dst_info += f"• Австралія: {'⏰ літній час' if aus_dst else '❄️ зимовий час'}"
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            popular_timezones = get_popular_timezones()
            
            buttons = [types.InlineKeyboardButton(label, callback_data=f'tz_{offset}') for offset, label in popular_timezones]
            for i in range(0, len(buttons), 2):
                if i+1 < len(buttons):
                    markup.add(buttons[i], buttons[i+1])
                else:
                    markup.add(buttons[i])
            
            bot.reply_to(message, f"🌍 Твій поточний часовий пояс: {tz_str}{dst_info}\n\nОбери новий часовий пояс:", reply_markup=markup)
            return
        
        tz_value = int(parts[1])
        
        if tz_value < -12 or tz_value > 14:
            bot.reply_to(message, "❌ Невірний часовий пояс! Допустимі значення: від -12 до +14\n\nПриклад:\n/timezone +3")
            return
        
        if user_id not in user_settings:
            user_settings[user_id] = {}
        
        user_settings[user_id]['timezone'] = tz_value
        save_settings()
        
        tz_str = get_timezone_string(tz_value)
        user_time = get_user_time(user_id).strftime('%H:%M')
        
        bot.reply_to(message, f"✅ Часовий пояс встановлено: {tz_str}\n\n🕐 Твій поточний час: {user_time}")
        
    except (ValueError, IndexError):
        bot.reply_to(message, "❌ Невірний формат!\n\nВикористовуй:\n/timezone +3 (для UTC+3)\n/timezone -5 (для UTC-5)\n/timezone 0 (для UTC)")

# Обробка вибору часового поясу через кнопки
@bot.callback_query_handler(func=lambda call: call.data.startswith('tz_'))
def callback_timezone(call):
    user_id = str(call.message.chat.id)
    tz_value = int(call.data.replace('tz_', ''))
    
    if user_id not in user_settings:
        user_settings[user_id] = {}
    
    user_settings[user_id]['timezone'] = tz_value
    save_settings()
    
    tz_str = get_timezone_string(tz_value)
    user_time = get_user_time(user_id).strftime('%H:%M')
    
    bot.answer_callback_query(call.id, f"✅ Встановлено")
    bot.edit_message_text(
        f"✅ Часовий пояс встановлено: {tz_str}\n\n🕐 Твій поточний час: {user_time}",
        call.message.chat.id,
        call.message.message_id
    )

# Команда /add
@bot.message_handler(commands=['add'])
def add_meeting_start(message):
    user_id = str(message.chat.id)
    
    if user_id not in user_settings or 'timezone' not in user_settings[user_id]:
        user_states[user_id] = {'step': 'awaiting_timezone', 'next_command': 'add'}
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        popular_timezones = get_popular_timezones()
        
        buttons = [types.InlineKeyboardButton(label, callback_data=f'tzadd_{offset}') for offset, label in popular_timezones]
        for i in range(0, len(buttons), 2):
            if i+1 < len(buttons):
                markup.add(buttons[i], buttons[i+1])
            else:
                markup.add(buttons[i])
        
        bot.send_message(message.chat.id, "🌍 Спочатку обери свій часовий пояс:", reply_markup=markup)
        return
    
    user_states[user_id] = {'step': 'date'}
    
    markup = types.InlineKeyboardMarkup()
    today_btn = types.InlineKeyboardButton('📅 Сьогодні', callback_data='date_today')
    tomorrow_btn = types.InlineKeyboardButton('📅 Завтра', callback_data='date_tomorrow')
    other_btn = types.InlineKeyboardButton('📅 Інша дата', callback_data='date_other')
    markup.add(today_btn, tomorrow_btn)
    markup.add(other_btn)
    
    tz = get_user_timezone(user_id)
    tz_str = get_timezone_string(tz)
    
    bot.send_message(message.chat.id, f"📅 Обери дату зустрічі:\n\n🌍 Часовий пояс: {tz_str}", reply_markup=markup)

# Обробка вибору часового поясу перед додаванням зустрічі
@bot.callback_query_handler(func=lambda call: call.data.startswith('tzadd_'))
def callback_timezone_before_add(call):
    user_id = str(call.message.chat.id)
    tz_value = int(call.data.replace('tzadd_', ''))
    
    if user_id not in user_settings:
        user_settings[user_id] = {}
    
    user_settings[user_id]['timezone'] = tz_value
    save_settings()
    
    tz_str = get_timezone_string(tz_value)
    
    bot.answer_callback_query(call.id, f"✅ Встановлено")
    
    user_states[user_id] = {'step': 'date'}
    
    markup = types.InlineKeyboardMarkup()
    today_btn = types.InlineKeyboardButton('📅 Сьогодні', callback_data='date_today')
    tomorrow_btn = types.InlineKeyboardButton('📅 Завтра', callback_data='date_tomorrow')
    other_btn = types.InlineKeyboardButton('📅 Інша дата', callback_data='date_other')
    markup.add(today_btn, tomorrow_btn)
    markup.add(other_btn)
    
    bot.edit_message_text(
        f"✅ Часовий пояс встановлено: {tz_str}\n\n📅 Обери дату зустрічі:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Обробка вибору дати через inline-кнопки
@bot.callback_query_handler(func=lambda call: call.data.startswith('date_'))
def callback_date(call):
    user_id = str(call.message.chat.id)
    
    if call.data == 'date_today':
        selected_date = get_user_time(user_id)
        user_states[user_id]['date'] = selected_date.strftime('%d.%m.%Y')
        user_states[user_id]['step'] = 'time'
        bot.answer_callback_query(call.id, "✅ Сьогодні")
        show_time_selection(call.message.chat.id, call.message.message_id, user_states[user_id]['date'])
        
    elif call.data == 'date_tomorrow':
        selected_date = get_user_time(user_id) + timedelta(days=1)
        user_states[user_id]['date'] = selected_date.strftime('%d.%m.%Y')
        user_states[user_id]['step'] = 'time'
        bot.answer_callback_query(call.id, "✅ Завтра")
        show_time_selection(call.message.chat.id, call.message.message_id, user_states[user_id]['date'])
        
    elif call.data == 'date_other':
        bot.answer_callback_query(call.id)
        bot.edit_message_text("📅 Введи дату у форматі ДД.ММ.РРРР\n\nНаприклад: 20.10.2025", 
                             call.message.chat.id, call.message.message_id)
        user_states[user_id]['step'] = 'custom_date'

# Функція для показу inline-кнопок вибору часу
def show_time_selection(chat_id, message_id, date_str):
    markup = types.InlineKeyboardMarkup(row_width=3)
    times = ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00', '17:00', '18:00']
    buttons = [types.InlineKeyboardButton(t, callback_data=f'time_{t}') for t in times]
    
    for i in range(0, len(buttons), 3):
        markup.add(*buttons[i:i+3])
    
    markup.add(types.InlineKeyboardButton('🕐 Інший час', callback_data='time_other'))
    
    bot.edit_message_text(f"🕐 Обери час зустрічі\n(Дата: {date_str}):", 
                         chat_id, message_id, reply_markup=markup)

# Обробка введення кастомної дати
@bot.message_handler(func=lambda message: str(message.chat.id) in user_states and user_states[str(message.chat.id)].get('step') == 'custom_date')
def process_custom_date(message):
    user_id = str(message.chat.id)
    
    try:
        date_obj = datetime.strptime(message.text, '%d.%m.%Y')
        user_now = get_user_time(user_id)
        
        if date_obj.date() < user_now.date():
            bot.send_message(message.chat.id, "❌ Не можна створити зустріч у минулому! Введи іншу дату:")
            return
        
        user_states[user_id]['date'] = message.text
        user_states[user_id]['step'] = 'time'
        
        markup = types.InlineKeyboardMarkup(row_width=3)
        times = ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00', '17:00', '18:00']
        buttons = [types.InlineKeyboardButton(t, callback_data=f'time_{t}') for t in times]
        
        for i in range(0, len(buttons), 3):
            markup.add(*buttons[i:i+3])
        
        markup.add(types.InlineKeyboardButton('🕐 Інший час', callback_data='time_other'))
        
        bot.send_message(message.chat.id, f"🕐 Обери час зустрічі\n(Дата: {user_states[user_id]['date']}):", reply_markup=markup)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Невірний формат дати!\n\nВикористовуй формат: ДД.ММ.РРРР\nНаприклад: 20.10.2025")

# Обробка вибору часу через inline-кнопки
@bot.callback_query_handler(func=lambda call: call.data.startswith('time_'))
def callback_time(call):
    user_id = str(call.message.chat.id)
    
    if call.data == 'time_other':
        bot.answer_callback_query(call.id)
        bot.edit_message_text("🕐 Введи час у форматі ГГ:ХХ\n\nНаприклад: 14:30", 
                             call.message.chat.id, call.message.message_id)
        user_states[user_id]['step'] = 'custom_time'
    else:
        time_str = call.data.replace('time_', '')
        user_states[user_id]['time'] = time_str
        user_states[user_id]['step'] = 'description'
        bot.answer_callback_query(call.id, f"✅ {time_str}")
        
        bot.edit_message_text(
            f"📝 Опиши зустріч\n\nДата: {user_states[user_id]['date']}\nЧас: {user_states[user_id]['time']}\n\nНаприклад: Зустріч з клієнтом",
            call.message.chat.id, call.message.message_id
        )

# Обробка введення кастомного часу
@bot.message_handler(func=lambda message: str(message.chat.id) in user_states and user_states[str(message.chat.id)].get('step') == 'custom_time')
def process_custom_time(message):
    user_id = str(message.chat.id)
    
    try:
        time_obj = datetime.strptime(message.text, '%H:%M')
        user_states[user_id]['time'] = message.text
        user_states[user_id]['step'] = 'description'
        
        bot.send_message(message.chat.id, f"📝 Опиши зустріч\n\nДата: {user_states[user_id]['date']}\nЧас: {user_states[user_id]['time']}\n\nНаприклад: Зустріч з клієнтом")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Невірний формат часу!\n\nВикористовуй формат: ГГ:ХХ\nНаприклад: 14:30")

# Обробка опису зустрічі
@bot.message_handler(func=lambda message: str(message.chat.id) in user_states and user_states[str(message.chat.id)].get('step') == 'description')
def process_description(message):
    user_id = str(message.chat.id)
    
    user_states[user_id]['description'] = message.text
    user_states[user_id]['step'] = 'tag'
    
    # Показуємо кнопки вибору тегу
    markup = types.InlineKeyboardMarkup(row_width=2)
    tag_buttons = [
        types.InlineKeyboardButton(f"{emoji} {tag.capitalize()}", callback_data=f'tag_{tag}')
        for tag, emoji in TAGS.items()
    ]
    
    for i in range(0, len(tag_buttons), 2):
        markup.add(*tag_buttons[i:i+2])
    
    markup.add(types.InlineKeyboardButton('➡️ Без тегу', callback_data='tag_none'))
    
    bot.send_message(
        message.chat.id,
        f"🏷️ Обери тег для зустрічі:\n\n📝 {message.text}",
        reply_markup=markup
    )

# Обробка вибору тегу
@bot.callback_query_handler(func=lambda call: call.data.startswith('tag_'))
def callback_tag(call):
    user_id = str(call.message.chat.id)
    tag = call.data.replace('tag_', '')
    
    if tag == 'none':
        user_states[user_id]['tag'] = None
        tag_emoji = ''
    else:
        user_states[user_id]['tag'] = tag
        tag_emoji = TAGS.get(tag, '')
    
    user_states[user_id]['step'] = 'reminder'
    user_states[user_id]['selected_reminders'] = []  # Новое: список обраних нагадувань
    
    # Показуємо кнопки вибору часу нагадування
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('⏰ 1 день', callback_data='remind_1440'),
        types.InlineKeyboardButton('⏰ 1 година', callback_data='remind_60')
    )
    markup.add(
        types.InlineKeyboardButton('⏰ 30 хвилин', callback_data='remind_30'),
        types.InlineKeyboardButton('⏰ 10 хвилин', callback_data='remind_10')
    )
    markup.add(
        types.InlineKeyboardButton('⏰ 5 хвилин', callback_data='remind_5')
    )
    markup.add(
        types.InlineKeyboardButton('✅ Готово', callback_data='remind_done')
    )
    
    tag_text = f"\n🏷️ {tag_emoji} {tag.capitalize()}" if tag != 'none' else ""
    bot.answer_callback_query(call.id, f"✅ {tag_emoji} {tag.capitalize() if tag != 'none' else 'Без тегу'}")
    bot.edit_message_text(
        f"⏰ Обери нагадування (можна кілька):\n\n📅 {user_states[user_id]['date']}\n🕐 {user_states[user_id]['time']}\n📝 {user_states[user_id]['description']}{tag_text}\n\nОбрано: немає",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Обробка вибору часу нагадування
@bot.callback_query_handler(func=lambda call: call.data.startswith('remind_'))
def callback_reminder(call):
    user_id = str(call.message.chat.id)
    
    try:
        if call.data == 'remind_done':
            # Завершуємо вибір нагадувань
            if not user_states[user_id].get('selected_reminders'):
                bot.answer_callback_query(call.id, "❌ Обери хоча б одне нагадування!")
                return
            
            date_str = user_states[user_id]['date']
            time_str = user_states[user_id]['time']
            description = user_states[user_id]['description']
            
            datetime_str = f"{date_str} {time_str}"
            meeting_datetime = datetime.strptime(datetime_str, "%d.%m.%Y %H:%M")
            user_now = get_user_time(user_id)
            
            if meeting_datetime <= user_now:
                bot.answer_callback_query(call.id, "❌ Не можна додати зустріч у минулому!")
                bot.edit_message_text("❌ Не можна додати зустріч у минулому!", call.message.chat.id, call.message.message_id)
                del user_states[user_id]
                return
            
            if user_id not in meetings:
                meetings[user_id] = []
            
            # Створюємо словник для відстеження повідомлень
            notifications_status = {}
            for reminder_min in user_states[user_id]['selected_reminders']:
                notifications_status[str(reminder_min)] = False
            
            meeting = {
                "datetime": datetime_str,
                "description": description,
                "notified_before": False,
                "notified_now": False,
                "reminder_minutes": user_states[user_id]['selected_reminders'],  # Список нагадувань
                "notifications_sent": notifications_status,  # Статус відправки кожного нагадування
                "repeat": "none",
                "completed": False,
                "tag": user_states[user_id].get('tag')
            }
            
            meetings[user_id].append(meeting)
            save_meetings()
            
            tz = get_user_timezone(user_id)
            tz_str = get_timezone_string(tz)
            
            tag = user_states[user_id].get('tag')
            tag_text = f"\n🏷️ {TAGS.get(tag, '')} {tag.capitalize()}" if tag else ""
            
            # Формуємо текст з обраними нагадуваннями
            reminders_list = []
            for min_val in sorted(user_states[user_id]['selected_reminders'], reverse=True):
                if min_val >= 1440:
                    reminders_list.append(f"{min_val // 1440} день")
                elif min_val >= 60:
                    reminders_list.append(f"{min_val // 60} година")
                else:
                    reminders_list.append(f"{min_val} хвилин")
            
            reminders_text = ", ".join(reminders_list)
            
            bot.answer_callback_query(call.id, "✅ Зустріч додано!")
            bot.edit_message_text(
                f"✅ Зустріч додано!\n\n📅 {date_str}\n🕐 {time_str}\n📝 {description}{tag_text}\n🌍 {tz_str}\n\n⏰ Нагадування: {reminders_text}",
                call.message.chat.id, 
                call.message.message_id
            )
            
            del user_states[user_id]
        
        else:
            # Додаємо/прибираємо нагадування зі списку
            reminder_minutes = int(call.data.replace('remind_', ''))
            
            if 'selected_reminders' not in user_states[user_id]:
                user_states[user_id]['selected_reminders'] = []
            
            if reminder_minutes in user_states[user_id]['selected_reminders']:
                # Прибираємо нагадування
                user_states[user_id]['selected_reminders'].remove(reminder_minutes)
                bot.answer_callback_query(call.id, "❌ Прибрано")
            else:
                # Додаємо нагадування
                user_states[user_id]['selected_reminders'].append(reminder_minutes)
                bot.answer_callback_query(call.id, "✅ Додано")
            
            # Оновлюємо кнопки з позначками обраних
            markup = types.InlineKeyboardMarkup()
            
            reminders_options = [
                (1440, '⏰ 1 день'),
                (60, '⏰ 1 година'),
                (30, '⏰ 30 хвилин'),
                (10, '⏰ 10 хвилин'),
                (5, '⏰ 5 хвилин')
            ]
            
            for min_val, label in reminders_options:
                if min_val in user_states[user_id]['selected_reminders']:
                    label = f"✅ {label}"
                
                if min_val >= 60:
                    markup.add(types.InlineKeyboardButton(label, callback_data=f'remind_{min_val}'))
                else:
                    if min_val == 30:
                        markup.row(
                            types.InlineKeyboardButton(label, callback_data=f'remind_{min_val}'),
                            types.InlineKeyboardButton('⏰ 10 хвилин' if 10 not in user_states[user_id]['selected_reminders'] else '✅ ⏰ 10 хвилин', callback_data='remind_10')
                        )
                    elif min_val == 10:
                        continue
                    else:
                        markup.add(types.InlineKeyboardButton(label, callback_data=f'remind_{min_val}'))
            
            markup.add(types.InlineKeyboardButton('✅ Готово', callback_data='remind_done'))
            
            # Формуємо список обраних нагадувань для відображення
            if user_states[user_id]['selected_reminders']:
                selected_list = []
                for min_val in sorted(user_states[user_id]['selected_reminders'], reverse=True):
                    if min_val >= 1440:
                        selected_list.append(f"{min_val // 1440} день")
                    elif min_val >= 60:
                        selected_list.append(f"{min_val // 60} год")
                    else:
                        selected_list.append(f"{min_val} хв")
                selected_text = ", ".join(selected_list)
            else:
                selected_text = "немає"
            
            tag = user_states[user_id].get('tag')
            tag_emoji = TAGS.get(tag, '') if tag else ''
            tag_text = f"\n🏷️ {tag_emoji} {tag.capitalize()}" if tag else ""
            
            bot.edit_message_text(
                f"⏰ Обери нагадування (можна кілька):\n\n📅 {user_states[user_id]['date']}\n🕐 {user_states[user_id]['time']}\n📝 {user_states[user_id]['description']}{tag_text}\n\nОбрано: {selected_text}",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Помилка")
        bot.edit_message_text(f"❌ Помилка: {str(e)}", call.message.chat.id, call.message.message_id)
        if user_id in user_states:
            del user_states[user_id]

# Команда /quickadd (оновлена - тепер як покроковий діалог)
@bot.message_handler(commands=['quickadd'])
def quick_add_meeting(message):
    user_id = str(message.chat.id)
    
    # Перевіряємо, чи встановлений часовий пояс
    if user_id not in user_settings or 'timezone' not in user_settings[user_id]:
        user_states[user_id] = {
            'step': 'awaiting_timezone',
            'next_command': 'quickadd'
        }
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        popular_timezones = get_popular_timezones()
        
        buttons = [types.InlineKeyboardButton(label, callback_data=f'tzquick_{offset}') for offset, label in popular_timezones]
        for i in range(0, len(buttons), 2):
            if i+1 < len(buttons):
                markup.add(buttons[i], buttons[i+1])
            else:
                markup.add(buttons[i])
        
        bot.reply_to(message, "🌍 Спочатку обери свій часовий пояс:", reply_markup=markup)
        return
    
    # Початок швидкого додавання
    user_states[user_id] = {'step': 'quickadd_date', 'mode': 'quickadd'}
    
    markup = types.InlineKeyboardMarkup()
    today_btn = types.InlineKeyboardButton('📅 Сьогодні', callback_data='quickdate_today')
    tomorrow_btn = types.InlineKeyboardButton('📅 Завтра', callback_data='quickdate_tomorrow')
    other_btn = types.InlineKeyboardButton('📅 Інша дата', callback_data='quickdate_other')
    markup.add(today_btn, tomorrow_btn)
    markup.add(other_btn)
    
    tz = get_user_timezone(user_id)
    tz_str = get_timezone_string(tz)
    
    bot.reply_to(message, f"⚡️ Швидке додавання зустрічі\n\n📅 Обери дату:\n\n🌍 Часовий пояс: {tz_str}", reply_markup=markup)

# Обробка вибору часового поясу перед quickadd
@bot.callback_query_handler(func=lambda call: call.data.startswith('tzquick_'))
def callback_timezone_before_quickadd(call):
    user_id = str(call.message.chat.id)
    tz_value = int(call.data.replace('tzquick_', ''))
    
    if user_id not in user_settings:
        user_settings[user_id] = {}
    
    user_settings[user_id]['timezone'] = tz_value
    save_settings()
    
    tz_str = get_timezone_string(tz_value)
    
    bot.answer_callback_query(call.id, f"✅ Встановлено")
    
    # Початок швидкого додавання
    user_states[user_id] = {'step': 'quickadd_date', 'mode': 'quickadd'}
    
    markup = types.InlineKeyboardMarkup()
    today_btn = types.InlineKeyboardButton('📅 Сьогодні', callback_data='quickdate_today')
    tomorrow_btn = types.InlineKeyboardButton('📅 Завтра', callback_data='quickdate_tomorrow')
    other_btn = types.InlineKeyboardButton('📅 Інша дата', callback_data='quickdate_other')
    markup.add(today_btn, tomorrow_btn)
    markup.add(other_btn)
    
    bot.edit_message_text(
        f"✅ Часовий пояс встановлено: {tz_str}\n\n⚡️ Швидке додавання зустрічі\n\n📅 Обери дату:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Обробка вибору дати для quickadd
@bot.callback_query_handler(func=lambda call: call.data.startswith('quickdate_'))
def callback_quickdate(call):
    user_id = str(call.message.chat.id)
    
    if call.data == 'quickdate_today':
        selected_date = get_user_time(user_id)
        user_states[user_id]['date'] = selected_date.strftime('%d.%m.%Y')
        user_states[user_id]['step'] = 'quickadd_time'
        bot.answer_callback_query(call.id, "✅ Сьогодні")
        show_quickadd_time_selection(call.message.chat.id, call.message.message_id, user_states[user_id]['date'])
        
    elif call.data == 'quickdate_tomorrow':
        selected_date = get_user_time(user_id) + timedelta(days=1)
        user_states[user_id]['date'] = selected_date.strftime('%d.%m.%Y')
        user_states[user_id]['step'] = 'quickadd_time'
        bot.answer_callback_query(call.id, "✅ Завтра")
        show_quickadd_time_selection(call.message.chat.id, call.message.message_id, user_states[user_id]['date'])
        
    elif call.data == 'quickdate_other':
        bot.answer_callback_query(call.id)
        bot.edit_message_text("📅 Введи дату у форматі ДД.ММ.РРРР\n\nНаприклад: 20.10.2025", 
                             call.message.chat.id, call.message.message_id)
        user_states[user_id]['step'] = 'quickadd_custom_date'

# Функція для показу вибору часу в quickadd
def show_quickadd_time_selection(chat_id, message_id, date_str):
    markup = types.InlineKeyboardMarkup(row_width=3)
    times = ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00', '17:00', '18:00']
    buttons = [types.InlineKeyboardButton(t, callback_data=f'quicktime_{t}') for t in times]
    
    for i in range(0, len(buttons), 3):
        markup.add(*buttons[i:i+3])
    
    markup.add(types.InlineKeyboardButton('🕐 Інший час', callback_data='quicktime_other'))
    
    bot.edit_message_text(f"⚡️ Швидке додавання\n\n🕐 Обери час зустрічі\n(Дата: {date_str}):", 
                         chat_id, message_id, reply_markup=markup)

# Обробка введення кастомної дати для quickadd
@bot.message_handler(func=lambda message: str(message.chat.id) in user_states and user_states[str(message.chat.id)].get('step') == 'quickadd_custom_date')
def process_quickadd_custom_date(message):
    user_id = str(message.chat.id)
    
    try:
        date_obj = datetime.strptime(message.text, '%d.%m.%Y')
        user_now = get_user_time(user_id)
        
        if date_obj.date() < user_now.date():
            bot.send_message(message.chat.id, "❌ Не можна створити зустріч у минулому! Введи іншу дату:")
            return
        
        user_states[user_id]['date'] = message.text
        user_states[user_id]['step'] = 'quickadd_time'
        
        markup = types.InlineKeyboardMarkup(row_width=3)
        times = ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00', '17:00', '18:00']
        buttons = [types.InlineKeyboardButton(t, callback_data=f'quicktime_{t}') for t in times]
        
        for i in range(0, len(buttons), 3):
            markup.add(*buttons[i:i+3])
        
        markup.add(types.InlineKeyboardButton('🕐 Інший час', callback_data='quicktime_other'))
        
        bot.send_message(message.chat.id, f"⚡️ Швидке додавання\n\n🕐 Обери час зустрічі\n(Дата: {user_states[user_id]['date']}):", reply_markup=markup)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Невірний формат дати!\n\nВикористовуй формат: ДД.ММ.РРРР\nНаприклад: 20.10.2025")

# Обробка вибору часу для quickadd
@bot.callback_query_handler(func=lambda call: call.data.startswith('quicktime_'))
def callback_quicktime(call):
    user_id = str(call.message.chat.id)
    
    if call.data == 'quicktime_other':
        bot.answer_callback_query(call.id)
        bot.edit_message_text("🕐 Введи час у форматі ГГ:ХХ\n\nНаприклад: 14:30", 
                             call.message.chat.id, call.message.message_id)
        user_states[user_id]['step'] = 'quickadd_custom_time'
    else:
        time_str = call.data.replace('quicktime_', '')
        user_states[user_id]['time'] = time_str
        user_states[user_id]['step'] = 'quickadd_description'
        bot.answer_callback_query(call.id, f"✅ {time_str}")
        
        bot.edit_message_text(
            f"⚡️ Швидке додавання\n\n📝 Опиши зустріч\n\nДата: {user_states[user_id]['date']}\nЧас: {user_states[user_id]['time']}\n\nНаприклад: Зустріч з клієнтом",
            call.message.chat.id, call.message.message_id
        )

# Обробка введення кастомного часу для quickadd
@bot.message_handler(func=lambda message: str(message.chat.id) in user_states and user_states[str(message.chat.id)].get('step') == 'quickadd_custom_time')
def process_quickadd_custom_time(message):
    user_id = str(message.chat.id)
    
    try:
        time_obj = datetime.strptime(message.text, '%H:%M')
        user_states[user_id]['time'] = message.text
        user_states[user_id]['step'] = 'quickadd_description'
        
        bot.send_message(message.chat.id, f"⚡️ Швидке додавання\n\n📝 Опиши зустріч\n\nДата: {user_states[user_id]['date']}\nЧас: {user_states[user_id]['time']}\n\nНаприклад: Зустріч з клієнтом")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Невірний формат часу!\n\nВикористовуй формат: ГГ:ХХ\nНаприклад: 14:30")

# Обробка опису для quickadd
@bot.message_handler(func=lambda message: str(message.chat.id) in user_states and user_states[str(message.chat.id)].get('step') == 'quickadd_description')
def process_quickadd_description(message):
    user_id = str(message.chat.id)
    
    user_states[user_id]['description'] = message.text
    user_states[user_id]['step'] = 'quickadd_tag'
    
    # Показуємо кнопки вибору тегу
    markup = types.InlineKeyboardMarkup(row_width=2)
    tag_buttons = [
        types.InlineKeyboardButton(f"{emoji} {tag.capitalize()}", callback_data=f'quicktag_{tag}')
        for tag, emoji in TAGS.items()
    ]
    
    for i in range(0, len(tag_buttons), 2):
        markup.add(*tag_buttons[i:i+2])
    
    markup.add(types.InlineKeyboardButton('➡️ Без тегу', callback_data='quicktag_none'))
    
    bot.send_message(
        message.chat.id,
        f"⚡️ Швидке додавання\n\n🏷️ Обери тег для зустрічі:\n\n📝 {message.text}",
        reply_markup=markup
    )

# Обробка вибору тегу для quickadd
@bot.callback_query_handler(func=lambda call: call.data.startswith('quicktag_'))
def callback_quicktag(call):
    user_id = str(call.message.chat.id)
    tag = call.data.replace('quicktag_', '')
    
    if tag == 'none':
        user_states[user_id]['tag'] = None
        tag_emoji = ''
    else:
        user_states[user_id]['tag'] = tag
        tag_emoji = TAGS.get(tag, '')
    
    user_states[user_id]['step'] = 'quickadd_reminder'
    user_states[user_id]['selected_reminders'] = []
    
    # Показуємо кнопки вибору часу нагадування
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('⏰ 1 день', callback_data='quickremind_1440'),
        types.InlineKeyboardButton('⏰ 1 година', callback_data='quickremind_60')
    )
    markup.add(
        types.InlineKeyboardButton('⏰ 30 хвилин', callback_data='quickremind_30'),
        types.InlineKeyboardButton('⏰ 10 хвилин', callback_data='quickremind_10')
    )
    markup.add(
        types.InlineKeyboardButton('⏰ 5 хвилин', callback_data='quickremind_5')
    )
    markup.add(
        types.InlineKeyboardButton('✅ Готово', callback_data='quickremind_done')
    )
    
    tag_text = f"\n🏷️ {tag_emoji} {tag.capitalize()}" if tag != 'none' else ""
    bot.answer_callback_query(call.id, f"✅ {tag_emoji} {tag.capitalize() if tag != 'none' else 'Без тегу'}")
    bot.edit_message_text(
        f"⚡️ Швидке додавання\n\n⏰ Обери нагадування (можна кілька):\n\n📅 {user_states[user_id]['date']}\n🕐 {user_states[user_id]['time']}\n📝 {user_states[user_id]['description']}{tag_text}\n\nОбрано: немає",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Обробка вибору нагадувань для quickadd
@bot.callback_query_handler(func=lambda call: call.data.startswith('quickremind_'))
def callback_quickremind(call):
    user_id = str(call.message.chat.id)
    
    try:
        if call.data == 'quickremind_done':
            # Завершуємо вибір нагадувань
            if not user_states[user_id].get('selected_reminders'):
                bot.answer_callback_query(call.id, "❌ Обери хоча б одне нагадування!")
                return
            
            date_str = user_states[user_id]['date']
            time_str = user_states[user_id]['time']
            description = user_states[user_id]['description']
            
            datetime_str = f"{date_str} {time_str}"
            meeting_datetime = datetime.strptime(datetime_str, "%d.%m.%Y %H:%M")
            user_now = get_user_time(user_id)
            
            if meeting_datetime <= user_now:
                bot.answer_callback_query(call.id, "❌ Не можна додати зустріч у минулому!")
                bot.edit_message_text("❌ Не можна додати зустріч у минулому!", call.message.chat.id, call.message.message_id)
                del user_states[user_id]
                return
            
            if user_id not in meetings:
                meetings[user_id] = []
            
            # Створюємо словник для відстеження повідомлень
            notifications_status = {}
            for reminder_min in user_states[user_id]['selected_reminders']:
                notifications_status[str(reminder_min)] = False
            
            meeting = {
                "datetime": datetime_str,
                "description": description,
                "notified_before": False,
                "notified_now": False,
                "reminder_minutes": user_states[user_id]['selected_reminders'],
                "notifications_sent": notifications_status,
                "repeat": "none",
                "completed": False,
                "tag": user_states[user_id].get('tag')
            }
            
            meetings[user_id].append(meeting)
            save_meetings()
            
            tz = get_user_timezone(user_id)
            tz_str = get_timezone_string(tz)
            
            tag = user_states[user_id].get('tag')
            tag_text = f"\n🏷️ {TAGS.get(tag, '')} {tag.capitalize()}" if tag else ""
            
            # Формуємо текст з обраними нагадуваннями
            reminders_list = []
            for min_val in sorted(user_states[user_id]['selected_reminders'], reverse=True):
                if min_val >= 1440:
                    reminders_list.append(f"{min_val // 1440} день")
                elif min_val >= 60:
                    reminders_list.append(f"{min_val // 60} година")
                else:
                    reminders_list.append(f"{min_val} хвилин")
            
            reminders_text = ", ".join(reminders_list)
            
            bot.answer_callback_query(call.id, "✅ Зустріч додано!")
            bot.edit_message_text(
                f"✅ Зустріч швидко додано!\n\n📅 {date_str}\n🕐 {time_str}\n📝 {description}{tag_text}\n🌍 {tz_str}\n\n⏰ Нагадування: {reminders_text}",
                call.message.chat.id, 
                call.message.message_id
            )
            
            del user_states[user_id]
        
        else:
            # Додаємо/прибираємо нагадування зі списку
            reminder_minutes = int(call.data.replace('quickremind_', ''))
            
            if 'selected_reminders' not in user_states[user_id]:
                user_states[user_id]['selected_reminders'] = []
            
            if reminder_minutes in user_states[user_id]['selected_reminders']:
                user_states[user_id]['selected_reminders'].remove(reminder_minutes)
                bot.answer_callback_query(call.id, "❌ Прибрано")
            else:
                user_states[user_id]['selected_reminders'].append(reminder_minutes)
                bot.answer_callback_query(call.id, "✅ Додано")
            
            # Оновлюємо кнопки
            markup = types.InlineKeyboardMarkup()
            
            reminders_options = [
                (1440, '⏰ 1 день'),
                (60, '⏰ 1 година'),
                (30, '⏰ 30 хвилин'),
                (10, '⏰ 10 хвилин'),
                (5, '⏰ 5 хвилин')
            ]
            
            for min_val, label in reminders_options:
                if min_val in user_states[user_id]['selected_reminders']:
                    label = f"✅ {label}"
                
                if min_val >= 60:
                    markup.add(types.InlineKeyboardButton(label, callback_data=f'quickremind_{min_val}'))
                else:
                    if min_val == 30:
                        markup.row(
                            types.InlineKeyboardButton(label, callback_data=f'quickremind_{min_val}'),
                            types.InlineKeyboardButton('⏰ 10 хвилин' if 10 not in user_states[user_id]['selected_reminders'] else '✅ ⏰ 10 хвилин', callback_data='quickremind_10')
                        )
                    elif min_val == 10:
                        continue
                    else:
                        markup.add(types.InlineKeyboardButton(label, callback_data=f'quickremind_{min_val}'))
            
            markup.add(types.InlineKeyboardButton('✅ Готово', callback_data='quickremind_done'))
            
            # Формуємо список обраних нагадувань
            if user_states[user_id]['selected_reminders']:
                selected_list = []
                for min_val in sorted(user_states[user_id]['selected_reminders'], reverse=True):
                    if min_val >= 1440:
                        selected_list.append(f"{min_val // 1440} день")
                    elif min_val >= 60:
                        selected_list.append(f"{min_val // 60} год")
                    else:
                        selected_list.append(f"{min_val} хв")
                selected_text = ", ".join(selected_list)
            else:
                selected_text = "немає"
            
            tag = user_states[user_id].get('tag')
            tag_emoji = TAGS.get(tag, '') if tag else ''
            tag_text = f"\n🏷️ {tag_emoji} {tag.capitalize()}" if tag else ""
            
            bot.edit_message_text(
                f"⚡️ Швидке додавання\n\n⏰ Обери нагадування (можна кілька):\n\n📅 {user_states[user_id]['date']}\n🕐 {user_states[user_id]['time']}\n📝 {user_states[user_id]['description']}{tag_text}\n\nОбрано: {selected_text}",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Помилка")
        bot.edit_message_text(f"❌ Помилка: {str(e)}", call.message.chat.id, call.message.message_id)
        if user_id in user_states:
            del user_states[user_id]

# Команда /updates (оновлена)
@bot.message_handler(commands=['updates'])
def updates_command(message):
    updates_text = """
📢 **Останнє оновлення бота**

🆕 (20.10.2025)

⏰ **Автоматичний літній/зимовий час**

Бот тепер автоматично визначає та відображає літній/зимовий час для всіх міст:
- 🌍 Європа (Київ, Лондон, Париж, Берлін, Афіни)
- 🌎 Північна Америка (Нью-Йорк, Лос-Анджелес, Денвер, Мехіко)
- 🌏 Австралія та Океанія (Сідней, Окленд)

Позначки:
- ⏰ літній час
- ❄️ зимовий час


---

🔙 **Попереднє оновлення (19.10.2025)**

✏️ **Додано команду /edit**

Можливість редагувати зустрічі:
- 📅 Змінити дату
- 🕐 Змінити час
- 📝 Змінити опис
- 🏷️ Змінити тег
- ⏰ Налаштувати нагадування
- 🔁 Змінити режим повторення

---
Використовуй /help для перегляду всіх команд
"""
    bot.reply_to(message, updates_text, parse_mode='Markdown')

# Команда /quickadd (оновлена - тепер як покроковий діалог)
@bot.message_handler(commands=['quickadd'])
def quick_add_meeting(message):
    user_id = str(message.chat.id)
    
    # Перевіряємо, чи встановлений часовий пояс
    if user_id not in user_settings or 'timezone' not in user_settings[user_id]:
        user_states[user_id] = {
            'step': 'awaiting_timezone',
            'next_command': 'quickadd'
        }
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        popular_timezones = get_popular_timezones()
        
        buttons = [types.InlineKeyboardButton(label, callback_data=f'tzquick_{offset}') for offset, label in popular_timezones]
        for i in range(0, len(buttons), 2):
            if i+1 < len(buttons):
                markup.add(buttons[i], buttons[i+1])
            else:
                markup.add(buttons[i])
        
        bot.reply_to(message, "🌍 Спочатку обери свій часовий пояс:", reply_markup=markup)
        return
    
    # Початок швидкого додавання
    user_states[user_id] = {'step': 'quickadd_date', 'mode': 'quickadd'}
    
    markup = types.InlineKeyboardMarkup()
    today_btn = types.InlineKeyboardButton('📅 Сьогодні', callback_data='quickdate_today')
    tomorrow_btn = types.InlineKeyboardButton('📅 Завтра', callback_data='quickdate_tomorrow')
    other_btn = types.InlineKeyboardButton('📅 Інша дата', callback_data='quickdate_other')
    markup.add(today_btn, tomorrow_btn)
    markup.add(other_btn)
    
    tz = get_user_timezone(user_id)
    tz_str = get_timezone_string(tz)
    
    bot.reply_to(message, f"⚡️ Швидке додавання зустрічі\n\n📅 Обери дату:\n\n🌍 Часовий пояс: {tz_str}", reply_markup=markup)

# Обробка вибору часового поясу перед quickadd
@bot.callback_query_handler(func=lambda call: call.data.startswith('tzquick_'))
def callback_timezone_before_quickadd(call):
    user_id = str(call.message.chat.id)
    tz_value = int(call.data.replace('tzquick_', ''))
    
    if user_id not in user_settings:
        user_settings[user_id] = {}
    
    user_settings[user_id]['timezone'] = tz_value
    save_settings()
    
    tz_str = get_timezone_string(tz_value)
    
    bot.answer_callback_query(call.id, f"✅ Встановлено")
    
    # Початок швидкого додавання
    user_states[user_id] = {'step': 'quickadd_date', 'mode': 'quickadd'}
    
    markup = types.InlineKeyboardMarkup()
    today_btn = types.InlineKeyboardButton('📅 Сьогодні', callback_data='quickdate_today')
    tomorrow_btn = types.InlineKeyboardButton('📅 Завтра', callback_data='quickdate_tomorrow')
    other_btn = types.InlineKeyboardButton('📅 Інша дата', callback_data='quickdate_other')
    markup.add(today_btn, tomorrow_btn)
    markup.add(other_btn)
    
    bot.edit_message_text(
        f"✅ Часовий пояс встановлено: {tz_str}\n\n⚡️ Швидке додавання зустрічі\n\n📅 Обери дату:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Обробка вибору дати для quickadd
@bot.callback_query_handler(func=lambda call: call.data.startswith('quickdate_'))
def callback_quickdate(call):
    user_id = str(call.message.chat.id)
    
    if call.data == 'quickdate_today':
        selected_date = get_user_time(user_id)
        user_states[user_id]['date'] = selected_date.strftime('%d.%m.%Y')
        user_states[user_id]['step'] = 'quickadd_time'
        bot.answer_callback_query(call.id, "✅ Сьогодні")
        show_quickadd_time_selection(call.message.chat.id, call.message.message_id, user_states[user_id]['date'])
        
    elif call.data == 'quickdate_tomorrow':
        selected_date = get_user_time(user_id) + timedelta(days=1)
        user_states[user_id]['date'] = selected_date.strftime('%d.%m.%Y')
        user_states[user_id]['step'] = 'quickadd_time'
        bot.answer_callback_query(call.id, "✅ Завтра")
        show_quickadd_time_selection(call.message.chat.id, call.message.message_id, user_states[user_id]['date'])
        
    elif call.data == 'quickdate_other':
        bot.answer_callback_query(call.id)
        bot.edit_message_text("📅 Введи дату у форматі ДД.ММ.РРРР\n\nНаприклад: 20.10.2025", 
                             call.message.chat.id, call.message.message_id)
        user_states[user_id]['step'] = 'quickadd_custom_date'

# Функція для показу вибору часу в quickadd
def show_quickadd_time_selection(chat_id, message_id, date_str):
    markup = types.InlineKeyboardMarkup(row_width=3)
    times = ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00', '17:00', '18:00']
    buttons = [types.InlineKeyboardButton(t, callback_data=f'quicktime_{t}') for t in times]
    
    for i in range(0, len(buttons), 3):
        markup.add(*buttons[i:i+3])
    
    markup.add(types.InlineKeyboardButton('🕐 Інший час', callback_data='quicktime_other'))
    
    bot.edit_message_text(f"⚡️ Швидке додавання\n\n🕐 Обери час зустрічі\n(Дата: {date_str}):", 
                         chat_id, message_id, reply_markup=markup)

# Обробка введення кастомної дати для quickadd
@bot.message_handler(func=lambda message: str(message.chat.id) in user_states and user_states[str(message.chat.id)].get('step') == 'quickadd_custom_date')
def process_quickadd_custom_date(message):
    user_id = str(message.chat.id)
    
    try:
        date_obj = datetime.strptime(message.text, '%d.%m.%Y')
        user_now = get_user_time(user_id)
        
        if date_obj.date() < user_now.date():
            bot.send_message(message.chat.id, "❌ Не можна створити зустріч у минулому! Введи іншу дату:")
            return
        
        user_states[user_id]['date'] = message.text
        user_states[user_id]['step'] = 'quickadd_time'
        
        markup = types.InlineKeyboardMarkup(row_width=3)
        times = ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00', '17:00', '18:00']
        buttons = [types.InlineKeyboardButton(t, callback_data=f'quicktime_{t}') for t in times]
        
        for i in range(0, len(buttons), 3):
            markup.add(*buttons[i:i+3])
        
        markup.add(types.InlineKeyboardButton('🕐 Інший час', callback_data='quicktime_other'))
        
        bot.send_message(message.chat.id, f"⚡️ Швидке додавання\n\n🕐 Обери час зустрічі\n(Дата: {user_states[user_id]['date']}):", reply_markup=markup)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Невірний формат дати!\n\nВикористовуй формат: ДД.ММ.РРРР\nНаприклад: 20.10.2025")

# Обробка вибору часу для quickadd
@bot.callback_query_handler(func=lambda call: call.data.startswith('quicktime_'))
def callback_quicktime(call):
    user_id = str(call.message.chat.id)
    
    if call.data == 'quicktime_other':
        bot.answer_callback_query(call.id)
        bot.edit_message_text("🕐 Введи час у форматі ГГ:ХХ\n\nНаприклад: 14:30", 
                             call.message.chat.id, call.message.message_id)
        user_states[user_id]['step'] = 'quickadd_custom_time'
    else:
        time_str = call.data.replace('quicktime_', '')
        user_states[user_id]['time'] = time_str
        user_states[user_id]['step'] = 'quickadd_description'
        bot.answer_callback_query(call.id, f"✅ {time_str}")
        
        bot.edit_message_text(
            f"⚡️ Швидке додавання\n\n📝 Опиши зустріч\n\nДата: {user_states[user_id]['date']}\nЧас: {user_states[user_id]['time']}\n\nНаприклад: Зустріч з клієнтом",
            call.message.chat.id, call.message.message_id
        )

# Обробка введення кастомного часу для quickadd
@bot.message_handler(func=lambda message: str(message.chat.id) in user_states and user_states[str(message.chat.id)].get('step') == 'quickadd_custom_time')
def process_quickadd_custom_time(message):
    user_id = str(message.chat.id)
    
    try:
        time_obj = datetime.strptime(message.text, '%H:%M')
        user_states[user_id]['time'] = message.text
        user_states[user_id]['step'] = 'quickadd_description'
        
        bot.send_message(message.chat.id, f"⚡️ Швидке додавання\n\n📝 Опиши зустріч\n\nДата: {user_states[user_id]['date']}\nЧас: {user_states[user_id]['time']}\n\nНаприклад: Зустріч з клієнтом")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Невірний формат часу!\n\nВикористовуй формат: ГГ:ХХ\nНаприклад: 14:30")

# Обробка опису для quickadd
@bot.message_handler(func=lambda message: str(message.chat.id) in user_states and user_states[str(message.chat.id)].get('step') == 'quickadd_description')
def process_quickadd_description(message):
    user_id = str(message.chat.id)
    
    user_states[user_id]['description'] = message.text
    user_states[user_id]['step'] = 'quickadd_tag'
    
    # Показуємо кнопки вибору тегу
    markup = types.InlineKeyboardMarkup(row_width=2)
    tag_buttons = [
        types.InlineKeyboardButton(f"{emoji} {tag.capitalize()}", callback_data=f'quicktag_{tag}')
        for tag, emoji in TAGS.items()
    ]
    
    for i in range(0, len(tag_buttons), 2):
        markup.add(*tag_buttons[i:i+2])
    
    markup.add(types.InlineKeyboardButton('➡️ Без тегу', callback_data='quicktag_none'))
    
    bot.send_message(
        message.chat.id,
        f"⚡️ Швидке додавання\n\n🏷️ Обери тег для зустрічі:\n\n📝 {message.text}",
        reply_markup=markup
    )

# Обробка вибору тегу для quickadd
@bot.callback_query_handler(func=lambda call: call.data.startswith('quicktag_'))
def callback_quicktag(call):
    user_id = str(call.message.chat.id)
    tag = call.data.replace('quicktag_', '')
    
    if tag == 'none':
        user_states[user_id]['tag'] = None
        tag_emoji = ''
    else:
        user_states[user_id]['tag'] = tag
        tag_emoji = TAGS.get(tag, '')
    
    user_states[user_id]['step'] = 'quickadd_reminder'
    user_states[user_id]['selected_reminders'] = []
    
    # Показуємо кнопки вибору часу нагадування
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('⏰ 1 день', callback_data='quickremind_1440'),
        types.InlineKeyboardButton('⏰ 1 година', callback_data='quickremind_60')
    )
    markup.add(
        types.InlineKeyboardButton('⏰ 30 хвилин', callback_data='quickremind_30'),
        types.InlineKeyboardButton('⏰ 10 хвилин', callback_data='quickremind_10')
    )
    markup.add(
        types.InlineKeyboardButton('⏰ 5 хвилин', callback_data='quickremind_5')
    )
    markup.add(
        types.InlineKeyboardButton('✅ Готово', callback_data='quickremind_done')
    )
    
    tag_text = f"\n🏷️ {tag_emoji} {tag.capitalize()}" if tag != 'none' else ""
    bot.answer_callback_query(call.id, f"✅ {tag_emoji} {tag.capitalize() if tag != 'none' else 'Без тегу'}")
    bot.edit_message_text(
        f"⚡️ Швидке додавання\n\n⏰ Обери нагадування (можна кілька):\n\n📅 {user_states[user_id]['date']}\n🕐 {user_states[user_id]['time']}\n📝 {user_states[user_id]['description']}{tag_text}\n\nОбрано: немає",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Обробка вибору нагадувань для quickadd
@bot.callback_query_handler(func=lambda call: call.data.startswith('quickremind_'))
def callback_quickremind(call):
    user_id = str(call.message.chat.id)
    
    try:
        if call.data == 'quickremind_done':
            # Завершуємо вибір нагадувань
            if not user_states[user_id].get('selected_reminders'):
                bot.answer_callback_query(call.id, "❌ Обери хоча б одне нагадування!")
                return
            
            date_str = user_states[user_id]['date']
            time_str = user_states[user_id]['time']
            description = user_states[user_id]['description']
            
            datetime_str = f"{date_str} {time_str}"
            meeting_datetime = datetime.strptime(datetime_str, "%d.%m.%Y %H:%M")
            user_now = get_user_time(user_id)
            
            if meeting_datetime <= user_now:
                bot.answer_callback_query(call.id, "❌ Не можна додати зустріч у минулому!")
                bot.edit_message_text("❌ Не можна додати зустріч у минулому!", call.message.chat.id, call.message.message_id)
                del user_states[user_id]
                return
            
            if user_id not in meetings:
                meetings[user_id] = []
            
            # Створюємо словник для відстеження повідомлень
            notifications_status = {}
            for reminder_min in user_states[user_id]['selected_reminders']:
                notifications_status[str(reminder_min)] = False
            
            meeting = {
                "datetime": datetime_str,
                "description": description,
                "notified_before": False,
                "notified_now": False,
                "reminder_minutes": user_states[user_id]['selected_reminders'],
                "notifications_sent": notifications_status,
                "repeat": "none",
                "completed": False,
                "tag": user_states[user_id].get('tag')
            }
            
            meetings[user_id].append(meeting)
            save_meetings()
            
            tz = get_user_timezone(user_id)
            tz_str = get_timezone_string(tz)
            
            tag = user_states[user_id].get('tag')
            tag_text = f"\n🏷️ {TAGS.get(tag, '')} {tag.capitalize()}" if tag else ""
            
            # Формуємо текст з обраними нагадуваннями
            reminders_list = []
            for min_val in sorted(user_states[user_id]['selected_reminders'], reverse=True):
                if min_val >= 1440:
                    reminders_list.append(f"{min_val // 1440} день")
                elif min_val >= 60:
                    reminders_list.append(f"{min_val // 60} година")
                else:
                    reminders_list.append(f"{min_val} хвилин")
            
            reminders_text = ", ".join(reminders_list)
            
            bot.answer_callback_query(call.id, "✅ Зустріч додано!")
            bot.edit_message_text(
                f"✅ Зустріч швидко додано!\n\n📅 {date_str}\n🕐 {time_str}\n📝 {description}{tag_text}\n🌍 {tz_str}\n\n⏰ Нагадування: {reminders_text}",
                call.message.chat.id, 
                call.message.message_id
            )
            
            del user_states[user_id]
        
        else:
            # Додаємо/прибираємо нагадування зі списку
            reminder_minutes = int(call.data.replace('quickremind_', ''))
            
            if 'selected_reminders' not in user_states[user_id]:
                user_states[user_id]['selected_reminders'] = []
            
            if reminder_minutes in user_states[user_id]['selected_reminders']:
                user_states[user_id]['selected_reminders'].remove(reminder_minutes)
                bot.answer_callback_query(call.id, "❌ Прибрано")
            else:
                user_states[user_id]['selected_reminders'].append(reminder_minutes)
                bot.answer_callback_query(call.id, "✅ Додано")
            
            # Оновлюємо кнопки
            markup = types.InlineKeyboardMarkup()
            
            reminders_options = [
                (1440, '⏰ 1 день'),
                (60, '⏰ 1 година'),
                (30, '⏰ 30 хвилин'),
                (10, '⏰ 10 хвилин'),
                (5, '⏰ 5 хвилин')
            ]
            
            for min_val, label in reminders_options:
                if min_val in user_states[user_id]['selected_reminders']:
                    label = f"✅ {label}"
                
                if min_val >= 60:
                    markup.add(types.InlineKeyboardButton(label, callback_data=f'quickremind_{min_val}'))
                else:
                    if min_val == 30:
                        markup.row(
                            types.InlineKeyboardButton(label, callback_data=f'quickremind_{min_val}'),
                            types.InlineKeyboardButton('⏰ 10 хвилин' if 10 not in user_states[user_id]['selected_reminders'] else '✅ ⏰ 10 хвилин', callback_data='quickremind_10')
                        )
                    elif min_val == 10:
                        continue
                    else:
                        markup.add(types.InlineKeyboardButton(label, callback_data=f'quickremind_{min_val}'))
            
            markup.add(types.InlineKeyboardButton('✅ Готово', callback_data='quickremind_done'))
            
            # Формуємо список обраних нагадувань
            if user_states[user_id]['selected_reminders']:
                selected_list = []
                for min_val in sorted(user_states[user_id]['selected_reminders'], reverse=True):
                    if min_val >= 1440:
                        selected_list.append(f"{min_val // 1440} день")
                    elif min_val >= 60:
                        selected_list.append(f"{min_val // 60} год")
                    else:
                        selected_list.append(f"{min_val} хв")
                selected_text = ", ".join(selected_list)
            else:
                selected_text = "немає"
            
            tag = user_states[user_id].get('tag')
            tag_emoji = TAGS.get(tag, '') if tag else ''
            tag_text = f"\n🏷️ {tag_emoji} {tag.capitalize()}" if tag else ""
            
            bot.edit_message_text(
                f"⚡️ Швидке додавання\n\n⏰ Обери нагадування (можна кілька):\n\n📅 {user_states[user_id]['date']}\n🕐 {user_states[user_id]['time']}\n📝 {user_states[user_id]['description']}{tag_text}\n\nОбрано: {selected_text}",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Помилка")
        bot.edit_message_text(f"❌ Помилка: {str(e)}", call.message.chat.id, call.message.message_id)
        if user_id in user_states:
            del user_states[user_id]

# Команда /list
@bot.message_handler(commands=['list'])
def list_meetings_command(message):
    user_id = str(message.chat.id)
    
    clean_old_meetings()
    
    if user_id not in meetings or not meetings[user_id]:
        bot.reply_to(message, "📭 У тебе поки немає запланованих зустрічей.\n\nДодай зустріч командою /add")
        return
    
    user_meetings = sorted(meetings[user_id], key=lambda x: x['datetime'])
    
    tz = get_user_timezone(user_id)
    tz_str = get_timezone_string(tz)
    
    response = f"📋 Твої зустрічі (🌍 {tz_str}):\n\n"
    for i, meeting in enumerate(user_meetings, 1):
        dt = datetime.strptime(meeting['datetime'], "%d.%m.%Y %H:%M")
        tag = meeting.get('tag')
        tag_text = f" {TAGS.get(tag, '')}" if tag else ""
        repeat_emoji = " 🔁" if meeting.get('repeat', 'none') != 'none' else ""
        response += f"{i}. 📅 {dt.strftime('%d.%m.%Y')} 🕐 {dt.strftime('%H:%M')}{tag_text}{repeat_emoji}\n   📝 {meeting['description']}\n\n"
    
    bot.reply_to(message, response)

# Команда /listbytag для фільтрації
@bot.message_handler(commands=['listbytag'])
def list_by_tag_command(message):
    user_id = str(message.chat.id)
    
    clean_old_meetings()
    
    if user_id not in meetings or not meetings[user_id]:
        bot.reply_to(message, "📭 У тебе поки немає запланованих зустрічей.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    tag_buttons = [
        types.InlineKeyboardButton(f"{emoji} {tag.capitalize()}", callback_data=f'filter_{tag}')
        for tag, emoji in TAGS.items()
    ]
    
    for i in range(0, len(tag_buttons), 2):
        markup.add(*tag_buttons[i:i+2])
    
    markup.add(types.InlineKeyboardButton('📋 Всі зустрічі', callback_data='filter_all'))
    
    bot.reply_to(message, "🏷️ Фільтр за тегом:", reply_markup=markup)

# Обробник фільтрації за тегами
@bot.callback_query_handler(func=lambda call: call.data.startswith('filter_'))
def callback_filter(call):
    user_id = str(call.message.chat.id)
    filter_tag = call.data.replace('filter_', '')
    
    if user_id not in meetings or not meetings[user_id]:
        bot.answer_callback_query(call.id, "📭 Немає зустрічей")
        return
    
    if filter_tag == 'all':
        filtered_meetings = meetings[user_id]
    else:
        filtered_meetings = [m for m in meetings[user_id] if m.get('tag') == filter_tag]
    
    if not filtered_meetings:
        bot.answer_callback_query(call.id, f"📭 Немає зустрічей з тегом {filter_tag}")
        bot.edit_message_text(
            f"📭 Немає зустрічей з тегом {TAGS.get(filter_tag, '')} {filter_tag.capitalize()}",
            call.message.chat.id,
            call.message.message_id
        )
        return
    
    filtered_meetings = sorted(filtered_meetings, key=lambda x: x['datetime'])
    
    tz = get_user_timezone(user_id)
    tz_str = get_timezone_string(tz)
    
    tag_emoji = TAGS.get(filter_tag, '') if filter_tag != 'all' else '📋'
    tag_name = filter_tag.capitalize() if filter_tag != 'all' else 'Всі'
    
    response = f"🏷️ {tag_emoji} {tag_name} (🌍 {tz_str}):\n\n"
    for i, meeting in enumerate(filtered_meetings, 1):
        dt = datetime.strptime(meeting['datetime'], "%d.%m.%Y %H:%M")
        tag = meeting.get('tag')
        tag_text = f" {TAGS.get(tag, '')}" if tag else ""
        repeat_emoji = " 🔁" if meeting.get('repeat', 'none') != 'none' else ""
        response += f"{i}. 📅 {dt.strftime('%d.%m.%Y')} 🕐 {dt.strftime('%H:%M')}{tag_text}{repeat_emoji}\n   📝 {meeting['description']}\n\n"
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id)

# Команда /edit
@bot.message_handler(commands=['edit'])
def edit_meeting_command(message):
    user_id = str(message.chat.id)
    
    clean_old_meetings()
    
    if user_id not in meetings or not meetings[user_id]:
        bot.reply_to(message, "📭 У тебе немає зустрічей для редагування.\n\nДодай зустріч командою /add")
        return
    
    markup = types.InlineKeyboardMarkup()
    
    for i, meeting in enumerate(meetings[user_id]):
        dt = datetime.strptime(meeting['datetime'], "%d.%m.%Y %H:%M")
        tag = meeting.get('tag')
        tag_text = f"{TAGS.get(tag, '')} " if tag else ""
        repeat_emoji = " 🔁" if meeting.get('repeat', 'none') != 'none' else ""
        button_text = f"{tag_text}{dt.strftime('%d.%m %H:%M')}{repeat_emoji} - {meeting['description'][:25]}"
        callback_data = f"edit_select_{i}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    
    bot.reply_to(message, "✏️ Обери зустріч для редагування:", reply_markup=markup)

# Обробка вибору зустрічі для редагування
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_select_'))
def callback_edit_select(call):
    user_id = str(call.message.chat.id)
    meeting_index = int(call.data.replace('edit_select_', ''))
    
    if user_id not in meetings or meeting_index >= len(meetings[user_id]):
        bot.answer_callback_query(call.id, "❌ Зустріч не знайдено")
        return
    
    meeting = meetings[user_id][meeting_index]
    tag = meeting.get('tag')
    tag_text = f"\n🏷️ {TAGS.get(tag, '')} {tag.capitalize()}" if tag else ""
    
    repeat_text = {
        'none': '',
        'daily': ' 🔁 Щоденно',
        'weekly': ' 🔁 Щотижня',
        'monthly': ' 🔁 Щомісяця'
    }.get(meeting.get('repeat', 'none'), '')
    
    # Форматуємо список нагадувань
    reminder_minutes_list = meeting.get('reminder_minutes', [])
    if isinstance(reminder_minutes_list, int):
        reminder_minutes_list = [reminder_minutes_list]
    
    reminders_list = []
    for min_val in sorted(reminder_minutes_list, reverse=True):
        if min_val >= 1440:
            reminders_list.append(f"{min_val // 1440}д")
        elif min_val >= 60:
            reminders_list.append(f"{min_val // 60}г")
        else:
            reminders_list.append(f"{min_val}хв")
    
    reminders_text = ", ".join(reminders_list) if reminders_list else "немає"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('📅 Дату', callback_data=f'edit_date_{meeting_index}'),
        types.InlineKeyboardButton('🕐 Час', callback_data=f'edit_time_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('📝 Опис', callback_data=f'edit_desc_{meeting_index}'),
        types.InlineKeyboardButton('🏷️ Тег', callback_data=f'edit_tag_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('⏰ Нагадування', callback_data=f'edit_remind_{meeting_index}'),
        types.InlineKeyboardButton('🔁 Повторення', callback_data=f'edit_repeat_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('❌ Скасувати', callback_data='edit_cancel')
    )
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        f"✏️ **Редагування зустрічі:**\n\n"
        f"📅 {meeting['datetime']}\n"
        f"📝 {meeting['description']}{tag_text}{repeat_text}\n"
        f"⏰ Нагадування: {reminders_text}\n\n"
        f"Що хочеш змінити?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown'
    )

# Редагування дати
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_date_'))
def callback_edit_date(call):
    user_id = str(call.message.chat.id)
    meeting_index = int(call.data.replace('edit_date_', ''))
    
    user_states[user_id] = {
        'step': 'edit_date',
        'meeting_index': meeting_index
    }
    
    markup = types.InlineKeyboardMarkup()
    today_btn = types.InlineKeyboardButton('📅 Сьогодні', callback_data=f'editdate_today_{meeting_index}')
    tomorrow_btn = types.InlineKeyboardButton('📅 Завтра', callback_data=f'editdate_tomorrow_{meeting_index}')
    other_btn = types.InlineKeyboardButton('📅 Інша дата', callback_data=f'editdate_other_{meeting_index}')
    markup.add(today_btn, tomorrow_btn)
    markup.add(other_btn)
    markup.add(types.InlineKeyboardButton('◀️ Назад', callback_data=f'edit_select_{meeting_index}'))
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "📅 Обери нову дату:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Обробка вибору нової дати
@bot.callback_query_handler(func=lambda call: call.data.startswith('editdate_'))
def callback_editdate(call):
    user_id = str(call.message.chat.id)
    parts = call.data.split('_')
    date_type = parts[1]
    meeting_index = int(parts[2])
    
    if date_type == 'today':
        selected_date = get_user_time(user_id)
        new_date = selected_date.strftime('%d.%m.%Y')
    elif date_type == 'tomorrow':
        selected_date = get_user_time(user_id) + timedelta(days=1)
        new_date = selected_date.strftime('%d.%m.%Y')
    elif date_type == 'other':
        user_states[user_id] = {
            'step': 'edit_custom_date',
            'meeting_index': meeting_index
        }
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            "📅 Введи нову дату у форматі ДД.ММ.РРРР\n\nНаприклад: 25.10.2025",
            call.message.chat.id,
            call.message.message_id
        )
        return
    else:
        return
    
    meeting = meetings[user_id][meeting_index]
    old_time = meeting['datetime'].split()[1]
    meeting['datetime'] = f"{new_date} {old_time}"
    
    # Скидаємо статус повідомлень
    meeting['notified_before'] = False
    meeting['notified_now'] = False
    if 'notifications_sent' in meeting:
        for key in meeting['notifications_sent']:
            meeting['notifications_sent'][key] = False
    
    save_meetings()
    
    bot.answer_callback_query(call.id, "✅ Дату змінено")
    
    # Повертаємося до меню редагування
    tag = meeting.get('tag')
    tag_text = f"\n🏷️ {TAGS.get(tag, '')} {tag.capitalize()}" if tag else ""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('📅 Дату', callback_data=f'edit_date_{meeting_index}'),
        types.InlineKeyboardButton('🕐 Час', callback_data=f'edit_time_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('📝 Опис', callback_data=f'edit_desc_{meeting_index}'),
        types.InlineKeyboardButton('🏷️ Тег', callback_data=f'edit_tag_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('⏰ Нагадування', callback_data=f'edit_remind_{meeting_index}'),
        types.InlineKeyboardButton('🔁 Повторення', callback_data=f'edit_repeat_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('✅ Готово', callback_data='edit_done')
    )
    
    bot.edit_message_text(
        f"✅ Дату змінено!\n\n"
        f"📅 {meeting['datetime']}\n"
        f"📝 {meeting['description']}{tag_text}\n\n"
        f"Продовжити редагування?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Обробка введення кастомної дати для редагування
@bot.message_handler(func=lambda message: str(message.chat.id) in user_states and user_states[str(message.chat.id)].get('step') == 'edit_custom_date')
def process_edit_custom_date(message):
    user_id = str(message.chat.id)
    meeting_index = user_states[user_id]['meeting_index']
    
    try:
        date_obj = datetime.strptime(message.text, '%d.%m.%Y')
        user_now = get_user_time(user_id)
        
        if date_obj.date() < user_now.date():
            bot.send_message(message.chat.id, "❌ Не можна встановити дату у минулому! Введи іншу дату:")
            return
        
        meeting = meetings[user_id][meeting_index]
        old_time = meeting['datetime'].split()[1]
        meeting['datetime'] = f"{message.text} {old_time}"
        
        # Скидаємо статус повідомлень
        meeting['notified_before'] = False
        meeting['notified_now'] = False
        if 'notifications_sent' in meeting:
            for key in meeting['notifications_sent']:
                meeting['notifications_sent'][key] = False
        
        save_meetings()
        
        tag = meeting.get('tag')
        tag_text = f"\n🏷️ {TAGS.get(tag, '')} {tag.capitalize()}" if tag else ""
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton('📅 Дату', callback_data=f'edit_date_{meeting_index}'),
            types.InlineKeyboardButton('🕐 Час', callback_data=f'edit_time_{meeting_index}')
        )
        markup.add(
            types.InlineKeyboardButton('📝 Опис', callback_data=f'edit_desc_{meeting_index}'),
            types.InlineKeyboardButton('🏷️ Тег', callback_data=f'edit_tag_{meeting_index}')
        )
        markup.add(
            types.InlineKeyboardButton('⏰ Нагадування', callback_data=f'edit_remind_{meeting_index}'),
            types.InlineKeyboardButton('🔁 Повторення', callback_data=f'edit_repeat_{meeting_index}')
        )
        markup.add(
            types.InlineKeyboardButton('✅ Готово', callback_data='edit_done')
        )
        
        bot.send_message(
            message.chat.id,
            f"✅ Дату змінено!\n\n"
            f"📅 {meeting['datetime']}\n"
            f"📝 {meeting['description']}{tag_text}\n\n"
            f"Продовжити редагування?",
            reply_markup=markup
        )
        
        del user_states[user_id]
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Невірний формат дати!\n\nВикористовуй формат: ДД.ММ.РРРР\nНаприклад: 25.10.2025")

# Редагування часу
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_time_'))
def callback_edit_time(call):
    user_id = str(call.message.chat.id)
    meeting_index = int(call.data.replace('edit_time_', ''))
    
    user_states[user_id] = {
        'step': 'edit_time',
        'meeting_index': meeting_index
    }
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    times = ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00', '17:00', '18:00']
    buttons = [types.InlineKeyboardButton(t, callback_data=f'edittime_{t}_{meeting_index}') for t in times]
    
    for i in range(0, len(buttons), 3):
        markup.add(*buttons[i:i+3])
    
    markup.add(types.InlineKeyboardButton('🕐 Інший час', callback_data=f'edittime_other_{meeting_index}'))
    markup.add(types.InlineKeyboardButton('◀️ Назад', callback_data=f'edit_select_{meeting_index}'))
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "🕐 Обери новий час:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Обробка вибору нового часу
@bot.callback_query_handler(func=lambda call: call.data.startswith('edittime_'))
def callback_edittime(call):
    user_id = str(call.message.chat.id)
    parts = call.data.split('_')
    
    if parts[1] == 'other':
        meeting_index = int(parts[2])
        user_states[user_id] = {
            'step': 'edit_custom_time',
            'meeting_index': meeting_index
        }
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            "🕐 Введи новий час у форматі ГГ:ХХ\n\nНаприклад: 15:30",
            call.message.chat.id,
            call.message.message_id
        )
        return
    
    new_time = parts[1]
    meeting_index = int(parts[2])
    
    meeting = meetings[user_id][meeting_index]
    old_date = meeting['datetime'].split()[0]
    meeting['datetime'] = f"{old_date} {new_time}"
    
    # Скидаємо статус повідомлень
    meeting['notified_before'] = False
    meeting['notified_now'] = False
    if 'notifications_sent' in meeting:
        for key in meeting['notifications_sent']:
            meeting['notifications_sent'][key] = False
    
    save_meetings()
    
    bot.answer_callback_query(call.id, "✅ Час змінено")
    
    tag = meeting.get('tag')
    tag_text = f"\n🏷️ {TAGS.get(tag, '')} {tag.capitalize()}" if tag else ""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('📅 Дату', callback_data=f'edit_date_{meeting_index}'),
        types.InlineKeyboardButton('🕐 Час', callback_data=f'edit_time_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('📝 Опис', callback_data=f'edit_desc_{meeting_index}'),
        types.InlineKeyboardButton('🏷️ Тег', callback_data=f'edit_tag_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('⏰ Нагадування', callback_data=f'edit_remind_{meeting_index}'),
        types.InlineKeyboardButton('🔁 Повторення', callback_data=f'edit_repeat_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('✅ Готово', callback_data='edit_done')
    )
    
    bot.edit_message_text(
        f"✅ Час змінено!\n\n"
        f"📅 {meeting['datetime']}\n"
        f"📝 {meeting['description']}{tag_text}\n\n"
        f"Продовжити редагування?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Обробка введення кастомного часу для редагування
@bot.message_handler(func=lambda message: str(message.chat.id) in user_states and user_states[str(message.chat.id)].get('step') == 'edit_custom_time')
def process_edit_custom_time(message):
    user_id = str(message.chat.id)
    meeting_index = user_states[user_id]['meeting_index']
    
    try:
        time_obj = datetime.strptime(message.text, '%H:%M')
        
        meeting = meetings[user_id][meeting_index]
        old_date = meeting['datetime'].split()[0]
        meeting['datetime'] = f"{old_date} {message.text}"
        
        # Скидаємо статус повідомлень
        meeting['notified_before'] = False
        meeting['notified_now'] = False
        if 'notifications_sent' in meeting:
            for key in meeting['notifications_sent']:
                meeting['notifications_sent'][key] = False
        
        save_meetings()
        
        tag = meeting.get('tag')
        tag_text = f"\n🏷️ {TAGS.get(tag, '')} {tag.capitalize()}" if tag else ""
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton('📅 Дату', callback_data=f'edit_date_{meeting_index}'),
            types.InlineKeyboardButton('🕐 Час', callback_data=f'edit_time_{meeting_index}')
        )
        markup.add(
            types.InlineKeyboardButton('📝 Опис', callback_data=f'edit_desc_{meeting_index}'),
            types.InlineKeyboardButton('🏷️ Тег', callback_data=f'edit_tag_{meeting_index}')
        )
        markup.add(
            types.InlineKeyboardButton('⏰ Нагадування', callback_data=f'edit_remind_{meeting_index}'),
            types.InlineKeyboardButton('🔁 Повторення', callback_data=f'edit_repeat_{meeting_index}')
        )
        markup.add(
            types.InlineKeyboardButton('✅ Готово', callback_data='edit_done')
        )
        
        bot.send_message(
            message.chat.id,
            f"✅ Час змінено!\n\n"
            f"📅 {meeting['datetime']}\n"
            f"📝 {meeting['description']}{tag_text}\n\n"
            f"Продовжити редагування?",
            reply_markup=markup
        )
        
        del user_states[user_id]
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Невірний формат часу!\n\nВикористовуй формат: ГГ:ХХ\nНаприклад: 15:30")

# Редагування опису
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_desc_'))
def callback_edit_desc(call):
    user_id = str(call.message.chat.id)
    meeting_index = int(call.data.replace('edit_desc_', ''))
    
    user_states[user_id] = {
        'step': 'edit_description',
        'meeting_index': meeting_index
    }
    
    meeting = meetings[user_id][meeting_index]
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        f"📝 Поточний опис:\n{meeting['description']}\n\nВведи новий опис:",
        call.message.chat.id,
        call.message.message_id
    )

# Обробка нового опису
@bot.message_handler(func=lambda message: str(message.chat.id) in user_states and user_states[str(message.chat.id)].get('step') == 'edit_description')
def process_edit_description(message):
    user_id = str(message.chat.id)
    meeting_index = user_states[user_id]['meeting_index']
    
    meeting = meetings[user_id][meeting_index]
    meeting['description'] = message.text
    save_meetings()
    
    tag = meeting.get('tag')
    tag_text = f"\n🏷️ {TAGS.get(tag, '')} {tag.capitalize()}" if tag else ""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('📅 Дату', callback_data=f'edit_date_{meeting_index}'),
        types.InlineKeyboardButton('🕐 Час', callback_data=f'edit_time_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('📝 Опис', callback_data=f'edit_desc_{meeting_index}'),
        types.InlineKeyboardButton('🏷️ Тег', callback_data=f'edit_tag_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('⏰ Нагадування', callback_data=f'edit_remind_{meeting_index}'),
        types.InlineKeyboardButton('🔁 Повторення', callback_data=f'edit_repeat_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('✅ Готово', callback_data='edit_done')
    )
    
    bot.send_message(
        message.chat.id,
        f"✅ Опис змінено!\n\n"
        f"📅 {meeting['datetime']}\n"
        f"📝 {meeting['description']}{tag_text}\n\n"
        f"Продовжити редагування?",
        reply_markup=markup
    )
    
    del user_states[user_id]

# Редагування тегу
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_tag_'))
def callback_edit_tag(call):
    user_id = str(call.message.chat.id)
    meeting_index = int(call.data.replace('edit_tag_', ''))
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    tag_buttons = [
        types.InlineKeyboardButton(f"{emoji} {tag.capitalize()}", callback_data=f'edittag_{tag}_{meeting_index}')
        for tag, emoji in TAGS.items()
    ]
    
    for i in range(0, len(tag_buttons), 2):
        markup.add(*tag_buttons[i:i+2])
    
    markup.add(types.InlineKeyboardButton('➡️ Без тегу', callback_data=f'edittag_none_{meeting_index}'))
    markup.add(types.InlineKeyboardButton('◀️ Назад', callback_data=f'edit_select_{meeting_index}'))
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "🏷️ Обери новий тег:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Обробка вибору нового тегу
@bot.callback_query_handler(func=lambda call: call.data.startswith('edittag_'))
def callback_edittag(call):
    user_id = str(call.message.chat.id)
    parts = call.data.split('_')
    new_tag = parts[1]
    meeting_index = int(parts[2])
    
    meeting = meetings[user_id][meeting_index]
    meeting['tag'] = None if new_tag == 'none' else new_tag
    save_meetings()
    
    tag_emoji = TAGS.get(new_tag, '') if new_tag != 'none' else ''
    bot.answer_callback_query(call.id, f"✅ {tag_emoji} {new_tag.capitalize() if new_tag != 'none' else 'Без тегу'}")
    
    tag_text = f"\n🏷️ {tag_emoji} {new_tag.capitalize()}" if new_tag != 'none' else ""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('📅 Дату', callback_data=f'edit_date_{meeting_index}'),
        types.InlineKeyboardButton('🕐 Час', callback_data=f'edit_time_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('📝 Опис', callback_data=f'edit_desc_{meeting_index}'),
        types.InlineKeyboardButton('🏷️ Тег', callback_data=f'edit_tag_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('⏰ Нагадування', callback_data=f'edit_remind_{meeting_index}'),
        types.InlineKeyboardButton('🔁 Повторення', callback_data=f'edit_repeat_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('✅ Готово', callback_data='edit_done')
    )
    
    bot.edit_message_text(
        f"✅ Тег змінено!\n\n"
        f"📅 {meeting['datetime']}\n"
        f"📝 {meeting['description']}{tag_text}\n\n"
        f"Продовжити редагування?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Редагування нагадувань
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_remind_'))
def callback_edit_remind(call):
    user_id = str(call.message.chat.id)
    meeting_index = int(call.data.replace('edit_remind_', ''))
    
    meeting = meetings[user_id][meeting_index]
    
    # Отримуємо поточні нагадування
    current_reminders = meeting.get('reminder_minutes', [])
    if isinstance(current_reminders, int):
        current_reminders = [current_reminders]
    
    user_states[user_id] = {
        'step': 'edit_reminders',
        'meeting_index': meeting_index,
        'selected_reminders': current_reminders.copy()
    }
    
    markup = types.InlineKeyboardMarkup()
    
    reminders_options = [
        (1440, '⏰ 1 день'),
        (60, '⏰ 1 година'),
        (30, '⏰ 30 хвилин'),
        (10, '⏰ 10 хвилин'),
        (5, '⏰ 5 хвилин')
    ]
    
    for min_val, label in reminders_options:
        if min_val in current_reminders:
            label = f"✅ {label}"
        
        if min_val >= 60:
            markup.add(types.InlineKeyboardButton(label, callback_data=f'editrem_{min_val}_{meeting_index}'))
        else:
            if min_val == 30:
                label_10 = '⏰ 10 хвилин' if 10 not in current_reminders else '✅ ⏰ 10 хвилин'
                markup.row(
                    types.InlineKeyboardButton(label, callback_data=f'editrem_{min_val}_{meeting_index}'),
                    types.InlineKeyboardButton(label_10, callback_data=f'editrem_10_{meeting_index}')
                )
            elif min_val == 10:
                continue
            else:
                markup.add(types.InlineKeyboardButton(label, callback_data=f'editrem_{min_val}_{meeting_index}'))
    
    markup.add(types.InlineKeyboardButton('✅ Зберегти', callback_data=f'editrem_save_{meeting_index}'))
    markup.add(types.InlineKeyboardButton('◀️ Назад', callback_data=f'edit_select_{meeting_index}'))
    
    # Формуємо список обраних нагадувань для відображення
    if current_reminders:
        selected_list = []
        for min_val in sorted(current_reminders, reverse=True):
            if min_val >= 1440:
                selected_list.append(f"{min_val // 1440} день")
            elif min_val >= 60:
                selected_list.append(f"{min_val // 60} година")
            else:
                selected_list.append(f"{min_val} хв")
        selected_text = ", ".join(selected_list)
    else:
        selected_text = "немає"
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        f"⏰ Редагування нагадувань\n\n"
        f"Обрано: {selected_text}\n\n"
        f"Обери нагадування (можна кілька):",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Обробка зміни нагадувань
@bot.callback_query_handler(func=lambda call: call.data.startswith('editrem_'))
def callback_editrem(call):
    user_id = str(call.message.chat.id)
    parts = call.data.split('_')
    
    if parts[1] == 'save':
        meeting_index = int(parts[2])
        
        if not user_states[user_id]['selected_reminders']:
            bot.answer_callback_query(call.id, "❌ Обери хоча б одне нагадування!")
            return
        
        meeting = meetings[user_id][meeting_index]
        meeting['reminder_minutes'] = user_states[user_id]['selected_reminders']
        
        # Оновлюємо notifications_sent
        notifications_status = {}
        for reminder_min in meeting['reminder_minutes']:
            notifications_status[str(reminder_min)] = False
        meeting['notifications_sent'] = notifications_status
        
        save_meetings()
        
        bot.answer_callback_query(call.id, "✅ Нагадування збережено")
        
        tag = meeting.get('tag')
        tag_text = f"\n🏷️ {TAGS.get(tag, '')} {tag.capitalize()}" if tag else ""
        
        # Форматуємо список нагадувань
        reminders_list = []
        for min_val in sorted(meeting['reminder_minutes'], reverse=True):
            if min_val >= 1440:
                reminders_list.append(f"{min_val // 1440}д")
            elif min_val >= 60:
                reminders_list.append(f"{min_val // 60}г")
            else:
                reminders_list.append(f"{min_val}хв")
        
        reminders_text = ", ".join(reminders_list)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton('📅 Дату', callback_data=f'edit_date_{meeting_index}'),
            types.InlineKeyboardButton('🕐 Час', callback_data=f'edit_time_{meeting_index}')
        )
        markup.add(
            types.InlineKeyboardButton('📝 Опис', callback_data=f'edit_desc_{meeting_index}'),
            types.InlineKeyboardButton('🏷️ Тег', callback_data=f'edit_tag_{meeting_index}')
        )
        markup.add(
            types.InlineKeyboardButton('⏰ Нагадування', callback_data=f'edit_remind_{meeting_index}'),
            types.InlineKeyboardButton('🔁 Повторення', callback_data=f'edit_repeat_{meeting_index}')
        )
        markup.add(
            types.InlineKeyboardButton('✅ Готово', callback_data='edit_done')
        )
        
        bot.edit_message_text(
            f"✅ Нагадування змінено!\n\n"
            f"📅 {meeting['datetime']}\n"
            f"📝 {meeting['description']}{tag_text}\n"
            f"⏰ Нагадування: {reminders_text}\n\n"
            f"Продовжити редагування?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        
        del user_states[user_id]
        return
    
    reminder_minutes = int(parts[1])
    meeting_index = int(parts[2])
    
    if 'selected_reminders' not in user_states[user_id]:
        meeting = meetings[user_id][meeting_index]
        current_reminders = meeting.get('reminder_minutes', [])
        if isinstance(current_reminders, int):
            current_reminders = [current_reminders]
        user_states[user_id]['selected_reminders'] = current_reminders.copy()
    
    if reminder_minutes in user_states[user_id]['selected_reminders']:
        user_states[user_id]['selected_reminders'].remove(reminder_minutes)
        bot.answer_callback_query(call.id, "❌ Прибрано")
    else:
        user_states[user_id]['selected_reminders'].append(reminder_minutes)
        bot.answer_callback_query(call.id, "✅ Додано")
    
    # Оновлюємо кнопки
    markup = types.InlineKeyboardMarkup()
    
    reminders_options = [
        (1440, '⏰ 1 день'),
        (60, '⏰ 1 година'),
        (30, '⏰ 30 хвилин'),
        (10, '⏰ 10 хвилин'),
        (5, '⏰ 5 хвилин')
    ]
    
    for min_val, label in reminders_options:
        if min_val in user_states[user_id]['selected_reminders']:
            label = f"✅ {label}"
        
        if min_val >= 60:
            markup.add(types.InlineKeyboardButton(label, callback_data=f'editrem_{min_val}_{meeting_index}'))
        else:
            if min_val == 30:
                label_10 = '⏰ 10 хвилин' if 10 not in user_states[user_id]['selected_reminders'] else '✅ ⏰ 10 хвилин'
                markup.row(
                    types.InlineKeyboardButton(label, callback_data=f'editrem_{min_val}_{meeting_index}'),
                    types.InlineKeyboardButton(label_10, callback_data=f'editrem_10_{meeting_index}')
                )
            elif min_val == 10:
                continue
            else:
                markup.add(types.InlineKeyboardButton(label, callback_data=f'editrem_{min_val}_{meeting_index}'))
    
    markup.add(types.InlineKeyboardButton('✅ Зберегти', callback_data=f'editrem_save_{meeting_index}'))
    markup.add(types.InlineKeyboardButton('◀️ Назад', callback_data=f'edit_select_{meeting_index}'))
    
    # Формуємо список обраних нагадувань
    if user_states[user_id]['selected_reminders']:
        selected_list = []
        for min_val in sorted(user_states[user_id]['selected_reminders'], reverse=True):
            if min_val >= 1440:
                selected_list.append(f"{min_val // 1440} день")
            elif min_val >= 60:
                selected_list.append(f"{min_val // 60} година")
            else:
                selected_list.append(f"{min_val} хв")
        selected_text = ", ".join(selected_list)
    else:
        selected_text = "немає"
    
    bot.edit_message_text(
        f"⏰ Редагування нагадувань\n\n"
        f"Обрано: {selected_text}\n\n"
        f"Обери нагадування (можна кілька):",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Редагування повторення
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_repeat_'))
def callback_edit_repeat(call):
    user_id = str(call.message.chat.id)
    meeting_index = int(call.data.replace('edit_repeat_', ''))
    
    meeting = meetings[user_id][meeting_index]
    current_repeat = meeting.get('repeat', 'none')
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('📅 Не повторювати', callback_data=f'editrep_none_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('🔁 Щоденно', callback_data=f'editrep_daily_{meeting_index}'),
        types.InlineKeyboardButton('🔁 Щотижня', callback_data=f'editrep_weekly_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('🔁 Щомісяця', callback_data=f'editrep_monthly_{meeting_index}')
    )
    markup.add(types.InlineKeyboardButton('◀️ Назад', callback_data=f'edit_select_{meeting_index}'))
    
    repeat_text = {
        'none': 'не повторюється',
        'daily': 'щоденно',
        'weekly': 'щотижня',
        'monthly': 'щомісяця'
    }.get(current_repeat, 'не повторюється')
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        f"🔁 Редагування повторень\n\n"
        f"📝 {meeting['description']}\n"
        f"📅 {meeting['datetime']}\n\n"
        f"Зараз: {repeat_text}\n\n"
        f"Обери новий режим:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Обробка зміни повторення
@bot.callback_query_handler(func=lambda call: call.data.startswith('editrep_'))
def callback_editrep(call):
    user_id = str(call.message.chat.id)
    parts = call.data.split('_')
    new_repeat = parts[1]
    meeting_index = int(parts[2])
    
    meeting = meetings[user_id][meeting_index]
    meeting['repeat'] = new_repeat
    save_meetings()
    
    repeat_text = {
        'none': 'не повторюється',
        'daily': 'щоденно',
        'weekly': 'щотижня',
        'monthly': 'щомісяця'
    }[new_repeat]
    
    bot.answer_callback_query(call.id, f"✅ {repeat_text.capitalize()}")
    
    tag = meeting.get('tag')
    tag_text = f"\n🏷️ {TAGS.get(tag, '')} {tag.capitalize()}" if tag else ""
    
    repeat_emoji = " 🔁" if new_repeat != 'none' else ""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('📅 Дату', callback_data=f'edit_date_{meeting_index}'),
        types.InlineKeyboardButton('🕐 Час', callback_data=f'edit_time_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('📝 Опис', callback_data=f'edit_desc_{meeting_index}'),
        types.InlineKeyboardButton('🏷️ Тег', callback_data=f'edit_tag_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('⏰ Нагадування', callback_data=f'edit_remind_{meeting_index}'),
        types.InlineKeyboardButton('🔁 Повторення', callback_data=f'edit_repeat_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('✅ Готово', callback_data='edit_done')
    )
    
    bot.edit_message_text(
        f"✅ Повторення змінено: {repeat_text}!\n\n"
        f"📅 {meeting['datetime']}{repeat_emoji}\n"
        f"📝 {meeting['description']}{tag_text}\n\n"
        f"Продовжити редагування?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Завершення редагування
@bot.callback_query_handler(func=lambda call: call.data == 'edit_done')
def callback_edit_done(call):
    bot.answer_callback_query(call.id, "✅ Зміни збережено")
    bot.edit_message_text(
        "✅ Зустріч успішно відредаговано!\n\nВикористовуй /list щоб переглянути всі зустрічі",
        call.message.chat.id,
        call.message.message_id
    )

# Скасування редагування
@bot.callback_query_handler(func=lambda call: call.data == 'edit_cancel')
def callback_edit_cancel(call):
    bot.answer_callback_query(call.id, "❌ Скасовано")
    bot.edit_message_text(
        "❌ Редагування скасовано",
        call.message.chat.id,
        call.message.message_id
    )

# Команда /delete
@bot.message_handler(commands=['delete'])
def delete_meeting(message):
    user_id = str(message.chat.id)
    
    if user_id not in meetings or not meetings[user_id]:
        bot.reply_to(message, "📭 У тебе немає зустрічей для видалення.")
        return
    
    markup = types.InlineKeyboardMarkup()
    
    for i, meeting in enumerate(meetings[user_id]):
        dt = datetime.strptime(meeting['datetime'], "%d.%m.%Y %H:%M")
        tag = meeting.get('tag')
        tag_text = f"{TAGS.get(tag, '')} " if tag else ""
        button_text = f"{tag_text}{dt.strftime('%d.%m %H:%M')} - {meeting['description'][:30]}"
        callback_data = f"delete_{i}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    
    bot.reply_to(message, "🗑 Обери зустріч для видалення:", reply_markup=markup)

# Обробка натискань на кнопки видалення
@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def callback_delete(call):
    user_id = str(call.message.chat.id)
    meeting_index = int(call.data.split('_')[1])
    
    if user_id in meetings and meeting_index < len(meetings[user_id]):
        deleted_meeting = meetings[user_id].pop(meeting_index)
        save_meetings()
        
        bot.answer_callback_query(call.id, "✅ Зустріч видалено")
        bot.edit_message_text(
            f"✅ Зустріч видалено:\n\n📝 {deleted_meeting['description']}\n📅 {deleted_meeting['datetime']}",
            call.message.chat.id,
            call.message.message_id
        )
    else:
        bot.answer_callback_query(call.id, "❌ Помилка видалення")

# Команда /repeat для налаштування повторюваних зустрічей
@bot.message_handler(commands=['repeat'])
def repeat_command(message):
    user_id = str(message.chat.id)
    
    if user_id not in meetings or not meetings[user_id]:
        bot.reply_to(message, "📭 У тебе немає зустрічей для налаштування повторень.\n\nДодай зустріч командою /add")
        return
    
    markup = types.InlineKeyboardMarkup()
    
    for i, meeting in enumerate(meetings[user_id]):
        dt = datetime.strptime(meeting['datetime'], "%d.%m.%Y %H:%M")
        repeat_status = "🔁" if meeting.get('repeat', 'none') != 'none' else "📅"
        button_text = f"{repeat_status} {dt.strftime('%d.%m %H:%M')} - {meeting['description'][:25]}"
        callback_data = f"repeat_select_{i}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    
    bot.reply_to(message, "🔁 Обери зустріч для налаштування повторень:", reply_markup=markup)

# Обробка вибору зустрічі для повторень
@bot.callback_query_handler(func=lambda call: call.data.startswith('repeat_select_'))
def callback_repeat_select(call):
    user_id = str(call.message.chat.id)
    meeting_index = int(call.data.replace('repeat_select_', ''))
    
    if user_id not in meetings or meeting_index >= len(meetings[user_id]):
        bot.answer_callback_query(call.id, "❌ Зустріч не знайдено")
        return
    
    meeting = meetings[user_id][meeting_index]
    current_repeat = meeting.get('repeat', 'none')
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('📅 Не повторювати', callback_data=f'repeat_none_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('🔁 Щоденно', callback_data=f'repeat_daily_{meeting_index}'),
        types.InlineKeyboardButton('🔁 Щотижня', callback_data=f'repeat_weekly_{meeting_index}')
    )
    markup.add(
        types.InlineKeyboardButton('🔁 Щомісяця', callback_data=f'repeat_monthly_{meeting_index}')
    )
    
    repeat_text = {
        'none': 'не повторюється',
        'daily': 'щоденно',
        'weekly': 'щотижня',
        'monthly': 'щомісяця'
    }.get(current_repeat, 'не повторюється')
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        f"🔁 Налаштування повторень\n\n📝 {meeting['description']}\n📅 {meeting['datetime']}\n\nЗараз: {repeat_text}\n\nОбери режим:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# Обробка встановлення режиму повторень
@bot.callback_query_handler(func=lambda call: call.data.startswith('repeat_none_') or call.data.startswith('repeat_daily_') or call.data.startswith('repeat_weekly_') or call.data.startswith('repeat_monthly_'))
def callback_set_repeat(call):
    user_id = str(call.message.chat.id)
    parts = call.data.split('_')
    repeat_type = parts[1]
    meeting_index = int(parts[2])
    
    if user_id not in meetings or meeting_index >= len(meetings[user_id]):
        bot.answer_callback_query(call.id, "❌ Зустріч не знайдено")
        return
    
    meeting = meetings[user_id][meeting_index]
    meeting['repeat'] = repeat_type
    save_meetings()
    
    repeat_text = {
        'none': 'не повторюється',
        'daily': 'щоденно',
        'weekly': 'щотижня',
        'monthly': 'щомісяця'
    }[repeat_type]
    
    emoji = "📅" if repeat_type == 'none' else "🔁"
    
    bot.answer_callback_query(call.id, f"✅ {repeat_text.capitalize()}")
    bot.edit_message_text(
        f"{emoji} Повторення налаштовано: {repeat_text}\n\n📝 {meeting['description']}\n📅 {meeting['datetime']}",
        call.message.chat.id,
        call.message.message_id
    )

# Команда /deleteall для масового видалення
@bot.message_handler(commands=['deleteall'])
def deleteall_command(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('📅 За датою', callback_data='delall_date'),
        types.InlineKeyboardButton('📝 За ключовим словом', callback_data='delall_keyword')
    )
    markup.add(
        types.InlineKeyboardButton('🏷️ За тегом', callback_data='delall_tag')
    )
    markup.add(
        types.InlineKeyboardButton('📆 За тиждень', callback_data='delall_week'),
        types.InlineKeyboardButton('📆 За місяць', callback_data='delall_month')
    )
    markup.add(
        types.InlineKeyboardButton('🗑 Всі зустрічі', callback_data='delall_all')
    )
    
    bot.reply_to(message, "🗑 Масове видалення зустрічей\n\nОбери спосіб:", reply_markup=markup)

# Обробка вибору способу видалення
@bot.callback_query_handler(func=lambda call: call.data.startswith('delall_'))
def callback_deleteall(call):
    user_id = str(call.message.chat.id)
    delete_type = call.data.replace('delall_', '')
    
    if delete_type == 'date':
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            "📅 Введи дату для видалення всіх зустрічей у цей день\n\nФормат: ДД.ММ.РРРР\nНаприклад: 20.10.2025",
            call.message.chat.id,
            call.message.message_id
        )
        user_states[user_id] = {'step': 'deleteall_date'}
        
    elif delete_type == 'keyword':
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            "📝 Введи ключове слово\n\nБудуть видалені всі зустрічі, що містять це слово\nНаприклад: Робота",
            call.message.chat.id,
            call.message.message_id
        )
        user_states[user_id] = {'step': 'deleteall_keyword'}
        
    elif delete_type == 'tag':
        markup = types.InlineKeyboardMarkup(row_width=2)
        tag_buttons = [
            types.InlineKeyboardButton(f"{emoji} {tag.capitalize()}", callback_data=f'deltag_{tag}')
            for tag, emoji in TAGS.items()
        ]
        
        for i in range(0, len(tag_buttons), 2):
            markup.add(*tag_buttons[i:i+2])
        
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            "🏷️ Обери тег для видалення всіх зустрічей з цим тегом:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        
    elif delete_type == 'week':
        if user_id not in meetings or not meetings[user_id]:
            bot.answer_callback_query(call.id, "📭 Немає зустрічей")
            return
        
        user_now = get_user_time(user_id)
        week_end = user_now + timedelta(days=7)
        
        original_count = len(meetings[user_id])
        meetings[user_id] = [
            m for m in meetings[user_id]
            if not (user_now <= datetime.strptime(m['datetime'], "%d.%m.%Y %H:%M") <= week_end)
        ]
        
        deleted_count = original_count - len(meetings[user_id])
        save_meetings()
        
        bot.answer_callback_query(call.id, f"✅ Видалено: {deleted_count}")
        bot.edit_message_text(
            f"✅ Видалено всі зустрічі на найближчий тиждень\n\nВидалено зустрічей: {deleted_count}",
            call.message.chat.id,
            call.message.message_id
        )
        
    elif delete_type == 'month':
        if user_id not in meetings or not meetings[user_id]:
            bot.answer_callback_query(call.id, "📭 Немає зустрічей")
            return
        
        user_now = get_user_time(user_id)
        month_end = user_now + timedelta(days=30)
        
        original_count = len(meetings[user_id])
        meetings[user_id] = [
            m for m in meetings[user_id]
            if not (user_now <= datetime.strptime(m['datetime'], "%d.%m.%Y %H:%M") <= month_end)
        ]
        
        deleted_count = original_count - len(meetings[user_id])
        save_meetings()
        
        bot.answer_callback_query(call.id, f"✅ Видалено: {deleted_count}")
        bot.edit_message_text(
            f"✅ Видалено всі зустрічі на найближчий місяць\n\nВидалено зустрічей: {deleted_count}",
            call.message.chat.id,
            call.message.message_id
        )
        
    elif delete_type == 'all':
        if user_id not in meetings or not meetings[user_id]:
            bot.answer_callback_query(call.id, "📭 Немає зустрічей")
            return
        
        count = len(meetings[user_id])
        meetings[user_id] = []
        save_meetings()
        
        bot.answer_callback_query(call.id, f"✅ Видалено: {count}")
        bot.edit_message_text(
            f"✅ Видалено ВСІ зустрічі\n\nВидалено зустрічей: {count}",
            call.message.chat.id,
            call.message.message_id
        )

# Обробник видалення за тегом
@bot.callback_query_handler(func=lambda call: call.data.startswith('deltag_'))
def callback_delete_by_tag(call):
    user_id = str(call.message.chat.id)
    tag = call.data.replace('deltag_', '')
    
    if user_id not in meetings or not meetings[user_id]:
        bot.answer_callback_query(call.id, "📭 Немає зустрічей")
        return
    
    original_count = len(meetings[user_id])
    meetings[user_id] = [m for m in meetings[user_id] if m.get('tag') != tag]
    
    deleted_count = original_count - len(meetings[user_id])
    save_meetings()
    
    tag_emoji = TAGS.get(tag, '')
    bot.answer_callback_query(call.id, f"✅ Видалено: {deleted_count}")
    bot.edit_message_text(
        f"✅ Видалено всі зустрічі з тегом {tag_emoji} {tag.capitalize()}\n\nВидалено зустрічей: {deleted_count}",
        call.message.chat.id,
        call.message.message_id
    )

# Обробка введення дати для видалення
@bot.message_handler(func=lambda message: str(message.chat.id) in user_states and user_states[str(message.chat.id)].get('step') == 'deleteall_date')
def process_deleteall_date(message):
    user_id = str(message.chat.id)
    
    try:
        date_obj = datetime.strptime(message.text, '%d.%m.%Y')
        date_str = date_obj.strftime('%d.%m.%Y')
        
        if user_id not in meetings or not meetings[user_id]:
            bot.send_message(message.chat.id, "📭 У тебе немає зустрічей для видалення.")
            del user_states[user_id]
            return
        
        original_count = len(meetings[user_id])
        meetings[user_id] = [
            m for m in meetings[user_id]
            if not m['datetime'].startswith(date_str)
        ]
        
        deleted_count = original_count - len(meetings[user_id])
        save_meetings()
        
        bot.send_message(message.chat.id, f"✅ Видалено всі зустрічі на {date_str}\n\nВидалено зустрічей: {deleted_count}")
        del user_states[user_id]
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Невірний формат дати!\n\nВикористовуй: ДД.ММ.РРРР\nНаприклад: 20.10.2025")

# Обробка введення ключового слова для видалення
@bot.message_handler(func=lambda message: str(message.chat.id) in user_states and user_states[str(message.chat.id)].get('step') == 'deleteall_keyword')
def process_deleteall_keyword(message):
    user_id = str(message.chat.id)
    keyword = message.text.lower()
    
    if user_id not in meetings or not meetings[user_id]:
        bot.send_message(message.chat.id, "📭 У тебе немає зустрічей для видалення.")
        del user_states[user_id]
        return
    
    original_count = len(meetings[user_id])
    meetings[user_id] = [
        m for m in meetings[user_id]
        if keyword not in m['description'].lower()
    ]
    
    deleted_count = original_count - len(meetings[user_id])
    save_meetings()
    
    bot.send_message(message.chat.id, f"✅ Видалено всі зустрічі що містять '{message.text}'\n\nВидалено зустрічей: {deleted_count}")
    del user_states[user_id]

# Команда /stats для статистики
@bot.message_handler(commands=['stats'])
def stats_command(message):
    user_id = str(message.chat.id)
    
    has_history = user_id in meetings_history and meetings_history[user_id]
    has_upcoming = user_id in meetings and meetings[user_id]
    
    if not has_history and not has_upcoming:
        bot.reply_to(message, "📭 У тебе поки немає зустрічей для статистики.\n\nДодай зустрічі командою /add")
        return
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('📊 За тиждень', callback_data='stats_week'),
        types.InlineKeyboardButton('📊 За місяць', callback_data='stats_month')
    )
    markup.add(
        types.InlineKeyboardButton('📊 За весь час', callback_data='stats_all')
    )
    
    bot.reply_to(message, "📊 Статистика зустрічей\n\nОбери період:", reply_markup=markup)

# Обробка вибору періоду статистики
@bot.callback_query_handler(func=lambda call: call.data.startswith('stats_'))
def callback_stats(call):
    user_id = str(call.message.chat.id)
    period = call.data.replace('stats_', '')
    
    if user_id not in meetings_history or not meetings_history[user_id]:
        if user_id not in meetings or not meetings[user_id]:
            bot.answer_callback_query(call.id, "📭 Немає даних")
            return
    
    user_now = get_user_time(user_id)
    tz = get_user_timezone(user_id)
    tz_str = get_timezone_string(tz)
    
    if period == 'week':
        start_date = user_now - timedelta(days=7)
        period_name = "за останній тиждень"
    elif period == 'month':
        start_date = user_now - timedelta(days=30)
        period_name = "за останній місяць"
    else:
        start_date = datetime(2000, 1, 1)
        period_name = "за весь час"
    
    period_meetings = []
    if user_id in meetings_history:
        period_meetings = [
            m for m in meetings_history[user_id]
            if datetime.strptime(m['datetime'], "%d.%m.%Y %H:%M") >= start_date
        ]
    
    total_completed = sum(1 for m in period_meetings if m.get('auto_completed', False))
    
    upcoming_meetings = []
    if user_id in meetings:
        if period == 'week':
            end_date = user_now + timedelta(days=7)
        elif period == 'month':
            end_date = user_now + timedelta(days=30)
        else:
            end_date = datetime(2100, 1, 1)
        
        upcoming_meetings = [
            m for m in meetings[user_id]
            if user_now <= datetime.strptime(m['datetime'], "%d.%m.%Y %H:%M") <= end_date
        ]
    
    total_upcoming = len(upcoming_meetings)
    
    if not period_meetings and not upcoming_meetings:
        bot.answer_callback_query(call.id, "📭 Немає зустрічей за цей період")
        bot.edit_message_text(
            f"📭 Немає зустрічей {period_name}",
            call.message.chat.id,
            call.message.message_id
        )
        return
    
    descriptions = [m['description'] for m in period_meetings]
    description_counter = Counter(descriptions)
    top_descriptions = description_counter.most_common(3)
    
    morning = 0
    afternoon = 0
    evening = 0
    night = 0
    
    for m in period_meetings:
        hour = int(m['datetime'].split()[1].split(':')[0])
        if 6 <= hour < 12:
            morning += 1
        elif 12 <= hour < 18:
            afternoon += 1
        elif 18 <= hour < 24:
            evening += 1
        else:
            night += 1
    
    weekday_stats = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    weekday_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд']
    
    for m in period_meetings:
        dt = datetime.strptime(m['datetime'], "%d.%m.%Y %H:%M")
        weekday = dt.weekday()
        weekday_stats[weekday] += 1
    
    response = f"📊 **Статистика {period_name}**\n"
    response += f"🌍 {tz_str}\n\n"
    
    response += "**📈 Загальна статистика:**\n"
    response += f"• 📅 Майбутні зустрічі: {total_upcoming}\n"
    response += f"• ✅ Завершені зустрічі: {total_completed}\n\n"
    
    if top_descriptions:
        response += "**🏷️ Найчастіші теми:**\n"
        for desc, count in top_descriptions:
            display_desc = desc if len(desc) <= 40 else desc[:37] + "..."
            response += f"• {display_desc}: {count} раз\n"
        response += "\n"
    
    if period_meetings:
        response += "**⏰ Розподіл за часом доби:**\n"
        response += f"• 🌅 Ранок (6-12): {morning} зустрічей\n"
        response += f"• ☀️ День (12-18): {afternoon} зустрічей\n"
        response += f"• 🌆 Вечір (18-24): {evening} зустрічей\n"
        response += f"• 🌙 Ніч (0-6): {night} зустрічей\n\n"
        
        response += "**📊 Графік по днях тижня:**\n"
        max_count = max(weekday_stats.values()) if weekday_stats.values() else 1
        for day_num, count in weekday_stats.items():
            day_name = weekday_names[day_num]
            bars = '█' * int((count / max_count * 10)) if max_count > 0 else ''
            response += f"{day_name}: {bars} {count}\n"
        
        if weekday_stats.values() and max(weekday_stats.values()) > 0:
            most_productive_day = weekday_names[max(weekday_stats, key=weekday_stats.get)]
            response += f"\n🏆 Найзавантаженіший день: **{most_productive_day}**"
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

# Обробка кнопок дій з нагадуваннями
@bot.callback_query_handler(func=lambda call: call.data.startswith('action_'))
def callback_meeting_action(call):
    user_id = str(call.message.chat.id)
    action_parts = call.data.split('_')
    action_type = action_parts[1]
    meeting_index = int(action_parts[2])
    
    if action_type == 'reschedule':
        if user_id in meetings and meeting_index < len(meetings[user_id]):
            meeting = meetings[user_id][meeting_index]
            
            current_datetime = datetime.strptime(meeting['datetime'], "%d.%m.%Y %H:%M")
            
            new_datetime = current_datetime + timedelta(days=1)
            meeting['datetime'] = new_datetime.strftime("%d.%m.%Y %H:%M")
            
            meeting['notified_before'] = False
            meeting['notified_now'] = False
            
            if 'notifications_sent' in meeting:
                for key in meeting['notifications_sent']:
                    meeting['notifications_sent'][key] = False
            
            save_meetings()
            
            bot.answer_callback_query(call.id, "✅ Перенесено на завтра")
            bot.edit_message_text(
                f"🔁 Зустріч перенесена на завтра!\n\n📝 {meeting['description']}\n📅 {meeting['datetime']}",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.answer_callback_query(call.id, "❌ Помилка перенесення")
    
    elif action_type == 'ok':
        if user_id in meetings and meeting_index < len(meetings[user_id]):
            meetings[user_id][meeting_index]['completed'] = True
            save_meetings()
        
        bot.answer_callback_query(call.id, "✅ OK")
        bot.edit_message_text(
            f"{call.message.text}\n\n✅ Прийнято!",
            call.message.chat.id,
            call.message.message_id
        )
    
    elif action_type == 'del':
        if user_id in meetings and meeting_index < len(meetings[user_id]):
            deleted_meeting = meetings[user_id].pop(meeting_index)
            save_meetings()
            
            bot.answer_callback_query(call.id, "✅ Зустріч видалено")
            bot.edit_message_text(
                f"🗑 Зустріч видалено!\n\n📝 {deleted_meeting['description']}\n📅 {deleted_meeting['datetime']}",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.answer_callback_query(call.id, "❌ Помилка видалення")

# Фоновий процес для відправки нагадувань
def send_reminders():
    while True:
        try:
            clean_old_meetings()
            
            for user_id, user_meetings in meetings.items():
                user_now = get_user_time(user_id)
                tz = get_user_timezone(user_id)
                tz_str = get_timezone_string(tz)
                
                for meeting_index, meeting in enumerate(user_meetings):
                    meeting_time = datetime.strptime(meeting['datetime'], "%d.%m.%Y %H:%M")
                    time_diff = (meeting_time - user_now).total_seconds()
                    
                    # Перевіряємо, чи є список нагадувань (новий формат) або одне нагадування (старий формат)
                    reminder_minutes_list = meeting.get('reminder_minutes')
                    
                    # Підтримка старого формату (одне число)
                    if isinstance(reminder_minutes_list, int):
                        reminder_minutes_list = [reminder_minutes_list]
                        meeting['reminder_minutes'] = reminder_minutes_list
                        meeting['notifications_sent'] = {str(reminder_minutes_list[0]): False}
                        save_meetings()
                    
                    # Ініціалізуємо notifications_sent якщо його немає
                    if 'notifications_sent' not in meeting:
                        meeting['notifications_sent'] = {}
                        for reminder_min in reminder_minutes_list:
                            meeting['notifications_sent'][str(reminder_min)] = False
                        save_meetings()
                    
                    # Перевіряємо кожне нагадування
                    for reminder_minutes in reminder_minutes_list:
                        reminder_seconds = reminder_minutes * 60
                        reminder_key = str(reminder_minutes)
                        
                        # Відправляємо нагадування, якщо час підійшов і воно ще не відправлено
                        if not meeting['notifications_sent'].get(reminder_key, False) and 0 < time_diff <= reminder_seconds:
                            markup = types.InlineKeyboardMarkup()
                            markup.add(
                                types.InlineKeyboardButton('🔁 Перенести на завтра', callback_data=f'action_reschedule_{meeting_index}')
                            )
                            markup.add(
                                types.InlineKeyboardButton('✅ OK', callback_data=f'action_ok_{meeting_index}'),
                                types.InlineKeyboardButton('🗑 Видалити', callback_data=f'action_del_{meeting_index}')
                            )
                            
                            tag = meeting.get('tag')
                            tag_text = f"\n🏷️ {TAGS.get(tag, '')} {tag.capitalize()}" if tag else ""
                            
                            # Форматуємо час нагадування
                            if reminder_minutes >= 1440:
                                time_text = f"{reminder_minutes // 1440} день"
                            elif reminder_minutes >= 60:
                                time_text = f"{reminder_minutes // 60} година"
                            else:
                                time_text = f"{reminder_minutes} хвилин"
                            
                            reminder_text = f"⏰ НАГАДУВАННЯ!\n\n📝 {meeting['description']}{tag_text}\n🕐 Через {time_text}\n📅 {meeting['datetime']}\n🌍 {tz_str}"
                            bot.send_message(int(user_id), reminder_text, reply_markup=markup)
                            
                            meeting['notifications_sent'][reminder_key] = True
                            save_meetings()
                    
                    # Нагадування у вказаний час
                    if not meeting.get('notified_now', False) and -60 <= time_diff <= 0:
                        tag = meeting.get('tag')
                        tag_text = f"\n🏷️ {TAGS.get(tag, '')} {tag.capitalize()}" if tag else ""
                        
                        reminder_text = f"🔔 ЗУСТРІЧ ПОЧАЛАСЬ!\n\n📝 {meeting['description']}{tag_text}\n🕐 {meeting['datetime']}\n🌍 {tz_str}\n\n⏰ Саме час!"
                        bot.send_message(int(user_id), reminder_text)
                        meeting['notified_now'] = True
                        
                        repeat_type = meeting.get('repeat', 'none')
                        if repeat_type != 'none':
                            meeting_time = datetime.strptime(meeting['datetime'], "%d.%m.%Y %H:%M")
                            
                            if repeat_type == 'daily':
                                new_time = meeting_time + timedelta(days=1)
                            elif repeat_type == 'weekly':
                                new_time = meeting_time + timedelta(weeks=1)
                            elif repeat_type == 'monthly':
                                new_time = meeting_time + timedelta(days=30)
                            
                            # Створюємо новий словник для відстеження повідомлень
                            new_notifications_status = {}
                            for reminder_min in reminder_minutes_list:
                                new_notifications_status[str(reminder_min)] = False
                            
                            new_meeting = {
                                "datetime": new_time.strftime("%d.%m.%Y %H:%M"),
                                "description": meeting['description'],
                                "notified_before": False,
                                "notified_now": False,
                                "reminder_minutes": reminder_minutes_list,
                                "notifications_sent": new_notifications_status,
                                "repeat": repeat_type,
                                "completed": False,
                                "tag": meeting.get('tag')
                            }
                            
                            user_meetings.append(new_meeting)
                        
                        save_meetings()
            
            time.sleep(30)
            
        except Exception as e:
            print(f"Помилка в send_reminders: {e}")
            time.sleep(30)

# Запуск бота
if __name__ == "__main__":
    load_meetings()
    load_settings()
    load_history()
    
    reminder_thread = threading.Thread(target=send_reminders, daemon=True)
    reminder_thread.start()
    
    print("🤖 Бот запущено!")
    bot.infinity_polling()