import os
import json
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

CITIES_FILE = 'dealer_cities.json'
MSK = timezone(timedelta(hours=3))

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'ru-RU,ru;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

BRANDS = [
    {'name': 'ГАЗ', 'url': 'https://stt.ru/become-partners', 'method': 'gaz_playwright'},
    {'name': 'УАЗ', 'url': 'https://www.uaz.ru/company/become-dealer', 'method': 'p_colon'},
    {'name': 'LADA', 'url': 'https://www.lada.ru/dealers/contest', 'method': 'ul_li'},
    {'name': 'МОСКВИЧ', 'url': 'https://moskvich.ru/become-a-dealer', 'method': 'ul_li'},
    {
        'name': 'HAVAL',
        'url': 'https://haval.ru/become_dealer/actual-dealer/',
        'method': 'regex',
        'pattern': r'(?:Список городов[^:]*:|в городах?:?|открытие дилеров[^:]*:)\s*(.*?)(?:\.|Для подачи|$)',
    },
    {
        'name': 'TANK',
        'url': 'https://tank.ru/become-dealer',
        'method': 'regex',
        'pattern': r'(?:Список городов[^:]*:|в городах?:?|открытие дилеров[^:]*:)\s*(.*?)(?:\.|Для подачи|$)',
    },
    {'name': 'GEELY', 'url': 'https://www.geely-motors.com/geelyinrussia/become-a-dealer', 'method': 'ul_li'},
    {'name': 'BELGEE', 'url': 'https://belgee.ru/become-dealer', 'method': 'ul_li'},
    {'name': 'KNEWSTAR', 'url': 'https://knewstar.ru/become-dealer', 'method': 'ul_li'},
    {'name': 'CHANGAN', 'url': 'https://changanauto.ru/about-us/become-a-dealer', 'method': 'changan_json', 'subbrand': 'changan'},
    {'name': 'CHANGAN UNI', 'url': 'https://changanauto.ru/about-us/become-a-dealer', 'method': 'changan_json', 'subbrand': 'uni'},
    {'name': 'AVATR', 'url': 'https://changanauto.ru/about-us/become-a-dealer', 'method': 'changan_json', 'subbrand': 'avatr'},
    {'name': 'DEEPAL', 'url': 'https://changanauto.ru/about-us/become-a-dealer', 'method': 'changan_json', 'subbrand': 'deepal'},
    {'name': 'GAC', 'url': 'https://gac.ru/become-a-dealer?footer', 'method': 'ul_li'},
    {'name': 'JAC', 'url': 'https://jac.ru/become-dealer', 'method': 'ul_li'},
    {'name': 'EVOLUTE', 'url': 'https://evolute.ru/become-dealer', 'method': 'ul_li'},
    {'name': 'TENET', 'url': 'https://tenet.ru/dealers/become-a-dealer/', 'method': 'ul_li'},
    {'name': 'OMODA', 'url': 'https://omoda.ru/omoda-dealers/become-a-dealer/', 'method': 'omoda_li'},
    {'name': 'JAECOO', 'url': 'https://jaecoo.ru/jaecoo-dealers/become-a-dealer/', 'method': 'ul_li'},
    {'name': 'EXEED', 'url': 'https://exeed.ru/dealers/become-dealer/', 'method': 'ul_li'},
    {'name': 'JETOUR', 'url': 'https://jetour-ru.com/explore/dealer-join', 'method': 'ul_li'},
    {'name': 'SOUEAST', 'url': 'https://soueast.ru/dealer-join', 'method': 'ul_li'},
    {'name': 'VOYAH', 'url': 'https://voyah.su/become-dealer', 'method': 'ul_li'},
    {'name': 'HONGQI', 'url': 'https://hongqi.ru/kak-stat-dilerom', 'method': 'ul_li'},
    {'name': 'SOLARIS', 'url': 'https://solaris.auto/become-dealer', 'method': 'ul_li'},
    {'name': 'KGM', 'url': 'https://kgm.ru/become-dealer', 'method': 'ul_li'},
    {'name': 'VOLGA', 'url': 'https://volga.auto/', 'method': 'volga_tilda'},
]

CITY_BLOCK_KEYWORDS = [
    'список городов', 'следующих городах', 'открытых город',
    'поиск партнера', 'поиск партнёра', 'прием заявок',
    'приём заявок', 'рассматривается открытие', 'планируется открытие',
    'приоритетные города', 'открытие дилеров', 'идет поиск партнера',
]

