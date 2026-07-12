import os
import sys
import json
import threading
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
        
        self.last_composition = None
        self.window = None
        self.render_thread = None
        self.preset_manager = PresetManager()

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
                
        success = self.model_manager.download_model(tier, progress_callback=prog_cb)
        if self.window:
            self.window.evaluate_js(f"onDownloadComplete({json.dumps(tier)}, {json.dumps(success)})")

    def cancel_render(self):
        """現在進行中のレンダリング処理をキャンセルする"""
        self.neural_renderer.cancel()
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
            
            self._notify_status("MIDI作曲中...")
            self._notify_progress(0.0)

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
                instruments=instruments
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

            self.neural_renderer.render(midi_bytes, self.preview_wav_path, render_params)
            
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
                "audio_url": "temp_preview.wav"
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
                instruments=kwargs.get("instruments")
            )
            self.last_composition = composition
            midi_bytes = json_to_midi(composition)
            self.lite_renderer.render(midi_bytes, self.preview_wav_path)
            
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
                "audio_url": "temp_preview.wav"
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
            if comp_data:
                self.last_composition = MidiComposition(**comp_data)
                # プレビュー音声を即座に生成
                midi_bytes = json_to_midi(self.last_composition)
                self.lite_renderer.render(midi_bytes, self.preview_wav_path)
                
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
                "audio_url": "temp_preview.wav"
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
