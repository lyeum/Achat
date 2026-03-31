# BUG_function.md — 기능 모드 도구 버그 목록

> 발견 경위: 실행 로그 분석 (2026-03-28)
> 재현 입력: "stable-diffusion 1.5 모델에게 귀여운 고양이의 픽셀아트를 생성하라고 하고싶은데 뭐라고 하면 될까?"
> 발생 로그: `파싱된 파라미터 — {'model': '', 'content': '귀여운 귀여운 귀여운 귀여운 귀여운 귀여운 고양이 픽셀아트 이미지 만들기 stable diffusion 1.5'}`
> 수정 완료: 2026-03-28 (BUG-F01~F05 전체)

---

## BUG-F01 · `agent/core.py` + `conversation/core/llm_client.py` — LoRA 파인튜닝 모델로 JSON 파라미터 추출 실패 ⭐ 핵심 ✅

**파일**: `agent/core.py:245`, `conversation/core/llm_client.py:105`

**증상**
```
파싱된 파라미터 — {'model': '', 'content': '귀여운 귀여운 귀여운 귀여운 귀여운 귀여운 고양이 픽셀아트 이미지 만들기 stable diffusion 1.5'}
```
- `model` 필드: 비어있음 (실제 입력에는 "stable-diffusion 1.5" 명시)
- `content` 필드: "귀여운" 6회 반복 + "stable diffusion 1.5"가 content에 혼입
- UI: "모델을 입력해주세요" 에러 표시

**원인**
`LoRA v9`는 Haru 캐릭터 대화 데이터로만 파인튜닝됨. function mode도 동일 `LLMClient` 인스턴스를 사용하므로 JSON 구조화 출력 요청에 LoRA 가중치의 대화 편향이 그대로 적용됨.

```
[요청] {"model": "...", "content": "..."} 형식으로만 응답해라
[LoRA 모델 응답] → 대화 패턴으로 출력, JSON 구조 무시, 토큰 반복 hallucination
```

베이스 모델(Qwen2.5-3B-Instruct)은 JSON 지시문을 따르지만, LoRA 어댑터가 이 능력을 부분적으로 덮어씀.

**초기 제안 방안 3가지**

### 방안 A — Rule-based model 추출 fallback
`parse_params()` 결과에서 model이 비어있으면, 사용자 입력에서 regex로 직접 추출.

### 방안 B — function mode 호출 시 LoRA 어댑터 임시 비활성화
PEFT의 `disable_adapter()` context manager를 사용해 JSON 추출 시에만 베이스 모델로 실행.

> **❌ 방안 B 적용 불가 결론**: GGUF 배포 환경(llama-cpp-python)은 `disable_adapter()` API를 지원하지 않음. dev 환경에서만 동작 가능하므로 배포 일관성 유지를 위해 적용하지 않기로 확정.

### 방안 C — system_prompt에 few-shot 예시 추가
4개의 구체적 입력→출력 예시를 system_prompt에 추가해 LoRA 모델이 JSON 구조를 따르도록 유도.

---

**✅ 실제 구현 (방안 C + A 동시 적용)**

**1. 방안 C — `tools/prompt_converter.py` system_prompt 개선**

입력 형식을 명확히 하는 4개의 few-shot 예시 추가:
```python
"예시:\n"
"입력: stable diffusion 1.5로 고양이 그려줘\n"
'출력: {"model": "Stable Diffusion 1.5", "content": "고양이"}\n'
"입력: midjourney에서 사이버펑크 도시\n"
'출력: {"model": "Midjourney", "content": "사이버펑크 도시"}\n'
"입력: stable-diffusion 1.5 모델에게 귀여운 고양이의 픽셀아트를 생성하라고 하고싶은데 뭐라고 하면 될까?\n"
'출력: {"model": "Stable Diffusion 1.5", "content": "귀여운 고양이 픽셀아트"}\n'
```
실패 패턴("stable-diffusion 1.5 모델에게...")을 직접 예시로 추가해 재현 입력에 대응.

