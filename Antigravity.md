# AI Background Music Maker (ABMM) 開発ロードマップ & ToDo リスト

## 開発方針・プロセス

本プロジェクトの開発は、以下のプロセスを厳格に遵守して進めます。

1. **フェーズ毎の進行**: 各フェーズのすべてのタスクを確実に完了してから次のフェーズへ進みます。
2. **テストコードの作成**: 各フェーズの実装が完了したら、対象機能に対応するユニットテストまたは統合テストコードを作成します。
3. **ビルド＆テスト検証**: ビルドとテストコードを実行し、警告やエラーがないことを確認します。
4. **エラー修正**: エラーが検出された場合は、原因を特定して修正し、再度テストを実行します。
5. **Gitコミット**: すべてのテストに合格し、エラーがないことを確認した上で Git コミットを行い、次のフェーズに進みます。

---

## 実装 ToDo リスト

### Phase 1: MIDIスキーマ定義とMIDIファイル変換 (Phase A - MVPの一部)
- [x] 1.1 MIDI JSONスキーマの設計とデータモデルクラスの実装 ([midi_schema.py](file:///Users/hiroshi/dev/abmm/app/composer/midi_schema.py))
- [x] 1.2 `pretty_midi` / `mido` などの必要なMIDIライブラリを `requirements.txt` に追加し、インストール
- [x] 1.3 JSONデータから標準MIDIファイル(.mid)バイナリへの変換ロジックを実装 ([midi_converter.py](file:///Users/hiroshi/dev/abmm/app/composer/midi_converter.py) の `json_to_midi`)
- [x] 1.4 標準MIDIファイル(.mid)からJSONデータへの逆変換ロジックを実装 ([midi_converter.py](file:///Users/hiroshi/dev/abmm/app/composer/midi_converter.py) の `midi_to_json`)
- [x] 1.5 音符配置の16分音符ステップグリッド変換ユーティリティ関数の実装
- [x] 1.6 Phase 1 の機能（JSON⇔MIDI変換）に対するテストコードを作成 (`tests/test_midi_converter.py`)
- [x] 1.7 ビルドの実行およびテストを実行し、エラーがないことを確認する
- [x] 1.8 エラーがあれば修正し、git commit を実行する

### Phase 2: Ollama連携とLLMによるMIDI JSON生成 (Phase A - MVPの一部)
- [ ] 2.1 Ollama APIクライアント共通モジュールを実装 ([llm_client.py](file:///Users/hiroshi/dev/abmm/app/api/llm_client.py))
- [ ] 2.2 MIDI生成のためのFew-shotプロンプトの基礎テンプレートを作成 ([prompt_builder.py](file:///Users/hiroshi/dev/abmm/app/composer/prompt_builder.py))
- [ ] 2.3 自然言語の指示からスキーマ準拠 of MIDI JSONを生成するロジックを実装 ([prompt_builder.py](file:///Users/hiroshi/dev/abmm/app/composer/prompt_builder.py) の `generate_midi_json`)
- [ ] 2.4 生成されたJSONに対するスキーマバリデーション（Pydantic等）を実装
- [ ] 2.5 スキーマエラー・JSONパースエラー発生時の自動リトライ・プロンプト補正ロジックを実装
- [ ] 2.6 パース失敗が続いた場合のフォールバック用デフォルトMIDI（4小節ループ）生成ロジックを実装
- [ ] 2.7 Phase 2 の機能（Ollama連携・パース・リトライ）に対するテストコードを作成 (`tests/test_llm_client.py`)
- [ ] 2.8 ビルドの実行およびテストを実行し、エラーがないことを確認する
- [ ] 2.9 エラーがあれば修正し、git commit を実行する

### Phase 3: FluidSynthによるプレビュー再生とUI基礎 (Phase A - MVPの完結)
- [ ] 3.1 `pyfluidsynth` を `requirements.txt` に追加し、インストール。Mac環境での動作・SoundFont配置を確認
- [ ] 3.2 MIDIファイル/JSONをSoundFontで即座に音声化(WAV/バッファ)するプレビュー再生エンジンを実装 ([renderer_lite.py](file:///Users/hiroshi/dev/abmm/app/render/renderer_lite.py))
- [ ] 3.3 `pywebview` から呼び出すPythonバックエンドAPI / ハンドラーモジュールを実装 ([handlers.py](file:///Users/hiroshi/dev/abmm/app/api/handlers.py))
- [ ] 3.4 フロントエンドUIの基礎レイアウトを作成（自然言語入力欄、Phase 1 作曲実行ボタン、再生ボタン） ([index.html](file:///Users/hiroshi/dev/abmm/frontend/index.html), [app.js](file:///Users/hiroshi/dev/abmm/frontend/app.js))
- [ ] 3.5 `pywebview` でのPython側APIとJavaScript間のブリッジ通信・イベントハンドリングの設定
- [ ] 3.6 UIからの作曲実行 → MIDI生成 → FluidSynthによるプレビュー再生の結合テストコード・シナリオを作成 (`tests/test_integration_mvp.py`)
- [ ] 3.7 ビルドの実行およびテストを実行し、エラーがないことを確認する
- [ ] 3.8 エラーがあれば修正し、git commit を実行する

### Phase 4: パラメータ統合とスライダー制御 (Phase B - 自然言語＋スライダー本実装)
- [ ] 4.1 スライダー値（テンポ、明るさ、エネルギー、密度、空間感、各楽器の比率等）のデータモデルおよびAPIパラメータ仕様を定義
- [ ] 4.2 スライダー値と自然言語指示を融合してLLMプロンプトを組み立てるロジックの強化 ([prompt_builder.py](file:///Users/hiroshi/dev/abmm/app/composer/prompt_builder.py))
- [ ] 4.3 テンポやキー情報をMIDIメタデータおよび音符生成ルール（スケール制限等）に反映するロジックの実装
- [ ] 4.4 フロントエンドUIに各種スライダーおよびコントロール群を追加 ([index.html](file:///Users/hiroshi/dev/abmm/frontend/index.html), [style.css](file:///Users/hiroshi/dev/abmm/frontend/style.css), [app.js](file:///Users/hiroshi/dev/abmm/frontend/app.js))
- [ ] 4.5 スライダー変更時のリアルタイム・サブミット時のパラメータ送信処理の実装
- [ ] 4.6 各種パラメータ（テンポ・キー等）がプロンプトおよび生成MIDIに正しく反映されるかを検証するテストコードを作成 (`tests/test_parameters.py`)
- [ ] 4.7 ビルドの実行およびテストを実行し、エラーがないことを確認する
- [ ] 4.8 エラーがあれば修正し、git commit を実行する

### Phase 5: ハードウェア検出とレンダラー抽象化 (Phase C - レンダリングフェーズ軽量版)
- [ ] 5.1 ハードウェア情報検出モジュールを実装し、Apple Siliconの世代・メモリ容量を取得 ([hardware_detect.py](file:///Users/hiroshi/dev/abmm/app/render/hardware_detect.py))
- [ ] 5.2 検出したスペックに基づき「動作可能モデルティアの判定」および「レンダリング可能な曲の長さ上限」を算出するロジックを実装
- [ ] 5.3 フロントエンドUI側で「曲の長さ」スライダー可動域および警告表示の動的制御を実装
- [ ] 5.4 レンダラー共通インターフェースクラスを設計・定義 ([renderer_base.py](file:///Users/hiroshi/dev/abmm/app/render/renderer_base.py))
- [ ] 5.5 `renderer_lite` (FluidSynth) を `renderer_base` インターフェースに適合するようにリファクタリング
- [ ] 5.6 スペック判定およびレンダラーの抽象化インターフェース動作を確認するテストコードを作成 (`tests/test_hardware_and_base.py`)
- [ ] 5.7 ビルドの実行およびテストを実行し、エラーがないことを確認する
- [ ] 5.8 エラーがあれば修正し、git commit を実行する

### Phase 6: ニューラルレンダラーとプレビューレンダリング (Phase D - レンダリングフェーズ ニューラルモデル)
- [ ] 6.1 音声生成用ニューラルモデル（MLX等）を実行するための関連ライブラリを `requirements.txt` に追加し、インストール
- [ ] 6.2 `renderer_neural` を実装し、ニューラルモデルによるMIDIから音声波形へのレンダリング推論ロジックを実装 ([renderer_neural.py](file:///Users/hiroshi/dev/abmm/app/render/renderer_neural.py))
- [ ] 6.3 モデルのダウンロード・キャッシュ管理・プレビュー用/本番用の切替ロジックを実装 ([model_manager.py](file:///Users/hiroshi/dev/abmm/app/render/model_manager.py))
- [ ] 6.4 本番書き出し前の「数十秒プレビューレンダリング」機能の実装
- [ ] 6.5 プレビュー用モデルと本番用モデルの個別設定および品質パラメータの調整ロジックの実装
- [ ] 6.6 レンダリング処理の非同期実行（バックグラウンドスレッド/タスク）およびプログレスバー用の進捗通知API・UI実装
- [ ] 6.7 レンダリング処理の安全な「キャンセル」機能の実装（UI・スレッド処理の連動）
- [ ] 6.8 ニューラルレンダラー、モデルマネージャー、およびキャンセル処理に対するテストコードを作成 (`tests/test_neural_renderer.py`)
- [ ] 6.9 ビルドの実行およびテストを実行し、エラーがないことを確認する
- [ ] 6.10 エラーがあれば修正し、git commit を実行する

### Phase 7: 長尺書き出しとポストプロセス (Phase E - 仕上げその1)
- [ ] 7.1 指定された長尺（最大60分）に合わせたMIDIセクションの追加生成または自動ループ化ロジックを実装 ([loop_export.py](file:///Users/hiroshi/dev/abmm/app/postprocess/loop_export.py))
- [ ] 7.2 レンダリングされた音声データを `pydub` や `soundfile` を用いて、クロスフェードを伴いながらループ結合するロジックの実装
- [ ] 7.3 生成した音声の書き出し機能（WAVフォーマットおよびMP3フォーマットへのエンコード）の実装
- [ ] 7.4 ラウドネス基準（LUFS等）に基づく音量正規化（音量レベルの一致）ロジックを実装
- [ ] 7.5 曲の開始・終了位置への自動フェードイン・フェードアウト処理（時間調整可能）を実装
- [ ] 7.6 ループ処理・フォーマット変換・正規化およびフェード処理に対するテストコードを作成 (`tests/test_postprocess.py`)
- [ ] 7.7 ビルドの実行およびテストを実行し、エラーがないことを確認する
- [ ] 7.8 エラーがあれば修正し、git commit を実行する

### Phase 8: プリセット管理とUI/UXの最終磨き上げ (Phase E - 仕上げその2)
- [ ] 8.1 プリセット保存/読込ロジックの実装（MIDIファイルとメタ情報JSONの関連付け保存） ([preset_manager.py](file:///Users/hiroshi/dev/abmm/app/presets/preset_manager.py))
- [ ] 8.2 フロントエンドUIにプリセット保存・読込用コントロールおよび一覧表示機能の追加
- [ ] 8.3 プリセット読み込み時にPhase 1をスキップして直接Phase 2を呼び出すパスの実装
- [ ] 8.4 フロントエンドUIのレスポンシブデザインおよび美的デザイン（CSS/JS）のブラッシュアップ（Antigravity Webアプリ開発の設計美学に従う）
- [ ] 8.5 アプリケーション全体のエラーハンドリング、詳細ログ出力、トースト通知表示の追加
- [ ] 8.6 プリセットの保存/読込およびUI連動のテストコード・検証シナリオを作成 (`tests/test_presets_and_ui.py`)
- [ ] 8.7 ビルドの実行およびテストを実行し、エラーがないことを確認する
- [ ] 8.8 エラーがあれば修正し、git commit を実行する

### Phase 9: パッケージングと配布パイプライン (Phase E - 仕上げその3)
- [ ] 9.1 `pyinstaller` 用のビルド設定ファイル ([abmm.spec](file:///Users/hiroshi/dev/abmm/abmm.spec)) の作成（arm64ターゲット、frontend同梱、Info.plist設定等）
- [ ] 9.2 ローカルでの `pyinstaller` ビルド実行スクリプトの作成と動作確認
- [ ] 9.3 GitHub Actions用ワークフロー定義ファイルを作成（macOSランナー、ビルド、ad-hoc署名、dittoによるZIP化、Releasesへのアップロード） (`.github/workflows/build.yml`)
- [ ] 9.4 ビルドされた `.app` がオフライン環境でリソースを正しく読み込めるかどうかの検証テストの実施
- [ ] 9.5 READMEにインストール方法、起動トラブルシューティング、およびGatekeeper回避手順（右クリック→開く）を追記
- [ ] 9.6 ビルドパッケージの整合性テストおよびインストール検証（テストコードまたは確認スクリプトの実行）
- [ ] 9.7 エラーがあれば修正し、git commit を実行する
