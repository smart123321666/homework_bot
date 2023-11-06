import logging
import os
import requests
import sys
import time

import telegram

from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)


def check_tokens():
    """Проверяет переменные окружения."""
    for token in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
        if not token:
            logging.critical(
                f'Отсутствует переменная окружения: {token}'
            )
            sys.exit(1)
    return (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)


def send_message(bot, message):
    """Отправляет сообщение в чат телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug("Сообщение успешно отправлено")
    except Exception as error:
        logging.error(f"Отправка сообщения невозможна: {error}")


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает статусы работ."""
    timestamp = 0 if not timestamp else int(time.time())
    params = {'from_date': timestamp}

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            raise KeyError(f"Некорректный статус кода {response.status_code}")
        return response.json()
    except Exception as error:
        raise KeyError(f"Возникла ошибка: {error}")


def check_response(response):
    """Проверяет ответ API на корректность."""
    if type(response) != dict:
        raise TypeError('Тип данных не соотвествует ожидаемуму результату')
    if 'homeworks' not in response:
        raise KeyError("Нет ключа homeworks")
    homeworks = response.get('homeworks')
    if type(homeworks) != list:
        raise TypeError('homeworks данные приходят не в виде списка ')

    return homeworks


def parse_status(homework):
    """Извлекает информацию о конкретной домашней работы статус работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not homework_name:
        raise KeyError("Нет ключа homework_name")
    if not homework:
        raise KeyError("Нет ключа homework")
    for homework in HOMEWORK_VERDICTS:
        if homework_status in HOMEWORK_VERDICTS:
            verdict = HOMEWORK_VERDICTS[homework_status]
            return (
                f'Изменился статус проверки работы "{homework_name}". '
                f'{verdict}')
    raise KeyError(f'Неизвестный статус домашней работы {homework_status}.')


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    prev_msg = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            if not response:
                logging.error("Не удалось получить ответ от API")
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
            else:
                message = "Ничего нового не произошло"
            if message != prev_msg:
                send_message(bot, message)
                prev_msg = message
            else:
                logging.info(message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message, exc_info=True)
            if message != prev_msg:
                send_message(bot, message)
                prev_msg = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
