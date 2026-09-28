# 草原とタイガの喫茶メニュー追加

2026-09-28。既存651種類に6種類を追加し、合計657種類。飲み物1種、食べ物5種。

モンゴル、シベリア、サハ、エヴェンキの食文化を「草原とタイガの喫茶卓」としてつなぐ。ロシア東部の多様な文化を一括りにせず、各カードの説明に関連する地域・民族名を明記する。サハとモンゴルをツングース系として扱わない。

| カード | 地域・文化 | 分類 | レアリティ |
| --- | --- | --- | --- |
| [草原のウルム](../src/cafe_collection/assets/steppe-urum.jpg) | モンゴル | 食べ物 | HN |
| [天日干しのアーロール](../src/cafe_collection/assets/sun-dried-aaruul.jpg) | モンゴル | 食べ物 | N |
| [チェリョームハのケーキ](../src/cafe_collection/assets/bird-cherry-cake.jpg) | シベリア | 食べ物 | R |
| [ベリーのケルチェフ](../src/cafe_collection/assets/berry-kerchekh.jpg) | サハ | 食べ物 | R |
| [焚き火のコロボ](../src/cafe_collection/assets/ember-kolobo.jpg) | エヴェンキ | 食べ物 | N |
| [タイガのベリーミルク](../src/cafe_collection/assets/taiga-berry-milk.jpg) | エヴェンキ | 飲み物 | HN |

## セットと既存動作

「草原とタイガの喫茶卓」は上記6品で完成する。セットキーは `steppe-taiga-cafe-table`。

既存651カードのキー・解説・分類・画像、既存73セット、所持データ、XP報酬、レアリティ別の基本排出率を維持する。追加したレアリティの個別排出率は既存の重み再配分に従って変わる。追加後は食べ物270品・飲み物387品、セット74種類。データベースのマイグレーションや認証情報の変更は不要。

塩入り乳茶と揚げ菓子は既存のシルチョイ・ピシュメに近いため今回は見送り、乳皮・乾燥乳・果実入りケーキ・泡立てたクリーム・無発酵パン・ベリー入り乳飲料の違いを優先した。

## 食文化の確認資料

- ウルムとアーロール: [オーストラリア国立大学モンゴル研究所「White Foods」](https://mongoliainstitute.anu.edu.au/content-centre/article/series/white-foods)。ウルムは乳皮クリーム、アーロールは乾燥した乳の固形物。砂糖を加える型もあるが、今回のカードでは添加を前提としない。
- チェリョームハのケーキ: [Open Kitchenのシベリア風ケーキ](https://openkitchen.eda.yandex/article/dishes/recipes/sibirskiy-cheryomukhoviy-tort)。挽いたチェリョームハの実を生地に使い、サワークリームを重ねる型を採用する。チョコレートケーキとして描かない。
- ケルチェフ: [サハの食文化紹介](https://food.ru/articles/10336-chto-edyat-v-yakutii)、[GoRuのケルチェフ紹介](https://goru.travel/place/kerchekh)。乳製品を泡立て、ベリーを添えるデザート。ウルムの乳皮とは異なる質感で描く。
- コロボ: [北方先住民族の民族文化アトラス・エヴェンキの物質文化](https://atlaskmns.ru/page/ru/people_evenki_matcult.html)。燃え尽きた焚き火の灰で焼く無発酵パン。
- ベリー入り乳飲料: [バイカル地域先住民族文化センターのエヴェンキ食文化資料](https://etno.pribaikal.ru/2025/12/01/tradicionaya-kuknya-evenkov-2025/)。トナカイの乳と季節の森のベリーを混ぜる食文化を参照。「タイガのベリーミルク」は説明的なカード名であり、伝統料理の固有名を新たに作ったものではない。健康効果や民族全体で統一された製法を断定しない。

## 画像制作と同期

画像生成スキルに従い、built-in image_genで1品1枚ずつ新規生成。自然光の写真風表現とし、食品の質感・器・分類を見分けられる構図を採用した。民族衣装や紋様を創作せず、人物・文字・枠・ロゴを入れない。sipsで既存と同じ768×768 JPEGへ正規化した。

画像6枚は上記リンク先の `src/cafe_collection/assets/` に保存。最終プロンプトと生成元ファイル名は [artwork-prompts-2026-09-28-steppe-taiga.json](artwork-prompts-2026-09-28-steppe-taiga.json) に記録する。

共通画像2枚を含め659画像のマニフェストをlevel-botと一致させる。Discord Botの既存のカード数・画像数互換性確認、台帳の図鑑総数、公開サイトのカード別ページ情報も更新する。既存の起動判定や認証方式を追加変更しない。
