import os
import pytest
from app.presets.preset_manager import PresetManager
from app.composer.midi_schema import MidiComposition, MidiTrack, MidiNote
from app.api.handlers import WebviewApi

@pytest.fixture
def temp_presets_dir(tmp_path):
    return str(tmp_path / "presets")

def test_preset_manager_flow(temp_presets_dir):
    manager = PresetManager(presets_dir=temp_presets_dir)
    
    comp = MidiComposition(
        tempo_bpm=120,
        time_signature="4/4",
        key_mode="minor",
        duration_minutes=0.5,
        sections=[],
        tracks=[
            MidiTrack(
                track_id="t1",
                track_name="Melody",
                instrument="piano",
                channel=0,
                notes=[MidiNote(step=0, pitch=60, velocity=80, duration_steps=4)]
            )
        ]
    )

    params = {
        "description": "Sad piano loop",
        "tempo": 120,
        "key_mode": "minor",
        "duration": 0.5,
        "brightness": 0.3,
        "energy": 0.4,
        "density": 0.3,
        "reverb_space": 0.8
    }

    # 1. 保存
    key = manager.save_preset("Chill Lofi Loop", params, comp)
    assert key == "Chill Lofi Loop"
    
    json_path = os.path.join(temp_presets_dir, "Chill Lofi Loop.json")
    mid_path = os.path.join(temp_presets_dir, "Chill Lofi Loop.mid")
    assert os.path.exists(json_path)
    assert os.path.exists(mid_path)

    # 2. リスト取得
    list_items = manager.list_presets()
    assert len(list_items) == 1
    assert list_items[0]["key"] == "Chill Lofi Loop"
    assert list_items[0]["name"] == "Chill Lofi Loop"
    assert list_items[0]["params"]["description"] == "Sad piano loop"
    assert list_items[0]["has_composition"] is True

    # 3. 読み込み
    loaded = manager.load_preset("Chill Lofi Loop")
    assert loaded is not None
    assert loaded["name"] == "Chill Lofi Loop"
    assert loaded["params"]["tempo"] == 120
    assert loaded["composition"]["tempo_bpm"] == 120

    # 4. 削除
    deleted = manager.delete_preset("Chill Lofi Loop")
    assert deleted is True
    assert not os.path.exists(json_path)
    assert not os.path.exists(mid_path)

def test_webview_api_preset_handlers(temp_presets_dir, tmp_path):
    api = WebviewApi()
    # プリセットフォルダをテスト用ディレクトリに上書き
    api.preset_manager = PresetManager(presets_dir=temp_presets_dir)
    api.preview_wav_path = str(tmp_path / "temp_preview.wav")

    comp = MidiComposition(
        tempo_bpm=90,
        time_signature="4/4",
        key_mode="major",
        duration_minutes=0.5,
        sections=[],
        tracks=[]
    )
    api.last_composition = comp

    params = {
        "description": "Happy test beat",
        "tempo": 90,
        "key_mode": "major"
    }

    # 最後の結果がない状態での保存エラーチェック
    api.last_composition = None
    err_res = api.save_preset("Test", params)
    assert err_res["status"] == "error"

    # 有効な状態での保存
    api.last_composition = comp
    res = api.save_preset("Test Preset", params)
    assert res["status"] == "success"
    assert res["key"] == "Test Preset"

    # リスト表示
    presets_list = api.list_presets()
    assert len(presets_list) == 1
    assert presets_list[0]["key"] == "Test Preset"

    # 読み込み (読み込み時にプレビュー再生用 WAV が自動生成されること)
    # LiteRenderer.render が実際に呼び出される
    # (FluidSynth binaries があればOK、モック不要でテスト用 WAV が生成される)
    load_res = api.load_preset("Test Preset")
    assert load_res["status"] == "success"
    assert load_res["name"] == "Test Preset"
    assert len(load_res["tracks"]) == 0
    assert load_res["audio_url"] == "temp_preview.wav"
    assert os.path.exists(api.preview_wav_path) # 即座に生成されたWAVファイルが存在すること

    # 削除
    del_res = api.delete_preset("Test Preset")
    assert del_res["status"] == "success"
