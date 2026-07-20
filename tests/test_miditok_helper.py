import pytest
from app.composer.miditok_helper import is_miditok_available, get_default_tokenizer, midi_bytes_to_tokens
from app.composer.midi_schema import MidiComposition, MidiTrack, MidiNote
from app.composer.midi_converter import json_to_midi

def test_miditok_availability():
    # 利用可能フラグの確認
    available = is_miditok_available()
    assert isinstance(available, bool)

def test_get_default_tokenizer():
    tokenizer = get_default_tokenizer()
    if is_miditok_available():
        assert tokenizer is not None
    else:
        assert tokenizer is None

def test_midi_bytes_to_tokens():
    if not is_miditok_available():
        pytest.skip("MidiTok is not installed in this environment.")
        
    comp = MidiComposition(
        tempo_bpm=120,
        duration_minutes=5.0,
        tracks=[
            MidiTrack(
                track_id="t1",
                track_name="Piano",
                instrument="acoustic_grand_piano",
                channel=0,
                notes=[
                    MidiNote(step=0, pitch=60, velocity=90, duration_steps=4),
                    MidiNote(step=4, pitch=64, velocity=90, duration_steps=4),
                ]
            )
        ]
    )
    midi_bytes = json_to_midi(comp)
    tokens = midi_bytes_to_tokens(midi_bytes)
    assert isinstance(tokens, list)
    assert len(tokens) > 0
