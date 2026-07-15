# Achat 장기 플랜 — 확장 항목 검토

> 작성일: 2026-05-07  
> 목적: 현재 로드맵(1~7단계) 이후 확장 방향 4가지를 실현 가능성 및 프로젝트 목적 부합도 기준으로 검토  
> 프로젝트 기본 목표: **로컬 구동, 경량화, 오프라인 우선, 사용자 프라이버시 보호**

---

## 1. 강화학습 (DPO / GRPO / RLHF)

### 계획 개요

현재 v11 SFT(Supervised Fine-Tuning) 기반 학습에서 사용자 피드백 데이터를 활용한 강화학습으로 전환.  
`training/log/feedback_pos`, `feedback_neg` 로그를 chosen/rejected 쌍으로 구성해 DPO 학습 적용.

### 실현 가능성: ★★★★☆ (높음)

이미 로드맵 6단계에 구체적으로 계획된 항목이며, 코드 인프라(EWC, 카테고리 가중치, 학습 모니터 등)가 완비된 상태.

| 방식 | VRAM 요구 | 현실성 | 비고 |
|---|---|---|---|
| **DPO** | 6~8GB (3B 기준) | ✅ 현 환경 적합 | RTX 5060 Ti 8GB 이내, 가장 현실적 |
| **RLAIF → DPO** | 6~8GB (Claude API가 reward 담당) | ✅ 현 환경 적합 | 아래 별도 섹션 참조 |
| GRPO | 8~12GB | ⚠️ 경계선 | 그룹 샘플 생성 오버헤드, OOM 위험 |
| RLHF (PPO) | 14~18GB (reward model 없어도) | ❌ 현 환경 불가 | PPO 자체 구조 문제 — 아래 설명 참조 |

**권장 방식: DPO 또는 RLAIF → DPO**

```
feedback_pos + feedback_neg (각 20건 이상)  ←또는→  RLAIF 자동 생성 쌍
        ↓
build_dpo_dataset.py  — chosen/rejected 쌍 구성
        ↓
DPO 학습 (v11 어댑터 기반 연장학습)
        ↓
scenario_eval.py 15/18 합격 기준 평가
```

### 프로젝트 목적 부합도: ★★★★★ (완전 부합)

학습은 개발 환경(WSL2 + GPU)에서만 수행. 배포 모델은 기존과 동일하게 GGUF Q4_K_M 형태로 로컬 CPU 추론. 사용자에게 추가 인프라 요구 없음.

### 선행 조건 및 리스크

- **선행 조건**: 로그 수집 파이프라인 활성화 필요 (현재 배포판에서 비활성화 상태)
  - 배포판 로그 수집 없이도 개발 환경 로그(`training/log/`)만으로 20건 확보 가능
- **리스크**: v12 사례처럼 DPO 후 hallucination 악화 가능성 → `scenario_eval.py` 합격률 기준 필수
- **데이터 품질**: `review.py`로 검수된 피드백만 DPO에 사용할 것 (미검수 로그 혼입 금지)

---

### 1-A. RLAIF — Claude를 Reward Model로 활용 (RLHF 확장 방안)

#### 아이디어 정리

기존 RLHF가 "별도 reward model 학습 → VRAM 부족"으로 불가 판정을 받은 이유는  
reward model 자체의 VRAM 점유 때문이었다. Claude API를 외부 judge로 사용하면  
**별도 reward model을 학습하거나 로컬에 올릴 필요가 없어진다.**

#### 방식: RLAIF → DPO (권장)

PPO 기반의 온라인 강화학습을 쓰는 게 아니라,  
Claude가 채점한 선호 쌍(chosen/rejected)을 데이터로 만들어 기존 DPO에 투입하는 방식이다.  
이를 **RLAIF(Reinforcement Learning from AI Feedback)** 라 부르며 Anthropic Constitutional AI에서 사용한 접근법과 동일하다.

```
[학습 데이터 생성 파이프라인]

1. 시나리오 입력 준비
   입력 예: "나 요즘 좀 힘들어" (호감도: friendly 단계, 감정: sad)

2. 현재 모델(v11)로 응답 N개 생성 (N=4~8)
   응답 A: "그랬구나... 무슨 일 있었어?"
   응답 B: "힘드셨군요. 어떤 어려움이 있으신가요?"  ← AI투 표현
   응답 C: "힘들었어? 나한테 말해봐."
   응답 D: "힘드시다니 걱정이 되네요."  ← 존댓말 오염

3. Claude API 호출 — 각 응답 점수 채점 (0~10)
   채점 기준: 아래 루브릭 참조

4. 점수 기반 chosen/rejected 쌍 구성
   chosen: 응답 A or C  /  rejected: 응답 B or D

5. DPO 학습에 투입
   기존 feedback_pos/neg 데이터와 혼합 사용 가능
```

