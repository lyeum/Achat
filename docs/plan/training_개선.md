# 학습 개선 구현 계획

> 참조: [training/학습.md](../../training/학습.md) § 7. 학습 개선안
> 우선순위: 7-2 EWC → 7-3 카테고리 가중치 → 7-1 Loss 마스킹 → 7-4 KL (보류)

---

## 1. EWC 다단계 학습 (`training/ewc.py` 신설)

### 1-1. Fisher 계산 (`compute_fisher`)

```
입력:
  model_name     — Qwen/Qwen2.5-3B-Instruct
  adapter_path   — output/LoRA_vN/adapter
  data_dir       — training/data
  out_dir        — output/LoRA_vN (fisher.pt, ref_params.pt 저장 위치)
  n_samples      — 500 (많을수록 정확, 느림. 500이면 ~5분 내외)
  max_length     — 512

처리 순서:
  1. base model + adapter 로드 (bfloat16)
  2. 모든 파라미터 requires_grad=False
  3. "lora_" 포함 파라미터만 requires_grad=True (LoRA 파라미터만 대상)
  4. ref_params = {name: param.data.clone()} 저장 (기준 가중치)
  5. training/data에서 n_samples건 랜덤 샘플링
  6. 각 샘플: forward → loss.backward() → param.grad² 누적
     OOM/오류 샘플은 skip
  7. 누적값 / n_processed → 평균 Fisher 대각
  8. fisher.pt, ref_params.pt 저장

저장 형식:
  fisher.pt     = {param_name (str): torch.Tensor (같은 shape as param)}
  ref_params.pt = {param_name (str): torch.Tensor (같은 shape as param)}
  → 두 파일 모두 named_parameters() 기준 키 사용 (naming mismatch 없음)

CLI:
  uv run python training/ewc.py \
    --model Qwen/Qwen2.5-3B-Instruct \
    --adapter output/LoRA_v6/adapter \
    --data_dir training/data \
    --out output/LoRA_v6 \
    --n_samples 500
```

---

### 1-2. EWC 패널티 클래스 (`EWCPenalty`)

```
__init__(fisher_path, ref_params_path, lambda_, device):
  - fisher.pt, ref_params.pt 로드 → self.fisher, self.ref_params
  - 둘 다 device로 이동

penalty(model) → torch.Tensor:
  loss = 0
  for name, param in model.named_parameters():
    if not param.requires_grad: skip
    if name not in self.fisher: skip   ← LoRA 외 파라미터 자동 제외
    f   = self.fisher[name]
    ref = self.ref_params[name]
    loss += (f * (param.float() - ref.float()).pow(2)).sum()
  return (lambda_ / 2) * loss
```

---

### 1-3. EWCTrainer (`lora_train.py` 내 클래스 추가)

```python
class EWCTrainer(Trainer):
    def __init__(self, ewc_penalty=None, **kwargs):
        super().__init__(**kwargs)
        self.ewc_penalty = ewc_penalty

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        result = super().compute_loss(model, inputs, return_outputs=True, **kwargs)
        loss, outputs = result
        if self.ewc_penalty is not None:
            loss = loss + self.ewc_penalty.penalty(model)
        return (loss, outputs) if return_outputs else loss
```

---

### 1-4. `lora_train.py` 인자 추가

| 인자 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `--ewc_fisher` | str | None | fisher.pt 경로 |
| `--ewc_ref_params` | str | None | ref_params.pt 경로 |
| `--ewc_lambda` | float | 0.0 | EWC 강도 (0이면 비활성) |

```python
# main() 내 처리
ewc_penalty = None
if args.ewc_lambda > 0:
    assert args.ewc_fisher and args.ewc_ref_params, "--ewc_fisher, --ewc_ref_params 필수"
    from training.ewc import EWCPenalty
    ewc_penalty = EWCPenalty(
        fisher_path=ROOT / args.ewc_fisher,
        ref_params_path=ROOT / args.ewc_ref_params,
        lambda_=args.ewc_lambda,
        device="cuda" if use_gpu else "cpu",
    )

# Trainer → EWCTrainer로 교체
trainer = EWCTrainer(ewc_penalty=ewc_penalty, ...)
```

---

## 2. 카테고리 가중치 샘플링 (`dataset.py` 수정)

### 2-1. `load_jsonl_files` 시그니처 변경

```python
def load_jsonl_files(
    data_dir: Path,
    max_samples: int = -1,
    seed: int = 42,
    category_weights: dict[str, float] | None = None,  # 추가
) -> list[dict]:
```

### 2-2. 카테고리 가중치 적용 로직

