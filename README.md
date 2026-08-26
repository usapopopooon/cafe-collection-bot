# cafe-collection-bot

`level-bot` から分離したカフェ・コレクション専用Discord Botです。

Discordのカフェ機能、カード画像495枚、サイト向け公開API、ヘルスAPI、CI、
Docker Composeをこのリポジトリが所有します。抽選・カード棚・ランキングは認証付き
内部APIを通じて、level-botに残る共通の抽選・XP・コレクション状態を利用します。

公開コマンド、パネルの文言・部品順、応答、投稿先は移行時に固定したUI契約に従い、
独自の公開操作や構成事情を示すDiscord表示は追加しません。抽選、XP・抽選枠、全カード棚、
お気に入り、XP・メダル交換、カード保護、棚テーマ、セットメニュー、ランキング、利用統計、
利用ロール管理を同じ操作で利用できます。UI契約は
[docs/feature-parity.md](docs/feature-parity.md) に固定しています。

状態、取引、公開データ、DBテーブルの正本は `level-bot` に残しています。サイトが参照する
図鑑・ランキング・個人棚APIとカード画像は
`https://cafe-collection-bot.chill-cafe.site` から配信します。JSON APIはサイトが
level-botとの通信に使っている同じ公開用Bearer JWTを要求し、画像URLは公開のままです。
カフェ台帳はこのBotに設定されたチャンネルへ投稿します。抽選とXP交換の操作ID、DB更新は
共通APIで一意に処理し、Discordの再送で同じ取引を二重確定しません。

新Botの公開コマンドは `/cafe-collection` 配下へ統一しています。

- `/cafe-collection setup`: カウンター・台帳・抽選パネルを作成または修復
- `/cafe-collection leaderboard-panel channel`: 選んだチャンネルへランキングパネルを投稿または更新
- `/cafe-collection stats`: 利用状況とXP収支を管理者だけに表示
- `/cafe-collection access-role add|remove|list`: 利用ロールを管理
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
設定します。`EXTERNAL_API_KEY` はchill-cafe-siteがlevel-botへ送っている公開用Bearer
JWTと同じ値をAPIコンテナだけに設定します。初回配置だけ `BOT_ENABLED=false` とし、
level-bot APIの準備後に有効化します。

## 検証

```bash
uv run ruff check src
uv run ruff format --check src
uv run mypy src
uv run pytest -q
```

## 責務境界

分離後の責務境界は [docs/migration.md](docs/migration.md) を参照してください。
Coolifyへの登録方法は [docs/coolify.md](docs/coolify.md) を参照してください。
