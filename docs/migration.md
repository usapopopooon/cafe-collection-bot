# Cafe Collection migration

## 現在の状態

このリポジトリは新しいBotプロセス、内部ヘルスAPI、空のPostgreSQLを所有します。
カフェ・コレクションのドメイン実装、画像、DBモデル、マイグレーション、公開APIは
引き続き `level-bot` が所有します。

## 移行順序

1. 新しいDiscord ApplicationとBot Tokenを用意する。
2. `level-bot` のカフェ機能を、既存のポート境界を保ったままこのリポジトリへ移す。
3. 共有DB期間中は、XPとカード消費を同一トランザクションで保護できるアダプターを使う。
4. 新Botのコマンド登録を無効にした状態で接続・読取確認を行う。
5. 切替直前に `level-bot` の `CAFE_COLLECTION_BOT_ENABLED=false` を設定する。
6. 旧Botのカフェコマンドが停止したことを確認してから、新Botのコマンド登録を有効にする。
7. 公開APIの移行後にだけ、旧API側の `CAFE_COLLECTION_PUBLIC_API_ENABLED=false` を設定する。

## 安全上の制約

カード残高の確認と消費を別プロセス間の単純な読取・書込に分けると競合が起きます。
DBを分離する場合は、冪等なイベントIDを持つ予約・確定APIまたは同等のトランザクション
プロトコルを先に導入します。