**2. 방안 A — `agent/core.py` _handle_function() fallback 추가**

```python
if tool.name == "prompt_convert":
    if not params.get("model"):
        import re as _re
        m = _re.search(
            r"(stable[\s\-]diffusion[\s\w\.]*|sdxl[\s\w\.]*"
            r"|midjourney[\s\w\.]*|dall[\s\-]e[\s\w\.]*"
            r"|flux[\s\w\.]*|leonardo[\s\w\.]*|imagen[\s\w\.]*)",
            user_input, _re.IGNORECASE,
        )
        if m:
            params["model"] = m.group(1).strip()
            logger.warning("[agent] prompt_convert model fallback(regex) ...")
    if not params.get("content"):
        params["content"] = user_input
        logger.warning("[agent] prompt_convert content fallback(user_input) ...")
```

**수정 결과**
```
수정 전: {'model': '', 'content': '귀여운 귀여운 귀여운... stable diffusion 1.5'}
수정 후: {'model': 'Stable Diffusion 1.5', 'content': '귀여운 고양이 픽셀아트'}
```

---

## BUG-F02 · `conversation/core/llm_client.py` — repetition_penalty 불충분 ✅

**파일**: `conversation/core/llm_client.py:115`

**증상**
"귀여운"이 6회 연속 반복 생성됨. `repetition_penalty=1.1` 설정에도 LoRA 편향이 강해 억제 실패.

**원인**
`repetition_penalty=1.1`은 베이스 모델에서는 충분하지만, 대화 LoRA가 특정 토큰(감정어, 명사)을 반복하도록 편향되어 있어 1.1 수준으로는 제어 불가.

```python
# 수정 전
out = self._model.generate(
    **inputs,
    temperature=0.8,
    repetition_penalty=1.1,   # ← 불충분
    ...
)
```

**✅ 실제 구현**

`LLMClient.generate()` / `_generate_transformers()`에 `mode` 파라미터 추가:

```python
def generate(self, messages, stream=False, max_tokens=512, mode: str = "chat") -> str:
    ...

def _generate_transformers(self, messages, max_tokens, mode: str = "chat"):
    if mode == "function":
        # JSON 추출: greedy decoding, 강한 반복 억제
        gen_kwargs: dict = dict(do_sample=False, repetition_penalty=1.3)
    else:
        # 대화: 기존 샘플링 유지
        gen_kwargs = dict(do_sample=True, temperature=0.8, repetition_penalty=1.1)
```

`agent/core.py`의 function mode LLM 호출:
```python
llm_output = self.llm.generate(messages=[...], stream=False, mode="function")
```

`mode="function"` 시 `do_sample=False`(greedy)로 전환되어 확률적 반복 생성 차단, `repetition_penalty=1.3`으로 강제 억제.

---

## BUG-F03 · `tools/base.py` — parse_params() 필드 유효성 검사 없음 ✅

**파일**: `tools/base.py:22`, `agent/core.py`

**증상**
LLM이 비정상 JSON(model 비어있음, content에 반복 텍스트)을 출력해도 `parse_params()`가 그대로 반환. `execute()`에서 model 누락 오류는 잡지만, content가 할루시네이션 텍스트인 경우는 감지 못 함.

**원인**
`parse_params()`는 JSON 구조 파싱만 담당. 필드 값의 의미적 유효성 검사 없음.

**초기 제안 방안 (Counter 기반 반복 감지)**
```python
words = content.split()
top_word, top_count = Counter(words).most_common(1)[0]
if top_count >= 3:
    content = ""  # fallback 트리거
```

**✅ 실제 구현 (단순화)**

크롤링 단계가 `model`만 사용하고 `content`는 사용하지 않는다는 점 확인 후, content 복잡 검사 없이 단순 폴백으로 결정:

```python
# agent/core.py _handle_function() 내부 (BUG-F01 fallback과 동일 블록)
if not params.get("content"):
    params["content"] = user_input
    logger.warning("[agent] prompt_convert content fallback(user_input) 적용")
```

