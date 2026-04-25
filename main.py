import os
import re
import json
import time
import sys
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urljoin, urldefrag
from urllib.request import Request, urlopen
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
_registered_drivers = set()
_registered_drivers_lock = threading.Lock()
MAX_MACHINE_RETRY = 3


def strip_json_comments(text):
    result = []
    in_string = False
    string_quote = ''
    escaped = False
    i = 0

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ''

        if in_string:
            result.append(ch)
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == string_quote:
                in_string = False
            i += 1
            continue

        if ch in ('"', "'"):
            in_string = True
            string_quote = ch
            result.append(ch)
            i += 1
            continue

        if ch == '/' and nxt == '/':
            i += 2
            while i < len(text) and text[i] not in ('\n', '\r'):
                i += 1
            continue

        if ch == '/' and nxt == '*':
            i += 2
            while i + 1 < len(text) and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2
            continue

        result.append(ch)
        i += 1

    return ''.join(result)


def strip_trailing_commas(text):
    result = []
    in_string = False
    string_quote = ''
    escaped = False
    i = 0

    while i < len(text):
        ch = text[i]

        if in_string:
            result.append(ch)
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == string_quote:
                in_string = False
            i += 1
            continue

        if ch in ('"', "'"):
            in_string = True
            string_quote = ch
            result.append(ch)
            i += 1
            continue

        if ch == ',':
            j = i + 1
            while j < len(text) and text[j] in (' ', '\t', '\n', '\r'):
                j += 1
            if j < len(text) and text[j] in (']', '}'):
                i += 1
                continue

        result.append(ch)
        i += 1

    return ''.join(result)


def load_config():
    with open(CONFIG_PATH, encoding='utf-8-sig') as f:
        raw = f.read()

    sanitized = strip_trailing_commas(strip_json_comments(raw))
    config = json.loads(sanitized)

    if 'save_dir' not in config:
        raise ValueError("config.json must contain 'save_dir'.")

    has_targets_path = 'targets_path' in config
    has_discovery = isinstance(config.get('discovery'), dict)
    if not has_targets_path and not has_discovery:
        raise ValueError("config.json must contain either 'targets_path' or 'discovery'.")

    return config


def resolve_path(path_value):
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else (BASE_DIR / path).resolve()


def load_targets_from_json(filepath):
    with open(filepath, encoding='utf-8-sig') as f:
        data = json.load(f)

    if isinstance(data, list):
        urls = [str(x).strip() for x in data if str(x).strip()]
    elif isinstance(data, dict) and isinstance(data.get('urls'), list):
        urls = [str(x).strip() for x in data['urls'] if str(x).strip()]
    else:
        raise ValueError("targets JSON must be a list or an object like {'urls': [...]}.")

    if not urls:
        raise ValueError("No URLs found in targets JSON.")

    return urls


def extract_links(html, base_url):
    links = []
    for href in re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE):
        href = unescape(href.strip())
        if not href or href.startswith('#'):
            continue
        if href.startswith('javascript:') or href.startswith('mailto:'):
            continue
        url = urljoin(base_url, href)
        url = urldefrag(url)[0]
        if url.startswith('http://') or url.startswith('https://'):
            links.append(url)
    return links


def fetch_html(url, timeout=15):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or 'utf-8'
        return response.read().decode(charset, errors='ignore')


def _query_value_set(values):
    return {str(v).strip() for v in values if str(v).strip()}


def is_target_data_url(url, allowed_t_values, allowed_m_values):
    if not allowed_t_values and not allowed_m_values:
        return True

    params = parse_qs(urlparse(url).query)
    t_value = params.get('t', [''])[0]
    m_value = params.get('m', [''])[0]

    if allowed_t_values and t_value not in allowed_t_values:
        return False
    if allowed_m_values and m_value not in allowed_m_values:
        return False
    return True


