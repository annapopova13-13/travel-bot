import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import pandas as pd
from math import radians, sin, cos, sqrt, atan2
import os
import json

VK_TOKEN = os.environ.get("VK_TOKEN")
GROUP_ID = int(os.environ.get("VK_GROUP_ID"))
CSV_FILE = "places.csv"

if not VK_TOKEN or not GROUP_ID:
    print("❌ ОШИБКА: Задайте переменные окружения VK_TOKEN и VK_GROUP_ID!")
    exit()

try:
    df = pd.read_csv(CSV_FILE, encoding='utf-8')
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
                if text in ["start", "начать", "привет", "/start"]:
                    vk.messages.send(peer_id=peer_id, message="Привет! Я твой гид по Санкт-Петербургу!\n\nВыбери, что тебя интересует:", random_id=0, keyboard=get_main_keyboard())
                elif text == "❓ помощь" or text == "помощь":
                    help_text = "📍 Просто отправь мне свою геолокацию после выбора категории!\n\nЯ найду рядом: кафе, рестораны, музеи, парки и другие интересные места."
                    vk.messages.send(peer_id=peer_id, message=help_text, random_id=0, keyboard=get_main_keyboard())
                elif text == "🍔 хочу поесть":
                    user_choice[user_id] = 'еда'
                    vk.messages.send(peer_id=peer_id, message="Отлично! Поделись своей геолокацией, и я найду ближайшие кафе и рестораны 🍕", random_id=0, keyboard=get_location_keyboard())
                elif text == "🏛️ хочу в музей":
                    user_choice[user_id] = 'культура'
                    vk.messages.send(peer_id=peer_id, message="Прекрасный выбор! Отправь геолокацию, и я покажу ближайшие музеи и достопримечательности 🏛️", random_id=0, keyboard=get_location_keyboard())
                geo_found = False
                if 'attachments' in msg:
                    for attachment in msg['attachments']:
                        if attachment['type'] == 'geo':
                            user_lat = attachment['geo']['coordinates']['lat']
                            user_lon = attachment['geo']['coordinates']['long']
                            geo_found = True
                            search_type = user_choice.get(user_id, 'еда')
                            nearest = find_nearest_places(float(user_lat), float(user_lon), search_type, 5)
                            if not nearest:
                                reply_msg = f"К сожалению, рядом ничего не найдено. Попробуйте выбрать другую категорию или переместитесь в центр города 🗺️"
                                vk.messages.send(peer_id=peer_id, message=reply_msg, random_id=0, keyboard=get_main_keyboard())
                            else:
                                type_name = "заведений" if search_type == "еда" else "музеев"
                                result_message = f"📍 Я нашел {len(nearest)} {type_name} поблизости:\n\n"
                                for item in nearest:
                                    index, row, dist = item
                                    result_message += f"🏷️ *{row['Полное название']}*\n📌 Адрес: {row['Адрес']}\n"
                                    if pd.notna(row.get('Рейтинг (звёзды в яндекс-картах)', '')):
                                        result_message += f"⭐ Рейтинг: {row['Рейтинг (звёзды в яндекс-картах)']}\n"
                                    site = row.get('Ссылка на официальный сайт', '')
                                    if pd.notna(site) and str(site).startswith('http'):
                                        result_message += f"🔗 [Сайт]({site})\n"
                                    result_message += f"📏 Расстояние: {dist:.1f} км\n\n"
                                result_message += "_Надеюсь, найдется что-то по душе! ✨_"
                                vk.messages.send(peer_id=peer_id, message=result_message, random_id=0, keyboard=get_main_keyboard(), disable_web_link_preview=False)
                            break
                if not geo_found and text and text not in ["start", "начать", "привет", "/start", "🍔 хочу поесть", "🏛️ хочу в музей", "❓ помощь", "помощь"]:
                    vk.messages.send(peer_id=peer_id, message="Я тебя не понял 😊\n\nПожалуйста, используй кнопки меню или напиши 'Помощь' для справки.", random_id=0, keyboard=get_main_keyboard())
            except Exception as e:
                print(f"⚠️ Произошла ошибка: {e}")
                try:
                    vk.messages.send(peer_id=peer_id, message="Произошла небольшая ошибка. Пожалуйста, начни заново командой 'Начать'", random_id=0)
                except:
                    pass

if __name__ == "__main__":
    main()
