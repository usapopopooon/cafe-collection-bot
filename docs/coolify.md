# Coolify deployment

## Application

GitHubリポジトリからDocker Composeアプリケーションを作成します。

- Build Pack: Docker Compose
- Docker Compose Location: `/docker-compose.coolify.yml`
- ヘルスチェック対象サービス: `api`
- 内部ポート: `8000`
- ヘルスチェックパス: `/readyz`

`bot` は公開ドメインを必要としません。`api` のポート8000へ
`https://cafe-collection-bot.chill-cafe.site` を割り当てます。サイト向けJSON APIと、
Botと同じマニフェストに固定したカード画像をこのサービスから配信します。

## Variables

`.env.coolify.example` の内容をCoolify Variablesへ設定します。連携キーにはランダムな
長い値を設定し、level-bot側と同じ値にしてください。

```text
BOT_ENABLED=false
DISCORD_TOKEN=...
LEVEL_BOT_API_BASE_URL=https://...
LEVEL_BOT_API_TOKEN=...
EXTERNAL_API_KEY=...
CORS_ORIGINS=https://chill-cafe.site
```

`EXTERNAL_API_KEY` は、chill-cafe-siteのビルドで `VITE_LEVEL_BOT_API_TOKEN` として
使っている公開用Bearer JWT、およびlevel-botの `EXTERNAL_API_KEY` と同じ値にします。
これはクローラー避けであり、権限認可の境界ではありません。カード画像は通常の
`img`要素とOGPから参照できるようBearer JWTを要求しません。

## Safe first deployment

初回は `BOT_ENABLED=false` でデプロイし、画像APIのヘルスチェックを先に確認します。
level-botへ同じ `CAFE_COLLECTION_API_TOKEN` を設定し、内部APIを先にデプロイしてから
新Botを有効にします。

このBotの全カフェ機能はlevel-botの内部APIを使い、抽選・XP・カード棚・交換・保護・
お気に入り・メダル・棚テーマ・ランキング状態を参照します。デプロイ後は
管理者が `/cafe-collection setup` を実行し、ランキングが必要なチャンネルを
`/cafe-collection leaderboard-panel channel` で選びます。

カフェ台帳はこのBotに設定されたチャンネルへ投稿します。取引を直後に投稿し、
一時的に失敗した投稿を最大5分間隔で再試行します。

Botを有効にした後は、Discordへ接続でき、かつlevel-bot内部APIのバージョン・画像
マニフェストが一致している場合だけBotコンテナがhealthyになります。Discordまたは
level-bot APIの切断・認証エラーは最大30秒程度でreadinessへ反映され、その後Composeの
ヘルスチェック再試行回数に従ってunhealthyになります。

カフェデータの正本はまだ `level-bot` 側です。未使用の空DBは置かず、実データの移行方式が
確定した段階でマイグレーションと一緒に追加します。

## Resource defaults

- Bot: 320 MB / 0.75 CPU
- API: 192 MB / 0.50 CPU

必要ならCoolify Variablesの `*_MEMORY_LIMIT` / `*_CPUS` で上書きできます。
