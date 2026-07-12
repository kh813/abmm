import os
import subprocess
import tempfile
import urllib.request
from typing import Optional
from app.render.renderer_base import BaseRenderer

DEFAULT_SOUNDFONT_URL = "https://github.com/craffel/pretty-midi/raw/main/pretty_midi/TimGM6mb.sf2"

class LiteRenderer(BaseRenderer):
    def __init__(self, soundfont_dir: Optional[str] = None):
        if soundfont_dir is None:
            # リポジトリルートを基準にしたパス設定
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            soundfont_dir = os.path.join(base_dir, "assets", "soundfonts")
        
        self.soundfont_dir = soundfont_dir
        self.soundfont_path = os.path.join(self.soundfont_dir, "default.sf2")

    def ensure_soundfont(self) -> None:
        """
        SoundFontが存在しない場合は、リポジトリ内のアセットディレクトリに自動ダウンロードする。
        """
        if os.path.exists(self.soundfont_path):
            return
            
        os.makedirs(self.soundfont_dir, exist_ok=True)
        print(f"[FluidSynth LiteRenderer] SoundFont downloading: {DEFAULT_SOUNDFONT_URL}")
        try:
            # urllibを使用してバイナリとしてダウンロード
            req = urllib.request.Request(
                DEFAULT_SOUNDFONT_URL,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            )
            with urllib.request.urlopen(req) as response:
                with open(self.soundfont_path, "wb") as f:
                    f.write(response.read())
            print(f"[FluidSynth LiteRenderer] SoundFont saved successfully to: {self.soundfont_path}")
        except Exception as e:
            raise RuntimeError(
                f"SoundFontのダウンロードに失敗しました: {e}. "
                "ネットワーク接続を確認するか、手動で default.sf2 を assets/soundfonts/ に配置してください。"
            )

    def render(self, midi_bytes: bytes, output_path: str, params: Optional[dict] = None) -> None:
        """
        MIDIバイナリデータをFluidSynth CLIを使用してWAVオーディオファイルに高速レンダリングする。
        """
        self.ensure_soundfont()
        
        # 一時MIDIファイルの作成
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as temp_midi:
            temp_midi.write(midi_bytes)
            temp_midi_name = temp_midi.name
            
        try:
            sample_rate = params.get("sample_rate", 44100) if params else 44100
            
            # FluidSynth レンダリングコマンドの組み立て
            cmd = [
                "fluidsynth",
                "-F", output_path,
                "-T", "wav",
                "-g", "1.5",
                "-ni",
                self.soundfont_path,
                temp_midi_name,
                "-r", str(sample_rate)
            ]
            
            # macOS Homebrew 環境対応（PATHの補強）
            env = os.environ.copy()
            paths = env.get("PATH", "").split(os.path.pathsep)
            brew_bin = "/opt/homebrew/bin"
            if brew_bin not in paths:
                paths.insert(0, brew_bin)
                env["PATH"] = os.path.pathsep.join(paths)
                
            # コマンドの非同期実行
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            if result.returncode != 0:
                raise RuntimeError(
                    f"FluidSynthによるオーディオレンダリングに失敗しました。\n"
                    f"Command: {' '.join(cmd)}\n"
                    f"Stderr: {result.stderr}"
                )
                
        finally:
            # 一時MIDIファイルの確実なクリーンアップ
            if os.path.exists(temp_midi_name):
                os.remove(temp_midi_name)
