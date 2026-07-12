import os
import json
from unittest.mock import patch, MagicMock
import pytest
from app.api.handlers import WebviewApi
from app.composer.midi_schema import MidiComposition

# Mock Chord Plan JSON
MOCK_MIDI_JSON = {
    "tempo_bpm": 85,
    "key_mode": "major",
    "style": "ambient",
    "instruments": ["piano", "guitar"],
    "sections": [
        {"name": "intro", "bars": 2, "chords": ["C", "F"]},
        {"name": "chorus", "bars": 4, "chords": ["C", "G", "Am", "F"]}
    ]
}

@pytest.fixture
def api_instance():
    return WebviewApi()

@patch("app.api.llm_client.OllamaClient.generate")
@patch("app.render.renderer_lite.LiteRenderer.ensure_soundfont")
@patch("subprocess.run")
def test_compose_and_preview_integration(mock_run, mock_ensure_sf, mock_llm_generate, api_instance):
    """
    Ollama (LLM) 呼び出し -> MIDI変換 -> FluidSynth (LiteRenderer) レンダリング
    までの一連の統合フローの検証テスト。
    """
    # 1. LLMレスポンスをモック化
    mock_llm_generate.return_value = json.dumps(MOCK_MIDI_JSON)
    
    # 2. SoundFontのダウンロード処理をスキップ (何もしない)
    mock_ensure_sf.return_value = None
    
    # 3. Subprocess (FluidSynth コマンド実行) をモック化し、ダミーのWAVファイル作成処理を注入
    def fake_subprocess_run(cmd, *args, **kwargs):
        output_path = cmd[2]
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00...")
            
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        return mock_proc
        
    mock_run.side_effect = fake_subprocess_run
    
    if os.path.exists(api_instance.preview_wav_path):
        os.remove(api_instance.preview_wav_path)
        
    # 4. APIを実行
    response = api_instance.compose_and_preview(
        description="A beautiful ambient soundscape",
        tempo=85,
        key_mode="major",
        duration=1.5
    )
    
    # 5. アサーションによる検証
    assert response["status"] == "success"
    assert response["tempo_bpm"] == 85
    assert response["key_mode"] == "major"
    assert response["duration_minutes"] == 1.5
    assert len(response["tracks"]) == 2
