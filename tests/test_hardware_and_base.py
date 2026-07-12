from unittest.mock import patch
import pytest
from app.render.hardware_detect import detect_hardware_spec
from app.render.renderer_base import BaseRenderer

def test_hardware_detect_low_spec():
    """
    メモリ 8GB 以下の低スペック環境下での制限ロジックを検証する。
    """
    with patch("app.render.hardware_detect.get_cpu_brand", return_value="Apple M1"):
        with patch("app.render.hardware_detect.get_total_memory_gb", return_value=8.0):
            specs = detect_hardware_spec()
            assert specs["max_duration_minutes"] == 15.0
            assert specs["recommended_model_tier"] == "Lite"
            assert specs["memory_gb"] == 8.0

def test_hardware_detect_mid_spec_m1():
    """
    メモリ 16GB だがチップ世代が古い(M1)場合の判定を検証する。
    """
    with patch("app.render.hardware_detect.get_cpu_brand", return_value="Apple M1"):
        with patch("app.render.hardware_detect.get_total_memory_gb", return_value=16.0):
            specs = detect_hardware_spec()
            assert specs["max_duration_minutes"] == 30.0
            assert specs["recommended_model_tier"] == "Lite"  # M1 + 16GB は Lite

def test_hardware_detect_mid_spec_m2():
    """
    メモリ 16GB でチップ世代が M2 の場合の判定を検証する。
    """
    with patch("app.render.hardware_detect.get_cpu_brand", return_value="Apple M2"):
        with patch("app.render.hardware_detect.get_total_memory_gb", return_value=16.0):
            specs = detect_hardware_spec()
            assert specs["max_duration_minutes"] == 30.0
            assert specs["recommended_model_tier"] == "Standard"  # M2 + 16GB は Standard 推奨

def test_hardware_detect_high_spec_pro():
    """
    メモリ 18GB/36GB 以上かつ Pro/Max 性能チップ搭載環境を検証する。
    """
    with patch("app.render.hardware_detect.get_cpu_brand", return_value="Apple M3 Pro"):
        with patch("app.render.hardware_detect.get_total_memory_gb", return_value=18.0):
            specs = detect_hardware_spec()
            assert specs["max_duration_minutes"] == 60.0
            assert specs["recommended_model_tier"] == "High Quality"

def test_hardware_detect_high_spec_base_m3():
    """
    大容量メモリだがベースチップの場合の判定を検証する。
    """
    with patch("app.render.hardware_detect.get_cpu_brand", return_value="Apple M3"):
        with patch("app.render.hardware_detect.get_total_memory_gb", return_value=24.0):
            specs = detect_hardware_spec()
            assert specs["max_duration_minutes"] == 60.0
            assert specs["recommended_model_tier"] == "High Quality" # M3世代で24GBは高品質

def test_renderer_interface():
    """
    BaseRenderer を正しく継承し、必須メソッドが実装されているかを検証する。
    """
    # 抽象メソッドが実装されていない場合はエラーになることを確認
    with pytest.raises(TypeError):
        class BrokenRenderer(BaseRenderer):
            pass
        BrokenRenderer()

    # 実装されていればインスタンス化できることを確認
    class DummyRenderer(BaseRenderer):
        def render(self, midi_bytes: bytes, output_path: str, params: dict) -> None:
            pass
            
    renderer = DummyRenderer()
    assert isinstance(renderer, BaseRenderer)
