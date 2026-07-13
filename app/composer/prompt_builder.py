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
  "instruments": ["piano", "guitar", "bass", "drums"],
  "melody_style": "steady" | "expressive" | "complex",
  "rhythm_variation": "none" | "slight" | "heavy"
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
    if style.lower() == "lofi":
        style_mapped = "jazz"
        
    if custom_chords_tuple:
        verse_chords, chorus_chords = custom_chords_tuple
    else:
        # マンネリ打破のための動的・ランダムなコード進行生成アルゴリズム (確率 40%)
        # これにより、固定パターン以外の無数の音楽的に正しい進行が生まれ続けます
        if random.random() < 0.40:
            if key_mode == "minor":
                # マイナーキーの機能的和声進行 (i -> bVI -> iv/bVII -> v/V)
                v_start = random.choice(["Am", "F"])
                v2 = random.choice(["F", "Dm", "G"])
                v3 = random.choice(["G", "C", "Em"])
                v4 = random.choice(["Em", "Am"])
                verse_chords = [v_start, v2, v3, v4]
                
                c_start = random.choice(["F", "Dm"])
                c2 = random.choice(["G", "Em"])
                c3 = random.choice(["Am", "F"])
                c4 = random.choice(["G", "Am"])
                chorus_chords = [c_start, c2, c3, c4]
            else:
                # メジャーキーの機能的和声進行 (I -> IV -> V/vii -> vi/iii)
                v_start = random.choice(["C", "Am", "F"])
                v2 = random.choice(["F", "Dm", "G"])
                v3 = random.choice(["G", "Em", "C"])
                v4 = random.choice(["Am", "F", "G"])
                verse_chords = [v_start, v2, v3, v4]
                
                c_start = random.choice(["F", "Dm", "C"])
                c2 = random.choice(["G", "Em"])
                c3 = random.choice(["Am", "F"])
                c4 = random.choice(["G", "C"])
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
    if genre != "auto":
        style = genre.lower()
        if style == "lofi":
            style = "jazz"
            
    # トランス/チルホップ/トリップホップのテンポを強制設定
    if style in ("trance", "dream_house"):
        tempo_bpm = 138
    elif style == "chillhop":
        tempo_bpm = 85
    elif style == "triphop":
        tempo_bpm = 74
            
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
        # コード進行のオーバーライド
        chord_prog = plan.get("chord_progression", "auto")
        custom_tuple = None
        if chord_prog != "auto" and chord_prog in PROGRESSION_MAP:
            custom_tuple = PROGRESSION_MAP[chord_prog]
            
        # 曲のセクション構成を動的に生成
        sections = get_song_structure(total_bars_needed, key_mode, style, custom_chords_tuple=custom_tuple)

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
                    if piano_rhythm_pattern == "ballad_arpeggio":
                        # アルペジオ分散和音
                        for i, p in enumerate(pitches):
                            step_offset = i * 4
                            track_notes["piano"].append(MidiNote(step=base_step + step_offset, pitch=p, velocity=60, duration_steps=4))
                    else:
                        duration = random.choice([12, 14, 15])
                        for p in pitches:
                            track_notes["piano"].append(MidiNote(step=base_step + 0, pitch=p, velocity=60, duration_steps=duration))
                else:
                    # サビ（高強度）のバッキングパターン分岐
                    if piano_rhythm_pattern == "syncopated":
                        offsets = [0, 3, 8, 11] if b % 2 == 0 else [0, 3, 6, 12]
                        for step_offset in offsets:
                            for p in pitches:
                                track_notes["piano"].append(MidiNote(step=base_step + step_offset, pitch=p, velocity=75, duration_steps=3))
                    elif piano_rhythm_pattern == "offbeat":
                        # オフビートで弾むパターン
                        for step_offset in [2, 6, 10, 14]:
                            for p in pitches:
                                track_notes["piano"].append(MidiNote(step=base_step + step_offset, pitch=p, velocity=72, duration_steps=2))
                    elif piano_rhythm_pattern == "ballad_arpeggio":
                        # 4つ刻みのバッキング
                        for step_offset in [0, 4, 8, 12]:
                            for p in pitches:
                                track_notes["piano"].append(MidiNote(step=base_step + step_offset, pitch=p, velocity=70, duration_steps=3))
                    else:
                        # "standard" パターン
                        if (b + 1) % 4 == 0:
                            for p in pitches:
                                track_notes["piano"].append(MidiNote(step=base_step + 0, pitch=p, velocity=75, duration_steps=4))
                                track_notes["piano"].append(MidiNote(step=base_step + 6, pitch=p, velocity=75, duration_steps=4))
                                track_notes["piano"].append(MidiNote(step=base_step + 12, pitch=p, velocity=70, duration_steps=3))
                        elif b % 2 == 1:
                            for p in pitches:
                                track_notes["piano"].append(MidiNote(step=base_step + 0, pitch=p, velocity=75, duration_steps=6))
                                track_notes["piano"].append(MidiNote(step=base_step + 6, pitch=p, velocity=70, duration_steps=4))
                                track_notes["piano"].append(MidiNote(step=base_step + 12, pitch=p, velocity=65, duration_steps=3))
                        else:
                            for p in pitches:
                                track_notes["piano"].append(MidiNote(step=base_step + 0, pitch=p, velocity=75, duration_steps=6))
                                track_notes["piano"].append(MidiNote(step=base_step + 8, pitch=p, velocity=70, duration_steps=6))
                    
            # 2. ギター（アルペジオ）トラック
            if "guitar" in instruments:
                if intensity == "low":
                    offsets = [0, 8] if b % 2 == 0 else [0, 4, 8, 12]
                    for i, step_offset in enumerate(offsets):
                        pitch_val = pitches[i % len(pitches)] + 12
                        track_notes["guitar"].append(MidiNote(step=base_step + step_offset, pitch=pitch_val, velocity=55, duration_steps=4))
                else:
                    if guitar_arpeggio_pattern == "broken_chord":
                        # 低音と高音の交互アルペジオ
                        offsets = [0, 2, 4, 6, 8, 10, 12, 14]
                        for i, step_offset in enumerate(offsets):
                            if i % 2 == 0:
                                p_val = pitches[0] + 12
                            else:
                                p_val = pitches[i % len(pitches)] + 12
                            track_notes["guitar"].append(MidiNote(step=base_step + step_offset, pitch=p_val, velocity=60, duration_steps=2))
                    elif guitar_arpeggio_pattern == "syncopated_strum":
                        # リズミカルなカッティング風
                        for step_offset in [0, 3, 6, 8, 11, 14]:
                            p_val = pitches[step_offset % len(pitches)] + 12
                            track_notes["guitar"].append(MidiNote(step=base_step + step_offset, pitch=p_val, velocity=65, duration_steps=2))
                    elif guitar_arpeggio_pattern == "walking_arp":
                        # 上昇するアルペジオ
                        for i in range(8):
                            step_offset = i * 2
                            p_val = pitches[i % len(pitches)] + 12
                            track_notes["guitar"].append(MidiNote(step=base_step + step_offset, pitch=p_val, velocity=58, duration_steps=2))
                    else:
                        # "classic_arp" パターン
                        if b % 2 == 1:
                            extended_pitches = [pitches[0], pitches[2], pitches[1], pitches[0]]
                        else:
                            extended_pitches = [pitches[0], pitches[1], pitches[2], pitches[1]]
                        step_offsets = [0, 4, 8, 12]
                        for i, (step_offset, p) in enumerate(zip(step_offsets, extended_pitches)):
                            dur = 3 if i < 3 else (4 if (b + 1) % 4 == 0 else 3)
                            track_notes["guitar"].append(MidiNote(step=base_step + step_offset, pitch=p + 12, velocity=65, duration_steps=dur))
                    
            # 3. ベーストラック
            if "bass" in instruments:
                root_pitch = pitches[0] - 24  # 2オクターブ低く
                if style == "trance":
                    # トランス用ローリングベースライン (16分音符のギャロップ)
                    for p_idx in range(4):
                        beat_offset = p_idx * 4
                        track_notes["bass"].append(MidiNote(step=base_step + beat_offset + 0, pitch=root_pitch, velocity=85, duration_steps=1))
                        track_notes["bass"].append(MidiNote(step=base_step + beat_offset + 2, pitch=root_pitch, velocity=80, duration_steps=1))
                        track_notes["bass"].append(MidiNote(step=base_step + beat_offset + 3, pitch=root_pitch, velocity=85, duration_steps=1))
                elif intensity == "low":
                    if b % 2 == 1 and len(pitches) > 2:
                        fifth_pitch = pitches[2] - 24
                        track_notes["bass"].append(MidiNote(step=base_step + 0, pitch=root_pitch, velocity=75, duration_steps=10))
                        track_notes["bass"].append(MidiNote(step=base_step + 12, pitch=fifth_pitch, velocity=65, duration_steps=3))
                    else:
                        track_notes["bass"].append(MidiNote(step=base_step + 0, pitch=root_pitch, velocity=75, duration_steps=14))
                else:
                    # サビ（高強度）のベースパターン分岐
                    if bass_rhythm_pattern == "walking_bass":
                        fifth_pitch = pitches[2] - 24 if len(pitches) > 2 else root_pitch + 7
                        third_pitch = pitches[1] - 24 if len(pitches) > 1 else root_pitch + 4
                        steps_and_pitches = [
                            (0, root_pitch),
                            (4, third_pitch),
                            (8, fifth_pitch),
                            (12, root_pitch + 12 if random.random() < 0.5 else root_pitch)
                        ]
                        for step_val, p_val in steps_and_pitches:
                            track_notes["bass"].append(MidiNote(step=base_step + step_val, pitch=p_val, velocity=80, duration_steps=3))
                    elif bass_rhythm_pattern == "syncopated_bass":
                        track_notes["bass"].append(MidiNote(step=base_step + 0, pitch=root_pitch, velocity=85, duration_steps=4))
                        track_notes["bass"].append(MidiNote(step=base_step + 6, pitch=root_pitch, velocity=80, duration_steps=4))
                        track_notes["bass"].append(MidiNote(step=base_step + 12, pitch=root_pitch, velocity=85, duration_steps=3))
                    elif bass_rhythm_pattern == "bounce_bass":
                        track_notes["bass"].append(MidiNote(step=base_step + 0, pitch=root_pitch, velocity=85, duration_steps=3))
                        track_notes["bass"].append(MidiNote(step=base_step + 4, pitch=root_pitch + 12, velocity=78, duration_steps=3))
                        track_notes["bass"].append(MidiNote(step=base_step + 8, pitch=root_pitch, velocity=85, duration_steps=3))
                        track_notes["bass"].append(MidiNote(step=base_step + 12, pitch=root_pitch + 12, velocity=78, duration_steps=3))
                    else:
                        # "standard_bass"
                        next_chord_name = chords[(b + 1) % len(chords)]
                        next_pitches = get_chord_pitches(next_chord_name, key_offset)
                        next_root = next_pitches[0] - 24
                        
                        if (b + 1) % 4 == 0:
                            track_notes["bass"].append(MidiNote(step=base_step + 0, pitch=root_pitch, velocity=85, duration_steps=4))
                            track_notes["bass"].append(MidiNote(step=base_step + 6, pitch=root_pitch, velocity=80, duration_steps=4))
                            approach_pitch = next_root + 1 if root_pitch > next_root else next_root - 1
                            track_notes["bass"].append(MidiNote(step=base_step + 12, pitch=approach_pitch, velocity=85, duration_steps=3))
                        else:
                            track_notes["bass"].append(MidiNote(step=base_step + 0, pitch=root_pitch, velocity=85, duration_steps=6))
                            fifth_pitch = pitches[2] - 24 if len(pitches) > 2 else root_pitch + 7
                            track_notes["bass"].append(MidiNote(step=base_step + 8, pitch=fifth_pitch, velocity=80, duration_steps=4))
                            track_notes["bass"].append(MidiNote(step=base_step + 12, pitch=root_pitch + 12, velocity=75, duration_steps=3))
                
            # 4. ドラムトラック (Channel 9, Kick=36, Snare=38, Hihat=42)
            if "drums" in instruments:
                if style in ("edm", "trance"):
                    # EDM 4つ打ちドラムパターン
                    for k in [0, 4, 8, 12]:
                        track_notes["drums"].append(MidiNote(step=base_step + k, pitch=36, velocity=100, duration_steps=2))
                    track_notes["drums"].append(MidiNote(step=base_step + 4, pitch=38, velocity=95, duration_steps=2))
                    track_notes["drums"].append(MidiNote(step=base_step + 12, pitch=38, velocity=95, duration_steps=2))
                    for h in [2, 6, 10, 14]:
                        track_notes["drums"].append(MidiNote(step=base_step + h, pitch=42, velocity=80, duration_steps=1))
                    if (b + 1) % drum_fill_frequency == 0:
                        for h in [8, 10, 12, 13, 14, 15]:
                            track_notes["drums"].append(MidiNote(step=base_step + h, pitch=38, velocity=90, duration_steps=1))
                elif style == "chillhop":
                    # Nujabes風 Boom Bap ビート
                    track_notes["drums"].append(MidiNote(step=base_step + 0, pitch=36, velocity=90, duration_steps=2))
                    if b % 2 == 0:
                        track_notes["drums"].append(MidiNote(step=base_step + 10, pitch=36, velocity=85, duration_steps=1))
                    else:
                        track_notes["drums"].append(MidiNote(step=base_step + 8, pitch=36, velocity=85, duration_steps=2))
                        track_notes["drums"].append(MidiNote(step=base_step + 11, pitch=36, velocity=80, duration_steps=1))
                    track_notes["drums"].append(MidiNote(step=base_step + 4, pitch=38, velocity=85, duration_steps=2))
                    track_notes["drums"].append(MidiNote(step=base_step + 12, pitch=38, velocity=85, duration_steps=2))
                    for h in range(8):
                        step_val = h * 2
                        vel = 75 if h % 2 == 0 else 45
                        track_notes["drums"].append(MidiNote(step=base_step + step_val, pitch=42, velocity=vel, duration_steps=1))
                elif style == "triphop":
                    # Trip Hop 重厚・スロウビート
                    track_notes["drums"].append(MidiNote(step=base_step + 0, pitch=36, velocity=95, duration_steps=2))
                    if b % 2 == 1:
                        track_notes["drums"].append(MidiNote(step=base_step + 10, pitch=36, velocity=85, duration_steps=2))
                    track_notes["drums"].append(MidiNote(step=base_step + 4, pitch=38, velocity=95, duration_steps=2))
                    track_notes["drums"].append(MidiNote(step=base_step + 12, pitch=38, velocity=95, duration_steps=2))
                    for h in [0, 4, 8, 12]:
                        track_notes["drums"].append(MidiNote(step=base_step + h, pitch=42, velocity=60, duration_steps=1))
                elif intensity == "low" and sec["name"] in ("intro", "outro"):
                    # イントロやアウトロはドラムなし、または非常に薄いハイハットのみ
                    if b % 2 == 0:
                        track_notes["drums"].append(MidiNote(step=base_step + 0, pitch=42, velocity=50, duration_steps=1))
                else:
                    # 通常ドラムパターン：drum_fill_frequency小節の後半でドラムフィルを入れる
                    if (b + 1) % drum_fill_frequency == 0:
                        # キック
                        track_notes["drums"].append(MidiNote(step=base_step + 0, pitch=36, velocity=95, duration_steps=2))
                        # スネア (2拍)
                        track_notes["drums"].append(MidiNote(step=base_step + 4, pitch=38, velocity=90, duration_steps=2))
                        for h in [0, 2, 4, 6]:
                            track_notes["drums"].append(MidiNote(step=base_step + h, pitch=42, velocity=70, duration_steps=1))
                        # ドラムフィル（スネア・ロータム連打）
                        track_notes["drums"].append(MidiNote(step=base_step + 8, pitch=38, velocity=80, duration_steps=1))
                        track_notes["drums"].append(MidiNote(step=base_step + 10, pitch=38, velocity=85, duration_steps=1))
                        track_notes["drums"].append(MidiNote(step=base_step + 12, pitch=43, velocity=85, duration_steps=1))
                        track_notes["drums"].append(MidiNote(step=base_step + 13, pitch=43, velocity=90, duration_steps=1))
                        track_notes["drums"].append(MidiNote(step=base_step + 14, pitch=38, velocity=90, duration_steps=1))
                        track_notes["drums"].append(MidiNote(step=base_step + 15, pitch=38, velocity=95, duration_steps=1))
                    else:
                        # 通常の小節パターン
                        # キック (1拍、3拍の頭と裏)
                        track_notes["drums"].append(MidiNote(step=base_step + 0, pitch=36, velocity=90, duration_steps=2))
                        if intensity == "high":
                            track_notes["drums"].append(MidiNote(step=base_step + 8, pitch=36, velocity=90, duration_steps=2))
                            if b % 2 == 1:
                                track_notes["drums"].append(MidiNote(step=base_step + 10, pitch=36, velocity=75, duration_steps=1))
                                
                        # スネア (2拍、4拍)
                        track_notes["drums"].append(MidiNote(step=base_step + 4, pitch=38, velocity=85, duration_steps=2))
                        track_notes["drums"].append(MidiNote(step=base_step + 12, pitch=38, velocity=85, duration_steps=2))
                        
                        # ハイハット
                        hihat_density = 8 if intensity == "high" else 4
                        step_jump = 16 // hihat_density
                        for h in range(hihat_density):
                            vel = 70 if h % 2 == 0 else 55
                            track_notes["drums"].append(MidiNote(step=base_step + (h * step_jump), pitch=42, velocity=vel, duration_steps=1))

    # トラックオブジェクトの構築
    tracks = []
    if "piano" in instruments and track_notes["piano"]:
        inst_name = "synth_lead" if style == "edm" else "acoustic_piano"
        track_name = "Synth Lead" if style == "edm" else "Acoustic Piano"
        tracks.append(MidiTrack(
            track_id="track_piano",
            track_name=track_name,
            instrument=inst_name,
            channel=0,
            notes=track_notes["piano"]
        ))
        
    if "guitar" in instruments and track_notes["guitar"]:
        inst_name = "synth_pad" if style in ("edm", "trance", "triphop") else "acoustic_guitar"
        track_name = "Synth Pad" if style in ("edm", "trance", "triphop") else "Acoustic Guitar"
        tracks.append(MidiTrack(
            track_id="track_guitar",
            track_name=track_name,
            instrument=inst_name,
            channel=1,
            notes=track_notes["guitar"]
        ))
        
    if "bass" in instruments and track_notes["bass"]:
        inst_name = "synth_bass" if style in ("edm", "trance", "triphop") else "electric_bass"
        track_name = "Synth Bass" if style in ("edm", "trance", "triphop") else "Electric Bass"
        tracks.append(MidiTrack(
            track_id="track_bass",
            track_name=track_name,
            instrument=inst_name,
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

def extract_chords_from_raw_tab(text: str) -> list[str]:
    """生のコード譜テキスト（歌詞付きなど）からコード進行記号のみを抽出する"""
    # コードとして認識する一般的なパターン（7sus4, 7sus, add9, m7b5 などもサポート）
    chord_pattern = re.compile(
        r'\b([A-G][#b]?(?:maj7|maj9|maj|min7|min9|m7b5|m7|m9|m|dim7|dim|aug|sus4|sus2|sus|7sus4|7sus|7|9|11|13|add9)?(?:\/[A-G][#b]?)?)\b'
    )
    
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
            if chord_pattern.fullmatch(clean_token):
                chord_count += 1
                line_chords.append(clean_token)
                
        # トークンの大半がコード、あるいは特定のセクション指示行の場合にコード行とみなす
        if chord_count > 0 and (chord_count / len(tokens) >= 0.5 or len(line_chords) >= 2):
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
            chords = [c.strip() for c in re.split(r'->| |,', chord_part) if c.strip()]
            if chords:
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
            "custom_bars": dsl_plan.get("custom_bars"),
            "genre": genre,
            "chord_progression": chord_progression
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
            plan["genre"] = genre
            plan["chord_progression"] = chord_progression
            
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
        "genre": genre,
        "chord_progression": chord_progression
    }
    return expand_chord_plan_to_midi(default_plan, duration_minutes)
