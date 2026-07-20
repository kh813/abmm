# ABMM (AI Background Music Maker)

[![Build and Release macOS App](https://github.com/kh813/abmm/actions/workflows/build.yml/badge.svg)](https://github.com/kh813/abmm/actions/workflows/build.yml)
[![Latest Release](https://img.shields.io/github/v/release/kh813/abmm)](https://github.com/kh813/abmm/releases/latest)

**ABMM (AI Background Music Maker)** は、自然言語での雰囲気指定や各種パラメータ設定から、著作権フリーのインストゥルメンタル BGM を高速生成する Apple Silicon macOS 向けデスクトップアプリケーションです。

ローカル LLM (Ollama) による楽曲構成・コード進行の生成と、FluidSynth を用いたレンダリングにより、完全ローカル環境でプライバシーを保ちながら BGM を制作できます。

---

## 🌟 主な特徴

- 🎨 **自然言語プロンプト生成**: 「雨上がりの午後、少し切ないローファイジャズ」といった曖昧な指示から曲の構成・コード進行を自動作成。
- 🎛️ **詳細パラメータ調整**: 楽曲の長さ（1〜60分）、BPM、楽器構成、展開（セクション構成）を自由にカスタマイズ可能。
- 🔒 **完全ローカル動作**: Ollama (ローカル LLM) と FluidSynth を利用するため、外部クラウドへのデータ送信なし。
- 🎵 **著作権フリー & 多彩な書き出し**: YouTube 動画、Vlog、社内イベント、プレゼン資料などのバックグラウンドミュージックとして制限なく利用可能。WAV および MP3 形式で保存可能。
- ⚡ **CLIレスの自動セットアップサポート**:
  - **FluidSynth の自動探訪 & フォールバック**: システム (`/opt/homebrew/bin`, `PATH`) やユーザー領域 (`~/Library/Application Support/ABMM/bin`) から動的に検索。
  - **Ollama の自動起動アシスト**: Ollama 未起動時はアプリから自動起動を試み、未インストールの場合はワンクリックで入手ページをオープン。

---

## 📥 インストール手順

### 1. アプリのダウンロード
[GitHub Releases ページ](https://github.com/kh813/abmm/releases/latest) から最新の `ABMM-macos-arm64.zip` をダウンロードして解凍します。

### 2. アプリの配置と初回起動 (Gatekeeper 回避)
Apple の開発者証明書（公証）を取得していないため、初回起動時のみ以下の手順で起動します：

1. 展開された `ABMM.app` を `/Applications` (アプリケーション) フォルダ等に移動します。
2. `ABMM.app` を **右クリック (または Control + クリック) して「開く」** を選択します。
3. 「開発元を検証できません」というダイアログで **「開く」** をクリックします。
4. 次回以降はダブルクリックのみで起動できるようになります。

> [!NOTE]
> **ターミナルでの事前コマンド（Homebrew 等）の入力は不要です！**  
> 音声合成エンジン (FluidSynth) はアプリが自動検出・セットアップします。また、LLM エンジン (Ollama) が未起動・未インストールの場合は、アプリ画面上に表示される **「Ollamaを起動 / 入手」** ボタンからワンクリックで準備できます。

---

## 🚀 基本的な使い方

1. **ABMM の起動**
   - `ABMM.app` を起動します。
   - **Ollama の確認**: Ollama が未起動の場合は画面上に警告と「Ollamaを起動 / 入手」ボタンが表示されます。ボタンを押すと自動起動またはダウンロードページが開きます。
2. **楽曲の指示・パラメーター設定**
   - **プロンプト入力**: 欲しい BGM の雰囲気（例: 「落ち着いた作業用カフェBGM、アコースティックギター中心」）を入力します。
   - **詳細設定**: 演奏時間（分）、BPM、メイン楽器などを必要に応じて調整します。
3. **生成 & プレビュー**
   - 「生成」ボタンを押すと、AI がコード進行とメロディを組み立てます。
   - 画面上のプレイヤーで即座にプレビュー再生が可能です。
4. **書き出し**
   - 「WAV エクスポート」または「MP3 エクスポート」を選択し、任意のフォルダに保存します。

---

## 💻 開発者向けガイド

ソースコードから直接実行またはビルドする場合の手順です。

### 依存関係のセットアップ
```bash
# リポジトリのクローン
git clone https://github.com/kh813/abmm.git
cd abmm

# 仮想環境の作成とライブラリのインストール
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### アプリの実行
```bash
python3 app/main.py
```

### ローカルでの macOS 用ビルド (.app / .zip)
```bash
chmod +x build_macos.sh
./build_macos.sh
```
* ビルド生成物: `dist/ABMM.app` および `dist/ABMM-macos-arm64.zip`

---

## 🔍 トラブルシューティング

- **Ollama に接続できない / LLM エラーが発生する**
  - アプリ画面上の「Ollamaを起動 / 入手」ボタンを押して Ollama を起動するか、[ollama.com](https://ollama.com) から最新版をインストールしてください。
  - 推奨モデル（`qwen2.5:3b` や `qwen2.5-coder:7b` 等）が導入されているか確認してください。
- **音が出ない / レンダリング失敗**
  - FluidSynth バイナリは自動探索されます。Homebrew 環境がある場合は `brew install fluidsynth` または `~/Library/Application Support/ABMM/bin/` への配置もサポートされています。

---

## 📄 ライセンス

[MIT License](file:///Users/hiroshi/dev/abmm/LICENSE)
