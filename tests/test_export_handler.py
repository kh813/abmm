import pytest
import json
from unittest.mock import MagicMock, patch
from app.api.handlers import WebviewApi
from app.composer.midi_schema import MidiComposition

def test_select_export_file():
    api = WebviewApi()
    api.window = MagicMock()
    
    # Mock file dialog response as a string path
    api.window.create_file_dialog.return_value = "/path/to/exported_file.wav"
    
    path = api.select_export_file("wav")
    assert path == "/path/to/exported_file.wav"
    api.window.create_file_dialog.assert_called_once_with(
        dialog_type=1,
        file_types=('WAV Files (*.wav)',),
        save_filename='background_music.wav'
    )

def test_select_export_file_tuple():
    api = WebviewApi()
    api.window = MagicMock()
    
    # Mock file dialog response as a tuple/list path
    api.window.create_file_dialog.return_value = ["/path/to/exported_file.mp3"]
    
    path = api.select_export_file("mp3")
    assert path == "/path/to/exported_file.mp3"

def test_select_export_file_none():
    api = WebviewApi()
    api.window = MagicMock()
    api.window.create_file_dialog.return_value = None
    
    path = api.select_export_file("wav")
    assert path is None

@patch("app.api.handlers.process_and_export_bgm")
@patch("app.api.handlers.json_to_midi")
def test_async_export_worker(mock_json_to_midi, mock_process_export):
    api = WebviewApi()
    api.window = MagicMock()
    api.neural_renderer = MagicMock() # Mock neural renderer to prevent actual FluidSynth rendering
    
    # Set mock composition
    mock_comp = MagicMock(spec=MidiComposition)
    mock_comp.tracks = []
    api.last_composition = mock_comp
    
    mock_json_to_midi.return_value = b"midi_binary_bytes"
    
    params = {
        "export_path": "/path/to/file.wav",
        "export_duration": 5.0,
        "export_format": "wav",
        "model_tier": "Standard"
    }
    
    # Call export worker directly synchronously for testing
    api._async_export_worker(params)
    
    # Check that MIDI binary was generated
    mock_json_to_midi.assert_called_once_with(mock_comp)
    
    # Verify neural renderer render was called
    api.neural_renderer.render.assert_called_once()
    
    # Check that process_and_export_bgm was called
    mock_process_export.assert_called_once_with(
        input_wav_path=api.temp_export_wav_path,
        output_path="/path/to/file.wav",
        target_duration_seconds=300.0,
        export_format="wav"
    )
    
    # Verify evaluate_js was called to notify front-end of completion
    api.window.evaluate_js.assert_any_call('onExportComplete({"status": "success", "export_path": "/path/to/file.wav"})')
