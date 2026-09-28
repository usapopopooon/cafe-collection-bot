# 中央アジアの喫茶メニュー追加

2026-09-28。既存645種類に6種類を追加し、合計651種類。飲み物3種、食べ物3種。

中央アジア五か国を「草原とオアシスの喫茶卓」としてつなぐ。国名は代表的な関連地域を示し、近隣国にも共有される食文化を一国だけのものとは扱わない。

| カード | 国 | 分類 | レアリティ |
| --- | --- | --- | --- |
| [香ばしいジェント](../src/cafe_collection/assets/toasted-millet-zhent.jpg) | カザフスタン | 食べ物 | HN |
| [街角のマクスム](../src/cafe_collection/assets/street-maksym.jpg) | キルギス | 飲み物 | HN |
| [ナヴァト添えの緑茶](../src/cafe_collection/assets/navat-green-tea.jpg) | ウズベキスタン | 飲み物 | HN |
| [窯焼きサムサ](../src/cafe_collection/assets/tandoor-samsa.jpg) | ウズベキスタン | 食べ物 | N |
| [パミールのシルチョイ](../src/cafe_collection/assets/pamir-shirchoy.jpg) | タジキスタン | 飲み物 | R |
| [祝宴のピシュメ](../src/cafe_collection/assets/festive-pishme.jpg) | トルクメニスタン | 食べ物 | N |

## セットと既存動作

「草原とオアシスの喫茶卓」は上記6品で完成する。セットキーは `steppe-oasis-cafe-table`。

既存カードのキー・解説・分類、既存72セット、所持データ、XP報酬、レアリティ別の基本排出率を維持する。追加したレアリティの個別排出率は既存の重み再配分に従って変わる。図鑑は651品、食べ物265品・飲み物386品、セット73種類になる。データベースのマイグレーションは不要。

## 食文化の確認資料

- ジェント: [アスタナ観光局のガストロノミーガイド](https://www.visitastana.kz/public/file/gastro-guide-en.pdf)。煎ったキビ・バター・砂糖を使う茶菓子。
- マクスム: [UNESCOの伝統製法紹介](https://ich.unesco.org/en/RL/traditional-knowledge-and-cultural-contexts-of-making-maksym-a-traditional-kyrgyz-beverage-02123)。穀物の発酵飲料として記載し、健康効果やアルコールゼロを断定しない。
- ナヴァトとお茶: [ウズベキスタン政府の料理紹介](https://gov.uz/en/pages/national_foods)、[現地の菓子紹介](https://www.visituzbekistan.co/articles/sweettreasures)。ナヴァトは飲料名ではなく添える結晶砂糖。
- サムサ: [ウズベキスタン観光局](https://uzbekistan.travel/en/o/uzbek-samsa/)。今回はタンドールで焼く肉入りの型。
- シルチョイ: [UNESCO-ICHCAP Traditional Food](https://archive.unesco-ichcap.org/kor/ek/sub2017_6/pdf_down/6.%20TRADITIONAL%20FOOD/0.%20Traditional%20food.pdf)。乳・茶・塩とバターの朝食。既存のチベットのバター茶とは別カードとしてパミールの食卓を描く。
- ピシュメ: [トルクメニスタン国立博物館の祝祭紹介](https://www.turkmenistan.gov.tm/en/post/92969/state-museum-turkmenistan-has-launched-exhibition-movement-new-day)、[料理紹介](https://www.advantour.com/rus/turkmenistan/food/sweets.htm)。小さな揚げ菓子を祝いの茶卓に置く。

## 画像制作と同期

built-in image_genで1品1枚ずつ新規生成。自然光の写真風表現で食材と器を見分けられるようにし、文字・枠・ロゴは入れない。sipsで既存と同じ768×768 JPEGへ正規化する。プロンプトと生成元は [artwork-prompts-2026-09-28.json](artwork-prompts-2026-09-28.json) に記録する。

画像は `src/cafe_collection/assets/` に保存し、共通画像2枚を含め653画像のマニフェストをlevel-botと一致させる。Discord Botの互換性確認、台帳の図鑑総数、公開サイトのカード別ページ情報も更新する。
