import os
import pytest
from unittest.mock import MagicMock, patch, mock_open, ANY
from app.api.handlers import WebviewApi
from app.composer.midi_schema import MidiComposition

def test_get_app_settings():
    api = WebviewApi()
    
    # Mock settings file missing -> returns default settings
    with patch("os.path.exists", return_value=False):
        settings = api.get_app_settings()
        assert settings == {"auto_update_check": True}

    # Mock settings file exists -> returns loaded settings
    with patch("os.path.exists", return_value=True):
        m_open = mock_open(read_data='{"auto_update_check": false}')
        with patch("builtins.open", m_open):
            settings = api.get_app_settings()
            assert settings == {"auto_update_check": False}

def test_save_app_settings():
    api = WebviewApi()
    m_open = mock_open()
    
    with patch("os.makedirs") as mock_makedirs, patch("builtins.open", m_open):
        res = api.save_app_settings({"auto_update_check": False})
        assert res == {"status": "success"}
        mock_makedirs.assert_called_once()
        m_open.assert_called_once_with(api.settings_path, "w", encoding="utf-8")

@patch("app.api.handlers.json_to_midi")
def test_export_midi_file(mock_json_to_midi):
    api = WebviewApi()
    api.window = MagicMock()
    
    # No composition -> returns error
    api.last_composition = None
    res = api.export_midi_file()
    assert res["status"] == "error"
    
    # User cancels dialog -> returns cancelled
    api.last_composition = MagicMock(spec=MidiComposition)
    api.window.create_file_dialog.return_value = None
    res = api.export_midi_file()
    assert res == {"status": "cancelled"}
    
    # Dialog returns path -> writes to file
    api.window.create_file_dialog.return_value = "/path/to/midi.mid"
    mock_json_to_midi.return_value = b"midi_binary"
    m_open = mock_open()
    
    with patch("builtins.open", m_open), patch("os.makedirs"):
        res = api.export_midi_file()
        assert res == {"status": "success", "file_path": "/path/to/midi.mid"}
        m_open.assert_called_once_with("/path/to/midi.mid", "wb")
        mock_json_to_midi.assert_called_once_with(api.last_composition)

@patch("app.api.handlers.json_to_midi")
@patch("app.composer.midi_converter.midi_to_json")
@patch("pretty_midi.PrettyMIDI")
def test_import_midi_file(mock_pretty_midi, mock_midi_to_json, mock_json_to_midi):
    api = WebviewApi()
    api.window = MagicMock()
    api.lite_renderer = MagicMock()
    
    # User cancels dialog -> returns cancelled
    api.window.create_file_dialog.return_value = None
    res = api.import_midi_file()
    assert res == {"status": "cancelled"}
    
    # Dialog returns path -> reads and parses file
    api.window.create_file_dialog.return_value = "/path/to/midi.mid"
    mock_pm = MagicMock()
    mock_pm.get_end_time.return_value = 120.0 # 2 minutes
    mock_pretty_midi.return_value = mock_pm
    
    mock_composition = MagicMock(spec=MidiComposition)
    mock_composition.tempo_bpm = 90
    mock_composition.key_mode = "minor"
    mock_composition.duration_minutes = 2.0
    mock_composition.tracks = []
    mock_midi_to_json.return_value = mock_composition
    mock_json_to_midi.return_value = b"midi_binary"
    
    m_open = mock_open(read_data=b"midi_file_data")
    
    with patch("builtins.open", m_open):
        res = api.import_midi_file()
        assert res["status"] == "success"
        assert res["tempo_bpm"] == 90
        assert res["key_mode"] == "minor"
        assert res["duration_minutes"] == 2.0
        
        m_open.assert_called_once_with("/path/to/midi.mid", "rb")
        mock_midi_to_json.assert_called_once_with(b"midi_file_data", duration_minutes=2.0)
        api.lite_renderer.render.assert_called_once_with(b"midi_binary", api.preview_wav_path)

def test_get_ollama_candidates():
    api = WebviewApi()
    candidates = api.get_ollama_candidates()
    assert isinstance(candidates, list)
    assert len(candidates) > 0
    # verify schema of candidates
    for c in candidates:
        assert "name" in c
        assert "label" in c
        assert "is_recommended" in c
        assert "disabled" in c

