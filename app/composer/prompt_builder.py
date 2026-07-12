import json
import random
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
  "instruments": ["piano", "guitar", "bass", "drums"]
}
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
  "instruments": ["piano", "guitar", "bass"]
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

def get_chord_pitches(chord_name: str, key_offset: int = 0) -> list:
    """コード名から構成音のピッチリストを取得し、キーオフセットを適用する"""
    chord_name = chord_name.strip()
    if chord_name in CHORD_MAP:
        base_pitches = CHORD_MAP[chord_name]
    else:
        # 簡易解析フォールバック
        base_note = chord_name[0].upper()
        if len(chord_name) > 1 and chord_name[1] in ("#", "b"):
            base_note += chord_name[1]
            
        is_minor = "m" in chord_name and "maj" not in chord_name.lower()
        notes_offsets = [0, 3, 7] if is_minor else [0, 4, 7]
        base_pitches_dict = {
            "C": 60, "C#": 61, "Db": 61, "D": 62, "D#": 63, "Eb": 63,
            "E": 64, "F": 65, "F#": 66, "Gb": 66, "G": 67, "G#": 68,
            "Ab": 68, "A": 69, "A#": 70, "Bb": 70, "B": 71
        }
        root = base_pitches_dict.get(base_note, 60)
        base_pitches = [root + offset for offset in notes_offsets]
        
    return [p + key_offset for p in base_pitches]

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

