import os
import pytest
from unittest.mock import patch, MagicMock
from app.render.model_manager import ModelManager
from app.render.renderer_neural import NeuralRenderer
from app.api.handlers import trim_composition_to_seconds
from app.composer.midi_schema import MidiComposition, MidiTrack, MidiNote

@pytest.fixture
def temp_cache_dir(tmp_path):
    return str(tmp_path / "cache")

def test_model_manager_paths(temp_cache_dir):
    manager = ModelManager(cache_dir=temp_cache_dir)
    standard_path = manager.get_model_path("Standard")
    assert standard_path == os.path.join(temp_cache_dir, "Standard", "model.safetensors")

    with pytest.raises(ValueError):
        manager.get_model_path("NonExistentTier")

def test_model_manager_is_downloaded(temp_cache_dir):
    manager = ModelManager(cache_dir=temp_cache_dir)
    # Initially False
    assert not manager.is_model_downloaded("Standard")
    # Lite is always True
    assert manager.is_model_downloaded("Lite")

    # Create dummy model file
    model_path = manager.get_model_path("Standard")
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    with open(model_path, "wb") as f:
        f.write(b"0" * (1024 * 1024 + 1))  # 1MB + 1B

    assert manager.is_model_downloaded("Standard")

@patch("urllib.request.urlopen")
def test_model_manager_download(mock_urlopen, temp_cache_dir):
    manager = ModelManager(cache_dir=temp_cache_dir)
    
    # Mock URL request
    mock_headers = MagicMock()
    mock_headers.get.return_value = "100" # content-length
    mock_response = MagicMock()
    mock_response.headers = mock_headers
    mock_response.read.side_effect = [b"a" * 50, b"b" * 50, b""] # 2 blocks
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    progress_vals = []
    def prog_cb(p):
        progress_vals.append(p)

    success = manager.download_model("Standard", progress_callback=prog_cb)
    assert success
    assert len(progress_vals) == 2
    assert progress_vals == [0.5, 1.0]
    assert os.path.exists(manager.get_model_path("Standard"))

@patch("app.render.renderer_lite.LiteRenderer.render")
def test_neural_renderer_fallback(mock_lite_render, temp_cache_dir):
    """
    モデルがダウンロードされていない場合、SoundFont (LiteRenderer) に
    自動でフォールバックすることを検証する。
    """
    manager = ModelManager(cache_dir=temp_cache_dir)
    renderer = NeuralRenderer(manager)

    # Standard model is not downloaded
    assert not manager.is_model_downloaded("Standard")

    renderer.render(b"midi", "output.wav", {"model_tier": "Standard"})

    # Ensure it forwarded the call to LiteRenderer.render
    mock_lite_render.assert_called_once_with(b"midi", "output.wav", {"model_tier": "Standard"})

@patch("app.render.renderer_lite.LiteRenderer.render")
def test_neural_renderer_cancellation(mock_lite_render, temp_cache_dir):
    """
    レンダリング中にキャンセルシグナルが入ると、処理が中断され
    InterruptedError を投げることを検証する。
    """
    manager = ModelManager(cache_dir=temp_cache_dir)
    
    # Create fake model file so that it executes neural path instead of fallback
    model_path = manager.get_model_path("Standard")
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    with open(model_path, "wb") as f:
        f.write(b"0" * (1024 * 1024 + 1))
        
    renderer = NeuralRenderer(manager)
    
    # 進捗コールバック内でキャンセルを実行する
    def progress_callback(p):
        if p > 0.0:
            renderer.cancel()
    
    with pytest.raises(InterruptedError):
        renderer.render(
            b"midi", 
            "output.wav", 
            {
                "model_tier": "Standard",
                "progress_callback": progress_callback
            }
        )

    # レンダリング完了のファイル出力は行われない
    mock_lite_render.assert_not_called()

def test_trim_composition():
    # Setup composition of 1.0 minute with notes up to step 60
    comp = MidiComposition(
        tempo_bpm=60, # 1 step = 0.25 seconds
        time_signature="4/4",
        key_mode="major",
        duration_minutes=1.0,
        sections=[],
        tracks=[
            MidiTrack(
                track_id="t1",
                track_name="Melody",
                instrument="piano",
                channel=0,
                notes=[
                    MidiNote(step=0, pitch=60, velocity=80, duration_steps=4), # starts at 0.0s, ends at 1.0s
                    MidiNote(step=80, pitch=64, velocity=80, duration_steps=4)  # starts at 20.0s, ends at 21.0s
                ]
            )
        ]
    )

    # Trim to 10 seconds (notes starting after step 40 should be deleted)
    trimmed = trim_composition_to_seconds(comp, 10.0)
    assert trimmed.duration_minutes == 10.0 / 60.0
    assert len(trimmed.tracks[0].notes) == 1
    assert trimmed.tracks[0].notes[0].step == 0
    assert trimmed.tracks[0].notes[0].pitch == 60
