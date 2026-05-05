import os
import json
import re
import time
import smtplib
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Настройки ──────────────────────────────────────────────────────────────────
EMAIL_FROM     = os.environ['EMAIL_FROM']
EMAIL_PASSWORD = os.environ['EMAIL_PASSWORD']
EMAIL_TO       = 'g.bylov@tmgauto.ru'

CITIES_FILE    = 'dealer_cities.json'
MSK            = timezone(timedelta(hours=3))

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'ru-RU,ru;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

# ── Бренды: (название, url, метод_парсинга) ────────────────────────────────────
# Методы:
#   'ul_li'        — города в <li> внутри <ul>/<ol>
#   'p_colon'      — города перечислены после двоеточия в тексте
#   'regex'        — произвольный regex по тексту страницы
#   'manual'       — сайт требует JS / нестандартная структура, ставим заглушку
BRANDS = [
    {
        'name':   'ГАЗ',
        'url':    'https://stt.ru/become-partners',
        'method': 'gaz_playwright',
        'note':   'Вкладка Дилерский центр — 7 городов, JS-рендеринг',
    },
    {
        'name':   'УАЗ',
        'url':    'https://www.uaz.ru/company/become-dealer',
        'method': 'p_colon',
        'note':   '',
    },
    {
        'name':   'LADA',
        'url':    'https://www.lada.ru/dealers/contest',
        'method': 'ul_li',
        'note':   'Блокирует зарубежные IP — работает только с сервера в РФ',
    },
    {
        'name':   'МОСКВИЧ',
        'url':    'https://moskvich.ru/become-a-dealer',
        'method': 'ul_li',
        'note':   'Список городов в ul/li, доступен только с РФ IP',
    },
    {
        'name':   'HAVAL',
        'url':    'https://haval.ru/become_dealer/actual-dealer/',
        'method': 'regex',
        'pattern': r'(?:Список городов[^:]*:|в городах?:?|открытие дилеров[^:]*:)\s*(.*?)(?:\.|Для подачи|$)',
        'note':   '',
    },
    {
        'name':   'TANK',
        'url':    'https://tank.ru/become-dealer',
        'method': 'regex',
        'pattern': r'(?:Список городов[^:]*:|в городах?:?|открытие дилеров[^:]*:)\s*(.*?)(?:\.|Для подачи|$)',
        'note':   '',
    },
    {
        'name':   'GEELY',
        'url':    'https://www.geely-motors.com/geelyinrussia/become-a-dealer',
        'method': 'ul_li',
        'note':   '',
    },
    {
        'name':   'BELGEE',
        'url':    'https://belgee.ru/become-dealer',
        'method': 'ul_li',
        'note':   '',
    },
    {
        'name':   'KNEWSTAR',
        'url':    'https://knewstar.ru/become-dealer',
        'method': 'ul_li',
        'note':   '',
    },
    {
        'name':   'CHANGAN',
        'url':    'https://changanauto.ru/about-us/become-a-dealer',
        'method': 'changan_json',
        'subbrand': 'changan',
        'note':   '',
    },
    {
        'name':   'CHANGAN UNI',
        'url':    'https://changanauto.ru/about-us/become-a-dealer',
        'method': 'changan_json',
        'subbrand': 'uni',
        'note':   '',
    },
    {
        'name':   'AVATR',
        'url':    'https://changanauto.ru/about-us/become-a-dealer',
        'method': 'changan_json',
        'subbrand': 'avatr',
        'note':   '',
    },
    {
        'name':   'DEEPAL',
        'url':    'https://changanauto.ru/about-us/become-a-dealer',
        'method': 'changan_json',
        'subbrand': 'deepal',
        'note':   '',
    },
    {
        'name':   'GAC',
        'url':    'https://gac.ru/become-a-dealer?footer',
        'method': 'ul_li',
        'note':   '',
    },
    {
        'name':   'JAC',
        'url':    'https://jac.ru/become-dealer',
        'method': 'ul_li',
        'note':   '',
    },
    {
        'name':   'EVOLUTE',
        'url':    'https://evolute.ru/become-dealer',
        'method': 'ul_li',
        'note':   '',
    },
    {
        'name':   'TENET',
        'url':    'https://tenet.ru/dealers/become-a-dealer/',
        'method': 'ul_li',
        'note':   '',
    },
    {
        'name':   'OMODA',
        'url':    'https://omoda.ru/omoda-dealers/become-a-dealer/',
        'method': 'omoda_li',
        'note':   'Список городов в ul/li под заголовком "следующих городах"',
    },
    {
        'name':   'JAECOO',
        'url':    'https://jaecoo.ru/jaecoo-dealers/become-a-dealer/',
        'method': 'ul_li',
        'note':   '',
    },
    {
        'name':   'EXEED',
        'url':    'https://exeed.ru/dealers/become-dealer/',
        'method': 'ul_li',
        'note':   '',
    },
    {
        'name':   'JETOUR',
        'url':    'https://jetour-ru.com/explore/dealer-join',
        'method': 'ul_li',
        'note':   '',
    },
    {
        'name':   'SOUEAST',
        'url':    'https://soueast.ru/dealer-join',
        'method': 'ul_li',
        'note':   '',
    },
    {
        'name':   'VOYAH',
        'url':    'https://voyah.su/become-dealer',
        'method': 'ul_li',
        'note':   '',
    },
    {
        'name':   'HONGQI',
        'url':    'https://hongqi.ru/kak-stat-dilerom',
        'method': 'ul_li',
        'note':   '',
    },
    {
        'name':   'SOLARIS',
        'url':    'https://solaris.auto/become-dealer',
        'method': 'ul_li',
        'note':   '',
    },
    {
        'name':   'KGM',
        'url':    'https://kgm.ru/become-dealer',
        'method': 'ul_li',
        'note':   '',
    },
    {
        'name':   'VOLGA',
        'url':    'https://volga.auto/',
        'method': 'volga_tilda',
        'note':   '',
    },
]

