import os
import json
import requests

# Этот словарь будем возвращать, как результат функции.
FUNC_RESPONSE = {
    'statusCode': 200,
    'body': ''
}

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")
OPENWEATHER_API_URL = "http://api.openweathermap.org/data/2.5/weather"
YANDEX_SPEECHKIT_API_KEY = os.environ.get("YANDEX_SPEECHKIT_API_KEY")
YANDEX_SPEECHKIT_ASR_API_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
YANDEX_SPEECHKIT_TTS_API_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"

def send_message(text, chat_id, reply_to_message_id=None):
    reply_message = {'chat_id': chat_id, 'text': text}
    if reply_to_message_id:
        reply_message['reply_to_message_id'] = reply_to_message_id
    requests.post(url=f'{TELEGRAM_API_URL}/sendMessage', json=reply_message)

def get_weather(city_name):
    params = {
        'q': city_name,
        'appid': OPENWEATHER_API_KEY,
        'units': 'metric',
        'lang': 'ru'
    }
    response = requests.get(OPENWEATHER_API_URL, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        return None

def synthesize_speech(text):
    headers = {
        'Authorization': f'Api-Key {YANDEX_SPEECHKIT_API_KEY}'
    }
    data = {
        'text': text,
        'lang': 'ru-RU',
        'voice': 'oksana',
        'format': 'oggopus'
    }
    response = requests.post(YANDEX_SPEECHKIT_TTS_API_URL, headers=headers, data=data)
    if response.status_code == 200:
        return response.content
    else:
        return None

def recognize_speech(file_path):
    headers = {
        'Authorization': f'Api-Key {YANDEX_SPEECHKIT_API_KEY}'
    }
    with open(file_path, 'rb') as f:
        data = f.read()
    response = requests.post(YANDEX_SPEECHKIT_ASR_API_URL, headers=headers, data=data)
    if response.status_code == 200:
        result = response.json()
        return result.get('result', None)
    else:
        return None

def handle_start_help(chat_id):
    text = ("Я расскажу о текущей погоде для населенного пункта.\n\n"
            "Я могу ответить на:\n"
            "- Текстовое сообщение с названием населенного пункта.\n"
            "- Голосовое сообщение с названием населенного пункта.\n"
            "- Сообщение с геопозицией.")
    send_message(text, chat_id)

def handle_text_message(message):
    chat_id = message['chat']['id']
    text = message['text']
    weather = get_weather(text)
    if weather:
        response_text = (
            f"{weather['weather'][0]['description'].capitalize()}.\n"
            f"Температура {weather['main']['temp']} ℃, ощущается как {weather['main']['feels_like']} ℃.\n"
            f"Атмосферное давление {weather['main']['pressure']} мм рт. ст.\n"
            f"Влажность {weather['main']['humidity']} %.\n"
            f"Видимость {weather['visibility']} метров.\n"
            f"Ветер {weather['wind']['speed']} м/с {weather['wind']['deg']}.\n"
            f"Восход солнца {weather['sys']['sunrise']} МСК. Закат {weather['sys']['sunset']} МСК."
        )
    else:
        response_text = f"Я не нашел населенный пункт \"{text}\"."
    send_message(response_text, chat_id, message['message_id'])

def handle_voice_message(message):
    chat_id = message['chat']['id']
    voice_duration = message['voice']['duration']
    if voice_duration > 30:
        response_text = "Я не могу обработать это голосовое сообщение."
        send_message(response_text, chat_id, message['message_id'])
        return

    # Получение URL для загрузки голосового сообщения
    file_id = message['voice']['file_id']
    file_info = requests.get(f"{TELEGRAM_API_URL}/getFile?file_id={file_id}").json()
    file_path = file_info['result']['file_path']
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"

    # Скачивание голосового сообщения
    voice_response = requests.get(file_url)
    voice_file_path = "/tmp/voice.ogg"
    with open(voice_file_path, 'wb') as f:
        f.write(voice_response.content)

    # Распознавание текста из голосового сообщения
    recognized_text = recognize_speech(voice_file_path)
    if recognized_text:
        weather = get_weather(recognized_text)
        if weather:
            response_text = (
                f"Населенный пункт {recognized_text}.\n"
                f"{weather['weather'][0]['description'].capitalize()}.\n"
                f"Температура {round(weather['main']['temp'])} градусов цельсия.\n"
                f"Ощущается как {round(weather['main']['feels_like'])} градусов цельсия.\n"
                f"Давление {round(weather['main']['pressure'])} миллиметров ртутного столба.\n"
                f"Влажность {round(weather['main']['humidity'])} процентов."
            )
            speech = synthesize_speech(response_text)
            if speech:
                files = {'voice': ('weather.ogg', speech, 'audio/ogg')}
                data = {'chat_id': chat_id, 'reply_to_message_id': message['message_id']}
                requests.post(url=f'{TELEGRAM_API_URL}/sendVoice', data=data, files=files)
        else:
            response_text = f"Я не нашел населенный пункт \"{recognized_text}\"."
            send_message(response_text, chat_id, message['message_id'])
    else:
        response_text = "Не удалось распознать голосовое сообщение."
        send_message(response_text, chat_id, message['message_id'])

def handle_location_message(message):
    chat_id = message['chat']['id']
    latitude = message['location']['latitude']
    longitude = message['location']['longitude']
    params = {
        'lat': latitude,
        'lon': longitude,
        'appid': OPENWEATHER_API_KEY,
        'units': 'metric',
        'lang': 'ru'
    }
    response = requests.get(OPENWEATHER_API_URL, params=params)
    if response.status_code == 200:
        weather = response.json()
        response_text = (
            f"{weather['weather'][0]['description'].capitalize()}.\n"
            f"Температура {weather['main']['temp']} ℃, ощущается как {weather['main']['feels_like']} ℃.\n"
            f"Атмосферное давление {weather['main']['pressure']} мм рт. ст.\n"
            f"Влажность {weather['main']['humidity']} %.\n"
            f"Видимость {weather['visibility']} метров.\n"
            f"Ветер {weather['wind']['speed']} м/с {weather['wind']['deg']}.\n"
            f"Восход солнца {weather['sys']['sunrise']} МСК. Закат {weather['sys']['sunset']} МСК."
        )
    else:
        response_text = "Я не знаю какая погода в этом месте."
    send_message(response_text, chat_id, message['message_id'])

def handler(event, context):
    if TELEGRAM_BOT_TOKEN is None:
        return FUNC_RESPONSE

    update = json.loads(event['body'])

    if 'message' not in update:
        return FUNC_RESPONSE

    message_in = update['message']

    if 'text' in message_in:
        if message_in['text'] in ['/start', '/help']:
            handle_start_help(message_in['chat']['id'])
        else:
            handle_text_message(message_in)
    elif 'voice' in message_in:
        handle_voice_message(message_in)
    elif 'location' in message_in:
        handle_location_message(message_in)
    else:
        response_text = ("Я не могу ответить на такой тип сообщения.\n"
                         "Но могу ответить на:\n"
                         "- Текстовое сообщение с названием населенного пункта.\n"
                         "- Голосовое сообщение с названием населенного пункта.\n"
                         "- Сообщение с геопозицией.")
        send_message(response_text, message_in['chat']['id'], message_in['message_id'])

    return FUNC_RESPONSE
