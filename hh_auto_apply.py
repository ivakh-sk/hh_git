import csv
import datetime as dt
import random
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any

import requests
from playwright.sync_api import sync_playwright, Page


# ==========================
#   SETTINGS IMPORT
# ==========================
# Репозиторий должен содержать только settings_example.py (без персональных данных).
# Локально создайте settings.py и переопределите значения при необходимости.
from settings_example import *  # noqa: F401,F403

try:
    from settings import *  # noqa: F401,F403
except ImportError:
    pass

# ==========================
#   ДАННЫЕ И УТИЛИТЫ
# ==========================

@dataclass
class VacancyRecord:
    vacancy_id: str
    title: str
    company: str
    city: str
    salary_from: Optional[int]
    salary_to: Optional[int]
    url: str
    published_at: str

    matched: bool
    applied: bool
    applied_at: Optional[str]
    needs_questionnaire: bool


def load_existing_records(csv_file: Path) -> Dict[str, VacancyRecord]:
    records: Dict[str, VacancyRecord] = {}
    if not csv_file.exists():
        return records

    with csv_file.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vacancy_id = row["vacancy_id"]
            records[vacancy_id] = VacancyRecord(
                vacancy_id=vacancy_id,
                title=row["title"],
                company=row["company"],
                city=row["city"],
                salary_from=int(row["salary_from"]) if row["salary_from"] else None,
                salary_to=int(row["salary_to"]) if row["salary_to"] else None,
                url=row["url"],
                published_at=row["published_at"],
                matched=(row["matched"].lower() == "true"),
                applied=(row["applied"].lower() == "true"),
                applied_at=row["applied_at"] or None,
                needs_questionnaire=(row["needs_questionnaire"].lower() == "true"),
            )
    return records


def save_records(csv_file: Path, records: Dict[str, VacancyRecord]) -> None:
    fieldnames = [
        "vacancy_id",
        "title",
        "company",
        "city",
        "salary_from",
        "salary_to",
        "url",
        "published_at",
        "matched",
        "applied",
        "applied_at",
        "needs_questionnaire",
    ]

    with csv_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records.values():
            row = asdict(rec)
            row["salary_from"] = row["salary_from"] or ""
            row["salary_to"] = row["salary_to"] or ""
            row["applied_at"] = row["applied_at"] or ""
            writer.writerow(row)


def normalize(s: str) -> str:
    return (
        (s or "")
        .lower()
        .replace("ё", "е")
        .replace("\u00a0", " ")
        .strip()
    )


def random_sleep(min_s: float, max_s: float) -> None:
    delay = random.uniform(min_s, max_s)
    time.sleep(delay)


def is_gov_employer(name: str) -> bool:
    n = normalize(name)
    return any(stem in n for stem in EMPLOYER_GOV_STEMS)


def has_forbidden_role_in_title(title: str) -> bool:
    t = normalize(title)
    return any(stem in t for stem in TITLE_FORBIDDEN_ROLE_STEMS)


def is_analyst_role(title: str, description: str) -> bool:
    t = normalize(title)
    d = normalize(description)

    if not any(stem in t for stem in ANALYST_STEMS):
        return False

    if not any(stem in (t + " " + d) for stem in ANALYST_DIRECTION_STEMS):
        return False

    if not any(stem in (t + " " + d) for stem in REMOTE_HYBRID_STEMS):
        return False

    return True


def is_experience_allowed(vacancy: Dict[str, Any]) -> bool:
    exp = vacancy.get("experience") or {}
    exp_id = exp.get("id")
    if not exp_id:
        return True
    return exp_id in ALLOWED_EXPERIENCE


def is_metro_kievskaya(vacancy: Dict[str, Any]) -> bool:
    address = vacancy.get("address") or {}
    stations = []

    if "metro_stations" in address:
        stations.extend(address["metro_stations"])
    if "metro" in address and address["metro"]:
        stations.append(address["metro"])

    for st in stations:
        name = normalize(st.get("station_name") or st.get("name") or "")
        if any(normalize(bad) in name for bad in FORBIDDEN_METRO_STATIONS):
            return True
    return False


def passes_salary_filter(vacancy: Dict[str, Any]) -> bool:
    salary = vacancy.get("salary")
    if not salary:
        return True

    s_from = salary.get("from")
    s_to = salary.get("to")

    if s_from is None and s_to is None:
        return True

    if s_from is not None and s_from >= SALARY_MIN_RUB:
        return True
    if s_to is not None and s_to >= SALARY_MIN_RUB:
        return True

    return False


