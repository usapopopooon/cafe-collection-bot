# cafe-collection-bot

カフェ・コレクションを `level-bot` から段階的に分離するためのDiscord Botです。

現在は独立した起動・設定・CI・Docker実行ができる最小構成です。カフェカード、抽選、
コレクション、交換、ランキング、公開API、DBテーブルはまだ `level-bot` が正であり、
このBotへは移していません。

## 開発

必要環境はPython 3.12です。

```bash
uv sync --extra dev
cp .env.example .env
uv run pytest -q
uv run python -m cafe_collection
```

`.env` の `DISCORD_TOKEN` には、新しく作成したDiscord ApplicationのBot Tokenを設定します。
旧Botとのコマンド二重登録を避けるため、移行準備中はこのBotを本番ギルドへ接続しないで
ください。

## 検証

```bash
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -q
```

## 段階移行

移行の責務境界と安全な切替順序は [docs/migration.md](docs/migration.md) を参照してください。
