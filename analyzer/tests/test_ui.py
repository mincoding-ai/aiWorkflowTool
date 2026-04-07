"""
Session 7 코드 테스트: wxPython UI

전략:
- wx 미설치 환경: pytest.importorskip('wx')로 전체 스킵
- wx 설치 환경:
  - wx.App + wx.Frame 헤드리스 모드(wx.App(False)) 로 인스턴스화 검증
  - ProgressPanel: update_* 메서드 호출 후 상태 검증
  - AnalyzerMainWindow: 위젯 초기 상태 검증
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

wx = pytest.importorskip("wx", reason="wxPython 미설치 — UI 테스트 스킵")

# wx import 성공한 경우에만 아래 코드 실행
from src.ui.main_window import AnalyzerMainWindow  # noqa: E402
from src.ui.progress_panel import ProgressPanel  # noqa: E402


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    """모듈 범위 wx.App (헤드리스)"""
    _app = wx.App(False)
    yield _app
    _app.Destroy()


@pytest.fixture
def frame(app):
    """테스트용 임시 wx.Frame"""
    f = wx.Frame(None)
    yield f
    f.Destroy()


@pytest.fixture
def panel(frame):
    """ProgressPanel 인스턴스"""
    p = ProgressPanel(frame)
    yield p


@pytest.fixture
def main_window(app):
    """AnalyzerMainWindow 인스턴스"""
    win = AnalyzerMainWindow()
    yield win
    win.Destroy()


# ──────────────────────────────────────────────
# ProgressPanel 초기 상태
# ──────────────────────────────────────────────

class TestProgressPanelInit:
    def test_게이지_초기값_0(self, panel):
        assert panel._gauge.GetValue() == 0

    def test_상태_레이블_초기값(self, panel):
        assert "대기" in panel._status_label.GetLabel()

    def test_로그_초기_빈값(self, panel):
        assert panel._log.GetValue() == ""


# ──────────────────────────────────────────────
# ProgressPanel update_* 메서드
# ──────────────────────────────────────────────

class TestProgressPanelUpdates:
    def test_phase_start_게이지_전진(self, panel):
        panel.update_phase_start(1, "전체 개요 분석")
        assert panel._gauge.GetValue() == 0  # (1-1)/5 * 100 = 0

    def test_phase_start_로그_추가(self, panel):
        panel.update_phase_start(2, "클래스 추출")
        assert "Phase 2" in panel._log.GetValue()
        assert "클래스 추출" in panel._log.GetValue()

    def test_phase_start_상태_레이블_변경(self, panel):
        panel.update_phase_start(3, "의존성 분석")
        label = panel._status_label.GetLabel()
        assert "Phase 3" in label
        assert "의존성 분석" in label

    def test_phase_done_게이지_전진(self, panel):
        panel.update_phase_done(1)
        assert panel._gauge.GetValue() == 20  # 1/5 * 100

    def test_phase_done_로그_추가(self, panel):
        panel.reset()
        panel.update_phase_done(2)
        assert "Phase 2" in panel._log.GetValue()

    def test_class_done_로그_추가(self, panel):
        panel.reset()
        panel.update_class_done("MyClass", 3, 10)
        log = panel._log.GetValue()
        assert "MyClass" in log
        assert "3/10" in log

    def test_pipeline_done_게이지_100(self, panel):
        panel.update_pipeline_done()
        assert panel._gauge.GetValue() == 100

    def test_pipeline_done_상태_레이블(self, panel):
        panel.update_pipeline_done()
        assert "완료" in panel._status_label.GetLabel()

    def test_pipeline_done_로그_추가(self, panel):
        panel.reset()
        panel.update_pipeline_done()
        assert "완료" in panel._log.GetValue()

    def test_error_상태_레이블(self, panel):
        panel.update_error("API 호출 실패", phase_num=1)
        assert "오류" in panel._status_label.GetLabel()

    def test_error_로그_추가(self, panel):
        panel.reset()
        panel.update_error("API 호출 실패", phase_num=2)
        log = panel._log.GetValue()
        assert "API 호출 실패" in log

    def test_reset_초기화(self, panel):
        panel.update_phase_done(3)
        panel.update_class_done("X", 5, 10)
        panel.reset()
        assert panel._gauge.GetValue() == 0
        assert panel._log.GetValue() == ""
        assert "대기" in panel._status_label.GetLabel()


# ──────────────────────────────────────────────
# AnalyzerMainWindow 초기 상태
# ──────────────────────────────────────────────

class TestMainWindowInit:
    def test_창_제목(self, main_window):
        assert "Analyzer" in main_window.GetTitle()

    def test_경로_입력_초기_빈값(self, main_window):
        assert main_window._path_ctrl.GetValue() == ""

    def test_api키_입력_초기_빈값(self, main_window):
        assert main_window._api_ctrl.GetValue() == ""

    def test_시작_버튼_활성화(self, main_window):
        assert main_window._start_btn.IsEnabled()

    def test_이어서_버튼_활성화(self, main_window):
        assert main_window._resume_btn.IsEnabled()

    def test_progress_panel_존재(self, main_window):
        assert isinstance(main_window._progress_panel, ProgressPanel)


# ──────────────────────────────────────────────
# AnalyzerMainWindow 콜백 처리
# ──────────────────────────────────────────────

class TestMainWindowCallback:
    def test_phase_start_콜백(self, main_window):
        """_pipeline_callback이 phase_start 이벤트를 ProgressPanel에 전달한다"""
        from src.core.pipeline import EVT_PHASE_START
        main_window._pipeline_callback(EVT_PHASE_START, {"phase": 1, "name": "개요 분석"})
        # wx.CallAfter가 큐에 등록됨 — wx.SafeYield()로 처리
        wx.SafeYield()
        log = main_window._progress_panel._log.GetValue()
        assert "Phase 1" in log

    def test_pipeline_done_콜백(self, main_window):
        from src.core.pipeline import EVT_PIPELINE_DONE
        main_window._pipeline_callback(EVT_PIPELINE_DONE, {})
        wx.SafeYield()
        assert main_window._progress_panel._gauge.GetValue() == 100

    def test_error_콜백(self, main_window):
        from src.core.pipeline import EVT_ERROR
        main_window._pipeline_callback(EVT_ERROR, {"message": "테스트 오류", "phase": 2})
        wx.SafeYield()
        log = main_window._progress_panel._log.GetValue()
        assert "테스트 오류" in log