#### Claude 채점 루브릭 (Achat 특화)

```python
SCORING_PROMPT = """
너는 AI 캐릭터 대화 품질 평가 전문가다.
아래 기준으로 응답을 0~10점으로 채점해라.

[캐릭터 정보]
{character_desc}  # CH_Haru.yaml 핵심 항목 주입

[대화 맥락]
{context}  # 직전 3턴

[사용자 발화]
{user_input}

[평가할 응답]
{response}

[채점 기준]
- 캐릭터 말투 일관성: 규정된 말투·어조 유지 (0~3점)
- 한국어 순도: 한자·중국어·부자연스러운 영어 혼입 없음 (0~2점)
- AI투 표현 부재: "~군요", "~네요", "걱정이 되다" 류 없음 (0~2점)
- 맥락 이해도: 감정/호감도 단계 반영, 이전 발화 연계 (0~2점)
- 간결성: 불필요한 장황함 없음 (0~1점)

JSON만 반환: {"score": 8, "reason": "말투 일관성 양호, AI투 없음"}
"""
```

#### VRAM 관점에서 재검토

| 구성 요소 | PPO (기존 RLHF) | RLAIF → DPO |
|---|---|---|
| Policy model (3B, bfloat16) | ~6GB | ~6GB |
| Reference model (frozen) | ~6GB (동시 로드) | ~6GB (동시 로드) |
| Value network (critic) | ~1GB 추가 | 없음 |
| PPO rollout 버퍼 | ~2~4GB | 없음 |
| Reward model | ~6GB (로컬) → Claude API 시 0GB | 0GB |
| **합계** | **14~18GB** ← 불가 | **~8GB** ← 기존 DPO와 동일 |

**핵심**: Claude를 judge로 써도 PPO는 policy+ref+value를 동시에 메모리에 올리기 때문에  
여전히 14~18GB가 필요하다. VRAM 8GB 환경에서 PPO 자체가 불가한 것이지,  
reward model 문제만이 아니었다.

→ **결론: RLAIF는 PPO가 아닌 DPO와 결합해야 현 환경에서 실현 가능하다.**

#### 비용 추정 (Claude API)

| 항목 | 수량 | 토큰 | 비용 (Sonnet 기준 $3/MTok) |
|---|---|---|---|
| 시나리오당 응답 4개 채점 | 200 시나리오 | 약 400K tok | ~$1.2 |
| 월 1회 갱신 시 연간 | 12회 | 약 4.8M tok | ~$14.4 |

인간 레이블러 대비 비용이 극히 낮고, 24시간 자동화 가능.

#### 구현 스케치

```python
# scripts/rlaif_score.py
import anthropic, json

client = anthropic.Anthropic()

def score_response(character_desc, context, user_input, response) -> dict:
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=128,
        system="너는 AI 캐릭터 대화 품질 평가 전문가다.",
        messages=[{"role": "user", "content": SCORING_PROMPT.format(
            character_desc=character_desc,
            context=context,
            user_input=user_input,
            response=response,
        )}],
    )
    return json.loads(msg.content[0].text)

def build_rlaif_pairs(scenarios: list, model, n_samples=4) -> list:
    pairs = []
    for scenario in scenarios:
        responses = [model.generate(scenario["input"]) for _ in range(n_samples)]
        scores = [score_response(..., r) for r in responses]
        best = max(zip(responses, scores), key=lambda x: x[1]["score"])
        worst = min(zip(responses, scores), key=lambda x: x[1]["score"])
        if best[1]["score"] - worst[1]["score"] >= 2:  # 점수 차 임계값
            pairs.append({"chosen": best[0], "rejected": worst[0]})
    return pairs
```

#### RLAIF 데이터 생성 장점

- **feedback 로그 수집 없이도 진행 가능**: 시나리오만 있으면 됨
- **v12 실패 재발 방지**: 데이터 품질을 Claude가 사전 필터링
- **기준 명문화**: 루브릭이 코드로 고정되어 있어 일관성 확보
- **확장 용이**: 루브릭에 기준 추가/수정만으로 학습 방향 조정 가능

#### 주의사항

- Claude API 호출은 **개발 환경 전용** — 사용자 데이터(대화 로그)를 API에 전송해선 안 됨
- 시나리오는 `training/eval/scenario_eval.py` 기존 18개 + 신규 제작분 사용 (실제 사용자 발화 미사용)
- 채점 결과는 로컬에 캐싱 (`training/rlaif_cache/`) — 동일 시나리오 재채점 비용 절감

---

## 2. 클라우드 기반 로그 수집 서버 구축 (AWS / Azure, DW 고려)

### 계획 개요