```
기존 records 로드 완료 후 (max_samples 적용 이후):

category_weights가 있으면:
  1. records를 category 필드 기준으로 그룹화
  2. 가중치 없는 카테고리는 그대로 유지
  3. weight > 1.0인 카테고리:
       n_target = round(len(cat_records) * weight)
       full_copies = n_target // len(cat_records)
       remainder   = n_target % len(cat_records)
       result = cat_records * full_copies + sample(cat_records, remainder)
  4. weight < 1.0인 카테고리:
       n_target = max(1, round(len(cat_records) * weight))
       result = sample(cat_records, n_target)
  5. 전체 shuffle(seed=seed) 후 반환

주의: max_samples=-1일 때도 category_weights 적용 가능
```

### 2-3. `lora_train.py` 인자 추가

```
--category_weights  str  None  카테고리별 가중치 JSON
                                예: '{"affection": 2.0, "memory_ref": 1.5}'
```

```python
# main() 내 처리
import json as _json
category_weights = _json.loads(args.category_weights) if args.category_weights else None
raw_ds = load_training_data(..., category_weights=category_weights)
```

---

## 3. ~~Assistant 토큰 마스킹~~ ✅ 완료 (lora_train.py v7~)

### 3-1. 마스킹 방식

```
Qwen2.5 ChatML 포맷 기준:
  <|im_start|>system\n...<|im_end|>\n
  <|im_start|>user\n...<|im_end|>\n
  <|im_start|>assistant\n[여기만 학습]<|im_end|>\n

labels 처리:
  - 전 구간 기본값: -100 (loss 계산 제외)
  - <|im_start|>assistant\n 이후 ~ <|im_end|> 이전 구간만 input_ids 값으로 세팅
  - 멀티턴 대화 시 각 assistant 구간 반복 적용
```

### 3-2. 구현 위치

`dataset.py`의 `apply_chat_template` 또는 `lora_train.py`의 `tokenize_dataset`에서 처리.

```python
def mask_non_assistant_labels(input_ids: list[int], tokenizer) -> list[int]:
    """assistant 응답 구간만 labels 활성화, 나머지는 -100."""
    labels = [-100] * len(input_ids)
    # assistant 시작 토큰 시퀀스 찾기
    # Qwen2.5: "<|im_start|>assistant\n" = tokenizer.encode("<|im_start|>assistant\n")
    asst_start_ids = tokenizer.encode("<|im_start|>assistant\n", add_special_tokens=False)
    end_id = tokenizer.encode("<|im_end|>", add_special_tokens=False)[0]

    i = 0
    while i < len(input_ids):
        # assistant 시작 위치 탐색
        if input_ids[i:i+len(asst_start_ids)] == asst_start_ids:
            i += len(asst_start_ids)
            # <|im_end|> 전까지 labels 활성화
            while i < len(input_ids) and input_ids[i] != end_id:
                labels[i] = input_ids[i]
                i += 1
        else:
            i += 1
    return labels
```

### 3-3. `lora_train.py` 인자 추가

```
--mask_non_assistant  store_true  False  assistant 외 구간 labels=-100 마스킹
```

---

## 4. 전체 다단계 워크플로우

```
[1단계 — vN 단일 학습]
  lora_train.py --data_dir training/data --output_dir output/LoRA_vN
                --epochs 6 --max_samples -1 --eval_split 0.1

[2단계 — Fisher 계산]
  ewc.py --adapter output/LoRA_vN/adapter
         --data_dir training/data
         --out output/LoRA_vN

[3단계 — eval 테스트로 약점 파악]
  eval/ai_tell_checker.py, memory_test.py, 직접 대화 테스트
  → "affection 응답이 단조로움", "memory_ref 반응이 약함" 등 확인

[4단계 — vN+1 학습 (EWC + 카테고리 가중치)]
  lora_train.py --data_dir training/data --output_dir output/LoRA_vN+1
                --ewc_fisher output/LoRA_vN/fisher.pt
                --ewc_ref_params output/LoRA_vN/ref_params.pt
                --ewc_lambda 0.5
                --category_weights '{"affection": 2.0}'
                --epochs 6 --max_samples -1 --eval_split 0.1

[5단계 — 반복]
  vN+1 Fisher 계산 → 테스트 → vN+2 학습 ...
```

---

## 5. 파일별 변경 요약

| 파일 | 변경 내용 |
|---|---|
| `training/ewc.py` | **신설** — Fisher 계산 CLI + `EWCPenalty` 클래스 |
| `training/lora_train.py` | `EWCTrainer` 클래스 추가, `--ewc_*`, `--category_weights`, `--mask_non_assistant` 인자 추가 |
| `training/dataset.py` | `load_jsonl_files` / `load_training_data`에 `category_weights` 파라미터 추가, `mask_non_assistant_labels` 함수 추가 |
