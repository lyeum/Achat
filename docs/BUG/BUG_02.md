# BUG_02.md — LLM OOM (Out of Memory)

> 발견 경위: 실환경 캐릭터 전환 테스트 (2026-03-30)
> 재현 조건: 대화 중 캐릭터 전환(changeCharacter) 시도
> 증상: 프로그램 강제 종료 또는 OS OOM-killer 발동
> 수정 완료: 2026-03-30

---

## BUG-02-A · `ui_ux/bridge.py` — 캐릭터 전환 시 LLM 이중 적재 OOM ✅

**파일**: `ui_ux/bridge.py` — `_rebuild_agent()`

### 증상

```
changeCharacter("다른_캐릭터") 호출
→ out of memory / 프로세스 강제 종료
```

### 발생 원인

`changeCharacter()` → `_rebuild_agent()` → `Agent.from_session()` 순서로 새 Agent를 생성할 때
기존 Agent의 LLM 모델 객체를 먼저 해제하지 않았다.

```
[기존 LLM] 메모리 점유 중 (Python 참조 유지)
     ↓
[신규 LLM] Agent.__init__() → LLMClient() → 모델 로드 시작
     ↓
두 모델이 동시에 메모리에 존재 → OOM
```

**모델별 메모리 사용량 (참고)**

| 백엔드 | 모델 | 메모리 |
|---|---|---|
| `transformers` | Qwen2.5-3B bfloat16 | ~6 GB RAM |
| `llama_cpp` | Qwen2.5-3B Q4_K_M | ~2.5 GB RAM |

캐릭터 전환 순간 `transformers` 기준 최대 **~12 GB** 동시 점유.

### 동일 위험이 있는 경로

`_rebuild_agent()`를 호출하는 슬롯이 3곳이며 모두 동일한 OOM 위험이 있었다:

| 슬롯 | 호출 경로 |
|---|---|
| `changeCharacter(char_id)` | 캐릭터 교체 |
| `newSession(keep_memory)` | 새 세션 시작 |
| `resetCharacter(char_id)` | 현재 캐릭터 초기화 후 재시작 |

### 해결 방법

`_rebuild_agent()` 내부에서 새 Agent 생성 **직전** `_unload_llm()`을 호출해
기존 LLM 모델을 명시적으로 해제한다.

**추가된 `_unload_llm()` 로직:**

```python
def _unload_llm(self) -> None:
    import gc
    llm    = getattr(self._agent, "llm", None)
    backend = getattr(llm, "backend", "")
    model  = getattr(llm, "_model", None)

    # llama_cpp: C 힙까지 해제하는 close() 필수
    if backend == "llama_cpp" and model is not None:
        model.close()

    # transformers: del + GPU 캐시 해제
    if backend == "transformers" and model is not None:
        del llm._model
        llm._model = None
        torch.cuda.empty_cache()   # GPU 사용 시

    del model
    gc.collect()
```

**`_rebuild_agent()` 수정 후:**

```python
def _rebuild_agent(self, state: SessionState) -> None:
    self._unload_llm()          # ← 핵심: 기존 모델 먼저 해제
    ...
    self._agent = Agent.from_session(state, cfg)
```

### 적용 범위

`_unload_llm()`은 `_rebuild_agent()` 단일 진입점에서만 호출되므로
`changeCharacter` / `newSession` / `resetCharacter` 세 슬롯 모두 자동으로 보호된다.

### 수정 파일

| 파일 | 변경 내용 |
|---|---|
| `ui_ux/bridge.py` | `_unload_llm()` 메서드 추가 + `_rebuild_agent()` 앞에서 호출 |

---

## 배포 환경(llama_cpp) 관련 메모

- `llama_cpp`의 `Llama` 객체는 Python GC만으로는 C 레벨 힙이 즉시 해제되지 않는다.
  `model.close()` 명시 호출이 반드시 필요하다.
- Q4_K_M GGUF 기준 메모리는 ~2.5 GB이므로 CPU 배포 환경(8 GB RAM)에서도
  해제 없이 교체 시 OOM이 발생할 수 있다.
- `gc.collect()` 단독으로는 C 확장 객체의 메모리를 즉시 회수하지 못하므로
  명시적 `close()` / `del` 선행이 필수다.
