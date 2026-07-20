import pytest
from app.composer.prompt_builder import parse_dsl_description, generate_midi_json, expand_chord_plan_to_midi
from app.render.hardware_detect import detect_hardware_spec, get_total_memory_gb
from unittest.mock import MagicMock, patch

def test_parse_dsl_description():
    # Standard format
    desc = "A nice piece [Am7 -> D7 -> Gmaj7 -> Cmaj7 : 4 bars : style=jazz]"
    res = parse_dsl_description(desc)
    assert res is not None
    assert res["custom_chords"] == ["Am7", "D7", "Gmaj7", "Cmaj7"]
    assert res["custom_bars"] == 4
    assert res["style"] == "jazz"

    # Space separators
    desc2 = "[C F G C]"
    res2 = parse_dsl_description(desc2)
    assert res2 is not None
    assert res2["custom_chords"] == ["C", "F", "G", "C"]
    assert "custom_bars" not in res2

    # Empty
    assert parse_dsl_description("Just natural language without brackets") is None

def test_extract_chords_from_raw_tab():
    raw_tab = """
    [Intro]
    Em7   G   Dsus4   A7sus4
    
    [Verse 1]
    Em7          G
    Today is gonna be the day that they're
    Dsus4             A7sus4
    gonna throw it back to you
    """
    res = parse_dsl_description(raw_tab)
    assert res is not None
    assert res["custom_chords"] == ["Em7", "G", "Dsus4", "A7sus4", "Em7", "G", "Dsus4", "A7sus4"]

    # Test style name noise word filtering (should not extract "pop" or "lofi" as chords)
    noise_tab = "Here is a list of styles: [pop] [lofi] which are not chords"
    assert parse_dsl_description(noise_tab) is None

    # Test sentence with accidental chord-like words (should fail ratio threshold 0.6)
    sentence_with_a = "A major breakthrough happened in the morning and we had Am coffee."
    assert parse_dsl_description(sentence_with_a) is None

def test_dsl_midi_generation():
    client = MagicMock()
    # If DSL is detected, client.generate should NOT be called at all!
    desc = "[Am7 D7 Gmaj7 Cmaj7 : 4 bars : style=jazz]"
    composition = generate_midi_json(
        client=client,
        description=desc,
        tempo_bpm=90,
        key_mode="minor",
        duration_minutes=1.0,
        instruments={"piano": 1.0, "guitar": 1.0, "bass": 0.0, "drums": 0.0}
    )
    
    # Verify no LLM call was made
    client.generate.assert_not_called()
    
    assert composition.tempo_bpm == 90
    # piano and guitar should be included, bass and drums skipped
    track_ids = [t.track_id for t in composition.tracks]
    assert "track_piano" in track_ids
    assert "track_guitar" in track_ids
    assert "track_bass" not in track_ids

def test_local_song_database_matching():
    client = MagicMock()
    composition = generate_midi_json(
        client=client,
        description="Arrange Oasis's Live Forever in EDM style",
        tempo_bpm=120,
        key_mode="major",
        duration_minutes=1.0,
        genre="edm"
    )
    client.generate.assert_not_called()
    assert composition.tempo_bpm == 120

def test_online_song_chords_search_fallback():
    client = MagicMock()
    with patch("app.composer.prompt_builder.search_chords_online") as mock_search:
        mock_search.return_value = ["C", "G", "Am", "F"]
        composition = generate_midi_json(
            client=client,
            description="Arrange Adele's Someone Like You",
            tempo_bpm=80,
            key_mode="major",
            duration_minutes=1.0,
            genre="pop"
        )
        mock_search.assert_called_once_with("Adele's Someone Like You")
        client.generate.assert_not_called()
        assert composition.tempo_bpm == 80

def test_detect_hardware_spec_llms():
    specs = detect_hardware_spec()
    assert "recommended_llm_models" in specs
    assert isinstance(specs["recommended_llm_models"], list)
    assert len(specs["recommended_llm_models"]) > 0

def test_genre_and_progression_overrides():
    client = MagicMock()
    # Test fallback flow with explicit genre and progression
    composition = generate_midi_json(
        client=client,
        description="Write a song",
        tempo_bpm=80,
        key_mode="major",
        duration_minutes=1.0,
        genre="rock",
        chord_progression="royal_road"
    )
    assert len(composition.tracks) > 0
    piano_track = next(t for t in composition.tracks if "piano" in t.track_name.lower())
    assert len(piano_track.notes) > 0