배포된 Achat 클라이언트에서 대화 로그·피드백 데이터를 클라우드 서버로 수집,  
Data Warehouse에 적재해 모델 개선(DPO/RLAIF 학습 데이터 확보)에 활용하는 인프라 구축.  
클라우드는 학습/추론이 아닌 **수집·저장·분석 전용**으로 사용한다.

### 현재 상태

> 로드맵.md "반려/영구 보류" 항목:  
> **"사용자 로그 수집 서버 (LOG-1~5) — 보안 설계 미해결 (서버 공격 대응 방안 없음). 해결 방안 확보 전 보류"**

기술 스택 자체는 어렵지 않으나, **사용자 동의 · 익명화 · 보안** 세 가지가 해결되지 않으면 진행 불가.

### 실현 가능성: ★★★☆☆ (중간, 보안 설계가 선결 과제)

### 필수 해결 과제

#### 2-1. 사용자 동의 (Consent)

```
첫 실행 시 명시적 opt-in 팝업:
"대화 품질 개선을 위해 익명화된 로그를 수집합니다.
 동의하지 않아도 모든 기능을 사용할 수 있으며, 언제든 철회할 수 있습니다."
```

- 동의한 사용자만 업로드, 언제든 철회 가능
- `preferences.json`에 `data_consent: bool` 저장
- 동의 철회 시 기존 서버 데이터 삭제 요청 엔드포인트 필요

#### 2-2. 비식별화 전략 선택

업로드 전 **로컬에서** 전처리 완료 후 전송 — 원본 로그는 절대 서버로 보내지 않는다.  
아래 7가지 비식별화 방식 중 Achat 대화 로그에 적합한 조합을 선택한다.

---

##### 방식 1 — 마스킹 (Masking)

**원리**: 발화 텍스트에서 민감 패턴(이름, 전화번호, 주소 등)을 감지해 `[NAME]`, `[PHONE]` 등 고정 토큰으로 대체. 원본 복원 불가.

```
"내 이름은 이민준이고 서울 강남구에 살아" → "내 이름은 [NAME]이고 [PLACE]에 살아"
```

**Achat 부합도: ★★★★☆ (필수 적용, 단 한계 있음)**
- ✅ 구현 단순, 규칙 기반으로 외부 의존 없이 클라이언트에서 실행 가능
- ✅ 발화 텍스트의 1차 방어선으로 반드시 필요
- ⚠️ 한국어 NER(고유명사 인식) 정확도 문제 — 3B 로컬 모델 없이 규칙 기반으로 하면 누락 위험
- ⚠️ "오늘 민준이랑 카페 갔어" 같은 간접 언급은 감지 어려움

---

##### 방식 2 — 가명처리 (Pseudonymization)

**원리**: 식별자(ID, 계정명 등)를 SHA-256 같은 단방향 해시 함수로 대체. 동일 입력 → 동일 출력으로 일관성은 유지하되 원본 역추적 불가.

```
char_id: "CH_Haru"   → sha256("CH_Haru")[:8] = "a3f8b2c1"
session_id: "sess_42" → sha256("sess_42")[:8] = "9e1d4f7a"
```

**Achat 부합도: ★★★★★ (필수 적용)**
- ✅ char_id, session_id에 즉시 적용 가능, 구현 비용 없음
- ✅ 서버에서 동일 세션의 로그를 연결·분석하는 데 일관성 유지
- ✅ Achat은 별도 user_id가 없어 개인 역추적 경로 자체가 제한적
- ⚠️ 발화 텍스트 내용 자체는 처리 불가 — 마스킹과 병행 필수

---

##### 방식 3 — 일반화 (Generalization)

**원리**: 구체적인 값을 더 넓은 범주로 치환. 정밀도를 낮춰 개인 특정 가능성을 줄임.

```
timestamp: "2026-05-07 15:32:11" → "2026-05-07"   (시각 제거)
affection:  72                   → "friendly"      (수치 → tier명)
turn_count: 47                   → "40~49"         (구간 표현)
```

**Achat 부합도: ★★★★★ (필수 적용)**
- ✅ 메타데이터 전반에 부담 없이 적용 가능
- ✅ timestamp 일반화만으로도 행동 패턴 추적 위험 크게 감소
- ✅ affection, mood 같은 상태값은 tier/이름으로 변환해도 학습 데이터로서 가치 유지
- ❌ 텍스트 발화 내용에는 직접 적용 불가

---

##### 방식 4 — 토큰화 / Vault (Tokenization)

**원리**: 민감값을 무작위 토큰으로 대체하고, 원본-토큰 매핑 테이블을 별도 안전 저장소(Vault)에 보관. 권한 있는 주체만 역참조 가능. PCI DSS의 신용카드 번호 보호에 주로 사용.

