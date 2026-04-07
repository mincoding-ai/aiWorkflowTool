# Design Ref: §5 Phase 3 — 클래스 의존성 분석 + 위상 정렬 (단순 → 복잡 순서 결정)

import ast
import warnings
from collections import deque

from .class_extractor import ClassInfo


class DependencyAnalyzer:
    """
    ClassInfo 목록을 받아 클래스 간 의존성 그래프를 구성하고
    Kahn's algorithm(위상 정렬)으로 단순 → 복잡 순서를 결정한다.
    순환 의존성이 있으면 경고 후 남은 클래스를 임의 순서로 추가한다.
    """

    def build_graph(
        self, classes: list[ClassInfo]
    ) -> dict[str, list[str]]:
        """
        각 ClassInfo의 소스코드를 분석하여 의존성 그래프를 생성한다.

        의존성 정의:
          클래스 A의 소스코드에 클래스 B의 이름이 ast.Name / ast.Attribute로
          등장하면 A는 B에 의존한다고 판단한다.
          (단, 기반 클래스 선언 자체는 제외하지 않고 포함한다.)

        Args:
            classes: ClassExtractor.extract() 결과

        Returns:
            {"ClassA": ["ClassB", "ClassC"], ...} 형태의 딕셔너리.
            값은 A가 의존하는 클래스명 목록 (중복 제거).
        """
        known = {cls.name for cls in classes}
        graph: dict[str, list[str]] = {cls.name: [] for cls in classes}

        for cls in classes:
            refs = self._find_references(cls.source_code, known - {cls.name})
            graph[cls.name] = sorted(refs)  # 결정론적 순서

        return graph

    def sort(self, classes: list[ClassInfo]) -> list[ClassInfo]:
        """
        위상 정렬(Kahn's algorithm)로 ClassInfo 목록을 단순 → 복잡 순서로 정렬한다.

        Args:
            classes: ClassExtractor.extract() 결과

        Returns:
            정렬된 ClassInfo 목록.
            순환 의존성이 있으면 경고 후 남은 클래스를 뒤에 추가한다.
        """
        graph = self.build_graph(classes)
        name_to_info = {cls.name: cls for cls in classes}

        # 역방향 인접 리스트 구성: reverse[B] = [A] → "A는 B에 의존, 즉 B→A 순서"
        # in_degree[A] = A가 기다려야 할 의존 클래스 수 (= A의 의존성 수)
        reverse: dict[str, list[str]] = {name: [] for name in graph}
        in_degree: dict[str, int] = {name: 0 for name in graph}

        for name, deps in graph.items():
            for dep in deps:
                if dep in reverse:
                    reverse[dep].append(name)   # dep 완료 후 name 처리 가능
                    in_degree[name] += 1        # name이 기다려야 할 의존 +1

        # 의존성이 없는 클래스(in_degree 0)부터 큐에 삽입 → 가장 단순한 클래스
        queue: deque[str] = deque(
            sorted(name for name, deg in in_degree.items() if deg == 0)
        )
        ordered: list[ClassInfo] = []

        while queue:
            name = queue.popleft()
            ordered.append(name_to_info[name])

            # 이 클래스를 기다리던(의존하던) 클래스들의 in_degree 감소
            for dependent in sorted(reverse[name]):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # 순환 의존성으로 정렬에서 빠진 클래스 처리
        remaining = [
            name_to_info[name]
            for name in graph
            if name_to_info[name] not in ordered
        ]
        if remaining:
            cycle_names = [cls.name for cls in remaining]
            warnings.warn(
                f"[DependencyAnalyzer] 순환 의존성 감지 — 임의 순서로 추가: {cycle_names}",
                stacklevel=2,
            )
            ordered.extend(remaining)

        return ordered

    def verify(
        self,
        original: list[ClassInfo],
        ordered: list[ClassInfo],
    ) -> list[str]:
        """
        원본 클래스 목록과 정렬된 목록이 동일한 클래스를 포함하는지 검증한다.

        Args:
            original: ClassExtractor.extract() 원본 목록
            ordered: sort() 결과

        Returns:
            누락된 클래스명 목록. 비어있으면 검증 성공.
        """
        original_names = {cls.name for cls in original}
        ordered_names = {cls.name for cls in ordered}
        missing = sorted(original_names - ordered_names)
        return missing

    # ──────────────────────────────────────────────
    # Private
    # ──────────────────────────────────────────────

    def _find_references(
        self, source_code: str, known_classes: set[str]
    ) -> set[str]:
        """
        단일 클래스 소스코드에서 알려진 클래스명이 참조되는지 탐색한다.

        Python: AST 기반 (ast.Name / ast.Attribute).
        Java/C++: 정규식 기반 단어 경계 매칭 (AST 파싱 불가 시 폴백).

        Args:
            source_code: 클래스 전체 소스코드 문자열
            known_classes: 참조 여부를 확인할 클래스명 집합

        Returns:
            source_code 내에서 참조된 known_classes 원소 집합
        """
        if not source_code.strip() or not known_classes:
            return set()

        # Python AST 시도
        try:
            tree = ast.parse(source_code)
            found: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id in known_classes:
                    found.add(node.id)
                elif isinstance(node, ast.Attribute) and node.attr in known_classes:
                    found.add(node.attr)
            return found
        except SyntaxError:
            pass

        # Java/C++ 폴백: 단어 경계 정규식 매칭
        import re
        found = set()
        for cls_name in known_classes:
            if re.search(r"\b" + re.escape(cls_name) + r"\b", source_code):
                found.add(cls_name)
        return found
