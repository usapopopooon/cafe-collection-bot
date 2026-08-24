# Coolify deployment

## Application

GitHubリポジトリからDocker Composeアプリケーションを作成します。

- Build Pack: Docker Compose
- Docker Compose Location: `/docker-compose.coolify.yml`
- ヘルスチェック対象サービス: `api`
- 内部ポート: `8000`
- ヘルスチェックパス: `/readyz`

`bot` は公開ドメインを必要としません。`api` は同じ画像セットを配信できますが、現在の
Botはコンテナ内の画像を直接添付するため、公開APIとして使わない間はドメイン不要です。

## Variables

`.env.coolify.example` の内容をCoolify Variablesへ設定します。連携キーにはランダムな
長い値を設定し、level-bot側と同じ値にしてください。

```text
BOT_ENABLED=false
DISCORD_TOKEN=...
LEVEL_BOT_API_BASE_URL=https://...
LEVEL_BOT_API_TOKEN=...
```

## Safe first deployment

初回は `BOT_ENABLED=false` でデプロイし、画像APIのヘルスチェックを先に確認します。
level-botへ同じ `CAFE_COLLECTION_API_TOKEN` を設定し、内部APIを先にデプロイしてから
新Botを有効にします。

新Botの全カフェ機能はlevel-botの内部APIを使うため、旧Botのパネルと同じ抽選・XP・
カード棚・交換・保護・お気に入り・メダル・棚テーマ・ランキング状態を参照します。旧Bot側の
`CAFE_COLLECTION_BOT_ENABLED=true` は維持でき、両Botを併用できます。デプロイ後は
管理者が配置先で `/cafe panel`、`/cafe ledger`、`/cafe ranking` を実行します。

カフェ台帳は各Botが自分に設定されたチャンネルへ投稿します。両方に台帳が設定されて
いれば、同じ確定取引が両方へ1回ずつ掲載されます。新Botは自分からの取引を直後に投稿し、
旧Botからの取引と一時的に失敗した投稿を最大5分間隔で再試行します。

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