```
"홍길동" → TOKEN_0x8A2F   (Vault: TOKEN_0x8A2F ↔ "홍길동" 보관)
```

**Achat 부합도: ★☆☆☆☆ (부적합, 과도한 설계)**
- ❌ 대화 텍스트 전체는 토큰화 단위로 처리 불가
- ❌ Achat은 user_id 자체가 없어 Vault가 보호할 식별자가 마땅치 않음
- ❌ Vault 서버 운영 비용·복잡도가 프로젝트 규모 대비 과도
- 가명처리(방식 2)로 동일한 목적을 더 단순하게 달성 가능

---

##### 방식 5 — k-익명성 (k-Anonymity)

**원리**: 데이터셋에서 어떤 레코드든 동일한 준식별자(quasi-identifier) 조합을 가진 레코드가 최소 k개 이상 존재하도록 보장. 특정 개인을 k명 중 한 명으로만 좁힐 수 있게 만듦.

```
나이+성별+지역 조합이 동일한 레코드가 최소 5개(k=5) 이상 → 5-익명성 달성
```

**Achat 부합도: ★★☆☆☆ (제한적 적용)**
- ⚠️ 구조화된 정형 데이터에 적합 — 대화 텍스트(비정형)에는 직접 적용 어려움
- ✅ 메타데이터(mood, affection_tier, date) 조합에는 부분 적용 가능
- ❌ 전체 로그 파이프라인에 도입하기엔 구현 복잡도 대비 효과 불명확
- 초기 단계에서는 마스킹 + 가명처리 + 일반화 조합으로 충분

---

##### 방식 6 — 차등 프라이버시 (Differential Privacy)

**원리**: 쿼리 결과나 모델 파라미터에 수학적으로 보정된 노이즈(Laplace/Gaussian 분포)를 추가. "특정 개인의 데이터가 포함되든 않든 결과가 거의 동일하게 보이도록" 보장. ε(epsilon)으로 프라이버시 보장 강도 표현(작을수록 강함).

```
집계 통계: 평균 턴 수 = 23.4 → 23.4 + N(0, σ²) = 24.1  (노이즈 추가)
```

**Achat 부합도: ★☆☆☆☆ (텍스트 로그에 부적합)**
- ❌ 대화 텍스트에 노이즈 추가 = 의미 파괴 → 학습 데이터로서 가치 소멸
- ✅ 집계 통계(평균 loss, 평균 응답 길이 등) OPS 컬렉션 수치에는 적용 가능
- ✅ 학습 시 DP-SGD(gradient에 노이즈 추가)로 별도 적용 가능 — 로그 전송 비식별화와는 다른 문제
- Dialogue 컬렉션 텍스트 처리 방식으로는 적합하지 않음

---

##### 방식 7 — 합성 데이터 생성 (Synthetic Data Generation)

**원리**: 실제 데이터의 통계적 패턴·분포를 학습해 원본과 유사하지만 실제 개인과 무관한 가짜 데이터를 생성. GAN, VAE, LLM 프롬프팅 방식 등.

```
실제 로그: "오늘 너무 힘들었어, 위로해줘" (사용자 A 발화)
합성 데이터: "요즘 많이 지쳐있어, 기운이 없어" (유사 패턴의 가상 발화 생성)
```

**Achat 부합도: ★★★☆☆ (RLAIF 맥락에서 대안으로 유효)**
- ✅ 실제 사용자 발화를 서버에 올리지 않아도 되므로 프라이버시 문제 원천 차단
- ✅ RLAIF 파이프라인(Claude가 시나리오 생성 → 응답 채점)과 철학적으로 동일
- ❌ 합성 데이터가 실제 사용자 행동의 엣지 케이스·분포를 반영하지 못할 수 있음
- ❌ 클라이언트에서 합성 생성 시 추가 LLM 호출 비용 발생
- 로그 수집 대신 **RLAIF로 대체하는 선택지**로 볼 수 있음

---

##### Achat 권장 비식별화 조합

| 방식 | 적용 대상 | 적용 여부 |
|---|---|---|
| 마스킹 | 발화 텍스트 내 고유명사 | ✅ 필수 |
| 가명처리 | char_id, session_id | ✅ 필수 |
| 일반화 | timestamp, affection 수치, turn_count | ✅ 필수 |
| k-익명성 | 메타데이터 조합 | ⚠️ 선택 (중기 이후) |
| 합성 데이터 | 로그 수집 자체를 대체 | ⚠️ RLAIF 선택 시 |
| 토큰화/Vault | — | ❌ 부적합 |
| 차등 프라이버시 | 텍스트 로그 | ❌ 부적합 (OPS 수치에만 선택 적용) |

