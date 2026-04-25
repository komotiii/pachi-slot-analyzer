import json
import re
import time
import logging
import requests
import pandas as pd
from datetime import datetime
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import concurrent.futures
from urllib.parse import urlparse, parse_qs

class PachinkoDataScraper:
    def __init__(self, headless=True):
        self.driver = self.setup_driver(headless)

    def setup_driver(self, headless):
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--user-agent=Mozilla/5.0")
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

        driver = webdriver.Chrome(options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def scrape(self, url):
        self.driver.get(url)
        WebDriverWait(self.driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(1.5)
        return self.extract_data()

    def extract_data(self):
        methods = [self.extract_from_dom, self.extract_from_js, self.extract_from_network, self.extract_from_text]
        for method in methods:
            data = method()
            if data:
                return data
        return None

    def extract_from_dom(self):
        try:
            root = self.driver.find_element(By.CSS_SELECTOR, ".panel")
            name = root.find_element(By.CSS_SELECTOR, "div.machineName h2").text.strip()
            match = re.match(r'(\d+)\s*番台(.*)', name)
            number, title = match.groups() if match else (None, name)
            table = root.find_element(By.CSS_SELECTOR, "section#dataSection table")
            today = self.parse_table(table)
            today['dBB'] = self.extract_bb_from_dom(root)
            return {'machineNumber': number, 'machineName': title, 'today': today, 'lastTime': self.now(), 'type': 'S'}
        except Exception as e:
            return None

    def extract_bb_from_dom(self, root):
        try:
            text = root.text
            match = re.search(r'BB[\s:：]*(\d+)', text)
            return int(match.group(1)) if match else 0
        except:
            return 0

    def extract_from_js(self):
        vars = ['machineData', 'machineInfo', 'dataInfo']
        for var in vars:
            try:
                data = self.driver.execute_script(f"return typeof {var} !== 'undefined' ? {var} : null;")
                if data: return data
            except: continue
        return None

    def extract_from_network(self):
        try:
            logs = self.driver.get_log('performance')
            urls = [json.loads(x['message'])['message']['params']['response']['url']
                    for x in logs if 'responseReceived' in x['message']]
            for url in urls:
                if any(k in url for k in ['data', 'api', 'json']):
                    r = requests.get(url)
                    if r.ok: return r.json()
        except: pass
        return None

    def extract_from_text(self):
        try:
            text = self.driver.find_element(By.TAG_NAME, "body").text
            patterns = {
                'dBB': r'BB[\s:：]*(\d+)', 'dRB': r'RB[\s:：]*(\d+)', 'dART': r'(?:AT|ART)[\s:：]*(\d+)',
                'dTotalStart': r'累計スタート[\s:：]*(\d+)', 'dNowStart': r'スタート[\s:：]*(\d+)',
                'dMY': r'最大持玉[\s:：]*(\d+)'
            }
            today = {k: int(re.search(p, text).group(1)) if re.search(p, text) else 0 for k, p in patterns.items()}
            return {'machineNumber': self.extract_number(), 'machineName': self.driver.title,
                    'today': today, 'lastTime': self.now(), 'type': 'S'}
        except: return None

    def parse_table(self, table):
        labels = {'dBB': 'BB', 'dRB': 'RB', 'dART': 'AT・ART',
                  'dTotalStart': '累計スタート', 'dNowStart': 'スタート', 'dMY': '最大持玉'}
        data = {}
        for key, label in labels.items():
            try:
                td = table.find_element(By.XPATH, f".//td[normalize-space()='{label}']/following-sibling::td")
                data[key] = int(td.text.replace(',', '').strip())
            except:
                data[key] = 0
        return data

    def extract_number(self):
        try:
            url = self.driver.current_url
            return url.split('n=')[1].split('&')[0] if 'n=' in url else None
        except: return None

    def now(self):
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def extract_bb_data(self, data):
        t = data.get('today', {})
        total = t.get('dTotalStart', 0)
        return {
            'machine_number': data.get('machineNumber'), 'machine_name': data.get('machineName'),
            'last_update': data.get('lastTime'), 'machine_type': data.get('type'),
            'today': {
                'bb_count': t.get('dBB', 0), 'rb_count': t.get('dRB', 0), 'art_count': t.get('dART', 0),
                'total_start': total, 'current_start': t.get('dNowStart', 0), 'max_balls': t.get('dMY', 0),
                'bb_probability': self.prob(total, t.get('dBB', 0)),
                'rb_probability': self.prob(total, t.get('dRB', 0)),
                'art_probability': self.prob(total, t.get('dART', 0)),
                'combined_probability': self.prob(total, sum([t.get(k, 0) for k in ['dBB','dRB','dART']]))
            }
        }

    def prob(self, total, count):
        return f"1/{round(total / count)}" if count and total else "-"

    def save_to_csv(self, data, fname=None):
        if not data: return False
        fname = fname or f"pachinko_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        today = data.get('today', {})
        row = {
            'machine_number': data['machine_number'], 'machine_name': data['machine_name'],
            'machine_type': data['machine_type'], 'period': '今日', 'last_update': data['last_update'], **today
        }
        df = pd.DataFrame([row])
        cols = ['machine_number', 'machine_name', 'machine_type', 'period', 'last_update',
                'bb_count', 'rb_count', 'art_count', 'total_start', 'current_start', 'max_balls',
                'bb_probability', 'rb_probability', 'art_probability', 'combined_probability']
        df = df.reindex(columns=cols, fill_value=None)
        df.to_csv(fname, index=False, encoding='utf-8-sig')
        return True

    def close(self):
        if self.driver:
            self.driver.quit()

    def __enter__(self): return self
    def __exit__(self, *args): self.close()

def extract_m_n_from_url(url):
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        m = params.get('m', [None])[0]
        n = params.get('n', [None])[0]
        return m, n
    except Exception:
        return None, None

def fetch_all(urls):
    results = []
    with PachinkoDataScraper(headless=True) as scraper:
        for url in urls:
            start = time.perf_counter()
            m, n = extract_m_n_from_url(url)
            if not m or not n:
                print(f"⚠️ URLからmまたはnを取得できませんでした: {url}")
                continue
            print(f"開始: m={m}, n={n} のデータ取得中...")

            try:
                raw = scraper.scrape(url)
                if raw:
                    bb = scraper.extract_bb_data(raw)
                    elapsed = time.perf_counter() - start
                    print(f"✅ {n} 取得成功 （所要時間: {elapsed:.2f}秒）")
                    results.append(bb)
                else:
                    elapsed = time.perf_counter() - start
                    print(f"❌ {n} データ取得失敗 （所要時間: {elapsed:.2f}秒）")
            except Exception as e:
                elapsed = time.perf_counter() - start
                print(f"❌ {n} 例外発生: {e} （所要時間: {elapsed:.2f}秒）")
    return results

def main():
    targets = [
        "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120096&n=1066",
        "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120096&n=1067",
        "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120096&n=1068",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120096&n=1070",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120126&n=1071",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120073&n=1072",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120093&n=1073",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120117&n=1075",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120248&n=1076",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120073&n=1077",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120034&n=1078",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120123&n=1080",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120168&n=1081",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120137&n=1082",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120126&n=1083",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120071&n=1085",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120089&n=1086",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120126&n=1087",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120073&n=1088",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120077&n=1100",
        #"https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120216&n=1131",
    ]


    overall_start = time.perf_counter()
    all_data = fetch_all(targets)
    overall_elapsed = time.perf_counter() - overall_start
    print(f"\n=== 全処理完了 所要時間: {overall_elapsed:.2f}秒 ===\n")

    if all_data:
        rows = []
        for data in all_data:
            today = data.get('today', {})
            row = {
                'machine_number': data['machine_number'], 'machine_name': data['machine_name'],
                'machine_type': data['machine_type'], 'period': '今日', 'last_update': data['last_update'],
                **today
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        cols = ['machine_number', 'machine_name', 'machine_type', 'period', 'last_update',
                'bb_count', 'rb_count', 'art_count', 'total_start', 'current_start', 'max_balls',
                'bb_probability', 'rb_probability', 'art_probability', 'combined_probability']
        df = df.reindex(columns=cols, fill_value=None)
        fname = f"pachinko_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(fname, index=False, encoding='utf-8-sig')
        print(f"✅ 全台分のCSV保存成功: {fname}")
    else:
        print("❌ データが取得できませんでした")


if __name__ == "__main__":
    main()
