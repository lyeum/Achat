# VDB — 벡터 데이터베이스 구조 및 운용 가이드

> 엔진: ChromaDB PersistentClient (`chroma_dev/`)
> 임베딩: BAAI/bge-m3 (SentenceTransformer)
> 유사도 공간: cosine (`hnsw:space=cosine`)
> threshold 계산: `distance ≤ 1.0 - threshold` (distance=0: 동일, 1: 직교)

---

## 0. 메모리 분류 원칙

VDB에 저장되는 데이터는 **수명(lifetime)** 기준으로 두 종류로 분류한다.

| 분류 | 컬렉션 | 설명 | 세션 초기화 시 |
|---|---|---|---|
| **에피소딕 (Episodic)** | `{char_id}_memory` | 특정 세션에서 사용자와 나눈 대화 기억 | 사용자 선택에 따라 삭제 가능 |
| **영구 지식 (Permanent)** | `world_knowledge` | 세계관·장소 정보, LLM이 대화 중 생성한 장소 | 절대 삭제하지 않음 |

> **에피소딕 기억**은 특정 캐릭터와의 한 세션(대화 회차) 동안 쌓이는 기억이다.
> 새 세션 시작 시 사용자가 저장을 원하지 않으면 해당 세션의 기억을 삭제할 수 있다.
>
> **영구 지식**은 세계관·장소 지식으로, 세션 초기화와 무관하게 항상 보존된다.
> 사용자가 대화를 통해 AI에게 알려준 세계/장소 정보도 여기에 속한다.

### play_log — 학습용 데이터 (VDB 외부)

`play_log`는 VDB와 **별개**로 관리되는 학습용 데이터다.

- 저장 위치: `training/log/{category}/{session_id}.jsonl` (JSONL 형식)
- 저장 주체: `training/log/conversation_logger.py` — `ConversationLogger.on_turn()`
- 카테고리: `daily` / `emotion` / `advice` / `memory` / `persona` / `feedback_pos` / `feedback_neg`
- 저장 대상: 대화 이력, 감정 표현 로그 등 fine-tuning용 원본 데이터
- **배포(deployment) 빌드에서는 불필요**: `config.py`의 `enable_play_log: False`로 비활성화.
  학습은 개발 단계에서만 수행되며, 배포 환경에는 로거를 초기화하지 않는다.
- VDB 조회·쓰기 경로와 완전히 분리되어 있어 런타임 응답 성능에 영향 없음

---

## 1. VDB 구성

### 1-1. 물리 저장 구조

ChromaDB는 벡터만 저장하는 게 아니라 **원본 텍스트·메타데이터·벡터를 분리 저장**한다.

```
chroma_dev/
├─ chroma.sqlite3        ← 원본 텍스트(document) + 메타데이터 (SQLite)
└─ {uuid}/
   └─ data_level0.bin   ← 벡터 임베딩 (HNSW 인덱스 바이너리)
```

- **SQLite**: 텍스트 원본, id, metadata 저장. 사람이 읽을 수 있는 형태.
- **HNSW 바이너리**: float 벡터 배열. 빠른 근사 최근접 이웃 탐색(ANN)용.

### 1-2. 검색 동작 원리

벡터는 검색 키로만 사용하고, 실제 반환값은 SQLite의 원본 텍스트다.

```
쿼리 텍스트
    → bge-m3 임베딩 → float 벡터
    → HNSW 인덱스에서 cosine 거리 계산
    → 거리 ≤ cutoff(=1 - threshold)인 항목의 id 추출
    → SQLite에서 id 기준 원본 document·metadata 반환
```

### 1-3. 갱신 방식

VDB 갱신은 **항목 단위 upsert**다. 스냅샷 교체 방식이 아니다.

| 상황 | 내부 동작 |
|---|---|
| 기억 저장 (summarizer) | `col.upsert(id=mem_xxx_...)` — id 없으면 추가, 있으면 덮어씀 |
| 동적 장소 추가 (world_nav) | `col.upsert(id=loc_장소명)` — 동일 |
| sources 수정 후 재인덱싱 | 예외적으로 컬렉션 삭제 후 전체 `col.add()` (`force=True`일 때만) |

### 1-4. 세션 종료와 데이터 영속성

`PersistentClient`는 `upsert()` / `add()` 호출 시점에 즉시 디스크(`chroma_dev/`)에 기록한다.
인메모리 DB가 아니므로 **프로세스가 종료되어도 데이터는 보존**된다.

