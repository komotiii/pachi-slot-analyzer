import os
import re
import time
import json
import requests
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import logging

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
logging.getLogger().setLevel(logging.CRITICAL)

#2.2
targets = [
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

        driver = webdriver.Chrome(options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def scrape(self, url):
        self.driver.get(url)
        WebDriverWait(self.driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(4)
        return self.extract_data()

    def extract_data(self):
        try:
            root = self.driver.find_element(By.CSS_SELECTOR, ".panel")
            name = root.find_element(By.CSS_SELECTOR, "div.machineName h2").text.strip()
            match = re.match(r'(\d+)\s*番台(.*)', name)
            number, title = match.groups() if match else (None, name)
            table = root.find_element(By.CSS_SELECTOR, "section#dataSection table")
            today['dBB'] = self.extract_bb_from_dom(root)
            return {'machineNumber': number, 'machineName': title}
        except:
            return None

    def extract_bb_from_dom(self, root):
        try:
            text = root.text
            match = re.search(r'BB[\s:：]*(\d+)', text)
            return int(match.group(1)) if match else 0
        except:
            return 0

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

    def close(self):
        if self.driver:
            self.driver.quit()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

def extract_m_n_from_url(url):
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return params.get('m', [None])[0], params.get('n', [None])[0]

def fetch_all(urls):
    results = []
    with PachinkoDataScraper(headless=True) as scraper:
        for url in urls:
            m, n = extract_m_n_from_url(url)
            print(f"Getting: m={m}, n={n}")
            raw = scraper.scrape(url)
            bb = scraper.extract_bb_data(raw) if raw else None
            if bb:
                results.append(bb)
    return results

def main():
    start = time.perf_counter()
    all_data = fetch_all(targets)
    print(f"\n=== Complete time: {time.perf_counter() - start:.2f} sec ===\n")
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
    print(f"Success to save csv: {fname}")

if __name__ == "__main__":
    main()
