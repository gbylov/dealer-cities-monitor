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
    # ── Латиница (по алфавиту) ────────────────────────────────────────────────
    {'name': 'AVATR',           'url': 'https://changanauto.ru/about-us/become-a-dealer', 'method': 'changan_json', 'subbrand': 'avatr'},
    {'name': 'BELGEE',          'url': 'https://belgee.ru/become-dealer',                  'method': 'ul_li'},
    {'name': 'CHANGAN',         'url': 'https://changanauto.ru/about-us/become-a-dealer', 'method': 'changan_json', 'subbrand': 'changan'},
    {'name': 'CHANGAN UNI',     'url': 'https://changanauto.ru/about-us/become-a-dealer', 'method': 'changan_json', 'subbrand': 'uni'},
    {'name': 'DEEPAL',          'url': 'https://changanauto.ru/about-us/become-a-dealer', 'method': 'changan_json', 'subbrand': 'deepal'},
    {'name': 'EVOLUTE',         'url': 'https://evolute.ru/become-dealer',                 'method': 'ul_li'},
    {'name': 'EXEED',           'url': 'https://exeed.ru/dealers/become-dealer/',          'method': 'ul_li'},
    {'name': 'GAC',             'url': 'https://gac.ru/become-a-dealer?footer',            'method': 'gac_li'},
    {'name': 'GEELY',           'url': 'https://www.geely-motors.com/geelyinrussia/become-a-dealer', 'method': 'ul_li'},
    {'name': 'HAVAL',           'url': 'https://haval.ru/become_dealer/actual-dealer/',    'method': 'regex', 'pattern': r'(?:Список городов[^:]*:|в городах?:?|открытие дилеров[^:]*:)\s*(.*?)(?:\.|Для подачи|$)'},
    {'name': 'HONGQI',          'url': 'https://hongqi.ru/kak-stat-dilerom',              'method': 'hongqi_table'},
    {'name': 'JAC',             'url': 'https://jaccar.ru/world-jac/become-a-dealer/',    'method': 'jac_strong'},
    {'name': 'JETOUR / SOUEAST','url': 'https://jetour-ru.com/explore/dealer-join',       'method': 'ul_li'},
    {'name': 'KGM',             'url': 'https://kgm.ru/become-dealer',                    'method': 'ul_li'},
    {'name': 'KNEWSTAR',        'url': 'https://knewstar.ru/become-dealer',               'method': 'ul_li'},
    {'name': 'LADA',            'url': 'https://www.lada.ru/dealers/contest',             'method': 'ul_li'},
    {'name': 'OMODA / JAECOO', 'url': 'https://omoda.ru/omoda-dealers/become-a-dealer/', 'method': 'omoda_li'},
    {'name': 'SOLARIS',         'url': 'https://solaris.auto/become-dealer',              'method': 'ul_li'},
    {'name': 'SOLLERS',         'url': 'https://sollers-cargo.ru/dealer/',                'method': 'sollers_li'},
    {'name': 'TANK',            'url': 'https://tank.ru/become-dealer',                   'method': 'regex', 'pattern': r'(?:Список городов[^:]*:|в городах?:?|открытие дилеров[^:]*:)\s*(.*?)(?:\.|Для подачи|$)'},
    {'name': 'TENET',           'url': 'https://tenet.ru/dealers/become-a-dealer/',       'method': 'ul_li'},
    {'name': 'VOLGA',           'url': 'https://volga.auto/',                             'method': 'volga_tilda'},
    {'name': 'VOYAH',           'url': 'https://voyah.su/become-dealer',                  'method': 'ul_li'},
    # ── Кириллица (по алфавиту) ───────────────────────────────────────────────
    {'name': 'ГАЗ',             'url': 'https://stt.ru/become-partners',                  'method': 'gaz_playwright'},
    {'name': 'МОСКВИЧ',         'url': 'https://moskvich.ru/become-a-dealer',             'method': 'moskvich_li'},
    {'name': 'УАЗ',             'url': 'https://www.uaz.ru/company/become-dealer',        'method': 'p_colon'},
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


