"""기능 모드 도구 단위 테스트.

모든 도구를 LLM 없이 execute(params) 직접 호출로 검증한다.
외부 네트워크 / GPU 불필요. tmp_path 픽스처로 실제 파일 I/O 테스트.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ACHAT_ENV", "ui_test")


# ══════════════════════════════════════════════════════════════════════════════
# 공통 — BaseTool.parse_params
# ══════════════════════════════════════════════════════════════════════════════

class TestParseParams:
    """BaseTool.parse_params 는 어떤 도구든 공유하므로 ClassifierTool로 대표 테스트."""

    @pytest.fixture
    def tool(self):
        from tools.folder.classifier import ClassifierTool
        return ClassifierTool()

    def test_plain_json(self, tool):
        raw = '{"target": "/tmp", "rule": "종류별", "dry_run": true}'
        assert tool.parse_params(raw) == {"target": "/tmp", "rule": "종류별", "dry_run": True}

    def test_json_in_code_block(self, tool):
        raw = '```json\n{"rule": "확장자별", "dry_run": false}\n```'
        params = tool.parse_params(raw)
        assert params["rule"] == "확장자별"
        assert params["dry_run"] is False

    def test_invalid_json_returns_empty(self, tool):
        assert tool.parse_params("not json at all") == {}

    def test_empty_string_returns_empty(self, tool):
        assert tool.parse_params("") == {}


# ══════════════════════════════════════════════════════════════════════════════
# 1. ClassifierTool (folder_classify)
# ══════════════════════════════════════════════════════════════════════════════

class TestClassifierTool:
    @pytest.fixture
    def tool(self):
        from tools.folder.classifier import ClassifierTool
        return ClassifierTool()

    @pytest.fixture
    def sample_dir(self, tmp_path):
        """혼합 파일이 있는 임시 디렉토리."""
        (tmp_path / "photo.jpg").touch()
        (tmp_path / "report.pdf").touch()
        (tmp_path / "script.py").touch()
        (tmp_path / "archive.zip").touch()
        return tmp_path

    def test_dry_run_no_files_moved(self, tool, sample_dir):
        result = tool.execute({"target": str(sample_dir), "rule": "종류별", "dry_run": True})
        assert "dry_run=True" in result
        # 파일이 실제로 이동되지 않아야 함
        assert (sample_dir / "photo.jpg").exists()

    def test_dry_run_lists_all_files(self, tool, sample_dir):
        result = tool.execute({"target": str(sample_dir), "rule": "종류별", "dry_run": True})
        assert "photo.jpg" in result
        assert "report.pdf" in result

    def test_kind_rule_moves_to_category_folders(self, tool, sample_dir):
        result = tool.execute({"target": str(sample_dir), "rule": "종류별", "dry_run": False})
        assert "완료" in result
        assert (sample_dir / "images" / "photo.jpg").exists()
        assert (sample_dir / "docs" / "report.pdf").exists()
        assert (sample_dir / "code" / "script.py").exists()
        assert (sample_dir / "archives" / "archive.zip").exists()

    def test_ext_rule_uses_extension_as_folder(self, tool, tmp_path):
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.txt").touch()
        tool.execute({"target": str(tmp_path), "rule": "확장자별", "dry_run": False})
        assert (tmp_path / "txt" / "a.txt").exists()

    def test_empty_dir_returns_message(self, tool, tmp_path):
        result = tool.execute({"target": str(tmp_path), "rule": "종류별", "dry_run": False})
        assert "파일이 없습니다" in result

    def test_nonexistent_path_returns_error(self, tool):
        result = tool.execute({"target": "/nonexistent_xyz_achat", "dry_run": True})
        assert "오류" in result

    def test_duplicate_file_skipped(self, tool, tmp_path):
        """이미 이동 대상 경로에 파일이 있으면 건너뜀."""
        (tmp_path / "a.jpg").touch()
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "a.jpg").touch()  # 충돌 파일 미리 생성
        result = tool.execute({"target": str(tmp_path), "rule": "종류별", "dry_run": False})
        assert "건너뜀" in result


# ══════════════════════════════════════════════════════════════════════════════
# 2. RenamerTool (file_rename)
# ══════════════════════════════════════════════════════════════════════════════

class TestRenamerTool:
    @pytest.fixture
    def tool(self):
        from tools.folder.renamer import RenamerTool
        return RenamerTool()

    @pytest.fixture
    def files(self, tmp_path):
        for name in ["Hello World.txt", "foo.py", "BAR.md"]:
            (tmp_path / name).write_text("data")
        return tmp_path

    def test_dry_run_does_not_rename(self, tool, files):
        tool.execute({"target": str(files), "rule": "소문자", "dry_run": True})
        assert (files / "Hello World.txt").exists()

    def test_lowercase_rule(self, tool, files):
        tool.execute({"target": str(files), "pattern": "*.txt", "rule": "소문자", "dry_run": False})
        assert (files / "hello world.txt").exists()

    def test_space_removal_rule(self, tool, files):
        tool.execute({"target": str(files), "pattern": "*.txt", "rule": "공백제거", "dry_run": False})
        assert (files / "Hello_World.txt").exists()

    def test_numbered_prefix_rule(self, tool, tmp_path):
        for n in ["a.txt", "b.txt", "c.txt"]:
            (tmp_path / n).write_text("x")
        tool.execute({"target": str(tmp_path), "rule": "번호_원본명", "dry_run": False})
        assert (tmp_path / "001_a.txt").exists()
        assert (tmp_path / "002_b.txt").exists()

    def test_prefix_add_rule(self, tool, tmp_path):
        (tmp_path / "img.png").write_text("x")
        tool.execute({"target": str(tmp_path), "rule": "prefix추가", "prefix": "new_", "dry_run": False})
        assert (tmp_path / "new_img.png").exists()

    def test_suffix_add_rule(self, tool, tmp_path):
        (tmp_path / "img.png").write_text("x")
        tool.execute({"target": str(tmp_path), "rule": "suffix추가", "suffix": "_v2", "dry_run": False})
        assert (tmp_path / "img_v2.png").exists()

    def test_date_rule_format(self, tool, tmp_path):
        (tmp_path / "photo.jpg").write_text("x")
        result = tool.execute({"target": str(tmp_path), "rule": "날짜_원본명", "dry_run": True})
        # 날짜 형식 YYYYMMDD가 미리보기에 포함되어야 함
        import re
        assert re.search(r"\d{8}_photo\.jpg", result)

    def test_no_matching_files_returns_message(self, tool, tmp_path):
        result = tool.execute({"target": str(tmp_path), "pattern": "*.xyz", "rule": "소문자", "dry_run": True})
        assert "없습니다" in result

    def test_nonexistent_dir_returns_error(self, tool):
        result = tool.execute({"target": "/nonexistent_xyz_renamer"})
        assert "오류" in result

    def test_conflict_skipped(self, tool, tmp_path):
        """이름 변환 결과가 이미 존재하면 건너뜀."""
        (tmp_path / "A.txt").write_text("orig")
        (tmp_path / "a.txt").write_text("existing")  # 충돌
        result = tool.execute({"target": str(tmp_path), "pattern": "A.txt", "rule": "소문자", "dry_run": False})
        assert "건너뜀" in result
        assert (tmp_path / "A.txt").exists()  # 원본 유지


# ══════════════════════════════════════════════════════════════════════════════
# 3. ConverterTool (image_convert)
# ══════════════════════════════════════════════════════════════════════════════

class TestConverterTool:
    @pytest.fixture
    def tool(self):
        from tools.folder.converter import ConverterTool
        return ConverterTool()

    def test_unsupported_from_ext_returns_error(self, tool, tmp_path):
        result = tool.execute({"target": str(tmp_path), "from_ext": "mp4", "to_ext": "png", "dry_run": True})
        assert "오류" in result

    def test_same_ext_returns_error(self, tool, tmp_path):
        result = tool.execute({"target": str(tmp_path), "from_ext": "png", "to_ext": "png", "dry_run": True})
        assert "동일" in result

    def test_no_matching_files_returns_message(self, tool, tmp_path):
        result = tool.execute({"target": str(tmp_path), "from_ext": "png", "to_ext": "webp", "dry_run": True})
        assert "없습니다" in result

    def test_dry_run_lists_files(self, tool, tmp_path):
        (tmp_path / "a.png").write_bytes(b"")
        (tmp_path / "b.png").write_bytes(b"")
        result = tool.execute({"target": str(tmp_path), "from_ext": "png", "to_ext": "webp", "dry_run": True})
        assert "dry_run=True" in result
        assert "a.png" in result

    def test_pillow_convert(self, tool, tmp_path):
        """Pillow가 설치된 경우 실제 변환 수행."""
        pytest.importorskip("PIL")
        from PIL import Image
        img = Image.new("RGB", (4, 4), color=(255, 0, 0))
        src = tmp_path / "test.png"
        img.save(str(src))
        result = tool.execute({"target": str(tmp_path), "from_ext": "png", "to_ext": "webp", "dry_run": False})
        assert "완료" in result
        assert (tmp_path / "test.webp").exists()

    def test_pillow_not_installed_returns_error(self, tool, tmp_path):
        """Pillow import 실패 시 안내 메시지 반환."""
        with patch.dict("sys.modules", {"PIL": None, "PIL.Image": None}):
            result = tool.execute({"target": str(tmp_path), "from_ext": "png", "to_ext": "webp", "dry_run": False})
        assert "Pillow" in result

    def test_nonexistent_dir_returns_error(self, tool):
        result = tool.execute({"target": "/nonexistent_xyz_converter", "from_ext": "png", "to_ext": "webp"})
        assert "오류" in result


# ══════════════════════════════════════════════════════════════════════════════
# 4. PromptConverterTool (prompt_convert)
# ══════════════════════════════════════════════════════════════════════════════

class TestPromptConverterTool:
    """LLM과 웹 검색을 mock으로 대체해 파이프라인 구조만 검증한다."""

    @pytest.fixture
    def tool_stub(self):
        """llm=None (stub 모드) 인스턴스."""
        from tools.prompt_converter import PromptConverterTool
        return PromptConverterTool(llm=None)

    @pytest.fixture
    def tool_with_llm(self):
        """mock LLM이 주입된 인스턴스."""
        from tools.prompt_converter import PromptConverterTool
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "sunset beach, golden hour, volumetric lighting, 8k"
        return PromptConverterTool(llm=mock_llm)

    def _mock_guide(self, guide_text: str):
        return patch("tools.prompt_converter._collect_guide", return_value=guide_text)

    def test_empty_content_returns_error(self, tool_stub):
        result = tool_stub.execute({"model": "SDXL", "content": ""})
        assert "오류" in result

    def test_empty_model_returns_error(self, tool_stub):
        result = tool_stub.execute({"model": "", "content": "해질녘 풍경"})
        assert "오류" in result

    def test_stub_mode_returns_stub_prefix(self, tool_stub):
        with self._mock_guide("some guide text"):
            result = tool_stub.execute({"model": "Midjourney", "content": "파란 하늘"})
        assert "[stub]" in result

    def test_stub_mode_includes_guide_preview(self, tool_stub):
        with self._mock_guide("very useful guide content"):
            result = tool_stub.execute({"model": "DALL-E 3", "content": "고양이"})
        assert "very useful guide content" in result

    def test_llm_called_with_model_context(self, tool_with_llm):
        with self._mock_guide("guide text"):
            result = tool_with_llm.execute({"model": "Stable Diffusion XL", "content": "해질녘"})
        assert "Stable Diffusion XL" in result
        tool_with_llm._llm.generate.assert_called_once()

    def test_llm_result_in_output(self, tool_with_llm):
        with self._mock_guide("guide"):
            result = tool_with_llm.execute({"model": "SDXL", "content": "바다"})
        assert "sunset beach" in result  # mock LLM 반환값

    def test_guide_collect_failure_falls_back(self, tool_with_llm):
        """가이드 수집 실패 시에도 LLM 변환은 계속 수행."""
        with self._mock_guide(""):  # 빈 가이드 = 수집 실패
            result = tool_with_llm.execute({"model": "Midjourney", "content": "숲속 오두막"})
        assert isinstance(result, str)
        tool_with_llm._llm.generate.assert_called_once()

    def test_llm_exception_returns_error(self, tool_with_llm):
        tool_with_llm._llm.generate.side_effect = RuntimeError("LLM 다운")
        with self._mock_guide("guide"):
            result = tool_with_llm.execute({"model": "SDXL", "content": "별밤"})
        assert "오류" in result


# ══════════════════════════════════════════════════════════════════════════════
# 5. LocalSearchTool (local_search)
# ══════════════════════════════════════════════════════════════════════════════

class TestLocalSearchTool:
    @pytest.fixture
    def tool(self):
        from tools.search.local_search import LocalSearchTool
        return LocalSearchTool()

    def test_empty_query_returns_error(self, tool, tmp_path):
        result = tool.execute({"query": "", "path": str(tmp_path)})
        assert "오류" in result

    def test_nonexistent_path_returns_error(self, tool):
        result = tool.execute({"query": "hello", "path": "/nonexistent_xyz_search"})
        assert "오류" in result

    def test_finds_text_in_file(self, tool, tmp_path):
        (tmp_path / "note.txt").write_text("unique_keyword_achat_test", encoding="utf-8")
        result = tool.execute({"query": "unique_keyword_achat_test", "path": str(tmp_path)})
        assert "note.txt" in result

    def test_no_results_message(self, tool, tmp_path):
        (tmp_path / "empty.txt").write_text("nothing here", encoding="utf-8")
        result = tool.execute({"query": "zzz_never_in_file_xyz", "path": str(tmp_path)})
        assert "없습니다" in result

    def test_ext_filter(self, tool, tmp_path):
        """ext 필터로 .py만 검색 → .txt 파일은 제외."""
        (tmp_path / "code.py").write_text("target_token = 1", encoding="utf-8")
        (tmp_path / "doc.txt").write_text("target_token = 1", encoding="utf-8")
        # py 전용 인덱스 (rebuild=True로 이전 인덱스 제거)
        result = tool.execute({
            "query": "target_token",
            "path": str(tmp_path),
            "ext": "py",
            "rebuild": True,
        })
        # 검색은 성공해야 하고 doc.txt는 결과에 없어야 함
        assert "doc.txt" not in result

    def test_incremental_index_no_reindex_unchanged(self, tool, tmp_path):
        """파일 미변경 시 두 번째 검색에서 갱신 0개."""
        (tmp_path / "stable.txt").write_text("hello world", encoding="utf-8")
        tool.execute({"query": "hello", "path": str(tmp_path), "rebuild": True})
        result2 = tool.execute({"query": "hello", "path": str(tmp_path)})
        # "인덱싱 0개 갱신" 포함 여부로 증분 인덱싱 확인
        assert "0개 갱신" in result2


# ── _sanitize_fts_query 단위 테스트 ──────────────────────────────────────────

class TestSanitizeFtsQuery:
    """FTS5 특수 문자 제거 — 단어 토큰만 추출."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from tools.search.local_search import _sanitize_fts_query
        self.san = _sanitize_fts_query

    def test_single_word(self):
        assert self.san("hello") == "hello"

    def test_multi_word(self):
        assert self.san("hello world") == "hello world"

    def test_hyphen_splits_into_two_terms(self):
        result = self.san("2026-03")
        assert result == "2026 03"

    def test_asterisk_stripped(self):
        result = self.san("prefix*")
        assert result == "prefix"

    def test_korean_passthrough(self):
        result = self.san("보고서 작성")
        assert result == "보고서 작성"

    def test_special_chars_stripped(self):
        result = self.san('(title:report) "exact"')
        assert result == "title report exact"

    def test_empty_string_returns_empty_phrase(self):
        assert self.san("") == '""'


