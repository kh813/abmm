import json
from typing import Dict, Any, Optional, List
from app.api.llm_client import OllamaClient
from app.composer.midi_schema import MidiComposition, MidiTrack, MidiNote, MidiSection

SYSTEM_PROMPT = """You are a high-level music composition assistant. Your job is to convert natural language descriptions and slider-based music parameters into a high-level Chord Plan JSON object.
You must output ONLY a valid JSON object matching the JSON schema, without any Markdown decoration, wrap-up text, or comments.

JSON Schema format:
{
  "tempo_bpm": int (60-120),
  "key_mode": "major" | "minor",
  "style": "lofi" | "jazz" | "pop" | "ambient" | "rock",
  "instruments": ["piano", "guitar", "bass", "drums"],
  "sections": [
    {
      "name": "intro" | "main" | "outro",
      "bars": int (usually 4 or 8),
      "chords": [string] (list of chord names matching the bars count, e.g. ["C", "F", "C", "G"])
    }
  ]
}

Rules for Chords selection:
1. For key_mode = "major": Use major chord progressions like ["C", "F", "C", "G"], ["C", "G", "Am", "F"], or ["F", "G", "C", "C"]. Dominant 7th/Maj7th chords like ["Cmaj7", "Fmaj7", "G7"] are also good.
2. For key_mode = "minor": Use minor chord progressions like ["Am", "Dm", "F", "E7"], ["Am", "F", "C", "G"], or ["Dm", "Am", "E7", "Am"].
3. Ensure the length of the "chords" list matches the "bars" count.
"""

FEW_SHOT_EXAMPLES = """
[Example 1]
Input Description: "A calm acoustic guitar piece for a peaceful afternoon"
Parameters: Tempo: 82 BPM, Key: Major, Duration: 1.0 minute
Output:
{
  "tempo_bpm": 82,
  "key_mode": "major",
  "style": "ambient",
  "instruments": ["piano", "guitar", "bass"],
  "sections": [
    {
      "name": "main",
      "bars": 8,
      "chords": ["Cmaj7", "Fmaj7", "Cmaj7", "G7", "Cmaj7", "Fmaj7", "Cmaj7", "Cmaj7"]
    }
  ]
}
"""

CHORD_MAP = {
    # Major chords
    "C": [60, 64, 67], "Db": [61, 65, 68], "D": [62, 66, 69], "Eb": [63, 67, 70],
    "E": [64, 68, 71], "F": [65, 69, 72], "F#": [66, 70, 73], "G": [67, 71, 74],
    "Ab": [68, 72, 75], "A": [69, 73, 76], "Bb": [58, 62, 65], "B": [59, 63, 66],
    
    # Minor chords
    "Cm": [60, 63, 67], "Dbm": [61, 64, 68], "Dm": [62, 65, 69], "Ebm": [63, 66, 70],
    "Em": [64, 67, 71], "Fm": [65, 68, 72], "F#m": [66, 69, 73], "Gm": [67, 70, 74],
    "Abm": [68, 71, 75], "Am": [57, 60, 64], "Bbm": [58, 61, 65], "Bm": [59, 62, 66],
    
    # Seventh chords (Major 7th)
    "Cmaj7": [60, 64, 67, 71], "Fmaj7": [65, 69, 72, 76], "Gmaj7": [67, 71, 74, 78],
    
    # Dominant seventh
    "C7": [60, 64, 67, 70], "D7": [62, 66, 69, 72], "E7": [64, 68, 71, 74],
    "F7": [65, 69, 72, 74], "G7": [67, 71, 74, 77], "A7": [69, 73, 76, 79],
    
    # Minor seventh
    "Cm7": [60, 63, 67, 70], "Dm7": [62, 65, 69, 72], "Em7": [64, 67, 71, 74],
    "Am7": [57, 60, 64, 67], "Bm7": [59, 62, 66, 72]
}

def get_chord_pitches(chord_name: str) -> list:
    """コード名から構成音のピッチリストを取得する"""
    chord_name = chord_name.strip()
    if chord_name in CHORD_MAP:
        return CHORD_MAP[chord_name]
    
    # 簡易解析フォールバック
    base_note = chord_name[0].upper()
    if len(chord_name) > 1 and chord_name[1] in ("#", "b"):
        base_note += chord_name[1]
        
    is_minor = "m" in chord_name and "maj" not in chord_name.lower()
    notes_offsets = [0, 3, 7] if is_minor else [0, 4, 7]
    base_pitches = {
        "C": 60, "C#": 61, "Db": 61, "D": 62, "D#": 63, "Eb": 63,
        "E": 64, "F": 65, "F#": 66, "Gb": 66, "G": 67, "G#": 68,
        "Ab": 68, "A": 69, "A#": 70, "Bb": 70, "B": 71
    }
    root = base_pitches.get(base_note, 60)
    return [root + offset for offset in notes_offsets]

