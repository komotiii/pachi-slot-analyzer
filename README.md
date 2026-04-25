# pachi-slot-analyzer

## Usage

Run with default config:

```bash
python main.py
```

## Config

`config.json` example:

```json
{
	"save_dir": "./data",
	"max_workers": 4,
	"discovery": {
		"start_urls": [
			"https://reitoweb.com/b_moba/doc/"
		],
		"include_pattern": "/machine\\.php\\?",
		"max_depth": 3,
		"max_pages": 800,
		"same_host_only": true,
		"cache_targets_path": "./targets.discovered.json"
	}
}
```

店舗指定の discovery は、以下の 2 段階で収集します。

1. `news.php?h=...` から `data.php`（機種一覧）を抽出
2. `data.php` から `machine.php`（各台）を抽出

例:

- レイト平塚: https://reitoweb.com/b_moba/doc/news.php?h=4
- レイト荒川沖: https://reitoweb.com/b_moba/doc/news.php?h=1

`cache_targets_path` を指定すると、発見した `machine.php` URL 一覧を JSON 保存します。

```json
{
	"save_dir": "./data",
	"max_workers": 4,
	"discovery": {
		"strategy": "news_to_data_to_machine",
		"news_urls": [
			"https://reitoweb.com/b_moba/doc/news.php?h=4",
			"https://reitoweb.com/b_moba/doc/news.php?h=1"
		],
		"data_include_pattern": "/data\\.php\\?",
		"machine_include_pattern": "/machine\\.php\\?",
		"max_data_pages": 800,
		"same_host_only": true,
		"cache_targets_path": "./targets.discovered.json"
	}
}
```

## Fallback (manual JSON)

再帰探索を使わず、従来どおり JSON を直接指定することもできます。

```json
{
	"save_dir": "./data",
	"max_workers": 4,
	"targets_path": "./targets.json"
}
```

`targets.json` format (recommended):

```json
{
	"urls": [
		"https://example.com/a",
		"https://example.com/b"
	]
}
```

You can also use a plain array:

```json
[
	"https://example.com/a",
	"https://example.com/b"
]
```