def discover_machine_urls(discovery):
    if discovery.get('strategy') == 'news_to_data_to_machine':
        return discover_machine_urls_from_news(discovery)

    start_urls = [str(u).strip() for u in discovery.get('start_urls', []) if str(u).strip()]
    if not start_urls:
        raise ValueError("discovery.start_urls must contain at least one URL.")

    include_pattern = discovery.get('include_pattern', r'/machine\.php\?')
    max_depth = int(discovery.get('max_depth', 2))
    max_pages = int(discovery.get('max_pages', 500))
    same_host_only = bool(discovery.get('same_host_only', True))

    pattern = re.compile(include_pattern)
    queue = deque()
    for start_url in start_urls:
        host = urlparse(start_url).netloc
        queue.append((start_url, 0, host))

    visited = set()
    machine_urls = set()

    while queue and len(visited) < max_pages:
        current_url, depth, seed_host = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)

        if pattern.search(current_url):
            machine_urls.add(current_url)

        if depth >= max_depth:
            continue

        try:
            html = fetch_html(current_url)
            links = extract_links(html, current_url)
        except Exception:
            continue

        for link in links:
            parsed = urlparse(link)
            if same_host_only and parsed.netloc != seed_host:
                continue
            if link not in visited:
                queue.append((link, depth + 1, seed_host))

    urls = sorted(machine_urls)
    if not urls:
        raise ValueError("No machine URLs discovered. Check discovery settings.")
    return urls


def discover_machine_urls_from_news(discovery):
    news_urls = [str(u).strip() for u in discovery.get('news_urls', []) if str(u).strip()]
    if not news_urls:
        raise ValueError("discovery.news_urls must contain at least one news.php URL.")

    data_pattern = re.compile(discovery.get('data_include_pattern', r'/data\.php\?'))
    machine_pattern = re.compile(discovery.get('machine_include_pattern', r'/machine\.php\?'))
    same_host_only = bool(discovery.get('same_host_only', True))
    max_data_pages = int(discovery.get('max_data_pages', 500))
    show_data_url_every = int(discovery.get('show_data_url_every', 10))
    allowed_t_values = _query_value_set(discovery.get('allowed_t_values', []))
    allowed_m_values = _query_value_set(discovery.get('allowed_m_values', []))

    data_urls = set()
    print(f"[Discovery] Start: news pages={len(news_urls)}", flush=True)
    if allowed_t_values:
        print(f"[Discovery] Filter: t in {sorted(allowed_t_values)}", flush=True)
    if allowed_m_values:
        print(f"[Discovery] Filter: m in {sorted(allowed_m_values)}", flush=True)

    for news_index, news_url in enumerate(news_urls, start=1):
        print(f"[Discovery] ({news_index}/{len(news_urls)}) Fetch news: {news_url}", flush=True)
        seed_host = urlparse(news_url).netloc
        try:
            html = fetch_html(news_url)
            links = extract_links(html, news_url)
        except Exception:
            print(f"[Discovery] Skip news (fetch failed): {news_url}", flush=True)
            continue

        before = len(data_urls)
        for link in links:
            parsed = urlparse(link)
            if same_host_only and parsed.netloc != seed_host:
                continue
            if data_pattern.search(link) and is_target_data_url(link, allowed_t_values, allowed_m_values):
                data_urls.add(link)
        print(f"[Discovery] data.php found in this page: +{len(data_urls) - before} (total {len(data_urls)})", flush=True)

    if not data_urls:
        raise ValueError("No data.php URLs discovered from news pages.")

    machine_urls = set()
    data_list = list(sorted(data_urls))[:max_data_pages]
    print(f"[Discovery] data pages to scan: {len(data_list)}", flush=True)
    for index, data_url in enumerate(data_list, start=1):
        if index == 1 or index % show_data_url_every == 0 or index == len(data_list):
            print(f"[Discovery] ({index}/{len(data_list)}) Scan data page: {data_url}", flush=True)
        data_host = urlparse(data_url).netloc
        try:
            html = fetch_html(data_url)
            links = extract_links(html, data_url)
        except Exception:
            continue

        for link in links:
            parsed = urlparse(link)
            if same_host_only and parsed.netloc != data_host:
                continue
            if machine_pattern.search(link):
                machine_urls.add(link)

    urls = sorted(machine_urls)
    print(f"[Discovery] Completed: machine targets={len(urls)}", flush=True)
    if not urls:
        raise ValueError("No machine.php URLs discovered from data.php pages.")
    return urls


