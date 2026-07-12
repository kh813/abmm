"""
AI Background Music Maker (ABMM) - エントリポイント

現時点ではビルドパイプライン検証用の最小構成（雛形）です。
Phase 1 / Phase 2 の実処理は今後の実装で追加していきます。
"""

import os
import sys


def resource_path(relative_path: str) -> str:
    """
    開発時実行 (python app/main.py) と、PyInstallerでバンドルされた実行ファイル
    の両方で、frontendリソースへの正しいパスを解決するためのヘルパー。
    """
    if hasattr(sys, "_MEIPASS"):
        # PyInstallerでバンドルされた場合、リソースは _MEIPASS 直下に展開される
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        # 開発時実行の場合は、このファイルから見たリポジトリルートを基準にする
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def main() -> None:
    import webview  # pywebview

    index_path = resource_path(os.path.join("frontend", "index.html"))

    webview.create_window(
        "AI Background Music Maker (ABMM)",
        index_path,
        width=1000,
        height=700,
        min_size=(800, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()
