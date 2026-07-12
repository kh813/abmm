import os
import json
import urllib.request
from typing import Dict, Any, Optional, Callable, List

# キャッシュディレクトリの定義
CACHE_DIR = os.path.expanduser("~/Library/Caches/ABMM/models")

DEFAULT_CONFIG = {
    "ollama_models": [
        {"name": "llama3.2:3b", "label": "llama3.2:3b (軽量・高速)", "estimated_size_mb": 2000.0, "min_ram_gb": 0.0},
        {"name": "qwen2.5:7b", "label": "qwen2.5:7b (標準・中量級)", "estimated_size_mb": 4700.0, "min_ram_gb": 16.0},
        {"name": "gemma2:9b", "label": "gemma2:9b (高精度)", "estimated_size_mb": 5500.0, "min_ram_gb": 16.0},
        {"name": "qwen2.5:14b", "label": "qwen2.5:14b (高精度・中重量級)", "estimated_size_mb": 9000.0, "min_ram_gb": 32.0},
        {"name": "gemma2:27b", "label": "gemma2:27b (超高精度・重量級)", "estimated_size_mb": 16000.0, "min_ram_gb": 32.0},
        {"name": "qwen2.5:32b", "label": "qwen2.5:32b (プロフェッショナル・超重量級)", "estimated_size_mb": 19000.0, "min_ram_gb": 64.0},
        {"name": "llama3:70b", "label": "llama3:70b (最高品質・フラッグシップ)", "estimated_size_mb": 40000.0, "min_ram_gb": 64.0},
        {"name": "command-r-plus", "label": "command-r-plus (最高峰・大規模)", "estimated_size_mb": 60000.0, "min_ram_gb": 128.0}
    ],
    "phase2_models": {
        "Standard": {
            "repo": "fewtarius/generaluser-gs",
            "filename": "GeneralUser_GS_v1.471.sf2",
            "size_mb": 30.5,
            "url": "https://github.com/fewtarius/generaluser-gs/raw/master/GeneralUser%20GS%20v1.471.sf2"
        },
        "High Quality": {
            "repo": "Arcriser/hummify-assets",
            "filename": "FluidR3_GM.sf2",
            "size_mb": 141.0,
            "url": "https://huggingface.co/datasets/Arcriser/hummify-assets/resolve/main/FluidR3_GM.sf2"
        }
    }
}

class ModelManager:
    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        self.config_dir = os.path.expanduser("~/Library/Application Support/ABMM")
        self.config_path = os.path.join(self.config_dir, "models_config.json")
        self.config = self._load_local_config()

    def _load_local_config(self) -> dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ModelManager] Failed to load local config: {e}")
        return DEFAULT_CONFIG

    def update_config_online(self) -> None:
        """オンラインから最新のモデル構成定義ファイルを非同期または同期で取得して更新する"""
        url = "https://raw.githubusercontent.com/hiroshi-dev/abmm-configs/main/models_config.json"
        try:
            print(f"[ModelManager] Fetching latest models config from {url}...")
            os.makedirs(self.config_dir, exist_ok=True)
            req = urllib.request.Request(url, headers={"User-Agent": "ABMM-Desktop/0.4"})
            with urllib.request.urlopen(req, timeout=3.0) as response:
                new_config = json.loads(response.read().decode("utf-8"))
                if "ollama_models" in new_config and "phase2_models" in new_config:
                    with open(self.config_path, "w", encoding="utf-8") as f:
                        json.dump(new_config, f, ensure_ascii=False, indent=2)
                    self.config = new_config
                    print("[ModelManager] Models configuration updated successfully from online source.")
        except Exception as e:
            print(f"[ModelManager] Failed to update config online (using local/fallback): {e}")

    def get_phase2_configs(self) -> dict:
        return self.config.get("phase2_models", DEFAULT_CONFIG["phase2_models"])

    def get_ollama_models(self) -> list:
        return self.config.get("ollama_models", DEFAULT_CONFIG["ollama_models"])

    def get_model_path(self, tier: str) -> str:
        """
        指定されたティアのモデルファイルの保存パスを取得する。
        """
        configs = self.get_phase2_configs()
        if tier not in configs:
            raise ValueError(f"無効なモデルティア: {tier}")
            
        config = configs[tier]
        return os.path.join(self.cache_dir, tier, config["filename"])

    def is_model_downloaded(self, tier: str) -> bool:
        """
        指定されたティアのモデルがダウンロード済みか確認する。
        """
        if tier == "Lite":
            return True # Lite (SoundFont) はDL不要
            
        path = self.get_model_path(tier)
        return os.path.exists(path) and os.path.getsize(path) > 1024 * 1024

    def download_model(self, tier: str, progress_callback: Optional[Callable[[float], None]] = None, is_cancelled: Optional[Callable[[], bool]] = None) -> bool:
        """
        指定されたティアのモデルファイルをダウンロードする。
        """
        configs = self.get_phase2_configs()
        if tier not in configs:
            raise ValueError(f"無効なモデルティア: {tier}")
            
        config = configs[tier]
        dest_path = self.get_model_path(tier)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        url = config["url"]
        
        try:
            print(f"[ModelManager] Downloading {tier} model weights from {url}...")
            
            req = urllib.request.Request(url, headers={"User-Agent": "ABMM-Desktop/0.4"})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                block_size = 1024 * 64
                
                with open(dest_path + ".tmp", "wb") as f:
                    while True:
                        if is_cancelled and is_cancelled():
                            raise InterruptedError("ダウンロードがキャンセルされました。")
                        block = response.read(block_size)
                        if not block:
                            break
                        f.write(block)
                        downloaded += len(block)
                        
                        if total_size > 0 and progress_callback:
                            percent = downloaded / total_size
                            progress_callback(percent)
                            
            os.rename(dest_path + ".tmp", dest_path)
            print(f"[ModelManager] Download completed: {dest_path}")
            return True
            
        except Exception as e:
            if os.path.exists(dest_path + ".tmp"):
                os.remove(dest_path + ".tmp")
            print(f"[ModelManager] Failed to download model: {e}")
            return False
            
    def get_model_size_mb(self, tier: str) -> float:
        configs = self.get_phase2_configs()
        if tier in configs:
            return configs[tier]["size_mb"]
        return 0.0
