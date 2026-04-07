# Design Ref: §6 (UI 설계) — 메인 창, 경로 입력, 파이프라인 스레드 실행

import threading

import wx

from ..core.pipeline import (
    EVT_CLASS_DONE,
    EVT_ERROR,
    EVT_PHASE_DONE,
    EVT_PHASE_START,
    EVT_PIPELINE_DONE,
    PipelineOrchestrator,
)
from .progress_panel import ProgressPanel

_APP_TITLE = "Source Code Analyzer"
_MIN_SIZE = (640, 560)


class AnalyzerMainWindow(wx.Frame):
    """
    소스코드 분석기 메인 창.
    소스 경로·API 키 입력, 분석 시작/이어서 버튼, 진행 패널로 구성된다.
    파이프라인은 UI 블로킹을 막기 위해 별도 스레드에서 실행된다.
    """

    def __init__(self, parent: wx.Window | None = None) -> None:
        super().__init__(parent, title=_APP_TITLE, size=_MIN_SIZE)
        self.SetMinSize(_MIN_SIZE)
        self._pipeline_thread: threading.Thread | None = None
        self._build_ui()
        self.Centre()

    # ──────────────────────────────────────────────
    # UI 구성
    # ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        """위젯 생성 및 레이아웃 구성"""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # ── 소스 경로 입력 ──
        path_label = wx.StaticText(panel, label="소스코드 경로:")
        main_sizer.Add(path_label, 0, wx.ALL, 8)

        path_row = wx.BoxSizer(wx.HORIZONTAL)
        self._path_ctrl = wx.TextCtrl(panel)
        browse_btn = wx.Button(panel, label="찾기")
        browse_btn.Bind(wx.EVT_BUTTON, self._on_browse)
        path_row.Add(self._path_ctrl, 1, wx.EXPAND | wx.RIGHT, 4)
        path_row.Add(browse_btn, 0)
        main_sizer.Add(path_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # ── API 키 입력 ──
        api_label = wx.StaticText(panel, label="OpenAI API 키:")
        main_sizer.Add(api_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self._api_ctrl = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        main_sizer.Add(self._api_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # ── 버튼 행 ──
        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self._start_btn = wx.Button(panel, label="분석 시작")
        self._resume_btn = wx.Button(panel, label="이어서 시작")
        self._start_btn.Bind(wx.EVT_BUTTON, self._on_start)
        self._resume_btn.Bind(wx.EVT_BUTTON, self._on_resume)
        btn_row.Add(self._start_btn, 1, wx.RIGHT, 8)
        btn_row.Add(self._resume_btn, 1)
        main_sizer.Add(btn_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # ── 구분선 ──
        main_sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        # ── 진행 패널 ──
        self._progress_panel = ProgressPanel(panel)
        main_sizer.Add(self._progress_panel, 1, wx.EXPAND | wx.ALL, 8)

        panel.SetSizer(main_sizer)

    # ──────────────────────────────────────────────
    # 이벤트 핸들러
    # ──────────────────────────────────────────────

    def _on_browse(self, event: wx.CommandEvent) -> None:
        """디렉토리 선택 다이얼로그를 열고 선택한 경로를 입력란에 채운다."""
        with wx.DirDialog(
            self,
            message="분석할 소스코드 폴더를 선택하세요",
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self._path_ctrl.SetValue(dlg.GetPath())

    def _on_start(self, event: wx.CommandEvent) -> None:
        """'분석 시작' — 처음부터 전체 파이프라인을 실행한다."""
        self._run(resume=False)

    def _on_resume(self, event: wx.CommandEvent) -> None:
        """'이어서 시작' — progress.json의 완료된 Phase를 건너뛰고 재개한다."""
        self._run(resume=True)

    # ──────────────────────────────────────────────
    # 파이프라인 실행
    # ──────────────────────────────────────────────

    def _run(self, resume: bool) -> None:
        """
        입력 값을 검증한 뒤 별도 스레드에서 파이프라인을 시작한다.

        Args:
            resume: True면 완료된 Phase 스킵
        """
        source_path = self._path_ctrl.GetValue().strip()
        api_key = self._api_ctrl.GetValue().strip()

        if not source_path:
            wx.MessageBox("소스코드 경로를 입력하세요.", "입력 오류", wx.OK | wx.ICON_WARNING)
            return
        if not api_key:
            wx.MessageBox("OpenAI API 키를 입력하세요.", "입력 오류", wx.OK | wx.ICON_WARNING)
            return
        if self._pipeline_thread and self._pipeline_thread.is_alive():
            wx.MessageBox("이미 분석이 진행 중입니다.", "경고", wx.OK | wx.ICON_WARNING)
            return

        self._progress_panel.reset()
        self._set_buttons_enabled(False)

        self._pipeline_thread = threading.Thread(
            target=self._run_pipeline,
            args=(source_path, api_key, resume),
            daemon=True,
        )
        self._pipeline_thread.start()

    def _run_pipeline(self, source_path: str, api_key: str, resume: bool) -> None:
        """
        백그라운드 스레드에서 PipelineOrchestrator를 실행한다.
        완료 또는 오류 발생 시 버튼 상태를 복원한다.
        """
        try:
            orchestrator = PipelineOrchestrator(
                source_path=source_path,
                api_key=api_key,
                callback=self._pipeline_callback,
            )
            orchestrator.run(resume=resume)
        except Exception as exc:
            # error 이벤트는 pipeline 내부에서 이미 callback으로 전달됨
            # 여기서는 버튼 복원만 처리
            _ = exc
        finally:
            wx.CallAfter(self._set_buttons_enabled, True)

    def _pipeline_callback(self, event: str, data: dict) -> None:
        """
        파이프라인 이벤트를 수신하여 wx.CallAfter로 UI 스레드에서 안전하게 업데이트한다.

        Args:
            event: EVT_* 상수 (예: "phase_start")
            data: 이벤트 데이터 딕셔너리
        """
        panel = self._progress_panel

        if event == EVT_PHASE_START:
            wx.CallAfter(
                panel.update_phase_start,
                data.get("phase", 0),
                data.get("name", ""),
            )
        elif event == EVT_PHASE_DONE:
            wx.CallAfter(panel.update_phase_done, data.get("phase", 0))
        elif event == EVT_CLASS_DONE:
            wx.CallAfter(
                panel.update_class_done,
                data.get("class", ""),
                data.get("index", 0),
                data.get("total", 1),
            )
        elif event == EVT_PIPELINE_DONE:
            wx.CallAfter(panel.update_pipeline_done)
        elif event == EVT_ERROR:
            wx.CallAfter(
                panel.update_error,
                data.get("message", "알 수 없는 오류"),
                data.get("phase"),
            )
        elif event == "log":
            wx.CallAfter(panel.append_log, f"  ℹ {data.get('message', '')}")

    # ──────────────────────────────────────────────
    # 내부 유틸
    # ──────────────────────────────────────────────

    def _set_buttons_enabled(self, enabled: bool) -> None:
        """
        분석 진행 중에는 버튼을 비활성화하고 완료 시 복원한다.

        Args:
            enabled: True면 버튼 활성화
        """
        self._start_btn.Enable(enabled)
        self._resume_btn.Enable(enabled)