def search_vacancies(session: requests.Session) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    base_url = "https://api.hh.ru/vacancies"

    search_text = SEARCH_TEXT

    for page in range(MAX_SEARCH_PAGES):
        if len(found) >= SEARCH_POOL_SIZE:
            break

        params = {
            "text": search_text,
            "search_field": SEARCH_FIELD,
            "per_page": PER_PAGE,
            "page": page,
            "only_with_salary": "false",
            "order_by": "publication_time",
        }

        random_sleep(REQUEST_SLEEP_MIN, REQUEST_SLEEP_MAX)
        resp = session.get(base_url, params=params, timeout=30)

        if resp.status_code != 200:
            print(f"[WARN] search page {page}: status {resp.status_code}")
            break

        data = resp.json()
        items = data.get("items", [])
        if not items:
            break

        found.extend(items)

        if page >= data.get("pages", 0) - 1:
            break

    return found[:SEARCH_POOL_SIZE]


def fetch_vacancy_details(session: requests.Session, vacancy_id: str) -> Optional[Dict[str, Any]]:
    url = f"https://api.hh.ru/vacancies/{vacancy_id}"
    random_sleep(DETAIL_SLEEP_MIN, DETAIL_SLEEP_MAX)
    resp = session.get(url, timeout=30)
    if resp.status_code != 200:
        return None
    return resp.json()


def build_vacancy_url(vacancy_id: str) -> str:
    return f"https://hh.ru/vacancy/{vacancy_id}"


def needs_questionnaire(page: Page) -> bool:
    text = normalize(page.inner_text("body"))
    return ("анкета" in text) or ("опрос" in text) or ("вопрос" in text)


def click_respond_button(page: Page) -> bool:
    try:
        btn = page.get_by_role("button", name="Откликнуться").first
        if btn.is_visible():
            btn.click()
            return True
        return False
    except Exception:
        return False


def fill_cover_letter_widget(page: Page) -> bool:
    """
    Пытаемся найти виджет с textarea name="text" и кнопкой 'Отправить',
    заполнить сопроводительное и отправить.

    Возвращает True, если, по нашему мнению, письмо удалось отправить.
    """
    if not (COVER_LETTER_TEXT or "").strip():
        return False

    try:
        textarea = page.locator('textarea[name="text"]').first
        if not textarea.is_visible():
            return False

        textarea.fill(COVER_LETTER_TEXT)
        random_sleep(CLICK_SLEEP_MIN, CLICK_SLEEP_MAX)

        send_btn = page.get_by_role("button", name="Отправить").first
        if not send_btn.is_visible():
            return False

        send_btn.click()
        random_sleep(CLICK_SLEEP_MIN, CLICK_SLEEP_MAX)
        return True
    except Exception:
        return False


def apply_to_vacancy_playwright(vacancy_url: str) -> str:
    """
    Возвращаем статус:
      - "applied": отклик отправлен
      - "questionnaire": требуется анкета/опросник
      - "already_applied": отклик уже существует
      - "failed": не получилось
    """
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            PLAYWRIGHT_PROFILE_DIR,
            headless=False,
        )
        page = context.new_page()

        page.goto(vacancy_url, wait_until="domcontentloaded")
        random_sleep(PAGE_OPEN_SLEEP_MIN, PAGE_OPEN_SLEEP_MAX)

        body_text = normalize(page.inner_text("body"))

        if "вы уже откликались" in body_text or "вы уже отправили отклик" in body_text:
            context.close()
            return "already_applied"

        if not click_respond_button(page):
            if "вы уже откликались" in body_text or "вы уже отправили отклик" in body_text:
                context.close()
                return "already_applied"
            context.close()
            return "failed"

        random_sleep(CLICK_SLEEP_MIN, CLICK_SLEEP_MAX)

        if needs_questionnaire(page):
            context.close()
            return "questionnaire"

        if fill_cover_letter_widget(page):
            context.close()
            return "applied"

        page_text = normalize(page.inner_text("body"))
        if "отклик отправлен" in page_text or "ваш отклик" in page_text:
            context.close()
            return "applied"

        context.close()
        return "failed"


