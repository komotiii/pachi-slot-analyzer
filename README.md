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
	"targets_path": "./targets.json",
	"max_workers": 4
}
```

`targets_path` is JSON only.

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
