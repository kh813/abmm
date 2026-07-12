import os
import numpy as np
import soundfile as sf
from typing import Dict, Any, Optional

def apply_crossfade(chunk1: np.ndarray, chunk2: np.ndarray, fade_len: int) -> np.ndarray:
    """
    2つのオーディオデータ（numpy配列）を指定されたサンプル数でクロスフェード結合する。
    """
    # チャンネル数に対応 (1D = Mono, 2D = Stereo)
    is_stereo = len(chunk1.shape) > 1
    
    # フェードカーブの作成（線形フェード）
    fade_out = np.linspace(1.0, 0.0, fade_len)
    fade_in = np.linspace(0.0, 1.0, fade_len)
    
    if is_stereo:
        # ステレオ用に次元を拡張
        fade_out = expand_fade_curve(fade_out, chunk1.shape[1])
        fade_in = expand_fade_curve(fade_in, chunk2.shape[1])
        
    # クロスフェードの計算
    faded = chunk1[-fade_len:] * fade_out + chunk2[:fade_len] * fade_in
    return faded

def expand_fade_curve(curve: np.ndarray, channels: int) -> np.ndarray:
    """フェードカーブをマルチチャンネル用に拡張する"""
    return np.tile(curve, (channels, 1)).T

def process_and_export_bgm(
    input_wav_path: str,
    output_path: str,
    target_duration_seconds: float,
    export_format: str = "wav",
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    オーディオファイルを読み込み、指定尺になるようクロスフェードループ処理を行い、
    音量正規化とフェードイン・フェードアウトを適用して書き出す。
    """
    params = params or {}
    crossfade_seconds = float(params.get("crossfade_seconds", 3.0))
    fade_in_seconds = float(params.get("fade_in_seconds", 2.0))
    fade_out_seconds = float(params.get("fade_out_seconds", 5.0))
    target_peak_db = float(params.get("target_peak_db", -1.0)) # デフォルト -1.0 dB

    # 1. 音声データの読み込み
    if not os.path.exists(input_wav_path):
        raise FileNotFoundError(f"入力オーディオファイルが見つかりません: {input_wav_path}")
        
    data, samplerate = sf.read(input_wav_path)
    
    num_samples = len(data)
    duration_seconds = num_samples / samplerate
    
    # 2. ループ回数の計算とループ処理
    target_samples = int(target_duration_seconds * samplerate)
    fade_len = int(crossfade_seconds * samplerate)
    
    # 音源が短すぎる場合はクロスフェード時間を縮小
    if duration_seconds <= crossfade_seconds * 2:
        crossfade_seconds = duration_seconds * 0.1
        fade_len = int(crossfade_seconds * samplerate)

    if fade_len < 1:
        fade_len = 1

    # 音源がすでに目標の長さより長い場合は、単にトリム
    if num_samples >= target_samples:
        looped_data = data[:target_samples].copy()
    else:
        # ループ構築用のリスト
        # 最初は1回丸ごとコピー
        out_chunks = [data]
        current_len = num_samples
        
        while current_len < target_samples + fade_len:
            # 前の末尾と新しい先頭をクロスフェード
            prev_chunk = out_chunks[-1]
            faded = apply_crossfade(prev_chunk, data, fade_len)
            
            # 前の末尾をクロスフェード結果で上書き
            # 元の配列を破壊しないようにスライスに代入
            # リスト内の前回の配列をコピーした上で末尾を差し替える
            last_idx = len(out_chunks) - 1
            out_chunks[last_idx] = out_chunks[last_idx].copy()
            out_chunks[last_idx][-fade_len:] = faded
            
            # 残りの部分（クロスフェード部より後）を新規追加
            remaining = data[fade_len:]
            out_chunks.append(remaining)
            
            # 加算された長さ（クロスフェードした分、全体が縮む）
            current_len += len(remaining)
            
        # 結合して目標サンプル数に切り詰める
        concatenated = np.concatenate(out_chunks, axis=0)
        looped_data = concatenated[:target_samples]

    # 3. フェードイン・フェードアウトの適用
    fade_in_len = int(fade_in_seconds * samplerate)
    fade_out_len = int(fade_out_seconds * samplerate)
    is_stereo = len(looped_data.shape) > 1

    # フェードイン
    if fade_in_len > 0 and len(looped_data) >= fade_in_len:
        curve_in = np.linspace(0.0, 1.0, fade_in_len)
        if is_stereo:
            curve_in = expand_fade_curve(curve_in, looped_data.shape[1])
        looped_data[:fade_in_len] *= curve_in

    # フェードアウト
    if fade_out_len > 0 and len(looped_data) >= fade_out_len:
        curve_out = np.linspace(1.0, 0.0, fade_out_len)
        if is_stereo:
            curve_out = expand_fade_curve(curve_out, looped_data.shape[1])
        looped_data[-fade_out_len:] *= curve_out

    # 4. 音量正規化 (Peak Normalization)
    max_val = np.max(np.abs(looped_data))
    if max_val > 0:
        # デシベルから線形倍率へ変換 (10 ^ (db / 20))
        target_scale = 10 ** (target_peak_db / 20.0)
        looped_data = looped_data * (target_scale / max_val)

    # 5. 音声の書き出し
    export_format = export_format.lower()
    actual_format = export_format
    
    # 保存先フォルダの作成
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    try:
        if export_format == "mp3":
            # soundfileがMP3書き出しに対応しているか確認
            # 対応していない場合は例外が飛ぶため、WAVフォールバックを行う
            sf.write(output_path, looped_data, samplerate, format="MP3")
        else:
            sf.write(output_path, looped_data, samplerate, format="WAV")
    except Exception as e:
        if export_format == "mp3":
            print(f"[loop_export] libsndfile does not support MP3 write natively. Falling back to WAV: {e}")
            # WAVとして書き出し、拡張子を修正
            base, _ = os.path.splitext(output_path)
            output_path = base + ".wav"
            sf.write(output_path, looped_data, samplerate, format="WAV")
            actual_format = "wav"
        else:
            raise e

    return {
        "status": "success",
        "output_path": output_path,
        "format": actual_format,
        "duration_seconds": len(looped_data) / samplerate,
        "samplerate": samplerate
    }
