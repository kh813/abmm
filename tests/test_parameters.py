import json
from unittest.mock import patch, MagicMock
import pytest
from app.api.handlers import WebviewApi
from app.composer.prompt_builder import build_prompt

def test_build_prompt_includes_all_parameters():
    """
    build_prompt がすべての微調整スライダー値および楽器バランスを
    システムプロンプトに正しく含めることを検証する。
    """
    description = "Quiet fireplace soundscape"
    tempo = 72
    key_mode = "minor"
    duration = 2.0
    brightness = 0.2
    energy = 0.1
    density = 0.3
    instruments = {
        "piano": 0.5,
        "guitar": 0.8,
        "drums": 0.0,
        "pad": 0.9,
        "bass": 0.4
    }

    prompt = build_prompt(
        description=description,
        tempo_bpm=tempo,
        key_mode=key_mode,
        duration_minutes=duration,
        brightness=brightness,
        energy=energy,
        density=density,
        instruments=instruments
    )

    # 各パラメータがプロンプトのテキストに含まれているか確認
    assert description in prompt
    assert "72 BPM" in prompt
    assert "minor" in prompt
    assert "2.0 minutes" in prompt
    assert "Brightness (Major/Minor balance): 0.2" in prompt
    assert "Energy (Dynamics/Volume): 0.1" in prompt
    assert "Density (Note count): 0.3" in prompt
    
    # 楽器バランス
    assert "piano: 0.5" in prompt
    assert "guitar: 0.8" in prompt
    assert "drums: 0.0" in prompt
    assert "pad: 0.9" in prompt
    assert "bass: 0.4" in prompt
    
    # 音楽的ルールのセクション
    assert "Musical Rules to Apply" in prompt
    assert "brightness < 0.5" in prompt
    assert "do NOT create a track for it" in prompt

@patch("app.api.llm_client.OllamaClient.generate")
@patch("app.render.renderer_lite.LiteRenderer.render")
def test_webview_api_handles_all_parameters(mock_render, mock_generate):
    """
    WebviewApi.compose_and_preview がすべての新規スライダーパラメータを受け取り、
    生成およびレンダラーに伝播させることを検証する。
    """
    api = WebviewApi()
    
    # モックの動作設定
    mock_generate.return_value = json.dumps({
        "tempo_bpm": 72,
        "time_signature": "4/4",
        "key_mode": "minor",
        "duration_minutes": 2.0,
        "sections": [],
        "tracks": []
    })
    
    instruments = {
        "piano": 0.5,
        "guitar": 0.8,
        "drums": 0.0,
        "pad": 0.9,
        "bass": 0.4
    }

    # すべての引数付きで呼び出し
    response = api.compose_and_preview(
        description="test music",
        tempo=72,
        key_mode="minor",
        duration=2.0,
        brightness=0.2,
        energy=0.1,
        density=0.3,
        reverb_space=0.6,
        instruments=instruments
    )

    assert response["status"] == "success"
    
    # generate_midi_json のモック呼び出し引数の検証
    mock_generate.assert_called_once()
    called_prompt = mock_generate.call_args[0][0]
    
    # プロンプトの中に詳細パラメータが渡っているかチェック
    assert "Brightness (Major/Minor balance): 0.2" in called_prompt
    assert "Energy (Dynamics/Volume): 0.1" in called_prompt
    assert "Density (Note count): 0.3" in called_prompt
    assert "piano: 0.5" in called_prompt
    assert "drums: 0.0" in called_prompt

    # レンダラーが呼び出されたことを確認
    mock_render.assert_called_once()
