"""통합 플로우 테스트 — 기능 시작~끝 전체 경로 검증.

각 기능을 "사용자 입력 → 내부 처리 → 최종 출력"의 전체 흐름으로 검증한다.
테스트 파일/폴더는 tests/fixtures/ 아래에만 생성되며,
각 테스트 함수 실행 후 즉시 삭제된다.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ACHAT_ENV", "ui_test")

from PySide6.QtCore import QCoreApplication
_app = QCoreApplication.instance() or QCoreApplication(sys.argv)


# ── 공통 픽스처 ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def fixtures_root():
    """tests/fixtures/ — 세션 시작 시 생성, 세션 종료 시 전체 삭제."""
    path = TESTS_DIR / "fixtures"
    path.mkdir(exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture()
def bridge():
    """PySide6 ChatBridge (stub agent, session=None)."""
    agent = MagicMock()
    agent.session = None
    agent.character = {"id": "Haru", "name": "하루"}
    agent.world = {"world_id": "seaside_world"}
    agent.router = None
    agent.llm = None
    agent.cfg = {}
    from ui_ux.bridge import ChatBridge
    return ChatBridge(agent)


# ══════════════════════════════════════════════════════════════════════════════
# 1. 로컬 파일 검색 — bridge.searchFiles() 전체 플로우
#
#    흐름: 폴더 선택 → searchFiles(query, folder, ext)
#          → JSON [{"path":..., "snippet":...}] 반환
#
#    검증 포인트:
#      · 루트 / 1단계 / 2단계 하위폴더 파일 모두 탐색되는지
#      · 한국어 파일명, 바이너리 파일, 확장자 키워드 검색
#      · 선택한 폴더 밖 결과가 섞이지 않는지
# ══════════════════════════════════════════════════════════════════════════════

class TestLocalSearchFullFlow:

    @pytest.fixture(autouse=True)
    def setup_dir(self, fixtures_root):
        """
        tests/fixtures/local_search/ 구조:
            readme.txt            ← 루트
            notes.md              ← 루트, 내용: "unique_keyword_root"
            screenshot.png        ← 바이너리
            documents/
                report.txt        ← 1단계, 내용: "분기 보고서"
                보고서_2026.txt   ← 한국어 파일명
                archive/
                    old_report.txt       ← 2단계
                    deep_unique_xyz.txt  ← 2단계, 유니크 내용
        """
        base = fixtures_root / "local_search"
        base.mkdir(exist_ok=True)

        (base / "readme.txt").write_text("이 파일은 루트 레벨입니다", encoding="utf-8")
        (base / "notes.md").write_text("unique_keyword_root", encoding="utf-8")
        (base / "screenshot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        sub1 = base / "documents"
        sub1.mkdir(exist_ok=True)
        (sub1 / "report.txt").write_text("분기 보고서 내용입니다", encoding="utf-8")
        (sub1 / "보고서_2026.txt").write_text("한국어 파일명 테스트 내용", encoding="utf-8")

        sub2 = sub1 / "archive"
        sub2.mkdir(exist_ok=True)
        (sub2 / "old_report.txt").write_text("오래된 보고서 내용", encoding="utf-8")
        (sub2 / "deep_unique_xyz.txt").write_text("깊은 폴더의 유니크 키워드 xyz9988", encoding="utf-8")

        self.base = base
        yield
        shutil.rmtree(base, ignore_errors=True)

    # ── 정상 탐색 ────────────────────────────────────────────────────────────

    def test_finds_file_in_root_dir(self, bridge):
        """루트 디렉토리 파일이 검색 결과에 포함된다."""
        items = json.loads(bridge.searchFiles("notes", str(self.base), ""))
        assert isinstance(items, list)
        assert any("notes.md" in r["path"] for r in items), \
            f"루트 파일 미검색. 결과: {[r['path'] for r in items]}"

    def test_finds_file_in_first_level_subfolder(self, bridge):
        """1단계 하위폴더(documents/) 파일이 검색 결과에 포함된다."""
        items = json.loads(bridge.searchFiles("report", str(self.base), ""))
        paths = [r["path"] for r in items]
        assert any("documents" in p and "report.txt" in p for p in paths), \
            f"1단계 하위폴더 미검색. 결과: {paths}"

    def test_finds_file_in_deep_nested_folder(self, bridge):
        """2단계 중첩 폴더(documents/archive/) 파일이 검색 결과에 포함된다."""
        items = json.loads(bridge.searchFiles("deep_unique_xyz", str(self.base), ""))
        paths = [r["path"] for r in items]
        assert any("archive" in p for p in paths), \
            f"2단계 중첩 폴더 미검색. 결과: {paths}"

    def test_finds_korean_filename_in_subfolder(self, bridge):
        """한국어 파일명을 검색어로 찾을 수 있다."""
        items = json.loads(bridge.searchFiles("보고서", str(self.base), ""))
        assert any("보고서" in r["path"] for r in items), \
            f"한국어 파일명 미검색. 결과: {[r['path'] for r in items]}"

    def test_finds_binary_file_by_extension_keyword(self, bridge):
        """'png' 키워드로 바이너리 .png 파일이 검색된다."""
        items = json.loads(bridge.searchFiles("png", str(self.base), ""))
        assert any("screenshot.png" in r["path"] for r in items), \
            f"바이너리 파일 미검색. 결과: {[r['path'] for r in items]}"

    # ── 결과 형식 ────────────────────────────────────────────────────────────

    def test_each_result_has_path_and_snippet_keys(self, bridge):
        """결과 항목은 반드시 'path', 'snippet' 키를 가진다."""
        items = json.loads(bridge.searchFiles("report", str(self.base), ""))
        assert len(items) > 0
        for item in items:
            assert "path" in item, f"'path' 키 없음: {item}"
            assert "snippet" in item, f"'snippet' 키 없음: {item}"

    def test_results_contain_only_files_under_selected_folder(self, bridge):
        """선택한 폴더 밖의 파일은 결과에 포함되지 않는다."""
        items = json.loads(bridge.searchFiles("report", str(self.base), ""))
        root_str = str(self.base)
        for item in items:
            assert item["path"].startswith(root_str), \
                f"선택 폴더 밖 파일 포함: {item['path']}"

    def test_no_match_returns_empty_list(self, bridge):
        """일치 항목 없으면 빈 배열을 반환한다."""
        items = json.loads(bridge.searchFiles("xyzzy_절대없음_99999", str(self.base), ""))
        assert items == []

    # ── 오류 처리 ────────────────────────────────────────────────────────────

    def test_empty_query_returns_error_json(self, bridge):
        """빈 검색어 → {"error": ...} JSON 반환."""
        parsed = json.loads(bridge.searchFiles("", str(self.base), ""))
        assert "error" in parsed

    def test_nonexistent_folder_returns_error_json(self, bridge):
        """존재하지 않는 폴더 → {"error": ...} JSON 반환."""
        parsed = json.loads(bridge.searchFiles("hello", "/nonexistent_xyz_achat_test", ""))
        assert "error" in parsed


# ══════════════════════════════════════════════════════════════════════════════
# 2. 로컬 검색 내부 함수 — _index_directory → _search 전체 플로우
#
#    흐름: _index_directory(root) → _search(query) → 결과 검증
#
#    검증 포인트:
#      · 모든 깊이의 파일이 인덱싱되는지
#      · FTS5 내용 검색이 하위폴더 파일까지 적용되는지
#      · 파일명 검색(_search_filenames)이 한국어·바이너리를 처리하는지
#      · 증분 인덱싱이 변경 없는 파일을 건너뛰는지
# ══════════════════════════════════════════════════════════════════════════════

class TestLocalSearchInternalFlow:

    @pytest.fixture(autouse=True)
    def setup_dir(self, fixtures_root):
        """
        tests/fixtures/search_internal/ 구조:
            root.txt              ← "root_level_content"
            level1/
                level1_file.txt  ← "unique_phrase_abc"
                level2/
                    level2_file.txt     ← "xyz_deep nested"
                    한국어_깊은곳.txt   ← 한국어 내용
            binary_data.bin      ← 바이너리
        """
        base = fixtures_root / "search_internal"
        base.mkdir(exist_ok=True)

        (base / "root.txt").write_text("root_level_content", encoding="utf-8")

        sub1 = base / "level1"
        sub1.mkdir(exist_ok=True)
        (sub1 / "level1_file.txt").write_text("unique_phrase_abc inside level one", encoding="utf-8")

        sub2 = sub1 / "level2"
        sub2.mkdir(exist_ok=True)
        (sub2 / "level2_file.txt").write_text("xyz_deep nested content here", encoding="utf-8")
        (sub2 / "한국어_깊은곳.txt").write_text("한국어 깊은 폴더 내용", encoding="utf-8")

        (base / "binary_data.bin").write_bytes(b"\x00\x01\x02\x03\xff\xfe")

        self.base = base
        self.db_path = base / "test_internal.db"
        yield
        shutil.rmtree(base, ignore_errors=True)

    def _conn(self):
        from tools.search.local_search import _get_conn
        return _get_conn(self.db_path)

    # ── 인덱싱 ───────────────────────────────────────────────────────────────

    def test_indexes_all_txt_files_including_subfolders(self):
        """_index_directory가 모든 하위폴더 .txt 파일(4개)을 인덱싱한다."""
        from tools.search.local_search import _index_directory
        conn = self._conn()
        updated = _index_directory(conn, self.base, {".txt"}, rebuild=True)
        conn.close()
        # root.txt + level1_file.txt + level2_file.txt + 한국어_깊은곳.txt = 4
        assert updated == 4, f"인덱싱된 파일 수 {updated} (기대: 4)"

    def test_incremental_indexing_skips_unchanged_files(self):
        """두 번째 인덱싱 시 변경된 파일 없으면 갱신 0개."""
        from tools.search.local_search import _index_directory
        conn = self._conn()
        _index_directory(conn, self.base, {".txt"}, rebuild=True)
        second_run = _index_directory(conn, self.base, {".txt"}, rebuild=False)
        conn.close()
        assert second_run == 0, f"증분 갱신 {second_run}개 (기대: 0)"

    # ── FTS5 내용 검색 ───────────────────────────────────────────────────────

    def test_fts_finds_content_in_root_file(self):
        from tools.search.local_search import _index_directory, _search
        conn = self._conn()
        _index_directory(conn, self.base, {".txt"}, rebuild=True)
        results = _search(conn, "root_level_content", root=self.base)
        conn.close()
        paths = [r[0] for r in results]
        assert any("root.txt" in p for p in paths), f"루트 파일 내용 미검색. 결과: {paths}"

    def test_fts_finds_content_in_level1_subfolder(self):
        from tools.search.local_search import _index_directory, _search
        conn = self._conn()
        _index_directory(conn, self.base, {".txt"}, rebuild=True)
        results = _search(conn, "unique_phrase_abc", root=self.base)
        conn.close()
        paths = [r[0] for r in results]
        assert any("level1_file.txt" in p for p in paths), \
            f"1단계 하위폴더 내용 미검색. 결과: {paths}"

    def test_fts_finds_content_in_level2_subfolder(self):
        from tools.search.local_search import _index_directory, _search
        conn = self._conn()
        _index_directory(conn, self.base, {".txt"}, rebuild=True)
        results = _search(conn, "xyz_deep", root=self.base)
        conn.close()
        paths = [r[0] for r in results]
        assert any("level2_file.txt" in p for p in paths), \
            f"2단계 깊은 폴더 내용 미검색. 결과: {paths}"

    # ── 파일명 검색 ──────────────────────────────────────────────────────────

    def test_filename_search_finds_korean_in_deep_folder(self):
        """한국어 파일명 — 깊은 폴더에 있어도 파일명으로 탐색된다."""
        from tools.search.local_search import _search_filenames
        results = _search_filenames(self.base, "한국어", limit=10)
        paths = [r[0] for r in results]
        assert any("한국어_깊은곳.txt" in p for p in paths), \
            f"한국어 파일명 미탐색. 결과: {paths}"

    def test_filename_search_finds_binary_file(self):
        """바이너리 파일도 파일명 탐색에 포함된다."""
        from tools.search.local_search import _search_filenames
        results = _search_filenames(self.base, "binary", limit=10)
        assert any("binary_data.bin" in r[0] for r in results)

    def test_filename_search_limit_is_respected(self):
        """limit 파라미터가 결과 수를 제한한다."""
        from tools.search.local_search import _search_filenames
        results = _search_filenames(self.base, "l", limit=2)
        assert len(results) <= 2

    # ── 통합 결과 ────────────────────────────────────────────────────────────

    def test_combined_search_returns_filename_and_content_hits(self):
        """_search: 파일명 히트 + FTS5 내용 히트가 합산된다."""
        from tools.search.local_search import _index_directory, _search
        conn = self._conn()
        _index_directory(conn, self.base, {".txt"}, rebuild=True)
        # "level1"은 파일명(level1_file.txt)에도, 내용("level one")에도 있음
        results = _search(conn, "level1", root=self.base)
        conn.close()
        assert len(results) >= 1
        paths = [r[0] for r in results]
        assert any("level1" in p for p in paths)

    def test_no_duplicate_paths_in_combined_result(self):
        """_search 결과에 중복 경로가 없다."""
        from tools.search.local_search import _index_directory, _search
        conn = self._conn()
        _index_directory(conn, self.base, {".txt"}, rebuild=True)
        results = _search(conn, "level1", root=self.base)
        conn.close()
        paths = [r[0] for r in results]
        assert len(paths) == len(set(paths)), f"중복 경로 존재: {paths}"


# ══════════════════════════════════════════════════════════════════════════════
# 3. 폴더 분류 — bridge.applyFolderClassify() 전체 플로우
#
#    흐름: 폴더 선택 → applyFolderClassify(path, rule, dry_run)
#          → 파일 이동 또는 미리보기 반환
#
#    검증 포인트:
#      · dry_run=True: 결과 문자열 반환, 파일 이동 없음
#      · dry_run=False 종류별: 이미지/문서/코드가 카테고리 폴더로 이동됨
#      · dry_run=False 확장자별: 확장자명 폴더로 이동됨
# ══════════════════════════════════════════════════════════════════════════════

class TestFolderClassifyFullFlow:

    @pytest.fixture(autouse=True)
    def setup_dir(self, fixtures_root):
        """
        tests/fixtures/classify/ — 혼합 파일 생성.
        각 테스트마다 새로 생성(destructive 작업이므로 함수 스코프).
        """
        base = fixtures_root / "classify"
        if base.exists():
            shutil.rmtree(base)
        base.mkdir()

        (base / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
        (base / "banner.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
        (base / "clip.mp4").write_bytes(b"\x00\x00\x00\x18ftyp" + b"\x00" * 20)
        (base / "report.pdf").write_bytes(b"%PDF-1.4" + b"\x00" * 20)
        (base / "notes.txt").write_text("내용", encoding="utf-8")
        (base / "script.py").write_text("print('hello')", encoding="utf-8")
        (base / "archive.zip").write_bytes(b"PK\x03\x04" + b"\x00" * 20)

        self.base = base
        yield
        shutil.rmtree(base, ignore_errors=True)

    def test_dry_run_returns_string_result(self, bridge):
        """dry_run=True — 문자열 결과 반환."""
        result = bridge.applyFolderClassify(str(self.base), "종류별", True)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_dry_run_does_not_move_files(self, bridge):
        """dry_run=True — 파일이 실제로 이동되지 않는다."""
        bridge.applyFolderClassify(str(self.base), "종류별", True)
        assert (self.base / "photo.jpg").exists(), "dry_run인데 photo.jpg 이동됨"
        assert (self.base / "report.pdf").exists(), "dry_run인데 report.pdf 이동됨"
        assert (self.base / "script.py").exists(), "dry_run인데 script.py 이동됨"

    def test_kind_rule_moves_images_to_subfolder(self, bridge):
        """종류별 분류 — 이미지 파일(jpg, png)이 루트에서 사라진다."""
        bridge.applyFolderClassify(str(self.base), "종류별", False)
        assert not (self.base / "photo.jpg").exists(), "photo.jpg가 이동되지 않음"
        assert not (self.base / "banner.png").exists(), "banner.png가 이동되지 않음"

    def test_kind_rule_moves_documents_to_subfolder(self, bridge):
        """종류별 분류 — 문서 파일(pdf)이 루트에서 사라진다."""
        bridge.applyFolderClassify(str(self.base), "종류별", False)
        assert not (self.base / "report.pdf").exists(), "report.pdf가 이동되지 않음"

    def test_kind_rule_moves_code_to_subfolder(self, bridge):
        """종류별 분류 — 코드 파일(.py)이 루트에서 사라진다."""
        bridge.applyFolderClassify(str(self.base), "종류별", False)
        assert not (self.base / "script.py").exists(), "script.py가 이동되지 않음"

    def test_ext_rule_dry_run_does_not_move(self, bridge):
        """확장자별 분류 dry_run — 파일 이동 없음."""
        bridge.applyFolderClassify(str(self.base), "확장자별", True)
        assert (self.base / "notes.txt").exists()
        assert (self.base / "script.py").exists()

    def test_nonexistent_path_returns_error_string(self, bridge):
        """존재하지 않는 경로 → 오류 문자열 반환."""
        result = bridge.applyFolderClassify("/nonexistent_xyz_achat_classify", "종류별", False)
        assert "오류" in result


# ══════════════════════════════════════════════════════════════════════════════
# 4. 파일 변환 — bridge.applyFileOptions() 전체 플로우
#
#    흐름: 파일 선택 → applyFileOptions(paths_json, rename_to, new_ext)
#          → 파일 이름/확장자 변경 검증
#
#    검증 포인트:
#      · 단일 파일 이름 변경: 새 이름 생성, 원본 삭제
#      · 다중 파일 이름 변경: 공통 접두어 + 번호 형식
#      · 확장자 변경: 새 확장자로 파일 생성, 원본 삭제
#      · 이름 + 확장자 동시 변경
#      · 충돌 시 기존 파일 보호
# ══════════════════════════════════════════════════════════════════════════════

class TestFileOptionsFullFlow:

    @pytest.fixture(autouse=True)
    def setup_dir(self, fixtures_root):
        base = fixtures_root / "file_options"
        if base.exists():
            shutil.rmtree(base)
        base.mkdir()
        self.base = base
        yield
        shutil.rmtree(base, ignore_errors=True)

    def test_rename_single_file_creates_new_and_removes_old(self, bridge):
        """단일 파일 이름 변경 → 새 이름 생성, 원본 삭제."""
        src = self.base / "original_name.txt"
        src.write_text("테스트 내용", encoding="utf-8")

        result = bridge.applyFileOptions(json.dumps([str(src)]), "renamed_file", "")

        assert "완료" in result
        assert (self.base / "renamed_file.txt").exists(), "새 파일이 생성되지 않음"
        assert not src.exists(), "원본 파일이 삭제되지 않음"

    def test_rename_multiple_files_applies_numbered_prefix(self, bridge):
        """다중 파일 이름 변경 → 공통 접두어 + _001, _002, _003 번호."""
        files = []
        for i in range(3):
            f = self.base / f"img_{i}.jpg"
            f.write_bytes(b"\xff\xd8\xff" + bytes([i]))
            files.append(str(f))

        result = bridge.applyFileOptions(json.dumps(files), "vacation", "")

        assert "완료" in result
        assert (self.base / "vacation_001.jpg").exists()
        assert (self.base / "vacation_002.jpg").exists()
        assert (self.base / "vacation_003.jpg").exists()
        for f_path in files:
            assert not Path(f_path).exists(), f"원본이 남아있음: {f_path}"

    def test_change_extension_creates_new_ext_file(self, bridge):
        """확장자 변경 → 새 확장자 파일 생성, 원본 삭제."""
        src = self.base / "data_file.txt"
        src.write_text("col1,col2\n1,2", encoding="utf-8")

        result = bridge.applyFileOptions(json.dumps([str(src)]), "", "csv")

        assert "완료" in result
        assert (self.base / "data_file.csv").exists(), "확장자 변경 파일 미생성"
        assert not src.exists(), "원본 파일이 삭제되지 않음"

    def test_rename_and_ext_change_simultaneously(self, bridge):
        """이름 변경 + 확장자 변경 동시 적용."""
        src = self.base / "old_name.txt"
        src.write_text("내용", encoding="utf-8")

        result = bridge.applyFileOptions(json.dumps([str(src)]), "new_name", "md")

        assert "완료" in result
        assert (self.base / "new_name.md").exists()
        assert not src.exists()

    def test_no_operation_returns_no_change_message(self, bridge):
        """rename_to='', new_ext='' → '변경 없음' 메시지, 원본 유지."""
        src = self.base / "unchanged.txt"
        src.write_text("x", encoding="utf-8")

        result = bridge.applyFileOptions(json.dumps([str(src)]), "", "")

        assert "변경 없음" in result
        assert src.exists(), "변경 없음인데 원본이 삭제됨"

    def test_conflict_does_not_overwrite_existing_file(self, bridge):
        """이름 충돌 시 기존 파일의 내용이 보존된다."""
        src = self.base / "source.txt"
        src.write_text("원본 내용", encoding="utf-8")
        dst = self.base / "target.txt"
        dst.write_text("기존 파일 내용", encoding="utf-8")

        bridge.applyFileOptions(json.dumps([str(src)]), "target", "")

        assert dst.read_text(encoding="utf-8") == "기존 파일 내용", \
            "충돌 시 기존 파일이 덮어써짐"

    def test_empty_paths_list_returns_error(self, bridge):
        """빈 파일 목록 → 오류 메시지 반환."""
        result = bridge.applyFileOptions("[]", "new_name", "")
        assert "없습니다" in result or "오류" in result

    def test_invalid_json_returns_error(self, bridge):
        """잘못된 JSON → 오류 메시지 반환."""
        result = bridge.applyFileOptions("not_valid_json{{{", "new_name", "")
        assert "오류" in result