세션 초기화(새 대화 시작) 시 동작:

| 데이터 종류 | 초기화 시 동작 |
|---|---|
| `{char_id}_memory` (에피소딕) | 사용자가 저장 거부 시 해당 세션의 기억 삭제 가능 |
| `world_knowledge` (영구 지식) | 초기화와 무관하게 항상 보존 |
| `play_log/*.jsonl` (학습용) | 항상 보존 (학습 데이터 누적 목적) |

---

## 2. 주의사항

### 2-1. `force=True` 삭제 범위

`force=True`로 재인덱싱할 때 삭제되는 것은 **`world_knowledge` 컬렉션 하나뿐**이다.
`{char_id}_memory`(장기 기억)는 전혀 건드리지 않는다.

```python
client.delete_collection("world_knowledge")  # 이것만 삭제
# haru_memory, seonjae_memory 등 기억 컬렉션은 그대로
```

### 2-2. 동적 생성 장소는 `force=True` 시 사라진다

대화 중 LLM이 생성한 장소(`source: "generated"`)는 `sources/*.md`에 기록되지 않는다.
`world_knowledge` 컬렉션 안에만 존재하므로 `force=True` 재인덱싱 시 함께 삭제된다.

동적 장소를 영구 보존하려면 재인덱싱 전에 아래 순서로 처리한다:

```python
# 1. 동적 생성 장소 목록 확인
col_w = client.get_collection("world_knowledge")
generated = col_w.get(where={"source": {"$eq": "generated"}})
# generated["documents"], generated["metadatas"] 확인

# 2. 필요한 항목을 rag/sources/world/place.md에 수동으로 추가

# 3. force=True 재인덱싱
```

### 2-3. ChromaDB metadata 타입 제약

ChromaDB metadata 값은 `str / int / float / bool`만 허용한다.
`list` 타입은 저장 불가 — `tags` 필드가 쉼표 직렬화(`"이름,취미,바다"`)로 저장되는 이유가 이것이다.

```python
# long_term.py store() 내부
flat_meta = {
    "tags": ",".join(meta.get("tags", [])),  # list → str 변환
    ...
}
```

### 2-4. threshold 기본값 vs 실제 적용값

코드 기본값과 실제 설정값이 다르다.

| 위치 | 값 |
|---|---|
| `long_term.py` / `retrieve.py` 코드 기본값 | `0.7` |
| `M_schema.json` retrieval_config | `0.7` |
| **실제 `config.py` 적용값** | **`0.52`** |

`config.py`의 `vdb_threshold: 0.52`가 우선 적용된다. M_schema.json의 값은 참조용 문서일 뿐 코드가 직접 읽지 않는다.

---

## 3. 컬렉션 구조

VDB 안에 두 개의 독립 컬렉션이 존재한다.

| 컬렉션명 | 분류 | 역할 | 저장 주체 | 검색 주체 |
|---|---|---|---|---|
| `{char_id}_memory` | 에피소딕 | 세션별 대화 기억 | `memory/summarizer.py` | `memory/long_term.py` |
| `world_knowledge` | 영구 지식 | 세계관·장소 지식 | `rag/index.py`, `rag/world_nav.py` | `rag/retrieve.py` |

`{char_id}_memory`는 **세션 단위**로 관리된다. 하나의 캐릭터에 대해 여러 세션이 존재할 수 있으며,
각 기억 항목에는 `session_id` 메타데이터가 붙어 세션별 조회·삭제가 가능하다.

---

## 4. `{char_id}_memory` — 에피소딕 기억 컬렉션

### 4-1. 저장 데이터 스키마 (`conversation/memory_act/M_schema.json`)

```
{
  "id":      "mem_haru_a3f2c1b0",        ← mem_{char_id}_{uuid8}
  "content": "사용자 이름은 민준. 바다를 좋아한다고 했다.",
  "metadata": {
    "character_id": "Haru",
    "session_id":   "...",
    "turn_range":   "10-20",             ← 요약 대상 턴 범위
    "importance":   0.85,               ← 0.5 미만은 저장 안 함
    "tags":         "이름,취미,바다",    ← list → 쉼표 직렬화 (ChromaDB 제약)
    "location":     "beach",
    "timestamp":    "2025-01-18T09:30:00Z"
  }
}
```

### 4-2. 중요도 기준 (`summarizer.score_importance`)