CITY_STOP_PHRASES = [
    'для подачи', 'для участия', 'скачать', 'заполнить',
    'отправить', 'необходимо', 'требования', 'кандидат',
    'опыт работы', 'финансовое', 'наличие', 'согласно',
    'стратегии', 'размер', 'площадь', 'расположение',
]

CITY_GARBAGE = {'России', 'в', 'и', 'г', 'ul', 'li', 'h2', '/h2', '<ul>', '</ul>', '<li>', '</li>'}


def fetch(url, retries=2, delay=3, timeout=15):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            print(f'  HTTP {r.status_code} ← {url}')
            return r
        except Exception as e:
            if attempt == retries - 1:
                print(f'  Ошибка {url}: {e}')
                raise
            print(f'  Попытка {attempt + 1} неудачна, повтор...')
            time.sleep(delay)


def clean_city(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('\xa0', ' ').replace('&nbsp;', ' ').replace('&nbsp', ' ')
    text = text.strip(' .:()«»"\'\n\r\t')
    return ' '.join(text.split())


def is_valid_city(text):
    text = clean_city(text)
    lower = text.lower()

    if not (2 <= len(text) <= 40):
        return False
    if not any(c.isalpha() for c in text):
        return False
    if text in CITY_GARBAGE or lower in CITY_GARBAGE:
        return False
    if 'http' in lower or '<' in text or '>' in text:
        return False
    if text[0].isdigit():
        return False

    bad_words = [
        'форма', 'заявка', 'дилер', 'сервис', 'партнер',
        'партнёр', 'скачать', 'отправить', 'требования',
        'заполнить', 'подать', 'контакт', 'телефон',
    ]
    return not any(w in lower for w in bad_words)


def find_city_block(soup):
    text_lower = soup.get_text(' ', strip=True).lower()
    found_kw = next((kw for kw in CITY_BLOCK_KEYWORDS if kw in text_lower), None)

    if not found_kw:
        return []

    for tag in soup.find_all(['p', 'div', 'li', 'span', 'h2', 'h3', 'h4']):
        tag_text = tag.get_text(' ', strip=True).lower()

        if found_kw in tag_text:
            combined = tag.get_text(' ', strip=True)
            nxt = tag.find_next_sibling()

            if nxt:
                combined += ' ' + nxt.get_text(' ', strip=True)

            cities = extract_cities_from_text(combined)

            if cities:
                return cities

    return []


def extract_cities_from_text(text):
    lower = text.lower()
    cut = -1

    for kw in CITY_BLOCK_KEYWORDS:
        idx = lower.find(kw)
        if idx != -1:
            cut = idx + len(kw)
            break

    if cut == -1:
        return []

    tail = text[cut:]

    for sp in CITY_STOP_PHRASES:
        idx = tail.lower().find(sp)
        if idx != -1:
            tail = tail[:idx]

    raw_cities = re.split(r'[,;\n•·–—]+', tail)

    cities = []
    seen = set()

    for c in raw_cities:
        c = clean_city(c)
        c = re.sub(r'\s+в\s+\d{4}\s+г\.?$', '', c).strip()
        c = re.sub(r'^\s*:\s*', '', c).strip()
        c = re.sub(r'^России\s*', '', c).strip()

        if is_valid_city(c) and c not in seen:
            seen.add(c)
            cities.append(c)

    return cities


def parse_ul_li(soup):
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'strong']):
        if any(kw in tag.get_text(' ', strip=True).lower() for kw in CITY_BLOCK_KEYWORDS):
            ul = tag.find_next('ul')

            if ul:
                cities = []
                seen = set()

                for li in ul.find_all('li'):
                    city = clean_city(li.get_text(' ', strip=True))

                    if is_valid_city(city) and city not in seen:
                        seen.add(city)
                        cities.append(city)

                if cities:
                    return cities

    return find_city_block(soup)


def parse_p_colon(soup):
    return find_city_block(soup)


def parse_regex(text, pattern):
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)

    if not m:
        return []

    raw = re.sub(r'<[^>]+>', ' ', m.group(1))
    cities = re.split(r'[,;\n•·–—]+', raw)

    result = []
    seen = set()

    for c in cities:
        c = clean_city(c)

        if is_valid_city(c) and c not in seen:
            seen.add(c)
            result.append(c)

    return result


