import logging
import os
import sys
import time
from http import HTTPStatus

import requests
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


def check_tokens():
    """Проверяет переменные окружения."""
    source = ("PRACTICUM_TOKEN", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID")
    missing_tokens = [token for token in source if not globals()[token]]

    if missing_tokens:
        error_message = f'''
        Отсутствуют переменные окружения: {", ".join(missing_tokens)}'''
        logging.critical(error_message)
        sys.exit(1)


def send_message(bot, message):
    """Отправляет сообщение в чат телеграм."""
    logging.debug("Начало отправки сообщения.")
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug("Сообщение успешно отправлено")
    except telegram.TelegramError as error:
        logging.error(f"Отправка сообщения невозможна: {error}")


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает статусы работ."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as error:
        raise ConnectionError("Возникла ошибка"
                              f"при отправке запроса к API: {error}."
                              f"Запрос к API с параметрами {params}")
    if response.status_code != HTTPStatus.OK:
        raise ValueError(f"Некорректный статус кода{response.status_code}")
    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    logging.debug("Начало проверки ответа сервера.")
    if not isinstance(response, dict):
        raise TypeError('Тип данных не соответствует ожидаемому результату.'
                        'Ожидался тип dict, получен тип:'
                        '{}'.format(type(response)))
    if 'current_date' not in response:
        raise KeyError("Отсутствует ключ 'current_date' в ответе сервера.")
    if 'homeworks' not in response:
        raise KeyError("Нет ключа homeworks")
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('homeworks данные приходят не в виде списка'
                        '{}'.format(type(homeworks)))

    return homeworks


def parse_status(homework):
    """Извлекает информацию о конкретной домашней работы статус работы."""
    homework_name = homework.get('homework_name')
    if not homework:
        raise KeyError("Нет ключа homework")
    homework_status = homework.get('status')
    if not homework_status:
        raise KeyError("Нет ключа status")
    if not homework_name:
        raise KeyError("Нет ключа homework_name")
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Неизвестный статус домашней работы'
                       f'{homework_status}.')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if verdict is not None:
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    prev_msg = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                prev_msg = message
            else:
                message = "Ничего нового не произошло"
                logging.debug(message)
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message, exc_info=True)
            if message != prev_msg:
                send_message(bot, message)
                prev_msg = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    stdout_handler = logging.StreamHandler(sys.stdout)
    file_handler = logging.FileHandler('program.log')
    formatter = logging.Formatter(
        '%(asctime)s, %(levelname)s, %(message)s, %(name)s')
    stdout_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[stdout_handler, file_handler]
    )
    main()