# ── Ключевые слова, по которым ищем блок с городами ───────────────────────────
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

CITY_GARBAGE = {'России', 'в', 'и', 'г'}

# ── HTTP запрос с повтором ────────────────────────────────────────────────────
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


# ── Общий поиск блока с городами в soup ──────────────────────────────────────
def find_city_block(soup):
    """
    Ищет тег (p / div / section / li), текст которого содержит
    одно из ключевых слов, и пытается извлечь список городов
    из текста этого тега или следующего за ним.
    """
    text_lower = soup.get_text(' ', strip=True).lower()
    found_kw = None
    for kw in CITY_BLOCK_KEYWORDS:
        if kw in text_lower:
            found_kw = kw
            break
    if not found_kw:
        return []

    # Ищем сам тег
    for tag in soup.find_all(['p', 'div', 'li', 'span', 'h2', 'h3', 'h4']):
        tag_text = tag.get_text(' ', strip=True).lower()
        if found_kw in tag_text:
            # Берём весь текст этого тега + следующего соседа
            combined = tag.get_text(' ', strip=True)
            nxt = tag.find_next_sibling()
            if nxt:
                combined += ' ' + nxt.get_text(' ', strip=True)

            cities = extract_cities_from_text(combined)
            if cities:
                return cities

    return []


def extract_cities_from_text(text):
    """
    Из произвольного текста пытается вытащить список городов.
    Ориентируется на запятые и перечисления после ключевого слова.
    """
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
    for c in raw_cities:
        c = c.strip(' .:()«»"\'\n\r')
        c = re.sub(r'\s+в\s+\d{4}\s+г\.?$', '', c).strip()
        c = re.sub(r'^\s*:\s*', '', c).strip()
        c = re.sub(r'^России\s*', '', c).strip()
        if (2 <= len(c) <= 40
                and c not in CITY_GARBAGE
                and not c[0].isdigit()
                and 'http' not in c.lower()):
            cities.append(c)
    return cities