비어있는 content만 user_input으로 대체. 할루시네이션으로 채워진 경우는 F01에서 few-shot으로 upstream에서 방지함. Counter 기반 감지는 필요 없다고 판단해 미적용.

---

## BUG-F04 · `tools/prompt_converter.py` — 웹 크롤링 직렬 실행으로 응답 지연 ✅

**파일**: `tools/prompt_converter.py:67` (`_collect_guide()`)

**증상**
`_collect_guide()` 실행 시 최대 3개 URL을 순차 크롤링. `_CRAWL_TIMEOUT=8`초 × 3개 = 최대 24초 대기 가능. DuckDuckGo 검색 자체도 수초 소요.

**원인**
```python
for r in results:            # 순차 루프
    text = _fetch_text(url)  # 각 URL마다 blocking HTTP 요청 (최대 8초)
    ...
```

LLMWorker 스레드에서 실행되므로 UI는 안 멈추지만, 사용자 입장에서는 응답이 30초 이상 늦어짐.

**✅ 실제 구현**

`concurrent.futures.ThreadPoolExecutor`로 URL 병렬 크롤링:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def _collect_guide(model: str) -> str:
    ...
    urls = [r.get("href", "") for r in results if r.get("href")]

    parts: list[str] = []
    with ThreadPoolExecutor(max_workers=_SEARCH_RESULTS) as executor:
        futures = {executor.submit(_fetch_text, url): url for url in urls}
        for future in as_completed(futures, timeout=_CRAWL_TIMEOUT + 2):
            text = future.result()
            if text:
                parts.append(text[:_CONTEXT_MAX // _SEARCH_RESULTS])

    return " ".join(parts)[:_CONTEXT_MAX]
```

순차 최대 24초 → 병렬 최대 10초로 단축 (3개 URL이 동시 진행, timeout은 가장 느린 URL 기준으로만 적용).

---

## BUG-F05 · `tools/prompt_converter.py` — `_fetch_text()` HTML 불완전 정제 ✅

**파일**: `tools/prompt_converter.py:45` (`_fetch_text()`)

**증상**
civitai.com, reddit.com 등에서 크롤링 시 아래 데이터가 LLM context에 섞임:
- `<script type="application/json">` 내 JSON 메타데이터 (script 태그 제거 대상이나 type 속성 처리 미흡)
- `<svg>` 블록 내 path data
- Base64 인코딩 이미지 데이터 (`src="data:image/..."`)
- 200자 이상 인라인 JSON 블록

→ 3000자 context 중 상당 부분이 의미없는 데이터로 채워져 LLM 변환 품질 저하.

**원인**
```python
# 수정 전: script/style 블록만 제거
html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", html, ...)
# SVG, 인라인 JSON, data-uri 미처리
```

**✅ 실제 구현**

제거 대상 태그 확장 + data-uri + 인라인 JSON 블록 제거:

```python
# script / style / svg / noscript / iframe 블록 전체 제거
html = re.sub(
    r"<(script|style|svg|noscript|iframe)[^>]*>.*?</(script|style|svg|noscript|iframe)>",
    " ", html, flags=re.DOTALL | re.IGNORECASE,
)
# src/data 속성의 data-uri 제거
html = re.sub(r'(src|data)="data:[^"]*"', "", html)
# 200자 초과 인라인 JSON/데이터 블록 제거
html = re.sub(r"\{[^{}]{200,}\}", " ", html)
```

svg, noscript, iframe 3개 태그 추가, data-uri 속성 제거, 200자 초과 중괄호 블록 제거.

---

## 패키지 이름 변경 대응 (별도 발견) ✅

**파일**: `tools/prompt_converter.py`, `tools/search/web_search.py`

**발견 경위**: BUG-F04 수정 중 `RuntimeWarning: duckduckgo_search not found` 경고 발생

**원인**
`duckduckgo-search` 패키지가 `ddgs`로 이름 변경됨. 기존 import가 동작하지 않음.

**수정**
```python
# 수정 전
from duckduckgo_search import DDGS
from duckduckgo_search import DuckDuckGoSearchException

# 수정 후
from ddgs import DDGS
from ddgs.exceptions import DDGSException
```

`pyproject.toml`: `duckduckgo-search>=8.1.1` → `ddgs>=9.12.0` (`uv add ddgs && uv remove duckduckgo-search`).

---

## BUG-19 · `agent/core.py` — regex fallback 두 가지 문제 ✅

**파일**: `agent/core.py` (`_PROMPT_CONVERT_MODEL_RE`, `_is_content_valid`)
**발견**: 2026-03-29

### 문제 A — `_PROMPT_CONVERT_MODEL_RE`의 `\w`가 한국어 포함

**증상**: `[\s\w\.]*` 패턴이 Python에서 Unicode 전체를 매칭해 모델명 뒤의 한국어 문장까지 캡처함.
```
입력: "stable diffusion 귀여운 고양이 그려줘"
잘못된 매칭: "stable diffusion 귀여운 고양이 그려줘" (모델명이 문장 전체를 흡수)
```

**수정**: `(?:\s+[a-zA-Z0-9._-]+){0,2}` — ASCII 문자/숫자/점/하이픈만 매칭하도록 제한.

### 문제 B — `_is_content_valid` 절대 임계값으로 한국어 혼입 미감지

**증상**: `_korean_ratio(content) < 0.1` 절대 임계값이 너무 낮아 "고양이 그리기 request for Stable Diffusion model"(~16% 한국어) 같은 content를 유효로 판정.

**수정**: 상대 임계값 `_korean_ratio(content) < src_ko * 0.5`로 변경. 입력 대비 content 한국어 비율이 절반 이하면 유효하지 않은 것으로 판정.

테스트: `tests/test_function_tools.py::TestPromptConvertFallbackUtils` 내 BUG-19 관련 케이스

---

## 우선순위 요약

| 버그 | 심각도 | 영향 | 상태 |
|---|---|---|---|
| BUG-F01 LoRA JSON 파라미터 추출 실패 | 🔴 높음 | prompt_convert 기능 완전 불동작 | ✅ 수정 완료 (방안 A+C 동시 적용, 2026-03-28) |
| BUG-F02 repetition_penalty 불충분 | 🟠 중간 | 출력 품질 저하, 반복 hallucination | ✅ 수정 완료 (mode="function" → do_sample=False, rep_penalty=1.3, 2026-03-28) |
| BUG-F03 parse_params() 유효성 검사 없음 | 🟡 낮음 | 비정상 content 통과 | ✅ 수정 완료 (content 비면 user_input 폴백으로 단순화, 2026-03-28) |
| BUG-F04 크롤링 직렬 실행 지연 | 🟠 중간 | 응답 최대 30초 대기 | ✅ 수정 완료 (ThreadPoolExecutor 병렬 크롤링 → 최대 10초, 2026-03-28) |
| BUG-F05 HTML 불완전 정제 | 🟡 낮음 | LLM context 오염 → 변환 품질 저하 | ✅ 수정 완료 (SVG/noscript/iframe/base64/JSON-LD 제거, 2026-03-28) |
| BUG-19 regex \w 한국어 포함 + 절대 임계값 | 🟡 낮음 | 모델명 오추출 / 한국어 혼입 미감지 | ✅ 수정 완료 (ASCII-only regex + 상대 임계값, 2026-03-29) |

---

## 근본 원인 요약

BUG-F01~F03의 공통 근본 원인:

> **대화 LoRA 파인튜닝 모델을 function mode의 JSON 추출에 재사용하는 구조적 문제.**
>
> 해결의 근본 방향:
> 1. **단기(적용 완료)**: 방안 A (regex + user_input fallback) + 방안 C (few-shot) → LoRA 출력 실패를 rule-based로 보정
> 2. **장기(방안 B — 미적용)**: PEFT `disable_adapter()` context는 llama-cpp GGUF 배포 환경에서 지원 안 됨. 배포/dev 동일 동작 보장을 위해 방안 A+C 조합만 유지.