```python
# scripts/anonymize_log.py — 권장 조합 구현 예시
def anonymize(log: dict) -> dict:
    # 마스킹: 발화 텍스트
    log["user"]       = mask_named_entities(log["user"])
    log["assistant"]  = mask_named_entities(log["assistant"])
    # 가명처리: 식별자
    log["char_id"]    = sha256(log["char_id"].encode())[:8]
    log["session_id"] = sha256(log["session_id"].encode())[:8]
    # 일반화: 메타데이터
    log["timestamp"]  = log["timestamp"][:10]               # 날짜만
    log["affection"]  = affection_to_tier(log["affection"]) # 72 → "friendly"
    log["turn_count"] = f"{(log['turn_count'] // 10) * 10}~{(log['turn_count'] // 10) * 10 + 9}"
    return log
```

#### 2-3. 전송 보안

- HTTPS only + 클라이언트 발급 JWT (설치 시 1회 발급, 로컬 저장)
- 업로드 엔드포인트는 쓰기 전용, 읽기·삭제 불가 (append-only)
- Rate limiting: 클라이언트 토큰당 1일 N건
- DDoS 대응: Cloudflare 프록시 앞단 배치

### 아키텍처

#### AWS 구성 (권장 — 서버리스, 운영 부담 최소)

```
[Achat 클라이언트]
      │  익명화 후 배치 업로드 (1일 1회, 세션 종료 시)
      ▼
[API Gateway + Lambda]  ← 수집 전용 엔드포인트, 서버리스
      │  parquet 변환 후 적재
      ▼
[S3 (raw zone)]         ← 원본 보존, 버전 관리
      │
      ▼
[AWS Glue (ETL)]        ← 카테고리 분류, 품질 필터링
      │
      ▼
[S3 (curated zone)]     ← 정제된 데이터 (feedback_pos / feedback_neg 분리)
      │
      ▼
[Amazon Athena]         ← SQL 쿼리·분석 (서버리스, 사용량 과금)
      │
      ▼
[학습 파이프라인 (로컬)]  feedback_pos/neg 다운로드 → DPO / RLAIF 학습
```

#### Azure 구성 (대안)

```
API Management → Azure Functions → Azure Blob Storage → Synapse Analytics
```

---

### 컬렉션 구조 설계

#### 컬렉션 분류

```
DW
├── OPS 컬렉션          ← 시스템 운영 로그 (사용자 발화 없음)
│   ├── /operation      ← LLM 작동 로그 (추론 시간, 토큰 수, 오류 등)
│   └── /training       ← 학습 로그 (epoch, loss, eval 점수 등)
│
└── Dialogue 컬렉션     ← LLM 대화 로그 (익명화 필수)
    ├── /daily          ← 일반 일상 대화
    ├── /emotion        ← 감정 반응 대화
    ├── /advice         ← 조언·도움 요청 대화  ⚠️ 강화학습 활용 가능성 높음
    ├── /feedback_neg   ← 부정적 피드백        ⚠️ 강화학습 활용 가능성 높음
    └── /feedback_pos   ← 긍정적 피드백        ⚠️ 강화학습 활용 가능성 높음
```

#### S3 경로 설계 (prefix 구조)

```
s3://achat-logs/
  ├── raw/                              ← 적재 직후 원본 (익명화 완료본)
  │   ├── ops/
  │   │   ├── operation/YYYY-MM-DD/
  │   │   └── training/YYYY-MM-DD/
  │   └── dialogue/
  │       ├── daily/YYYY-MM-DD/
  │       ├── emotion/YYYY-MM-DD/
  │       ├── advice/YYYY-MM-DD/        ← ⚠️ QC 대기
  │       ├── feedback_neg/YYYY-MM-DD/  ← ⚠️ QC 대기
  │       └── feedback_pos/YYYY-MM-DD/  ← ⚠️ QC 대기
  │
  └── curated/                          ← QC 통과분만 (학습 파이프라인 입력)
      ├── ops/
      └── dialogue/
          ├── advice/
          ├── feedback_neg/
          └── feedback_pos/
```

#### 각 컬렉션 상세

| 컬렉션 | 경로 | 수집 내용 | 품질 기준 | 학습 활용 |
|---|---|---|---|---|
| OPS / operation | `/operation` | 추론 시간, 토큰 수, 오류 코드, 백엔드 구분 | N/A (수치 데이터) | 모니터링·이상 감지 |
| OPS / training | `/training` | epoch, train/eval loss, eval 점수, 채택 여부 | N/A (수치 데이터) | 학습 이력 관리 |
| Dialogue / daily | `/daily` | 일상 주제 대화 턴 | 기본 (AI투·한국어 체크) | SFT 보조 데이터 |
| Dialogue / emotion | `/emotion` | 감정 유발 상황 대화 | 기본 | SFT 감정 카테고리 |
| Dialogue / advice | `/advice` | 조언·도움 요청 응답 | **엄격** | DPO chosen 후보 |
| Dialogue / feedback_neg | `/feedback_neg` | 사용자 부정 피드백 발화·응답 쌍 | **엄격** | DPO rejected 후보 |
| Dialogue / feedback_pos | `/feedback_pos` | 사용자 긍정 피드백 발화·응답 쌍 | **엄격** | DPO chosen 후보 |

