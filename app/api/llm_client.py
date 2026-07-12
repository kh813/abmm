import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2:3b"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, prompt: str, system_prompt: Optional[str] = None, format_json: bool = False) -> str:
        """
        Ollamaの /api/generate エンドポイントを呼び出す。
        """
        url = f"{self.base_url}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3, # 決定論的で構造化データに向いた低めの温度
            }
        }
        if system_prompt:
            payload["system"] = system_prompt
        if format_json:
            payload["format"] = "json"

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        try:
            # タイムアウトは長尺MIDI生成を考慮して90秒に設定
            with urllib.request.urlopen(req, timeout=90) as response:
                resp_bytes = response.read()
                resp_json = json.loads(resp_bytes.decode("utf-8"))
                return resp_json.get("response", "")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama APIへの接続に失敗しました: {e}. Ollamaが起動しているか確認してください。")
        except json.JSONDecodeError:
            raise RuntimeError("Ollama APIからのレスポンスをJSONとしてパースできませんでした。")
