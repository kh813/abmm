"""
MidiTok 連携ヘルパーモジュール
MidiTokライブラリを使用して、MIDIバイナリとLLM向けトークン表現（REMI等）の相互変換を提供します。
"""
import io
import logging
from typing import List, Optional, Any

logger = logging.getLogger(__name__)

try:
    import miditok
    from symusic import Score
    MIDITOK_AVAILABLE = True
except ImportError:
    MIDITOK_AVAILABLE = False
    logger.warning("MidiTok または symusic がインストールされていません。MidiTok機能は利用できません。")


def is_miditok_available() -> bool:
    """MidiTokが利用可能かどうかを返す。"""
    return MIDITOK_AVAILABLE


def get_default_tokenizer() -> Optional[Any]:
    """デフォルトのREMIトークナイザーを取得する。"""
    if not MIDITOK_AVAILABLE:
        return None
    try:
        config = miditok.TokenizerConfig(
            pitch_range=(21, 109),
            num_velocities=32,
            use_chords=True,
            use_tempos=True,
            use_time_signatures=True,
        )
        return miditok.REMI(config)
    except Exception as e:
        logger.error(f"Tokenizerの初期化に失敗しました: {e}")
        return None


def midi_bytes_to_tokens(midi_bytes: bytes) -> List[int]:
    """
    MIDIバイナリデータをMidiTokのトークンIDリストに変換する。
    """
    if not MIDITOK_AVAILABLE:
        raise RuntimeError("MidiTokライブラリが利用できません。")

    tokenizer = get_default_tokenizer()
    if tokenizer is None:
        raise RuntimeError("Tokenizerの取得に失敗しました。")

    # symusic.Scoreを使用してバイナリからロード
    score = Score.from_midi(midi_bytes)
    tokens = tokenizer(score)
    
    # miditokの返り値構造（TokSequenceまたはそのリスト）から平坦なintリストを取り出す
    if isinstance(tokens, list):
        result = []
        for seq in tokens:
            if hasattr(seq, "ids"):
                result.extend(seq.ids)
            elif isinstance(seq, list):
                result.extend(seq)
        return result
    elif hasattr(tokens, "ids"):
        return tokens.ids
    return list(tokens)
