# Design Ref: §8 (PipelineOrchestrator) — 5단계 파이프라인 조율 + progress.json 이어하기 지원

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..ai.client import AIClient
from .class_extractor import ClassExtractor, ClassInfo
from .comment_injector import CommentInjector
from .dependency_analyzer import DependencyAnalyzer
from .file_scanner import FileScanner

# 이벤트 상수
EVT_PHASE_START = "phase_start"
EVT_PHASE_DONE = "phase_done"
EVT_CLASS_DONE = "class_done"
EVT_PIPELINE_DONE = "pipeline_done"
EVT_ERROR = "error"

_PHASE_NAMES = {
    "phase1": "전체 개요 분석 (PRD.md + DESIGN.md)",
    "phase2": "클래스 추출 (CLASS.md)",
    "phase3": "의존성 분석 (CLASS_ORDER.md)",
    "phase4": "주석 삽입",
    "phase5": "그래프 데이터 생성 (graph.json)",
}

_PHASE_ORDER = ["phase1", "phase2", "phase3", "phase4", "phase5"]

_INITIAL_PROGRESS = {
    "phases": {
        pid: {"status": "pending"}
        for pid in _PHASE_ORDER
    }
}


class PipelineOrchestrator:
    """
    소스코드 분석 5단계 파이프라인을 순차적으로 실행한다.
    progress.json으로 중단 지점을 저장하여 이어하기(resume)를 지원한다.
    각 단계 완료·오류 시 callback을 통해 UI에 이벤트를 전달한다.
    """

    def __init__(
        self,
        source_path: str | Path,
        api_key: str,
        callback: Callable[[str, dict], None] | None = None,
        model: str = AIClient.DEFAULT_MODEL,
    ) -> None:
        """
        Args:
            source_path: 분석할 소스코드 루트 경로
            api_key: OpenAI API 키
            callback: 이벤트 수신 함수 (event_name, data) 시그니처. None이면 무시.
            model: 사용할 OpenAI 모델명
        """
        self.source_path = Path(source_path)
        self.output_dir = self.source_path / "_ai_analysis"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.ai = AIClient(api_key=api_key, model=model)
        self.callback = callback

        self._progress_path = self.output_dir / "progress.json"
        self.progress = self._load_progress()

    # ──────────────────────────────────────────────
    # Public
    # ──────────────────────────────────────────────

    def run(self, resume: bool = False) -> None:
        """
        5단계 파이프라인을 실행한다.

        Args:
            resume: True면 이미 완료된 Phase를 건너뛴다.
        """
        phase_fns = {
            "phase1": self._run_phase1,
            "phase2": self._run_phase2,
            "phase3": self._run_phase3,
            "phase4": self._run_phase4,
            "phase5": self._run_phase5,
        }

        for phase_id in _PHASE_ORDER:
            if resume and self.progress["phases"][phase_id]["status"] == "completed":
                continue

            phase_num = int(phase_id[-1])
            self._emit(EVT_PHASE_START, {"phase": phase_num, "name": _PHASE_NAMES[phase_id]})

            try:
                phase_fns[phase_id]()
            except Exception as exc:
                self._emit(EVT_ERROR, {"phase": phase_num, "message": str(exc)})
                raise

            self._mark_phase_done(phase_id)
            self._emit(EVT_PHASE_DONE, {"phase": phase_num})

        self._emit(EVT_PIPELINE_DONE, {})

    # ──────────────────────────────────────────────
    # Phase 구현
    # ──────────────────────────────────────────────

    def _run_phase1(self) -> None:
        """전체 소스코드 탐색 → AI로 PRD.md + DESIGN.md 생성"""
        scanner = FileScanner()
        files = scanner.scan(self.source_path)

        if not files:
            raise RuntimeError(
                f"분석 대상 소스파일을 찾을 수 없습니다: {self.source_path}\n"
                "경로가 올바른지, .py/.java/.cpp/.c/.h 파일이 존재하는지 확인하세요."
            )

        self._emit("log", {"message": f"파일 {len(files)}개 스캔 완료: {', '.join(Path(p).name for p in list(files)[:5])}{'...' if len(files) > 5 else ''}"})

        combined = FileScanner.combine(files)
        self._emit("log", {"message": f"AI에 전달할 소스코드 크기: {len(combined):,} 문자"})

        prd_text, design_text = self.ai.generate_overview(combined)

        (self.output_dir / "PRD.md").write_text(prd_text, encoding="utf-8")
        (self.output_dir / "DESIGN.md").write_text(design_text, encoding="utf-8")

    def _run_phase2(self) -> None:
        """클래스 추출 → CLASS.md 생성"""
        extractor = ClassExtractor()
        classes = extractor.extract(self.source_path)

        lines = ["# CLASS.md\n"]
        for cls in classes:
            methods_str = ", ".join(cls.methods) if cls.methods else "없음"
            bases_str = ", ".join(cls.base_classes) if cls.base_classes else "-"
            rel_path = Path(cls.file_path).relative_to(self.source_path)
            lines.append(f"## {cls.name} ({rel_path}:{cls.line_start})")
            lines.append(f"- 메서드: {methods_str}")
            lines.append(f"- 기반 클래스: {bases_str}\n")

        (self.output_dir / "CLASS.md").write_text("\n".join(lines), encoding="utf-8")

        # Phase 4에서 재사용할 수 있도록 progress에 클래스 목록 저장
        self.progress["phases"]["phase2"]["classes"] = [
            {
                "name": c.name,
                "file_path": c.file_path,
                "line_start": c.line_start,
                "line_end": c.line_end,
                "methods": c.methods,
                "base_classes": c.base_classes,
                "source_code": c.source_code,
            }
            for c in classes
        ]
        self._save_progress()

    def _run_phase3(self) -> None:
        """의존성 분석 + 위상 정렬 → CLASS_ORDER.md 생성"""
        classes = self._load_classes_from_progress()
        analyzer = DependencyAnalyzer()
        graph = analyzer.build_graph(classes)
        ordered = analyzer.sort(classes)
        missing = analyzer.verify(classes, ordered)
        if missing:
            warnings.warn(
                f"[Pipeline] CLASS.md에서 누락된 클래스: {missing}", stacklevel=2
            )

        lines = [
            "# CLASS_ORDER.md",
            "# 분석 순서: 단순(의존성 없음) → 복잡(다수 의존)\n",
        ]
        for i, cls in enumerate(ordered, 1):
            deps = graph.get(cls.name, [])
            dep_str = ", ".join(deps) if deps else "없음"
            lines.append(f"{i}. {cls.name}  (의존: {dep_str})")

        (self.output_dir / "CLASS_ORDER.md").write_text("\n".join(lines), encoding="utf-8")

        # 정렬된 순서를 progress에 저장 (Phase 4에서 순서 참조)
        self.progress["phases"]["phase3"]["ordered_names"] = [c.name for c in ordered]
        self._save_progress()

    def _run_phase4(self) -> None:
        """클래스별 주석 삽입 + analysis.md 기록 (이어하기 지원)"""
        classes_by_name = {c.name: c for c in self._load_classes_from_progress()}
        ordered_names: list[str] = self.progress["phases"]["phase3"].get(
            "ordered_names", list(classes_by_name.keys())
        )

        phase4 = self.progress["phases"]["phase4"]
        completed: list[str] = phase4.get("completed_classes", [])
        total = len(ordered_names)
        phase4["total_classes"] = total
        phase4["status"] = "in_progress"
        self._save_progress()

        prd_content = self._read_output("PRD.md")
        design_content = self._read_output("DESIGN.md")
        injector = CommentInjector()
        analysis_lines: list[str] = self._load_existing_analysis()

        for idx, class_name in enumerate(ordered_names, 1):
            if class_name in completed:
                continue

            cls = classes_by_name.get(class_name)
            if cls is None:
                continue

            commented_src, purpose = self.ai.analyze_class(
                cls.source_code, prd_content, design_content
            )
            injector.inject(cls, commented_src)

            analysis_lines.append(f"{class_name} : {purpose}")
            (self.output_dir / "analysis.md").write_text(
                "\n".join(["# analysis.md", ""] + analysis_lines),
                encoding="utf-8",
            )

            completed.append(class_name)
            phase4["completed_classes"] = completed
            self._save_progress()

            self._emit(EVT_CLASS_DONE, {"class": class_name, "index": idx, "total": total})

    def _run_phase5(self) -> None:
        """그래프 데이터 생성 → graph.json (GraphGenerator는 Session 6에서 구현)"""
        # Plan SC: graph.json 생성 (Session 6 구현 후 연결)
        try:
            from ..graph.graph_generator import GraphGenerator  # noqa: F401

            analysis_content = self._read_output("analysis.md")
            design_content = self._read_output("DESIGN.md")
            classes = self._load_classes_from_progress()
            analyzer = DependencyAnalyzer()
            dep_graph = analyzer.build_graph(classes)

            gen = GraphGenerator(self.ai)
            graph_data = gen.generate(analysis_content, design_content, dep_graph)
            (self.output_dir / "graph.json").write_text(
                json.dumps(graph_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except ImportError:
            warnings.warn(
                "[Pipeline] GraphGenerator 미구현 — Phase 5 건너뜀 (Session 6 구현 후 활성화)",
                stacklevel=2,
            )

    # ──────────────────────────────────────────────
    # Progress 관리
    # ──────────────────────────────────────────────

    def _load_progress(self) -> dict:
        """
        progress.json을 읽어 반환한다. 파일이 없으면 초기 상태를 반환한다.
        """
        if self._progress_path.exists():
            try:
                return json.loads(self._progress_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        import copy
        return copy.deepcopy(_INITIAL_PROGRESS)

    def _save_progress(self) -> None:
        """현재 progress 상태를 progress.json에 저장한다."""
        self._progress_path.write_text(
            json.dumps(self.progress, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _mark_phase_done(self, phase_id: str) -> None:
        """
        지정된 Phase를 완료 상태로 기록하고 저장한다.

        Args:
            phase_id: "phase1" ~ "phase5"
        """
        self.progress["phases"][phase_id]["status"] = "completed"
        self.progress["phases"][phase_id]["completed_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        self._save_progress()

    # ──────────────────────────────────────────────
    # 내부 유틸
    # ──────────────────────────────────────────────

    def _emit(self, event: str, data: dict) -> None:
        """
        UI 콜백에 이벤트를 전달한다. callback이 None이면 무시한다.

        Args:
            event: 이벤트 이름 (EVT_* 상수)
            data: 이벤트 데이터 딕셔너리
        """
        if self.callback is not None:
            self.callback(event, data)

    def _read_output(self, filename: str) -> str:
        """
        output_dir 내 파일을 읽어 반환한다. 없으면 빈 문자열.

        Args:
            filename: 파일명 (예: "PRD.md")
        """
        path = self.output_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _load_classes_from_progress(self) -> list[ClassInfo]:
        """
        phase2 progress에 저장된 ClassInfo 직렬화 데이터를 복원한다.
        저장된 데이터가 없으면 ClassExtractor로 재추출한다.
        """
        raw = self.progress["phases"].get("phase2", {}).get("classes")
        if raw:
            return [
                ClassInfo(
                    name=c["name"],
                    file_path=c["file_path"],
                    line_start=c["line_start"],
                    line_end=c["line_end"],
                    methods=c["methods"],
                    base_classes=c["base_classes"],
                    source_code=c["source_code"],
                )
                for c in raw
            ]
        return ClassExtractor().extract(self.source_path)

    def _load_existing_analysis(self) -> list[str]:
        """
        기존 analysis.md에서 이미 기록된 항목을 읽어 반환한다.
        Phase 4 이어하기 시 중복 기록 방지 목적.
        """
        content = self._read_output("analysis.md")
        if not content:
            return []
        # "# analysis.md" 헤더와 빈 줄을 제외한 실제 항목만
        return [
            line for line in content.splitlines()
            if line and not line.startswith("#")
        ]