def build_prompt(
    description: str,
    tempo_bpm: int,
    key_mode: str,
    duration_minutes: float,
    brightness: float = 0.5,
    energy: float = 0.5,
    density: float = 0.5,
    instruments: Optional[Dict[str, float]] = None
) -> str:
    inst_str = ""
    if instruments:
        inst_parts = [f"{k}: {v:.1f}" for k, v in instruments.items()]
        inst_str = ", ".join(inst_parts)
    else:
        inst_str = "Default composition"
        
    prompt = f"""Generate a structured Chord Plan JSON based on the following requirements:

User Description: "{description}"
Tempo: {tempo_bpm} BPM
Key Mode: {key_mode}
Duration: {duration_minutes} minutes
Brightness (Major/Minor balance): {brightness}
Energy (Dynamics/Volume): {energy}
Density (Note count): {density}
Instrument Balance Weights: {inst_str}

Please generate a corresponding JSON output.
{FEW_SHOT_EXAMPLES}
"""
    return prompt

def expand_chord_plan_to_midi(plan: Dict[str, Any], duration_minutes: float) -> MidiComposition:
    """高次のコード進行・構成プランを具体的なMIDIノート（MidiComposition）へ拡張・展開する"""
    tempo_bpm = int(plan.get("tempo_bpm", 80))
    key_mode = plan.get("key_mode", "major")
    style = plan.get("style", "lofi").lower()
    instruments = plan.get("instruments", ["piano", "guitar", "bass", "drums"])
    sections_plan = plan.get("sections", [])
    
    # 指定の再生時間をカバーするのに必要な総小節数を計算
    seconds_per_beat = 60.0 / tempo_bpm
    seconds_per_bar = seconds_per_beat * 4.0
    target_seconds = duration_minutes * 60.0
    total_bars_needed = max(4, int(target_seconds / seconds_per_bar))
    
    if not sections_plan:
        sections_plan = [
            {"name": "main", "bars": 4, "chords": ["C", "G", "Am", "F"] if key_mode == "major" else ["Am", "Dm", "F", "E"]}
        ]
        
    # 目標の小節数をカバーするよう、セクションプランを循環して割り当てる
    sections = []
    current_bar = 0
    section_index = 0
    
    while current_bar < total_bars_needed:
        sec_plan = sections_plan[section_index % len(sections_plan)]
        name = sec_plan.get("name", "main")
        bars = int(sec_plan.get("bars", 4))
        chords = sec_plan.get("chords", ["C"])
        
        # 最終小節の調整
        if current_bar + bars > total_bars_needed:
            bars = total_bars_needed - current_bar
            
        sections.append({
            "name": name,
            "start_bar": current_bar,
            "bars": bars,
            "chords": chords
        })
        current_bar += bars
        section_index += 1

    # 各楽器トラックごとのノート生成
    track_notes: Dict[str, List[MidiNote]] = {
        "piano": [],
        "guitar": [],
        "bass": [],
        "drums": []
    }
    
    for sec in sections:
        start_bar = sec["start_bar"]
        bars = sec["bars"]
        chords = sec["chords"]
        if not chords:
            chords = ["C"]
            
        for b in range(bars):
            bar_index = start_bar + b
            base_step = bar_index * 16
            
            # 各小節のコード進行
            chord_name = chords[b % len(chords)]
            pitches = get_chord_pitches(chord_name)
            
            # 1. ピアノ（コード・伴奏）トラック
            if "piano" in instruments:
                for p in pitches:
                    track_notes["piano"].append(MidiNote(step=base_step + 0, pitch=p, velocity=75, duration_steps=6))
                    track_notes["piano"].append(MidiNote(step=base_step + 8, pitch=p, velocity=70, duration_steps=6))
                    
            # 2. ギター（アルペジオ）トラック
            if "guitar" in instruments:
                # 16ビートアルペジオパターン
                extended_pitches = pitches * 2
                for step_offset, p in zip([0, 4, 8, 12], extended_pitches):
                    track_notes["guitar"].append(MidiNote(step=base_step + step_offset, pitch=p + 12, velocity=65, duration_steps=3))
                    
            # 3. ベーストラック
            if "bass" in instruments:
                root_pitch = pitches[0] - 24  # 2オクターブ低く
                track_notes["bass"].append(MidiNote(step=base_step + 0, pitch=root_pitch, velocity=85, duration_steps=8))
                track_notes["bass"].append(MidiNote(step=base_step + 8, pitch=root_pitch, velocity=80, duration_steps=8))
                
            # 4. ドラムトラック (Channel 9, Kick=36, Snare=38, Hihat=42)
            if "drums" in instruments:
                # 8ビート基本リズムパターン
                track_notes["drums"].append(MidiNote(step=base_step + 0, pitch=36, velocity=95, duration_steps=2))
                track_notes["drums"].append(MidiNote(step=base_step + 8, pitch=36, velocity=95, duration_steps=2))
                track_notes["drums"].append(MidiNote(step=base_step + 4, pitch=38, velocity=85, duration_steps=2))
                track_notes["drums"].append(MidiNote(step=base_step + 12, pitch=38, velocity=85, duration_steps=2))
                
                # クローズドハイハットの連続
                for h in range(8):
                    track_notes["drums"].append(MidiNote(step=base_step + (h * 2), pitch=42, velocity=70, duration_steps=1))

    # トラックオブジェクトの構築
    tracks = []
    if "piano" in instruments and track_notes["piano"]:
        tracks.append(MidiTrack(
            track_id="track_piano",
            track_name="Acoustic Piano",
            instrument="acoustic_piano",
            channel=0,
            notes=track_notes["piano"]
        ))
        
    if "guitar" in instruments and track_notes["guitar"]:
        tracks.append(MidiTrack(
            track_id="track_guitar",
            track_name="Acoustic Guitar",
            instrument="acoustic_guitar",
            channel=1,
            notes=track_notes["guitar"]
        ))
        
    if "bass" in instruments and track_notes["bass"]:
        tracks.append(MidiTrack(
            track_id="track_bass",
            track_name="Electric Bass",
            instrument="electric_bass",
            channel=2,
            notes=track_notes["bass"]
        ))
        
    if "drums" in instruments and track_notes["drums"]:
        tracks.append(MidiTrack(
            track_id="track_drums",
            track_name="Drums",
            instrument="synth_drum_kit",
            channel=9,
            notes=track_notes["drums"]
        ))
        
    final_sections = [MidiSection(name=sec["name"], start_bar=sec["start_bar"], bars=sec["bars"]) for sec in sections]
    
    return MidiComposition(
        tempo_bpm=tempo_bpm,
        time_signature="4/4",
        key_mode=key_mode,
        duration_minutes=duration_minutes,
        sections=final_sections,
        tracks=tracks
    )

