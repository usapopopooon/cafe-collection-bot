# シンガポール、コピティアムのひと休み

2026-10-02。既存669種類にシンガポールで親しまれる6品を追加し、合計675種類。飲み物2種、食べ物4種。

既存のカヤトーストとテータリックに加え、バター入りの珈琲、ローズミルク、パンダンを使う菓子、層や型押しが特徴の伝統菓子を選んだ。近隣地域にも広がる食文化として扱い、シンガポールだけの発祥とは断定しない。クエ・ラピスは色の異なる層を蒸す型で、茶色い焼き菓子のラピス・レギットとは区別する。

| カード・保存画像 | 分類 | 表示レアリティ |
| --- | --- | --- |
| [コピ・グーユー](../src/cafe_collection/assets/kopi-gu-you.jpg) | 飲み物 | HN |
| [バンドン](../src/cafe_collection/assets/bandung.jpg) | 飲み物 | N |
| [パンダンシフォンケーキ](../src/cafe_collection/assets/pandan-chiffon-cake.jpg) | 食べ物 | HN |
| [オンデオンデ](../src/cafe_collection/assets/ondeh-ondeh.jpg) | 食べ物 | HN |
| [クエ・ラピス（蒸し菓子）](../src/cafe_collection/assets/steamed-kueh-lapis.jpg) | 食べ物 | R |
| [アンクークエ](../src/cafe_collection/assets/ang-ku-kueh.jpg) | 食べ物 | N |

## セットと既存動作

セット「シンガポール、コピティアムのひと休み」は上記6品すべてで完成する。セットキーは `singapore-kopitiam-break`。

全6品を文化タグに、コピ・グーユーを珈琲タグに、食べ物4品を甘味タグに追加する。

既存669カードのキー・解説・分類・画像、既存76セット、所持データ、XP報酬、レアリティ別の基本排出率を維持する。追加したレアリティ内で各カードの重みは既存の配分式に従って再配分される。追加後は食べ物281品・飲み物394品、セット77種類。データベースのマイグレーションや認証情報の変更は不要。

## 食文化の確認資料

- コピ・グーユー: [シンガポール政府観光局のコピ注文ガイド](https://www.visitsingapore.com.cn/things-to-do/dining/local-food-and-drinks/order-coffee-like-a-local/)、[HDB Our Life Stories Issue 27](https://www.hdb.gov.sg/-/media/doc/CRG/LS_Issue27.pdf)。練乳入りの珈琲にバターを加える型を採用する。
- バンドン: [シンガポール政府観光局のローカル飲食紹介](https://www.visitsingapore.com/things-to-do/dining/local-food-and-drinks/)。ローズシロップとミルクのピンク色の飲み物で、苺ミルクとは区別する。
- パンダンシフォンケーキ: [シンガポール政府観光局の地元ブランド紹介](https://www.visitsingapore.com/things-to-do/shop/singapore-local-brands/)。パンダンとココナツミルクを使い、淡い緑の軽い生地を描く。
- オンデオンデ: [シンガポール政府公開資料のレシピ](https://file.go.gov.sg/csesep-dec25.pdf)。パンダンの餅生地にグラ・マラッカ（パームシュガー）を包み、削ったココナツをまぶす。断面の中身はチョコレートではなく糖蜜とする。
- クエ・ラピス: [SG101 Kueh 101](https://www.sg101.gov.sg/resources/archives/kueh101/)。蒸す型と焼く型を区別し、今回のカードはピンクと白の層を重ねた蒸し菓子とする。
- アンクークエ: [シンガポール国家遺産庁 Kueh](https://www.roots.gov.sg/ich-landing/ich/kueh)。赤い亀甲型の餅菓子。複数ある餡のうち緑豆餡の型を描く。

## 画像制作と同期

画像生成には内蔵の画像生成機能（built-in image_gen）を使用した。1品1枚、自然光の写真風、文字・ロゴ・人物・枠なし。コピのバター、バンドンのピンク、シフォンの気泡、オンデオンデの糖蜜、クエ・ラピスの蒸した層、アンクークエの型押しと緑豆餡を区別し、生成結果を目視確認した。

最終プロンプトと生成元ファイル名は [artwork-prompts-2026-10-02-singapore.json](artwork-prompts-2026-10-02-singapore.json) に記録した。保存先は上記カード画像リンク。sipsで既存と同じ768×768 JPEGに正規化し、原寸法・形式・ファイル対応をテストでも確認した。

共通画像2枚を含め677画像のマニフェストをlevel-botと同期し、Botの互換性確認、台帳の図鑑総数、公開サイトのカード別ページ情報も更新する。公開時は既存の件数・画像マニフェスト照合に合わせ、level-botと専用Botの対応版を揃える。

## ローカル検証結果

- level-bot: 最終版で `.venv/bin/pytest -q` が787件すべて成功。Ruff lint・format、Mypy（214ファイル）、Compose環境変数スコープ検査、frontendの `npm run tsc`・`npm run lint`・`API_URL=http://localhost:8000 npm run build` が成功。
- cafe-collection-bot: `uv sync --frozen --extra dev`、`uv run ruff check src scripts`、`uv run ruff format --check src scripts`、`uv run mypy src`、両Compose設定確認、環境変数スコープ検査、画像マニフェスト検査、`uv run pytest -q`（87件）が成功。
- chill-cafe-site: `npm ci`、`npm run format:check`、`npm run lint`、`npm run typecheck`、`npm run test:run`（16件）、`npm run build`、`node scripts/verify-pages-artifact.mjs`、`npm run build-storybook` が成功。最終説明文の同期後にformat・build・artifact検査を再実行。ページ情報210件・生成ルート213件、新6ページのタイトル・説明・画像URLを確認した。
- 3リポジトリの `git diff --check` が成功。HEAD対比で旧669カードの内容・分類・タグ、旧76セット、旧671画像のサイズ・SHA256、旧204ページ情報を保持。旧サイト生成物210ファイルのSHA256も保持。全677画像の実ファイルと両マニフェスト、新6品のカタログ・ページ情報・画像・プロンプトの対応を照合した。
- 新規テストは新6品の名前・レアリティ・分類・タグ・画像、セットの全6枚完成条件、内部/公開API、旧版との互換性拒否を検査。既存テストは総数・分類総数・タグ総数・交換数量上限とコンプリート境界を追加仕様に合わせて更新し、以前のケースも保持した。669枚所持は未完成となり、675枚で完成する。レアリティ全体の排出率とXP規則は不変で、Kブロートの基本排出率0.24%の既存アサーションも維持した。

合計890テストが成功。既存のaudioop非推奨警告、frontend/Storybookのビルド警告、サイト依存関係のaudit警告は今回の変更対象外。サイトREADMEの既存変更とBotの未追跡 `output/` は触れていない。コミット・プッシュ・本番反映は行っておらず、本番環境は未検証。
