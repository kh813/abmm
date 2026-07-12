from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class MidiNote(BaseModel):
    step: int = Field(..., description="16分音符単位のグリッド位置（1小節=16ステップ）")
    pitch: int = Field(..., ge=0, le=127, description="MIDIノート番号")
    velocity: int = Field(..., ge=0, le=127, description="音量/強さ (0-127)")
    duration_steps: int = Field(..., ge=1, description="ステップ単位の音の長さ")

class MidiTrack(BaseModel):
    track_id: str = Field(..., description="トラックの一意の識別子")
    track_name: str = Field(..., description="表示名（例: Piano, Bass）")
    instrument: str = Field(..., description="楽器の種類（General MIDI名等、例: acoustic_piano）")
    channel: int = Field(..., ge=0, le=15, description="MIDIチャンネル (0-15)")
    muted: bool = Field(default=False, description="トラックのミュート状態")
    notes: List[MidiNote] = Field(default_factory=list, description="音符リスト")

class MidiSection(BaseModel):
    name: str = Field(..., description="セクション名（例: intro, main, outro）")
    start_bar: int = Field(..., ge=0, description="開始小節番号（0から開始）")
    bars: int = Field(..., ge=1, description="セクションの小節数")

class MidiComposition(BaseModel):
    tempo_bpm: int = Field(..., ge=20, le=300, description="テンポ (BPM)")
    time_signature: str = Field(default="4/4", description="拍子記号（現状は4/4固定）")
    key_mode: str = Field(default="major", description="キーモード（major または minor）")
    duration_minutes: float = Field(..., ge=0.1, le=120.0, description="曲全体の指定の長さ（分）")
    sections: List[MidiSection] = Field(default_factory=list, description="曲の構成セクションリスト")
    tracks: List[MidiTrack] = Field(default_factory=list, description="トラックリスト")

    @field_validator("time_signature")
    @classmethod
    def validate_time_signature(cls, v: str) -> str:
        if v != "4/4":
            raise ValueError("ABMM v0.4 では拍子は 4/4 のみサポートされています。")
        return v

    @field_validator("key_mode")
    @classmethod
    def validate_key_mode(cls, v: str) -> str:
        if v not in ("major", "minor"):
            raise ValueError("key_mode は 'major' または 'minor' である必要があります。")
        return v