#### 로컬 training/log/ 와의 매핑

현재 `ConversationLogger`가 수집하는 로컬 카테고리와 DW 경로의 대응 관계.

| 로컬 카테고리 | DW 컬렉션 / 경로 | 비고 |
|---|---|---|
| `daily.jsonl` | Dialogue / `/daily` | 직접 대응 |
| `emotion.jsonl` | Dialogue / `/emotion` | 직접 대응 |
| `advice.jsonl` | Dialogue / `/advice` | 직접 대응, QC 엄격 |
| `feedback_neg.jsonl` | Dialogue / `/feedback_neg` | 직접 대응, QC 엄격 |
| `feedback_pos.jsonl` | Dialogue / `/feedback_pos` | 직접 대응, QC 엄격 |
| `memory.jsonl` | — | DW 미수집 (로컬 VDB 관리 영역) |
| `persona.jsonl` | — | DW 미수집 (캐릭터 고정 설정 영역) |
| LLM 추론 메타 | OPS / `/operation` | 현재 미수집 → 별도 계측 필요 |
| `lora_train.py` 결과 | OPS / `/training` | 현재 로컬 only → 업로드 스크립트 필요 |

#### ⚠️ advice / feedback_neg / feedback_pos — 엄격 품질 검사

이 세 카테고리는 강화학습(DPO/RLAIF) policy 작성에 직접 투입되므로, 저품질 데이터 혼입이 모델 품질 저하로 직결된다. raw → curated 이동 시 아래 단계를 모두 통과해야 한다.

```
[raw 적재]
    │
    ▼
1단계: 자동 필터 (Glue ETL 또는 Lambda)
    - AI투 표현 패턴 감지 (ai_tell_checker 기준 유용어 목록)
    - 한국어 순도 검사 (한자·중국어 문자 포함 시 reject)
    - 응답 길이 범위 검사 (너무 짧거나 장황한 응답 제외)
    - 중복 제거 (Jaccard 유사도 0.55 이상이면 최신 건만 유지)
    │
    ▼
2단계: Claude judge 자동 채점 (RLAIF 파이프라인과 동일 루브릭)
    - 점수 7점 미만 → rejected 버킷 이동 (학습 제외)
    - 점수 7점 이상 → 3단계로
    │
    ▼
3단계: 수동 검수 (review.py 기반)
    - y(승인) / n(재분류) / d(삭제) 처리
    - 검수자 승인 완료 시에만 curated/ 이동
    │
    ▼
[curated 적재] → 학습 파이프라인 입력
```

---

#### AWS vs Azure 선택 기준

| 항목 | AWS | Azure |
|---|---|---|
| 서버리스 성숙도 | Lambda 안정적, 문서 풍부 | Functions 유사하나 cold start 더 김 |
| 소규모 비용 | Lambda + S3 무료 티어 적극적 | 무료 티어 제한적 |
| DW 쿼리 | Athena (per-query 과금) | Synapse (DWU 예약 비용 발생) |
| 한국 리전 | ap-northeast-2 (서울) | Korea Central |
| **결론** | **소규모 초기 단계에 유리** | 기업 규모로 성장 시 재검토 |

### DW 필요성 검토

DW(Data Warehouse)는 데이터가 **10만 건 이상** 누적된 후에야 쿼리 성능 이점이 생긴다.  
초기에는 S3 + Athena(서버리스 쿼리)로 충분하며, DW 도입은 사용자 규모를 보고 결정한다.

| 단계 | 누적 로그 수 | 권장 스택 |
|---|---|---|
| 초기 | ~1,000건 | S3 + Athena (월 $1 미만) |
| 중기 | 1만~10만 건 | S3 + Athena + Glue ETL |
| 성장기 | 10만 건 이상 | Redshift Serverless 또는 Synapse |

### 비용 추정 (AWS, 초기 단계)

| 항목 | 월 비용 |
|---|---|
| Lambda (수집 엔드포인트) | $0 (월 100만 건 무료 티어) |
| S3 저장 (1GB 기준) | $0.023 |
| API Gateway | $0 (월 100만 건 무료 티어) |
| Athena 쿼리 (10GB 스캔) | $0.50 |
| **합계** | **~$1/월** (초기 단계) |

### 프로젝트 목적 부합도: ★★★☆☆ (opt-in 기본값 유지 시)