def get_gac_dealer_cities(soup):
    """
    gac.ru/become-a-dealer — города спрятаны в аккордеоне td-accordion.
    Кнопка аккордеона: <button>Список городов...</button>
    Тело аккордеона: <div class="td-accordion__body"> с тремя колонками ul/li.
    """
    keyword = 'список городов'
    # Ищем кнопку аккордеона с нужным текстом
    for tag in soup.find_all(['button', 'h2', 'h3', 'h4', 'p', 'strong']):
        if keyword in tag.get_text(' ', strip=True).lower():
            cities = []
            seen = set()
            # Для аккордеона — тело идёт как следующий sibling div
            parent = tag.parent  # div.td-accordion
            body = parent.find('div', class_='td-accordion__body') if parent else None
            if not body:
                # Fallback: ищем все ul после тега
                body = tag.find_next('div')
            if body:
                for ul in body.find_all('ul'):
                    for li in ul.find_all('li'):
                        city = clean_city(li.get_text())
                        if is_valid_city(city) and city not in seen:
                            seen.add(city)
                            cities.append(city)
            if cities:
                return cities
    return []


def get_hongqi_cities(soup):
    """
    hongqi.ru/kak-stat-dilerom — таблица рендерится JS, с сервера не приходит.
    Используем жёстко прописанный список (27 городов).
    Обновлять вручную при изменениях.
    """
    # Пробуем парсить на случай если страница вдруг отдаст таблицу
    for table in soup.find_all('table'):
        cities = []
        seen = set()
        for td in table.find_all('td'):
            city = clean_city(td.get_text())
            if is_valid_city(city) and city not in seen:
                seen.add(city)
                cities.append(city)
        if len(cities) >= 5:
            return cities
    # Fallback — последний известный список
    return [
        'Астрахань', 'Киров', 'Уфа', 'Волгоград',
        'Минеральные Воды', 'Абакан', 'Ставрополь', 'Ижевск',
        'Оренбург', 'Чебоксары', 'Сыктывкар', 'Липецк',
        'Ульяновск', 'Тольятти', 'Барнаул', 'Омск',
        'Пенза', 'Нижнекамск', 'Саранск', 'Тверь',
        'Магнитогорск', 'Саратов', 'Стерлитамак', 'Аксай',
        'Курск', 'Смоленск', 'Сызрань',
    ]



def get_jac_cities(soup):
    """
    jaccar.ru — города в <p><strong> внутри div.cg-1.mt-orange (два слайда).
    Сайт рендерится JS — fallback с жёстким списком.
    """
    cities = []
    seen = set()
    for block in soup.find_all('div', class_=lambda c: c and 'mt-orange' in c and 'text-content' in c):
        for strong in block.find_all('strong'):
            city = clean_city(strong.get_text())
            if is_valid_city(city) and city not in seen:
                seen.add(city)
                cities.append(city)
    if cities:
        return cities
    return [
        'Москва', 'Санкт-Петербург', 'Архангельск', 'Барнаул', 'Брянск',
        'Вологда', 'Кемерово', 'Краснодар', 'Курск', 'Липецк',
        'Нижний Тагил', 'Омск', 'Орел', 'Оренбург', 'Пенза',
        'Пермь', 'Саратов', 'Сочи', 'Ставрополь', 'Стерлитамак',
        'Тамбов', 'Томск', 'Тула', 'Ульяновск', 'Челябинск',
        'Череповец', 'Энгельс',
    ]



def get_sollers_cities(soup):
    """
    sollers-cargo.ru/dealer/ — первая карточка c-cards__item (Продажи+сервис).
    Сайт рендерится JS — fallback с жёстким списком.
    """
    first_card = soup.find('div', class_='c-cards__item')
    if first_card:
        cities = []
        seen = set()
        for li in first_card.find_all('li'):
            city = clean_city(li.get_text())
            if is_valid_city(city) and city not in seen:
                seen.add(city)
                cities.append(city)
        if cities:
            return cities
    return [
        'Архангельск', 'Астрахань', 'Брянск', 'Владикавказ', 'Волгоград',
        'Воронеж', 'Грозный', 'Донецкая Народная Республика', 'Запорожская область',
        'Киров', 'Комсомольск-на-Амуре', 'Курган', 'Курск',
        'Луганская Народная Республика', 'Магнитогорск', 'Махачкала',
        'Минеральные воды', 'Москва', 'Нижневартовск', 'Орел', 'Пенза',
        'Петрозаводск', 'Самара', 'Севастополь', 'Смоленск', 'Тамбов',
        'Ульяновск', 'Херсонская область', 'Челябинск', 'Ярославль',
    ]



