import pytest
from pydantic import ValidationError
from app.composer.midi_schema import MidiComposition, MidiTrack, MidiNote, MidiSection
from app.composer.midi_converter import (
    steps_to_seconds,
    seconds_to_steps,
    json_to_midi,
    midi_to_json
)

def test_steps_to_seconds():
    # 82 BPM: 1 step = 15.0 / 82 = 0.1829268... seconds
    assert steps_to_seconds(0, 82) == 0.0
    assert pytest.approx(steps_to_seconds(4, 60)) == 1.0  # 60 BPM: 4 steps = 1 beat = 1.0 second
    assert pytest.approx(steps_to_seconds(16, 120)) == 2.0 # 120 BPM: 16 steps = 4 beats = 2.0 seconds

    with pytest.raises(ValueError):
        steps_to_seconds(4, 0)
    with pytest.raises(ValueError):
        steps_to_seconds(4, -10)

def test_seconds_to_steps():
    # 60 BPM: 1 step = 0.25 seconds
    assert seconds_to_steps(0.0, 60) == 0
    assert seconds_to_steps(1.0, 60) == 4
    assert seconds_to_steps(0.24, 60) == 1
    assert seconds_to_steps(0.38, 60) == 2  # round to nearest

    with pytest.raises(ValueError):
        seconds_to_steps(1.0, 0)

def test_midi_schema_validation():
    # Valid composition
    valid_data = {
        "tempo_bpm": 120,
        "time_signature": "4/4",
        "key_mode": "minor",
        "duration_minutes": 2.5,
        "sections": [
            {"name": "intro", "start_bar": 0, "bars": 4}
        ],
        "tracks": [
            {
                "track_id": "track_1",
                "track_name": "Melody",
                "instrument": "acoustic_grand_piano",
                "channel": 0,
                "notes": [
                    {"step": 0, "pitch": 60, "velocity": 90, "duration_steps": 4}
                ]
            }
        ]
    }
    comp = MidiComposition(**valid_data)
    assert comp.tempo_bpm == 120
    assert comp.tracks[0].notes[0].pitch == 60

    # Invalid time signature
    invalid_data_ts = valid_data.copy()
    invalid_data_ts["time_signature"] = "3/4"
    with pytest.raises(ValidationError):
        MidiComposition(**invalid_data_ts)

    # Invalid key mode
    invalid_data_key = valid_data.copy()
    invalid_data_key["key_mode"] = "dorian"
    with pytest.raises(ValidationError):
        MidiComposition(**invalid_data_key)

    # Out of bounds pitch
    invalid_data_pitch = valid_data.copy()
    invalid_data_pitch["tracks"] = [
        {
            "track_id": "track_1",
            "track_name": "Melody",
            "instrument": "acoustic_grand_piano",
            "channel": 0,
            "notes": [
                {"step": 0, "pitch": 128, "velocity": 90, "duration_steps": 4}  # 128 is invalid
            ]
        }
    ]
    with pytest.raises(ValidationError):
        MidiComposition(**invalid_data_pitch)

from unittest.mock import patch

@patch("random.randint", return_value=0)
@patch("random.uniform", return_value=0.0)
def test_bidirectional_conversion(mock_uniform, mock_randint):
    # Simple composition setup
    comp = MidiComposition(
        tempo_bpm=80,
        time_signature="4/4",
        key_mode="major",
        duration_minutes=1.0,
        sections=[MidiSection(name="main", start_bar=0, bars=4)],
        tracks=[
            MidiTrack(
                track_id="track_1",
                track_name="Piano",
                instrument="acoustic_piano",
                channel=0,
                muted=False,
                notes=[
                    MidiNote(step=0, pitch=60, velocity=80, duration_steps=4),
                    MidiNote(step=4, pitch=64, velocity=90, duration_steps=4),
                    MidiNote(step=8, pitch=67, velocity=100, duration_steps=8),
                ]
            ),
            MidiTrack(
                track_id="track_2",
                track_name="Drums",
                instrument="synth_drum_kit",
                channel=9,
                muted=False,
                notes=[
                    MidiNote(step=0, pitch=36, velocity=120, duration_steps=2),
                    MidiNote(step=8, pitch=38, velocity=110, duration_steps=2),
                ]
            )
        ]
    )

    # Convert to MIDI bytes
    midi_bytes = json_to_midi(comp)
    assert isinstance(midi_bytes, bytes)
    assert len(midi_bytes) > 0

    # Convert back to MidiComposition
    parsed_comp = midi_to_json(midi_bytes, duration_minutes=1.0)

    # Verify properties
    assert parsed_comp.tempo_bpm == comp.tempo_bpm
    assert len(parsed_comp.tracks) == len(comp.tracks)

    # Verify Piano track
    piano_track = next(t for t in parsed_comp.tracks if t.channel == 0)
    assert len(piano_track.notes) == 3
    assert piano_track.notes[0].pitch == 60
    assert piano_track.notes[0].step == 0
    assert piano_track.notes[0].velocity == 80
    assert piano_track.notes[0].duration_steps == 4

    # Verify Drums track
    drum_track = next(t for t in parsed_comp.tracks if t.channel == 9)
    assert len(drum_track.notes) == 2
    assert drum_track.notes[0].pitch == 36
    assert drum_track.notes[0].step == 0
    assert drum_track.notes[0].velocity == 120
