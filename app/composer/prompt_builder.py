import json
import random
from typing import Dict, Any, Optional, List
from app.api.llm_client import OllamaClient
from app.composer.midi_schema import MidiComposition, MidiTrack, MidiNote, MidiSection

SYSTEM_PROMPT = """You are a high-level music composition assistant. Your job is to convert natural language descriptions and slider-based music parameters into a high-level Chord Plan JSON object.
You must output ONLY a valid JSON object matching the JSON schema, without any Markdown decoration, wrap-up text, or comments.

If the user specifies a famous song, artist (e.g. "Oasis の Live forever", "Michael Jackson", "Beatles"), or a specific vibe/mood (e.g. "朝の曲", "Billie Jean"), you MUST generate the appropriate chords matching that request inside the "custom_chords" object with "verse" and "chorus" keys containing lists of chord strings.

JSON Schema format:
{
  "tempo_bpm": int (50-150),
  "key_mode": "major" | "minor",
  "style": "lofi" | "jazz" | "pop" | "ambient" | "rock" | "edm" | "trance" | "chillhop" | "triphop" | "bossanova",
  "instruments": ["piano", "guitar", "bass", "drums"],
  "melody_style": "steady" | "expressive" | "complex",
  "rhythm_variation": "none" | "slight" | "heavy",
  "custom_chords": {
    "verse": ["C", "G", "Am", "F"],
    "chorus": ["F", "G", "Em", "Am"]
  }
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
  "instruments": ["piano", "guitar", "bass"],
  "melody_style": "expressive",
  "rhythm_variation": "slight"
}

[Example 2]
Input Description: "Oasis の Live forever をEDM風にアレンジして"
Parameters: Tempo: 120 BPM, Key: Major, Duration: 1.5 minutes
Output:
{
  "tempo_bpm": 120,
  "key_mode": "major",
  "style": "edm",
  "instruments": ["piano", "guitar", "bass", "drums"],
  "melody_style": "complex",
  "rhythm_variation": "heavy",
  "custom_chords": {
    "verse": ["G", "D", "Am", "C", "D"],
    "chorus": ["Em", "D", "C", "D"]
  }
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
    "Am7": [57, 60, 64, 67], "Bm7": [59, 62, 66, 72],
    
    # sus4 / 7sus4
    "Csus4": [60, 65, 67], "Dsus4": [62, 67, 69], "Esus4": [64, 69, 71], "Fsus4": [65, 70, 72], "Gsus4": [67, 72, 74], "Asus4": [69, 74, 76], "Bsus4": [59, 64, 66],
    "C7sus4": [60, 65, 67, 70], "D7sus4": [62, 67, 69, 72], "E7sus4": [64, 69, 71, 74], "A7sus4": [69, 74, 76, 79], "G7sus4": [67, 72, 74, 77],
    
    # 9th chords
    "Cmaj9": [60, 64, 67, 71, 74], "Fmaj9": [65, 69, 72, 76, 79],
    "C9": [60, 64, 67, 70, 74], "D9": [62, 66, 69, 72, 76], "E9": [64, 68, 71, 74, 78], "G9": [67, 71, 74, 77, 81], "A9": [69, 73, 76, 79, 83],
    "Cm9": [60, 63, 67, 70, 74], "Dm9": [62, 65, 69, 72, 76], "Em9": [64, 67, 71, 74, 78], "Am9": [57, 60, 64, 67, 71]
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
            
        # テンション解析
        has_7 = "7" in chord_name
        has_9 = "9" in chord_name
        is_maj = "maj" in chord_name.lower() or "M" in chord_name
        is_sus4 = "sus4" in chord_name.lower()
        is_power = "5" in chord_name and not has_7 and not has_9
        is_minor = "m" in chord_name and not is_maj and not is_sus4 and not is_power
        
        if is_power:
            notes_offsets = [0, 7]  # パワーコード (ルート & 5度のみ)
        elif is_sus4:
            if has_7:
                notes_offsets = [0, 5, 7, 10]
            else:
                notes_offsets = [0, 5, 7]
        elif is_minor:
            if has_9:
                notes_offsets = [0, 3, 7, 10, 14] # m9 (root, b3, 5, b7, 9)
            elif has_7:
                notes_offsets = [0, 3, 7, 10] # m7
            else:
                notes_offsets = [0, 3, 7] # m
        else: # Major
            if has_9:
                if is_maj:
                    notes_offsets = [0, 4, 7, 11, 14] # maj9
                else:
                    notes_offsets = [0, 4, 7, 10, 14] # dominant 9 (9)
            elif has_7:
                if is_maj:
                    notes_offsets = [0, 4, 7, 11] # maj7
                else:
                    notes_offsets = [0, 4, 7, 10] # 7
            else:
                notes_offsets = [0, 4, 7] # major triad
            
        base_pitches_dict = {
            "C": 60, "C#": 61, "Db": 61, "D": 62, "D#": 63, "Eb": 63,
            "E": 64, "F": 65, "F#": 66, "Gb": 66, "G": 67, "G#": 68,
            "Ab": 68, "A": 69, "A#": 70, "Bb": 70, "B": 71
        }
        root = base_pitches_dict.get(base_note, 60)
        base_pitches = [root + offset for offset in notes_offsets]
        
    return [p + key_offset for p in base_pitches]

def arrange_chords_for_bossanova(chords: list[str]) -> list[str]:
    """コード進行をボサノバらしいテンションコードやセブンスコードに自動アレンジする"""
    arranged = []
    for chord in chords:
        c = chord.strip()
        # すでに複雑なテンションがある場合はそのまま
        if "9" in c or "11" in c or "13" in c or "maj7" in c.lower() or "m7" in c:
            if c == "Em7":
                arranged.append("Em9")
            elif c == "Am7":
                arranged.append("Am9")
            elif c == "Dm7":
                arranged.append("Dm9")
            else:
                arranged.append(c)
            continue
            
        # 単純なコードをボサノバ風に変換
        if c == "C":
            arranged.append("Cmaj7")
        elif c == "G":
            arranged.append("Gmaj7")
        elif c == "F":
            arranged.append("Fmaj7")
        elif c == "D":
            arranged.append("D7")
        elif c == "A":
            arranged.append("A7")
        elif c == "E":
            arranged.append("E7")
        elif c == "B":
            arranged.append("B7")
        elif c == "Am":
            arranged.append("Am7")
        elif c == "Em":
            arranged.append("Em7")
        elif c == "Dm":
            arranged.append("Dm7")
        elif c == "Bm":
            arranged.append("Bm7")
        elif c == "F#m" or c == "Gbm":
            arranged.append("F#m7")
        elif c == "C#m" or c == "Dbm":
            arranged.append("C#m7")
        elif c == "G#m" or c == "Abm":
            arranged.append("G#m7")
        elif c == "Dsus4":
            arranged.append("D7(9)" if random.random() < 0.5 else "D9")
        elif c == "A7sus4":
            arranged.append("A7(9)" if random.random() < 0.5 else "A9")
        else:
            arranged.append(c)
    return arranged

def arrange_chords_by_style(chords: list[str], style: str) -> list[str]:
    """スタイルに応じてコード進行の構成（テンション等）を自動アレンジする"""
    style_lower = style.lower()
    
    # 1. ボサノバ/ジャズ/ローファイ
    if style_lower in ("bossanova", "bossa", "jazz", "lofi", "funk"):
        return arrange_chords_for_bossanova(chords)
        
    # 2. アンビエント / チルアウト (Enya風など)
    elif style_lower in ("ambient", "chillhop", "triphop"):
        arranged = []
        for c in chords:
            c_strip = c.strip()
            # テンションを追加
            if c_strip == "C": arranged.append("Cmaj7")
            elif c_strip == "G": arranged.append("Gmaj7")
            elif c_strip == "F": arranged.append("Fmaj7")
            elif c_strip == "D": arranged.append("Dadd9")
            elif c_strip == "A": arranged.append("Aadd9")
            elif c_strip == "Em": arranged.append("Em7")
            elif c_strip == "Am": arranged.append("Am7")
            elif c_strip == "Dm": arranged.append("Dm9")
            elif c_strip == "Em7": arranged.append("Em9")
            elif c_strip == "Dsus4": arranged.append("Dadd9")
            elif c_strip == "A7sus4": arranged.append("A7")
            else:
                arranged.append(c_strip)
        return arranged
        
    # 3. ロック / メタル / グランジ (テンションを削ぎ落としてパワーコード化する)
    elif style_lower in ("rock", "metal", "grunge", "nirvana_lofi"):
        arranged = []
        for c in chords:
            c_strip = c.strip()
            # 最初のルート音（C, C#, Db等）を抽出して「5」を付与する
            base_note = c_strip[0].upper()
            if len(c_strip) > 1 and c_strip[1] in ("#", "b"):
                base_note += c_strip[1]
            arranged.append(base_note + "5")
        return arranged
        
    # 4. レゲエ / ポップス (極めてシンプルにする)
    elif style_lower in ("reggae", "pop"):
        arranged = []
        for c in chords:
            c_strip = c.strip()
            # テンションを削ぎ落とす
            if c_strip == "Em7": arranged.append("Em")
            elif c_strip == "Dsus4": arranged.append("D")
            elif c_strip == "A7sus4": arranged.append("A")
            elif c_strip == "Cmaj7": arranged.append("C")
            elif c_strip == "Gmaj7": arranged.append("G")
            elif c_strip == "Fmaj7": arranged.append("F")
            elif c_strip == "Am7": arranged.append("Am")
            elif c_strip == "Dm7": arranged.append("Dm")
            else:
                arranged.append(c_strip)
        return arranged
        
    return chords

def parse_key_offset_from_description(description: str) -> int:
    """指示テキストからキー変更（転調）の指示を抽出し、key_offset値を返す"""
    desc = description.lower()
    if any(w in desc for w in ["原曲", "そのまま", "オリジナル", "original"]):
        return 999
    
    # 1. 直接的な数値指定の検出 (例: キー+2, key -3, 2半音上げて, etc.)
    m_plus = re.search(r'(?:key|キー|カポ|capo|pitch|ピッチ)\s*([\+\-]\d+)', desc)
    if m_plus:
        return int(m_plus.group(1))
        
    m_up = re.search(r'(\d+)\s*(?:半音|step|steps)?\s*(?:上げて|上げ|up)', desc)
    if m_up:
        return int(m_up.group(1))
        
    m_down = re.search(r'(\d+)\s*(?:半音|step|steps)?\s*(?:下げて|下げ|down)', desc)
    if m_down:
        return -int(m_down.group(1))
        
    # 2. キー名指定の検出 (例: in C, キーをAmにして)
    # 元の曲が Wonderwall (Em/G) だと仮定した場合のターゲットキーへのトランスポーズ
    # Wonderwall の基準キーは G Major / E minor (offset = 0)
    key_map = {
        "c": 5, "c#": 6, "db": 6, "d": 7, "d#": 8, "eb": 8, "e": 9, "f": 10, "f#": 11, "gb": 11, "g": 0, "g#": 1, "ab": 1, "a": 2, "a#": 3, "bb": 3, "b": 4
    }
    m_key = re.search(r'(?:key|キー|in|トランスポーズ)\s*(?:を|に)?\s*([a-g][#b]?)(?:m|major|minor)?', desc)
    if m_key:
        target_key = m_key.group(1)
        if target_key in key_map:
            # G Major (0) からの差分
            return key_map[target_key]
            
    return 0

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

LOCAL_SONG_DATABASE = [
    {
        "keywords": ["live forever", "liveforever"],
        "style": "rock",
        "custom_chords": {
            "verse": ["G", "D", "Am", "C", "D"],
            "chorus": ["Em", "D", "C", "D"]
        }
    },
    {
        "keywords": ["wonderwall"],
        "style": "rock",
        "custom_chords": {
            "verse": ["Em7", "G", "Dsus4", "A7sus4"],
            "chorus": ["C", "D", "Em7", "G"]
        },
        "custom_melody": {
            "verse": [
                # 小節 0 (Em7)
                [(0, 78), (2, 79), (4, 78), (6, 79), (8, 78), (10, 79)],
                # 小節 1 (G)
                [(0, 78), (2, 76), (4, 74), (6, 76), (8, 74)],
                # 小節 2 (Dsus4)
                [(0, 78), (2, 79), (4, 78), (6, 79), (8, 78), (10, 79)],
                # 小節 3 (A7sus4)
                [(0, 78), (2, 76), (4, 74), (6, 76), (8, 74)]
            ],
            "chorus": [
                # 小節 0 (C)
                [(0, 79), (2, 81), (4, 83), (6, 83), (8, 83), (10, 83), (12, 83)],
                # 小節 1 (D)
                [(0, 81), (2, 83), (4, 84), (6, 84), (8, 84), (10, 84), (12, 84)],
                # 小節 2 (Em7)
                [(0, 83), (2, 84), (4, 86), (6, 86), (8, 86), (10, 86), (12, 86)],
                # 小節 3 (G)
                [(0, 83), (4, 81), (8, 79), (12, 79)]
            ]
        }
    },
    {
        "keywords": ["don't look back in anger", "dont look back in anger"],
        "style": "rock",
        "custom_chords": {
            "verse": ["C", "G", "Am", "E7", "F", "G", "C", "G"],
            "chorus": ["F", "Fm", "C", "F", "Fm", "C"]
        }
    },
    {
        "keywords": ["billie jean", "billiejean", "michael jackson", "マイケル", "jackson"],
        "style": "pop",
        "custom_chords": {
            "verse": ["F#m", "Bm7", "F#m", "Bm7"],
            "chorus": ["D", "C#m", "D", "C#m"]
        }
    },
    {
        "keywords": ["yesterday"],
        "style": "pop",
        "custom_chords": {
            "verse": ["F", "Em7", "A7", "Dm", "Bb", "C7", "F"],
            "chorus": ["Dm", "G7", "Bb", "F"]
        },
        "custom_melody": {
            "verse": [
                # 小節 0 (F): "Yes-ter-day" (G - F - F)
                [(2, 67), (4, 65), (8, 65)],
                # 小節 1 (Em7/A7): "all my troubles" (A - B - C# - D - E)
                [(0, 69), (3, 71), (4, 73), (6, 74), (8, 76), (10, 77), (12, 76), (14, 74)],
                # 小節 2 (Dm): "now it looks as though"
                [(0, 76), (2, 74), (4, 72), (6, 74), (8, 77), (10, 81), (12, 79)],
                # 小節 3 (Bb/C7): "oh, I believe in yesterday"
                [(0, 77), (2, 79), (4, 81), (6, 79), (8, 77), (10, 76), (12, 77)]
            ],
            "chorus": [
                # 小節 0 (Dm/G7): "Why she had to go"
                [(0, 81), (4, 79), (8, 77), (10, 76), (12, 74)],
                # 小節 1 (Bb/F): "I don't know, she wouldn't say"
                [(0, 77), (4, 79), (8, 81), (10, 79), (12, 77), (14, 77)],
                # 小節 2 (Dm/G7): "I said something wrong"
                [(0, 81), (4, 79), (8, 77), (10, 76), (12, 74)],
                # 小節 3 (Bb/F): "now I long for yesterday"
                [(0, 77), (4, 79), (8, 81), (10, 79), (12, 77), (14, 77)]
            ]
        }
    },
    {
        "keywords": ["let it be", "letitbe"],
        "style": "pop",
        "custom_chords": {
            "verse": ["C", "G", "Am", "F", "C", "G", "F", "C"],
            "chorus": ["Am", "G", "F", "C", "G", "F", "C"]
        }
    },
    {
        "keywords": ["wake me up", "wakemeup", "avicii", "アヴィーチー"],
        "style": "edm",
        "custom_chords": {
            "verse": ["Am", "F", "C", "G"],
            "chorus": ["Am", "F", "C", "G"]
        }
    },
    {
        "keywords": ["朝の曲", "朝の光", "朝", "canon", "カノン", "morning"],
        "style": "ambient",
        "custom_chords": {
            "verse": ["C", "G", "Am", "Em", "F", "C", "F", "G"],
            "chorus": ["C", "G", "Am", "Em", "F", "C", "F", "G"]
        }
    },
    {
        "keywords": ["hotel california", "hotelcalifornia"],
        "style": "rock",
        "custom_chords": {
            "verse": ["Bm", "F#", "A", "E", "G", "D", "Em", "F#"],
            "chorus": ["G", "D", "F#", "Bm", "G", "D", "Em", "F#"]
        }
    },
    {
        "keywords": ["imagine"],
        "style": "pop",
        "custom_chords": {
            "verse": ["C", "Cmaj7", "F", "C", "Cmaj7", "F"],
            "chorus": ["F", "G", "C", "E7", "F", "G", "C"]
        }
    },
    {
        "keywords": ["hey jude", "heyjude"],
        "style": "pop",
        "custom_chords": {
            "verse": ["F", "C", "C7", "F", "Bb", "F", "C7", "F"],
            "chorus": ["F7", "Bb", "Gm7", "C7", "F"]
        }
    },
    {
        "keywords": ["viva la vida", "vivalavida"],
        "style": "pop",
        "custom_chords": {
            "verse": ["C", "D", "G", "Em"],
            "chorus": ["C", "D", "G", "Em"]
        }
    },
    {
        "keywords": ["smells like teen spirit", "smellsliketeenspirit", "nirvana"],
        "style": "rock",
        "custom_chords": {
            "verse": ["Fm", "Bbm", "Ab", "Db"],
            "chorus": ["Fm", "Bbm", "Ab", "Db"]
        }
    },
    {
        "keywords": ["creep", "radiohead"],
        "style": "rock",
        "custom_chords": {
            "verse": ["G", "B", "C", "Cm"],
            "chorus": ["G", "B", "C", "Cm"]
        }
    },
    {
        "keywords": ["残酷な天使のテーゼ", "残酷な天使", "cruel angel"],
        "style": "pop",
        "custom_chords": {
            "verse": ["Em", "Am", "Bm", "Em"],
            "chorus": ["C", "D", "Bm", "Em", "Am", "D", "G"]
        }
    },
    {
        "keywords": ["丸の内サディスティック", "丸の内", "marunouchi"],
        "style": "jazz",
        "custom_chords": {
            "verse": ["Abmaj7", "G7", "Cm7", "Ebm7", "Abmaj7", "G7", "Cm7"],
            "chorus": ["Abmaj7", "G7", "Cm7", "Ebm7", "Abmaj7", "G7", "Cm7"]
        }
    }
]

def check_local_song_database(description: str) -> Optional[Dict[str, Any]]:
    desc_lower = description.lower()
    for entry in LOCAL_SONG_DATABASE:
        for kw in entry["keywords"]:
            if kw in desc_lower:
                return {
                    "style": entry["style"],
                    "custom_chords": entry["custom_chords"],
                    "custom_melody": entry.get("custom_melody")
                }
    return None

def extract_song_query(description: str) -> Optional[str]:
    """指示テキストから曲名/アーティスト検索用のクエリをクレンジング抽出する"""
    # 1. 括弧や引用符（「」『』"" ''）で囲まれた部分があれば、それを曲名候補として最優先で抽出
    for q in [r'「([^」]+)」', r'『([^』]+)』', r'\"([^\"]+)\"', r'\'([^\']+)\'']:
        m = re.search(q, description)
        if m:
            val = m.group(1).strip()
            if len(val) > 1:
                return val

    # 2. English の English パターン (例: BeatlesのYellow submarine)
    m_eng = re.search(r'([a-zA-Z0-9\s\'\-]{2,})の([a-zA-Z0-9\s\'\-]{2,})', description)
    if m_eng:
        return f"{m_eng.group(1).strip()} {m_eng.group(2).strip()}"

    # 3. アルファベット・数字の単語を抽出し、指示語やジャンル名などのノイズを除去して結合
    words = re.findall(r'[a-zA-Z0-9\-\']+', description)
    noise_genres_instructions = {
        'avici', 'avicii', 'edm', 'trance', 'lofi', 'jazz', 'rock', 'pop', 'ambient', 'chillhop',
        'triphop', 'synthwave', 'folk', 'metal', 'funk', 'reggae', 'techno', 'house', 'classical',
        'rnb', 'cover', 'arrange', 'play', 'compose', 'make', 'create', 'style', 'song', 'music', 'bgm'
    }
    filtered = [w for w in words if w.lower() not in noise_genres_instructions]
    if len(filtered) >= 2:
        return ' '.join(filtered)

    # 4. フォールバック: 元のクリーニング処理
    cleaned = description
    cleaned = re.sub(r'(?i)\b(arrange|play|compose|make|create|cover|rendering|render)\b', '', cleaned)
    noise_patterns = [
        r'を?.*風に?(アレンジ|作曲|演奏|再生|カバー)?して?',
        r'の曲',
        r'風$',
        r'風の曲',
        r'スタイル',
        r'っぽく',
        r'っぽい'
    ]
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, '', cleaned)
        
    cleaned = cleaned.replace("の", " ").replace("by", " ").strip()
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    if len(cleaned) > 2:
        return cleaned
    return None

def search_chords_online(song_query: str) -> Optional[List[str]]:
    """インターネットを検索し、指示された曲のコード進行譜を自動で探し出す"""
    import urllib.request
    import urllib.parse
    import re
    
    print(f"[Online Chord Search] Searching chords online for: {song_query}")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive"
        }
        search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(song_query + ' chords')}"
        req = urllib.request.Request(search_url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode("utf-8", errors="ignore")
            
        redirect_urls = re.findall(r'uddg=([^&"#]+)', html)
        decoded_urls = []
        seen_urls = set()
        for u in redirect_urls:
            dec = urllib.parse.unquote(u)
            if dec not in seen_urls:
                seen_urls.add(dec)
                decoded_urls.append(dec)
            
        # 候補となるURLをフィルタリングして収集（最大6個まで試す）
        candidate_urls = []
        for u in decoded_urls:
            u_lower = u.lower()
            # クローラー規制（403等）の厳しいサイトやコード譜形式でないサイトを事前に除外する
            if any(domain in u_lower for domain in ["ultimate-guitar.com", "e-chords.com", "songsterr.com", "gprotab.net"]):
                continue
            if any(domain in u_lower for domain in ["chord", "tab", "guitar", "music", "tabs"]):
                candidate_urls.append(u)
                
        # バックアップとして、上位3つのURLも追加しておく
        for u in decoded_urls[:3]:
            if u not in candidate_urls and "ultimate-guitar.com" not in u and "y.js" not in u:
                candidate_urls.append(u)
                
        if not candidate_urls:
            print("[Online Chord Search] No search results found.")
            return None
            
        # 各候補URLから順にコード抽出を試みるループ
        for target_url in candidate_urls[:6]:
            print(f"[Online Chord Search] Trying chords page: {target_url}")
            try:
                req_page = urllib.request.Request(target_url, headers=headers)
                with urllib.request.urlopen(req_page, timeout=8) as response_page:
                    page_html = response_page.read().decode("utf-8", errors="ignore")
                    
                # メタ記述(description)からコード進行が抽出できる場合が多いため、退避させて結合する
                meta_desc = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', page_html, flags=re.IGNORECASE)
                meta_text = meta_desc.group(1) if meta_desc else ""
                
                clean_text = re.sub(r'<script.*?</script>', '', page_html, flags=re.DOTALL)
                clean_text = re.sub(r'<style.*?</style>', '', clean_text, flags=re.DOTALL)
                clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
                
                # メタテキストを先頭にマージ
                clean_text = meta_text + "\n" + clean_text
                
                extracted = extract_chords_from_raw_tab(clean_text)
                if len(extracted) >= 4:
                    print(f"[Online Chord Search] Successfully extracted {len(extracted)} chords: {extracted[:12]}...")
                    return extracted
                print(f"[Online Chord Search] Extracted only {len(extracted)} chords, skipping page.")
            except Exception as page_err:
                print(f"[Online Chord Search] Failed to fetch/parse {target_url}: {page_err}")
                
        print("[Online Chord Search] All candidate URLs failed to yield valid chords.")
    except Exception as e:
        print(f"[Online Chord Search] Search failed: {e}")
        
    return None

def get_song_structure(total_bars_needed: int, key_mode: str, style: str, custom_chords_tuple: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """音楽理論的セオリーに基づき、イントロ、サビ、Aメロ、Bメロ、アウトロの曲構成とコード進行を構築する"""
    
    # 決定論的なマンネリを防ぐため、毎回異なるコード進行プールから選択
    # 決定論的なマンネリを防ぐため、多数の音楽理論的・歴史的コード進行パターンからランダムに選択
    # メジャーキー進行（Aメロ）
    major_verse_pools = {
        "pop": [
            ["C", "G", "Am", "Em"],          # カノン進行前半風
            ["C", "Am", "F", "G"],           # 50年代進行 (Stand By Me)
            ["Am", "F", "C", "G"],           # 朝陽進行 (Sensitive Pop)
            ["C", "G/B", "Am", "G"],         # ベースライン順次下降進行
            ["C", "F", "C", "G"]             # I-IV-I-V シンプルフォーク
        ],
        "jazz": [
            ["Dm7", "G7", "Cmaj7", "A7"],     # 1-6-2-5の循環進行
            ["Cmaj7", "Am7", "Dm7", "G7"],    # Rhythm Changes
            ["Dm7", "G7", "Em7", "Am7"],      # 2-5-3-6 進行
            ["Fmaj7", "Bb7", "Cmaj7", "A7"],  # バックドア・ドミナント
            ["Cmaj7", "Ebdim7", "Dm7", "G7"]  # パッシングディミニッシュ
        ],
        "rock": [
            ["C", "F", "G", "C"],             # I-IV-V-I 基本ロック
            ["C", "Bb", "F", "C"],            # ミクソリディアンロック (Hey Jude風)
            ["C", "G", "F", "F"],             # I-V-IV-IV スタジアムロック
            ["Am", "G", "F", "G"],            # 80年代バラード進行
            ["C5", "G5", "A5", "F5"]          # パワーコード進行
        ],
        "ambient": [
            ["Cmaj7", "Fmaj7", "Cmaj7", "Fmaj7"], # 1-4フローティング
            ["Cmaj7", "G6", "Am7", "Fmaj7"],     # モーダル展開
            ["Fmaj7", "G6", "Em7", "Am7"],       # ドリーミー展開
            ["Cmaj7", "D7", "Fmaj7", "Cmaj7"]    # リディアン風味
        ],
        "edm": [
            ["Am", "F", "C", "G"],            # 王道EDM 4コード
            ["F", "Am", "G", "C"],            # Avicii風ループ
            ["C", "Em", "Am", "F"]            # 高揚系メロディックEDM
        ],
        "trance": [
            ["Am", "F", "C", "G"],            # クラシックトランス定番
            ["F", "G", "Am", "Em"],           # 叙情トランス
            ["Dm", "Bb", "F", "C"]            # 浮遊系トランス
        ],
        "chillhop": [
            ["Fmaj7", "E7", "Am7", "Gm7", "C7"], # Nujabes風 ジャズヒップホップ
            ["Cmaj7", "Am7", "Dm7", "G7"],    # 2-5-1 循環
            ["Dm7", "G7", "Em7", "Am7"]        # メロウヒップホップ
        ],
        "triphop": [
            ["Cmaj7", "Abmaj7", "Dm7", "G7"], # ダークチルアウト
            ["Cmaj7", "Fmaj7", "Fm6", "Cmaj7"] # 憂鬱なメロウ
        ]
    }
    
    # メジャーキー進行（サビ）
    major_chorus_pools = {
        "pop": [
            ["Fmaj7", "G7", "Em7", "Am7"],    # 王道進行 (IV-V-III-VI)
            ["C", "G", "Am", "F"],            # 洋楽ポップ王道 (I-V-VI-IV)
            ["F", "G", "C", "C"],             # 順次上昇解決進行
            ["C", "Am", "Em", "F"],           # 叙情ポップサビ
            ["Dm7", "G7", "C", "Am"]          # 2-5-1-6 解決型
        ],
        "jazz": [
            ["Fmaj7", "Fm6", "Em7", "A7"],    # サブドミナントマイナー解決
            ["Cmaj7", "A7", "Dm7", "G7"],     # 1-6-2-5 ターンアラウンド
            ["Dm7", "G7", "Em7b5", "A7"],     # セカンダリードミナント経由
            ["Fmaj7", "G7", "Cmaj7", "C7"]     # ブルース解決
        ],
        "rock": [
            ["F", "G", "Am", "C"],            # IV-V-VI-I 高揚進行
            ["Am", "F", "C", "G"],            # 高エネルギーロックサビ (VI-IV-I-V)
            ["C", "G", "D", "D"],             # ダブルプラガルロック
            ["D", "C", "G", "D"]              # クラシック・ロックアンセム風
        ],
        "ambient": [
            ["Am7", "Fmaj7", "Cmaj7", "G6"],  # 幻想的終止
            ["Cmaj7", "Em7", "Fmaj7", "G"],   # ゆっくりとした上昇
            ["Dm7", "Fmaj7", "G6", "Am7"]     # 催眠的リピート
        ],
        "edm": [
            ["F", "G", "Am", "C"],            # 上昇解決サビ
            ["Am", "F", "C", "G"],            # 定番ループ
            ["Fmaj7", "Am7", "G", "C"]        # メロウ解決
        ],
        "trance": [
            ["F", "G", "Am", "G"],            # 疾走サビ
            ["Am", "F", "C", "G"],            # 哀愁トランスループ
            ["Fmaj7", "G", "Am", "Em"]        # エピックトランス解決
        ],
        "chillhop": [
            ["Dm7", "G7", "Cmaj7", "Cmaj7"],  # ジャジーヒップホップ終止
            ["Fmaj7", "Bb7", "Cmaj7", "A7"]   # バックドアサビ解決
        ],
        "triphop": [
            ["Am7", "Fmaj7", "Dm7", "Em7"],   # チルアウト解決
            ["Cmaj7", "Ab7", "Dbmaj7", "G7"]  # ダークネオソウル
        ]
    }
    
    # マイナーキー進行（Aメロ）
    minor_verse_pools = {
        "pop": [
            ["Am", "F", "C", "G"],            # 小室進行 / マイナーポップ定番
            ["Am", "Em", "F", "C"],           # 暗から明へのグラデーション
            ["Am", "Dm", "G", "C"],           # 五度圏マイナー進行
            ["Am", "G", "F", "E7"],           # アンダルシア進行
            ["Am", "Am", "Dm", "E7"]          # 民族調マイナー
        ],
        "jazz": [
            ["Dm7b5", "G7", "Cm7", "Abmaj7"], # 2-5-1-6 マイナー
            ["Am7", "D7", "Bm7b5", "E7"],     # ドリアン・ジャズ進行
            ["Am7", "Fmaj7", "Bm7b5", "E7"],  # 1-6-2-5 マイナー
            ["Dm7", "G7", "Cmaj7", "Fmaj7"]   # スムースサークル進行
        ],
        "rock": [
            ["Am", "G", "F", "E7"],           # アンダルシアロック進行
            ["Am", "F", "G", "Am"],           # パワーマイナーロック
            ["Am", "C", "D", "F"],            # ドリアンロック (Pink Floyd風)
            ["Am", "G", "Am", "G"]            # クラシックマイナージャム
        ],
        "ambient": [
            ["Am7", "Dm7", "Fmaj7", "Em7"],   # ダークメディテーション
            ["Am7", "Em7", "Fmaj7", "G6"],    # フローティングマイナー
            ["Am7", "Bm7b5", "Cmaj7", "Em7"]  # ドリアンアンビエント
        ],
        "edm": [
            ["Am", "F", "C", "G"],            # マイナーポップ調EDM
            ["F", "Dm", "Am", "G"]            # ディープハウス風
        ],
        "trance": [
            ["Am", "F", "C", "G"],            # Robert Miles風 Childrenコード進行
            ["Am", "Em", "F", "G"]            # 哀愁マイナートランス
        ],
        "chillhop": [
            ["Am7", "D7", "Gmaj7", "Cmaj7"],  # ネオソウル風コードループ
            ["Am7", "Dm7", "G7", "Cmaj7"]     # ジャジーメロウマイナー
        ],
        "triphop": [
            ["Am", "Fmaj7", "Dm7", "E7"],     # ダークトリップホップ
            ["Am7", "Bm7b5", "E7", "Am7"]     # 憂鬱マイナー循環
        ]
    }
    
    # マイナーキー進行（サビ）
    minor_chorus_pools = {
        "pop": [
            ["F", "G", "Am", "C"],            # VI-VII-I-III クライマックス進行
            ["Am", "F", "C", "G"],            # 王道マイナーサビ
            ["Dm", "G", "C", "Am"],           # サブドミナント解決
            ["F", "G", "Em", "Am"]            # VI-VII-v-i ドラマチック終止
        ],
        "jazz": [
            ["Fmaj7", "E7", "Am7", "Am7"],    # VI-V-i-i ターンアラウンド
            ["Bm7b5", "E7", "Am7", "A7"],     # iiø-V-i-VI7
            ["Dm7", "G7", "Cmaj7", "Fmaj7"],  # サークルオブフィフスサビ
            ["Am7", "D7", "Gmaj7", "Cmaj7"]   # メジャーマイナー境界進行
        ],
        "rock": [
            ["F", "G", "Am", "Am"],           # VI-VII-i-i パワフルロック終止
            ["Am", "G", "F", "G"],            # 標準的な哀愁ハードロックサビ
            ["F", "C", "G", "Am"],            # VI-III-VII-i エピックロック
            ["Am", "F", "G", "E7"]            # ヘヴィドラマチックサビ
        ],
        "ambient": [
            ["Fmaj7", "G6", "Am7", "Em7"],    # ソフトランディング終止
            ["Am7", "Fmaj7", "Dm7", "Em7"]     # メロウマイナー終止
        ],
        "edm": [
            ["F", "G", "Am", "Em"],           # ドラマチック終止
            ["Am", "F", "C", "G"]             # フェスアンセム定番
        ],
        "trance": [
            ["F", "G", "Am", "G"],            # トランスサビ解放
            ["Am", "F", "C", "G"]             # 定番哀愁
        ],
        "chillhop": [
            ["Fmaj7", "E7", "Am7", "Am7"],    # 哀愁ヒップホップ
            ["Dm7", "G7", "Cmaj7", "Fmaj7"]   # スムース解決サビ
        ],
        "triphop": [
            ["Am", "Dm", "Fmaj7", "Bbmaj7"],  # 絶望と叙情の狭間
            ["Fmaj7", "E7", "Am7", "Am7"]     # ダーク解決サビ
        ]
    }
    
    style_mapped = style.lower() if style.lower() in ("pop", "jazz", "rock", "ambient", "edm", "trance", "chillhop", "triphop") else "pop"
    if style.lower() in ("bossanova", "bossa", "lofi"):
        style_mapped = "jazz"
    elif style.lower() in ("synthwave", "house", "techno"):
        style_mapped = "edm"
    elif style.lower() == "folk":
        style_mapped = "ambient"
    elif style.lower() == "metal":
        style_mapped = "rock"
    elif style.lower() in ("funk", "rnb"):
        style_mapped = "jazz"
    elif style.lower() == "classical":
        style_mapped = "ambient"
    elif style.lower() == "reggae":
        style_mapped = "pop"
        
    if custom_chords_tuple:
        verse_chords, chorus_chords = custom_chords_tuple
    else:
        # マンネリ打破のための動的・ランダムなコード進行生成アルゴリズム (確率 85%)
        # これにより、固定パターン以外の無数の音楽的に正しい進行が生まれ続けます
        if random.random() < 0.85:
            if key_mode == "minor":
                # マイナーキーの機能的和声進行 (i -> bVI -> iv/bVII -> v/V)
                v_start = random.choice(["Am", "F", "Dm", "C"])
                v2 = random.choice(["F", "Dm", "G", "Am", "Bb"])
                v3 = random.choice(["G", "C", "Em", "Fmaj7", "Dm7"])
                v4 = random.choice(["Em", "Am", "E7", "G", "C"])
                verse_chords = [v_start, v2, v3, v4]
                
                c_start = random.choice(["F", "Dm", "Fmaj7", "Bb"])
                c2 = random.choice(["G", "Em", "C", "E7"])
                c3 = random.choice(["Am", "F", "Dm", "C"])
                c4 = random.choice(["G", "Am", "Em", "F"])
                chorus_chords = [c_start, c2, c3, c4]
            else:
                # メジャーキーの機能的和声進行 (I -> IV -> V/vii -> vi/iii)
                v_start = random.choice(["C", "Am", "F", "Cmaj7"])
                v2 = random.choice(["F", "Dm", "G", "Am7"])
                v3 = random.choice(["G", "Em", "C", "G7", "Dm7"])
                v4 = random.choice(["Am", "F", "G", "C", "Em"])
                verse_chords = [v_start, v2, v3, v4]
                
                c_start = random.choice(["F", "Dm", "C", "Fmaj7"])
                c2 = random.choice(["G", "Em", "Am", "D7"])
                c3 = random.choice(["Am", "F", "C", "Dm7"])
                c4 = random.choice(["G", "C", "Am", "F"])
                chorus_chords = [c_start, c2, c3, c4]
        else:
            # 60% の確率はプールから定番進行を選択
            if key_mode == "minor":
                verse_chords = random.choice(minor_verse_pools[style_mapped])
                chorus_chords = random.choice(minor_chorus_pools[style_mapped])
            else:
                verse_chords = random.choice(major_verse_pools[style_mapped])
                chorus_chords = random.choice(major_chorus_pools[style_mapped])

        # コード進行のミューテーション（突然変異）(確率 30%)
        # トライアド（3和音）をランダムにセブンスコード（7th）やサスフォー（sus4）などにアップグレードして響きを豊かにする
        if random.random() < 0.30:
            def mutate_chord(c: str) -> str:
                if len(c) > 2 and any(suffix in c for suffix in ("maj7", "m7", "sus4", "7", "9")):
                    return c
                # セブンスコードへのアップグレード
                if c.endswith("m"):
                    return c + "7" if random.random() < 0.5 else c
                elif c in ("C", "F", "G", "D", "A", "E"):
                    if c == "G":
                        return "G7" if random.random() < 0.5 else c
                    return c + "maj7" if random.random() < 0.5 else c
                return c

            verse_chords = [mutate_chord(c) for c in verse_chords]
            chorus_chords = [mutate_chord(c) for c in chorus_chords]

    # Bメロ（Bridge）用コード進行：サビへの緊張感を高める進行（サブドミナントから開始など）
    bridge_chords = [verse_chords[2], verse_chords[3], chorus_chords[0], chorus_chords[1]]
    
    # 毎回異なるコード進行にするため、Cメジャー/Aマイナーからランダムにキー転調 (Transposition Offset) を施す
    key_offset = random.randint(-5, 6)
    
    sections_layout = []
    
    # 短尺時と長尺時で構成を変更
    if total_bars_needed <= 8:
        # 短尺：Aメロ ➡ サビ
        sections_layout.append({"name": "verse", "bars": total_bars_needed // 2, "chords": verse_chords, "intensity": "low"})
        sections_layout.append({"name": "chorus", "bars": total_bars_needed - (total_bars_needed // 2), "chords": chorus_chords, "intensity": "high"})
    else:
        # 長尺：イントロ ➡ Aメロ ➡ Bメロ ➡ サビ ➡ 間奏 ➡ Aメロ ➡ Bメロ ➡ サビ ➡ アウトロ
        intro_bars = 4
        outro_bars = 4
        middle_bars = total_bars_needed - intro_bars - outro_bars
        
        sections_layout.append({"name": "intro", "bars": intro_bars, "chords": verse_chords, "intensity": "low"})
        
        current_middle = 0
        cycle = 0
        while current_middle < middle_bars:
            remaining = middle_bars - current_middle
            
            if cycle % 3 == 0:
                # Aメロ (Verse)
                bars = min(8, remaining)
                sections_layout.append({"name": "verse", "bars": bars, "chords": verse_chords, "intensity": "low"})
            elif cycle % 3 == 1:
                # Bメロ (Bridge) - 中間的な盛り上がり
                bars = min(4, remaining)
                sections_layout.append({"name": "bridge", "bars": bars, "chords": bridge_chords, "intensity": "medium"})
            else:
                # サビ (Chorus) - 最大の盛り上がり
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

PROGRESSION_MAP = {
    # Major key custom progressions (Verse, Chorus)
    "royal_road": (["Fmaj7", "G7", "Em7", "Am7"], ["Fmaj7", "G7", "Em7", "Am7"]),
    "canon": (["C", "G", "Am", "Em", "F", "C", "F", "G"], ["C", "G", "Am", "Em", "F", "C", "F", "G"]),
    "stand_by_me": (["C", "Am", "F", "G"], ["C", "Am", "F", "G"]),
    "descending_bass": (["C", "G/B", "Am", "G"], ["C", "G/B", "Am", "G"]),
    "simple_folk": (["C", "F", "C", "G"], ["C", "F", "C", "G"]),
    "noel": (["Em7", "G", "Dsus4", "A7sus4"], ["C", "G/B", "Am", "Fmaj7"]), # Noel Gallagher風
    
    # Minor key custom progressions (Verse, Chorus)
    "komuro": (["Am", "F", "C", "G"], ["F", "G", "Am", "C"]),
    "andalusian": (["Am", "G", "F", "E7"], ["F", "G", "Am", "Am"]),
    "fifths": (["Am", "Dm", "G", "C"], ["Dm", "G", "C", "Am"]),
    "dorian_rock": (["Am", "C", "D", "F"], ["Am", "G", "F", "G"]),
    "edm_loop": (["Am", "F", "C", "G"], ["Fmaj7", "Am7", "G", "C"]), # EDM風ループ
    "trance_epic": (["Am", "F", "C", "G"], ["F", "G", "Am", "Em"]), # エピックトランス風
    "jazzy_hop": (["Fmaj7", "E7", "Am7", "Gm7", "C7"], ["Dm7", "G7", "Cmaj7", "A7"]), # Nujabes風ジャズヒップホップ
    "triphop_dark": (["Am", "Fmaj7", "Dm7", "E7"], ["Am7", "Dm7", "Fmaj7", "Bbmaj7"]) # トリップホップ風ダーク進行
}

def expand_chord_plan_to_midi(plan: Dict[str, Any], duration_minutes: float) -> MidiComposition:
    """高次のコード進行・構成プランを具体的なMIDIノート（MidiComposition）へ拡張・展開する"""
    import time
    random.seed(time.time_ns())
    
    # 決定論的なマンネリを防ぐため、楽曲ごとに異なる伴奏アレンジパターンをランダム選択
    piano_rhythm_pattern = random.choice(["standard", "syncopated", "offbeat", "ballad_arpeggio"])
    guitar_arpeggio_pattern = random.choice(["classic_arp", "broken_chord", "syncopated_strum", "walking_arp"])
    bass_rhythm_pattern = random.choice(["standard_bass", "walking_bass", "syncopated_bass", "bounce_bass"])
    drum_fill_frequency = random.choice([2, 4, 8])
    
    tempo_bpm = int(plan.get("tempo_bpm", 80))
    key_mode = plan.get("key_mode", "major")
    style = plan.get("style", "lofi").lower()
    
    # ジャンル指定のオーバーライド
    genre = plan.get("genre", "auto")
    desc = plan.get("description", "")
    desc_lower = desc.lower()
    
    # 指示文から明示的なスタイル指定があるかチェック
    styles_list = ["lofi", "jazz", "pop", "ambient", "rock", "edm", "trance", "chillhop", "triphop", "bossanova", "bossa", "funk", "grunge", "metal", "nirvana"]
    japanese_styles_map = {
        "ボサノバ": "bossanova", "ボサノヴァ": "bossanova",
        "ジャズ": "jazz", "ポップ": "pop", "ロック": "rock",
        "アンビエント": "ambient", "ファンク": "funk",
        "グランジ": "rock", "メタル": "rock", "ニルヴァーナ": "rock", "ニルバーナ": "rock"
    }
    
    detected_desc_style = None
    for s in styles_list:
        if s in desc_lower:
            detected_desc_style = s
            break
    if not detected_desc_style:
        for jp_s, eng_s in japanese_styles_map.items():
            if jp_s in desc_lower:
                detected_desc_style = eng_s
                break
                
    # スタイルの決定優先度：UI上のジャンル指定 (auto以外) を最優先し、次に指示文からの自動検出を適用する
    if genre != "auto":
        style = genre.lower()
        if style == "lofi":
            style = "jazz"
        elif style == "bossa":
            style = "bossanova"
    elif detected_desc_style:
        style = detected_desc_style
        if style == "bossa":
            style = "bossanova"
        elif style in ("nirvana", "grunge"):
            style = "rock"
            
    # トランス/チルホップ/トリップホップおよび新ジャンルのテンポを設定
    if style in ("trance", "dream_house"):
        tempo_bpm = 138
    elif style in ("bossanova", "bossa"):
        tempo_bpm = 120
    elif style == "chillhop":
        tempo_bpm = 85
    elif style == "triphop":
        tempo_bpm = 74
    elif style == "synthwave":
        tempo_bpm = 115
    elif style == "folk":
        tempo_bpm = 88
    elif style == "metal":
        tempo_bpm = 130
    elif style == "funk":
        tempo_bpm = 105
    elif style == "reggae":
        tempo_bpm = 76
    elif style == "techno":
        tempo_bpm = 126
    elif style == "house":
        tempo_bpm = 122
    elif style == "classical":
        tempo_bpm = 72
    elif style == "rnb":
        tempo_bpm = 84
            
    instruments = plan.get("instruments", ["piano", "guitar", "bass", "drums"])
    
    # physical パラメータの取得とスケーラー計算
    brightness = float(plan.get("brightness", 0.5))
    energy = float(plan.get("energy", 0.5))
    density = float(plan.get("density", 0.5))
    energy_factor = 0.4 + energy * 1.2
    
    # 指定の再生時間をカバーするのに必要な総小節数を計算
    seconds_per_beat = 60.0 / tempo_bpm
    seconds_per_bar = seconds_per_beat * 4.0
    target_seconds = duration_minutes * 60.0
    total_bars_needed = max(4, int(target_seconds / seconds_per_bar))
    
    # カスタムDSL進行指定のチェック
    custom_chords = plan.get("custom_chords")
    
    # スキーマ例のダミー値（C-G-Am-F等）と同じなら、LLMのデフォルトコピペとみなして無視する
    if custom_chords and isinstance(custom_chords, dict):
        v = custom_chords.get("verse", [])
        c = custom_chords.get("chorus", [])
        if v == ["C", "G", "Am", "F"] and c == ["F", "G", "Em", "Am"]:
            print("[expand_chord_plan_to_midi] Dummy chords detected from LLM response. Ignoring custom_chords.")
            custom_chords = None

    if custom_chords:
        if isinstance(custom_chords, dict):
            # LLM / データベース形式 {"verse": [...], "chorus": [...]}
            verse_chords = custom_chords.get("verse") or ["C"]
            chorus_chords = custom_chords.get("chorus") or ["C"]
        else:
            # フラットリスト (DSL形式)
            verse_chords = custom_chords
            chorus_chords = custom_chords
            
        # スタイルに応じてコード進行を自動アレンジする
        verse_chords = arrange_chords_by_style(verse_chords, style)
        chorus_chords = arrange_chords_by_style(chorus_chords, style)
            
        # 指示文からキーオフセット（転調）をパースする
        description = plan.get("description", "")
        key_offset = parse_key_offset_from_description(description)
        
        # 毎回同じキーで再生されるのを避けるために、マンネリ防止の自動転調を適用する
        if key_offset == 999:
            key_offset = 0
        elif key_offset == 0:
            key_offset = random.choice([-3, -2, -1, 2, 3, 4])
        
        sections = []
        current_bar = 0
        while current_bar < total_bars_needed:
            remaining_bars = total_bars_needed - current_bar
            
            name = "verse" if (current_bar // 8) % 2 == 0 else "chorus"
            section_bars = min(8, remaining_bars)
            if section_bars <= 0:
                break
                
            chords_to_use = verse_chords if name == "verse" else chorus_chords
            intensity = "low" if name == "verse" else "high"
            
            sections.append({
                "name": name,
                "start_bar": current_bar,
                "bars": section_bars,
                "chords": chords_to_use,
                "intensity": intensity,
                "key_offset": key_offset
            })
            current_bar += section_bars
    else:
        # コード進行のオーバーライド
        chord_prog = plan.get("chord_progression", "auto")
        custom_tuple = None
        if chord_prog != "auto" and chord_prog in PROGRESSION_MAP:
            custom_tuple = PROGRESSION_MAP[chord_prog]
            
        # 曲のセクション構成を動的に生成
        sections = get_song_structure(total_bars_needed, key_mode, style, custom_chords_tuple=custom_tuple)

    # 各楽器トラックごとのノート生成
    # リズムバリエーションをランダム決定 (曲ごとに異なるビート感を演出)
    chillhop_pattern = random.choice([0, 1, 2])
    jazz_pattern = random.choice([0, 1])
    piano_pattern = random.choice([0, 1, 2])
    bass_pattern = random.choice([0, 1, 2])

    # セクション種別ごとに1トラック：track_notes[楽器][セクション名] = [ノート]
    track_notes: Dict[str, Dict[str, List[MidiNote]]] = {
        "piano": {},
        "guitar": {},
        "bass": {},
        "drums": {},
        "melody": {}
    }
    current_sec_name: str = "verse"  # セクションループ内で更新

    def tnote(inst: str, note: MidiNote) -> None:
        """現在のセクション種別バケットにノートを追加するヘルパー"""
        bucket = track_notes[inst]
        if current_sec_name not in bucket:
            bucket[current_sec_name] = []
        bucket[current_sec_name].append(note)

    for sec in sections:
        start_bar = sec["start_bar"]
        bars = sec["bars"]
        chords = sec["chords"]
        intensity = sec["intensity"]
        key_offset = sec["key_offset"]
        current_sec_name = sec["name"]  # ヘルパーで参照
        
        if not chords:
            chords = ["C"]
            
        for b in range(bars):
            bar_index = start_bar + b
            base_step = bar_index * 16
            
            # セクションや小節によって演奏パターンを動的に切り替えて単調さを防ぐ（マルチトラック・バリエーション）
            if intensity == "low" or sec["name"] in ("intro", "outro", "bridge"):
                # 静かなセクション用
                piano_pattern_to_use = "ballad_arpeggio"
                guitar_pattern_to_use = "classic_arp"
                bass_pattern_to_use = "standard_bass"
            else:
                # 賑やかなセクション（サビなど）用。偶数/奇数小節で切り替えて人間味を出す
                if b % 2 == 0:
                    piano_pattern_to_use = "syncopated"
                    guitar_pattern_to_use = "syncopated_strum"
                    bass_pattern_to_use = "syncopated_bass"
                else:
                    piano_pattern_to_use = "offbeat"
                    guitar_pattern_to_use = "broken_chord"
                    bass_pattern_to_use = "bounce_bass"
            
             # 各小節のコード進行
            chord_name = chords[b % len(chords)]
            pitches = get_chord_pitches(chord_name, key_offset)
            
            # 1. ピアノ（コード・伴奏）トラック
            if "piano" in instruments:
                if style in ("bossanova", "bossa"):
                    # ボサノバ特有のコンピングパターン
                    if b % 2 == 0:
                        offsets = [0, 3, 6, 10, 13]
                    else:
                        offsets = [2, 6, 8, 11, 14]
                    for step_offset in offsets:
                        for p in pitches:
                            tnote("piano", MidiNote(step=base_step + step_offset, pitch=p, velocity=65, duration_steps=2))
                elif style == "reggae":
                    # レゲエ特有のスカンク（裏打ち）バッキング
                    # 2拍目と4拍目の頭（または各拍の裏）で「チャッ、チャッ」と短く和音を刻む
                    for step_offset in [2, 6, 10, 14]:
                        for p in pitches:
                            tnote("piano", MidiNote(step=base_step + step_offset, pitch=p, velocity=65, duration_steps=1))
                elif style in ("jazz", "lofi", "chillhop"):
                    # ジャズ/ローファイ/チルホップのバッキングバリエーション
                    if piano_pattern == 0:
                        # コンピング（裏打ち）
                        if b % 2 == 0:
                            offsets = [2, 6, 12]
                        else:
                            offsets = [0, 10, 14]
                        for step_offset in offsets:
                            for p in pitches:
                                tnote("piano", MidiNote(step=base_step + step_offset, pitch=p, velocity=60, duration_steps=2))
                    elif piano_pattern == 1:
                        # 4つ打ちコード（まったりしたバッキング）
                        for step_offset in [0, 4, 8, 12]:
                            for p in pitches:
                                tnote("piano", MidiNote(step=base_step + step_offset, pitch=p, velocity=55, duration_steps=3))
                    else:
                        # アルペジオ分散和音
                        for i, p in enumerate(pitches):
                            step_offset = i * 4
                            tnote("piano", MidiNote(step=base_step + step_offset, pitch=p, velocity=55, duration_steps=4))
                elif intensity == "low":
                    if piano_pattern_to_use == "ballad_arpeggio":
                        # アルペジオ分散和音
                        for i, p in enumerate(pitches):
                            step_offset = i * 4
                            tnote("piano", MidiNote(step=base_step + step_offset, pitch=p, velocity=60, duration_steps=4))
                    else:
                        duration = random.choice([12, 14, 15])
                        for p in pitches:
                            tnote("piano", MidiNote(step=base_step + 0, pitch=p, velocity=60, duration_steps=duration))
                else:
                    # サビ（高強度）のバッキングパターン分岐
                    if piano_pattern_to_use == "syncopated":
                        offsets = [0, 3, 8, 11] if b % 2 == 0 else [0, 3, 6, 12]
                        for step_offset in offsets:
                            for p in pitches:
                                tnote("piano", MidiNote(step=base_step + step_offset, pitch=p, velocity=75, duration_steps=3))
                    elif piano_pattern_to_use == "offbeat":
                        # オフビートで弾むパターン
                        for step_offset in [2, 6, 10, 14]:
                            for p in pitches:
                                tnote("piano", MidiNote(step=base_step + step_offset, pitch=p, velocity=72, duration_steps=2))
                    elif piano_pattern_to_use == "ballad_arpeggio":
                        # 4つ刻みのバッキング
                        for step_offset in [0, 4, 8, 12]:
                            for p in pitches:
                                tnote("piano", MidiNote(step=base_step + step_offset, pitch=p, velocity=70, duration_steps=3))
                    else:
                        # "standard" パターン
                        if (b + 1) % 4 == 0:
                            for p in pitches:
                                tnote("piano", MidiNote(step=base_step + 0, pitch=p, velocity=75, duration_steps=4))
                                tnote("piano", MidiNote(step=base_step + 6, pitch=p, velocity=75, duration_steps=4))
                                tnote("piano", MidiNote(step=base_step + 12, pitch=p, velocity=70, duration_steps=3))
                        elif b % 2 == 1:
                            for p in pitches:
                                tnote("piano", MidiNote(step=base_step + 0, pitch=p, velocity=75, duration_steps=6))
                                tnote("piano", MidiNote(step=base_step + 6, pitch=p, velocity=70, duration_steps=4))
                                tnote("piano", MidiNote(step=base_step + 12, pitch=p, velocity=65, duration_steps=3))
                        else:
                            for p in pitches:
                                tnote("piano", MidiNote(step=base_step + 0, pitch=p, velocity=75, duration_steps=6))
                                tnote("piano", MidiNote(step=base_step + 8, pitch=p, velocity=70, duration_steps=6))
                    
            # 2. ギター（アルペジオ）トラック
            if "guitar" in instruments:
                if style in ("bossanova", "bossa"):
                    # ギターもボサノバ特有のバッキングパターン
                    if b % 2 == 0:
                        offsets = [0, 3, 6, 8, 11, 14]
                    else:
                        offsets = [0, 4, 6, 10, 14]
                    for step_offset in offsets:
                        for p in pitches:
                            tnote("guitar", MidiNote(step=base_step + step_offset, pitch=p + 12, velocity=60, duration_steps=2))
                elif style in ("jazz", "lofi"):
                    # ジャズ・ギター（4つ打ちコンピングまたはオフビート）
                    if b % 2 == 0:
                        offsets = [4, 12]
                    else:
                        offsets = [0, 8]
                    for step_offset in offsets:
                        for p in pitches:
                            tnote("guitar", MidiNote(step=base_step + step_offset, pitch=p + 12, velocity=55, duration_steps=2))
                elif intensity == "low":
                    offsets = [0, 8] if b % 2 == 0 else [0, 4, 8, 12]
                    for i, step_offset in enumerate(offsets):
                        pitch_val = pitches[i % len(pitches)] + 12
                        tnote("guitar", MidiNote(step=base_step + step_offset, pitch=pitch_val, velocity=55, duration_steps=4))
                else:
                    if guitar_pattern_to_use == "broken_chord":
                        # 低音と高音の交互アルペジオ
                        offsets = [0, 2, 4, 6, 8, 10, 12, 14]
                        for i, step_offset in enumerate(offsets):
                            if i % 2 == 0:
                                p_val = pitches[0] + 12
                            else:
                                p_val = pitches[i % len(pitches)] + 12
                            tnote("guitar", MidiNote(step=base_step + step_offset, pitch=p_val, velocity=60, duration_steps=2))
                    elif guitar_pattern_to_use == "syncopated_strum":
                        # リズミカルなカッティング風
                        for step_offset in [0, 3, 6, 8, 11, 14]:
                            p_val = pitches[step_offset % len(pitches)] + 12
                            tnote("guitar", MidiNote(step=base_step + step_offset, pitch=p_val, velocity=65, duration_steps=2))
                    elif guitar_pattern_to_use == "walking_arp":
                        # 上昇するアルペジオ
                        for i in range(8):
                            step_offset = i * 2
                            p_val = pitches[i % len(pitches)] + 12
                            tnote("guitar", MidiNote(step=base_step + step_offset, pitch=p_val, velocity=58, duration_steps=2))
                    else:
                        # "classic_arp" パターン
                        if b % 2 == 1:
                            extended_pitches = [pitches[0], pitches[2], pitches[1], pitches[0]]
                        else:
                            extended_pitches = [pitches[0], pitches[1], pitches[2], pitches[1]]
                        step_offsets = [0, 4, 8, 12]
                        for i, (step_offset, p) in enumerate(zip(step_offsets, extended_pitches)):
                            dur = 3 if i < 3 else (4 if (b + 1) % 4 == 0 else 3)
                            tnote("guitar", MidiNote(step=base_step + step_offset, pitch=p + 12, velocity=65, duration_steps=dur))
                    
            # 3. ベーストラック
            if "bass" in instruments:
                root_pitch = pitches[0] - 24  # 2オクターブ低く
                if style in ("bossanova", "bossa"):
                    fifth_pitch = pitches[2] - 24 if len(pitches) > 2 else root_pitch + 7
                    # 1拍目(0): ルート音
                    tnote("bass", MidiNote(step=base_step + 0, pitch=root_pitch, velocity=75, duration_steps=4))
                    # 2拍目裏(6): ルート音
                    tnote("bass", MidiNote(step=base_step + 6, pitch=root_pitch, velocity=70, duration_steps=2))
                    # 3拍目(8): 5度音
                    tnote("bass", MidiNote(step=base_step + 8, pitch=fifth_pitch, velocity=75, duration_steps=4))
                    # 4拍目裏(14): 経過音
                    next_chord_name = chords[(b + 1) % len(chords)]
                    next_pitches = get_chord_pitches(next_chord_name, key_offset)
                    next_root = next_pitches[0] - 24
                    approach_pitch = next_root + 1 if root_pitch > next_root else next_root - 1
                    tnote("bass", MidiNote(step=base_step + 14, pitch=approach_pitch, velocity=70, duration_steps=2))
                elif style in ("jazz", "lofi"):
                    # 常時ウォーキング・ベース
                    third_pitch = pitches[1] - 24 if len(pitches) > 1 else root_pitch + 4
                    fifth_pitch = pitches[2] - 24 if len(pitches) > 2 else root_pitch + 7
                    next_chord_name = chords[(b + 1) % len(chords)]
                    next_pitches = get_chord_pitches(next_chord_name, key_offset)
                    next_root = next_pitches[0] - 24
                    approach_pitch = next_root + 1 if root_pitch > next_root else next_root - 1
                    
                    # 1拍目: ルート
                    tnote("bass", MidiNote(step=base_step + 0, pitch=root_pitch, velocity=75, duration_steps=3))
                    # 2拍目: 3度
                    tnote("bass", MidiNote(step=base_step + 4, pitch=third_pitch, velocity=70, duration_steps=3))
                    # 3拍目: 5度
                    tnote("bass", MidiNote(step=base_step + 8, pitch=fifth_pitch, velocity=72, duration_steps=3))
                    # 4拍目: アプローチ音（経過音）
                    tnote("bass", MidiNote(step=base_step + 12, pitch=approach_pitch, velocity=70, duration_steps=3))
                elif style in ("chillhop", "lofi"):
                    # チルホップ/ローファイ用のベースバリエーション
                    if bass_pattern == 0:
                        # 1拍目と3拍目に合わせるシンプルなベース
                        tnote("bass", MidiNote(step=base_step + 0, pitch=root_pitch, velocity=75, duration_steps=6))
                        tnote("bass", MidiNote(step=base_step + 8, pitch=root_pitch, velocity=70, duration_steps=6))
                    elif bass_pattern == 1:
                        # シンコペーション（少し弾む）
                        tnote("bass", MidiNote(step=base_step + 0, pitch=root_pitch, velocity=75, duration_steps=4))
                        tnote("bass", MidiNote(step=base_step + 6, pitch=root_pitch, velocity=70, duration_steps=4))
                        tnote("bass", MidiNote(step=base_step + 12, pitch=root_pitch + 12, velocity=65, duration_steps=3))
                    else:
                        # 穏やかなルート白玉（ロングトーン）
                        tnote("bass", MidiNote(step=base_step + 0, pitch=root_pitch, velocity=70, duration_steps=14))
                elif style == "reggae":
                    # レゲエ特有のうねるベースライン（1拍目を抜くのが基本）
                    # ドラムのワンドロップ（ステップ8）に合わせて、ステップ 4, 8, 12 でシンコペーションする
                    tnote("bass", MidiNote(step=base_step + 4, pitch=root_pitch, velocity=80, duration_steps=2))
                    fifth_pitch = pitches[2] - 24 if len(pitches) > 2 else root_pitch + 7
                    tnote("bass", MidiNote(step=base_step + 8, pitch=fifth_pitch, velocity=85, duration_steps=2))
                    tnote("bass", MidiNote(step=base_step + 12, pitch=root_pitch, velocity=75, duration_steps=2))
                elif style == "synthwave":
                    # シンセウェーブ王道のオクターブ交互8分音符ベース (ズズズズという疾走感)
                    for h in range(8):
                        step_offset = h * 2
                        # 低音と高音（オクターブ上）を交互に演奏
                        pitch_val = root_pitch if h % 2 == 0 else root_pitch + 12
                        tnote("bass", MidiNote(step=base_step + step_offset, pitch=pitch_val, velocity=85, duration_steps=1))
                elif style == "trance":
                    # トランス用ローリングベースライン (16分音符 of ギャロップ)
                    for p_idx in range(4):
                        beat_offset = p_idx * 4
                        tnote("bass", MidiNote(step=base_step + beat_offset + 0, pitch=root_pitch, velocity=85, duration_steps=1))
                        tnote("bass", MidiNote(step=base_step + beat_offset + 2, pitch=root_pitch, velocity=80, duration_steps=1))
                        tnote("bass", MidiNote(step=base_step + beat_offset + 3, pitch=root_pitch, velocity=85, duration_steps=1))
                elif intensity == "low":
                    if b % 2 == 1 and len(pitches) > 2:
                        fifth_pitch = pitches[2] - 24
                        tnote("bass", MidiNote(step=base_step + 0, pitch=root_pitch, velocity=75, duration_steps=10))
                        tnote("bass", MidiNote(step=base_step + 12, pitch=fifth_pitch, velocity=65, duration_steps=3))
                    else:
                        tnote("bass", MidiNote(step=base_step + 0, pitch=root_pitch, velocity=75, duration_steps=14))
                else:
                    # サビ（高強度）のベースパターン分岐
                    if bass_pattern_to_use == "walking_bass":
                        fifth_pitch = pitches[2] - 24 if len(pitches) > 2 else root_pitch + 7
                        third_pitch = pitches[1] - 24 if len(pitches) > 1 else root_pitch + 4
                        steps_and_pitches = [
                            (0, root_pitch),
                            (4, third_pitch),
                            (8, fifth_pitch),
                            (12, root_pitch + 12 if random.random() < 0.5 else root_pitch)
                        ]
                        for step_val, p_val in steps_and_pitches:
                            tnote("bass", MidiNote(step=base_step + step_val, pitch=p_val, velocity=80, duration_steps=3))
                    elif bass_pattern_to_use == "syncopated_bass":
                        tnote("bass", MidiNote(step=base_step + 0, pitch=root_pitch, velocity=85, duration_steps=4))
                        tnote("bass", MidiNote(step=base_step + 6, pitch=root_pitch, velocity=80, duration_steps=4))
                        tnote("bass", MidiNote(step=base_step + 12, pitch=root_pitch, velocity=85, duration_steps=3))
                    elif bass_pattern_to_use == "bounce_bass":
                        tnote("bass", MidiNote(step=base_step + 0, pitch=root_pitch, velocity=85, duration_steps=3))
                        tnote("bass", MidiNote(step=base_step + 4, pitch=root_pitch + 12, velocity=78, duration_steps=3))
                        tnote("bass", MidiNote(step=base_step + 8, pitch=root_pitch, velocity=85, duration_steps=3))
                        tnote("bass", MidiNote(step=base_step + 12, pitch=root_pitch + 12, velocity=78, duration_steps=3))
                    else:
                        # "standard_bass"
                        next_chord_name = chords[(b + 1) % len(chords)]
                        next_pitches = get_chord_pitches(next_chord_name, key_offset)
                        next_root = next_pitches[0] - 24
                        
                        if (b + 1) % 4 == 0:
                            tnote("bass", MidiNote(step=base_step + 0, pitch=root_pitch, velocity=85, duration_steps=4))
                            tnote("bass", MidiNote(step=base_step + 6, pitch=root_pitch, velocity=80, duration_steps=4))
                            approach_pitch = next_root + 1 if root_pitch > next_root else next_root - 1
                            tnote("bass", MidiNote(step=base_step + 12, pitch=approach_pitch, velocity=85, duration_steps=3))
                        else:
                            tnote("bass", MidiNote(step=base_step + 0, pitch=root_pitch, velocity=85, duration_steps=6))
                            fifth_pitch = pitches[2] - 24 if len(pitches) > 2 else root_pitch + 7
                            tnote("bass", MidiNote(step=base_step + 8, pitch=fifth_pitch, velocity=80, duration_steps=4))
                            tnote("bass", MidiNote(step=base_step + 12, pitch=root_pitch + 12, velocity=75, duration_steps=3))
                
            # 4. ドラムトラック (Channel 9, Kick=36, Snare=38, Hihat=42)
            if "drums" in instruments:
                if style in ("bossanova", "bossa"):
                    # 1. キック
                    tnote("drums", MidiNote(step=base_step + 0, pitch=36, velocity=85, duration_steps=2))
                    tnote("drums", MidiNote(step=base_step + 6, pitch=36, velocity=60, duration_steps=1))
                    tnote("drums", MidiNote(step=base_step + 8, pitch=36, velocity=85, duration_steps=2))
                    tnote("drums", MidiNote(step=base_step + 14, pitch=36, velocity=60, duration_steps=1))

                    # 2. ハイハット (8分音符で刻む)
                    for h in range(8):
                        step_val = h * 2
                        vel = 65 if h % 2 == 0 else 45
                        tnote("drums", MidiNote(step=base_step + step_val, pitch=42, velocity=vel, duration_steps=1))

                    # 3. リムショット (ボサノバクラーベ)
                    rim_pitch = 37
                    if b % 2 == 0:
                        for r_step in [0, 3, 6, 10, 13]:
                            tnote("drums", MidiNote(step=base_step + r_step, pitch=rim_pitch, velocity=75, duration_steps=1))
                    else:
                        for r_step in [2, 6, 8, 12, 14]:
                            tnote("drums", MidiNote(step=base_step + r_step, pitch=rim_pitch, velocity=75, duration_steps=1))
                elif style in ("jazz", "lofi"):
                    # ジャズ・スウィング・ドラムパターン
                    # 1. ライドシンバル (チー・チッキ・チー・チッキ)
                    cymbal_pitch = 51
                    for beat in [0, 4, 8, 12]:
                        tnote("drums", MidiNote(step=base_step + beat, pitch=cymbal_pitch, velocity=70, duration_steps=2))
                    for bounce in [3, 11]:
                         tnote("drums", MidiNote(step=base_step + bounce, pitch=cymbal_pitch, velocity=50, duration_steps=1))
                    # 2. ハイハットペダル (2拍、4拍)
                    tnote("drums", MidiNote(step=base_step + 4, pitch=44, velocity=65, duration_steps=1))
                    tnote("drums", MidiNote(step=base_step + 12, pitch=44, velocity=65, duration_steps=1))
                    # 3. キック (フェザリング)
                    for k in [0, 8]:
                        tnote("drums", MidiNote(step=base_step + k, pitch=36, velocity=45, duration_steps=1))
                    # 4. スネア (コンピング)
                    if b % 2 == 0:
                         tnote("drums", MidiNote(step=base_step + 10, pitch=38, velocity=40, duration_steps=1))
                    else:
                         tnote("drums", MidiNote(step=base_step + 14, pitch=38, velocity=45, duration_steps=1))
                elif style in ("edm", "trance", "synthwave"):
                    # EDM / トランス / シンセウェーブ 4つ打ち疾走ビート
                    for k in [0, 4, 8, 12]:
                        tnote("drums", MidiNote(step=base_step + k, pitch=36, velocity=100, duration_steps=2))
                    tnote("drums", MidiNote(step=base_step + 4, pitch=38, velocity=95, duration_steps=2))
                    tnote("drums", MidiNote(step=base_step + 12, pitch=38, velocity=95, duration_steps=2))
                    for h in [2, 6, 10, 14]:
                        tnote("drums", MidiNote(step=base_step + h, pitch=42, velocity=80, duration_steps=1))
                    if (b + 1) % drum_fill_frequency == 0:
                        for h in [8, 10, 12, 13, 14, 15]:
                            tnote("drums", MidiNote(step=base_step + h, pitch=38, velocity=90, duration_steps=1))
                elif style == "reggae":
                    # レゲエ特有のワンドロップ（One Drop）ビート
                    # 1拍目（ステップ0）は無音、3拍目（ステップ8）にキックとスネアを同時打鍵！
                    tnote("drums", MidiNote(step=base_step + 8, pitch=36, velocity=90, duration_steps=2)) # キック
                    tnote("drums", MidiNote(step=base_step + 8, pitch=38, velocity=90, duration_steps=2)) # スネア/リム
                    
                    # 4拍目の裏（ステップ14）に軽いキックを入れるバリエーション
                    if b % 2 == 1:
                        tnote("drums", MidiNote(step=base_step + 14, pitch=36, velocity=75, duration_steps=1))
                        
                    # 裏打ちハイハット（ツク、ツク）
                    for h in [2, 6, 10, 14]:
                        tnote("drums", MidiNote(step=base_step + h, pitch=42, velocity=80, duration_steps=1))
                elif style in ("chillhop", "lofi"):
                    # チルホップ/ローファイのドラムバリエーション
                    if chillhop_pattern == 0:
                        # 標準Boom Bap
                        tnote("drums", MidiNote(step=base_step + 0, pitch=36, velocity=90, duration_steps=2))
                        if b % 2 == 0:
                            tnote("drums", MidiNote(step=base_step + 10, pitch=36, velocity=85, duration_steps=1))
                        else:
                            tnote("drums", MidiNote(step=base_step + 8, pitch=36, velocity=85, duration_steps=2))
                            tnote("drums", MidiNote(step=base_step + 11, pitch=36, velocity=80, duration_steps=1))
                        tnote("drums", MidiNote(step=base_step + 4, pitch=38, velocity=85, duration_steps=2))
                        tnote("drums", MidiNote(step=base_step + 12, pitch=38, velocity=85, duration_steps=2))
                    elif chillhop_pattern == 1:
                        # シンコペーション・ビート
                        tnote("drums", MidiNote(step=base_step + 0, pitch=36, velocity=90, duration_steps=2))
                        tnote("drums", MidiNote(step=base_step + 6, pitch=36, velocity=80, duration_steps=1))
                        tnote("drums", MidiNote(step=base_step + 12, pitch=36, velocity=85, duration_steps=1))
                        tnote("drums", MidiNote(step=base_step + 4, pitch=38, velocity=85, duration_steps=2))
                        tnote("drums", MidiNote(step=base_step + 14, pitch=38, velocity=85, duration_steps=2))
                    else:
                        # レイドバック（ダブ・スロウ風味）
                        tnote("drums", MidiNote(step=base_step + 0, pitch=36, velocity=90, duration_steps=2))
                        tnote("drums", MidiNote(step=base_step + 8, pitch=36, velocity=85, duration_steps=2))
                        tnote("drums", MidiNote(step=base_step + 12, pitch=38, velocity=90, duration_steps=2))
                    
                    # ハイハットペダル / クローズドハット
                    for h in range(8):
                        step_val = h * 2
                        vel = 75 if h % 2 == 0 else 45
                        tnote("drums", MidiNote(step=base_step + step_val, pitch=42, velocity=vel, duration_steps=1))
                elif style == "triphop":
                    # Trip Hop 重厚・スロウビート
                    tnote("drums", MidiNote(step=base_step + 0, pitch=36, velocity=95, duration_steps=2))
                    if b % 2 == 1:
                        tnote("drums", MidiNote(step=base_step + 10, pitch=36, velocity=85, duration_steps=2))
                    tnote("drums", MidiNote(step=base_step + 4, pitch=38, velocity=95, duration_steps=2))
                    tnote("drums", MidiNote(step=base_step + 12, pitch=38, velocity=95, duration_steps=2))
                    for h in [0, 4, 8, 12]:
                        tnote("drums", MidiNote(step=base_step + h, pitch=42, velocity=60, duration_steps=1))
                elif intensity == "low" and sec["name"] in ("intro", "outro"):
                    # イントロやアウトロはドラムなし、または非常に薄いハイハットのみ
                    if b % 2 == 0:
                        tnote("drums", MidiNote(step=base_step + 0, pitch=42, velocity=50, duration_steps=1))
                else:
                    # 通常ドラムパターン：drum_fill_frequency小節の後半でドラムフィルを入れる
                    if (b + 1) % drum_fill_frequency == 0:
                        # キック
                        tnote("drums", MidiNote(step=base_step + 0, pitch=36, velocity=95, duration_steps=2))
                        # スネア (2拍)
                        tnote("drums", MidiNote(step=base_step + 4, pitch=38, velocity=90, duration_steps=2))
                        for h in [0, 2, 4, 6]:
                            tnote("drums", MidiNote(step=base_step + h, pitch=42, velocity=70, duration_steps=1))
                        # ドラムフィル（スネア・ロータム連打）
                        tnote("drums", MidiNote(step=base_step + 8, pitch=38, velocity=80, duration_steps=1))
                        tnote("drums", MidiNote(step=base_step + 10, pitch=38, velocity=85, duration_steps=1))
                        tnote("drums", MidiNote(step=base_step + 12, pitch=43, velocity=85, duration_steps=1))
                        tnote("drums", MidiNote(step=base_step + 13, pitch=43, velocity=90, duration_steps=1))
                        tnote("drums", MidiNote(step=base_step + 14, pitch=38, velocity=90, duration_steps=1))
                        tnote("drums", MidiNote(step=base_step + 15, pitch=38, velocity=95, duration_steps=1))
                    else:
                        # 通常の小節パターン
                        # キック (1拍、3拍の頭と裏)
                        tnote("drums", MidiNote(step=base_step + 0, pitch=36, velocity=90, duration_steps=2))
                        if intensity == "high":
                            tnote("drums", MidiNote(step=base_step + 8, pitch=36, velocity=90, duration_steps=2))
                            if b % 2 == 1:
                                tnote("drums", MidiNote(step=base_step + 10, pitch=36, velocity=75, duration_steps=1))
                                
                        # スネア (2拍、4拍)
                        tnote("drums", MidiNote(step=base_step + 4, pitch=38, velocity=85, duration_steps=2))
                        tnote("drums", MidiNote(step=base_step + 12, pitch=38, velocity=85, duration_steps=2))
                        
                        # ハイハット
                        # density（密度）パラメータで細かさを物理決定
                        if density < 0.3:
                            hihat_density = 2
                        elif density > 0.7:
                            hihat_density = 8
                        else:
                            hihat_density = 4
                            
                        step_jump = 16 // hihat_density
                        for h in range(hihat_density):
                            vel = 70 if h % 2 == 0 else 55
                            tnote("drums", MidiNote(step=base_step + (h * step_jump), pitch=42, velocity=vel, duration_steps=1))

            # 5. メロディ（主旋律）トラックの生成
            if sec["name"] in ("verse", "bridge", "chorus"):
                # カスタムメロディの定義があるかチェック
                custom_melody = plan.get("custom_melody")
                sec_melody = None
                if custom_melody and isinstance(custom_melody, dict):
                    sec_name_key = "chorus" if sec["name"] == "chorus" else "verse"
                    sec_melody = custom_melody.get(sec_name_key)
                
                if sec_melody:
                    # 小節インデックスに基づいて、定義済みのメロディパターンを適用する
                    bar_melody_notes = sec_melody[b % len(sec_melody)]
                    for step_offset, base_pitch in bar_melody_notes:
                        # 基準キーでのMIDIノート番号にkey_offsetを足して移調する
                        melody_pitch = base_pitch + key_offset
                        tnote("melody", MidiNote(step=base_step + step_offset, pitch=melody_pitch, velocity=95, duration_steps=2))
                else:
                    # デフォルトのメロディ生成（オクターブ折り返しで音域 [60, 84] 内に旋律を保つ）
                    def fit_pitch_in_range(pitch: int, min_p: int = 60, max_p: int = 84) -> int:
                        """オクターブを加減算して音高を [min_p, max_p] に収め、音程差を破壊しない"""
                        while pitch > max_p:
                            pitch -= 12
                        while pitch < min_p:
                            pitch += 12
                        return pitch

                    is_chorus = sec["name"] == "chorus"
                    if style in ("bossanova", "bossa", "jazz", "lofi"):
                        # ジャズ/ボサノバ風：浮遊感のあるメロディ
                        melody_steps = [0, 2, 4, 6, 8, 10, 12, 14] if intensity == "high" else [0, 3, 6, 8, 10, 14]
                        for step_offset in melody_steps:
                            if random.random() < 0.65:
                                p_base = random.choice(pitches)
                                raw_pitch = p_base + 12
                                if random.random() < 0.35 and len(pitches) > 2:
                                    raw_pitch = pitches[0] + 14  # 9thテンション音
                                melody_pitch = fit_pitch_in_range(raw_pitch, 60, 84)
                                tnote("melody", MidiNote(step=base_step + step_offset, pitch=melody_pitch, velocity=90, duration_steps=2))
                    else:
                        # ポップス/ロック/その他：動的フレーズ＆コード音によるメロディ生成
                        melody_steps = [0, 2, 4, 6, 8, 10, 12, 14] if (intensity == "high" or is_chorus) else [0, 4, 8, 12]
                        prev_pitch = None
                        for step_offset in melody_steps:
                            if random.random() < 0.75:
                                if prev_pitch is not None and random.random() < 0.4:
                                    # 同一音の重複またはモチーフ維持
                                    raw_pitch = prev_pitch
                                else:
                                    p_base = random.choice(pitches)
                                    octave_shift = 12 if not is_chorus else (12 if random.random() < 0.4 else 24)
                                    raw_pitch = p_base + octave_shift
                                melody_pitch = fit_pitch_in_range(raw_pitch, 62 if is_chorus else 60, 84)
                                prev_pitch = melody_pitch
                                tnote("melody", MidiNote(step=base_step + step_offset, pitch=melody_pitch, velocity=95, duration_steps=2))

    # ─── トラックオブジェクトの構築（セクション種別ごとに1トラック）─────────────────
    # 楽器ごとのチャンネル・楽器名を決定するヘルパー情報
    def get_inst_info(inst_key: str) -> tuple[str, str, int]:
        """(inst_name, track_base_name, channel) を返す"""
        if inst_key == "piano":
            if style in ("edm", "trance", "synthwave", "techno", "house"):
                return "synth_lead", "Synth Lead", 0
            elif style in ("rock", "metal", "grunge", "nirvana_lofi"):
                return "distortion_guitar", "Dist. Guitar", 0
            else:
                return "acoustic_piano", "Acoustic Piano", 0
        elif inst_key == "guitar":
            if style in ("edm", "trance", "synthwave", "techno", "house", "triphop", "ambient", "classical"):
                return "synth_pad", "Synth Pad", 1
            elif style in ("rock", "metal", "grunge", "nirvana_lofi"):
                return "overdriven_guitar", "OD Guitar", 1
            else:
                return "acoustic_guitar", "Acoustic Guitar", 1
        elif inst_key == "bass":
            if style in ("edm", "trance", "synthwave", "techno", "house", "triphop"):
                return "synth_bass", "Synth Bass", 2
            elif style in ("rock", "metal", "grunge", "nirvana_lofi"):
                return "electric_bass_pick", "Pick Bass", 2
            else:
                return "electric_bass", "Electric Bass", 2
        elif inst_key == "drums":
            return "synth_drum_kit", "Drums", 9
        else:  # melody
            if style in ("edm", "trance", "synthwave", "techno", "house"):
                return "synth_lead", "Melody Lead", 3
            elif style in ("jazz", "lofi", "bossanova", "bossa"):
                inst = "vibraphone" if random.random() < 0.5 else "electric_piano"
                return inst, "Melody Vib", 3
            elif style in ("rock", "metal", "grunge", "nirvana_lofi"):
                inst = "distortion_guitar" if random.random() < 0.5 else "electric_guitar_clean"
                return inst, "Melody Guitar", 3
            else:
                inst = "acoustic_guitar" if "piano" in instruments else "acoustic_piano"
                return inst, "Melody", 3

    # セクション種別の表示順を固定（intro→verse→bridge→chorus→outro）
    SEC_ORDER = ["intro", "verse", "bridge", "chorus", "outro"]

    tracks = []
    for inst_key in ["piano", "guitar", "bass", "drums", "melody"]:
        # 楽器が無効なら skip
        if inst_key != "melody" and inst_key != "drums" and inst_key not in instruments:
            continue
        if inst_key == "drums" and "drums" not in instruments:
            continue
        if inst_key == "melody" and not any(track_notes["melody"].values()):
            continue

        inst_name, base_name, channel = get_inst_info(inst_key)
        sec_buckets = track_notes[inst_key]

        # セクション種別を出現順（曲の構成順）でソート
        present_secs = list(sec_buckets.keys())
        ordered_secs = [s for s in SEC_ORDER if s in present_secs]
        ordered_secs += [s for s in present_secs if s not in SEC_ORDER]  # 未知のセクション名は後ろへ

        for sec_type in ordered_secs:
            notes = sec_buckets[sec_type]
            if not notes:
                continue
            label = sec_type.capitalize()  # "Verse", "Chorus", etc.
            tracks.append(MidiTrack(
                track_id=f"track_{inst_key}_{sec_type}",
                track_name=f"{base_name} - {label}",
                instrument=inst_name,
                channel=channel,
                notes=notes
            ))
        
    print("\n" + "="*60)
    print("[ABMM COMPOSITION LOG - ACTUAL GENERATED CHORDS]")
    print(f"  Description:       '{plan.get('description', '')}'")
    print(f"  UI Genre / Style:  '{plan.get('genre', 'auto')}' -> Final Style: '{style}'")
    print(f"  Tempo / Key Mode:  {tempo_bpm} BPM / {key_mode}")
    print("  Structure & Chords (with applied key offset):")
    for sec in sections:
        sec_chords = sec["chords"]
        offset = sec.get("key_offset", 0)
        offset_str = f" (key offset: {offset:+d})" if offset != 0 else ""
        print(f"    - Section '{sec['name']}': {sec_chords}{offset_str}")
        
    print("\n  Generated MIDI Tracks & Notes (Phase 1 Output):")
    for track in tracks:
        print(f"    - Track '{track.track_name}' (Instrument: {track.instrument}, Channel: {track.channel}):")
        print(f"        Total Notes: {len(track.notes)}")
        # 最初の12ノートをプレビュー出力
        preview_notes = track.notes[:12]
        notes_str = ", ".join([f"(step={n.step}, pitch={n.pitch}, vel={n.velocity}, dur={n.duration_steps})" for n in preview_notes])
        if len(track.notes) > 12:
            notes_str += ", ..."
        print(f"        Notes Preview: {notes_str}")
    print("="*60 + "\n")
        
    # energy & brightness 物理パラメータの一括反映
    for track in tracks:
        # 1. 音量（Energy）のベロシティ反映（ドラム含む全トラック）
        for note in track.notes:
            note.velocity = max(20, min(127, int(note.velocity * energy_factor)))
            
        # 2. 明るさ（Brightness）のメロディオクターブピッチ反映
        if track.track_id.startswith("track_melody"):
            brightness_shift = 0
            if brightness < 0.35:
                brightness_shift = -12
            elif brightness > 0.75:
                brightness_shift = 12
                
            if brightness_shift != 0:
                for note in track.notes:
                    note.pitch = max(0, min(127, note.pitch + brightness_shift))
        
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

# コードとして誤認識されやすい、スタイル名・ジャンル名・一般的な単語のノイズリスト。
# これらは chord_pattern の正規表現にはマッチしてしまう（例: "pop" の p は無視されるが
# 単体の "A" や "Am"（morning の略）等はコードと見分けがつかない）ため、
# DSL やタブ抽出の入力から明示的に除外する。
_CHORD_NOISE_WORDS = {
    "pop", "jazz", "rock", "ambient", "lofi", "edm", "trance", "chillhop",
    "triphop", "classical", "hiphop", "hip-hop", "folk", "funk", "blues",
    "reggae", "house", "techno", "major", "minor", "auto",
}
# 注意: "A" や "Am" は実在のコード表記（A / Aマイナー）として正当なため、
# ノイズ扱いにはしない。英文の冒頭に出る "A"（冠詞）は行単位の閾値判定
# （chord_count >= 2 かつ比率 0.6 以上）である程度弾かれる。

_CHORD_TOKEN_PATTERN = re.compile(
    r'([A-G][#b]?(?:maj7|maj9|maj|min7|min9|m7b5|m7|m9|m|dim7|dim|aug|sus4|sus2|sus|7sus4|7sus|7|9|11|13|add9)?(?:\/[A-G][#b]?)?)'
)

def _is_valid_chord_token(token: str) -> bool:
    """トークンが実在のコード表記らしいかを判定する（スタイル名やただの単語を除外）"""
    if not token:
        return False
    if token.lower() in _CHORD_NOISE_WORDS:
        return False
    return bool(_CHORD_TOKEN_PATTERN.fullmatch(token))

def extract_chords_from_raw_tab(text: str) -> list[str]:
    """生のコード譜テキスト（歌詞付きなど）からコード進行記号のみを抽出する"""
    # ChordPro形式（[C]word などの連結）に対応するため、カッコ類をスペースに置換して単語を分離する
    text = text.replace('[', ' ').replace(']', ' ').replace('{', ' ').replace('}', ' ')
    found_chords = []
    lines = text.split('\n')
    for line in lines:
        tokens = line.split()
        if not tokens:
            continue
            
        chord_count = 0
        line_chords = []
        for token in tokens:
            clean_token = token.strip("()[]{}|:,.-")
            if _is_valid_chord_token(clean_token):
                chord_count += 1
                line_chords.append(clean_token)
                
        # トークンの大半がコード、あるいは特定のセクション指示行の場合にコード行とみなす
        # (通常の文章にコードらしき単語が1〜2個混ざる誤検出を防ぐため閾値をやや厳しくする)
        if chord_count >= 2 and chord_count / len(tokens) >= 0.3:
            found_chords.extend(line_chords)
            
    return found_chords

def parse_dsl_description(description: str) -> Optional[Dict[str, Any]]:
    """
    ユーザーの自然言語指示の中に DSL 形式 [Am7 -> D7 -> Gmaj7 -> Cmaj7 : 4 bars : style=jazz] があるか確認し、
    パースして辞書を返す。なければ Raw Tab からのコード抽出を試みる。
    """
    match = re.search(r'\[([^\]]+)\]', description)
    if match:
        dsl_content = match.group(1).strip()
        # セクションヘッダー（例: [Intro], [Verse], [サビ] など）はDSLとしては無視してRaw Tab処理に回す
        header_words = {"intro", "verse", "chorus", "bridge", "outro", "solo", "interlude", "aメロ", "bメロ", "サビ", "イントロ", "アウトロ"}
        is_header = any(hw in dsl_content.lower() for hw in header_words)
        
        if not is_header:
            parts = [p.strip() for p in dsl_content.split(':')]
            
            # 進行の抽出
            chord_part = parts[0]
            raw_tokens = [c.strip() for c in re.split(r'->| |,', chord_part) if c.strip()]
            # "[pop]" や "[lofi]" のようなスタイル指定・非コード文字列を
            # コード進行として誤採用しないよう、実在するコード表記のみを残す。
            # 有効なコードが2つ未満しか無ければ、DSLとしては扱わずフォールスルーする。
            chords = [c for c in raw_tokens if _is_valid_chord_token(c)]
            if len(chords) >= 2:
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
                    elif part_lower in ("lofi", "jazz", "pop", "ambient", "rock", "edm", "trance", "chillhop", "triphop"):
                        result["style"] = part_lower
                        
                return result

    # DSL形式がない場合、入力テキストから直接コード進行の自動抽出を試みる (Raw Tab対応)
    chords = extract_chords_from_raw_tab(description)
    if len(chords) >= 4:
        return {
            "custom_chords": chords
        }
        
    return None

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
    max_retries: int = 2,
    genre: str = "auto",
    chord_progression: str = "auto"
) -> MidiComposition:
    """
    Ollama経由でLLMに高次のコード構成案を生成させ、それをPython側で展開して完全なMidiCompositionを構築する。
    """
    # 1. DSL形式の優先判定（DSLが記述されている場合は即座にバイパス処理）
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
            "custom_bars": dsl_plan.get("custom_bars"),
            "genre": genre,
            "chord_progression": chord_progression,
            "description": description
        }
        return expand_chord_plan_to_midi(plan, duration_minutes)

    # 2. ローカル辞書およびオンラインスクレイピングによるコード進行の事前検出
    detected_chords = None
    detected_style = None
    # ※ detected_melody は廃止 — DBのハードコードメロディは使わず、常にコード音から動的生成する

    desc_lower = description.lower()
    is_bossanova = any(kw in desc_lower for kw in ["bossa", "bossanova", "ボサノバ", "ボサノヴァ"])

    song_query = extract_song_query(description)
    local_match = check_local_song_database(song_query) if song_query else None

    # DBマッチからはスタイルのヒントのみ取得（コード進行は後でオンラインが上書き可能）
    if local_match:
        print(f"[Database Match] Famous song/style matched: {local_match}")
        detected_chords = local_match["custom_chords"]   # DB chords as fallback
        detected_style = "bossanova" if is_bossanova else local_match.get("style")

    # オンライン検索は曲名がある場合は常に実行（DBマッチがあっても上書き優先）
    if song_query:
        is_song_request = (
            "by" in desc_lower or
            "の" in description or
            "song" in desc_lower or
            "曲" in description or
            "テーマ" in description or
            "cover" in desc_lower or
            "を" in description and "風" in description or
            any(q in description for q in ['"', "'", "「", "」", "『", "』"]) or
            len([w for w in song_query.split() if w[0].isupper() and w.lower() not in {"a", "an", "the", "arrange", "play", "compose", "make", "create", "cover"}]) >= 2
        )
        generic_words = {"sad", "happy", "lofi", "ambient", "jazz", "rock", "pop", "edm", "trance", "chill", "dark", "fast", "slow", "piano", "guitar", "beat", "drums", "bass", "bgm", "music", "composition"}
        query_words = set(song_query.lower().split())
        if query_words.issubset(generic_words) or not song_query.strip():
            is_song_request = False

        if is_song_request:
            online_chords = search_chords_online(song_query)
            if online_chords:
                print(f"[Online Search Match] Chords found online for '{song_query}': {online_chords[:12]}")
                # 重複除去しつつ順序を保持し、最大8コードに圧縮する
                seen = []
                for c in online_chords:
                    if c not in seen:
                        seen.append(c)
                    if len(seen) >= 8:
                        break
                unique_chords = seen
                # 前半をverse、後半をchorusに（最低2コード保証）
                half = max(len(unique_chords) // 2, 2)
                verse_chords = unique_chords[:half]
                chorus_chords = unique_chords[half:] if len(unique_chords) > half else unique_chords
                # オンラインコードはDBコードより優先して上書き
                detected_chords = {
                    "verse": verse_chords,
                    "chorus": chorus_chords
                }
                if not detected_style:
                    detected_style = "bossanova" if is_bossanova else "pop"

    if is_bossanova and not detected_style:
        detected_style = "bossanova"
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
            plan["genre"] = genre
            plan["chord_progression"] = chord_progression
            plan["description"] = description
            plan["brightness"] = brightness
            plan["energy"] = energy
            plan["density"] = density
            
            if instruments and isinstance(instruments, dict):
                active_insts = [inst for inst, val in instruments.items() if val > 0.0]
                if active_insts:
                    plan["instruments"] = active_insts
            
            # 事前に検出されたコード進行をマージ（メロディのハードコードは廃止）
            if detected_chords:
                plan["custom_chords"] = detected_chords
                if detected_style and not plan.get("style"):
                    plan["style"] = detected_style
            # custom_melody は設定しない → 常にコード音から動的にメロディを生成させる
            
            # 展開処理の実行
            composition = expand_chord_plan_to_midi(plan, duration_minutes)
            return composition

        except Exception as e:
            last_error = str(e)
            print(f"[Ollama Plan Generation] Attempt {attempt + 1} failed: {last_error}")

    # フォールバック
    print("[Ollama Plan Generation] All attempts failed. Falling back to default Chord Plan.")
    active_insts = ["piano", "guitar", "bass", "drums"]
    if instruments and isinstance(instruments, dict):
        active_insts = [inst for inst, val in instruments.items() if val > 0.0]
        if not active_insts:
            active_insts = ["piano"]

    default_plan = {
        "tempo_bpm": tempo_bpm,
        "key_mode": key_mode,
        "style": detected_style or "lofi",
        "instruments": active_insts,
        "genre": genre,
        "chord_progression": chord_progression,
        "description": description,
        "brightness": brightness,
        "energy": energy,
        "density": density
    }
    if detected_chords:
        default_plan["custom_chords"] = detected_chords
    # custom_melody は設定しない → 常にコード音から動的にメロディを生成させる
    return expand_chord_plan_to_midi(default_plan, duration_minutes)