- 수집 **기본값은 off (opt-out)**으로 설계 — 프로젝트의 "텔레메트리 없음" 원칙 유지
- 동의한 사용자의 데이터만 수집 → 모델 개선에 직접 기여
- 로컬 추론·오프라인 동작에는 영향 없음

### 권장 진행 순서

1. `scripts/anonymize_log.py` 구현 → 로컬에서 익명화 결과 품질 검증
2. opt-in 동의 UI 구현 (`preferences.json` `data_consent` 연동)
3. AWS Lambda + API Gateway 수집 엔드포인트 MVP 구축
4. S3 적재 + Athena 쿼리 파이프라인 연결
5. 누적 1,000건 후 feedback_pos/neg 추출 → DPO 학습 데이터로 활용
6. 규모 성장 시 Glue ETL + Redshift 전환 검토

---

### DW의 CRUD는 일반 DB와 다르다

DW는 OLAP(분석) 최적화 시스템으로, 기본 설계 철학이 **"대량 적재 + 대용량 읽기"** 다.  
일반 RDBMS와 달리 U(수정), D(삭제)가 제한적이거나 파일 단위로 동작한다.

| 동작 | 일반 RDBMS | S3 + Athena | Redshift |
|---|---|---|---|
| **C (적재)** | INSERT row | S3에 parquet 파일 업로드 | INSERT / COPY |
| **R (읽기/추출)** | SELECT | Athena SQL → 결과 다운로드 | SELECT |
| **U (수정)** | UPDATE row | ❌ 기본 불가 (파일 단위) | ✅ 가능하나 느림 |
| **D (삭제)** | DELETE row | ❌ 기본 불가 (파일 단위) | ✅ 가능 |

#### 데이터 가져와서 학습 파이프라인에 쓰는 것 (R) — 완전히 가능

```python
# 방법 1: boto3로 S3에서 직접 다운로드
import boto3, pandas as pd

s3 = boto3.client("s3")
s3.download_file("achat-logs", "curated/feedback_pos/2026-05.parquet", "local.parquet")
df = pd.read_parquet("local.parquet")
# → DPO chosen/rejected 쌍으로 가공 후 학습 투입
```

```python
# 방법 2: Athena SQL로 조건 필터링 후 추출
import boto3

athena = boto3.client("athena", region_name="ap-northeast-2")
athena.start_query_execution(
    QueryString="""
        SELECT * FROM feedback
        WHERE category = 'feedback_pos'
          AND date >= '2026-04-01'
    """,
    ResultConfiguration={"OutputLocation": "s3://achat-logs/query-results/"},
)
# 결과 parquet 다운로드 → 로컬 학습 데이터로 사용
```

#### 수정 (U) — 로그 특성상 거의 불필요

로그 데이터는 사후 수정할 일이 거의 없다. `review.py` 검수 결과 반영 시에도 기존 행을 고치는 것이 아니라 `reviewed: true` 같은 새 컬럼을 추가하는 방식이 DW 설계에 더 적합하며 이력 추적도 용이하다.

#### 삭제 (D) — 가장 복잡한 부분, 사전 설계 필요

사용자가 동의 철회 시 해당 사용자 데이터를 삭제해야 하는데, S3+Athena 기본 구성은 파일 단위 처리라 특정 사용자의 행만 골라 삭제하기가 복잡하다. 해결 방법은 두 가지다.

**옵션 A: Apache Iceberg 포맷 사용 (권장)**

S3 위에 Iceberg 테이블 레이어를 올리면 row-level DELETE가 가능해진다.  
AWS Glue + Athena가 Iceberg를 네이티브 지원하므로 별도 인프라 추가 없이 적용 가능.

```sql
-- Athena에서 직접 실행 가능 (Iceberg 테이블 한정)
DELETE FROM achat_logs WHERE user_hash = 'a3f8b2c1';
```

**옵션 B: 익명화 완벽 처리 → 삭제 자체를 무의미하게**

익명화가 완벽하면 `user_hash`로 원래 사용자를 역추적할 수 없으므로, 삭제 요청이 들어와도 "이미 개인 식별 불가 상태"로 응답 가능. 단, 사용자가 자신의 hash를 알 방법이 없으므로 삭제 요청과 실제 데이터를 연결하는 별도 메커니즘이 필요하다(예: 클라이언트 로컬에 hash 저장 후 제출).

#### 결론

- **데이터 추출·파이프라인(R)**: Python + boto3로 완전 자동화 가능, 표준 패턴
- **수정(U)**: 새 컬럼 추가 방식으로 대체, 행 수정 불필요
- **삭제(D)**: 처음부터 **Iceberg 포맷**으로 테이블 설계하거나, 익명화 수준을 높여 삭제 필요성 자체를 없애는 방향으로 사전 설계 필요

