# Coolify deployment

## Application

GitHubリポジトリからDocker Composeアプリケーションを作成します。

- Build Pack: Docker Compose
- Docker Compose Location: `/docker-compose.coolify.yml`
- ヘルスチェック対象サービス: `api`
- 内部ポート: `8000`
- ヘルスチェックパス: `/readyz`

`bot` は公開ドメインを必要としません。`api` も現在は内部ヘルスチェックだけなので、
公開ドメインを割り当てる必要はありません。

## Variables

`.env.coolify.example` の内容をCoolify Variablesへ設定します。少なくともDBパスワードを
ランダムな長い値へ変更してください。

```text
SERVICE_PASSWORD_POSTGRES=...
BOT_ENABLED=false
DISCORD_TOKEN=...
```

## Safe first deployment

現行 `level-bot` がカフェコマンドを所有している間は、必ず
`BOT_ENABLED=false` でデプロイします。この状態でもBotコンテナは待機し、APIとPostgresの
ヘルスチェックを先に確認できます。

現時点の新Botは移行用の実行基盤だけで、カフェコマンドをまだ搭載していません。
したがって `BOT_ENABLED=true` にしても切替は完了しません。ドメイン機能とデータ移行が
完了するまでは無効のままにします。

## Database

Postgres 18のデータは `postgres18-data` ボリュームへ保存され、外部公開しません。
カフェデータの正本はまだ `level-bot` 側です。この新DBへのデータコピーや旧DBの削除は
自動実行しません。

## Resource defaults

- Bot: 256 MB / 0.75 CPU
- API: 192 MB / 0.50 CPU
- PostgreSQL: 192 MB / 0.50 CPU

必要ならCoolify Variablesの `*_MEMORY_LIMIT` / `*_CPUS` で上書きできます。
