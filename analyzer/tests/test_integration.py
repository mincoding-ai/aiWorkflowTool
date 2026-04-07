"""
Session 8 통합 테스트: PipelineOrchestrator 전체 흐름

전략:
- tmp_path에 실제 Python 샘플 프로젝트 생성 (두 클래스, 의존성 있음)
- AIClient만 Mock으로 대체 → 실제 FileScanner/ClassExtractor/DependencyAnalyzer/
  CommentInjector/GraphGenerator 모두 실제 실행
- 산출물 파일 존재 + 기본 내용 검증
- 이어하기(resume) 시나리오 검증
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.pipeline import PipelineOrchestrator, EVT_PIPELINE_DONE, _PHASE_ORDER


# ──────────────────────────────────────────────
# 샘플 프로젝트 생성 헬퍼
# ──────────────────────────────────────────────

def create_sample_project(base: Path) -> Path:
    """
    두 클래스(Logger, Engine)가 있는 최소 Python 프로젝트를 생성한다.
    Engine이 Logger를 사용하는 의존성을 갖는다.
    """
    src = base / "sample_project"
    src.mkdir()

    (src / "logger.py").write_text(
        "class Logger:\n"
        "    def log(self, msg):\n"
        "        print(msg)\n",
        encoding="utf-8",
    )

    (src / "engine.py").write_text(
        "from logger import Logger\n\n"
        "class Engine:\n"
        "    def __init__(self):\n"
        "        self.logger = Logger()\n"
        "    def run(self):\n"
        "        self.logger.log('running')\n",
        encoding="utf-8",
    )

    return src


def make_mock_ai():
    """AIClient Mock — 파이프라인이 필요한 모든 메서드에 stub 응답 제공"""
    ai = MagicMock()
    ai.generate_overview.return_value = (
        "# PRD\n이 프로젝트는 샘플입니다.",
        "# DESIGN\n로거와 엔진으로 구성됩니다.",
    )
    ai.analyze_class.side_effect = lambda src, prd, design: (src, "테스트 클래스 목적")
    ai.extract_semantic_nodes.return_value = [
        {"id": "Logger", "label": "로거", "purpose": "로깅 담당"},
        {"id": "Engine", "label": "엔진", "purpose": "실행 담당"},
    ]
    ai.extract_semantic_edges.return_value = [
        {"source": "Engine", "target": "Logger", "relation": "로깅에 사용"}
    ]
    return ai


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def sample_src(tmp_path):
    return create_sample_project(tmp_path)


@pytest.fixture
def orchestrator(sample_src):
    with patch("src.core.pipeline.AIClient") as MockAI:
        MockAI.return_value = make_mock_ai()
        orch = PipelineOrchestrator(source_path=sample_src, api_key="test-key")
        orch.ai = MockAI.return_value
        yield orch


# ──────────────────────────────────────────────
# 전체 파이프라인 실행 — 산출물 검증
# ──────────────────────────────────────────────

class TestFullPipelineRun:
    def test_PRD_생성(self, orchestrator):
        orchestrator.run()
        prd = orchestrator.output_dir / "PRD.md"
        assert prd.exists()
        assert "PRD" in prd.read_text(encoding="utf-8")

    def test_DESIGN_생성(self, orchestrator):
        orchestrator.run()
        design = orchestrator.output_dir / "DESIGN.md"
        assert design.exists()
        assert "DESIGN" in design.read_text(encoding="utf-8")

    def test_CLASS_md_생성(self, orchestrator):
        orchestrator.run()
        class_md = orchestrator.output_dir / "CLASS.md"
        assert class_md.exists()
        content = class_md.read_text(encoding="utf-8")
        assert "Logger" in content
        assert "Engine" in content

    def test_CLASS_ORDER_md_생성(self, orchestrator):
        orchestrator.run()
        order_md = orchestrator.output_dir / "CLASS_ORDER.md"
        assert order_md.exists()
        content = order_md.read_text(encoding="utf-8")
        # Logger (의존 없음)가 Engine보다 먼저 나와야 함
        logger_pos = content.find("Logger")
        engine_pos = content.find("Engine")
        assert logger_pos < engine_pos

    def test_analysis_md_생성(self, orchestrator):
        orchestrator.run()
        analysis = orchestrator.output_dir / "analysis.md"
        assert analysis.exists()
        content = analysis.read_text(encoding="utf-8")
        assert "Logger" in content
        assert "Engine" in content

    def test_graph_json_생성(self, orchestrator):
        orchestrator.run()
        graph = orchestrator.output_dir / "graph.json"
        assert graph.exists()
        data = json.loads(graph.read_text(encoding="utf-8"))
        assert "nodes" in data
        assert "edges" in data
        assert "generated_at" in data

    def test_graph_json_nodes_내용(self, orchestrator):
        orchestrator.run()
        data = json.loads((orchestrator.output_dir / "graph.json").read_text(encoding="utf-8"))
        node_ids = [n["id"] for n in data["nodes"]]
        assert "Logger" in node_ids
        assert "Engine" in node_ids

    def test_graph_json_edges_내용(self, orchestrator):
        orchestrator.run()
        data = json.loads((orchestrator.output_dir / "graph.json").read_text(encoding="utf-8"))
        assert len(data["edges"]) >= 1
        assert data["edges"][0]["source"] == "Engine"
        assert data["edges"][0]["target"] == "Logger"

    def test_progress_json_모든_phase_완료(self, orchestrator):
        orchestrator.run()
        progress = json.loads(
            (orchestrator.output_dir / "progress.json").read_text(encoding="utf-8")
        )
        for pid in _PHASE_ORDER:
            assert progress["phases"][pid]["status"] == "completed"

    def test_pipeline_done_이벤트_발행(self, orchestrator):
        events = []
        orchestrator.callback = lambda e, d: events.append(e)
        orchestrator.run()
        assert EVT_PIPELINE_DONE in events

    def test_bak_파일_생성(self, orchestrator, sample_src):
        """주석 삽입 후 원본 .bak 백업 파일이 생성되어야 한다"""
        orchestrator.run()
        bak_files = list(sample_src.glob("**/*.bak"))
        assert len(bak_files) > 0


# ──────────────────────────────────────────────
# 이어하기(resume) 시나리오
# ──────────────────────────────────────────────

class TestResumeScenario:
    def test_resume_phase1_2_완료_후_재개(self, sample_src):
        """Phase 1~2가 완료된 상태에서 resume=True로 재개하면 Phase 3~5만 실행된다"""
        called = []

        with patch("src.core.pipeline.AIClient") as MockAI:
            MockAI.return_value = make_mock_ai()
            orch = PipelineOrchestrator(source_path=sample_src, api_key="key")
            orch.ai = MockAI.return_value

            # Phase 1~2 완료로 표시
            orch.progress["phases"]["phase1"]["status"] = "completed"
            orch.progress["phases"]["phase2"]["status"] = "completed"
            # Phase 2 데이터 저장 (Phase 3이 참조)
            from src.core.class_extractor import ClassExtractor
            classes = ClassExtractor().extract(sample_src)
            orch.progress["phases"]["phase2"]["classes"] = [
                {
                    "name": c.name, "file_path": c.file_path,
                    "line_start": c.line_start, "line_end": c.line_end,
                    "methods": c.methods, "base_classes": c.base_classes,
                    "source_code": c.source_code,
                }
                for c in classes
            ]
            orch._save_progress()

            orig_phase1 = orch._run_phase1
            orig_phase2 = orch._run_phase2
            orch._run_phase1 = lambda: called.append("phase1")
            orch._run_phase2 = lambda: called.append("phase2")

            orch.run(resume=True)

        assert "phase1" not in called
        assert "phase2" not in called
        # Phase 3~5는 실행됨 (산출물로 확인)
        assert (orch.output_dir / "CLASS_ORDER.md").exists()
        assert (orch.output_dir / "analysis.md").exists()

    def test_완전한_resume_모든_phase_완료(self, orchestrator):
        """모든 Phase가 완료 상태일 때 resume=True면 즉시 pipeline_done 발행"""
        events = []
        orchestrator.callback = lambda e, d: events.append(e)

        for pid in _PHASE_ORDER:
            orchestrator.progress["phases"][pid]["status"] = "completed"
        orchestrator.progress["phases"]["phase4"]["completed_classes"] = []
        orchestrator.progress["phases"]["phase3"]["ordered_names"] = []
        orchestrator.progress["phases"]["phase2"]["classes"] = []

        orchestrator.run(resume=True)
        assert EVT_PIPELINE_DONE in events


# ──────────────────────────────────────────────
# 오류 전파
# ──────────────────────────────────────────────

class TestErrorPropagation:
    def test_phase1_오류_시_예외_전파(self, orchestrator):
        orchestrator._run_phase1 = MagicMock(side_effect=RuntimeError("API 실패"))
        with pytest.raises(RuntimeError, match="API 실패"):
            orchestrator.run()

    def test_오류_후_progress_json_갱신_안됨(self, orchestrator):
        """오류 발생 시 phase1은 completed가 아니어야 한다"""
        orchestrator._run_phase1 = MagicMock(side_effect=RuntimeError("실패"))
        try:
            orchestrator.run()
        except RuntimeError:
            pass
        assert orchestrator.progress["phases"]["phase1"]["status"] != "completed"
