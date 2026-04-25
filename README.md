# pachi-slot-analyzer

特定サイトの台ページを自動探索し、当日データをCSV保存するPythonツールです。

## できること

- `news.php -> data.php -> machine.php` の順で対象URLを自動探索
- 各台ページを並列スクレイピング
- 一時的に `0番台` が表示されるページを待機してから取得
- 取得失敗時はドライバを作り直してリトライ
- BB/RB/ART、回転数、合算確率などをCSV出力

## セットアップ

1. 依存ライブラリをインストール

```bash
pip install -r requirements.txt
```

2. 設定ファイルを作成

```bash
copy config.example.json config.json
```

3. `config.json` を必要に応じて編集

4. 実行

```bash
python main.py
```

## 設定ファイル

- `config.json` はローカル運用（`.gitignore` 対象）
- テンプレートは `config.example.json`
- 相対パスは `main.py` のあるディレクトリ基準で解決

### 設定例

```json
{
   "save_dir": "./data",
   "max_workers": 4,
   "discovery": {
      "strategy": "news_to_data_to_machine",
      "news_urls": [
         "https://reitoweb.com/b_moba/doc/news.php"
      ],
      "data_include_pattern": "/data\\.php\\?",
      "machine_include_pattern": "/machine\\.php\\?",
      "allowed_h_values": ["4", "11"],
      "allowed_t_values": ["37", "31", "28"],
      "allowed_m_values": [],
      "show_data_url_every": 10,
      "max_data_pages": 800,
      "same_host_only": true
   }
}
```

### 実際に使用される主なキー

- `save_dir`: CSV保存先
- `max_workers`: 台ページ取得の並列数
- `discovery.news_urls`: 探索開始URL（必須）
- `discovery.data_include_pattern`: `data.php` 抽出用正規表現
- `discovery.machine_include_pattern`: `machine.php` 抽出用正規表現
- `discovery.allowed_h_values`: `news_urls` に `h=` がない場合の展開候補
- `discovery.allowed_t_values`: `data.php` の `t=` フィルタ
- `discovery.allowed_m_values`: `data.php` の `m=` フィルタ
- `discovery.max_data_pages`: 走査する `data.php` の上限
- `discovery.max_workers`: `data.php` 走査時の並列数（未指定時は10）

## 処理フロー

1. 設定を読み込み、保存先ディレクトリを作成
2. ニュースページから `data.php` を収集し、さらに `machine.php` を収集
3. `machine.php` を並列取得
4. 各ページで `document.readyState == complete` を待機
5. `div.machineName h2` が `0番台` 以外になるまで待機してから解析
6. 失敗時は最大3回までリトライ（スレッド内ドライバをリセット）
7. 結果を台番号順でソートし、CSV保存

## 出力CSV

ファイル名: `pachinko_YYYYmmdd_HHMMSS.csv`

列:

- `h` (ホール名)
- `n` (番台)
- `machine` (機種)
- `tG` (累計スタート)
- `cG` (現在スタート)
- `bb`, `rb`, `art` (数)
- `bbp`, `rbp`, `artp`, `brp` (確率)
- `max` (最大持玉)

## 補足

- SeleniumとChromeDriverが必要
- Chromeはヘッドレスモードで起動
- サイト側のHTML構造が変わると、セレクタ調整が必要