def generate_midi_json(
    client: OllamaClient,
    description: str,
    tempo_bpm: int,
    key_mode: str,
    duration_minutes: float,
    brightness: float = 0.5,
    energy: float = 0.5,
    density: float = 0.5,
    instruments: Optional[Dict[str, float]] = None,
    max_retries: int = 2
) -> MidiComposition:
    """
    Ollama経由でLLMに高次のコード構成案を生成させ、それをPython側で展開して完全なMidiCompositionを構築する。
    """
    prompt = build_prompt(
        description=description,
        tempo_bpm=tempo_bpm,
        key_mode=key_mode,
        duration_minutes=duration_minutes,
        brightness=brightness,
        energy=energy,
        density=density,
        instruments=instruments
    )

    last_error = ""
    last_response = ""

    for attempt in range(max_retries + 1):
        try:
            current_prompt = prompt
            if attempt > 0:
                current_prompt = (
                    f"{prompt}\n\n"
                    f"CRITICAL FIX NEEDED:\n"
                    f"Your previous response failed validation with error: {last_error}\n"
                    f"Your previous response was:\n{last_response}\n\n"
                    f"Please fix the error and output ONLY the valid JSON object conforming strictly to the schema."
                )

            # JSON形式でのLLM生成
            response_text = client.generate(current_prompt, system_prompt=SYSTEM_PROMPT, format_json=True)
            last_response = response_text

            clean_text = response_text.strip()
            if clean_text.startswith("```"):
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                else:
                    clean_text = clean_text[3:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()

            plan = json.loads(clean_text)
            
            # 展開処理の実行
            composition = expand_chord_plan_to_midi(plan, duration_minutes)
            return composition

        except Exception as e:
            last_error = str(e)
            print(f"[Ollama Plan Generation] Attempt {attempt + 1} failed: {last_error}")

    # フォールバック
    print("[Ollama Plan Generation] All attempts failed. Falling back to default Chord Plan.")
    default_plan = {
        "tempo_bpm": tempo_bpm,
        "key_mode": key_mode,
        "style": "lofi",
        "instruments": ["piano", "guitar", "bass", "drums"],
        "sections": [
            {"name": "main", "bars": 4, "chords": ["C", "G", "Am", "F"] if key_mode == "major" else ["Am", "Dm", "F", "E"]}
        ]
    }
    return expand_chord_plan_to_midi(default_plan, duration_minutes)
