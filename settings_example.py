from pathlib import Path

# ==========================
#   USER SETTINGS (EXAMPLE)
# ==========================
# Скопируйте этот файл в settings.py и отредактируйте под себя.
# settings.py добавьте в .gitignore (там будет персональное).

CSV_FILE = Path("hh_vacancies_log.csv")

# Максимальное количество ОТКЛИКОВ за один запуск (анти-бан)
MAX_RESPONSES_PER_RUN = 30

# Пул свежих вакансий (до скольких штук тащим из API)
SEARCH_POOL_SIZE = 500
MAX_SEARCH_PAGES = 10      # 10 * 50 = 500 максимум
PER_PAGE = 50

# Параметры случайных задержек (секунды)
REQUEST_SLEEP_MIN = 5      # между запросами к API
REQUEST_SLEEP_MAX = 25

PAGE_OPEN_SLEEP_MIN = 5    # после открытия страницы вакансии
PAGE_OPEN_SLEEP_MAX = 15

CLICK_SLEEP_MIN = 5        # после нажатий кнопок
CLICK_SLEEP_MAX = 15

# Задержка для загрузки деталей вакансии
DETAIL_SLEEP_MIN = 0.5
DETAIL_SLEEP_MAX = 1.5

# Поисковый запрос
SEARCH_TEXT = "аналитик"
SEARCH_FIELD = "name"

# Опыт, который подходит (кроме 6+)
ALLOWED_EXPERIENCE = ["noExperience", "between1And3", "between3And6"]

# Минимальная зарплата (RUB) для фильтра
SALARY_MIN_RUB = 180000

# Запрещённые станции метро (подстроки; сравнение идёт по normalize())
FORBIDDEN_METRO_STATIONS = ["киевская"]

# Директория профиля браузера Playwright (сюда сохранятся cookies hh.ru)
PLAYWRIGHT_PROFILE_DIR = "hh_profile"

# Сопроводительное письмо (в репозитории держите заглушку; реальный текст — в settings.py)
COVER_LETTER_TEXT = """Ваш текст сопроводительного письма.
(Заполните в settings.py)
""".strip()


# ==========================
#   ФИЛЬТРЫ (STEMS)
# ==========================

EMPLOYER_GOV_STEMS = [
    "государствен",
    "казенн",
    "бюджетн",
    "муниципальн",

    "министерств",
    "правительств",
    "ведомств",
    "департамент",
    "агентств",
    "комитет",
    "служб",
    "управлен",
    "госкорпорац",
    "госуслуг",

    "российск",
    "федерац",
    "федеральн",
    "региональн",
    "администрац",
    "московская область",
    "рф",

    "ано",
    "автономн",
    "гку",
    "гбу",
    "гуп",
    "мбу",
    "мку",
    "муп",
    "фку",
    "фбу",
    "фгбу",
    "фгуп",
    "гу",
    "фау",
    "фгау",
]

TITLE_FORBIDDEN_ROLE_STEMS = [
    "бухгалтер",
    "менеджер",
    "engineer",
    "инженер",
    "программист",
    "developer",
    "разработчик",
    "разраб",
    "1С",
    "1C",
]

ANALYST_STEMS = [
    "аналит",
    "analyst",
]

ANALYST_DIRECTION_STEMS = [
    "product",
    "бизнес",
    "business",
    "system",
    "системн",
    "bi",
    "ai ",
    " ai ",
    " ии",
    "ии ",
]

REMOTE_HYBRID_STEMS = [
    "удален",
    "гибрид",
    "hybrid",
    "remote",
    "частично удал",
    "офис/удален",
]
