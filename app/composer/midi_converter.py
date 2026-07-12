import io
from typing import Union
import pretty_midi
from app.composer.midi_schema import MidiComposition, MidiTrack, MidiNote, MidiSection

def steps_to_seconds(steps: int, tempo_bpm: float) -> float:
    """
    16分音符のステップ数を秒数に変換する。
    1拍 = 4ステップ。1分 (60秒) = tempo_bpm 拍。
    したがって、1ステップ = 15.0 / tempo_bpm 秒。
    """
    if tempo_bpm <= 0:
        raise ValueError("tempo_bpm は正の数値である必要があります。")
    step_duration = 15.0 / tempo_bpm
    return steps * step_duration

def seconds_to_steps(seconds: float, tempo_bpm: float) -> int:
    """
    秒数を16分音符のステップ数（最も近い整数に丸め）に変換する。
    """
    if tempo_bpm <= 0:
        raise ValueError("tempo_bpm は正の数値である必要があります。")
    step_duration = 15.0 / tempo_bpm
    return int(round(seconds / step_duration))

def json_to_midi(composition: MidiComposition) -> bytes:
    """
    MidiCompositionデータモデルを標準MIDIファイルのバイナリデータに変換する。
    """
    # PrettyMIDIインスタンスを初期テンポで初期化
    pm = pretty_midi.PrettyMIDI(initial_tempo=composition.tempo_bpm)
    
    # トラックを追加
    for track in composition.tracks:
        is_drum = (track.channel == 9)
        program = 0
        
        if not is_drum:
            try:
                # 楽器名からGMプログラム番号に変換
                program = pretty_midi.instrument_name_to_program(track.instrument)
            except (ValueError, KeyError):
                # マッチしない場合のデフォルトフォールバック
                # よく使われそうな楽器名の手動変換
                inst_lower = track.instrument.lower()
                if "piano" in inst_lower:
                    program = 0
                elif "guitar" in inst_lower:
                    program = 24
                elif "bass" in inst_lower:
                    program = 32
                elif "synth" in inst_lower:
                    program = 80
                else:
                    program = 0 # acoustic_piano

        inst = pretty_midi.Instrument(program=program, is_drum=is_drum, name=track.track_name)
        
        # 音符を整理して同時打鍵（コード）を検出する
        from collections import defaultdict
        import random
        
        step_groups = defaultdict(list)
        for note_data in track.notes:
            step_groups[note_data.step].append(note_data)
            
        is_guitar_prog = (24 <= program <= 31)
        is_piano_prog = (program <= 7)
        
        for step, group in sorted(step_groups.items()):
            # 和音時のずらし（アルペジエーター／ストラミング効果）のため、ピッチの低い順にソート
            group.sort(key=lambda n: n.pitch)
            
            for i, note_data in enumerate(group):
                start_time = steps_to_seconds(note_data.step, composition.tempo_bpm)
                end_time = steps_to_seconds(note_data.step + note_data.duration_steps, composition.tempo_bpm)
                
                # 1. 音量（Velocity）の人間らしさ：ランダムに微小変化を加える
                vel = note_data.velocity + random.randint(-6, 6)
                vel = max(1, min(127, vel))
                
                # 2. マイクロタイミングのゆらぎとコードのストラミング
                if not is_drum:
                    # 全般的な打鍵タイミングの微細なゆらぎ (±10ms程度)
                    timing_offset = random.uniform(-0.010, 0.010)
                    
                    if is_guitar_prog and len(group) > 1:
                        # ギターのストラミング（ジャカラン効果）：低い弦から順にタイミングをわずかに遅らせる (15ms間隔)
                        timing_offset += i * random.uniform(0.012, 0.018)
                    elif is_piano_prog and len(group) > 1:
                        # ピアノの両手による同時打鍵のわずかなバラつき
                        timing_offset += i * random.uniform(0.004, 0.007)
                        
                    start_time = max(0.0, start_time + timing_offset)
                    end_time = max(start_time + 0.05, end_time + timing_offset)
                else:
                    # ドラム：クオンタイズを保ちつつ、ハイハットのみ僅かにゆらす (グルーヴ感)
                    if note_data.pitch == 42:
                        timing_offset = random.uniform(-0.004, 0.004)
                        start_time = max(0.0, start_time + timing_offset)
                        end_time = max(start_time + 0.02, end_time + timing_offset)
                
                note = pretty_midi.Note(
                    velocity=vel,
                    pitch=note_data.pitch,
                    start=start_time,
                    end=end_time
                )
                inst.notes.append(note)
                
        pm.instruments.append(inst)
        
    # バイナリデータに書き出し
    buf = io.BytesIO()
    pm.write(buf)
    return buf.getvalue()

def midi_to_json(midi_bytes: bytes, duration_minutes: float = 5.0) -> MidiComposition:
    """
    標準MIDIファイルのバイナリデータをMidiCompositionデータモデルに変換する。
    """
    pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    
    # テンポの取得
    tempo_times, tempos = pm.get_tempo_changes()
    tempo_bpm = int(round(tempos[0])) if len(tempos) > 0 else 120
    
    tracks = []
    for i, inst in enumerate(pm.instruments):
        notes = []
        for note in inst.notes:
            step = seconds_to_steps(note.start, tempo_bpm)
            duration_steps = seconds_to_steps(note.end - note.start, tempo_bpm)
            # 最低でも1ステップの長さを確保
            if duration_steps < 1:
                duration_steps = 1
                
            notes.append(MidiNote(
                step=step,
                pitch=note.pitch,
                velocity=note.velocity,
                duration_steps=duration_steps
            ))
            
        # 音符をステップとピッチの順にソート
        notes.sort(key=lambda n: (n.step, n.pitch))
        
        # 楽器名の取得
        if inst.is_drum:
            instrument_name = "synth_drum_kit" # ドラム用の汎用名
        else:
            try:
                instrument_name = pretty_midi.program_to_instrument_name(inst.program)
            except ValueError:
                instrument_name = "acoustic_piano"
                
        # チャンネルの決定 (ドラムは9、その他は衝突しないように適当に割り当て)
        channel = 9 if inst.is_drum else (i if i != 9 else 10)
        
        tracks.append(MidiTrack(
            track_id=f"track_{i+1}",
            track_name=inst.name or f"Track {i+1}",
            instrument=instrument_name,
            channel=channel,
            muted=False,
            notes=notes
        ))
        
    return MidiComposition(
        tempo_bpm=tempo_bpm,
        time_signature="4/4",
        key_mode="major", # MIDIバイナリから正確なキー/モードの判定は難しいためデフォルト値
        duration_minutes=duration_minutes,
        sections=[], # MIDIファイルからセクションは判別不能なため空
        tracks=tracks
    )
