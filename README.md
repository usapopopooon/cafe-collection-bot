# cafe-collection-bot

カフェ・コレクションを `level-bot` から段階的に分離するためのDiscord Botです。

現在は独立したBot、画像・ヘルスAPI、CI、Docker Composeを持ち、Coolifyへ
配置できます。抽選・カード棚・ランキングは認証付き内部APIを通じてlevel-botの
同じ抽選・XP・コレクション状態を利用します。画像363枚は両リポジトリで同じ
SHA-256マニフェストに固定しています。

公開コマンド、パネルの文言・部品順、応答、投稿先は `level-bot` の既存UIを基準とし、
独自の公開操作や移行事情を示すDiscord表示は追加しません。抽選、XP・抽選枠、全カード棚、
お気に入り、XP・メダル交換、カード保護、棚テーマ、セットメニュー、ランキング、利用統計、
利用ロール管理を同じ操作で利用できます。UI契約は
[docs/feature-parity.md](docs/feature-parity.md) に固定しています。

状態、取引、公開API、DBテーブルの正本はまだ `level-bot` です。カフェ台帳は各Botが
自分に設定されたチャンネルへ独立して投稿します。両方に台帳が設定されていれば、同じ
確定取引を両方の台帳へ1回ずつ掲載します。抽選とXP交換の操作ID、DB更新は共通のため、
Discordの再送や2つのBotの併用で同じ取引そのものを二重確定しません。

公開コマンドも `level-bot` と同じです。

- `/cafe-gacha setup`: カウンター・台帳・抽選パネルを作成または修復
- `/cafe-gacha leaderboard-panel channel`: 選んだチャンネルへランキングパネルを投稿または更新
- `/cafe-gacha stats`: 利用状況とXP収支を管理者だけに表示
- `/cafe-gacha access-role add|remove|list`: 利用ロールを管理
- `/cafe-collection protect`: 名前検索で所持カードの保護／解除を切り替え

台帳チャンネルに説明用の見出しカードは投稿しません。確定した抽選結果とXP交換だけを
掲載し、一時的に失敗した投稿は最大5分間隔で再試行します。

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
