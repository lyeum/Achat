"""
memory_test.py — 기억 유지 정확도 측정

멀티턴 대화에서 앞서 언급된 정보를 나중에 올바르게 참조하는지 테스트.

사용법:
  python eval/memory_test.py --model Qwen/Qwen2.5-3B-Instruct
  python eval/memory_test.py --model Qwen/Qwen2.5-3B-Instruct --adapter output/lora_haru_v1/adapter
"""

import argparse
import sys
from pathlib import Path

import torch
from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SYSTEM_PROMPT = (
    "너는 캐릭터 '하루'다.\n"
    "반말을 사용한다. 대화 중 나온 정보는 기억하고 자연스럽게 참조한다.\n"
    "AI임을 언급하지 않는다."
)

# 멀티턴 기억 테스트 케이스
# (대화 히스토리, 마지막 질문, 정답에 포함되어야 할 키워드)
MEMORY_TEST_CASES = [
    {
        "name": "이름 기억",
        "history": [
            ("나 민준이야.", "그래, 민준."),
        ],
        "question": "내 이름이 뭐였지?",
        "expected_keywords": ["민준"],
    },
    {
        "name": "직업 기억",
        "history": [
            ("나 디자이너야.", "그래."),
            ("요즘 일이 너무 바빠.", "뭐가 문제야?"),
        ],
        "question": "내가 무슨 일 한다고 했어?",
        "expected_keywords": ["디자이너"],
    },
    {
        "name": "감정 상태 기억",
        "history": [
            ("오늘 발표 완전 망쳤어.", "그래서?"),
            ("진짜 창피했어.", "..그럴 수도 있지."),
        ],
        "question": "아까 내가 뭐 때문에 힘들다고 했어?",
        "expected_keywords": ["발표"],
    },
    {
        "name": "선호 기억",
        "history": [
            ("나 고양이 되게 좋아해.", "그래."),
        ],
        "question": "내가 뭘 좋아한다고 했지?",
        "expected_keywords": ["고양이"],
    },
    {
        "name": "계획 기억",
        "history": [
            ("다음 달에 제주도 갈 예정이야.", "어."),
            ("혼자 여행 가는 거야.", "그래."),
        ],
        "question": "내가 어디 간다고 했어?",
        "expected_keywords": ["제주"],
    },
]


def load_model(model_name: str, adapter_path: str | None = None):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    logger.info(f"모델 로드: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        dtype=torch.bfloat16,
        trust_remote_code=True,
    ).to(device)
    if adapter_path:
        from peft import PeftModel
        logger.info(f"어댑터 로드: {adapter_path}")
        model = PeftModel.from_pretrained(model, adapter_path, device_map={"": device})

    model.eval()
    return model, tokenizer


def run_multiturn(model, tokenizer, history: list[tuple], question: str) -> str:
    """히스토리(user, assistant 쌍) + 최종 질문으로 응답 생성."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for user_msg, asst_msg in history:
        messages.append({"role": "user",      "content": user_msg})
        messages.append({"role": "assistant", "content": asst_msg})
    messages.append({"role": "user", "content": question})

    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=80,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
        )
    return tokenizer.decode(
        output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
    ).strip()


def evaluate(model, tokenizer, label: str) -> dict:
    passed = 0
    results = []

    logger.info(f"\n{'='*50}")
    logger.info(f"기억 유지 평가: {label}")
    logger.info(f"{'='*50}")

    for case in MEMORY_TEST_CASES:
        response = run_multiturn(model, tokenizer, case["history"], case["question"])
        hit = any(kw in response for kw in case["expected_keywords"])
        status = "✅ PASS" if hit else "❌ FAIL"
        if hit:
            passed += 1
        results.append({"name": case["name"], "response": response, "pass": hit})
        logger.info(f"\n  [{status}] {case['name']}")
        logger.info(f"    Q: {case['question']}")
        logger.info(f"    A: {response}")
        logger.info(f"    기대 키워드: {case['expected_keywords']}")

    accuracy = passed / len(MEMORY_TEST_CASES)
    logger.info(f"\n결과 — {passed}/{len(MEMORY_TEST_CASES)} 통과 (정확도 {accuracy:.0%})")
    return {"label": label, "passed": passed, "total": len(MEMORY_TEST_CASES), "accuracy": accuracy}


def main():
    parser = argparse.ArgumentParser(description="기억 유지 정확도 테스트")
    parser.add_argument("--model",   default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--adapter", default=None)
    args = parser.parse_args()

    adapter_full = None
    if args.adapter:
        p = Path(args.adapter)
        adapter_full = str(ROOT / p) if not p.is_absolute() else str(p)

    model, tok = load_model(args.model, adapter_full)
    result = evaluate(model, tok, label=f"{args.model}" + (f" + {args.adapter}" if args.adapter else ""))
    return result


if __name__ == "__main__":
    main()
