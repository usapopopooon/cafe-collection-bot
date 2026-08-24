# Cafe Collection migration

## 現在の状態

このリポジトリは新しいBotプロセスとサイト向け公開APIを所有します。カード画像は両Botで
同じSHA-256マニフェストへ固定したコピーを持ちます。カフェ・コレクションのドメイン実装、
DBモデル、マイグレーション、公開データの正本は引き続き `level-bot` が所有します。
サイトは新BotのAPIを参照し、新Botはlevel-botの公開データAPIを上流として中継します。

## 移行順序

1. 新しいDiscord ApplicationとBot Tokenを用意する。
2. `level-bot` に専用内部APIと `CAFE_COLLECTION_API_TOKEN` を先に配置する。
3. 新Botを `BOT_ENABLED=false` で配置し、画像APIとマニフェスト一致を確認する。
4. `CAFE_COLLECTION_BOT_ENABLED=true` を維持したまま新Botを有効にし、両Botで同じ抽選・
   XP・コレクション状態が見えることを確認する。
5. 新Botで `/cafe-collection setup` を実行してカウンター・台帳・抽選パネルを作成し、
   `/cafe-collection leaderboard-panel channel` でランキングの投稿先を選ぶ。
6. 新Botでも交換、保護、お気に入り、メダル、棚テーマ、セットメニュー、統計、
   利用ロール管理を含む全機能が使えることを確認する。状態の正本はlevel-botに置いた
   まま、旧Botも有効に保つ。各Botは自分に設定された台帳へ独立して投稿する。
7. 公開台帳の再試行を含む全機能が新Botへ移り、回帰確認が終わった後にだけ旧Botの
   `CAFE_COLLECTION_BOT_ENABLED=false` を設定する。
8. 公開データの正本も新Botへ移し、level-botを上流に使わなくなった後にだけ、旧API側の
   `CAFE_COLLECTION_PUBLIC_API_ENABLED=false` を設定する。現在は無効化しない。
9. DB分離は、XPとカード消費の原子性を維持する移行方式とマイグレーションを用意してから行う。

## 安全上の制約

カード残高の確認と消費を別プロセス間の単純な読取・書込に分けると競合が起きます。
DBを分離する場合は、冪等なイベントIDを持つ予約・確定APIまたは同等のトランザクション
プロトコルを先に導入します。

両Botのパネルは併用できます。内部のボタン識別子はBotごとに分離し、抽選は共通APIへ
Discord操作IDを冪等キーとして渡します。旧Botと新Botは、自分に設定された台帳へ同じ
確定取引を1回ずつ投稿します。投稿済みIDはBot別に持つため、一方の投稿が他方を止めず、
各Bot内の再試行でも重複投稿しません。