| 등급 | 점수 범위 | 저장 여부 | 트리거 키워드 예시 |
|---|---|---|---|
| high | 0.85 | ✅ | 이름, 약속, 비밀, 미안, 기억해줘, 고마워 |
| mid  | 0.60 | ✅ | 취미, 감정, 슬퍼, 저번에, 다음에, 피드백 |
| low  | 0.0 | ❌ (기본값) | 키워드 없음 — 기본 0.0으로 저장 안 됨 |

> `score_importance()`는 키워드 없으면 기본 0.0을 반환한다.
> VDB 쓰기 임계값이 **0.65** 이므로 키워드에 매칭되지 않는 요약은 저장되지 않는다 (VDB 오염 차단).

### 4-3. 저장 흐름

```
매 턴 종료 후 (conversation/core/router.py handle_turn)
    │
    └─ summarizer.check_trigger(session, trigger_n=5)
           session.turn_count % 5 == 0 이면 True (백그라운드 스레드로 비동기 실행)
               │
               ├─ summarizer.summarize()
               │      최근 20개 메시지 → LLM (max_tokens=250)
               │      "사용자에 대해 알게 된 정보 중심, 객관적으로 1~3문장"
               │
               ├─ summarizer.score_importance(summary)
               │      키워드 매칭 → 0.0 / 0.60 / 0.85
               │
               └─ summarizer.write_to_vdb()
                      score ≥ 0.65 → long_term.store() → ChromaDB upsert
```

### 4-4. 검색 흐름

```
매 턴 시작 (handle_turn 2번)
    │
    └─ long_term.query(user_input, character_id)
           ChromaDB query(n_results=2, where={importance: {$gte: 0.65}})
           distance ≤ 1.0 - 0.52 = 0.48 필터
               │
               └─ Layer C (장기 기억 150토큰) 로 PromptBuilder에 전달
```

### 4-5. 세션 초기화 시 에피소딕 기억 삭제

새 세션 시작 시 이전 세션 기억을 삭제하려면 `session_id` 기준으로 삭제한다.

```python
col = client.get_collection(f"{char_id}_memory")
col.delete(where={"session_id": {"$eq": old_session_id}})
```

> 사용자가 저장을 원하는 경우 삭제하지 않고 다음 세션에도 조회되도록 유지할 수 있다.
> `world_knowledge`는 이 과정에서 절대 건드리지 않는다.

---

## 5. `world_knowledge` — 영구 지식 컬렉션

### 5-1. 초기 인덱싱 (sources/*.md → VDB)

```
conversation/main.py 시작 시 자동 실행 (force=False)
    │
    └─ rag/index.index_world(world_dir, force=False)
           컬렉션 이미 있으면 → 스킵
           없으면:
             rag/sources/world/*.md 파일 읽기
             → _chunk_text(size=400, overlap=50) 분할
             → ChromaDB add(ids, documents, metadatas)
                 id 형식: {파일명_without_ext}_{chunk_index:03d}
                          예: place_000, culture_001, story_002
                 metadata: {source: "place.md", chunk_index: 0}
```

현재 `sources/world/` 파일:

| 파일 | 내용 |
|---|---|
| `Seaside.md` | 장소·문화·스토리 통합 단일 파일. `## 장소`, `## 문화`, `## 스토리` 섹션으로 구분. 청킹 시 섹션 경계를 존중하는 분할 방식 적용. |

> **구조 변경 이력**: 기존 `place.md` / `culture.md` / `story.md` 분리 파일을 `Seaside.md` 단일 파일로 통합.
> 재인덱싱 시 `force=True`로 기존 컬렉션을 삭제 후 재빌드.

### 5-2. 검색 흐름

```
매 턴 시작 (handle_turn 3번)
    │
    └─ WorldRetriever.query(user_input)
           ChromaDB query(n_results=2)
           distance ≤ 0.48 필터
               │
               └─ Layer B (세계관+act 200토큰) 로 PromptBuilder에 전달
```

### 5-3. 동적 장소 생성 흐름 ⚠️

대화 중 유저가 sources에 없는 장소로 이동을 요청할 경우:

