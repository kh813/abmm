from abc import ABC, abstractmethod

class BaseRenderer(ABC):
    """
    すべての音源レンダラーの共通インターフェース定義。
    """
    @abstractmethod
    def render(self, midi_bytes: bytes, output_path: str, params: dict) -> None:
        """
        MIDIバイナリデータを音声ファイル（WAV等）にレンダリングして保存する。
        
        :param midi_bytes: MIDIファイルのバイナリデータ
        :param output_path: 出力先オーディオファイルの絶対パス
        :param params: レンダリングパラメータの辞書
        """
        pass
