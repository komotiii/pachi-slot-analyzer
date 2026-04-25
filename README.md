# pachi-slot-analyzer

特定サイトから台データを取得し、CSVとして保存するツールです。

## できること

- 店舗ページから対象機種ページを自動探索
- 各台ページを並列取得
- BB/RB/ART や回転数をCSV出力
- 探索結果URLをキャッシュして、2回目以降を高速化

## セットアップ

1. 依存ライブラリをインストール

```bash
pip install -r requirements.txt
```

2. 設定ファイルを作成

```bash
copy config.example.json config.json
```

3. 必要に応じて `config.json` を編集

4. 実行

```bash
python main.py
```

## 設定ファイル

- `config.json` はローカル運用（`.gitignore` 対象）
- テンプレートは `config.example.json`

### 設定例

```json
{
  "save_dir": "./data",
  "max_workers": 2,
  "discovery": {
    "strategy": "news_to_data_to_machine",
    "news_urls": [
      "https://reitoweb.com/b_moba/doc/news.php?h=4"
    ],
    "data_include_pattern": "/data\\.php\\?",
    "machine_include_pattern": "/machine\\.php\\?",
    "allowed_t_values": ["37"],
    "allowed_m_values": ["99120010"],
    "show_data_url_every": 5,
    "max_data_pages": 800,
    "same_host_only": true,
    "cache_targets_path": "./targets.discovered.json",
    "use_cached_targets_if_exists": true
  }
}
```

## main.py の処理内容

`main.py` の全体フローは次の順です。

1. `load_config()`
   - `config.json` を読み込み（コメント付きJSONにも対応）
2. ターゲットURLの決定
   - `discovery` がある場合はニュースページから `machine.php` を探索
   - `use_cached_targets_if_exists` が有効ならキャッシュを優先利用
3. `fetch_all_parallel()`
   - `ThreadPoolExecutor` で台URLを並列取得
4. `fetch_url()`
   - 一時的な `0番台` / 空データ対策としてリトライ
5. CSV保存
   - 取得済みデータを `data/pachinko_YYYYmmdd_HHMMSS.csv` に保存

## 探索方式

`strategy = news_to_data_to_machine` のときは次の順にたどります。

1. `news.php?h=...` を読む
2. リンクから `data.php` を抽出
3. 各 `data.php` から `machine.php` を抽出

フィルタで探索範囲を絞れます。

- `allowed_t_values`: `data.php` の `t=` を絞る
- `allowed_m_values`: `data.php` の `m=` を絞る

## 2回目以降の速度

`cache_targets_path` に探索結果を保存し、次回はそのJSONを使って探索をスキップできます。

- 高速化される部分: URL探索（news/data）
- 毎回必要な部分: 各台ページの実データ取得

## 補足

- SeleniumとChromeDriverが必要です
- 出力CSVやローカル設定はGit管理対象から除外しています
