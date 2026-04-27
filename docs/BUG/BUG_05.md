# BUG-07 — DEP-1 병합 중 OOM (Out of Memory) 크래시

> 발생일: 2026-04-27
> 단계: 5단계 배포 파이프라인 — DEP-1 (LoRA v11 병합)
> 환경: WSL2 (Ubuntu), RAM 8GB, Swap 2GB

---

## 증상

```bash
uv run python scripts/merge_lora.py \
  --adapter output/LoRA_v11/adapter \
  --output_dir output/merged_v11
```

실행 중 시스템 전체가 응답 불능 상태(hang)에 빠지고 강제 재부팅이 필요했음.
프로세스 로그 없이 커널 OOM killer에 의해 종료된 것으로 추정.

---

## 원인 분석

| 항목 | 수치 |
|---|---|
| 시스템 RAM | 8GB |
| WSL2 오버헤드 | ~1~1.5GB |
| Python/PyTorch 런타임 | ~0.5GB |
| 베이스 모델 로드 (float16) | ~6GB |
| safetensors 저장 피크 | +1~2GB |
| **합산 피크 추정** | **~8.5~9.5GB** |
| 당시 가용 Swap | 2GB |

float16 기준 Qwen2.5-3B 모델 로드에 ~6GB, `save_pretrained()` 직전 텐서 복사 시 피크가 추가로 발생함.
WSL2는 호스트 메모리를 공유하므로 Linux 네이티브 대비 가용 메모리가 더 적음.

---

## 해결 과정

### 1. merge_lora.py 코드 개선 (사전 완화)

- `torch_dtype=torch.float16` kwarg 수정 (기존 오타: `dtype=`)
- `save_pretrained(..., safe_serialization=True, max_shard_size="2GB")` 추가 — 저장 시 2GB 단위 샤드 분할로 피크 메모리 절감
- `_check_memory()` 함수 추가 — psutil로 실행 전 가용 RAM+Swap 합산 확인, 7GB 미만 시 경고 + swap 확장 안내 출력

### 2. Swap 임시 확장 (근본 해결)

```bash
# Swap 6GB 추가 생성 및 활성화
sudo fallocate -l 6G /swapfile2 && sudo chmod 600 /swapfile2
sudo mkswap /swapfile2 && sudo swapon /swapfile2

# 병합 실행
uv run python scripts/merge_lora.py \
  --adapter output/LoRA_v11/adapter \
  --output_dir output/merged_v11

# 완료 후 Swap 제거
sudo swapoff /swapfile2 && sudo rm /swapfile2
```

Swap 확장 후 재실행 시 정상 완료.
출력: `output/merged_v11/model-0000{1..4}-of-00004.safetensors` (4-shard, 총 ~6GB)

---

## 결과

```
output/merged_v11/
├── config.json
├── generation_config.json
├── model-00001-of-00004.safetensors
├── model-00002-of-00004.safetensors
├── model-00003-of-00004.safetensors
├── model-00004-of-00004.safetensors
├── model.safetensors.index.json
├── tokenizer.json
├── tokenizer_config.json
└── chat_template.jinja
```

---

## 재현 방지

- `_check_memory()` 경고: 합산 가용 메모리 < 7GB 시 실행 전 안내 출력됨
- WSL2 + 8GB RAM 환경에서는 항상 swap 확장 후 진행할 것
- 영구 swap 확장이 필요하다면 `/etc/fstab`에 등록하거나 WSL2 메모리 제한을 `~/.wslconfig`에서 조정 가능

```ini
# ~/.wslconfig (Windows 홈 디렉토리)
[wsl2]
memory=8GB
swap=8GB
```
