# ABMM (AI Background Music Maker)

ABMM は、ローカル LLM (Ollama) および Apple Silicon 向けの高速な音声合成エンジンを組み合わせた、macOS 向けデスクトップ BGM 自動生成アプリケーションです。

詳細な仕様は [abmm-spec.md](file:///Users/hiroshi/dev/abmm/abmm-spec.md) を参照してください。

---

## 💻 開発環境のセットアップと動作確認

### 1. 依存バイナリのインストール
macOS 上で SoundFont プレビュー再生を行うため、`fluidsynth` を Homebrew 経由でインストールします。
```bash
brew install fluidsynth
```

### 2. 仮想環境の作成と起動
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. アプリケーションの実行
Ollama (ローカル LLM) が起動していることを確認した上で、以下を実行します。
```bash
python3 app/main.py
```

---

## 🛠️ ローカルでのビルド手順 (.app)

Apple Silicon Mac 上で実行してください。ビルド、アドホック署名、ZIP アーカイブ作成を一元化するスクリプトが用意されています。

```bash
chmod +x build_macos.sh
./build_macos.sh
```
*   **ビルド生成物**: `dist/ABMM.app` および `dist/ABMM-macos-arm64.zip`

---

## 🚀 配布とインストール（Gatekeeper 回避手順）

配布された `ABMM-macos-arm64.zip` からアプリを展開して起動する際、Apple の正式な公証（Notarization）を経ていないため、macOS のセキュリティ（Gatekeeper）によるブロック警告が表示されます。

### 初回起動時の実行手順
1.  ダウンロードした ZIP を展開し、`ABMM.app` を `/Applications` (アプリケーション) フォルダ等に移動します。
2.  `ABMM.app` を**右クリック (または Control + クリック) し、「開く」を選択**します。
3.  確認ダイアログが表示されますので、**「開く」をクリック**して実行します。
4.  これにより、次回以降はダブルクリックのみで安全に起動可能になります。

---

## 🔍 トラブルシューティング

### 1. 起動直後に「Python API がロードされていません」などの警告が出る
*   pywebview によるウィンドウ初期化タイミングのズレ、または Python ランタイムエラーが発生している可能性があります。コンソールログを確認してください。

### 2. プレビュー再生時に音が出ない
*   システムに `fluidsynth` バイナリがインストールされているか確認してください (`which fluidsynth`)。また、MuseScore などの標準 SoundFont が `assets/soundfonts/` 内に正しく自動ダウンロードされているか確認してください。

### 3. Ollama との接続エラー
*   ローカル環境で Ollama サーバーが起動し、ポート `11434` をリッスンしているか確認してください。
*   モデル（デフォルト: `qwen2.5-coder:7b` または `qwen2.5:3b` 等）がインストールされているか確認してください (`ollama list`）。

---

## 🛠️ CI/CD パイプライン (GitHub Actions)

`.github/workflows/build.yml` にて自動ビルドパイプラインが定義されています。

*   **トリガー**: `v*` 形式のタグがプッシュされた際、または手動トリガー (`workflow_dispatch`) で動作します。
*   **処理フロー**: macOS ランナーのセットアップ $\to$ `fluidsynth` の Brew インストール $\to$ `pytest` によるテスト実行 $\to$ PyInstaller ビルド $\to$ コード署名 $\to$ GitHub Releases への ZIP 自動デプロイ。
