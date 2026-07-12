import json
from typing import Dict, Any, Optional, List
from app.api.llm_client import OllamaClient
from app.composer.midi_schema import MidiComposition, MidiTrack, MidiNote, MidiSection

SYSTEM_PROMPT = """You are a structured music composition assistant. Your job is to convert natural language descriptions and slider-based music parameters into a structured MIDI representation in JSON format.
You must output ONLY a JSON object matching the JSON schema, without any Markdown decoration, wrap-up text, or comments.

JSON Schema format:
{
  "tempo_bpm": int (60-120),
  "time_signature": "4/4",
  "key_mode": "major" | "minor",
  "duration_minutes": float,
  "sections": [
    {"name": str, "start_bar": int, "bars": int}
  ],
  "tracks": [
    {
      "track_id": str,
      "track_name": str,
      "instrument": str,
      "channel": int (0-15, where channel 9 is reserved for drums),
      "muted": bool,
      "notes": [
        {"step": int, "pitch": int, "velocity": int, "duration_steps": int}
      ]
    }
  ]
}

Rules:
1. 1 bar = 16 steps (4/4 time signature).
2. The `step` of a note is the start step in the timeline. 0 is the start of the song.
3. Keep the notes list sorted by step and pitch.
4. Set channel 9 for drum tracks and use program numbers/instrument names suitable for percussion.
5. Strictly instrumental music. Do not generate vocal tracks or lyrics.
6. Make sure notes step and durations make musical sense (e.g., chords, melodies, or drum beats matching the specified tempo and energy).
7. Do not wrap the JSON output in markdown code blocks like ```json ... ```. Output raw JSON.
"""

FEW_SHOT_EXAMPLES = """
[Example 1]
Input Description: "A calm acoustic guitar piece for a peaceful afternoon"
Parameters: Tempo: 82 BPM, Key: Major, Duration: 1.0 minute, Energy: 0.3
Output:
{
  "tempo_bpm": 82,
  "time_signature": "4/4",
  "key_mode": "major",
  "duration_minutes": 1.0,
  "sections": [
    {"name": "main", "start_bar": 0, "bars": 8}
  ],
  "tracks": [
    {
      "track_id": "track_1",
      "track_name": "Acoustic Guitar",
      "instrument": "acoustic_guitar",
      "channel": 0,
      "muted": false,
      "notes": [
        {"step": 0, "pitch": 57, "velocity": 70, "duration_steps": 4},
        {"step": 0, "pitch": 60, "velocity": 65, "duration_steps": 4},
        {"step": 4, "pitch": 64, "velocity": 75, "duration_steps": 4},
        {"step": 8, "pitch": 62, "velocity": 70, "duration_steps": 8}
      ]
    }
  ]
}
"""

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
    """
    ユーザー指示とパラメータからLLMプロンプトを構築する。
    """
    inst_str = ""
    if instruments:
        inst_parts = [f"{k}: {v:.1f}" for k, v in instruments.items()]
        inst_str = ", ".join(inst_parts)
    else:
        inst_str = "Default composition"
        
    prompt = f"""Generate a structured MIDI JSON composition based on the following requirements:

User Description: "{description}"
Tempo: {tempo_bpm} BPM
Key Mode: {key_mode}
Duration: {duration_minutes} minutes
Brightness (Major/Minor balance): {brightness}
Energy (Dynamics/Volume): {energy}
Density (Note count): {density}
Instrument Balance Weights: {inst_str}

Musical Rules to Apply:
1. Scale and Atmosphere (Key Mode & Brightness):
   - key_mode = 'major' / brightness >= 0.5: Use a major scale (e.g. C major: pitches 60, 62, 64, 65, 67, 69, 71). Create a bright, happy, peaceful, or uplifiting sound.
   - key_mode = 'minor' / brightness < 0.5: Use a natural/harmonic minor scale (e.g. A minor: pitches 57, 59, 60, 62, 64, 65, 67/68). Create a sad, dark, emotional, or mysterious sound.
2. Velocity and Intensity (Energy):
   - Energy controls the note velocity and drum presence. High energy ({energy} >= 0.7) should have louder notes (velocity 90-110) and a steady, driving drum track. Low energy ({energy} < 0.3) should have soft notes (velocity 50-70) and no or very sparse drums.
3. Rhythm and Duration (Density):
   - Density controls how frequently notes occur. High density ({density} >= 0.7) should have many notes spaced by 2 or 4 steps (8th or 16th notes). Low density ({density} < 0.3) should have fewer, longer notes (whole/half notes spaced by 8 or 16 steps, duration 8-16 steps).
4. Instrument Allocation (Weights):
   - Allocate tracks based on the instrument weights. If an instrument has a weight of 0.0, do NOT create a track for it. Give the track with the highest weight the main melody/most notes.

Please generate a corresponding JSON output.
{FEW_SHOT_EXAMPLES}
"""
    return prompt