def save_targets_json(filepath, urls):
    payload = {'urls': urls}
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def cleanup_drivers():
    with _registered_drivers_lock:
        drivers = list(_registered_drivers)
        _registered_drivers.clear()

    for driver in drivers:
        try:
            driver.quit()
        except Exception:
            pass

    if drivers:
        print(f"[Main] Closed Chrome drivers: {len(drivers)}", flush=True)


def reset_thread_driver():
    driver = getattr(_driver_pool, "driver", None)
    if not driver:
        return

    with _registered_drivers_lock:
        _registered_drivers.discard(driver)

    try:
        driver.quit()
    except Exception:
        pass

    try:
        delattr(_driver_pool, "driver")
    except Exception:
        pass

_driver_pool = threading.local()

def get_driver():
    if not hasattr(_driver_pool, "driver"):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--log-level=3")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--remote-debugging-pipe")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--user-agent=Mozilla/5.0")
        _driver_pool.driver = webdriver.Chrome(options=options)
        _driver_pool.driver.set_page_load_timeout(8)
        with _registered_drivers_lock:
            _registered_drivers.add(_driver_pool.driver)
        _driver_pool.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return _driver_pool.driver

class PachinkoScraper:
    @staticmethod
    def scrape(url):
        driver = get_driver()
        try:
            driver.get(url)
        except Exception:
            return None

        for _ in range(30):
            try:
                if driver.execute_script("return document.readyState") == "complete":
                    break
            except Exception:
                return None
            time.sleep(0.2)

        time.sleep(0.3)
        return PachinkoScraper.extract_data(driver)

    @staticmethod
    def extract_data(driver):
        try:
            root = driver.find_element(By.CSS_SELECTOR, ".panel")
            name = root.find_element(By.CSS_SELECTOR, "div.machineName h2").text.strip()
            match = re.match(r'(\d+)\s*番台(.*)', name)
            number, title = match.groups() if match else (None, name)
            table = root.find_element(By.CSS_SELECTOR, "section#dataSection table")
            today = PachinkoScraper.parse_table(table)
            today['dBB'] = PachinkoScraper.extract_bb_from_dom(root)
            return {'machineNumber': number, 'machineName': title, 'today': today,
                    'lastTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'type': 'S'}
        except Exception:
            return None

    @staticmethod
    def extract_bb_from_dom(root):
        text = root.text
        match = re.search(r'BB[\s:：]*(\d+)', text)
        return int(match.group(1)) if match else 0

    @staticmethod
    def parse_table(table):
        labels = {'dBB': 'BB', 'dRB': 'RB', 'dART': 'AT・ART',
                  'dTotalStart': '累計スタート', 'dNowStart': 'スタート', 'dMY': '最大持玉'}
        data = {}
        for key, label in labels.items():
            try:
                td = table.find_element(By.XPATH, f".//td[normalize-space()='{label}']/following-sibling::td")
                data[key] = int(td.text.replace(',', '').strip())
            except Exception:
                data[key] = 0
        return data

    @staticmethod
    def extract_bb_data(data):
        t = data.get('today', {})
        total = t.get('dTotalStart', 0)
        return {
            'n': data.get('machineNumber'), 'name': data.get('machineName'),
            'last_update': data.get('lastTime'), 'machine_type': data.get('type'),
            'today': {
                'bb': t.get('dBB', 0), 'rb': t.get('dRB', 0), 'art': t.get('dART', 0),
                'tG': total, 'cG': t.get('dNowStart', 0), 'max': t.get('dMY', 0),
                'bbp': PachinkoScraper.prob(total, t.get('dBB', 0)),
                'rbp': PachinkoScraper.prob(total, t.get('dRB', 0)),
                'artp': PachinkoScraper.prob(total, t.get('dART', 0)),
                'brp': PachinkoScraper.prob(total, sum([t.get(k, 0) for k in ['dBB','dRB','dART']]))
            }
        }

    @staticmethod
    def prob(total, count):
        return f"1/{round(total / count)}" if count and total else "-"

def fetch_url(url):
    m, n = extract_m_n_from_url(url)
    for attempt in range(1, MAX_MACHINE_RETRY + 1):
        print(f"[Thread] Getting: m={m}, n={n} (try {attempt}/{MAX_MACHINE_RETRY})")
        raw = PachinkoScraper.scrape(url)
        if raw:
            data = PachinkoScraper.extract_bb_data(raw)
            machine_name = (data.get('name') or '').strip()
            machine_number = str(data.get('n') or '').strip()
            if machine_name and machine_number not in ('', '0', '0000'):
                return data

        if attempt < MAX_MACHINE_RETRY:
            print(f"[Thread] Retry invalid machine page: m={m}, n={n}", flush=True)
            reset_thread_driver()
            time.sleep(0.4 * attempt)

    print(f"[Thread] Skip invalid machine page after retries: m={m}, n={n}", flush=True)
    return None

def extract_m_n_from_url(url):
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return params.get('m', [None])[0], params.get('n', [None])[0]

def fetch_all_parallel(urls, max_workers=4):
    results = []
    total = len(urls)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_url, url): url for url in urls}
        for index, future in enumerate(as_completed(futures), start=1):
            try:
                result = future.result()
                if result:
                    results.append(result)
                    today = result.get('today', {})
                    print(
                        f"[{index}/{total}] {result.get('n', '-') }番台 {result.get('name', '-') } | "
                        f"tG={today.get('tG', 0)} bb={today.get('bb', 0)} rb={today.get('rb', 0)} "
                        f"bbp={today.get('bbp', '-')} rbp={today.get('rbp', '-')} artp={today.get('artp', '-')}",
                        flush=True,
                    )
            except Exception as e:
                print(f"Error: {e}")
    return results


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)

    config = load_config()
    save_dir = resolve_path(config['save_dir'])
    max_workers = int(config.get('max_workers', 4))

    os.makedirs(save_dir, exist_ok=True)

    start = time.perf_counter()
    print("[Main] Start run", flush=True)
    if isinstance(config.get('discovery'), dict):
        print("[Main] Mode: discovery", flush=True)
        discovery = config['discovery']
        cache_path_value = discovery.get('cache_targets_path')
        use_cached_targets = bool(discovery.get('use_cached_targets_if_exists', True))
        cache_path = resolve_path(cache_path_value) if cache_path_value else None

        if use_cached_targets and cache_path and cache_path.exists():
            targets = load_targets_from_json(cache_path)
            print(f"[Main] Use cached targets: {cache_path} ({len(targets)})", flush=True)
        else:
            targets = discover_machine_urls(discovery)
            if cache_path:
                save_targets_json(cache_path, targets)
                print(f"Discovered {len(targets)} targets and saved: {cache_path}")
            else:
                print(f"Discovered {len(targets)} targets")
    else:
        print("[Main] Mode: static targets_path", flush=True)
        targets_path = resolve_path(config['targets_path'])
        if targets_path.suffix.lower() != '.json':
            raise ValueError("targets_path must point to a .json file")
        targets = load_targets_from_json(targets_path)

    print(f"[Main] Scraping start: targets={len(targets)} workers={max_workers}", flush=True)
    all_data = fetch_all_parallel(targets, max_workers=max_workers)
    cleanup_drivers()
    print(f"\n=== Complete in {time.perf_counter() - start:.2f} sec ===")

    if not all_data:
        print("[Main] No data to save.", flush=True)
        return

    rows = []
    for data in all_data:
        today = data['today']
        rows.append({
            'n': data['n'], 'name': data['name'],
            'tG': today['tG'], 'cG': today['cG'],
            'tG>4000': 'YES' if today['tG'] >= 4000 else 'NO',
            'tG!=0&cG<100': 'YES' if today['tG'] and today['cG'] < 100 else 'NO',
            'cG>400': 'YES' if today['cG'] >= 400 else 'NO',
            'bb': today['bb'], 'bbp': today['bbp'],
            'rb': today['rb'], 'rbp': today['rbp'],
            'art': today['art'], 'artp': today['artp'],
            'brp': today['brp'], 'max': today['max'],
        })

    df = pd.DataFrame(rows)
    fname = save_dir / f"pachinko_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(fname, index=False, encoding='utf-8-sig')
    print(f"Saved CSV: {fname}")

if __name__ == "__main__":
    main()
