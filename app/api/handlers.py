import os
from typing import Dict, Any, Optional
from app.api.llm_client import OllamaClient
from app.composer.prompt_builder import generate_midi_json
from app.composer.midi_converter import json_to_midi
from app.render.renderer_lite import LiteRenderer

class WebviewApi:
    """
    pywebview の Javascript から呼び出し可能な API クラス。
    Python-JS ブリッジとして機能する。
    """
    def __init__(self):
        self.llm_client = OllamaClient()
        self.lite_renderer = LiteRenderer()
        
        # パス設定の解決
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.frontend_dir = os.path.join(self.base_dir, "frontend")
        self.preview_wav_path = os.path.join(self.frontend_dir, "temp_preview.wav")
        self.last_composition = None

    def compose_and_preview(self, description: str, tempo: int, key_mode: str, duration: float) -> Dict[str, Any]:
        """
        自然言語入力とスライダーの基本パラメータに基づき MIDI JSON を生成し、
        FluidSynthでWAVプレビューファイルをレンダリングする統合処理。
        """
        try:
            # 1. MIDI JSONの生成 (Ollama)
            composition = generate_midi_json(
                client=self.llm_client,
                description=description,
                tempo_bpm=int(tempo),
                key_mode=key_mode,
                duration_minutes=float(duration)
            )
            self.last_composition = composition

            # 2. MIDI JSON から MIDI バイナリへの変換
            midi_bytes = json_to_midi(composition)

            # 3. FluidSynth によるプレビューWAVのレンダリング
            self.lite_renderer.render(midi_bytes, self.preview_wav_path)

            # 4. レンスポンス用にトラック情報を整理
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
                "audio_url": "temp_preview.wav"  # frontend ディレクトリからの相対パス
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
            
    def get_last_composition(self) -> Optional[Dict[str, Any]]:
        """最後に生成されたMIDI JSONを取得（デバッグ用）"""
        if self.last_composition:
            return self.last_composition.model_dump()
        return None
