import os
import re
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"


def load_config():
    with open(CONFIG_PATH, encoding='utf-8-sig') as f:
        config = json.load(f)

    if 'save_dir' not in config or 'targets_path' not in config:
        raise ValueError("config.json must contain 'save_dir' and 'targets_path'.")

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
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--user-agent=Mozilla/5.0")
        _driver_pool.driver = webdriver.Chrome(options=options)
        _driver_pool.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return _driver_pool.driver

class PachinkoScraper:
    @staticmethod
    def scrape(url):
        driver = get_driver()
        driver.get(url)
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(1.5)
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
    print(f"[Thread] Getting: m={m}, n={n}")
    raw = PachinkoScraper.scrape(url)
    return PachinkoScraper.extract_bb_data(raw) if raw else None

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
    config = load_config()
    save_dir = resolve_path(config['save_dir'])
    targets_path = resolve_path(config['targets_path'])
    max_workers = int(config.get('max_workers', 4))

    if targets_path.suffix.lower() != '.json':
        raise ValueError("targets_path must point to a .json file")

    os.makedirs(save_dir, exist_ok=True)

    start = time.perf_counter()
    targets = load_targets_from_json(targets_path)
    all_data = fetch_all_parallel(targets, max_workers=max_workers)
    print(f"\n=== Complete in {time.perf_counter() - start:.2f} sec ===")

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
