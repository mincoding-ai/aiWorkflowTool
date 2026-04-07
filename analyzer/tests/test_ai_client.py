"""
Session 1 코드 테스트: AIClient

테스트 전략:
- OpenAI API는 Mock으로 대체 (실제 API 호출 없음)
- _call() 재시도 로직, 파싱 메서드를 집중 검증
- 실제 API 연동은 인간 테스트로 별도 진행
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai.client import AIClient


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def client():
    """테스트용 AIClient (실제 API 호출 없음)"""
    return AIClient(api_key="test-key", model="gpt-4o")


def make_mock_response(content: str):
    """openai 응답 Mock 객체 생성"""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    return mock_resp


# ──────────────────────────────────────────────
# _call() 테스트
# ──────────────────────────────────────────────

class TestCall:
    def test_성공_시_응답_텍스트_반환(self, client):
        """정상 응답이면 content 문자열을 반환해야 한다"""
        mock_resp = make_mock_response("hello world")
        with patch.object(client._client.chat.completions, "create", return_value=mock_resp):
            result = client._call("test prompt")
        assert result == "hello world"

    def test_rate_limit_재시도_3회_후_실패(self, client):
        """RateLimitError가 3회 연속 발생하면 RuntimeError를 발생시켜야 한다"""
        from openai import RateLimitError

        # RateLimitError 생성 (openai SDK 방식)
        mock_response = MagicMock()
        mock_response.status_code = 429
        error = RateLimitError("rate limit", response=mock_response, body={})

        with patch.object(client._client.chat.completions, "create", side_effect=error):
            with patch("time.sleep"):  # sleep 스킵
                with pytest.raises(RuntimeError, match="3회 재시도"):
                    client._call("test")

    def test_rate_limit_후_성공(self, client):
        """RateLimitError 이후 재시도에서 성공하면 정상 반환해야 한다"""
        from openai import RateLimitError

        mock_response = MagicMock()
        mock_response.status_code = 429
        rate_error = RateLimitError("rate limit", response=mock_response, body={})

        success_resp = make_mock_response("retry success")

        with patch.object(
            client._client.chat.completions,
            "create",
            side_effect=[rate_error, success_resp],
        ):
            with patch("time.sleep"):
                result = client._call("test")

        assert result == "retry success"

    def test_4xx_오류는_재시도_없이_즉시_raise(self, client):
        """인증 오류(401) 등 4xx는 재시도 없이 바로 raise해야 한다"""
        from openai import APIStatusError

        mock_response = MagicMock()
        mock_response.status_code = 401
        error = APIStatusError("unauthorized", response=mock_response, body={})

        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise error

        with patch.object(client._client.chat.completions, "create", side_effect=side_effect):
            with pytest.raises(APIStatusError):
                client._call("test")

        assert call_count == 1  # 재시도 없이 1회만 호출


# ──────────────────────────────────────────────
# _parse_overview() 테스트
# ──────────────────────────────────────────────

class TestParseOverview:
    def test_정상_구분자_있는_경우(self, client):
        response = "### PRD.md\nPRD 내용\n\n### DESIGN.md\nDESIGN 내용"
        prd, design = client._parse_overview(response)
        assert "PRD 내용" in prd
        assert "DESIGN 내용" in design

    def test_DESIGN_md_없는_경우_PRD만_반환(self, client):
        response = "### PRD.md\nPRD만 있음"
        prd, design = client._parse_overview(response)
        assert "PRD만 있음" in prd
        assert design == ""

    def test_구분자_없는_경우_전체를_PRD로(self, client):
        response = "그냥 텍스트"
        prd, design = client._parse_overview(response)
        assert prd == "그냥 텍스트"
        assert design == ""


# ──────────────────────────────────────────────
# _parse_comment_response() 테스트
# ──────────────────────────────────────────────

class TestParseCommentResponse:
    def test_코드블록_있는_경우(self, client):
        response = "```python\nclass Foo:\n    pass\n```\n데이터 처리 클래스"
        code, purpose = client._parse_comment_response(response)
        assert "class Foo" in code
        assert "데이터 처리 클래스" in purpose

    def test_코드블록_없는_경우_마지막_줄이_목적(self, client):
        response = "class Foo:\n    pass\n데이터 처리 클래스"
        code, purpose = client._parse_comment_response(response)
        assert "class Foo" in code
        assert purpose == "데이터 처리 클래스"


# ──────────────────────────────────────────────
# _parse_json_response() 테스트
# ──────────────────────────────────────────────

class TestParseJsonResponse:
    def test_정상_JSON_파싱(self, client):
        response = '[{"id": "Foo", "label": "푸", "purpose": "테스트"}]'
        result = client._parse_json_response(response)
        assert len(result) == 1
        assert result[0]["id"] == "Foo"

    def test_코드블록_감싸인_JSON(self, client):
        response = "```json\n[{\"id\": \"Bar\"}]\n```"
        result = client._parse_json_response(response)
        assert result[0]["id"] == "Bar"

    def test_JSON_없으면_빈_리스트(self, client):
        result = client._parse_json_response("JSON이 없는 텍스트")
        assert result == []

    def test_잘못된_JSON이면_빈_리스트(self, client):
        result = client._parse_json_response("[{broken json")
        assert result == []


# ──────────────────────────────────────────────
# generate_overview() 통합 테스트 (mock)
# ──────────────────────────────────────────────

class TestGenerateOverview:
    def test_PRD와_DESIGN_텍스트_반환(self, client):
        mock_resp = make_mock_response(
            "### PRD.md\n요구사항 내용\n\n### DESIGN.md\n아키텍처 내용"
        )
        with patch.object(client._client.chat.completions, "create", return_value=mock_resp):
            prd, design = client.generate_overview("소스코드 내용")
        assert "요구사항" in prd
        assert "아키텍처" in design


# ──────────────────────────────────────────────
# extract_semantic_nodes() + edges() 통합 (mock)
# ──────────────────────────────────────────────

class TestSemanticExtraction:
    def test_nodes_파싱(self, client):
        nodes_json = '[{"id": "UserManager", "label": "사용자 관리", "purpose": "사용자 CRUD"}]'
        mock_resp = make_mock_response(nodes_json)
        with patch.object(client._client.chat.completions, "create", return_value=mock_resp):
            nodes = client.extract_semantic_nodes("분석 내용", "설계 내용")
        assert nodes[0]["id"] == "UserManager"

    def test_edges_파싱(self, client):
        edges_json = '[{"source": "A", "target": "B", "relation": "데이터를 조회"}]'
        mock_resp = make_mock_response(edges_json)
        with patch.object(client._client.chat.completions, "create", return_value=mock_resp):
            edges = client.extract_semantic_edges([], {})
        assert edges[0]["relation"] == "데이터를 조회"
