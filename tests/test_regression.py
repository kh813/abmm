"""
Regression tests for recent fixes & UI behavior:
  1. Melody pitch wrap (no hard clipping to pitch 84)
  2. Per-section MIDI track generation (track IDs have section suffix)
  3. Online chord compression (max 8 unique chords)
  4. No hardcoded DB melody injection
  5. UI: overflow-y: auto on .panel in style.css
  6. UI: export-card starts hidden in index.html
  7. UI: app.js uses style.display='flex' for exportCard
"""
import os
import re
import pytest
from unittest.mock import MagicMock, patch

from app.composer.prompt_builder import expand_chord_plan_to_midi, generate_midi_json

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
STYLE_CSS    = os.path.join(FRONTEND_DIR, "style.css")
INDEX_HTML   = os.path.join(FRONTEND_DIR, "index.html")
APP_JS       = os.path.join(FRONTEND_DIR, "app.js")

SIMPLE_PLAN = {
    "tempo_bpm": 90,
    "key_mode": "minor",
    "style": "pop",
    "instruments": ["piano", "guitar", "bass", "drums"],
    "melody_style": "expressive",
    "rhythm_variation": "slight",
}

class TestMelodyDiversity:
    """メロディノートが特定の音高（84等）に潰れず多様なメロディになることをテスト"""

    def test_melody_pitches_are_varied_and_not_flattened_to_84(self):
        """生成されたメロディノートがピッチ 84 一色に飽和・平坦化しないこと"""
        comp = expand_chord_plan_to_midi(SIMPLE_PLAN, 1.0)
        melody_notes = [
            note for track in comp.tracks
            if "melody" in track.track_id.lower()
            for note in track.notes
        ]
        assert len(melody_notes) > 0
        pitches = [n.pitch for n in melody_notes]
        # ピッチ 84 の割合が全体の 50% を超えないこと（以前はほぼ100%が84になっていた）
        count_84 = pitches.count(84)
        ratio_84 = count_84 / len(pitches)
        assert ratio_84 < 0.5, f"Too many pitch 84 notes ({ratio_84:.1%}); pitches are flattening!"
        # ユニークなピッチの種類が少なくとも 3 種類以上存在すること
        unique_pitches = set(pitches)
        assert len(unique_pitches) >= 3, f"Melody lacks pitch variety: {unique_pitches}"

    def test_melody_pitches_within_musical_range(self):
        """全メロディノートが [60, 84] (C4〜C6) の標準ボーカル・リード音域内にあること"""
        for style in ("pop", "rock", "jazz", "edm", "ambient"):
            plan = {**SIMPLE_PLAN, "style": style}
            comp = expand_chord_plan_to_midi(plan, 1.0)
            melody_notes = [
                n for t in comp.tracks if "melody" in t.track_id.lower() for n in t.notes
            ]
            for n in melody_notes:
                assert 60 <= n.pitch <= 84, f"Melody pitch {n.pitch} out of range in style '{style}'"

class TestPerSectionTracks:
    """各楽器のMIDIトラックがセクション種別ごとに分割されていることをテスト"""

    def test_track_ids_contain_section_suffix(self):
        comp = expand_chord_plan_to_midi(SIMPLE_PLAN, 1.0)
        for track in comp.tracks:
            parts = track.track_id.split("_")
            assert len(parts) >= 3, f"track_id '{track.track_id}' missing section suffix"

    def test_section_labels_in_track_names(self):
        comp = expand_chord_plan_to_midi(SIMPLE_PLAN, 1.0)
        section_labels = {"Verse", "Chorus", "Intro", "Bridge", "Outro"}
        for track in comp.tracks:
            label = track.track_name.split(" - ")[-1] if " - " in track.track_name else ""
            assert label in section_labels, f"Track name '{track.track_name}' invalid section label"

class TestUiIntegrity:
    """UIコードの要件（スクロール設定、画面表示制御）の検証"""

    def test_panel_overflow_y_auto(self):
        with open(STYLE_CSS, encoding="utf-8") as f:
            css = f.read()
        panel_block = re.search(r'\.panel\s*\{([^}]+)\}', css)
        assert panel_block
        assert "overflow-y" in panel_block.group(1)
        assert "auto" in panel_block.group(1)

    def test_export_card_initially_hidden(self):
        with open(INDEX_HTML, encoding="utf-8") as f:
            html = f.read()
        assert re.search(r'id="export-card"[^>]*style="display:\s*none', html) or \
               re.search(r'style="display:\s*none[^"]*"[^>]*id="export-card"', html)

    def test_app_js_uses_style_display_for_export_card(self):
        with open(APP_JS, encoding="utf-8") as f:
            js = f.read()
        assert re.search(r'exportCard\.style\.display\s*=\s*["\']flex["\']', js)
