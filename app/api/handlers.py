import os
import sys
import json
import threading
import webview
from typing import Dict, Any, Optional
from app.api.llm_client import OllamaClient
from app.composer.prompt_builder import generate_midi_json
from app.composer.midi_converter import json_to_midi
from app.render.renderer_lite import LiteRenderer
from app.render.renderer_neural import NeuralRenderer
from app.render.model_manager import ModelManager
from app.render.hardware_detect import detect_hardware_spec
from app.composer.midi_schema import MidiComposition
from app.presets.preset_manager import PresetManager
from app.postprocess.loop_export import process_and_export_bgm

def trim_composition_to_seconds(composition: MidiComposition, seconds: float) -> MidiComposition:
    """
    MIDI Compositionを指定された秒数でトリムする（30秒プレビュー再生用など）。
    """
    trimmed = composition.model_copy(deep=True)
    if trimmed.tempo_bpm <= 0:
        return trimmed
        
    step_duration = 15.0 / trimmed.tempo_bpm
    trimmed.duration_minutes = min(trimmed.duration_minutes, seconds / 60.0)
    
    for track in trimmed.tracks:
        trimmed_notes = []
        for note in track.notes:
            note_start_time = note.step * step_duration
            if note_start_time < seconds:
                note_end_time = (note.step + note.duration_steps) * step_duration
                if note_end_time > seconds:
                    # 音の長さをトリム位置までに切り詰める
                    note.duration_steps = int(round((seconds - note_start_time) / step_duration))
                    if note.duration_steps < 1:
                        note.duration_steps = 1
                trimmed_notes.append(note)
        track.notes = trimmed_notes
        
    return trimmed