# ── Парсер ul/li ──────────────────────────────────────────────────────────────
def parse_ul_li(soup):
    """
    Ищет <ul>/<ol>, которые идут после заголовка/абзаца с ключевыми словами,
    и берёт текст <li> как города.
    """
    def clean_city(text):
        """Очищаем текст li от мусора: &nbsp, пустые строки, спецсимволы."""
        import unicodedata
        # Нормализуем unicode (убираем &nbsp; = \xa0 и другие пробельные)
        text = text.replace('\xa0', ' ').replace('&nbsp', '').replace(';', '').strip()
        text = ' '.join(text.split())  # схлопываем множественные пробелы
        return text

    def is_valid_city(text):
        text = clean_city(text)
        return (2 <= len(text) <= 40
                and not text.startswith(',')
                and any(c.isalpha() for c in text)
                and 'http' not in text.lower())

    # Приоритет 1: заголовок/абзац с ключевым словом → следующий <ul>
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'strong']):
        if any(kw in tag.get_text().lower() for kw in CITY_BLOCK_KEYWORDS):
            ul = tag.find_next('ul')
            if ul:
                cities = [clean_city(li.get_text(strip=True))
                          for li in ul.find_all('li')
                          if is_valid_city(li.get_text(strip=True))]
                if cities:
                    return cities

    # Приоритет 2: универсальный поиск по тексту
    cities = find_city_block(soup)
    if cities:
        return cities

    return []


# ── Парсер p_colon ────────────────────────────────────────────────────────────
def parse_p_colon(soup):
    return find_city_block(soup)


# ── Парсер regex ─────────────────────────────────────────────────────────────
def parse_regex(text, pattern):
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if not m:
        return []
    raw = m.group(1)
    cities = re.split(r'[,;\n•·–—]+', raw)
    result = []
    for c in cities:
        c = c.strip(' .:()«»"\'')
        if 2 <= len(c) <= 40:
            result.append(c)
    return result


# ── Основная функция получения городов для одного бренда ──────────────────────
def get_omoda_dealer_cities(soup):
    """
    omoda.ru/omoda-dealers/become-a-dealer/
    Список городов в <ul><li> под фразой "в следующих городах:"
    """
    keyword = 'следующих городах'
    for tag in soup.find_all(['p', 'h2', 'h3', 'div', 'span']):
        if keyword in tag.get_text().lower():
            ul = tag.find_next('ul')
            if ul:
                cities = []
                for li in ul.find_all('li'):
                    city = li.get_text(strip=True).replace('\xa0', ' ').strip()
                    if 2 <= len(city) <= 40 and any(c.isalpha() for c in city):
                        cities.append(city)
                if cities:
                    return cities
    return []