def get_song_structure(total_bars_needed: int, key_mode: str, style: str) -> List[Dict[str, Any]]:
    """音楽理論的セオリーに基づき、イントロ、サビ、Aメロ、アウトロの曲構成とコード進行を構築する"""
    
    # 決定論的なマンネリを防ぐため、毎回異なるコード進行プールから選択
    major_pools = {
        "royal_road": ["Fmaj7", "G7", "Em7", "Am7"],
        "pop": ["C", "G", "Am", "F"],
        "canon": ["C", "G", "Am", "Em", "F", "C", "F", "G"],
        "lofi_jazz": ["Cmaj7", "A7", "Dm7", "G7"],
        "ambient": ["Cmaj7", "Fmaj7", "Cmaj7", "Fmaj7"]
    }
    minor_pools = {
        "andalusian": ["Am", "G", "F", "E7"],
        "minor_pop": ["Am", "F", "C", "G"],
        "lofi_jazz": ["Am7", "D7", "Gmaj7", "Cmaj7"],
        "ambient": ["Am7", "Em7", "Fmaj7", "G6"]
    }
    
    pool = minor_pools if key_mode == "minor" else major_pools
    
    # スタイルに応じたセクション進行の割り当て
    if style in ("lofi", "jazz"):
        verse_chords = pool["lofi_jazz"]
        chorus_chords = pool["lofi_jazz"]
    elif style == "ambient":
        verse_chords = pool["ambient"]
        chorus_chords = pool["ambient"]
    else:
        verse_chords = pool["andalusian"] if key_mode == "minor" else pool["royal_road"]
        chorus_chords = pool["minor_pop"] if key_mode == "minor" else pool["pop"]

    # 毎回異なるコード進行にするため、Cメジャー/Aマイナーからランダムにキー転調 (Transposition Offset) を施す
    key_offset = random.randint(-5, 6)
    
    sections_layout = []
    
    # 短尺時と長尺時で構成を変更
    if total_bars_needed <= 8:
        # 短尺：Aメロ ➡ サビ
        sections_layout.append({"name": "verse", "bars": total_bars_needed // 2, "chords": verse_chords, "intensity": "low"})
        sections_layout.append({"name": "chorus", "bars": total_bars_needed - (total_bars_needed // 2), "chords": chorus_chords, "intensity": "high"})
    else:
        # 長尺：イントロ ➡ Aメロ（静か） ➡ サビ（盛り上がり） ➡ 間奏 ➡ サビ ➡ アウトロ（静か）
        intro_bars = 4
        outro_bars = 4
        middle_bars = total_bars_needed - intro_bars - outro_bars
        
        sections_layout.append({"name": "intro", "bars": intro_bars, "chords": verse_chords, "intensity": "low"})
        
        current_middle = 0
        cycle = 0
        while current_middle < middle_bars:
            remaining = middle_bars - current_middle
            
            if cycle % 2 == 0:
                # Aメロ (Verse)
                bars = min(8, remaining)
                sections_layout.append({"name": "verse", "bars": bars, "chords": verse_chords, "intensity": "low"})
            else:
                # サビ (Chorus)
                bars = min(8, remaining)
                sections_layout.append({"name": "chorus", "bars": bars, "chords": chorus_chords, "intensity": "high"})
                
            current_middle += bars
            cycle += 1
            
        sections_layout.append({"name": "outro", "bars": outro_bars, "chords": verse_chords, "intensity": "low"})

    final_sections = []
    current_bar = 0
    for sec in sections_layout:
        final_sections.append({
            "name": sec["name"],
            "start_bar": current_bar,
            "bars": sec["bars"],
            "chords": sec["chords"],
            "intensity": sec["intensity"],
            "key_offset": key_offset
        })
        current_bar += sec["bars"]
        
    return final_sections

def expand_chord_plan_to_midi(plan: Dict[str, Any], duration_minutes: float) -> MidiComposition:
    """高次のコード進行・構成プランを具体的なMIDIノート（MidiComposition）へ拡張・展開する"""
    tempo_bpm = int(plan.get("tempo_bpm", 80))
    key_mode = plan.get("key_mode", "major")
    style = plan.get("style", "lofi").lower()
    instruments = plan.get("instruments", ["piano", "guitar", "bass", "drums"])
    
    # 指定の再生時間をカバーするのに必要な総小節数を計算
    seconds_per_beat = 60.0 / tempo_bpm
    seconds_per_bar = seconds_per_beat * 4.0
    target_seconds = duration_minutes * 60.0
    total_bars_needed = max(4, int(target_seconds / seconds_per_bar))
    
    # カスタムDSL進行指定のチェック
    custom_chords = plan.get("custom_chords")
    if custom_chords:
        custom_bars = plan.get("custom_bars") or len(custom_chords)
        key_offset = 0 # DSL指定時は転調を行わない
        
        sections = []
        current_bar = 0
        while current_bar < total_bars_needed:
            remaining_bars = total_bars_needed - current_bar
            section_bars = min(custom_bars, remaining_bars)
            if section_bars <= 0:
                break
                
            name = "verse" if (current_bar // custom_bars) % 2 == 0 else "chorus"
            intensity = "low" if name == "verse" else "high"
            
            sections.append({
                "name": name,
                "start_bar": current_bar,
                "bars": section_bars,
                "chords": custom_chords,
                "intensity": intensity,
                "key_offset": key_offset
            })
            current_bar += section_bars
    else:
        # 曲のセクション構成を動的に生成
        sections = get_song_structure(total_bars_needed, key_mode, style)

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
        intensity = sec["intensity"]
        key_offset = sec["key_offset"]
        
        if not chords:
            chords = ["C"]
            
        for b in range(bars):
            bar_index = start_bar + b
            base_step = bar_index * 16
            
            # 各小節のコード進行
            chord_name = chords[b % len(chords)]
            pitches = get_chord_pitches(chord_name, key_offset)
            
            # 1. ピアノ（コード・伴奏）トラック
            if "piano" in instruments:
                if intensity == "low":
                    # 静かなパート：白玉コード（小節頭で一回伸ばす）
                    for p in pitches:
                        track_notes["piano"].append(MidiNote(step=base_step + 0, pitch=p, velocity=60, duration_steps=14))
                else:
                    # 盛り上がるサビ：リズム感のあるコードバッキング
                    for p in pitches:
                        track_notes["piano"].append(MidiNote(step=base_step + 0, pitch=p, velocity=75, duration_steps=6))
                        track_notes["piano"].append(MidiNote(step=base_step + 8, pitch=p, velocity=70, duration_steps=6))
                    
            # 2. ギター（アルペジオ）トラック
            if "guitar" in instruments:
                if intensity == "low":
                    # 静かなパート：音数を減らしたゆっくりしたアルペジオ
                    for step_offset, p in zip([0, 8], pitches):
                        track_notes["guitar"].append(MidiNote(step=base_step + step_offset, pitch=p + 12, velocity=55, duration_steps=6))
                else:
                    # 盛り上がるパート：16ビートの細かなアルペジオ
                    extended_pitches = pitches * 2
                    for step_offset, p in zip([0, 4, 8, 12], extended_pitches):
                        track_notes["guitar"].append(MidiNote(step=base_step + step_offset, pitch=p + 12, velocity=65, duration_steps=3))
                    
            # 3. ベーストラック
            if "bass" in instruments:
                root_pitch = pitches[0] - 24  # 2オクターブ低く
                if intensity == "low":
                    # Aメロなどは全音符でルートを支えるのみ
                    track_notes["bass"].append(MidiNote(step=base_step + 0, pitch=root_pitch, velocity=75, duration_steps=14))
                else:
                    # サビは8ビートやシンコペーションでリズムを刻む
                    track_notes["bass"].append(MidiNote(step=base_step + 0, pitch=root_pitch, velocity=85, duration_steps=6))
                    track_notes["bass"].append(MidiNote(step=base_step + 8, pitch=root_pitch, velocity=80, duration_steps=6))
                
            # 4. ドラムトラック (Channel 9, Kick=36, Snare=38, Hihat=42)
            if "drums" in instruments:
                if intensity == "low" and sec["name"] in ("intro", "outro"):
                    # イントロやアウトロはドラムなし、または非常に薄いハイハットのみ
                    if b % 2 == 0:
                        track_notes["drums"].append(MidiNote(step=base_step + 0, pitch=42, velocity=50, duration_steps=1))
                else:
                    # 通常ドラムパターン
                    # キック
                    track_notes["drums"].append(MidiNote(step=base_step + 0, pitch=36, velocity=90, duration_steps=2))
                    if intensity == "high":
                        track_notes["drums"].append(MidiNote(step=base_step + 8, pitch=36, velocity=90, duration_steps=2))
                        
                    # スネア (2拍、4拍)
                    track_notes["drums"].append(MidiNote(step=base_step + 4, pitch=38, velocity=85, duration_steps=2))
                    track_notes["drums"].append(MidiNote(step=base_step + 12, pitch=38, velocity=85, duration_steps=2))
                    
                    # ハイハット
                    hihat_density = 8 if intensity == "high" else 4
                    step_jump = 16 // hihat_density
                    for h in range(hihat_density):
                        track_notes["drums"].append(MidiNote(step=base_step + (h * step_jump), pitch=42, velocity=65, duration_steps=1))

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

import re

def parse_dsl_description(description: str) -> Optional[Dict[str, Any]]:
    """
    ユーザーの自然言語指示の中に DSL 形式 [Am7 -> D7 -> Gmaj7 -> Cmaj7 : 4 bars : style=jazz] があるか確認し、
    パースして辞書を返す。なければ None。
    """
    match = re.search(r'\[([^\]]+)\]', description)
    if not match:
        return None
        
    dsl_content = match.group(1).strip()
    parts = [p.strip() for p in dsl_content.split(':')]
    
    # 進行の抽出
    chord_part = parts[0]
    chords = [c.strip() for c in re.split(r'->| |,', chord_part) if c.strip()]
    if not chords:
        return None
        
    result = {
        "custom_chords": chords
    }
    
    # オプション（小節数、スタイル）のパース
    for part in parts[1:]:
        part_lower = part.lower()
        if "bars" in part_lower or "bar" in part_lower:
            bar_match = re.search(r'(\d+)', part_lower)
            if bar_match:
                result["custom_bars"] = int(bar_match.group(1))
        elif "style=" in part_lower:
            result["style"] = part.split('=')[1].strip()
        elif part_lower in ("lofi", "jazz", "pop", "ambient", "rock"):
            result["style"] = part_lower
            
    return result

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
    # 1. DSL構文のチェックとバイパス
    dsl_plan = parse_dsl_description(description)
    if dsl_plan:
        print(f"[DSL Composer] Custom chord progression detected: {dsl_plan}")
        inst_list = ["piano", "guitar", "bass", "drums"]
        if instruments:
            inst_list = [k for k, v in instruments.items() if v > 0.0]
            if not inst_list:
                inst_list = ["piano"]
                
        plan = {
            "tempo_bpm": tempo_bpm,
            "key_mode": key_mode,
            "style": dsl_plan.get("style", "lofi"),
            "instruments": inst_list,
            "custom_chords": dsl_plan["custom_chords"],
            "custom_bars": dsl_plan.get("custom_bars")
        }
        return expand_chord_plan_to_midi(plan, duration_minutes)

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

    # より創造的（クリエイティブ）かつ毎回コード進行にブレが出るよう、Temperatureを0.7に引き上げる
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
        "instruments": ["piano", "guitar", "bass", "drums"]
    }
    return expand_chord_plan_to_midi(default_plan, duration_minutes)
