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

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"

_registered_drivers = set()
_registered_drivers_lock = threading.Lock()
MAX_MACHINE_RETRY = 3
_driver_pool = threading.local()

# --- 1. Config & File Utils ---
def load_config():
    with open(CONFIG_PATH, encoding='utf-8-sig') as f:
        config = json.load(f)
    if 'save_dir' not in config:
        raise ValueError("config.json must contain 'save_dir'.")
    if 'targets_path' not in config and not isinstance(config.get('discovery'), dict):
        raise ValueError("config.json must contain either 'targets_path' or 'discovery'.")
    return config

def resolve_path(path_value):
    p = Path(path_value).expanduser()
    return p if p.is_absolute() else (BASE_DIR / p).resolve()

def load_targets_with_meta(filepath):
    with open(filepath, encoding='utf-8-sig') as f:
        data = json.load(f)
    urls = [str(x).strip() for x in (data if isinstance(data, list) else data.get('urls', [])) if str(x).strip()]
    if not urls: raise ValueError("No URLs found in targets JSON.")
    return urls, data.get('_meta', {}) if isinstance(data, dict) else {}

# --- 2. Discovery Core ---
def fetch_html(url, timeout=15):
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=timeout) as res:
        return res.read().decode(res.headers.get_content_charset() or 'utf-8', errors='ignore')

def extract_links(html, base_url):
    return [urldefrag(urljoin(base_url, unescape(h)))[0]
            for h in re.findall(r'href=["\']([^"\']+)["\']', html, re.I)
            if h and not h.startswith(('#', 'javascript:', 'mailto:'))]

def discover_machine_urls_from_news(discovery):
    news_urls = [str(u).strip() for u in discovery.get('news_urls', []) if str(u).strip()]
    if not news_urls: raise ValueError("discovery.news_urls is empty.")

    d_pat = re.compile(discovery.get('data_include_pattern', r'/data\.php\?'))
    m_pat = re.compile(discovery.get('machine_include_pattern', r'/machine\.php\?'))
    allow_t, allow_m = set(discovery.get('allowed_t_values', [])), set(discovery.get('allowed_m_values', []))

    print(f"[Discovery] Start: news pages={len(news_urls)}", flush=True)
    data_urls = set()
    for news_url in news_urls:
        try:
            links = extract_links(fetch_html(news_url), news_url)
            for link in links:
                if d_pat.search(link):
                    q = parse_qs(urlparse(link).query)
                    if (not allow_t or q.get('t', [''])[0] in allow_t) and (not allow_m or q.get('m', [''])[0] in allow_m):
                        data_urls.add(link)
        except Exception as e: print(f"[Discovery] Skip news {news_url}: {e}")

    if not data_urls: raise ValueError("No data.php URLs discovered.")

    data_list, machine_urls = list(sorted(data_urls))[:int(discovery.get('max_data_pages', 500))], set()
    print(f"[Discovery] Scanning {len(data_list)} data pages...", flush=True)

    def scan_page(url):
        host = urlparse(url).netloc
        try:
            return {l for l in extract_links(fetch_html(url), url) if m_pat.search(l) and urlparse(l).netloc == host}
        except Exception: return set()

    with ThreadPoolExecutor(max_workers=int(discovery.get('max_workers', 10))) as ex:
        for fut in as_completed({ex.submit(scan_page, u): u for u in data_list}):
            machine_urls.update(fut.result())

    if not machine_urls: raise ValueError("No machine URLs discovered.")
    print(f"[Discovery] Completed: targets={len(machine_urls)}", flush=True)
    return sorted(machine_urls)

# --- 3. Selenium & Scraping ---
def get_driver():
    if not hasattr(_driver_pool, "driver"):
        opts = Options()
        for arg in ["--headless", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                    "--log-level=3", "--window-size=1920,1080", "--disable-blink-features=AutomationControlled",
                    "--blink-settings=imagesEnabled=false", "--disable-application-cache"]:
            opts.add_argument(arg)
        opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        opts.add_argument("--user-agent=Mozilla/5.0")
        d = webdriver.Chrome(options=opts)
        d.set_page_load_timeout(8)
        d.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        with _registered_drivers_lock: _registered_drivers.add(d)
        _driver_pool.driver = d
    return _driver_pool.driver

def reset_thread_driver():
    d = getattr(_driver_pool, "driver", None)
    if d:
        with _registered_drivers_lock: _registered_drivers.discard(d)
        try: d.quit()
        except: pass
        delattr(_driver_pool, "driver")

def cleanup_drivers():
    for d in list(_registered_drivers):
        try: d.quit()
        except: pass
    _registered_drivers.clear()