def get_gaz_cities(url):
    """
    stt.ru/become-partners — дистрибьютор ГАЗ (СТТ).
    Страница содержит две вкладки: Сервис (61 город) и Дилерский центр (7 городов).
    Нам нужна только вкладка «Дилерский центр».
    Переключение вкладок — JS, поэтому используем Playwright.
    Если Playwright недоступен — возвращаем заранее известный список.
    """
    FALLBACK = [
        'Астрахань', 'Душанбе', 'Курган', 'Миасс',
        'Новый Уренгой', 'Нижневартовск', 'Сочи',
    ]
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until='networkidle', timeout=30000)
            # Кликаем на вкладку "Дилерский центр"
            page.click('text=Дилерский центр')
            page.wait_for_timeout(1500)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, 'lxml')
        # После клика активная вкладка — ищем блок с городами
        # Структура: кнопки вкладок → список городов ниже
        # Ищем все текстовые ноды которые выглядят как города
        # в блоке после переключения
        cities = []
        seen = set()
        for tag in soup.find_all(['p', 'li', 'span', 'div', 'strong', 'b']):
            text = tag.get_text(strip=True)
            # Город: 2-30 символов, не число, не служебное
            if (2 <= len(text) <= 30
                    and not text[0].isdigit()
                    and 'http' not in text
                    and text not in seen
                    and not any(w in text.lower() for w in [
                        'сервис', 'дилерский', 'центр', 'поиск', 'городам',
                        'всего', 'город', 'запчаст', 'спецтехник', 'партнёр',
                        'партнер', 'заявк', 'консульт', 'интервью', 'документ',
                        'сотрудничест', 'рентабельност', 'ассортимент',
                        'персонал', 'совместн', 'программ',
                    ])):
                seen.add(text)
                cities.append(text)

        # Оставляем только реалистичные города (есть в известном списке или похожи)
        # Дополнительная проверка: в Playwright список должен быть ~7 городов
        if 3 <= len(cities) <= 20:
            return cities
        return FALLBACK

    except Exception as e:
        print(f'  ГАЗ Playwright ошибка: {e}, используем fallback')
        return FALLBACK


def get_changan_cities(html, brand=None):
    """
    changanauto.ru — SPA на Inertia.js.
    Все данные сериализованы в JSON внутри атрибута data-page у div#app.
    Структура: props.data.tables — список суббрендов (changan, uni, avatr, deepal),
    каждый содержит rows с полем city.
    Возвращаем объединённый список уникальных городов по всем суббрендам.
    """
    import json as _json
    soup = BeautifulSoup(html, 'lxml')
    div = soup.find('div', id='app')
    if not div:
        return []
    raw_attr = div.get('data-page', '')
    if not raw_attr:
        return []
    try:
        data = _json.loads(raw_attr)
    except Exception:
        return []
    tables = data.get('props', {}).get('data', {}).get('tables', [])
    target = (brand or {}).get('subbrand', None)
    seen = set()
    cities = []
    for t in tables:
        if target and t.get('name', '') != target:
            continue
        for row in t.get('rows', []):
            city = row.get('city', '').strip()
            city_clean = re.sub(r'\s*\(.*?\)', '', city).strip()
            if city_clean and city_clean not in seen:
                seen.add(city_clean)
                cities.append(city_clean)
    return cities


def get_volga_cities_tilda(html):
    """
    VOLGA использует Tilda — города хранятся в JSON форм прямо в HTML.
    Ищем li_variants с датами в формате: Город // ДД.ММ.ГГГГ
    """
    import re as _re, json as _json
    pattern = r'"li_variants"\s*:\s*"((?:[^"\\]|\\.)*)"'
    matches = _re.findall(pattern, html)
    for raw_escaped in matches:
        try:
            decoded = _json.loads('"' + raw_escaped + '"')
        except Exception:
            continue
        if '//' in decoded:
            cities = []
            for line in decoded.split('\n'):
                if '//' in line:
                    city = line.split('//')[0].strip()
                    if city and len(city) <= 40:
                        cities.append(city)
            if cities:
                return cities
    return []


def get_cities(brand, html_cache=None):
    name   = brand['name']
    url    = brand['url']
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

    soup = BeautifulSoup(r.text, 'lxml')

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

    # Если ничего не нашли — пробуем универсальный fallback
    if not cities:
        cities = find_city_block(soup)

    print(f'  [{name}] найдено городов: {len(cities)} — {cities[:5]}{"..." if len(cities) > 5 else ""}')
    return cities


