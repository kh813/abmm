import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Callable

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2:3b"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def check_status(self) -> Dict[str, Any]:
        """
        Ollamaの起動状態およびインストール済みモデル一覧を取得する。
        """
        url = f"{self.base_url}/api/tags"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                resp_json = json.loads(response.read().decode("utf-8"))
                models = [m["name"] for m in resp_json.get("models", [])]
                return {
                    "running": True,
                    "models": models
                }
        except Exception as e:
            return {
                "running": False,
                "models": [],
                "error": str(e)
            }

    def pull_model(self, model_name: str, progress_callback: Optional[Callable[[float, str], None]] = None) -> bool:
        """
        Ollamaにモデルのダウンロード（pull）を要求する。
        """
        url = f"{self.base_url}/api/pull"
        payload = {
            "name": model_name,
            "stream": True
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            # モデルのダウンロードを考慮してタイムアウトを長めに設定
            with urllib.request.urlopen(req, timeout=600) as response:
                for line in response:
                    if not line:
                        continue
                    line_data = json.loads(line.decode("utf-8"))
                    status = line_data.get("status", "")
                    
                    completed = line_data.get("completed", 0)
                    total = line_data.get("total", 0)
                    percent = 0.0
                    if total > 0:
                        percent = completed / total
                        
                    if progress_callback:
                        progress_callback(percent, status)
            return True
        except Exception as e:
            print(f"[OllamaClient] Failed to pull model {model_name}: {e}")
            return False

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
