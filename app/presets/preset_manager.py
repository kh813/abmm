import os
import json
from typing import List, Dict, Any, Optional
from app.composer.midi_schema import MidiComposition
from app.composer.midi_converter import json_to_midi

PRESETS_DIR = os.path.expanduser("~/Library/Application Support/ABMM/presets")

class PresetManager:
    def __init__(self, presets_dir: str = PRESETS_DIR):
        self.presets_dir = presets_dir

    def ensure_dir(self) -> None:
        """プリセット保存用ディレクトリの確保"""
        os.makedirs(self.presets_dir, exist_ok=True)

    def save_preset(self, name: str, params: Dict[str, Any], composition: MidiComposition) -> str:
        """
        現在の作曲パラメータと生成された MIDI データをプリセットとしてローカルに保存する。
        """
        self.ensure_dir()
        
        # 安全なファイル名の生成
        safe_name = "".join([c for c in name if c.isalpha() or c.isdigit() or c in " _-"]).rstrip()
        if not safe_name:
            safe_name = "untitled_preset"
            
        json_path = os.path.join(self.presets_dir, f"{safe_name}.json")
        mid_path = os.path.join(self.presets_dir, f"{safe_name}.mid")
        
        # プリセットメタデータの構築
        preset_data = {
            "name": name,
            "params": params,
            "composition": composition.model_dump()
        }
        
        # 1. JSON (メタデータ & Composition) 保存
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(preset_data, f, ensure_ascii=False, indent=2)
            
        # 2. MIDI バイナリ保存
        midi_bytes = json_to_midi(composition)
        with open(mid_path, "wb") as f:
            f.write(midi_bytes)
            
        print(f"[PresetManager] Saved preset '{name}' to {json_path}")
        return safe_name

    def list_presets(self) -> List[Dict[str, Any]]:
        """
        保存されているすべてのプリセット一覧（メタ情報のみ）を取得する。
        """
        self.ensure_dir()
        presets = []
        
        for file in os.listdir(self.presets_dir):
            if file.endswith(".json"):
                json_path = os.path.join(self.presets_dir, file)
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        presets.append({
                            "key": os.path.splitext(file)[0],
                            "name": data.get("name", file),
                            "params": data.get("params", {}),
                            "has_composition": "composition" in data
                        })
                except Exception as e:
                    print(f"[PresetManager] Failed to load preset metadata from {json_path}: {e}")
                    
        return presets

    def load_preset(self, key: str) -> Optional[Dict[str, Any]]:
        """
        指定されたキーのプリセット詳細をロードする。
        """
        json_path = os.path.join(self.presets_dir, f"{key}.json")
        if not os.path.exists(json_path):
            return None
            
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            print(f"[PresetManager] Failed to read preset file {json_path}: {e}")
            return None

    def delete_preset(self, key: str) -> bool:
        """
        プリセットの削除を行う。
        """
        json_path = os.path.join(self.presets_dir, f"{key}.json")
        mid_path = os.path.join(self.presets_dir, f"{key}.mid")
        
        deleted = False
        if os.path.exists(json_path):
            os.remove(json_path)
            deleted = True
        if os.path.exists(mid_path):
            os.remove(mid_path)
            deleted = True
            
        return deleted
