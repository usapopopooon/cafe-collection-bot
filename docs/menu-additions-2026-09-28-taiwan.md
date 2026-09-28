# 台湾老街の甘いひと休み

2026-09-28。既存657種類に台湾で親しまれる6品を追加し、合計663種類。飲み物3種、食べ物3種。

既存の台湾茶12品やタピオカ系カードとの重なりを避け、果物のミルク、冬瓜の甘い飲み物、客家の擂茶、豆花、愛玉、鳳梨酥を選んだ。客家の食文化を台湾だけの起源とは断定しない。

| カード・保存画像 | 分類 | 表示レアリティ |
| --- | --- | --- |
| [夜市のパパイヤミルク（木瓜牛奶）](../src/cafe_collection/assets/night-market-papaya-milk.jpg) | 飲み物 | N |
| [老街の冬瓜茶](../src/cafe_collection/assets/old-street-winter-melon-tea.jpg) | 飲み物 | N |
| [客家の擂茶（レイチャ）](../src/cafe_collection/assets/hakka-lei-cha.jpg) | 飲み物 | R |
| [ピーナッツの豆花](../src/cafe_collection/assets/peanut-douhua.jpg) | 食べ物 | HN |
| [レモンの愛玉ゼリー](../src/cafe_collection/assets/lemon-aiyu-jelly.jpg) | 食べ物 | HN |
| [鳳梨酥（パイナップルケーキ）](../src/cafe_collection/assets/taiwan-pineapple-cake.jpg) | 食べ物 | HN |

## セットと既存動作

セット「台湾老街の甘いひと休み」は上記6品すべてで完成する。セットキーは `taiwan-old-street-sweet-break`。

全6品を文化タグに、擂茶だけを茶タグに、擂茶以外の5品を甘味タグに追加する。冬瓜茶は茶葉を使わないため茶タグに含めない。

既存657カードのキー・解説・分類・画像、既存74セット、所持データ、XP報酬、レアリティ別の基本排出率を維持する。追加したレアリティの個別排出率は既存の重み再配分に従って変わる。追加後は食べ物273品・飲み物390品、セット75種類。データベースのマイグレーションや認証情報の変更は不要。

## 食文化の確認資料

- パパイヤミルク・豆花・愛玉: [台湾観光署の特色小吃紹介](https://www.taiwan.net.tw/m1.aspx?sno=0000072)、[日本語版の台湾小吃紹介](https://jp.taiwan.net.tw/m1.aspx?sNo=0015555)。パパイヤと牛乳を合わせる飲料、豆乳のやわらかな甘味、愛玉の種子を水中でもみ出して作るゼリーを参照。豆花は今回、煮たピーナッツを添える型を選んだ。
- 冬瓜茶: [台湾教育部の台湾語辞典「冬瓜茶」](https://sutian.moe.edu.tw/zh-hant/su/1459/)、[教育部の地域文化紹介](https://itaiwan.moe.gov.tw/local_info.php?id=3657)。冬瓜と砂糖を煮て作る飲み物として扱い、茶葉入りの茶とは区別する。
- 擂茶: [台湾観光署の案内資料](https://www.taiwan.net.tw/att/travelcenter/7063.pdf)、[客家料理の紹介](https://www.taiwan.net.tw/m1.aspx?sno=0027003)。茶葉・ごま・落花生などをすりつぶし、お湯を加える客家の飲み物を参照。具材や配合が一つに固定されているとはしない。
- 愛玉のレモン添え: [台湾農業部の食農教育資料](https://fae.moa.gov.tw/files/topics/1146/A02_2.pdf)。レモンと合わせる涼味として描写し、ゼラチン製のプリンや寒天の角切りとして描かない。
- 鳳梨酥: [台湾観光署のおみやげ紹介](https://jp.taiwan.net.tw/m1.aspx?page=1&sNo=0003027)。ほろりとした生地でパイナップル餡を包む焼き菓子として描く。冬瓜を配合する型もあるが、今回のカードはパイナップルの繊維感が見える型を採用した。

## 画像制作と同期

画像生成スキルに従い、内蔵の画像生成機能（built-in image_gen）で1品1枚ずつ新規生成した。自然光の写真風表現で、乳飲料の不透明さ、冬瓜茶の透明感、擂茶のすりつぶした質感、豆花の薄いすくい跡、愛玉の柔らかな透明感、鳳梨酥のほろりとした皮と果実餡を区別した。人物・文字・枠・ロゴは入れない。生成結果を目視確認し、sipsで既存と同じ768×768 JPEGへ正規化した。

保存先は上記6品の画像リンク。最終プロンプトと生成元ファイル名は [artwork-prompts-2026-09-28-taiwan.json](artwork-prompts-2026-09-28-taiwan.json) に記録する。

共通画像2枚を含め665画像のマニフェストをlevel-botと一致させる。Discord Botの既存のカード数・画像数互換性確認、台帳の図鑑総数、公開サイトのカード別ページ情報も更新する。既存の起動判定や認証方式は追加変更しない。

## ローカル検証結果

- level-bot: CI相当の依存整合性確認、`ruff check`、`ruff format --check`、`mypy src`、`python scripts/check_compose_env_scope.py` が成功。`pytest -q` 相当の全775テストが成功（画像同期待ちの2テストを除いた773件と、同期後の2件を分割実行）。フロント側の `npm ci`、`npm run tsc`、`npm run lint`、`API_URL=http://localhost:8000 npm run build` も成功。
- cafe-collection-bot: `uv sync --frozen --extra dev`、Ruff lint/format、mypy、両Compose設定確認、環境変数のスコープ検査、画像マニフェスト検査、`pytest -q`（81件）が成功。
- chill-cafe-site: `npm ci`、`npm run format:check`、`npm run lint`、`npm run typecheck`、`npm run test:run`（16件）、`npm run build`、`node scripts/verify-pages-artifact.mjs`、`npm run build-storybook` が成功。ページ情報198件・生成ルート201件、新6ページのタイトル・説明・画像URLが一致。
- 3リポジトリの `git diff --check` が成功。旧657カード・74セットの意味内容、旧659画像の実ファイルを保持。全665画像のサイズ・SHA256、2リポジトリのマニフェスト、新6品のカード・セット・ページ・プロンプトの対応を確認。
- 新規テストは新6品の分類・画像・内部/公開API・セット完成条件・旧版との互換性拒否を追加。既存テストの変更は、追加に伴う総数・分類件数・上限・完成境界の更新に限る。

合計872テストが成功。既存の非推奨警告、サイト依存パッケージの監査警告とStorybookのサイズ警告は今回の対象外。サイトREADMEの既存変更とBotの未追跡 `output/` は触れていない。この制作段階ではコミット・プッシュ・本番反映は行っておらず、本番環境は未検証。
