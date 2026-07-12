import json
import pytest
from unittest.mock import patch, MagicMock
from app.api.llm_client import OllamaClient

def test_ollama_client_offline():
    client = OllamaClient()
    
    # urllib.request.urlopen raises URLError
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        status = client.check_status()
        assert status["running"] is False
        assert status["models"] == []

def test_ollama_client_online():
    client = OllamaClient()
    
    # Mock tags response
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "models": [
            {"name": "llama3.2:3b"},
            {"name": "gemma2:9b"}
        ]
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    
    with patch("urllib.request.urlopen", return_value=mock_resp):
        status = client.check_status()
        assert status["running"] is True
        assert "llama3.2:3b" in status["models"]
        assert "gemma2:9b" in status["models"]

def test_ollama_client_pull_model():
    client = OllamaClient()
    
    # Mock streaming pull responses
    mock_resp = MagicMock()
    # 2 lines of streaming progress, then end
    mock_resp.__iter__.return_value = [
        json.dumps({"status": "downloading", "completed": 25, "total": 100}).encode("utf-8"),
        json.dumps({"status": "downloading", "completed": 75, "total": 100}).encode("utf-8")
    ]
    mock_resp.__enter__.return_value = mock_resp
    
    progress_calls = []
    def prog_cb(pct, status):
        progress_calls.append((pct, status))
        
    with patch("urllib.request.urlopen", return_value=mock_resp):
        success = client.pull_model("llama3.2:3b", progress_callback=prog_cb)
        assert success is True
        assert len(progress_calls) == 2
        assert progress_calls[0] == (0.25, "downloading")
        assert progress_calls[1] == (0.75, "downloading")
