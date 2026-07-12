import os
import json
from unittest.mock import patch, MagicMock
import pytest
from app.api.handlers import WebviewApi
from app.composer.midi_schema import MidiComposition

# Mock MIDI JSON matching Pydantic schema
MOCK_MIDI_JSON = {
    "tempo_bpm": 85,
    "time_signature": "4/4",
    "key_mode": "major",
    "duration_minutes": 1.5,
    "sections": [
        {"name": "intro", "start_bar": 0, "bars": 2},
        {"name": "chorus", "start_bar": 2, "bars": 4}
    ],
    "tracks": [
        {
            "track_id": "track_test_1",
            "track_name": "Ambient Synth",
            "instrument": "synth_lead",
            "channel": 1,
            "muted": False,
            "notes": [
                {"step": 0, "pitch": 60, "velocity": 70, "duration_steps": 4},
                {"step": 4, "pitch": 64, "velocity": 70, "duration_steps": 4},
                {"step": 8, "pitch": 67, "velocity": 80, "duration_steps": 8}
            ]
        },
        {
            "track_id": "track_test_2",
            "track_name": "Synth Bass",
            "instrument": "synth_bass_1",
            "channel": 2,
            "muted": False,
            "notes": [
                {"step": 0, "pitch": 36, "velocity": 85, "duration_steps": 8},
                {"step": 8, "pitch": 43, "velocity": 85, "duration_steps": 8}
            ]
        }
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
        # cmd[2] に output_path (temp_preview.wav) が入っているはず
        output_path = cmd[2]
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # ダミーのWAVファイルを作成 (テスト成功の確認用)
        with open(output_path, "wb") as f:
            f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00...")
        
        # 正常終了の CompletedProcess オブジェクトを返す
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        return mock_proc

    mock_run.side_effect = fake_subprocess_run

    # 保存先を確認して必要なら旧ファイルをクリーンアップ
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
    assert response["tracks"][0]["track_name"] == "Ambient Synth"
    assert response["tracks"][0]["notes_count"] == 3
    assert response["tracks"][1]["track_name"] == "Synth Bass"
    assert response["tracks"][1]["notes_count"] == 2
    assert response["audio_url"] == "temp_preview.wav"

    # レンダリング結果のファイルが正常に生成されているかチェック
    assert os.path.exists(api_instance.preview_wav_path)
    assert os.path.getsize(api_instance.preview_wav_path) > 0

    # 呼び出しパラメータの検証
    mock_llm_generate.assert_called_once()
    mock_ensure_sf.assert_called_once()
    mock_run.assert_called_once()

    # 6. クリーンアップ
    if os.path.exists(api_instance.preview_wav_path):
        os.remove(api_instance.preview_wav_path)