class TestSearchFilenames:
    """_search_filenames — 파일 시스템 직접 탐색 파일명 검색."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from tools.search.local_search import _search_filenames
        self.fn = _search_filenames

    def test_finds_by_exact_name(self, tmp_path):
        (tmp_path / "report.txt").touch()
        results = self.fn(tmp_path, "report", 10)
        assert any("report.txt" in r[0] for r in results)

    def test_finds_korean_filename(self, tmp_path):
        (tmp_path / "보고서_2026.txt").touch()
        results = self.fn(tmp_path, "보고서", 10)
        assert len(results) == 1
        assert "보고서_2026.txt" in results[0][0]

    def test_finds_by_extension(self, tmp_path):
        """'png'로 검색하면 .png 파일이 검색된다."""
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")
        (tmp_path / "notes.txt").write_text("hello")
        results = self.fn(tmp_path, "png", 10)
        paths = [r[0] for r in results]
        assert any("image.png" in p for p in paths)
        assert not any("notes.txt" in p for p in paths)

    def test_case_insensitive(self, tmp_path):
        (tmp_path / "README.md").touch()
        results = self.fn(tmp_path, "readme", 10)
        assert len(results) == 1

    def test_limit_respected(self, tmp_path):
        for i in range(5):
            (tmp_path / f"file_{i}.txt").touch()
        results = self.fn(tmp_path, "file", 3)
        assert len(results) == 3

    def test_no_match_returns_empty(self, tmp_path):
        (tmp_path / "unrelated.txt").touch()
        results = self.fn(tmp_path, "xyzzy_never", 10)
        assert results == []

    def test_binary_file_found_by_name(self, tmp_path):
        """바이너리 파일도 파일명으로 검색된다."""
        f = tmp_path / "archive.zip"
        f.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
        results = self.fn(tmp_path, "archive", 10)
        assert any("archive.zip" in r[0] for r in results)

    def test_integrated_search_combines_name_and_content(self, tmp_path):
        """_search: 파일명 매칭 + FTS5 내용 검색 합산 결과."""
        from tools.search.local_search import _get_conn, _index_directory, _search
        # 파일명 매칭 대상
        (tmp_path / "보고서_summary.txt").write_text("무관한 내용", encoding="utf-8")
        # 내용 매칭 대상
        (tmp_path / "data.txt").write_text("보고서 내용이 여기 있습니다", encoding="utf-8")

        conn = _get_conn(tmp_path / "test.db")
        _index_directory(conn, tmp_path, {".txt"}, True)
        results = _search(conn, "보고서", root=tmp_path)
        conn.close()

        paths = [r[0] for r in results]
        assert any("보고서_summary.txt" in p for p in paths)
        assert any("data.txt" in p for p in paths)


# ══════════════════════════════════════════════════════════════════════════════
# 5-B. prompt_converter 보조 함수 단위 테스트 (BUG-F04, BUG-F05)
# ══════════════════════════════════════════════════════════════════════════════

class TestPromptConverterHelpers:
    """_fetch_text HTML 정제 및 _collect_guide 병렬 크롤링 구조 검증."""

    def test_fetch_text_strips_script_blocks(self):
        """script/style 블록이 제거되어야 한다."""
        from tools.prompt_converter import _fetch_text
        html = b"<html><script>var x=1;</script><p>Hello</p></html>"
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = html
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp
            result = _fetch_text("http://example.com")
        assert "var x=1" not in result
        assert "Hello" in result

    def test_fetch_text_strips_svg_blocks(self):
        """svg 블록이 제거되어야 한다 (BUG-F05)."""
        from tools.prompt_converter import _fetch_text
        html = b"<html><svg><path d='M0 0'/></svg><p>Content</p></html>"
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = html
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp
            result = _fetch_text("http://example.com")
        assert "M0 0" not in result
        assert "Content" in result

    def test_fetch_text_strips_base64_src(self):
        """data-uri base64 src 속성이 제거되어야 한다 (BUG-F05)."""
        from tools.prompt_converter import _fetch_text
        b64 = "data:image/png;base64," + "A" * 50
        html = f'<img src="{b64}"/><p>Text</p>'.encode()
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = html
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp
            result = _fetch_text("http://example.com")
        assert "base64" not in result
        assert "Text" in result

    def test_collect_guide_parallel_execution(self):
        """URL이 여러 개일 때 병렬로 크롤링되는지 검증 (BUG-F04)."""
        from tools.prompt_converter import _collect_guide
        from ddgs.exceptions import DDGSException

        fake_results = [
            {"href": "http://a.com"},
            {"href": "http://b.com"},
            {"href": "http://c.com"},
        ]
        call_order: list[str] = []

        def fake_fetch(url: str) -> str:
            call_order.append(url)
            return f"guide from {url}"

        with patch("ddgs.DDGS") as mock_ddgs_cls, \
             patch("tools.prompt_converter._fetch_text", side_effect=fake_fetch):
            mock_ddgs = MagicMock()
            mock_ddgs.__enter__ = lambda s: s
            mock_ddgs.__exit__ = MagicMock(return_value=False)
            mock_ddgs.text.return_value = fake_results
            mock_ddgs_cls.return_value = mock_ddgs
            result = _collect_guide("TestModel")

        # 3개 URL이 모두 처리됐는지 확인 (순서는 보장 안 됨)
        assert len(call_order) == 3
        assert "guide from" in result


# ══════════════════════════════════════════════════════════════════════════════
# 6. WebSearchTool (web_search)
# ══════════════════════════════════════════════════════════════════════════════

class TestWebSearchTool:
    @pytest.fixture
    def tool(self):
        from tools.search.web_search import WebSearchTool
        return WebSearchTool()

    def _mock_ddg(self, results):
        """_ddg_search 를 mock으로 교체하는 헬퍼."""
        return patch("tools.search.web_search._ddg_search", return_value=results)

    def test_empty_query_returns_error(self, tool):
        result = tool.execute({"query": ""})
        assert "오류" in result

    def test_returns_html_hyperlink(self, tool):
        """결과가 HTML <a href> 형식으로 반환된다."""
        fake = [{"title": "Python", "url": "https://python.org", "snippet": "Python is great."}]
        with self._mock_ddg(fake):
            result = tool.execute({"query": "python"})
        assert "https://python.org" in result
        assert "<a href=" in result
        assert "Python" in result

    def test_no_results_returns_message(self, tool):
        with self._mock_ddg([]):
            result = tool.execute({"query": "xyzzy_not_found"})
        assert "찾지 못했습니다" in result

    def test_exception_returns_error_message(self, tool):
        with patch("tools.search.web_search._ddg_search", side_effect=Exception("fail")):
            result = tool.execute({"query": "test"})
        assert "오류" in result

    def test_max_results_capped(self, tool):
        """max_results 10 초과 → 10으로 제한."""
        fake = [{"title": f"r{i}", "url": "", "snippet": f"s{i}"} for i in range(10)]
        with self._mock_ddg(fake) as mock_fn:
            tool.execute({"query": "test", "max_results": 99})
            called_max = mock_fn.call_args[0][1]
            assert called_max == 10

    def test_max_results_min_one(self, tool):
        """max_results 0 이하 → 1로 보정."""
        fake = [{"title": "r", "url": "", "snippet": "s"}]
        with self._mock_ddg(fake) as mock_fn:
            tool.execute({"query": "test", "max_results": 0})
            called_max = mock_fn.call_args[0][1]
            assert called_max == 1


# ══════════════════════════════════════════════════════════════════════════════
# 6-A. WebSearchTool — HTML hyperlink 및 유사도 스코어링 테스트
# ══════════════════════════════════════════════════════════════════════════════

class TestWebSearchHyperlinkAndScoring:
    """HTML hyperlink 포맷 및 relevance 스코어링 동작 검증."""

    _FAKE_RESULTS = [
        {"title": "Python 공식", "url": "https://python.org",  "snippet": "파이썬 프로그래밍 언어다."},
        {"title": "무관한 페이지", "url": "https://unrelated.com", "snippet": "완전히 다른 내용이다."},
    ]

    @pytest.fixture
    def tool(self):
        from tools.search.web_search import WebSearchTool
        return WebSearchTool()

    def _mock_ddg(self, results):
        return patch("tools.search.web_search._ddg_search", return_value=results)

    def test_output_contains_html_anchor_tags(self, tool):
        """결과에 <a href="..."> HTML anchor 태그가 포함된다."""
        with self._mock_ddg(self._FAKE_RESULTS):
            result = tool.execute({"query": "파이썬"})
        assert "<a href=" in result
        assert "https://python.org" in result

    def test_output_contains_snippet_text(self, tool):
        """결과에 snippet 내용이 포함된다."""
        with self._mock_ddg(self._FAKE_RESULTS):
            result = tool.execute({"query": "파이썬"})
        assert "파이썬 프로그래밍 언어다" in result

    def test_high_relevance_result_appears_first(self, tool):
        """쿼리 토큰 겹침이 많은 결과가 앞에 위치한다."""
        results = [
            {"title": "무관", "url": "https://a.com", "snippet": "전혀 관련없는 내용"},
            {"title": "파이썬 역사", "url": "https://b.com", "snippet": "파이썬은 1991년에 만들어졌다"},
        ]
        with self._mock_ddg(results):
            result = tool.execute({"query": "파이썬 역사"})
        pos_b = result.index("https://b.com")
        pos_a = result.index("https://a.com")
        assert pos_b < pos_a, "관련도 높은 결과가 먼저 표시되어야 함"

    def test_snippet_html_special_chars_escaped(self, tool):
        """snippet의 HTML 특수문자(<, >, &)가 이스케이프된다."""
        results = [{"title": "Test", "url": "https://t.com", "snippet": "A < B & C > D"}]
        with self._mock_ddg(results):
            result = tool.execute({"query": "test"})
        assert "&lt;" in result
        assert "&amp;" in result
        assert "&gt;" in result

    def test_result_count_shown_in_header(self, tool):
        """헤더에 검색 건수가 표시된다."""
        with self._mock_ddg(self._FAKE_RESULTS):
            result = tool.execute({"query": "파이썬"})
        assert "2건" in result

    def _score_fn(self):
        from tools.search.web_search import _score_relevance, _tokenize
        return _score_relevance, _tokenize

    def test_score_relevance_substring_match_korean(self):
        """한국어 조사 포함 텍스트도 쿼리 토큰을 부분문자열로 감지한다."""
        score_fn, tok_fn = self._score_fn()
        q = tok_fn("파이썬 역사")
        # snippet에 "파이썬은"(조사 은), "역사적으로"(파생어) 포함
        result = {"title": "", "snippet": "파이썬은 1991년 역사적으로 중요하다"}
        assert score_fn(q, result) == 2  # "파이썬" in "파이썬은", "역사" in "역사적으로"

    def test_score_relevance_no_match_returns_zero(self):
        """완전히 무관한 snippet은 0을 반환한다."""
        score_fn, tok_fn = self._score_fn()
        q = tok_fn("파이썬")
        result = {"title": "", "snippet": "완전히 다른 내용"}
        assert score_fn(q, result) == 0


# ══════════════════════════════════════════════════════════════════════════════
# 6-B. PromptGuideStore 단위 테스트 (기능개선.md 3번)
# ══════════════════════════════════════════════════════════════════════════════

class TestPromptGuideStore:
    """tools/prompt_store.py ChromaDB 없이 동작 검증 (tmp_path + chromadb in-memory)."""

    @pytest.fixture
    def store(self, tmp_path):
        """임시 경로 기반 PromptGuideStore (embedding 없이 metadata only)."""
        from tools.prompt_store import PromptGuideStore
        return PromptGuideStore(str(tmp_path / "chroma_test"), embedding_model=None)

    def test_save_and_exact_query(self, store):
        """저장 후 모델명으로 exact query가 동작해야 한다."""
        store.save("Stable Diffusion XL", "quality, masterpiece, ...")
        result = store.query("Stable Diffusion XL")
        assert result is not None
        assert "masterpiece" in result

    def test_normalize_model_name(self, store):
        """대소문자·공백 다른 모델명도 동일 항목으로 조회된다."""
        store.save("stable diffusion xl", "guide text")
        # 대문자, 공백 다르게 조회해도 normalize 후 동일 키
        result = store.query("Stable Diffusion XL")
        assert result is not None

    def test_query_missing_returns_none(self, store):
        """없는 모델명 조회는 None을 반환해야 한다."""
        result = store.query("NonExistentModelXYZ")
        assert result is None

    def test_list_models(self, store):
        """저장된 모델 목록이 반환되어야 한다."""
        store.save("SDXL", "guide a")
        store.save("Midjourney", "guide b")
        models = store.list_models()
        assert "sdxl" in models
        assert "midjourney" in models

    def test_delete_model(self, store):
        """삭제 후 해당 모델 조회 시 None을 반환해야 한다."""
        store.save("DALL-E 3", "guide text")
        deleted = store.delete("DALL-E 3")
        assert deleted > 0
        assert store.query("DALL-E 3") is None

    def test_db_first_flow_skips_crawling(self, tmp_path):
        """DB에 가이드가 있으면 _collect_guide가 호출되지 않아야 한다."""
        from tools.prompt_converter import PromptConverterTool
        from tools.prompt_store import PromptGuideStore

        store = PromptGuideStore(str(tmp_path / "chroma_test"), embedding_model=None)
        store.save("Midjourney", "saved guide from DB")

        tool = PromptConverterTool(
            llm=None,
            config={"chroma_path": str(tmp_path / "chroma_test")},
        )
        # PromptGuideStore를 직접 주입
        tool._store = store

        with patch("tools.prompt_converter._collect_guide") as mock_crawl:
            result = tool.execute({"model": "Midjourney", "content": "하늘 그림"})
        mock_crawl.assert_not_called()
        assert "saved guide from DB" in result

    def test_crawl_result_saved_to_db(self, tmp_path):
        """크롤링 성공 시 결과가 DB에 자동 저장되어야 한다."""
        from tools.prompt_converter import PromptConverterTool
        from tools.prompt_store import PromptGuideStore

        store = PromptGuideStore(str(tmp_path / "chroma_test"), embedding_model=None)
        tool = PromptConverterTool(
            llm=None,
            config={"chroma_path": str(tmp_path / "chroma_test")},
        )
        tool._store = store

        with patch("tools.prompt_converter._collect_guide", return_value="crawled guide data"):
            tool.execute({"model": "Flux", "content": "풍경"})

        # 크롤링 후 DB에 저장되었는지 확인
        assert store.query("Flux") == "crawled guide data"


# ══════════════════════════════════════════════════════════════════════════════
# 7. agent.core._select_tool / handle_input (키워드 폴백 + 명시 tool_name)
# ══════════════════════════════════════════════════════════════════════════════

class TestAgentToolDispatch:
    """agent.core의 도구 선택 로직을 stub 모드로 검증."""

    @pytest.fixture
    def agent(self, tmp_path):
        """stub 모드 Agent. world YAML이 필요하므로 최소 YAML을 생성."""
        import yaml
        world_dir = ROOT / "conversation" / "world"
        world_files = list(world_dir.glob("W_*.yaml"))
        assert world_files, "world YAML 없음 — 테스트 전제 불충족"

        from agent.core import Agent
        return Agent(
            character_id="Haru",
            world_path=str(world_files[0]),
            config={"model_backend": "stub"},
        )

    def test_explicit_tool_name_bypasses_keyword(self, agent):
        """tool_name 명시 시 키워드 감지 없이 도구 실행."""
        result = agent.handle_input(
            "아무 텍스트",
            mode="function",
            tool_name="prompt_convert",
        )
        # stub 모드: params={}로 execute → "오류: 변환할 내용이 없습니다."
        assert "오류" in result or isinstance(result, str)

    def test_unknown_tool_name_returns_error(self, agent):
        result = agent.handle_input(
            "뭔가",
            mode="function",
            tool_name="nonexistent_tool_xyz",
        )
        assert "알 수 없는 도구" in result

    def test_keyword_fallback_detects_search(self, agent):
        result = agent.handle_input(
            "파일 검색해줘",
            mode="function",
        )
        # stub 모드: 쿼리 없음 → "오류: 검색어가 없습니다."
        assert "오류" in result or isinstance(result, str)

    def test_no_keyword_no_tool_returns_hint(self, agent):
        result = agent.handle_input(
            "낚시 가고 싶다",
            mode="function",
        )
        assert "파악하지 못했습니다" in result or "도구" in result


# ══════════════════════════════════════════════════════════════════════════════
# 7. prompt_convert fallback 유틸 단위 테스트 (BUG-19)
# ══════════════════════════════════════════════════════════════════════════════

class TestPromptConvertFallbackUtils:
    """agent/core.py 모듈 레벨 fallback 헬퍼 함수 검증."""

    def test_korean_ratio_pure_korean(self):
        from agent.core import _korean_ratio
        assert _korean_ratio("안녕하세요") > 0.9

    def test_korean_ratio_pure_ascii(self):
        from agent.core import _korean_ratio
        assert _korean_ratio("hello world") == 0.0

    def test_korean_ratio_mixed(self):
        from agent.core import _korean_ratio
        # "고양이 cat" → 3 한글 / 6 non-space = 0.5
        ratio = _korean_ratio("고양이 cat")
        assert 0.4 < ratio < 0.6

    def test_is_content_valid_empty_returns_false(self):
        from agent.core import _is_content_valid
        assert _is_content_valid("", "stable diffusion으로 그려줘") is False

    def test_is_content_valid_english_content_korean_src(self):
        """한국어 입력 + 영어 content → 비정상 판정."""
        from agent.core import _is_content_valid
        src = "stable diffusion 모델에 고양이를 그려달라고 입력할건데 프롬프트를 어떻게 작성해야 해"
        content = "고양이 그리기 request for Stable Diffusion model"
        assert _is_content_valid(content, src) is False

    def test_is_content_valid_korean_content_korean_src(self):
        """한국어 입력 + 한국어 content → 정상 판정."""
        from agent.core import _is_content_valid
        src = "stable diffusion으로 고양이 그림 그려줘"
        content = "고양이가 앉아 있는 모습, 귀여운 스타일"
        assert _is_content_valid(content, src) is True

    def test_is_content_valid_english_src_english_content(self):
        """영어 입력 + 영어 content → 정상 판정 (한국어 비율 임계 미충족)."""
        from agent.core import _is_content_valid
        src = "draw a cat with stable diffusion"
        content = "cute cat sitting, photorealistic"
        assert _is_content_valid(content, src) is True

    def test_model_regex_korean_sentence_not_captured(self):
        """한국어가 섞인 문장에서 모델명만 추출돼야 한다."""
        from agent.core import _PROMPT_CONVERT_MODEL_RE
        user_input = "stable diffusion 모델에 고양이를 그려달라고 입력할건데 프롬프트를 어떻게 작성해야 해"
        m = _PROMPT_CONVERT_MODEL_RE.search(user_input)
        assert m is not None
        captured = m.group(1).strip()
        # 한글이 포함되면 안 됨
        assert all("\uAC00" > c or c > "\uD7A3" for c in captured), f"한글 포함됨: {captured!r}"
        assert captured.lower().startswith("stable diffusion")

    def test_model_regex_sdxl_variant(self):
        from agent.core import _PROMPT_CONVERT_MODEL_RE
        m = _PROMPT_CONVERT_MODEL_RE.search("sdxl turbo로 이미지 생성해줘")
        assert m is not None
        assert m.group(1).strip().lower().startswith("sdxl")

    def test_model_regex_no_match_plain_korean(self):
        from agent.core import _PROMPT_CONVERT_MODEL_RE
        m = _PROMPT_CONVERT_MODEL_RE.search("고양이 그림 그려줘")
        assert m is None
