# Design Ref: §7 (AI Client 설계) — OpenAI GPT-4 API 래퍼. 재시도·토큰 관리 담당.

import json
import time
from typing import Any

from openai import OpenAI, RateLimitError, APIStatusError

from .prompts import (
    PROMPT_OVERVIEW,
    PROMPT_COMMENT,
    PROMPT_GRAPH_NODES,
    PROMPT_GRAPH_EDGES,
)


class AIClient:
    """
    OpenAI GPT-4 API 호출을 담당하는 클라이언트.
    각 파이프라인 Phase에 대응하는 메서드를 제공하며,
    API 오류 시 지수 백오프로 최대 3회 재시도한다.
    """

    DEFAULT_MODEL = "gpt-4o"
    MAX_RETRIES = 3
    BASE_DELAY = 2.0  # 초 단위 기본 대기 시간

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        """
        Args:
            api_key: OpenAI API 키
            model: 사용할 모델명 (기본값: gpt-4o)
        """
        self._client = OpenAI(api_key=api_key)
        self.model = model

    # ──────────────────────────────────────────────
    # Public: Phase별 API 메서드
    # ──────────────────────────────────────────────

    def generate_overview(self, file_contents: str) -> tuple[str, str]:
        """
        전체 소스코드를 받아 PRD.md와 DESIGN.md 텍스트를 생성한다 (Phase 1).

        Args:
            file_contents: 전체 소스파일 내용을 합친 문자열

        Returns:
            (prd_text, design_text) 튜플
        """
        prompt = PROMPT_OVERVIEW.format(file_contents=file_contents)
        response = self._call(prompt, max_tokens=4096)
        return self._parse_overview(response)

    def analyze_class(
        self,
        class_source: str,
        prd_content: str,
        design_content: str,
    ) -> tuple[str, str]:
        """
        단일 클래스 소스코드에 한글 주석을 삽입하고 클래스 목적 한 줄을 반환한다 (Phase 4).

        Args:
            class_source: 주석을 달 클래스의 원본 소스코드
            prd_content: PRD.md 전문 (문맥 참조용)
            design_content: DESIGN.md 전문 (문맥 참조용)

        Returns:
            (commented_source, purpose_one_line) 튜플
        """
        prompt = PROMPT_COMMENT.format(
            prd_content=prd_content,
            design_content=design_content,
            class_source=class_source,
        )
        response = self._call(prompt, max_tokens=4096)
        return self._parse_comment_response(response)

    def extract_semantic_nodes(
        self, analysis_content: str, design_content: str
    ) -> list[dict[str, str]]:
        """
        analysis.md와 DESIGN.md를 기반으로 의미론적 핵심 Node 목록을 추출한다 (Phase 5).

        Args:
            analysis_content: analysis.md 전문
            design_content: DESIGN.md 전문

        Returns:
            [{"id": ..., "label": ..., "purpose": ...}] 형태의 리스트
        """
        prompt = PROMPT_GRAPH_NODES.format(
            analysis_content=analysis_content,
            design_content=design_content,
        )
        response = self._call(prompt, max_tokens=2048)
        return self._parse_json_response(response)

    def extract_semantic_edges(
        self,
        nodes: list[dict[str, str]],
        dependency_graph: dict[str, list[str]],
    ) -> list[dict[str, str]]:
        """
        Node 목록과 의존성 그래프를 기반으로 의미적 Edge를 추출한다 (Phase 5).

        Args:
            nodes: extract_semantic_nodes() 반환값
            dependency_graph: {"ClassA": ["ClassB", "ClassC"]} 형태의 의존성 딕셔너리

        Returns:
            [{"source": ..., "target": ..., "relation": ...}] 형태의 리스트
        """
        prompt = PROMPT_GRAPH_EDGES.format(
            nodes_json=json.dumps(nodes, ensure_ascii=False, indent=2),
            dependency_graph=json.dumps(dependency_graph, ensure_ascii=False, indent=2),
        )
        response = self._call(prompt, max_tokens=2048)
        return self._parse_json_response(response)

    # ──────────────────────────────────────────────
    # Private: API 호출 + 파싱
    # ──────────────────────────────────────────────

    def _call(self, prompt: str, max_tokens: int = 4096) -> str:
        """
        OpenAI Chat Completions API를 호출한다.
        429(Rate Limit) 또는 5xx 오류 시 지수 백오프로 최대 3회 재시도한다.

        Args:
            prompt: 사용자 메시지 텍스트
            max_tokens: 응답 최대 토큰 수

        Returns:
            API 응답 텍스트

        Raises:
            RuntimeError: 최대 재시도 횟수 초과 시
        """
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""

            except RateLimitError as e:
                last_error = e
                # 지수 백오프: 2초 → 4초 → 8초
                wait = self.BASE_DELAY * (2 ** attempt)
                time.sleep(wait)

            except APIStatusError as e:
                if e.status_code >= 500:
                    last_error = e
                    wait = self.BASE_DELAY * (2 ** attempt)
                    time.sleep(wait)
                else:
                    # 4xx(인증 실패 등)는 재시도 불필요
                    raise

        raise RuntimeError(
            f"OpenAI API 호출 실패 ({self.MAX_RETRIES}회 재시도): {last_error}"
        )

    def _parse_overview(self, response: str) -> tuple[str, str]:
        """
        generate_overview() 응답에서 PRD.md와 DESIGN.md 텍스트를 분리한다.

        Args:
            response: API 응답 전문

        Returns:
            (prd_text, design_text) 튜플. 파싱 실패 시 빈 문자열 반환.
        """
        prd_text = ""
        design_text = ""

        # "### PRD.md" ~ "### DESIGN.md" 구간 추출
        if "### PRD.md" in response and "### DESIGN.md" in response:
            parts = response.split("### DESIGN.md", 1)
            prd_text = parts[0].replace("### PRD.md", "").strip()
            design_text = parts[1].strip()
        elif "### PRD.md" in response:
            prd_text = response.replace("### PRD.md", "").strip()
        else:
            # 구분자 없이 전체가 반환된 경우 전체를 PRD로 취급
            prd_text = response.strip()

        return prd_text, design_text

    def _parse_comment_response(self, response: str) -> tuple[str, str]:
        """
        analyze_class() 응답에서 주석 달린 코드와 목적 한 줄을 분리한다.

        Args:
            response: API 응답 전문

        Returns:
            (commented_source, purpose_one_line) 튜플
        """
        lines = response.strip().splitlines()

        # 마지막 비어있지 않은 줄을 목적 한 줄로 간주
        # 코드 블록(```)을 기준으로 분리 시도
        if "```" in response:
            # 코드 블록 내부 추출
            inside = response.split("```")
            # 홀수 인덱스가 코드 블록 내용
            code_blocks = [inside[i] for i in range(1, len(inside), 2)]
            commented_source = code_blocks[0].lstrip("python").strip() if code_blocks else ""
            # 코드 블록 이후 텍스트에서 목적 추출
            after_code = inside[-1].strip() if len(inside) % 2 == 0 else inside[-1].strip()
            purpose = after_code.splitlines()[0].strip() if after_code else ""
        else:
            # 코드 블록 없는 경우: 마지막 줄이 목적, 나머지가 코드
            purpose = lines[-1].strip() if lines else ""
            commented_source = "\n".join(lines[:-1]).strip()

        return commented_source, purpose

    def _parse_json_response(self, response: str) -> list[dict[str, Any]]:
        """
        JSON 배열을 포함한 응답을 파싱한다.

        Args:
            response: JSON 배열이 포함된 API 응답

        Returns:
            파싱된 리스트. 파싱 실패 시 빈 리스트 반환.
        """
        # 코드 블록 제거 후 JSON 파싱
        text = response.strip()
        if "```" in text:
            parts = text.split("```")
            text = parts[1].lstrip("json").strip() if len(parts) > 1 else text

        # "[" 시작 위치부터 추출
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            return []

        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return []
