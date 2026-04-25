import os
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
save_dir = r"C:\Users\yakim\OneDrive - 筑波大学\Unification\Slot\data"
os.makedirs(save_dir, exist_ok=True)

targets = [
    #20Slot

    #5.5Slot
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120226&n=1120",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120231&n=1121",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120252&n=1122",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120194&n=1123",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120155&n=1125",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120292&n=1126",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120142&n=1127",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120203&n=1128",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120191&n=1130",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120216&n=1131",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120145&n=1132",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120155&n=1133",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120122&n=1135",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120180&n=1136",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120217&n=1137",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120268&n=1138",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120187&n=1150",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120155&n=1151",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120216&n=1152",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120103&n=1153",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120256&n=1155",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120191&n=1156",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120244&n=1157",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120182&n=1158",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120230&n=1160",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120279&n=1161",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120253&n=1162",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120130&n=1163",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120271&n=1165",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120258&n=1166",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120238&n=1167",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120217&n=1168",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120181&n=1170",
    #2.2Slot
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120096&n=1066",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120096&n=1067",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120096&n=1068",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120096&n=1070",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120126&n=1071",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120073&n=1072",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120093&n=1073",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120117&n=1075",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120248&n=1076",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120073&n=1077",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120034&n=1078",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120123&n=1080",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120168&n=1081",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120137&n=1082",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120126&n=1083",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120071&n=1085",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120089&n=1086",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120126&n=1087",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120073&n=1088",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=28&m=99120077&n=1100",
    "https://reitoweb.com/b_moba/doc/machine.php?h=4&t=31&m=99120216&n=1131",
]

_driver_pool = threading.local()

def get_driver():
    if not hasattr(_driver_pool, "driver"):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
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
        except:
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
            except:
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
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_url, url): url for url in urls}
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                print(f"Error: {e}")
    return results


def main():
    start = time.perf_counter()
    all_data = fetch_all_parallel(targets, max_workers=4)
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
    fname = os.path.join(save_dir, f"pachinko_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    df.to_csv(fname, index=False, encoding='utf-8-sig')
    print(f"Saved CSV: {fname}")

if __name__ == "__main__":
    main()
