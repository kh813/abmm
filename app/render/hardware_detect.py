import subprocess
import re
from typing import Dict, Any

def get_cpu_brand() -> str:
    """
    macOSの sysctl を使用して CPUのブランド名を取得する。
    """
    try:
        res = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode == 0:
            return res.stdout.strip()
        return "Unknown CPU"
    except Exception:
        return "Apple M1" # 開発/テスト用のデフォルトフォールバック

def get_total_memory_gb() -> float:
    """
    macOSの hw.memsize を使用してトータルのメモリ容量（GB単位）を取得する。
    """
    try:
        res = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode == 0:
            mem_bytes = int(res.stdout.strip())
            return mem_bytes / (1024 ** 3)
        return 8.0 # デフォルトフォールバック
    except Exception:
        return 8.0

def detect_hardware_spec() -> Dict[str, Any]:
    """
    Apple Silicon Macのスペック（チップ世代、メモリ容量）を検出し、
    推奨モデルティアとレンダリング可能な曲の長さ上限を返す。
    """
    cpu = get_cpu_brand()
    mem_gb = get_total_memory_gb()
    
    # デフォルトの制限値
    max_duration = 15.0
    recommended_tier = "Lite"
    
    # Apple Silicon M シリーズチップの世代をパース (例: "Apple M3 Pro" -> 3)
    chip_generation = 1
    m_match = re.search(r"Apple\s+M(\d+)", cpu)
    if m_match:
        chip_generation = int(m_match.group(1))
    else:
        # "Apple" または "M" の文字が含まれている場合は Apple Silicon として扱う
        if "apple" in cpu.lower():
            chip_generation = 1
            
    is_high_perf_chip = any(x in cpu for x in ["Pro", "Max", "Ultra"])

    # メモリとチップ性能に基づく上限判定ロジック
    if mem_gb <= 8.5:
        # メモリが8GB以下の場合は、動作時間制限を厳しくし、シンセサイザー合成(Lite)を推奨
        max_duration = 15.0
        recommended_tier = "Lite"
    elif mem_gb <= 16.5:
        # メモリが16GB程度の場合
        max_duration = 30.0
        # M2以上のチップであれば標準ニューラルモデル、それ以外はLite推奨
        if chip_generation >= 2:
            recommended_tier = "Standard"
        else:
            recommended_tier = "Lite"
    else:
        # 18GB/24GB/32GB/36GB 以上の大容量メモリ搭載マシンの場合
        max_duration = 60.0
        # M3以上またはPro/Max/Ultraチップであれば高品質ニューラルモデル、それ以外は標準モデル
        if chip_generation >= 3 or is_high_perf_chip:
            recommended_tier = "High Quality"
        else:
            recommended_tier = "Standard"
            
    # RAM量に応じた推奨Ollamaモデルの決定
    if mem_gb < 15.5:
        recommended_llms = ["llama3.2:3b"]
    elif mem_gb < 31.5:
        recommended_llms = ["llama3.2:3b", "qwen2.5-coder:7b", "gemma2:9b"]
    elif mem_gb < 63.5:
        recommended_llms = ["qwen2.5-coder:14b", "gemma2:27b", "mistral:7b"]
    elif mem_gb < 127.5:
        recommended_llms = ["qwen2.5:32b", "llama3:70b"]
    else:
        recommended_llms = ["llama3:70b", "command-r-plus"]

    return {
        "cpu_brand": cpu,
        "memory_gb": round(mem_gb, 1),
        "max_duration_minutes": max_duration,
        "recommended_model_tier": recommended_tier,
        "recommended_llm_models": recommended_llms
    }
