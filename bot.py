import subprocess
import sys
import os

# ------------------ УСТАНОВКА БИБЛИОТЕК ------------------
libraries = ["vk-api", "pandas"]
for lib in libraries:
    try:
        __import__(lib.replace("-", "_"))
    except ImportError:
        print(f"Устанавливаю {lib}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
# ---------------------------------------------------------

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import pandas as pd
from math import radians, sin, cos, sqrt, atan2
import json

# ===== БЕЗОПАСНО: Токен и ID из переменных окружения =====
VK_TOKEN = os.environ.get("VK_TOKEN")
GROUP_ID = int(os.environ.get("VK_GROUP_ID"))

if not VK_TOKEN or not GROUP_ID:
    print("❌ ОШИБКА: Задайте переменные окружения VK_TOKEN и VK_GROUP_ID!")
    exit()
# =========================================================

CSV_FILE = "Shablon_tablitsy.csv"

# Загружаем данные (on_bad_lines='skip' пропускает кривые строки)
try:
    df = pd.read_csv(CSV_FILE, encoding='utf-8', on_bad_lines='skip')
    print(f"✅ База загружена! Найдено мест: {len(df)}")
except Exception as e:
    print(f"❌ Ошибка загрузки базы: {e}")
    exit()

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def find_nearest_places(user_lat, user_lon, place_type, n=5):
    if 'Тип' not in df.columns:
        print("❌ В файле нет столбца 'Тип'")
        return []
    filtered_df = df[df['Тип'].str.lower() == place_type.lower()]
    if filtered_df.empty:
        return []
    distances = []
    for index, row in filtered_df.iterrows():
        coords = str(row['Координаты']).split(',')
        if len(coords) == 2:
            try:
                place_lat = float(coords[0].strip())
                place_lon = float(coords[1].strip())
                dist = calculate_distance(user_lat, user_lon, place_lat, place_lon)
                distances.append((index, row, dist))
            except:
                continue
    distances.sort(key=lambda x: x[2])
    return distances[:n]

def get_main_keyboard():
    keyboard = {
        "one_time": False,
        "buttons": [
            [{"action": {"type": "text", "label": "🍔 Хочу поесть"}, "color": "positive"}],
            [{"action": {"type": "text", "label": "🏛️ Хочу в музей"}, "color": "primary"}],
            [{"action": {"type": "text", "label": "❓ Помощь"}, "color": "secondary"}]
        ]
    }
    return json.dumps(keyboard, ensure_ascii=False)

def get_location_keyboard():
    keyboard = {
        "one_time": True,
        "buttons": [
            [{"action": {"type": "location", "label": "📍 Отправить моё местоположение"}}]
        ]
    }
    return json.dumps(keyboard, ensure_ascii=False)

def main():
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, GROUP_ID)
    print("🤖 Бот успешно запущен и ждет сообщений!")
    user_choice = {}
    
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            try:
                msg = event.object.message
                user_id = msg['from_id']
                text = msg['text'].lower().strip() if msg['text'] else ""
                peer_id = msg['peer_id']
                
                print(f"Получено сообщение: {text}")
                
                if text in ["начать", "старт", "привет", "start", "/start"]:
                    vk.messages.send(
                        peer_id=peer_id,
                        message="Привет! Я твой гид по Санкт-Петербургу!\n\nВыбери, что тебя интересует:",
                        random_id=0,
                        keyboard=get_main_keyboard()
                    )
                elif text in ["помощь", "❓ помощь", "help"]:
                    vk.messages.send(
                        peer_id=peer_id,
                        message="📍 Отправь геолокацию после выбора категории!\n\nЯ найду: кафе, рестораны, музеи, парки",
                        random_id=0,
                        keyboard=get_main_keyboard()
                    )
                elif "поесть" in text:
                    user_choice[user_id] = 'еда'
                    vk.messages.send(
                        peer_id=peer_id,
                        message="Отлично! Поделись геолокацией, найду кафе и рестораны 🍕",
                        random_id=0,
                        keyboard=get_location_keyboard()
                    )
                elif "музей" in text:
                    user_choice[user_id] = 'культура'
                    vk.messages.send(
                        peer_id=peer_id,
                        message="Отправь геолокацию, покажу музеи и достопримечательности 🏛️",
                        random_id=0,
                        keyboard=get_location_keyboard()
                    )
                else:
                    vk.messages.send(
                        peer_id=peer_id,
                        message="Я тебя не понял 😊\n\nНапиши 'Начать' или выбери действие из кнопок",
                        random_id=0,
                        keyboard=get_main_keyboard()
                    )
                
                if 'attachments' in msg:
                    for attachment in msg['attachments']:
                        if attachment['type'] == 'geo':
                            user_lat = attachment['geo']['coordinates']['lat']
                            user_lon = attachment['geo']['coordinates']['long']
                            search_type = user_choice.get(user_id, 'еда')
                            nearest = find_nearest_places(user_lat, user_lon, search_type, 5)
                            
                            if not nearest:
                                vk.messages.send(peer_id=peer_id, message="Рядом ничего не найдено 🗺️", random_id=0, keyboard=get_main_keyboard())
                            else:
                                type_name = "заведений" if search_type == "еда" else "музеев"
                                result_message = f"📍 Нашел {len(nearest)} {type_name} рядом:\n\n"
                                for item in nearest:
                                    index, row, dist = item
                                    result_message += f"🏷️ {row['Полное название']}\n📌 {row['Адрес']}\n"
                                    if pd.notna(row.get('Рейтинг (звёзды в яндекс-картах)', '')):
                                        result_message += f"⭐ Рейтинг: {row['Рейтинг (звёзды в яндекс-картах)']}\n"
                                    result_message += f"📏 {dist:.1f} км\n\n"
                                vk.messages.send(peer_id=peer_id, message=result_message, random_id=0, keyboard=get_main_keyboard())
                            break
                            
            except Exception as e:
                print(f"Ошибка: {e}")

if __name__ == "__main__":
    main()
