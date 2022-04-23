import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

from exception import GetApiAnswerException, BotMessageException
from http import HTTPStatus

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='program.log',
    level=logging.ERROR
)

logger = logging.getLogger(__name__)
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

VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        text = message
        bot.send_message(TELEGRAM_CHAT_ID, text)
    except Exception:
        raise BotMessageException('сбой при отправке сообщений')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    logger.info('get_api_answer начал делать запрос к API')
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as err:
        raise ConnectionError('ошибка при запросе к API') from err
    if response.status_code != HTTPStatus.OK:
        raise GetApiAnswerException('ответ API не соответствует ожидаемому')
    return response.json()


def check_response(response):
    """Проверка ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('ответ от API не являеться словарем')
    homeworks = response.get("homeworks")
    if not homeworks:
        raise KeyError('нет ключа "homeworks"')
    if "current_date" not in response:
        raise KeyError('нет ключа "current_date"')
    if not isinstance(homeworks, list):
        raise TypeError('"homeworks" не являеться списком')
    return homeworks


def parse_status(homework):
    """Информация о конкретной домашней работе, статус этой работы."""
    homework_name = homework.get("homework_name")
    if not homework_name:
        raise KeyError('нет ключа "homework_name"')
    homework_status = homework.get("status")
    if homework_status not in VERDICTS:
        raise KeyError('нет такого статуса')
    verdict = VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности  переменных окружения."""
    flag = all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])
    return flag


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'отсутствуют переменные окружения'
        logger.critical(message)
        sys.exit(message)
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    except Exception as error:
        logger.error(f'bot не запустился ошибка:{error}')
    prev_report = {'messege': None}
    while True:
        try:
            current_timestamp = int(time.time()) - ONE_MONTH
            '''
            ONE_MONTH - это количество одного месяца в секундах
            без него API возвращает пустой список
            '''
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            current_report = {'messege': parse_status(homeworks[0])}
            if current_report != prev_report:
                send_message(bot, current_report['messege'])
            else:
                logger.debug('в ответе нет новых статусов')
            prev_report = current_report.copy()
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    main()