def main() -> None:
    existing_records = load_existing_records(CSV_FILE)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        }
    )

    print("[1/5] Ищем вакансии через HH API...")
    raw_vacancies = search_vacancies(session)
    print(f"  Найдено вакансий: {len(raw_vacancies)}")

    matched_count = 0
    responses_sent = 0
    questionnaire_count = 0

    print("[2/5] Фильтруем вакансии...")
    suitable: List[Dict[str, Any]] = []

    for v in raw_vacancies:
        vacancy_id = str(v.get("id") or "")
        if not vacancy_id:
            continue

        if vacancy_id in existing_records:
            continue

        title = v.get("name") or ""
        employer_name = (v.get("employer") or {}).get("name") or ""
        city = (v.get("area") or {}).get("name") or ""
        published_at = v.get("published_at") or ""
        url = build_vacancy_url(vacancy_id)

        if is_gov_employer(employer_name):
            continue

        if has_forbidden_role_in_title(title):
            continue

        if not is_experience_allowed(v):
            continue

        if is_metro_kievskaya(v):
            continue

        if not passes_salary_filter(v):
            continue

        details = fetch_vacancy_details(session, vacancy_id)
        if not details:
            continue

        description = details.get("description") or ""
        if not is_analyst_role(title, description):
            continue

        salary = v.get("salary") or {}
        salary_from = salary.get("from")
        salary_to = salary.get("to")

        suitable.append(
            dict(
                vacancy_id=vacancy_id,
                title=title,
                employer_name=employer_name,
                city=city,
                salary_from=salary_from,
                salary_to=salary_to,
                url=url,
                published_at=published_at,
            )
        )

    print(f"  Подходящих вакансий после фильтров: {len(suitable)}")

    if not suitable:
        print("[DONE] Нет подходящих вакансий.")
        return

    print("[3/5] Подготовка к откликам...")
    print("  Убедитесь, что вы залогинены в hh.ru в профиле Playwright.")
    input("  Если всё готово — продолжить, нажмите Enter в консоли... ")

    print("[4/5] Начинаем отклики...")
    for item in suitable:
        if responses_sent >= MAX_RESPONSES_PER_RUN:
            print("[STOP] Достигнут лимит откликов за запуск.")
            break

        vacancy_id = item["vacancy_id"]
        title = item["title"]
        employer_name = item["employer_name"]
        city = item["city"]
        salary_from = item["salary_from"]
        salary_to = item["salary_to"]
        url = item["url"]
        published_at = item["published_at"]

        print(f"\n-> {title} / {employer_name} / {city}")
        print(f"   {url}")

        result = apply_to_vacancy_playwright(url)

        now_str = dt.datetime.now().isoformat(timespec="seconds")

        if result == "applied":
            responses_sent += 1
            matched_count += 1
            existing_records[vacancy_id] = VacancyRecord(
                vacancy_id=vacancy_id,
                title=title,
                company=employer_name,
                city=city,
                salary_from=salary_from,
                salary_to=salary_to,
                url=url,
                published_at=published_at,
                matched=True,
                applied=True,
                applied_at=now_str,
                needs_questionnaire=False,
            )
            print("  -> Отклик отправлен.")

        elif result == "questionnaire":
            questionnaire_count += 1
            matched_count += 1
            existing_records[vacancy_id] = VacancyRecord(
                vacancy_id=vacancy_id,
                title=title,
                company=employer_name,
                city=city,
                salary_from=salary_from,
                salary_to=salary_to,
                url=url,
                published_at=published_at,
                matched=True,
                applied=False,
                applied_at=None,
                needs_questionnaire=True,
            )
            print("  -> Требуется анкета/опросник. Пропускаем.")

        elif result == "already_applied":
            print("  -> По этой вакансии уже есть ваш отклик. Повтор не делаем.")
            existing_records[vacancy_id] = VacancyRecord(
                vacancy_id=vacancy_id,
                title=title,
                company=employer_name,
                city=city,
                salary_from=salary_from,
                salary_to=salary_to,
                url=url,
                published_at=published_at,
                matched=False,
                applied=False,
                applied_at=None,
                needs_questionnaire=False,
            )

        else:
            print("  -> Не удалось откликнуться.")
            existing_records[vacancy_id] = VacancyRecord(
                vacancy_id=vacancy_id,
                title=title,
                company=employer_name,
                city=city,
                salary_from=salary_from,
                salary_to=salary_to,
                url=url,
                published_at=published_at,
                matched=False,
                applied=False,
                applied_at=None,
                needs_questionnaire=False,
            )

        save_records(CSV_FILE, existing_records)

    print("\n[SUMMARY]")
    print(f"  Подходящих вакансий (matched): {matched_count}")
    print(f"  Откликов отправлено:          {responses_sent}")
    print(f"  Требуют анкету:               {questionnaire_count}")
    print(f"  Всего записей в CSV:          {len(existing_records)}")


if __name__ == "__main__":
    main()
