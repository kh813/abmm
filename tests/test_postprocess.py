import os
import numpy as np
import soundfile as sf
import pytest
from unittest.mock import patch

from app.postprocess.loop_export import (
    apply_crossfade,
    process_and_export_bgm
)

@pytest.fixture
def temp_audio_paths(tmp_path):
    input_wav = tmp_path / "input_short.wav"
    output_wav = tmp_path / "output_bgm.wav"
    output_mp3 = tmp_path / "output_bgm.mp3"
    return str(input_wav), str(output_wav), str(output_mp3)

def test_apply_crossfade_mono():
    # 100 samples, mono
    chunk1 = np.ones(100) * 1.0
    chunk2 = np.ones(100) * 2.0
    fade_len = 10
    
    faded = apply_crossfade(chunk1, chunk2, fade_len)
    assert len(faded) == fade_len
    # First sample of crossfade is exactly 1.0 (chunk1 * 1.0 + chunk2 * 0.0)
    assert pytest.approx(faded[0]) == 1.0
    # At index 5: 1.0 * (4/9) + 2.0 * (5/9) = 14/9 = 1.55555...
    assert pytest.approx(faded[5]) == 1.5555555555555556
    # Last sample of crossfade is exactly 2.0
    assert pytest.approx(faded[-1]) == 2.0

def test_apply_crossfade_stereo():
    # Stereo chunks (100 samples, 2 channels)
    chunk1 = np.ones((100, 2)) * 1.0
    chunk2 = np.ones((100, 2)) * 2.0
    fade_len = 10
    
    faded = apply_crossfade(chunk1, chunk2, fade_len)
    assert faded.shape == (fade_len, 2)
    assert pytest.approx(faded[5, 0]) == 1.5555555555555556
    assert pytest.approx(faded[5, 1]) == 1.5555555555555556


def test_process_and_export_bgm_wav(temp_audio_paths):
    input_wav, output_wav, _ = temp_audio_paths
    
    # 1. 2秒間のサイン波ステレオ信号（44100Hz）を作成して保存
    sr = 44100
    t = np.linspace(0.0, 2.0, 2 * sr, endpoint=False)
    sig_left = 0.5 * np.sin(2 * np.pi * 440 * t)
    sig_right = 0.5 * np.sin(2 * np.pi * 880 * t)
    sig = np.column_stack((sig_left, sig_right))
    sf.write(input_wav, sig, sr, format="WAV")
    
    # 2. 5秒間のBGMにループ拡大（3秒クロスフェード、0.5秒フェードイン、0.5秒フェードアウト、Peak -2.0dB）
    res = process_and_export_bgm(
        input_wav_path=input_wav,
        output_path=output_wav,
        target_duration_seconds=5.0,
        export_format="wav",
        params={
            "crossfade_seconds": 0.5,
            "fade_in_seconds": 0.5,
            "fade_out_seconds": 0.5,
            "target_peak_db": -2.0
        }
    )
    
    assert res["status"] == "success"
    assert res["format"] == "wav"
    assert os.path.exists(output_wav)
    
    # 3. 生成されたファイルを検証
    data, samplerate = sf.read(output_wav)
    assert samplerate == sr
    # 目標サンプル数（5秒 * 44100）であること
    assert len(data) == 5 * sr
    
    # ピーク音量の検証: -2.0 dB = 10^(-2.0/20) = 0.794328...
    peak = np.max(np.abs(data))
    assert pytest.approx(peak, abs=1e-3) == 10 ** (-2.0 / 20.0)
    
    # フェードインの検証（先頭は0.0から始まり、徐々に増加）
    assert data[0, 0] == 0.0
    assert data[0, 1] == 0.0
    assert np.max(np.abs(data[:10])) < np.max(np.abs(data[20000:20010]))
    
    # フェードアウトの検証（末尾は0.0で終了）
    assert pytest.approx(data[-1, 0], abs=1e-5) == 0.0
    assert pytest.approx(data[-1, 1], abs=1e-5) == 0.0

def test_process_and_export_bgm_mp3_fallback(temp_audio_paths):
    input_wav, _, output_mp3 = temp_audio_paths
    
    # 2秒間のサイン波ステレオ信号（44100Hz）を作成して保存
    sr = 44100
    t = np.linspace(0.0, 2.0, 2 * sr, endpoint=False)
    sig = np.column_stack((0.5 * np.sin(2 * np.pi * 440 * t), 0.5 * np.sin(2 * np.pi * 440 * t)))
    sf.write(input_wav, sig, sr, format="WAV")
    
    # sf.write が MP3 書き出しで例外をスローするようにモック化
    original_sf_write = sf.write
    def mock_write(path, data, samplerate, **kwargs):
        if kwargs.get("format") == "MP3":
            raise RuntimeError("MP3 format not supported by this libsndfile build")
        return original_sf_write(path, data, samplerate, **kwargs)

    with patch("soundfile.write", side_effect=mock_write):
        res = process_and_export_bgm(
            input_wav_path=input_wav,
            output_path=output_mp3,
            target_duration_seconds=3.0,
            export_format="mp3"
        )
        
        # WAVフォールバックが発生したことを確認
        assert res["status"] == "success"
        assert res["format"] == "wav"
        # 拡張子が .wav に変わってファイルが生成されていること
        base, _ = os.path.splitext(output_mp3)
        fallback_path = base + ".wav"
        assert os.path.exists(fallback_path)
        assert not os.path.exists(output_mp3) # 元の .mp3 はできていないこと

def test_process_and_export_bgm_seamless(temp_audio_paths):
    input_wav, output_wav, _ = temp_audio_paths
    
    sr = 16000
    t = np.linspace(0.0, 1.0, sr, endpoint=False)
    sig = np.column_stack((0.5 * np.cos(2 * np.pi * 440 * t), 0.5 * np.cos(2 * np.pi * 440 * t)))
    sf.write(input_wav, sig, sr, format="WAV")
    
    # Run with 0 fades (seamless)
    res = process_and_export_bgm(
        input_wav_path=input_wav,
        output_path=output_wav,
        target_duration_seconds=3.0,
        export_format="wav",
        params={
            "fade_in_seconds": 0.0,
            "fade_out_seconds": 0.0
        }
    )
    
    assert res["status"] == "success"
    data, samplerate = sf.read(output_wav)
    
    # Assert start and end are NOT zero!
    assert data[0, 0] != 0.0
    assert data[-1, 0] != 0.0

