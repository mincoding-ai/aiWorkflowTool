# Design Ref: §6 (UI 설계) — 진행 패널 (게이지 + 로그 + 상태 레이블)

import wx

_TOTAL_PHASES = 5


class ProgressPanel(wx.Panel):
    """
    파이프라인 진행 상태를 실시간으로 표시하는 패널.
    Phase 게이지, 현재 상태 레이블, 스크롤 가능한 로그 영역으로 구성된다.
    모든 update_* 메서드는 wx.CallAfter를 통해 UI 스레드에서 안전하게 호출해야 한다.
    """

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self._build_ui()

    # ──────────────────────────────────────────────
    # Public update API (wx.CallAfter로 호출)
    # ──────────────────────────────────────────────

    def update_phase_start(self, phase_num: int, phase_name: str) -> None:
        """
        Phase 시작 시 게이지와 상태 레이블을 업데이트하고 로그를 추가한다.

        Args:
            phase_num: 1~5 Phase 번호
            phase_name: Phase 이름 (예: "전체 개요 분석")
        """
        progress_pct = int((phase_num - 1) / _TOTAL_PHASES * 100)
        self._gauge.SetValue(progress_pct)
        self._status_label.SetLabel(f"Phase {phase_num}/{_TOTAL_PHASES}: {phase_name} 중...")
        self._append_log(f"🔄 Phase {phase_num} 시작: {phase_name}")

    def update_phase_done(self, phase_num: int) -> None:
        """
        Phase 완료 시 게이지를 전진시키고 완료 로그를 추가한다.

        Args:
            phase_num: 완료된 Phase 번호 (1~5)
        """
        progress_pct = int(phase_num / _TOTAL_PHASES * 100)
        self._gauge.SetValue(progress_pct)
        self._append_log(f"✅ Phase {phase_num} 완료")

    def update_class_done(self, class_name: str, index: int, total: int) -> None:
        """
        클래스 분석 완료 시 세부 진행 상태를 업데이트한다.

        Args:
            class_name: 완료된 클래스 이름
            index: 완료된 클래스 순번 (1-based)
            total: 전체 클래스 수
        """
        # Phase 4 구간 (60%~80%) 내에서 클래스별 세부 진행
        phase4_start = int(3 / _TOTAL_PHASES * 100)
        phase4_end = int(4 / _TOTAL_PHASES * 100)
        if total > 0:
            inner = int((index / total) * (phase4_end - phase4_start))
            self._gauge.SetValue(phase4_start + inner)

        self._status_label.SetLabel(
            f"Phase 4/{_TOTAL_PHASES}: 주석 삽입 ({index}/{total}) — {class_name}"
        )
        self._append_log(f"  💬 {class_name} ({index}/{total})")

    def update_pipeline_done(self) -> None:
        """파이프라인 완료 시 게이지를 100%로 설정하고 완료 메시지를 표시한다."""
        self._gauge.SetValue(100)
        self._status_label.SetLabel("분석 완료!")
        self._append_log("🎉 전체 분석 완료! _ai_analysis/ 폴더를 확인하세요.")

    def update_error(self, message: str, phase_num: int | None = None) -> None:
        """
        오류 발생 시 빨간 텍스트로 로그에 추가한다.

        Args:
            message: 오류 메시지
            phase_num: 오류가 발생한 Phase 번호 (없으면 None)
        """
        location = f"Phase {phase_num}" if phase_num is not None else "파이프라인"
        self._status_label.SetLabel(f"오류 발생 — {location}")
        self._append_log(f"❌ 오류 ({location}): {message}", color=wx.RED)

    def reset(self) -> None:
        """게이지, 상태 레이블, 로그를 초기 상태로 되돌린다."""
        self._gauge.SetValue(0)
        self._status_label.SetLabel("대기 중...")
        self._log.SetValue("")

    def append_log(self, text: str, color: wx.Colour | None = None) -> None:
        """
        외부에서 직접 로그를 추가할 때 사용한다 (wx.CallAfter로 호출).

        Args:
            text: 추가할 텍스트
            color: 텍스트 색상 (None이면 기본색)
        """
        self._append_log(text, color)

    # ──────────────────────────────────────────────
    # Private
    # ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        """UI 위젯을 생성하고 레이아웃을 구성한다."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # 진행 상황 레이블
        progress_label = wx.StaticText(self, label="진행 상황:")
        sizer.Add(progress_label, 0, wx.ALL, 4)

        # 게이지
        self._gauge = wx.Gauge(self, range=100, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self._gauge.SetValue(0)
        sizer.Add(self._gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        # 현재 상태 레이블
        self._status_label = wx.StaticText(self, label="대기 중...")
        sizer.Add(self._status_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        # 로그 텍스트 (읽기 전용, 스크롤)
        self._log = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.HSCROLL,
        )
        self._log.SetMinSize((-1, 200))
        sizer.Add(self._log, 1, wx.EXPAND | wx.ALL, 4)

        self.SetSizer(sizer)

    def _append_log(self, text: str, color: wx.Colour | None = None) -> None:
        """
        로그 텍스트 영역에 한 줄을 추가하고 맨 아래로 스크롤한다.

        Args:
            text: 추가할 텍스트
            color: 텍스트 색상 (None이면 기본색)
        """
        if color is not None:
            self._log.SetDefaultStyle(wx.TextAttr(color))
        self._log.AppendText(text + "\n")
        if color is not None:
            self._log.SetDefaultStyle(wx.TextAttr(wx.NullColour))
        self._log.ShowPosition(self._log.GetLastPosition())