def get_omoda_dealer_cities(soup):
    keyword = 'следующих городах'

    for tag in soup.find_all(['p', 'h2', 'h3', 'div', 'span']):
        if keyword in tag.get_text(' ', strip=True).lower():
            ul = tag.find_next('ul')

            if ul:
                cities = []
                seen = set()

                for li in ul.find_all('li'):
                    city = clean_city(li.get_text(' ', strip=True))

                    if is_valid_city(city) and city not in seen:
                        seen.add(city)
                        cities.append(city)

                if cities:
                    return cities

    return []


def get_gaz_cities(url):
    fallback = [
        'Астрахань', 'Душанбе', 'Курган', 'Миасс',
        'Новый Уренгой', 'Нижневартовск', 'Сочи',
    ]

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until='networkidle', timeout=30000)
            page.click('text=Дилерский центр')
            page.wait_for_timeout(1500)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, 'html.parser')
        cities = []
        seen = set()

        for tag in soup.find_all(['p', 'li', 'span', 'div', 'strong', 'b']):
            text = clean_city(tag.get_text(' ', strip=True))

            if (
                is_valid_city(text)
                and text not in seen
                and not any(w in text.lower() for w in [
                    'сервис', 'дилерский', 'центр', 'поиск', 'городам',
                    'всего', 'город', 'запчаст', 'спецтехник', 'партнёр',
                    'партнер', 'заявк', 'консульт', 'интервью', 'документ',
                    'сотрудничест', 'рентабельност', 'ассортимент',
                    'персонал', 'совместн', 'программ',
                ])
            ):
                seen.add(text)
                cities.append(text)

        return cities if 3 <= len(cities) <= 20 else fallback

    except Exception as e:
        print(f'  ГАЗ Playwright ошибка: {e}, используем fallback')
        return fallback


def get_changan_cities_from_table(html, subbrand=None):
    """
    changanauto.ru теперь рендерит города в HTML-таблицах (Vue SSR).
    Каждая таблица соответствует суббренду (changan, uni, avatr, deepal).
    Первый <td> каждой строки — название города.
    Таблицы идут последовательно, порядок: changan, uni, avatr, deepal.
    """
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')

    # Маппинг суббренда на индекс таблицы
    subbrand_index = {'changan': 0, 'uni': 1, 'avatr': 2, 'deepal': 3}

    if subbrand and subbrand in subbrand_index:
        idx = subbrand_index[subbrand]
        target_tables = [tables[idx]] if idx < len(tables) else []
    else:
        target_tables = tables

    seen = set()
    cities = []
    for table in target_tables:
        for row in table.find_all('tr')[1:]:  # пропускаем заголовок
            tds = row.find_all('td')
            if tds:
                city = clean_city(tds[0].get_text())
                if is_valid_city(city) and city not in seen:
                    seen.add(city)
                    cities.append(city)
    return cities


def get_changan_cities(html, brand=None):
    """
    changanauto.ru — Vue SSR.
    Города рендерятся в HTML-таблицах (приоритет).
    Fallback: JSON в data-page атрибуте div#app (старый формат).
    Порядок таблиц: changan=0, uni=1, avatr=2, deepal=3.
    """
    subbrand = (brand or {}).get('subbrand')

    # ── Приоритет 1: HTML-таблицы (новый формат Vue SSR) ─────────────────────
    cities = get_changan_cities_from_table(html, subbrand)
    if cities:
        return cities

    # ── Fallback: JSON в data-page (старый формат Inertia.js) ────────────────
    soup = BeautifulSoup(html, 'html.parser')
    div = soup.find('div', id='app')
    if div:
        raw_attr = div.get('data-page', '')
        if raw_attr:
            try:
                data = json.loads(raw_attr)
                json_tables = data.get('props', {}).get('data', {}).get('tables', [])
                target = subbrand
                seen = set()
                result = []
                for t in json_tables:
                    if target and t.get('name', '') != target:
                        continue
                    for row in t.get('rows', []):
                        city = clean_city(re.sub(r'\s*\(.*?\)', '', row.get('city', '').strip()))
                        if is_valid_city(city) and city not in seen:
                            seen.add(city)
                            result.append(city)
                if result:
                    return result
            except Exception:
                pass

    return []


def get_volga_cities_tilda(html):
    pattern = r'"li_variants"\s*:\s*"((?:[^"\\]|\\.)*)"'
    matches = re.findall(pattern, html)

    for raw_escaped in matches:
        try:
            decoded = json.loads('"' + raw_escaped + '"')
        except Exception:
            continue

        if '//' in decoded:
            cities = []
            seen = set()

            for line in decoded.split('\n'):
                if '//' in line:
                    city = clean_city(line.split('//')[0].strip())

                    if is_valid_city(city) and city not in seen:
                        seen.add(city)
                        cities.append(city)

            if cities:
                return cities

    return []