def get_moskvich_cities(soup):
    """
    moskvich.ru/become-a-dealer — города в ul/li внутри div.dealer_tender_block2
    """
    block = soup.find('div', class_='dealer_tender_block2')
    if block:
        cities = []
        seen = set()
        for li in block.find_all('li'):
            city = clean_city(li.get_text())
            if is_valid_city(city) and city not in seen:
                seen.add(city)
                cities.append(city)
        if cities:
            return cities
    return []


def get_gaz_cities(url):
    """
    stt.ru/become-partners — дистрибьютор ГАЗ.
    Вкладки Сервис/Дилерский центр разделяются JS.
    С сервера приходит только один список (Сервис, 61 город).
    Используем жёстко прописанный список Дилерский центр (7 городов).
    Обновлять вручную при изменениях на сайте.
    """
    return ['Астрахань', 'Душанбе', 'Курган', 'Миасс',
            'Новый Уренгой', 'Нижневартовск', 'Сочи']



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
    changanauto.ru — Vue CSR (клиентский рендеринг).
    Таблицы появляются только после выполнения JS.
    Используем Playwright чтобы дождаться таблиц, потом парсим HTML.
    Порядок таблиц: changan=0, uni=1, avatr=2, deepal=3.
    Fallback: жёстко прописанные города из последнего известного состояния.
    """
    FALLBACK = {
        'changan': ['Березники', 'Владивосток', 'Волгоград', 'Кемерово',
                    'Майкоп', 'Нефтекамск', 'Обнинск', 'Псков', 'Хабаровск'],
        'uni':     ['Березники', 'Владивосток', 'Волгоград', 'Кемерово',
                    'Майкоп', 'Нефтекамск', 'Обнинск', 'Псков'],
        'avatr':   ['Владимир', 'Грозный', 'Иркутск', 'Кемерово', 'Красноярск',
                    'Минеральные Воды', 'Новороссийск', 'Омск', 'Ростов-на-Дону',
                    'Рязань', 'Самара', 'Саратов', 'Сочи', 'Тула', 'Ярославль'],
        'deepal':  ['Абакан', 'Белгород', 'Владимир', 'Иркутск', 'Калуга',
                    'Красноярск', 'Курск', 'Липецк', 'Мурманск', 'Орёл',
                    'Петрозаводск', 'Самара', 'Саратов', 'Сургут', 'Ярославль'],
    }
    subbrand = (brand or {}).get('subbrand')

    # Кеш Playwright-рендеренного HTML чтобы не грузить страницу 4 раза
    _CHANGAN_RENDERED = getattr(get_changan_cities, '_rendered_html', None)
    if _CHANGAN_RENDERED is None:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto('https://changanauto.ru/about-us/become-a-dealer',
                          wait_until='networkidle', timeout=30000)
                page.wait_for_selector('table', timeout=15000)
                _CHANGAN_RENDERED = page.content()
                browser.close()
            get_changan_cities._rendered_html = _CHANGAN_RENDERED
        except ImportError:
            print('  CHANGAN: Playwright не установлен, используем fallback')
            return FALLBACK.get(subbrand, [])
        except Exception as e:
            print(f'  CHANGAN: Playwright ошибка: {e}, используем fallback')
            get_changan_cities._rendered_html = ''
            return FALLBACK.get(subbrand, [])
    if _CHANGAN_RENDERED:
        result = get_changan_cities_from_table(_CHANGAN_RENDERED, subbrand)
        if result:
            return result
    return FALLBACK.get(subbrand, [])


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

    if method == 'hongqi_table':
        cities = get_hongqi_cities(soup)
    elif method == 'moskvich_li':
        cities = get_moskvich_cities(soup)
    elif method == 'gac_li':
        cities = get_gac_dealer_cities(soup)
    elif method == 'omoda_li':
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

    for brand_name, cities in results.items():
        if cities:
            lines.append(f'• {brand_name}: {", ".join(cities)}')
        else:
            lines.append(f'• {brand_name}: —')

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
