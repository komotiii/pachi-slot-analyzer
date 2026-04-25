# pachi-slot-analyzer

パチスロ台データを自動収集して CSV に保存するスクリプトです。

## 使い方

```bash
python main.py
```

設定は `config.json` を編集します。

## 設定例（店舗ニュース起点の自動探索）

```json
{
  "save_dir": "./data",
  "max_workers": 4,
  "discovery": {
    "strategy": "news_to_data_to_machine",
    "news_urls": [
      "https://reitoweb.com/b_moba/doc/news.php?h=4"
    ],
    "data_include_pattern": "/data\\.php\\?",
    "machine_include_pattern": "/machine\\.php\\?",
    "allowed_t_values": "37",
    "show_data_url_every": 5,
    "max_data_pages": 800,
    "same_host_only": true,
    "cache_targets_path": "./targets.discovered.json",
    "use_cached_targets_if_exists": true
  }
}
```

## 探索フロー

1. `news.php?h=...` から `data.php`（機種一覧）を抽出
2. `data.php` から `machine.php`（各台）を抽出
3. `machine.php` を並列スクレイピングして CSV 出力

## 2回目以降の速度

`use_cached_targets_if_exists: true` の場合、`cache_targets_path` が存在すれば URL 探索をスキップして、その JSON を再利用します。

- 速くなる部分: `news.php` / `data.php` の探索フェーズ
- 毎回必要な部分: 各 `machine.php` の実データ取得

つまり、2回目以降は探索分だけ速くなります。

## 主要パラメータ

- `allowed_t_values`: `data.php` の `t=` を許可リストで絞る
- `allowed_m_values`: `data.php` の `m=` を許可リストで絞る（未指定なら全機種）
- `show_data_url_every`: 何件ごとに「今見ている data.php URL」を表示するか
- `max_data_pages`: 読み込む `data.php` の最大件数

## 手動ターゲット指定（フォールバック）

自動探索を使わず、JSON で対象 URL を直接指定することもできます。

```json
{
  "save_dir": "./data",
  "max_workers": 4,
  "targets_path": "./targets.json"
}
```

`targets.json` は以下のどちらでも可:

```json
{
  "urls": [
    "https://example.com/a",
    "https://example.com/b"
  ]
}
```