def get_cities(brand, html_cache=None):
    name = brand['name']
    url = brand['url']
    method = brand['method']

    print(f'\n[{name}] {url}')

    if html_cache is not None and url in html_cache:
        r = html_cache[url]
        print(f'  [{name}] (из кеша)')
    else:
        try:
            r = fetch(url)
        except Exception as e:
            print(f'  [{name}] недоступен: {e}')
            return []

        if r.status_code != 200:
            print(f'  [{name}] HTTP {r.status_code}')
            return []

        if html_cache is not None:
            html_cache[url] = r

    soup = BeautifulSoup(r.text, 'html.parser')

    if method == 'omoda_li':
        cities = get_omoda_dealer_cities(soup)
    elif method == 'gaz_playwright':
        cities = get_gaz_cities(url)
    elif method == 'changan_json':
        cities = get_changan_cities(r.text, brand)
    elif method == 'volga_tilda':
        cities = get_volga_cities_tilda(r.text)
    elif method == 'ul_li':
        cities = parse_ul_li(soup)
    elif method == 'p_colon':
        cities = parse_p_colon(soup)
    elif method == 'regex':
        pattern = brand.get('pattern', '')
        cities = parse_regex(r.text, pattern) if pattern else find_city_block(soup)
    else:
        cities = []

    if not cities:
        cities = find_city_block(soup)

    print(f'  [{name}] найдено городов: {len(cities)} — {cities[:5]}{"..." if len(cities) > 5 else ""}')
    return cities


def load_previous():
    try:
        with open(CITIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_cities(data):
    with open(CITIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_telegram_text(results, changes, today_str):
    lines = []
    lines.append(f'📊 Города для дилерства — {today_str}')
    lines.append('')

    has_changes = any(v for v in changes.values())

    if has_changes:
        lines.append('🔔 Изменения:')
        for brand_name, brand_changes in changes.items():
            for change in brand_changes:
                lines.append(f'{brand_name}: {change}')
        lines.append('')
    else:
        lines.append('🔕 Изменений с прошлого запуска не найдено.')
        lines.append('')

    lines.append('📍 Текущая картина:')

    for brand_name, cities in results.items():
        if cities:
            preview = ', '.join(cities[:12])
            suffix = f' … ещё {len(cities) - 12}' if len(cities) > 12 else ''
            lines.append(f'• {brand_name}: {preview}{suffix}')
        else:
            lines.append(f'• {brand_name}: нет данных / не найдено')

    return '\n'.join(lines)


def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print('Telegram не отправлен: TELEGRAM_TOKEN или TELEGRAM_CHAT_ID не заданы')
        return False

    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    parts = [message[i:i + 3500] for i in range(0, len(message), 3500)]

    ok = True

    for idx, part in enumerate(parts, start=1):
        try:
            response = requests.post(
                url,
                json={
                    'chat_id': TELEGRAM_CHAT_ID,
                    'text': part,
                    'disable_web_page_preview': True,
                },
                timeout=20,
            )

            if response.status_code != 200:
                ok = False
                print(f'Telegram ошибка HTTP {response.status_code}: {response.text}')
            else:
                print(f'Telegram сообщение {idx}/{len(parts)} отправлено')

        except Exception as e:
            ok = False
            print(f'Telegram ошибка: {e}')

        time.sleep(1)

    return ok


if __name__ == '__main__':
    print('=== Запуск мониторинга городов для дилерства ===')

    today = datetime.now(MSK).strftime('%d.%m.%Y')

    old_data = load_previous()
    new_data = {}
    changes = {}
    html_cache = {}

    for brand in BRANDS:
        name = brand['name']
        cities = get_cities(brand, html_cache)

        new_data[name] = cities

        old_cities = set(old_data.get(name, []))
        new_cities = set(cities)

        brand_changes = []

        for c in sorted(new_cities - old_cities):
            brand_changes.append(f'🆕 Добавлен: {c}')

        for c in sorted(old_cities - new_cities):
            brand_changes.append(f'❌ Убран: {c}')

        changes[name] = brand_changes

        time.sleep(1)

    save_cities(new_data)
    print(f'\nДанные сохранены в {CITIES_FILE}')

    print('Отправляем в Telegram...')
    telegram_text = build_telegram_text(new_data, changes, today)
    send_telegram(telegram_text)

    print('\n=== Готово ===')