```
유저: "카페 가자"
    │
    └─ router._handle_location(user_input)
           rag/world_nav.detect_move_intent()
             키워드 필터("가자" 포함) → 통과
             LLM 추출(max_tokens=15): "카페"
               │
               ├─ YAML acts 매칭 시도 (location 필드 부분 일치)
               │      → 없으면 다음 단계
               │
               └─ find_or_create_location("카페", world_desc, retriever, llm)
                      WorldRetriever.query("카페")
                        → RAG 히트 있으면 → 기존 묘사 반환 (끝)
                        → 히트 없으면:
                            LLM 생성 (max_tokens=200)
                            "세계관 배경 + '카페' 묘사, 150자 내외 산문"
                                │
                                └─ retriever.add_document(
                                       doc_id="loc_카페",
                                       text="[카페] {묘사}",
                                       metadata={source: "generated", location: "카페"}
                                   )
                                   → ChromaDB world_knowledge에 upsert
                                   → session.location_context = "카페\n{묘사}"
```

**주의: 동적 생성 장소는 `sources/*.md`에 반영되지 않는다.**

- ChromaDB에만 저장되므로 `force=True`로 재인덱싱하면 사라짐
- `metadata.source = "generated"`으로 구분 가능
- 영구 보존이 필요하면 수동으로 `sources/world/place.md`에 추가 후 재인덱싱

---

## 6. sources/*.md 수정 및 재인덱싱

세계관 원본 문서를 수정하고 VDB에 반영하는 방법:

```bash
# 1. sources 파일 편집
vim rag/sources/world/place.md

# 2. 강제 재인덱싱
uv run python -c "
from config import get_config
from pathlib import Path
from rag.index import index_world

cfg = get_config()
index_world(
    world_dir=Path('rag/sources/world'),
    chroma_path=cfg['chroma_path'],
    embedding_model=cfg.get('embedding_model', 'BAAI/bge-m3'),
    force=True,   # 기존 컬렉션 삭제 후 재인덱싱
)
print('재인덱싱 완료')
"
```

> `force=True`는 기존 `world_knowledge` 컬렉션을 통째로 삭제하므로
> **동적 생성 장소도 함께 사라진다.** 필요시 사전에 sources에 병합할 것.

---

## 7. VDB 직접 조회·수정 명령어

### 장기 기억 조회

```python
import chromadb

client = chromadb.PersistentClient(path="./chroma_dev")
col = client.get_collection("haru_memory")

# 전체 조회
col.get()

# 중요도 높은 기억만
col.get(where={"importance": {"$gte": 0.8}})

# 특정 세션 기억
col.get(where={"session_id": {"$eq": "세션ID"}})
```

### 장기 기억 수정·삭제

```python
# 내용 수정 (id 필요)
col.update(ids=["mem_haru_a3f2c1b0"], documents=["수정된 요약 내용"])

# 단건 삭제
col.delete(ids=["mem_haru_a3f2c1b0"])

# 중요도 낮은 항목 일괄 삭제
col.delete(where={"importance": {"$lt": 0.6}})
```

### 세계관 컬렉션 조회

```python
col_w = client.get_collection("world_knowledge")

# 전체 청크 확인
col_w.get()

# 동적 생성 장소만 확인
col_w.get(where={"source": {"$eq": "generated"}})
```

### 컬렉션 목록 확인

```python
[c.name for c in client.list_collections()]
# → ['haru_memory', 'world_knowledge']  등
```

---

## 8. 관련 파일 요약

| 파일 | 분류 | 역할 |
|---|---|---|
| `memory/long_term.py` | 에피소딕 | ChromaDB store/query (세션별 기억) |
| `memory/short_term.py` | 런타임 | 슬라이딩 윈도우 단기 버퍼 (VDB 미사용) |
| `memory/summarizer.py` | 에피소딕 | N턴 요약 → 중요도 scoring → VDB 저장 |
| `rag/index.py` | 영구 지식 | sources/*.md → world_knowledge 인덱싱 |
| `rag/retrieve.py` | 영구 지식 | world_knowledge 시맨틱 검색 + 동적 upsert |
| `rag/world_nav.py` | 영구 지식 | 이동 의도 감지 → 동적 장소 생성·저장 |
| `conversation/core/router.py` | — | 한 턴 전체 흐름 조율 (VDB·RAG 모두 여기서 호출) |
| `conversation/memory_act/M_schema.json` | — | 기억 항목 스키마 + 중요도 규칙 |
| `training/log/conversation_logger.py` | 학습용 | 대화 이력·감정 로그 수집 (배포 불필요, dev-only) |
| `chroma_dev/` | — | ChromaDB 런타임 데이터 (gitignore 권장) |
| `rag/sources/world/` | 영구 지식 | 세계관 원본 문서 (인덱싱 소스) |
