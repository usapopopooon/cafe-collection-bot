# 香港・マカオ、港町の午後

2026-10-02。既存663種類に香港・マカオで親しまれる6品を追加し、合計669種類。飲み物2種、食べ物4種。

既存の香港式ミルクティーとは別に、コーヒーを混ぜる鴛鴦茶とレモン入りの紅茶を選んだ。菠蘿油は台湾の鳳梨酥と異なり、パイナップルの果実や餡を使わないバター入りのパンとして扱う。マカオ側はポルトガル系の二つのデザートと伝統的な杏仁餅を組み合わせ、特定地域だけの発祥とは断定しない。

| カード・保存画像 | 分類 | 表示レアリティ |
| --- | --- | --- |
| [鴛鴦茶（ユンヨンチャー）](../src/cafe_collection/assets/hong-kong-yuenyeung.jpg) | 飲み物 | HN |
| [凍檸茶（香港式アイスレモンティー）](../src/cafe_collection/assets/hong-kong-iced-lemon-tea.jpg) | 飲み物 | N |
| [菠蘿油（バター入りパイナップルパン）](../src/cafe_collection/assets/pineapple-bun-with-butter.jpg) | 食べ物 | HN |
| [マカオ式エッグタルト（葡撻）](../src/cafe_collection/assets/macao-egg-tart.jpg) | 食べ物 | HN |
| [セラドゥーラ](../src/cafe_collection/assets/macao-serradura.jpg) | 食べ物 | R |
| [杏仁餅（アーモンドクッキー）](../src/cafe_collection/assets/macao-almond-cookie.jpg) | 食べ物 | N |

## セットと既存動作

セット「香港・マカオ、港町の午後」は上記6品すべてで完成する。セットキーは `hong-kong-macao-harbour-afternoon`。

全6品を文化タグに、鴛鴦茶だけを珈琲タグに、飲み物2品を茶タグに、食べ物4品を甘味タグに追加する。

既存663カードのキー・解説・分類・画像、既存75セット、所持データ、XP報酬、レアリティ別の基本排出率を維持する。追加したレアリティの個別排出率は既存の重み再配分に従って変わる。追加後は食べ物277品・飲み物392品、セット76種類。データベースのマイグレーションや認証情報の変更は不要。

Nのカード数は270から272へ増える。既存の配分式では、合計6,500の配分値をカード数で割り、余りを先頭から配った後で15倍する。`k-pan` の重みは375から360へ変わり、全体150,000に対する基本排出率は0.25%から0.24%になる。公開APIの既存テスト2か所はこの結果に合わせて更新するが、配分処理とN全体の65%は変更しない。

## 食文化の確認資料

