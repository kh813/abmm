# ABMM アプリアイコン

## 同梱ファイル
- `AppIcon.icns` — macOSアプリ用アイコン（複数解像度を内包済み。PyInstaller/py2appにそのまま渡せます）
- `AppIcon.iconset/` — `iconutil`で.icnsを作り直したい場合用の標準命名PNG一式
- `icon_1024.png` — 1024x1024のソースPNG（再編集・別用途への流用に）
- `icon_preview_sheet.png` — 複数サイズ・明背景/暗背景での見え方プレビュー

## デザイン意図
- 背景: インディゴ→バイオレットの対角グラデーション（AI/テクノロジーを想起させつつ、音楽アプリらしい深みのある色)
- 中央: 山形に配置したサウンドウェーブ（イコライザー）バー。BGM生成アプリであることを一目で伝える
- 右上: 小さな4方向スパークル。「AIが生成する」ことを示すさりげないアクセント
- 形状: macOS標準の角丸スクエア（squircle）でOS標準アイコンとなじむようにしています

## PyInstallerでの使い方
`abmm.spec` の `BUNDLE()` 内、`icon=None` となっている箇所を以下のように変更してください。

```python
app = BUNDLE(
    coll,
    name="ABMM.app",
    icon="assets/AppIcon.icns",   # ← ここを変更
    bundle_identifier="com.abmm.app",
    ...
)
```

`AppIcon.icns` はリポジトリの `assets/` フォルダ等に配置してください。

## .iconsetから.icnsを作り直したい場合（Mac上で）
```bash
iconutil -c icns AppIcon.iconset -o AppIcon.icns
```

## 気に入らない場合
色味（インディゴ/バイオレット以外）や、モチーフ（サウンドウェーブ以外、例えば音符・散歩道など）を
変えたバリエーションもすぐ作れるので、方向性の希望があれば教えてください。
