# DEP-0 배포 환경 동작 검증 체크리스트

> 배포 전 필수 선행 확인 항목. Windows + CPU 환경 기준.
> 순서대로 진행하며 각 항목 통과 후 다음 단계로 넘어간다.

---

## 1단계 — 병합 및 변환 (Linux 개발 환경)

| # | 항목 | 명령 / 확인 방법 | 통과 기준 |
|---|---|---|---|
| 1-1 | LoRA v11 병합 | `uv run python scripts/merge_lora.py --adapter output/LoRA_v11/adapter --output_dir output/merged_v11` | `output/merged_v11/config.json` 생성 확인 |
| 1-2 | 병합 모델 무결성 | `python -c "from transformers import AutoModelForCausalLM; AutoModelForCausalLM.from_pretrained('output/merged_v11', device_map='cpu')"` | 오류 없이 로드 |
| 1-3 | GGUF 변환 | `bash scripts/convert_to_gguf.sh --merged output/merged_v11 --out_dir output/gguf --llama_cpp <llama.cpp 경로>` | `output/gguf/model_q4km.gguf` (~2GB) 생성 |
| 1-4 | 배포 패키지 생성 | `bash scripts/package_deploy.sh --gguf output/gguf/model_q4km.gguf` | `dist/achat/` 디렉토리 + `dist/achat.zip` 생성 |

---

## 2단계 — Windows 환경 세팅

| # | 항목 | 확인 방법 | 통과 기준 |
|---|---|---|---|
| 2-1 | Python 3.10+ | `python --version` | `3.10.x` 이상 |
| 2-2 | uv 설치 | `uv --version` | 오류 없음 |
| 2-3 | 의존성 설치 | `dist/achat/` 에서 `uv sync` | 오류 없이 완료 |
| 2-4 | llama-cpp-python CPU 지원 | `python -c "import llama_cpp; print(llama_cpp.__version__)"` | 오류 없음 |
| 2-5 | AVX2 지원 확인 | CPU-Z 또는 `wmic cpu get caption` | AVX2 항목 확인 |

---

## 3단계 — 개별 컴포넌트 검증

Windows `dist/achat/` 에서 `ACHAT_ENV=deploy` 설정 후 각 항목 확인.

### 3-1. LLM 추론 (llama-cpp)

```bat
set ACHAT_ENV=deploy
python -c "
from config import get_config
from conversation.core.llm_client import LLMClient
cfg = get_config()
llm = LLMClient(cfg)
resp = llm.generate([{'role':'user','content':'안녕'}], stream=False)
print('LLM OK:', resp[:30])
"
```

통과 기준: 한국어 응답 출력, OOM 없음

### 3-2. 임베딩 + ChromaDB (VDB)

```bat
python -c "
from config import get_config
from memory.long_term import LongTermMemory
cfg = get_config()
cfg['chroma_path'] = './chroma_deploy_test'
m = LongTermMemory(cfg)
m.add_entry('TestChar', '테스트 기억입니다.', {'importance': 0.8})
result = m.query('테스트', 'TestChar')
print('VDB OK:', result)
m.clear_all('TestChar')
"
```

통과 기준: 저장 후 쿼리 결과 반환

### 3-3. RAG 인덱싱 + 검색

```bat
python -c "
from config import get_config
from rag.index import index_world
from rag.retrieve import WorldRetriever
cfg = get_config()
cfg['chroma_path'] = './chroma_deploy_test'
index_world('rag/sources/world', chroma_path='./chroma_deploy_test', force=True)
rag = WorldRetriever(cfg)
result = rag.query('등대지기 전설에 대해 들어봤어?')
print('RAG OK:', len(result), '건')
"
```

통과 기준: 1건 이상 반환

### 3-4. QML UI 기동

```bat
set ACHAT_ENV=deploy
python main.py
```

통과 기준:
- 플로팅 창 정상 표시
- 채팅 입력 → 응답 수신 (10~30초 이내, CPU 추론)
- 트레이 아이콘 표시
- 창 닫아도 앱 유지, 트레이에서 재열기 가능

---

## 4단계 — 통합 동작 검증

| # | 항목 | 확인 방법 |
|---|---|---|
| 4-1 | 첫 대화 응답 | "안녕" 입력 → 하루 응답 출력 |
| 4-2 | 이름 기억 | "나 민준이야" → 몇 턴 후 "내 이름 기억해?" → "민준" 포함 응답 |
| 4-3 | 세계관 질문 | "등대지기 전설에 대해 들어봤어?" → 세계관 내용 포함 응답 |
| 4-4 | 기능 모드 전환 | "#파일찾기" 또는 기능 키워드 입력 → 기능 모드 진입 확인 |
| 4-5 | 세션 재시작 | 앱 종료 후 재실행 → 이전 대화 컨텍스트 일부 유지 |

---

---

## 5단계 — exe 인스톨러 검증 (AchatSetup.exe)

> 방법 A 설치 마법사 경로 전체를 클린 Windows 환경에서 검증한다.

| # | 항목 | 확인 방법 | 통과 기준 |
|---|---|---|---|
| 5-1 | 인스톨러 실행 | `AchatSetup.exe` 더블클릭 | 설치 마법사 창 정상 표시 |
| 5-2 | 경로 변경 설치 | 기본 경로(`C:\Achat`) 외 다른 경로 선택 | 선택한 경로에 정상 설치 |
| 5-3 | uv sync 자동 실행 | 마법사 완료 후 "의존성 패키지 설치 중..." 표시 | `.venv` 폴더 생성 확인 |
| 5-4 | 모델 없이 실행 | `models\model_q4km.gguf` 없는 상태로 `Achat.exe` 실행 | "모델 파일을 찾을 수 없습니다" 안내창 출력 |
| 5-5 | 정상 실행 | `model_q4km.gguf` 복사 후 `Achat.exe` 더블클릭 | 플로팅 UI 정상 기동, 대화 가능 |
| 5-6 | 제어판 제거 | 제어판 → 앱 → Achat → 제거 | 설치 경로 + `.venv` + `chroma_deploy` + `data\sessions` 모두 삭제됨 |
| 5-7 | 잔여 파일 없음 | 레지스트리 및 C드라이브 전체 확인 | `C:\Achat` (또는 설치 경로) 외 어디에도 파일 없음 |

---

## 알려진 배포 환경 제약

| 항목 | 내용 |
|---|---|
| CPU 추론 속도 | 8~15 tok/s (AVX2 기준), 응답에 10~30초 소요 |
| 첫 실행 초기화 | bge-m3 모델 다운로드 (~500MB), ChromaDB 인덱싱 — 최초 1회만 |
| VRAM | 불필요 (CPU 전용), RAM 4GB 이상 권장 |
| DEP-5 LoRA 런타임 | 현재 미지원 (llama-cpp-python PR 대기 중) — 모델은 병합된 GGUF로 배포 |
| Inno Setup 앱 아이콘 | `ui_ux/assets/icons/app.ico` 미생성 시 기본 아이콘 사용 (PNG → ICO 변환 필요) |
