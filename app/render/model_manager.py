import os
import urllib.request
from typing import Dict, Any, Optional, Callable

# キャッシュディレクトリの定義
CACHE_DIR = os.path.expanduser("~/Library/Caches/ABMM/models")

MODEL_CONFIGS = {
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

class ModelManager:
    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir

    def get_model_path(self, tier: str) -> str:
        """
        指定されたティアのモデルファイルの保存パスを取得する。
        """
        if tier not in MODEL_CONFIGS:
            raise ValueError(f"無効なモデルティア: {tier}")
            
        config = MODEL_CONFIGS[tier]
        return os.path.join(self.cache_dir, tier, config["filename"])

    def is_model_downloaded(self, tier: str) -> bool:
        """
        指定されたティアのモデルがダウンロード済みか確認する。
        """
        if tier == "Lite":
            return True # Lite (SoundFont) はDL不要 (LiteRenderer側で自動ハンドリング)
            
        path = self.get_model_path(tier)
        return os.path.exists(path) and os.path.getsize(path) > 1024 * 1024 # 最小サイズ検証 (1MB以上)

    def download_model(self, tier: str, progress_callback: Optional[Callable[[float], None]] = None) -> bool:
        """
        指定されたティアのモデルファイルをHuggingFace等からダウンロードする。
        """
        if tier not in MODEL_CONFIGS:
            raise ValueError(f"無効なモデルティア: {tier}")
            
        config = MODEL_CONFIGS[tier]
        dest_path = self.get_model_path(tier)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        url = config["url"]
        
        try:
            print(f"[ModelManager] Downloading {tier} model weights from {url}...")
            
            # urllibを使用して進捗付ダウンロードを実装
            req = urllib.request.Request(url, headers={"User-Agent": "ABMM-Desktop/0.4"})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                block_size = 1024 * 64
                
                with open(dest_path + ".tmp", "wb") as f:
                    while True:
                        block = response.read(block_size)
                        if not block:
                            break
                        f.write(block)
                        downloaded += len(block)
                        
                        if total_size > 0 and progress_callback:
                            percent = downloaded / total_size
                            progress_callback(percent)
                            
            # ダウンロード完了後にtmpファイルをリネーム
            os.rename(dest_path + ".tmp", dest_path)
            print(f"[ModelManager] Download completed: {dest_path}")
            return True
            
        except Exception as e:
            # 失敗時のクリーンアップ
            if os.path.exists(dest_path + ".tmp"):
                os.remove(dest_path + ".tmp")
            print(f"[ModelManager] Failed to download model: {e}")
            return False
            
    def get_model_size_mb(self, tier: str) -> float:
        if tier in MODEL_CONFIGS:
            return MODEL_CONFIGS[tier]["size_mb"]
        return 0.0
