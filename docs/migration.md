# Cafe Collection migration

## 現在の状態

このリポジトリは新しいBotプロセスと画像・ヘルスAPIを所有します。カード画像は両Botで
同じSHA-256マニフェストへ固定したコピーを持ちます。カフェ・コレクションのドメイン実装、
DBモデル、マイグレーション、公開APIの正本は引き続き `level-bot` が所有します。

## 移行順序

1. 新しいDiscord ApplicationとBot Tokenを用意する。
2. `level-bot` に専用内部APIと `CAFE_COLLECTION_API_TOKEN` を先に配置する。
3. 新Botを `BOT_ENABLED=false` で配置し、画像APIとマニフェスト一致を確認する。
4. `CAFE_COLLECTION_BOT_ENABLED=true` を維持したまま新Botを有効にし、両Botで同じ抽選・
   XP・コレクション状態が見えることを確認する。
5. 交換、カスタマイズ、ランキング、公開台帳の移行中も旧Botを有効に保つ。
6. 公開台帳の再試行を含む全機能が新Botへ移り、回帰確認が終わった後にだけ旧Botの
   `CAFE_COLLECTION_BOT_ENABLED=false` を設定する。
7. 公開APIの移行後にだけ、旧API側の `CAFE_COLLECTION_PUBLIC_API_ENABLED=false` を設定する。
8. DB分離は、XPとカード消費の原子性を維持する移行方式とマイグレーションを用意してから行う。

## 安全上の制約

カード残高の確認と消費を別プロセス間の単純な読取・書込に分けると競合が起きます。
DBを分離する場合は、冪等なイベントIDを持つ予約・確定APIまたは同等のトランザクション
プロトコルを先に導入します。
