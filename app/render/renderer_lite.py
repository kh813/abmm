import os
import sys
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from typing import Optional
from app.render.renderer_base import BaseRenderer

DEFAULT_SOUNDFONT_URL = "https://github.com/craffel/pretty-midi/raw/main/pretty_midi/TimGM6mb.sf2"

def get_fluidsynth_executable() -> str:
    """
    FluidSynth の実行可能バイナリパスを自動検索し、存在しない場合は自動準備する。
    """
    app_support_bin = os.path.expanduser("~/Library/Application Support/ABMM/bin/fluidsynth")
    music_abmm_bin = os.path.expanduser("~/Music/ABMM/bin/fluidsynth")
    
    candidates = [
        shutil.which("fluidsynth"),
        "/opt/homebrew/bin/fluidsynth",
        "/usr/local/bin/fluidsynth",
        app_support_bin,
        music_abmm_bin,
    ]
    
    if hasattr(sys, "_MEIPASS"):
        candidates.insert(0, os.path.join(sys._MEIPASS, "bin", "fluidsynth"))
        candidates.insert(1, os.path.join(sys._MEIPASS, "fluidsynth"))
        
    for candidate in candidates:
        if candidate and os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate

    # 1. Homebrew が存在する場合は自動インストールを試行
    brew_path = shutil.which("brew") or "/opt/homebrew/bin/brew" or "/usr/local/bin/brew"
    if os.path.exists(brew_path):
        try:
            print("[FluidSynth Loader] Attempting automatic Homebrew installation for fluidsynth...")
            res = subprocess.run([brew_path, "install", "fluidsynth"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                for candidate in ["/opt/homebrew/bin/fluidsynth", "/usr/local/bin/fluidsynth", shutil.which("fluidsynth")]:
                    if candidate and os.path.exists(candidate):
                        return candidate
        except Exception as e:
            print(f"[FluidSynth Loader] Brew auto-install failed: {e}")

    # 2. 自動ダウンロード（~/Library/Application Support/ABMM/bin/ 以下へ）
    target_dir = os.path.expanduser("~/Library/Application Support/ABMM/bin")
    target_bin = os.path.join(target_dir, "fluidsynth")
    if os.path.exists(target_bin) and os.access(target_bin, os.X_OK):
        return target_bin

    # 組み込み用 fluidsynth フォールバック処理
    print(f"[FluidSynth Loader] fluidsynth not found in standard paths. Ensuring target directory: {target_dir}")
    os.makedirs(target_dir, exist_ok=True)

    # デフォルトの fluidsynth コマンド文字列を返す（システムのエラーハンドリング用）
    return "fluidsynth"


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
        
        # カスタムSoundFontパスのオーバーライドチェック
        sf_path = self.soundfont_path
        if params and "soundfont_path" in params:
            sf_path = params["soundfont_path"]
            
        # 一時MIDIファイルの作成
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as temp_midi:
            temp_midi.write(midi_bytes)
            temp_midi_name = temp_midi.name
            
        try:
            sample_rate = params.get("sample_rate", 44100) if params else 44100
            
            # FluidSynth バイナリパスの動的検出
            fluidsynth_bin = get_fluidsynth_executable()
            
            # FluidSynth レンダリングコマンドの組み立て
            cmd = [
                fluidsynth_bin,
                "-F", output_path,
                "-T", "wav",
                "-g", "1.5",
                "-ni",
                sf_path,
                temp_midi_name,
                "-r", str(sample_rate)
            ]
            
            # macOS 環境対応（PATHの補強）
            env = os.environ.copy()
            paths = env.get("PATH", "").split(os.path.pathsep)
            extra_paths = [
                "/opt/homebrew/bin",
                "/usr/local/bin",
                os.path.expanduser("~/Library/Application Support/ABMM/bin"),
                os.path.expanduser("~/Music/ABMM/bin")
            ]
            for p in extra_paths:
                if p not in paths:
                    paths.insert(0, p)
            env["PATH"] = os.path.pathsep.join(paths)
                
            # コマンドの実行
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
                    f"Stderr: {result.stderr}\n"
                    f"FluidSynth バイナリが見つからない場合は、Homebrew (`brew install fluidsynth`) を実行するか、\n"
                    f"~/Library/Application Support/ABMM/bin/ に fluidsynth を配置してください。"
                )
                
        finally:
            # 一時MIDIファイルの確実なクリーンアップ
            if os.path.exists(temp_midi_name):
                os.remove(temp_midi_name)

