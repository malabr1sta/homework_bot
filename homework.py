import logging
import os
import time
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

from exception import (check_tokens_exception, get_api_answer_exception,
                       parse_status_exception)

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='program.log',
    level=logging.ERROR
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    'my_logger.log',
    maxBytes=50000000,
    backupCount=5
)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ONE_MONTH = 2592000
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        text = message
        bot.send_message(TELEGRAM_CHAT_ID, text)
    except Exception as error:
        logger.error(f'сбой при отправке сообщения в Telegram. Ошибка:{error}')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != 200:
        raise get_api_answer_exception('нет ответа от API')
    return response.json()


def check_response(response):
    """Проверка ответ API на корректность."""
    if type(response) is not dict:
        raise TypeError('не корректный ответ API')
    homeworks = response.get("homeworks")
    if homeworks is None:
        raise KeyError('нет ключа "homeworks"')
    if type(homeworks) is not list:
        raise TypeError('"homeworks" не являеться списком')
    return homeworks
    

def parse_status(homework):
    """Информация о конкретной домашней работе, статус этой работы."""
    homework_name = homework.get("homework_name")
    if homework_name is None:
        raise KeyError('нет ключа "homework_name"')
    homework_status = homework.get("status")
    if homework_status is None:
        raise KeyError('нет ключа "homework_status"')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    if verdict is None:
        raise parse_status_exception('нет такого статуса')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности  переменных окружения."""
    sekret_programm = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    flag = True
    for token in sekret_programm:
        if token is None:
            flag = False
            break
    return flag


def get_homeworks_status(bot, current_timestamp):
    """Текущий статус работы."""
    response = get_api_answer(current_timestamp)
    homeworks = check_response(response)
    homework_status = parse_status(homeworks[0])
    return homework_status


def func_exception(bot, message):
    """Фцнкция для формирования сообщения при исключений."""
    logger.error(message)
    send_message(bot, message)
    time.sleep(RETRY_TIME)


def main():
    """Основная логика работы бота."""
    try:
        check_token = check_tokens()
        if check_token == False:
            raise check_tokens_exception
    except check_tokens_exception as error:
        logger.critical(f'отсутствуют обязательные переменные окружения ошибка:{error}')
    try:    
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    except Exception as error:
        logger.error(f'bot не запустился ошибка:{error}')   
    current_timestamp = int(time.time()) - ONE_MONTH
    while True:
        try:
            homework_status = get_homeworks_status(bot, current_timestamp)
            time.sleep(RETRY_TIME)
            current_timestamp = int(time.time()) - ONE_MONTH
            compared_homework_status = get_homeworks_status(bot, current_timestamp)
            if compared_homework_status != homework_status:
                send_message(bot, compared_homework_status)
            else:
                logger.debug('в ответе новых нет статусов')
            time.sleep(RETRY_TIME)
        except get_api_answer_exception as error:
            message = f'API не отвечает: {error}'
            func_exception(bot, message)
        except TypeError as error:
            message = f'не корректный ответ API: {error}'
            func_exception(bot, message)
        except parse_status_exception as error:
            message = f'не удалост получить статус домашней работы: {error}'
            func_exception(bot, message)
        except KeyError as error:
            message = f'не коректный ключ : {error}'
            func_exception(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            func_exception(bot, message)


if __name__ == '__main__':
    main()