def get_default_midi(tempo_bpm: int, key_mode: str, duration_minutes: float) -> MidiComposition:
    """
    パース失敗などの緊急フォールバック用のデフォルトMIDI（4小節ループ）を生成する。
    """
    # ピアノトラック用のコード進行ノート
    # Major: C - G - Am - F
    # Minor: Am - Dm - F - E
    piano_notes = []
    
    # 4小節 (64ステップ)
    if key_mode == "minor":
        # Am (A3=57, C4=60, E4=64) at bar 0 (step 0)
        piano_notes.extend([
            MidiNote(step=0, pitch=57, velocity=80, duration_steps=12),
            MidiNote(step=0, pitch=60, velocity=80, duration_steps=12),
            MidiNote(step=0, pitch=64, velocity=80, duration_steps=12),
        ])
        # Dm (D3=50, F3=53, A3=57) at bar 1 (step 16)
        piano_notes.extend([
            MidiNote(step=16, pitch=50, velocity=80, duration_steps=12),
            MidiNote(step=16, pitch=53, velocity=80, duration_steps=12),
            MidiNote(step=16, pitch=57, velocity=80, duration_steps=12),
        ])
        # F (F3=53, A3=57, C4=60) at bar 2 (step 32)
        piano_notes.extend([
            MidiNote(step=32, pitch=53, velocity=80, duration_steps=12),
            MidiNote(step=32, pitch=57, velocity=80, duration_steps=12),
            MidiNote(step=32, pitch=60, velocity=80, duration_steps=12),
        ])
        # E (E3=52, G#3=56, B3=59) at bar 3 (step 48)
        piano_notes.extend([
            MidiNote(step=48, pitch=52, velocity=80, duration_steps=12),
            MidiNote(step=48, pitch=56, velocity=80, duration_steps=12),
            MidiNote(step=48, pitch=59, velocity=80, duration_steps=12),
        ])
    else:
        # C (C3=48, E3=52, G3=55)
        piano_notes.extend([
            MidiNote(step=0, pitch=48, velocity=80, duration_steps=12),
            MidiNote(step=0, pitch=52, velocity=80, duration_steps=12),
            MidiNote(step=0, pitch=55, velocity=80, duration_steps=12),
        ])
        # G (G2=43, B2=47, D3=50)
        piano_notes.extend([
            MidiNote(step=16, pitch=43, velocity=80, duration_steps=12),
            MidiNote(step=16, pitch=47, velocity=80, duration_steps=12),
            MidiNote(step=16, pitch=50, velocity=80, duration_steps=12),
        ])
        # Am (A2=45, C3=48, E3=52)
        piano_notes.extend([
            MidiNote(step=32, pitch=45, velocity=80, duration_steps=12),
            MidiNote(step=32, pitch=48, velocity=80, duration_steps=12),
            MidiNote(step=32, pitch=52, velocity=80, duration_steps=12),
        ])
        # F (F2=41, A2=45, C3=48)
        piano_notes.extend([
            MidiNote(step=48, pitch=41, velocity=80, duration_steps=12),
            MidiNote(step=48, pitch=45, velocity=80, duration_steps=12),
            MidiNote(step=48, pitch=48, velocity=80, duration_steps=12),
        ])

    # ドラムトラック (Channel 9, Kick=36, Snare=38, Hihat=42)
    drum_notes = []
    for bar in range(4):
        base_step = bar * 16
        # Kick on 1 and 3 beats (steps 0, 8)
        drum_notes.append(MidiNote(step=base_step + 0, pitch=36, velocity=100, duration_steps=2))
        drum_notes.append(MidiNote(step=base_step + 8, pitch=36, velocity=100, duration_steps=2))
        # Snare on 2 and 4 beats (steps 4, 12)
        drum_notes.append(MidiNote(step=base_step + 4, pitch=38, velocity=90, duration_steps=2))
        drum_notes.append(MidiNote(step=base_step + 12, pitch=38, velocity=90, duration_steps=2))
        # Hihat on 8th notes (0, 2, 4, 6, 8, 10, 12, 14)
        for h in range(8):
            drum_notes.append(MidiNote(step=base_step + (h * 2), pitch=42, velocity=75, duration_steps=1))

    piano_track = MidiTrack(
        track_id="fallback_piano",
        track_name="Acoustic Piano",
        instrument="acoustic_piano",
        channel=0,
        muted=False,
        notes=piano_notes
    )

    drum_track = MidiTrack(
        track_id="fallback_drums",
        track_name="Drums",
        instrument="synth_drum_kit",
        channel=9,
        muted=False,
        notes=drum_notes
    )

    return MidiComposition(
        tempo_bpm=tempo_bpm,
        time_signature="4/4",
        key_mode=key_mode,
        duration_minutes=duration_minutes,
        sections=[
            MidiSection(name="intro", start_bar=0, bars=4)
        ],
        tracks=[piano_track, drum_track]
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
    Ollama経由でLLMを呼び出し、MIDI JSONデータを生成する。
    JSONのデコードエラーやスキーマバリデーションエラー時には自動的にリトライと修正指示を行う。
    すべて失敗した場合はデフォルトの4小節構成MIDIデータを返す。
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
            # 修正指示用プロンプトの構成
            current_prompt = prompt
            if attempt > 0:
                current_prompt = (
                    f"{prompt}\n\n"
                    f"CRITICAL FIX NEEDED:\n"
                    f"Your previous response failed validation with error: {last_error}\n"
                    f"Your previous response was:\n{last_response}\n\n"
                    f"Please fix the error and output ONLY the valid JSON object conforming strictly to the schema. "
                    f"Do NOT wrap it in backticks or markdown."
                )

            # Ollama呼び出し (format="json" を強制)
            response_text = client.generate(current_prompt, system_prompt=SYSTEM_PROMPT, format_json=True)
            last_response = response_text

            # クリーンアップ (余分なスペースや改行の削除)
            clean_text = response_text.strip()
            # 万が一markdownのコードブロックで囲まれていた場合のはぎ取り
            if clean_text.startswith("```"):
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                else:
                    clean_text = clean_text[3:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()

            # Pydanticモデルでのバリデーション
            composition = MidiComposition.model_validate_json(clean_text)
            return composition

        except Exception as e:
            last_error = str(e)
            print(f"[Ollama MIDI Generation] Attempt {attempt + 1} failed: {last_error}")

    # すべてのリトライが失敗した場合はデフォルトにフォールバック
    print("[Ollama MIDI Generation] All attempts failed. Falling back to default MIDI template.")
    return get_default_midi(tempo_bpm=tempo_bpm, key_mode=key_mode, duration_minutes=duration_minutes)
