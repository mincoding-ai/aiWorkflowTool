"""
Session 5 코드 테스트: PipelineOrchestrator

전략:
- AIClient, FileScanner, ClassExtractor 등 외부 의존성 전부 Mock
- progress.json 로딩/저장, resume, 이벤트 콜백 순서에 집중
- 실제 파일 I/O는 tmp_path로 처리
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.class_extractor import ClassInfo
from src.core.pipeline import (
    PipelineOrchestrator,
    EVT_CLASS_DONE,
    EVT_ERROR,
    EVT_PHASE_DONE,
    EVT_PHASE_START,
    EVT_PIPELINE_DONE,
    _PHASE_ORDER,
)


# ──────────────────────────────────────────────
# Helpers / Fixtures
# ──────────────────────────────────────────────

def make_class(name: str, tmp_path: Path) -> ClassInfo:
    """테스트용 ClassInfo (소스파일 실제 생성)"""
    f = tmp_path / f"{name.lower()}.py"
    src = f"class {name}:\n    def run(self):\n        pass\n"
    f.write_text(src, encoding="utf-8")
    return ClassInfo(
        name=name,
        file_path=str(f),
        line_start=1,
        line_end=3,
        methods=["run"],
        base_classes=[],
        source_code=src,
    )


@pytest.fixture
def src_path(tmp_path):
    """빈 소스 디렉토리"""
    return tmp_path / "src"


@pytest.fixture
def orchestrator(src_path):
    """AIClient를 Mock으로 대체한 PipelineOrchestrator"""
    src_path.mkdir()
    (src_path / "dummy.py").write_text("x = 1\n", encoding="utf-8")

    with patch("src.core.pipeline.AIClient") as MockAI:
        instance = MockAI.return_value
        instance.generate_overview.return_value = ("PRD 내용", "DESIGN 내용")
        instance.analyze_class.return_value = ("class A:\n    pass\n", "A의 목적")
        instance.extract_semantic_nodes.return_value = []
        instance.extract_semantic_edges.return_value = []

        orch = PipelineOrchestrator(source_path=src_path, api_key="test-key")
        orch.ai = instance
        yield orch


# ──────────────────────────────────────────────
# progress.json 로딩 / 저장
# ──────────────────────────────────────────────

class TestProgressManagement:
    def test_progress_json_없으면_초기상태(self, src_path):
        src_path.mkdir(exist_ok=True)
        with patch("src.core.pipeline.AIClient"):
            orch = PipelineOrchestrator(source_path=src_path, api_key="key")
        for pid in _PHASE_ORDER:
            assert orch.progress["phases"][pid]["status"] == "pending"

    def test_progress_json_저장_후_로딩(self, src_path):
        src_path.mkdir(exist_ok=True)
        with patch("src.core.pipeline.AIClient"):
            orch = PipelineOrchestrator(source_path=src_path, api_key="key")

        orch.progress["phases"]["phase1"]["status"] = "completed"
        orch._save_progress()

        with patch("src.core.pipeline.AIClient"):
            orch2 = PipelineOrchestrator(source_path=src_path, api_key="key")
        assert orch2.progress["phases"]["phase1"]["status"] == "completed"

    def test_mark_phase_done(self, orchestrator):
        orchestrator._mark_phase_done("phase1")
        assert orchestrator.progress["phases"]["phase1"]["status"] == "completed"
        assert "completed_at" in orchestrator.progress["phases"]["phase1"]

    def test_손상된_progress_json_초기화(self, src_path):
        src_path.mkdir(exist_ok=True)
        ai_dir = src_path / "_ai_analysis"
        ai_dir.mkdir()
        (ai_dir / "progress.json").write_text("NOT JSON{{{", encoding="utf-8")

        with patch("src.core.pipeline.AIClient"):
            orch = PipelineOrchestrator(source_path=src_path, api_key="key")
        # 손상된 파일은 초기 상태로 대체
        assert orch.progress["phases"]["phase1"]["status"] == "pending"


# ──────────────────────────────────────────────
# 이벤트 콜백
# ──────────────────────────────────────────────

class TestEventCallback:
    def test_callback_없으면_오류_없음(self, src_path):
        src_path.mkdir(exist_ok=True)
        with patch("src.core.pipeline.AIClient"):
            orch = PipelineOrchestrator(source_path=src_path, api_key="key", callback=None)
        # callback=None이어도 _emit 호출 시 오류 없어야 함
        orch._emit(EVT_PHASE_START, {"phase": 1, "name": "test"})

    def test_phase_start_이벤트_전달(self, orchestrator):
        events = []
        orchestrator.callback = lambda e, d: events.append((e, d))
        orchestrator._emit(EVT_PHASE_START, {"phase": 1, "name": "테스트"})
        assert events[0] == (EVT_PHASE_START, {"phase": 1, "name": "테스트"})

    def test_pipeline_done_이벤트_전달(self, orchestrator):
        events = []
        orchestrator.callback = lambda e, d: events.append(e)

        # 모든 Phase를 완료로 표시한 뒤 run(resume=True)
        for pid in _PHASE_ORDER:
            orchestrator.progress["phases"][pid]["status"] = "completed"
        # phase4 completed_classes 설정
        orchestrator.progress["phases"]["phase4"]["completed_classes"] = []
        orchestrator.progress["phases"]["phase3"]["ordered_names"] = []
        orchestrator.progress["phases"]["phase2"]["classes"] = []

        orchestrator.run(resume=True)
        assert EVT_PIPELINE_DONE in events


# ──────────────────────────────────────────────
# resume 기능
# ──────────────────────────────────────────────

class TestResume:
    def test_완료된_phase_스킵(self, orchestrator):
        called = []
        orchestrator._run_phase1 = lambda: called.append("phase1")
        orchestrator._run_phase2 = lambda: called.append("phase2")
        orchestrator._run_phase3 = lambda: called.append("phase3")
        orchestrator._run_phase4 = lambda: called.append("phase4")
        orchestrator._run_phase5 = lambda: called.append("phase5")

        # phase1, phase2 완료로 표시
        orchestrator.progress["phases"]["phase1"]["status"] = "completed"
        orchestrator.progress["phases"]["phase2"]["status"] = "completed"

        orchestrator.run(resume=True)

        assert "phase1" not in called
        assert "phase2" not in called
        assert "phase3" in called
        assert "phase4" in called
        assert "phase5" in called

    def test_resume_false면_전체_실행(self, orchestrator):
        called = []
        for pid in _PHASE_ORDER:
            def make_fn(p):
                return lambda: called.append(p)
            setattr(orchestrator, f"_run_{pid}", make_fn(pid))
            orchestrator.progress["phases"][pid]["status"] = "completed"

        orchestrator.run(resume=False)
        assert called == _PHASE_ORDER


# ──────────────────────────────────────────────
# Phase 4: 클래스별 이어하기
# ──────────────────────────────────────────────

class TestPhase4Resume:
    def test_완료_클래스_스킵(self, orchestrator, tmp_path):
        cls_a = make_class("Alpha", tmp_path)
        cls_b = make_class("Beta", tmp_path)

        orchestrator.progress["phases"]["phase2"]["classes"] = [
            {"name": c.name, "file_path": c.file_path,
             "line_start": c.line_start, "line_end": c.line_end,
             "methods": c.methods, "base_classes": c.base_classes,
             "source_code": c.source_code}
            for c in [cls_a, cls_b]
        ]
        orchestrator.progress["phases"]["phase3"]["ordered_names"] = ["Alpha", "Beta"]
        # Alpha는 이미 완료
        orchestrator.progress["phases"]["phase4"]["completed_classes"] = ["Alpha"]

        processed = []
        def mock_analyze(src, prd, design):
            processed.append("called")
            return (src, "목적")

        orchestrator.ai.analyze_class = mock_analyze

        with patch("src.core.pipeline.CommentInjector") as MockInj:
            MockInj.return_value.inject.return_value = True
            orchestrator._read_output = lambda f: "내용"
            orchestrator._run_phase4()

        # Beta만 처리되어야 함 (Alpha는 스킵)
        assert len(processed) == 1

    def test_class_done_이벤트_발행(self, orchestrator, tmp_path):
        cls_a = make_class("Gamma", tmp_path)

        orchestrator.progress["phases"]["phase2"]["classes"] = [
            {"name": cls_a.name, "file_path": cls_a.file_path,
             "line_start": cls_a.line_start, "line_end": cls_a.line_end,
             "methods": cls_a.methods, "base_classes": cls_a.base_classes,
             "source_code": cls_a.source_code}
        ]
        orchestrator.progress["phases"]["phase3"]["ordered_names"] = ["Gamma"]
        orchestrator.progress["phases"]["phase4"]["completed_classes"] = []

        events = []
        orchestrator.callback = lambda e, d: events.append((e, d))
        orchestrator.ai.analyze_class = lambda src, p, d: (src, "목적")
        orchestrator._read_output = lambda f: "내용"

        with patch("src.core.pipeline.CommentInjector") as MockInj:
            MockInj.return_value.inject.return_value = True
            orchestrator._run_phase4()

        class_events = [d for e, d in events if e == EVT_CLASS_DONE]
        assert len(class_events) == 1
        assert class_events[0]["class"] == "Gamma"
        assert class_events[0]["total"] == 1


# ──────────────────────────────────────────────
# 오류 처리
# ──────────────────────────────────────────────

class TestErrorHandling:
    def test_phase_오류_시_error_이벤트_후_예외_전파(self, orchestrator):
        events = []
        orchestrator.callback = lambda e, d: events.append(e)
        orchestrator._run_phase1 = MagicMock(side_effect=RuntimeError("API 실패"))

        with pytest.raises(RuntimeError, match="API 실패"):
            orchestrator.run()

        assert EVT_ERROR in events
        assert EVT_PIPELINE_DONE not in events


# ──────────────────────────────────────────────
# Phase 5: GraphGenerator 미구현 시 경고
# ──────────────────────────────────────────────

class TestPhase5Stub:
    def test_graph_generator_없으면_경고_후_진행(self, orchestrator, tmp_path):
        orchestrator.progress["phases"]["phase2"]["classes"] = []
        orchestrator.progress["phases"]["phase3"]["ordered_names"] = []
        orchestrator._read_output = lambda f: "내용"

        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            orchestrator._run_phase5()

        # ImportError → 경고 발생 or graph.json 생성 둘 중 하나
        graph_path = orchestrator.output_dir / "graph.json"
        if not graph_path.exists():
            assert any("GraphGenerator" in str(warning.message) for warning in w)