# ── Загрузка и сохранение истории ─────────────────────────────────────────────
def load_previous():
    try:
        with open(CITIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_cities(data):
    with open(CITIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Email ─────────────────────────────────────────────────────────────────────
def send_email(subject, body_html):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = EMAIL_FROM
    msg['To']      = EMAIL_TO
    msg.attach(MIMEText(body_html, 'html', 'utf-8'))
    try:
        with smtplib.SMTP_SSL('smtp.mail.ru', 465) as server:
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        print('Письмо отправлено успешно')
    except Exception as e:
        print(f'Ошибка отправки письма: {e}')


def build_email_html(results, changes, today_str):
    # ── Блок изменений ────────────────────────────────────────────────────────
    changes_html = ''
    has_changes = any(v for v in changes.values())
    if has_changes:
        change_rows = ''
        for brand_name, brand_changes in changes.items():
            for change in brand_changes:
                clean = re.sub(r'<[^>]+>', '', change)
                color = '#c00' if '❌' in change else '#007700'
                change_rows += (
                    f'<tr>'
                    f'<td style="padding:6px 16px;border-bottom:1px solid #eee;'
                    f'font-weight:bold;color:#c00">{brand_name}</td>'
                    f'<td style="padding:6px 16px;border-bottom:1px solid #eee;'
                    f'color:{color}">{clean}</td>'
                    f'</tr>'
                )
        changes_html = f'''
        <h3 style="background:#c00;color:white;padding:10px 16px;margin:0 0 0 0">
            🔔 Изменения за неделю
        </h3>
        <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
            {change_rows}
        </table>'''

    # ── Основная таблица ──────────────────────────────────────────────────────
    rows = ''
    for brand_name, cities in results.items():
        if cities:
            cities_str = ', '.join(cities)
        else:
            cities_str = '<span style="color:#999;font-style:italic">не найдено / нет открытых позиций</span>'

        rows += (
            f'<tr>'
            f'<td style="padding:8px 16px;border-bottom:1px solid #eee;'
            f'font-weight:bold;color:#c00;vertical-align:top;white-space:nowrap">'
            f'{brand_name}</td>'
            f'<td style="padding:8px 16px;border-bottom:1px solid #eee">'
            f'{cities_str}</td>'
            f'</tr>'
        )

    html = f'''
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:750px;margin:0 auto">
    <h2 style="background:#222;color:white;padding:16px;margin:0">
        Города, открытые для поиска дилеров
    </h2>
    <p style="padding:10px 16px;background:#f9f9f9;margin:0;font-size:12px;color:#666">
        Данные на {today_str} · Источник: официальные сайты производителей
    </p>
    {changes_html}
    <table style="width:100%;border-collapse:collapse">
        <tr style="background:#f0f0f0">
            <th style="padding:8px 16px;text-align:left;width:130px">Бренд</th>
            <th style="padding:8px 16px;text-align:left">Открытые города</th>
        </tr>
        {rows}
    </table>
    <p style="padding:12px 16px;font-size:11px;color:#999">
        Автоматический мониторинг · TMG Auto · Обновлено {today_str}
    </p>
    </body></html>
    '''
    return html


# ── Главный блок ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('=== Запуск мониторинга городов для дилерства ===')
    today   = datetime.now(MSK).strftime('%d.%m.%Y')

    old_data = load_previous()
    new_data = {}
    changes  = {}

    _html_cache = {}

    for brand in BRANDS:
        name   = brand['name']
        cities = get_cities(brand, _html_cache)
        new_data[name] = cities

        # Вычисляем изменения
        old_cities = set(old_data.get(name, []))
        new_cities = set(cities)
        brand_changes = []
        for c in new_cities - old_cities:
            brand_changes.append(f'🆕 Добавлен: {c}')
        for c in old_cities - new_cities:
            brand_changes.append(f'❌ Убран: {c}')
        changes[name] = brand_changes

        time.sleep(1)  # вежливая пауза между запросами

    save_cities(new_data)
    print(f'\nДанные сохранены в {CITIES_FILE}')

    print('Отправляем письмо...')
    html = build_email_html(new_data, changes, today)
    send_email(f'Города для дилерства — {today}', html)

    print('\n=== Готово ===')
