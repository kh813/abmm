# ABMM (AI Background Music Maker) - プロジェクト雛形

現時点ではビルドパイプライン検証用の最小構成です。Phase 1 / Phase 2 の実処理は今後実装します。
詳細な仕様は `docs/abmm-spec.md`（別途配布）を参照してください。

## ローカルでの動作確認

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app/main.py
```

## ローカルで .app をビルドする

Apple Silicon Mac上で実行してください（Intel Macは非対応）。

```bash
source .venv/bin/activate
pyinstaller abmm.spec --noconfirm --clean
# 生成物: dist/ABMM.app

# 自己署名（ad-hoc）してGatekeeperの一部警告を軽減する場合
codesign --force --deep --sign - "dist/ABMM.app"
```

## GitHub Actionsでのビルド

`.github/workflows/build-macos.yml` が以下を自動実行します。

- `main`ブランチへのpush、`v*`タグのpush、Pull Request、手動実行(`workflow_dispatch`)をトリガーに実行
- `macos-14`ランナー（Apple Silicon / arm64ネイティブ）上で `pyinstaller abmm.spec` を実行し `.app` を生成
- ad-hocコードサイニングを実施
- `.app`をzip化してActionsのartifactとしてアップロード
- `v*`タグのpush時は、GitHub Releaseを自動作成しzipを添付

### 使い方
1. このリポジトリをGitHubにpush
2. `git tag v0.1.0 && git push origin v0.1.0` のようにタグをpushすると、自動でビルド＆リリースが作成される
3. 通常のpush/PRでは、Actionsの「Artifacts」からビルド済み`.app`（zip）をダウンロードして動作確認できる

### 今後の対応（未実装・将来課題）
- Apple Developer ID証明書によるコードサイニング・notarization（現状はad-hoc署名のみのため、配布先で
  Gatekeeperの警告が出ます。右クリック→「開く」で起動可能ですが、正式配布には署名/公証が必要です）
- アプリアイコン（`.icns`）の追加
- 自動アップデート機能（GitHub Releasesを参照してバージョンチェックする仕組み。仕様書14.3節を参照）
