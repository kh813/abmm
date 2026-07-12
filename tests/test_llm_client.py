import json
import urllib.error
from unittest.mock import MagicMock, patch
import pytest
from pydantic import ValidationError

from app.api.llm_client import OllamaClient
from app.composer.prompt_builder import (
    build_prompt,
    get_default_midi,
    generate_midi_json
)
from app.composer.midi_schema import MidiComposition

# Valid MIDI JSON template for mocking
VALID_RESPONSE = {
    "tempo_bpm": 90,
    "time_signature": "4/4",
    "key_mode": "minor",
    "duration_minutes": 2.0,
    "sections": [
        {"name": "intro", "start_bar": 0, "bars": 4}
    ],
    "tracks": [
        {
            "track_id": "track_1",
            "track_name": "Piano",
            "instrument": "acoustic_piano",
            "channel": 0,
            "muted": False,
            "notes": [
                {"step": 0, "pitch": 60, "velocity": 80, "duration_steps": 4}
            ]
        }
    ]
}

@pytest.fixture
def mock_client():
    client = OllamaClient(base_url="http://localhost:11434", model="test-model")
    return client

def test_ollama_client_success(mock_client):
    # Mock urllib.request.urlopen
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"response": '{"status": "ok"}'}).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        res = mock_client.generate("hello", system_prompt="sys", format_json=True)
        assert res == '{"status": "ok"}'
        
        # Verify the arguments sent to urlopen
        mock_urlopen.assert_called_once()
        called_req = mock_urlopen.call_args[0][0]
        assert called_req.full_url == "http://localhost:11434/api/generate"
        assert called_req.get_header("Content-type") == "application/json"

def test_ollama_client_connection_error(mock_client):
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        with pytest.raises(RuntimeError) as exc_info:
            mock_client.generate("hello")
        assert "Ollama APIへの接続に失敗しました" in str(exc_info.value)

def test_build_prompt():
    prompt = build_prompt(
        description="Relaxing music",
        tempo_bpm=80,
        key_mode="minor",
        duration_minutes=3.0,
        brightness=0.3,
        energy=0.4,
        density=0.5,
        instruments={"piano": 0.8, "guitar": 0.2}
    )
    assert "Relaxing music" in prompt
    assert "80 BPM" in prompt
    assert "minor" in prompt
    assert "piano: 0.8, guitar: 0.2" in prompt

def test_get_default_midi():
    default_major = get_default_midi(82, "major", 5.0)
    assert isinstance(default_major, MidiComposition)
    assert default_major.tempo_bpm == 82
    assert default_major.key_mode == "major"
    assert len(default_major.tracks) == 2
    assert default_major.tracks[0].track_name == "Acoustic Piano"
    assert default_major.tracks[1].track_name == "Drums"

    default_minor = get_default_midi(75, "minor", 1.5)
    assert default_minor.tempo_bpm == 75
    assert default_minor.key_mode == "minor"
    # Ensure notes exist
    assert len(default_minor.tracks[0].notes) > 0

@patch.object(OllamaClient, "generate")
def test_generate_midi_json_success(mock_generate, mock_client):
    # Setup mock to return a valid JSON string
    mock_generate.return_value = json.dumps(VALID_RESPONSE)
    
    comp = generate_midi_json(
        client=mock_client,
        description="happy ambient",
        tempo_bpm=90,
        key_mode="minor",
        duration_minutes=2.0
    )
    
    assert isinstance(comp, MidiComposition)
    assert comp.tempo_bpm == 90
    assert comp.tracks[0].notes[0].pitch == 60
    assert mock_generate.call_count == 1

@patch.object(OllamaClient, "generate")
def test_generate_midi_json_retry_on_parse_error(mock_generate, mock_client):
    # First call: returns invalid JSON
    # Second call: returns valid JSON
    mock_generate.side_effect = [
        "invalid json string",
        json.dumps(VALID_RESPONSE)
    ]
    
    comp = generate_midi_json(
        client=mock_client,
        description="test retry",
        tempo_bpm=90,
        key_mode="minor",
        duration_minutes=2.0,
        max_retries=2
    )
    
    assert isinstance(comp, MidiComposition)
    assert comp.tempo_bpm == 90
    assert mock_generate.call_count == 2
    # Ensure the second prompt contained retry warning
    second_call_prompt = mock_generate.call_args_list[1][0][0]
    assert "CRITICAL FIX NEEDED" in second_call_prompt

@patch.object(OllamaClient, "generate")
def test_generate_midi_json_retry_on_validation_error(mock_generate, mock_client):
    # First call: returns JSON with invalid pitch (128)
    invalid_response = VALID_RESPONSE.copy()
    # Deep copy notes to modify
    invalid_notes = [{"step": 0, "pitch": 128, "velocity": 80, "duration_steps": 4}]
    invalid_tracks = [VALID_RESPONSE["tracks"][0].copy()]
    invalid_tracks[0]["notes"] = invalid_notes
    invalid_response["tracks"] = invalid_tracks

    # Second call: returns valid JSON
    mock_generate.side_effect = [
        json.dumps(invalid_response),
        json.dumps(VALID_RESPONSE)
    ]
    
    comp = generate_midi_json(
        client=mock_client,
        description="test validation retry",
        tempo_bpm=90,
        key_mode="minor",
        duration_minutes=2.0,
        max_retries=2
    )
    
    assert isinstance(comp, MidiComposition)
    assert comp.tracks[0].notes[0].pitch == 60
    assert mock_generate.call_count == 2

@patch.object(OllamaClient, "generate")
def test_generate_midi_json_fallback_after_all_fails(mock_generate, mock_client):
    # All calls fail (invalid JSON)
    mock_generate.return_value = "completely broken response"
    
    comp = generate_midi_json(
        client=mock_client,
        description="test fallback",
        tempo_bpm=70,
        key_mode="major",
        duration_minutes=4.0,
        max_retries=2
    )
    
    assert isinstance(comp, MidiComposition)
    # Check that it returns get_default_midi outputs
    assert comp.tempo_bpm == 70
    assert comp.key_mode == "major"
    assert len(comp.tracks) == 2
    assert comp.tracks[0].track_name == "Acoustic Piano"
    assert mock_generate.call_count == 3  # Initial + 2 retries
