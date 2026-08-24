# cafe-collection-bot

カフェ・コレクションを `level-bot` から段階的に分離するためのDiscord Botです。

現在は独立したBot、画像・ヘルスAPI、CI、Docker Composeを持ち、Coolifyへ
配置できます。`/cafe draw` と `/cafe collection` は認証付き内部APIを通じてlevel-botの
同じ抽選・XP・コレクション状態を利用します。画像363枚は両リポジトリで同じ
SHA-256マニフェストに固定しています。

交換、カスタマイズ、ランキング、公開台帳、公開API、DBテーブルの正本はまだ
`level-bot` です。併用中の新Botの抽選結果は本人だけに表示し、旧Botの公開台帳処理と
二重投稿しないようにしています。確定した抽選はlevel-bot側の既存再試行処理が拾い、
最大5分程度で従来のカフェ台帳にも投稿します。

## 開発

必要環境はPython 3.12です。

```bash
uv sync --extra dev
cp .env.example .env
docker compose up -d api
uv run pytest -q
uv run python -m cafe_collection
```

`.env` の `DISCORD_TOKEN` には、新しく作成したDiscord ApplicationのBot Tokenを設定します。
`LEVEL_BOT_API_BASE_URL` と `LEVEL_BOT_API_TOKEN` はlevel-bot APIのURLと専用キーを
設定します。初回配置だけ `BOT_ENABLED=false` とし、level-bot APIの準備後に有効化します。

## 検証

```bash
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -q
```

## 段階移行

移行の責務境界と安全な切替順序は [docs/migration.md](docs/migration.md) を参照してください。
Coolifyへの登録方法は [docs/coolify.md](docs/coolify.md) を参照してください。
