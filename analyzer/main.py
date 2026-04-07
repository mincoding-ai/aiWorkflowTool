# Design Ref: §2 (모듈 구조) — 앱 진입점. wx.App 초기화 후 AnalyzerMainWindow 실행.

import os
import sys
from pathlib import Path


def _load_dotenv() -> None:
    """
    python-dotenv가 설치되어 있으면 .env 파일을 로드한다.
    미설치 시 조용히 무시한다 (선택적 의존성).
    """
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent / ".env"
        load_dotenv(env_path)
    except ImportError:
        pass


def main() -> None:
    """
    Source Code Analyzer 앱을 시작한다.

    .env 파일(또는 환경변수) OPENAI_API_KEY가 설정되어 있으면
    창 초기화 시 자동으로 API 키 입력란에 채운다.
    wxPython이 설치되어 있지 않으면 안내 메시지를 출력하고 종료한다.
    """
    _load_dotenv()
    try:
        import wx
    except ImportError:
        print(
            "[오류] wxPython이 설치되어 있지 않습니다.\n"
            "설치 명령: pip install wxPython>=4.2.0"
        )
        sys.exit(1)

    from src.ui.main_window import AnalyzerMainWindow

    app = wx.App(False)
    win = AnalyzerMainWindow()

    # 환경변수에서 API 키 자동 주입
    api_key_env = os.environ.get("OPENAI_API_KEY", "")
    if api_key_env:
        win._api_ctrl.SetValue(api_key_env)

    win.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