class WebviewApi:
    """
    pywebview の Javascript から呼び出し可能な API クラス。
    非同期レンダリング・キャンセル処理、スペック検出、モデル管理を仲介する。
    """
    def __init__(self):
        self.llm_client = OllamaClient()
        self.lite_renderer = LiteRenderer()
        self.model_manager = ModelManager()
        self.neural_renderer = NeuralRenderer(self.model_manager)
        
        # パス設定
        if hasattr(sys, "_MEIPASS"):
            self.base_dir = sys._MEIPASS
        else:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.frontend_dir = os.path.join(self.base_dir, "frontend")
        self.preview_wav_path = os.path.join(self.frontend_dir, "temp_preview.wav")
        self.temp_export_wav_path = os.path.join(self.frontend_dir, "temp_export.wav")
        
        self.last_composition = None
        self.window = None
        self.render_thread = None
        self.preset_manager = PresetManager()
        self.settings_path = os.path.expanduser("~/Library/Application Support/ABMM/settings.json")
        self._download_cancel_requested = False
        
        # バックグラウンドでオンラインモデル設定ファイルを更新
        threading.Thread(target=self.model_manager.update_config_online, daemon=True).start()

    def _get_dynamic_preview_path(self) -> tuple[str, str]:
        """
        古い temp_preview_*.wav ファイルをクリーンアップし、
        キャッシュ回避のためのユニークな新しいWAVファイル名と絶対パスを返す。
        """
        import time
        try:
            for f in os.listdir(self.frontend_dir):
                if f.startswith("temp_preview_") and f.endswith(".wav"):
                    try:
                        os.remove(os.path.join(self.frontend_dir, f))
                    except Exception:
                        pass
        except Exception as e:
            print(f"[handlers] Failed to clean up temp files: {e}")
            
        filename = f"temp_preview_{int(time.time() * 1000)}.wav"
        full_path = os.path.join(self.frontend_dir, filename)
        self.preview_wav_path = full_path
        return filename, full_path

    def set_window(self, window):
        """pywebviewのウィンドウインスタンスを紐づける"""
        self.window = window

    def get_hardware_specs(self):
        """PCのスペック情報を取得する"""
        try:
            return detect_hardware_spec()
        except Exception as e:
            return {
                "cpu_brand": "Unknown (Error)",
                "memory_gb": 8.0,
                "max_duration_minutes": 15.0,
                "recommended_model_tier": "Lite",
                "error": str(e)
            }

    def check_model_downloaded(self, tier):
        """指定モデルがダウンロード済みか確認する"""
        try:
            return self.model_manager.is_model_downloaded(tier)
        except Exception:
            return False

    def start_model_download(self, tier):
        """非同期でモデルのダウンロードを開始する"""
        import shutil
        try:
            total, used, free = shutil.disk_usage(self.model_manager.cache_dir)
            free_mb = free / (1024 * 1024)
            required_mb = self.model_manager.get_model_size_mb(tier)
            if free_mb < required_mb + 100: # 100MBのマージン
                return {
                    "status": "error", 
                    "message": f"ディスク空き容量が不足しています。必要: {required_mb:.1f}MB, 空き: {free_mb:.1f}MB"
                }
        except Exception as e:
            print(f"[handlers] Disk space check failed: {e}")

        self._download_cancel_requested = False
        download_thread = threading.Thread(
            target=self._async_download_worker,
            args=(tier,),
            daemon=True
        )
        download_thread.start()
        return {"status": "success", "message": "Download started"}

    def _async_download_worker(self, tier: str) -> None:
        def prog_cb(percent: float):
            if self.window:
                self.window.evaluate_js(f"onDownloadProgress({json.dumps(tier)}, {percent})")
                
        success = self.model_manager.download_model(
            tier, 
            progress_callback=prog_cb, 
            is_cancelled=lambda: self._download_cancel_requested
        )
        if self.window:
            self.window.evaluate_js(f"onDownloadComplete({json.dumps(tier)}, {json.dumps(success)})")

    def cancel_render(self):
        """現在進行中のレンダリングまたはダウンロード処理をキャンセルする"""
        self.neural_renderer.cancel()
        self._download_cancel_requested = True
        return {"status": "success", "message": "Cancellation request sent"}

    def start_render_async(self, params):
        """
        非同期で作曲＆レンダリング処理（全体本番 or 30秒プレビュー）を開始する。
        """
        if self.render_thread and self.render_thread.is_alive():
            return {"status": "error", "message": "レンダリングが既に実行中です。"}
            
        self.render_thread = threading.Thread(
            target=self._async_render_worker,
            args=(params,),
            daemon=True
        )
        self.render_thread.start()
        return {"status": "success", "message": "Render thread launched"}

    def _async_render_worker(self, params: Dict[str, Any]) -> None:
        try:
            description = params.get("description", "")
            tempo = int(params.get("tempo", 80))
            key_mode = params.get("key_mode", "major")
            duration = float(params.get("duration", 1.0))
            
            # 各種スライダー微調整
            brightness = float(params.get("brightness", 0.5))
            energy = float(params.get("energy", 0.5))
            density = float(params.get("density", 0.5))
            instruments = params.get("instruments")
            
            # モデル構成
            model_tier = params.get("model_tier", "Standard")
            preview_only = params.get("preview_only", False)
            ollama_model = params.get("ollama_model")
            if ollama_model:
                self.llm_client.model = ollama_model
            
            self._notify_status("MIDI作曲中...")
            self._notify_progress(0.0)

            genre = params.get("genre", "auto")
            chord_progression = params.get("chord_progression", "auto")

            # 1. MIDI JSONの生成 (Ollama)
            composition = generate_midi_json(
                client=self.llm_client,
                description=description,
                tempo_bpm=tempo,
                key_mode=key_mode,
                duration_minutes=duration,
                brightness=brightness,
                energy=energy,
                density=density,
                instruments=instruments,
                genre=genre,
                chord_progression=chord_progression
            )
            self.last_composition = composition
            self._notify_progress(0.2)

            if preview_only:
                self._notify_status("プレビュー用に30秒トリム中...")
                composition = trim_composition_to_seconds(composition, 30.0)

            # 2. MIDI JSON から MIDI バイナリへの変換
            midi_bytes = json_to_midi(composition)
            self._notify_progress(0.3)

            # 3. レンダリングの実行
            self._notify_status("オーディオ波形生成中...")
            
            # 進行率を 0.3 から 1.0 の幅にマッピング
            def render_progress_cb(p: float):
                scaled_val = 0.3 + p * 0.7
                self._notify_progress(scaled_val)

            render_params = {
                "model_tier": model_tier,
                "progress_callback": render_progress_cb
            }

            audio_filename, preview_wav_path = self._get_dynamic_preview_path()
            self.neural_renderer.render(midi_bytes, preview_wav_path, render_params)
            
            # 4. 完了データの準備と通知
            tracks_info = []
            for track in composition.tracks:
                tracks_info.append({
                    "track_id": track.track_id,
                    "track_name": track.track_name,
                    "instrument": track.instrument,
                    "notes_count": len(track.notes)
                })

            result = {
                "status": "success",
                "tempo_bpm": composition.tempo_bpm,
                "key_mode": composition.key_mode,
                "duration_minutes": composition.duration_minutes,
                "tracks": tracks_info,
                "audio_url": audio_filename
            }
            
            if self.window:
                self.window.evaluate_js(f"onRenderComplete({json.dumps(result)})")

        except Exception as e:
            print(f"[handlers] Async render worker failed: {e}")
            if self.window:
                self.window.evaluate_js(f"onRenderError({json.dumps(str(e))})")

    def _notify_progress(self, val: float) -> None:
        if self.window:
            self.window.evaluate_js(f"updateRenderProgress({val})")

    def _notify_status(self, msg: str) -> None:
        if self.window:
            self.window.evaluate_js(f"updateRenderStatus({json.dumps(msg)})")

    def get_last_composition(self):
        """最後に生成されたMIDI JSONを取得"""
        if self.last_composition:
            return self.last_composition.model_dump()
        return None

    def compose_and_preview(self, description, tempo, key_mode, duration, **kwargs):
        """互換性維持のための同期メソッド"""
        # start_render_async を代わりに走らせるシミュレーション、
        # あるいは直接LiteRendererを呼ぶ
        try:
            composition = generate_midi_json(
                client=self.llm_client,
                description=description,
                tempo_bpm=int(tempo),
                key_mode=key_mode,
                duration_minutes=float(duration),
                brightness=float(kwargs.get("brightness", 0.5)),
                energy=float(kwargs.get("energy", 0.5)),
                density=float(kwargs.get("density", 0.5)),
                instruments=kwargs.get("instruments"),
                genre=kwargs.get("genre", "auto"),
                chord_progression=kwargs.get("chord_progression", "auto")
            )
            self.last_composition = composition
            midi_bytes = json_to_midi(composition)
            audio_filename, preview_wav_path = self._get_dynamic_preview_path()
            self.lite_renderer.render(midi_bytes, preview_wav_path)
            
            tracks_info = []
            for track in composition.tracks:
                tracks_info.append({
                    "track_id": track.track_id,
                    "track_name": track.track_name,
                    "instrument": track.instrument,
                    "notes_count": len(track.notes)
                })

            return {
                "status": "success",
                "tempo_bpm": composition.tempo_bpm,
                "key_mode": composition.key_mode,
                "duration_minutes": composition.duration_minutes,
                "tracks": tracks_info,
                "audio_url": audio_filename
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def save_preset(self, name, params):
        """現在の作曲結果とパラメータをプリセットに保存する"""
        if not self.last_composition:
            return {"status": "error", "message": "保存する作曲データがありません。先に作曲を実行してください。"}
        try:
            key = self.preset_manager.save_preset(name, params, self.last_composition)
            return {"status": "success", "key": key}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_presets(self):
        """保存されたプリセット一覧を取得する"""
        try:
            return self.preset_manager.list_presets()
        except Exception:
            return []

    def load_preset(self, key):
        """プリセットを読み込んでパラメータとMIDI compositionをセットする"""
        try:
            data = self.preset_manager.load_preset(key)
            if not data:
                return {"status": "error", "message": "プリセットが見つかりませんでした。"}
                
            # メモリ内の last_composition を上書きして、Phase 1をスキップできるようにする
            comp_data = data.get("composition")
            tracks_info = []
            audio_filename = "temp_preview.wav"
            if comp_data:
                self.last_composition = MidiComposition(**comp_data)
                # プレビュー音声を即座に生成
                midi_bytes = json_to_midi(self.last_composition)
                audio_filename, preview_wav_path = self._get_dynamic_preview_path()
                self.lite_renderer.render(midi_bytes, preview_wav_path)
                
                for track in self.last_composition.tracks:
                    tracks_info.append({
                        "track_id": track.track_id,
                        "track_name": track.track_name,
                        "instrument": track.instrument,
                        "notes_count": len(track.notes)
                    })
                
            return {
                "status": "success",
                "name": data.get("name"),
                "params": data.get("params"),
                "tracks": tracks_info,
                "audio_url": audio_filename
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def delete_preset(self, key):
        """プリセットを削除する"""
        try:
            success = self.preset_manager.delete_preset(key)
            if success:
                return {"status": "success"}
            return {"status": "error", "message": "プリセットの削除に失敗しました。"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def check_ollama_status(self):
        """Ollamaの接続状況とモデル一覧を取得する"""
        return self.llm_client.check_status()

    def start_ollama_model_download(self, model_name):
        """非同期でOllamaのモデルダウンロードを開始する"""
        import shutil
        try:
            total, used, free = shutil.disk_usage(os.path.expanduser("~"))
            free_mb = free / (1024 * 1024)
            # 推定サイズ
            estimated_mb = 2000.0
            if "9b" in model_name:
                estimated_mb = 5500.0
            elif "7b" in model_name:
                estimated_mb = 4700.0
                
            if free_mb < estimated_mb + 500: # 500MBのマージン
                return {
                    "status": "error",
                    "message": f"ディスク空き容量が不足しています。必要: {estimated_mb/1024:.1f}GB, 空き: {free_mb/1024:.1f}GB"
                }
        except Exception as e:
            print(f"[handlers] Ollama disk check failed: {e}")

        t = threading.Thread(
            target=self._async_ollama_download_worker,
            args=(model_name,),
            daemon=True
        )
        t.start()
        return {"status": "success"}

    def _async_ollama_download_worker(self, model_name):
        def prog_cb(percent, status):
            if self.window:
                self.window.evaluate_js(f"onOllamaDownloadProgress({json.dumps(model_name)}, {percent}, {json.dumps(status)})")
        
        success = self.llm_client.pull_model(model_name, progress_callback=prog_cb)
        if self.window:
            self.window.evaluate_js(f"onOllamaDownloadComplete({json.dumps(model_name)}, {json.dumps(success)})")

    def set_ollama_model(self, model_name):
        """Ollamaクライアントのアクティブモデルを設定する"""
        self.llm_client.model = model_name
        return {"status": "success", "model": model_name}

    def select_export_file(self, export_format):
        """保存先ファイルを選択するダイアログを表示する"""
        if not self.window:
            return None
        
        file_types = ('WAV Files (*.wav)',) if export_format == "wav" else ('MP3 Files (*.mp3)',)
        
        # デフォルト保存先を ~/Music/ABMM に設定し、存在しない場合は自動作成する
        music_dir = os.path.expanduser("~/Music/ABMM")
        try:
            os.makedirs(music_dir, exist_ok=True)
        except Exception:
            music_dir = os.path.expanduser("~")
            
        file_path = self.window.create_file_dialog(
            dialog_type=webview.SAVE_DIALOG,
            directory=music_dir,
            file_types=file_types,
            save_filename=f"background_music.{export_format}"
        )
        if file_path:
            if isinstance(file_path, (list, tuple)):
                return file_path[0] if len(file_path) > 0 else None
            return file_path
        return None

    def start_export_async(self, params):
        """本番レンダリング＆ループ処理を非同期で開始する"""
        threading.Thread(
            target=self._async_export_worker,
            args=(params,),
            daemon=True
        ).start()
        return {"status": "success"}

    def _async_export_worker(self, params):
        try:
            export_path = params.get("export_path")
            export_duration_minutes = float(params.get("export_duration", 10.0))
            export_format = params.get("export_format", "wav")
            model_tier = params.get("model_tier", "Standard")

            if not self.last_composition:
                raise ValueError("MIDI組成が存在しません。先に作曲を行ってください。")

            self._notify_status("本番レンダリング中...")
            self._notify_progress(0.0)

            # 1. MIDIバイナリの変換
            midi_bytes = json_to_midi(self.last_composition)
            self._notify_progress(0.1)

            # 2. 本番用のレンダリング
            def render_progress_cb(p: float):
                # 進行状況を 0.1 から 0.7 までの範囲にスケーリング
                scaled_val = 0.1 + p * 0.6
                self._notify_progress(scaled_val)

            render_params = {
                "model_tier": model_tier,
                "progress_callback": render_progress_cb
            }
            self.neural_renderer.render(midi_bytes, self.temp_export_wav_path, render_params)
            
            # 3. ループ処理と書き出し
            self._notify_status("ループ＆フェード処理中...")
            self._notify_progress(0.75)

            target_duration_seconds = export_duration_minutes * 60.0
            
            export_params = {}
            if params.get("seamless_loop", False):
                export_params["fade_in_seconds"] = 0.0
                export_params["fade_out_seconds"] = 0.0
            
            process_and_export_bgm(
                input_wav_path=self.temp_export_wav_path,
                output_path=export_path,
                target_duration_seconds=target_duration_seconds,
                export_format=export_format,
                params=export_params
            )
            
            self._notify_progress(1.0)
            result = {
                "status": "success",
                "export_path": export_path
            }
            if self.window:
                self.window.evaluate_js(f"onExportComplete({json.dumps(result)})")

        except Exception as e:
            print(f"[handlers] Export worker failed: {e}")
            if self.window:
                self.window.evaluate_js(f"onExportError({json.dumps(str(e))})")

    def get_models_disk_info(self):
        """ダウンロード済みモデル一覧、使用容量、ディスク空き容量を取得する"""
        import shutil
        cache_dir = self.model_manager.cache_dir
        
        models_info = []
        
        # 1. Phase 2モデル
        for tier in ["Standard", "High Quality"]:
            downloaded = self.model_manager.is_model_downloaded(tier)
            size_mb = 0.0
            if downloaded:
                path = self.model_manager.get_model_path(tier)
                try:
                    size_mb = os.path.getsize(path) / (1024 * 1024)
                except Exception:
                    pass
            models_info.append({
                "name": f"Phase 2 - {tier}",
                "tier": tier,
                "type": "phase2",
                "downloaded": downloaded,
                "size_mb": round(size_mb, 1)
            })
            
        # 2. Ollamaモデル
        ollama_status = self.llm_client.check_status()
        if ollama_status.get("status") == "online":
            models = ollama_status.get("models", [])
            ollama_candidates = [
                {"name": "llama3.2:3b", "label": "llama3.2:3b (軽量)", "estimated_size_mb": 2000.0},
                {"name": "gemma2:9b", "label": "gemma2:9b (高精度)", "estimated_size_mb": 5500.0},
                {"name": "qwen2.5:7b", "label": "qwen2.5:7b (標準)", "estimated_size_mb": 4700.0}
            ]
            for cand in ollama_candidates:
                is_dl = False
                actual_size_mb = 0.0
                for m in models:
                    if cand["name"] in m["name"]:
                        is_dl = True
                        size_bytes = m.get("size", 0)
                        if size_bytes > 0:
                            actual_size_mb = size_bytes / (1024 * 1024)
                        else:
                            actual_size_mb = cand["estimated_size_mb"]
                        break
                
                models_info.append({
                    "name": f"Ollama - {cand['label']}",
                    "model_name": cand["name"],
                    "type": "ollama",
                    "downloaded": is_dl,
                    "size_mb": round(actual_size_mb if is_dl else 0.0, 1)
                })
        
        try:
            total, used, free = shutil.disk_usage(cache_dir)
            total_gb = total / (1024 * 1024 * 1024)
            free_gb = free / (1024 * 1024 * 1024)
            used_gb = used / (1024 * 1024 * 1024)
        except Exception:
            total_gb = 0.0
            free_gb = 0.0
            used_gb = 0.0
            
        return {
            "models": models_info,
            "disk_total_gb": round(total_gb, 1),
            "disk_used_gb": round(used_gb, 1),
            "disk_free_gb": round(free_gb, 1)
        }

    def delete_model(self, model_type, name_or_tier):
        """ダウンロード済みのモデルを削除する"""
        try:
            if model_type == "phase2":
                tier = name_or_tier
                if tier == "Lite":
                    return {"status": "error", "message": "Liteモデルは削除できません。"}
                path = self.model_manager.get_model_path(tier)
                if os.path.exists(path):
                    os.remove(path)
                    return {"status": "success"}
                return {"status": "error", "message": "モデルファイルが存在しません。"}
            elif model_type == "ollama":
                import urllib.request
                import json
                payload = {"name": name_or_tier}
                req = urllib.request.Request(
                    f"{self.llm_client.base_url}/api/delete",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="DELETE"
                )
                with urllib.request.urlopen(req) as res:
                    pass
                return {"status": "success"}
            return {"status": "error", "message": f"不明なモデルタイプです: {model_type}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_app_settings(self):
        """設定データを取得する（なければデフォルト値）"""
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[handlers] Failed to load settings: {e}")
        return {"auto_update_check": True}

    def save_app_settings(self, settings):
        """設定データを保存する"""
        try:
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def export_midi_file(self):
        """Phase 1で生成されたMIDIデータをファイルとして保存する"""
        if not self.window:
            return {"status": "error", "message": "Window context not found"}
        if not self.last_composition:
            return {"status": "error", "message": "MIDIデータがありません。先に作曲を行うか、プリセットをロードしてください。"}
            
        file_types = ('MIDI Files (*.mid;*.midi)',)
        default_dir = os.path.expanduser("~/Music/ABMM")
        try:
            os.makedirs(default_dir, exist_ok=True)
        except Exception:
            default_dir = os.path.expanduser("~")
            
        file_path = self.window.create_file_dialog(
            dialog_type=webview.SAVE_DIALOG,
            directory=default_dir,
            file_types=file_types,
            save_filename="composition.mid"
        )
        if not file_path:
            return {"status": "cancelled"}
            
        if isinstance(file_path, (list, tuple)):
            file_path = file_path[0] if len(file_path) > 0 else None
            
        if not file_path:
            return {"status": "cancelled"}
            
        try:
            midi_bytes = json_to_midi(self.last_composition)
            with open(file_path, "wb") as f:
                f.write(midi_bytes)
            return {"status": "success", "file_path": file_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def import_midi_file(self):
        """外部のMIDIファイル(.mid)を読み込み、現在の組成データとしてセットする"""
        if not self.window:
            return {"status": "error", "message": "Window context not found"}
            
        file_types = ('MIDI Files (*.mid;*.midi)',)
        default_dir = os.path.expanduser("~/Music/ABMM")
        if not os.path.exists(default_dir):
            default_dir = os.path.expanduser("~")
            
        file_path = self.window.create_file_dialog(
            dialog_type=webview.OPEN_DIALOG,
            directory=default_dir,
            file_types=file_types
        )
        if not file_path:
            return {"status": "cancelled"}
            
        if isinstance(file_path, (list, tuple)):
            file_path = file_path[0] if len(file_path) > 0 else None
            
        if not file_path:
            return {"status": "cancelled"}
            
        try:
            import io
            import pretty_midi
            with open(file_path, "rb") as f:
                midi_bytes = f.read()
            
            pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
            duration_minutes = round(pm.get_end_time() / 60.0, 1)
            if duration_minutes < 0.1:
                duration_minutes = 0.1
                
            from app.composer.midi_converter import midi_to_json
            composition = midi_to_json(midi_bytes, duration_minutes=duration_minutes)
            self.last_composition = composition
            
            tracks_info = []
            for track in composition.tracks:
                tracks_info.append({
                    "track_id": track.track_id,
                    "track_name": track.track_name,
                    "instrument": track.instrument,
                    "notes_count": len(track.notes)
                })
                
            audio_filename = "temp_preview.wav"
            try:
                midi_bin = json_to_midi(composition)
                audio_filename, preview_wav_path = self._get_dynamic_preview_path()
                self.lite_renderer.render(midi_bin, preview_wav_path)
            except Exception as render_err:
                print(f"[handlers] Failed to auto-render imported MIDI preview: {render_err}")

            result = {
                "status": "success",
                "tempo_bpm": composition.tempo_bpm,
                "key_mode": composition.key_mode,
                "duration_minutes": composition.duration_minutes,
                "tracks": tracks_info,
                "audio_url": audio_filename
            }
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_ollama_candidates(self):
        """ハードウェア推奨マーク付きのOllamaモデル定義リストを取得する"""
        specs = detect_hardware_spec()
        host_ram = specs.get("memory_gb", 8.0)
        recommended_models = specs.get("recommended_llm_models", [])
        
        candidates = self.model_manager.get_ollama_models()
        result = []
        for cand in candidates:
            name = cand["name"]
            label = cand["label"]
            min_ram = cand.get("min_ram_gb", 0.0)
            
            is_recommended = name in recommended_models
            # 搭載RAMが最小必要RAM未満の場合は選択不可（無効化）にする
            disabled = host_ram < min_ram
            
            # 推奨モデルにはラベルに (推奨) を付加
            if is_recommended and "推奨" not in label:
                label = label.replace(name, f"{name} (推奨)")
            if disabled:
                label += " [スペック不足]"
                
            result.append({
                "name": name,
                "label": label,
                "is_recommended": is_recommended,
                "disabled": disabled
            })
        return result