- 鴛鴦茶: [香港政府観光局「蘭芳園」](https://www.discoverhongkong.com/eng/place-to-go/travel.guide-lan-fong-yuen.html)、[香港無形文化遺産リスト（5.37）](https://www.icho.hk/documents/Intangible-Cultural-Heritage-Inventory/2024/ich_inventory_2024_en.pdf)。紅茶・コーヒー・ミルクを合わせる飲み物として扱う。
- 凍檸茶: [PMQによる香港のレモンティー取材](https://www.pmq.org.hk/leisureculture/lemon-tea-matters/?lang=en)、[Hong Kong Cookeryのレシピ](https://www.thehongkongcookery.com/2014/06/hong-kong-style-iced-lemon-tea.html)。濃い紅茶、輪切りのレモン、氷、レモンを押すスプーンを参照する。
- 菠蘿油: [香港政府観光局「金華冰廳」](https://www.discoverhongkong.com/eng/place-to-go/travel.guide-kam-wah-cafe.html)、[香港無形文化遺産リスト（5.34）](https://www.icho.hk/documents/Intangible-Cultural-Heritage-Inventory/2024/ich_inventory_2024_en.pdf)。甘い皮の菠蘿包にバターを挟む型を採用し、果物入りのパンとして描かない。
- エッグタルト・セラドゥーラ: [マカオ政府観光局のマカオ・ポルトガル料理紹介](https://www.macaotourism.gov.mo/en/dining/taste-of-macao/macanese-and-portuguese-dishes)。エッグタルトはパイ生地と焼き目のある卵カスタード、セラドゥーラはクリームと砕いたビスケットの層として区別する。
- 杏仁餅: [マカオ政府観光局のローカルフード紹介](https://www.macaotourism.gov.mo/en/dining/taste-of-macao/local-food)、[Macao Magazineの伝統菓子取材](https://macaomagazine.net/preserving-macaos-identity/)。アーモンドや緑豆粉を使い、型に詰めて成形するほろほろの焼き菓子を参照した。配合の種類は複数あり、今回のカードは特定の食事制限への適合をうたわない。

## 画像制作と同期

画像生成スキルに従い、内蔵の画像生成機能（built-in image_gen）で1品1枚ずつ新規生成した。自然光の写真風表現で、鴛鴦茶の均一なミルク色、凍檸茶の透明な紅茶と氷、菠蘿油のひび割れた皮と厚切りバター、タルトのパイ層と焼き目、セラドゥーラの淡いクリームとビスケット層、杏仁餅の型押しと崩れる質感を区別した。人物・文字・枠・ロゴは入れない。生成結果を目視確認し、sipsで既存と同じ768×768 JPEGへ正規化した。

保存先は上記6品の画像リンク。最終プロンプトと生成元ファイル名は [artwork-prompts-2026-10-02-hong-kong-macao.json](artwork-prompts-2026-10-02-hong-kong-macao.json) に記録する。

共通画像2枚を含め671画像のマニフェストをlevel-botと一致させる。Discord Botの既存のカード数・画像数互換性確認、台帳の図鑑総数、公開サイトのカード別ページ情報も更新する。既存の起動判定や認証方式は追加変更しない。

## ローカル検証結果

- level-bot: CI相当の依存整合性確認、`ruff check src scripts/check_compose_env_scope.py`、`ruff format --check src scripts/check_compose_env_scope.py`、`mypy src`、`python scripts/check_compose_env_scope.py` が成功。`pytest -q` 相当の全781テストが成功（画像依存2件を除く779件と、画像同期後の2件を分割実行）。フロント側の `npm ci`、`npm run tsc`、`npm run lint`、`API_URL=http://localhost:8000 npm run build` も成功。
- cafe-collection-bot: `uv sync --frozen --extra dev`、`ruff check src scripts`、`ruff format --check src scripts`、`mypy src`、両Compose設定確認、環境変数のスコープ検査、画像マニフェスト検査、`pytest -q`（84件）が成功。
- chill-cafe-site: `npm ci`、`npm run format:check`、`npm run lint`、`npm run typecheck`、`npm run test:run`（16件）、`npm run build`、`node scripts/verify-pages-artifact.mjs`、`npm run build-storybook` が成功。ページ情報204件・生成ルート207件、新6ページのタイトル・説明・画像URLが一致。
- 3リポジトリの `git diff --check` が成功。HEAD対比で旧663カードの内容・分類・タグ、旧75セット、旧665画像、旧198件のサイトページ情報を保持。全671画像の実ファイルのサイズ・SHA256、2リポジトリのマニフェスト、新6品のカード・セット・ページ・プロンプトの対応を確認。
- 新規テストは新6品の分類・画像・内部/公開API・セット完成条件・旧版との互換性拒否を追加。既存テストの変更は、追加に伴う総数・分類件数・数量上限・完成境界と、上述の個別排出率の更新に限る。既存テストの削除や検査の弱体化は行っていない。

合計881テストが成功。既存の非推奨警告は今回の対象外。サイトREADMEの既存変更とBotの未追跡 `output/` は触れていない。この制作段階ではコミット・プッシュ・本番反映は行っておらず、本番環境は未検証。将来の公開時は、既存の件数・画像マニフェスト照合に合わせ、level-botと専用Botの対応版を揃える必要がある。