---

## 3. LangChain & LangGraph로의 교체 고려

### 계획 개요

현재 커스텀 파이프라인(`agent/core.py`, `conversation/core/router.py`, `prompt_build.py`, `memory/` 등)을  
LangChain(LLM 추상화 + 도구 체인) / LangGraph(상태 기반 멀티에이전트 그래프)로 교체.

### 실현 가능성: ★★☆☆☆ (낮음, 권장하지 않음)

### 프로젝트 목적 부합도: ★★☆☆☆ (경량화 목표와 충돌)

교체를 권장하지 않는 이유를 구체적으로 정리한다.

#### 4-1. 의존성 무게

| 항목 | 현재 Achat | LangChain 추가 시 |
|---|---|---|
| 핵심 패키지 수 | ~15개 | +100개 이상 (langchain-core, langchain-community, langchain-openai 등) |
| 설치 용량 | ~150MB | +300~500MB |
| Windows 배포 | PyInstaller 단일 exe | langchain 동적 import 충돌 빈발 |

> `pyproject-deploy.toml`에서 whoosh도 삭제한 이유가 의존성 절감이었다.  
> LangChain 추가는 그 방향과 정반대다.

#### 4-2. 메모리 시스템 비호환

Achat의 3계층 메모리(단기 슬라이딩 윈도우 + 중기 session_context + 장기 ChromaDB VDB)는  
LangChain의 `ConversationBufferMemory` / `VectorStoreRetrieverMemory` 추상화와 구조가 맞지 않는다.

- LangChain 메모리는 단일 대화 히스토리 가정
- Achat은 affection 기반 eviction, TTL, quota, dedup, mood 연동이 메모리 쓰기/읽기에 통합됨
- 마이그레이션 시 이 로직을 LangChain 위에 재구현해야 하며, 오히려 복잡도가 증가

#### 4-3. llama-cpp-python 연동 품질

LangChain의 `LlamaCpp` 래퍼는 존재하지만:
- `n_ctx`, `repeat_penalty`, `repeat_last_n` 등 현재 튜닝된 파라미터 노출이 불완전
- streaming 응답과 QML LLMWorker 연동 시 시그널 체계 재설계 필요
- 업스트림 LangChain 업데이트로 인한 API 파손 위험 (과거 0.x → 1.x 대규모 브레이킹 체인지 선례)

#### 4-4. LangGraph는 현재 사용 사례에 과스펙

LangGraph는 **멀티에이전트 협업 + 복잡한 분기 조건 + 사람 개입(human-in-the-loop)**이 필요한 시스템용.  
Achat의 현재 구조는 단일 에이전트, 선형 파이프라인으로 LangGraph의 이점이 거의 없다.

```
현재 Achat 흐름:
user → router.handle_turn() → (RAG → prompt_build → LLM → state update → memory) → response

LangGraph가 유리한 구조:
user → [의도 분류 노드] → [분기: 대화|검색|함수] → [병렬 서브에이전트] → [통합 응답 노드]
```

멀티캐릭터 그룹 대화 기능이 추가될 경우 LangGraph 재검토 가치 있음.

### 부분 도입 가능한 영역

전면 교체 대신 아이디어만 차용하는 방식이 현실적이다.

| LangChain 개념 | Achat 적용 아이디어 | 구현 방식 |
|---|---|---|
| Tool 추상화 | `tools/base.py` `BaseTool` 이미 유사 구조 | 현행 유지 |
| Prompt Template | `prompt_build.py` Layer 시스템 | 현행 유지 |
| Streaming | `LLMWorker` QThread | 현행 유지 |
| LCEL 체인 | `router.handle_turn()` 파이프라인 | 현행 유지 |

**결론**: LangChain/LangGraph 전면 교체는 비용 대비 이득이 없다.  
현재 커스텀 파이프라인이 이미 충분히 모듈화되어 있고, 배포 경량화 요건과 충돌한다.

---

## 종합 우선순위

| 항목 | 실현 가능성 | 목적 부합도 | 권장 시점 |
|---|---|---|---|
| **강화학습 (DPO)** | ★★★★☆ | ★★★★★ | feedback 20건 이상 누적 후 즉시 진행 |
| **RLAIF → DPO (Claude judge)** | ★★★★☆ | ★★★★★ | 시나리오 준비 완료 후 (피드백 로그 불필요) |
| **클라우드 로그 수집 서버 (AWS)** | ★★★☆☆ | ★★★☆☆ | 익명화 모듈 + opt-in UI 완성 후 |
| **LangChain/LangGraph 전환** | ★★☆☆☆ | ★★☆☆☆ | 권장하지 않음 (멀티에이전트 확장 시 재검토) |