class PachinkoScraper:
    @staticmethod
    def prob(total, count): return f"1/{round(total / count)}" if count and total else "-"

    @staticmethod
    def scrape(url):
        driver = get_driver()
        try: driver.get(url)
        except Exception: return None

        for _ in range(30):
            try:
                if driver.execute_script("return document.readyState") == "complete": break
            except Exception: return None
            time.sleep(0.2)

        for _ in range(25):
            try:
                txt = driver.find_element(By.CSS_SELECTOR, "div.machineName h2").text
                m = re.search(r'(\d+)\s*番台', txt)
                if m and m.group(1) not in ('0', '0000'): break
            except Exception: pass
            time.sleep(0.2)

        try:
            root = driver.find_element(By.CSS_SELECTOR, ".panel")
            m = re.match(r'(\d+)\s*番台(.*)', root.find_element(By.CSS_SELECTOR, "div.machineName h2").text.strip())
            num, title = m.groups() if m else (None, "")

            labels = {'dBB': 'BB', 'dRB': 'RB', 'dART': 'AT・ART', 'dTotalStart': '累計スタート', 'dNowStart': 'スタート', 'dMY': '最大持玉'}
            td_data = {}
            for k, lbl in labels.items():
                try: td_data[k] = int(root.find_element(By.XPATH, f".//td[normalize-space()='{lbl}']/following-sibling::td").text.replace(',', ''))
                except Exception: td_data[k] = 0

            bb_match = re.search(r'BB[\s:：]*(\d+)', root.text)
            td_data['dBB'] = int(bb_match.group(1)) if bb_match else 0

            total = td_data['dTotalStart']
            return {
                'n': num, 'name': title,
                'today': {
                    'bb': td_data['dBB'], 'rb': td_data['dRB'], 'art': td_data['dART'],
                    'tG': total, 'cG': td_data['dNowStart'], 'max': td_data['dMY'],
                    'bbp': PachinkoScraper.prob(total, td_data['dBB']), 'rbp': PachinkoScraper.prob(total, td_data['dRB']),
                    'artp': PachinkoScraper.prob(total, td_data['dART']), 'brp': PachinkoScraper.prob(total, sum([td_data['dBB'], td_data['dRB'], td_data['dART']]))
                }
            }
        except Exception: return None

def fetch_url(url):
    q = parse_qs(urlparse(url).query)
    m, n = q.get('m', [None])[0], q.get('n', [None])[0]
    for attempt in range(1, MAX_MACHINE_RETRY + 1):
        data = PachinkoScraper.scrape(url)
        if data and data.get('name') and data.get('n') not in (None, '', '0', '0000'): return data
        if attempt < MAX_MACHINE_RETRY:
            reset_thread_driver()
            time.sleep(0.4 * attempt)
    return None

# --- 4. Main ---
def main():
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(line_buffering=True)
    start_t = time.perf_counter()
    config = load_config()
    save_dir = resolve_path(config['save_dir'])
    os.makedirs(save_dir, exist_ok=True)

    if isinstance(config.get('discovery'), dict):
        targets = discover_machine_urls_from_news(config['discovery'])
    else:
        targets, _ = load_targets_with_meta(resolve_path(config['targets_path']))

    max_workers = int(config.get('max_workers', 4))
    print(f"[Main] Scraping start: targets={len(targets)} workers={max_workers}", flush=True)

    all_data = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for idx, fut in enumerate(as_completed({ex.submit(fetch_url, u): u for u in targets}), 1):
            res = fut.result()
            if res:
                all_data.append(res)
                t = res['today']
                print(f"[{idx:>2}/{len(targets):>2}] {res['n']:>4}番台 | G数:{t['tG']:>5} | BB:{t['bb']:>2} ({t['bbp']:>5}) | RB:{t['rb']:>2} ({t['rbp']:>5}) | 合算:{t['brp']:>5} | {res['name']}")

    cleanup_drivers()
    print(f"\n=== Complete in {time.perf_counter() - start_t:.2f} sec ===")

    if not all_data: return

    all_data.sort(key=lambda x: int(re.search(r'\d+', str(x.get('n', '0'))).group()) if re.search(r'\d+', str(x.get('n', ''))) else float('inf'))

    df = pd.DataFrame([{
        'n': d['n'],
        'machine': d['name'],
        'tG': d['today']['tG'],
        'cG': d['today']['cG'],
        'bb': d['today']['bb'],
        'bbp': d['today']['bbp'],
        'rb': d['today']['rb'],
        'rbp': d['today']['rbp'],
        'art': d['today']['art'],
        'artp': d['today']['artp'],
        'brp': d['today']['brp'],
        'max': d['today']['max'],
    } for d in all_data])

    fname = save_dir / f"pachinko_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(fname, index=False, encoding='utf-8-sig')
    print(f"Saved CSV: {fname}")

if __name__ == "__main__":
    main()
