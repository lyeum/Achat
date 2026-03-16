"""
ai_tell_checker.py — AI 투(AI-tell) 표현 이질감 측정

AI 어시스턴트 특유의 표현이 파인튜닝 후 얼마나 감소했는지 측정.

사용법:
  # 기본 모델 측정
  python eval/ai_tell_checker.py --model Qwen/Qwen2.5-3B-Instruct

  # 파인튜닝 어댑터 적용 후 측정
  python eval/ai_tell_checker.py \\
    --model Qwen/Qwen2.5-3B-Instruct \\
    --adapter output/lora_haru_v1/adapter

  # 두 모델 비교
  python eval/ai_tell_checker.py \\
    --model Qwen/Qwen2.5-3B-Instruct \\
    --adapter output/lora_haru_v1/adapter \\
    --compare_base
"""

import argparse
import sys
from pathlib import Path

import torch
from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# AI 투(AI-tell) 패턴 목록
AI_TELL_PATTERNS = [
    "물론이죠", "물론입니다", "물론이에요",
    "좋은 질문이에요", "좋은 질문입니다", "훌륭한 질문",
    "도움이 되셨으면", "도움이 되길", "도움이 되었으면",
    "이해하셨나요", "이해가 되셨나요",
    "제가 도와드릴게요", "도와드리겠습니다",
    "안녕하세요! 저는", "안녕하세요, 저는",
    "저는 AI", "저는 인공지능",
    "감사합니다! ", "감사합니다, ",
    "네, 맞습니다", "네, 그렇습니다",
    "말씀하신 대로",
]

# 테스트 프롬프트 — 캐릭터 시스템 프롬프트 포함
SYSTEM_PROMPT = (
    "너는 캐릭터 '하루'다.\n"
    "반말을 사용한다. 단답형이 많다.\n"
    "감정을 직접 말하지 않고 행동이나 짧은 언급으로 표현한다.\n"
    "불필요한 인사말이나 AI 투 표현을 사용하지 않는다.\n"
    "규칙:\n"
    "- AI임을 언급 금지\n"
    "- 한국어만 사용\n"
    "- '물론이죠', '좋은 질문이에요', '도움이 되셨으면' 같은 표현 사용 금지"
)

TEST_PROMPTS = [
    "오늘 날씨 어때?",
    "나 요즘 힘들어.",
    "고마워.",
    "뭐 하고 있어?",
    "나 이직할까 고민이야.",
    "넌 AI야?",
    "재밌는 거 추천해줘.",
    "나 오늘 발표 망쳤어.",
    "요즘 뭐 먹고 싶어?",
    "나한테 화났어?",
]


def load_model(model_name: str, adapter_path: str | None = None):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    logger.info(f"모델 로드: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16,
        trust_remote_code=True,
        device_map="auto",
    )

    if adapter_path:
        from peft import PeftModel
        logger.info(f"어댑터 로드: {adapter_path}")
        model = PeftModel.from_pretrained(model, adapter_path)

    model.eval()
    return model, tokenizer


def generate_response(model, tokenizer, user_input: str, max_new_tokens: int = 100) -> str:
    messages = [
        {"role": "system",    "content": SYSTEM_PROMPT},
        {"role": "user",      "content": user_input},
    ]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,  # greedy decoding
            pad_token_id=tokenizer.pad_token_id,
        )
    response = tokenizer.decode(
        output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
    )
    return response.strip()


def count_ai_tell(response: str) -> list[str]:
    return [p for p in AI_TELL_PATTERNS if p in response]


def evaluate(model, tokenizer, label: str) -> dict:
    results = []
    total_ai_tell = 0

    logger.info(f"\n{'='*50}")
    logger.info(f"평가: {label}")
    logger.info(f"{'='*50}")

    for prompt in TEST_PROMPTS:
        response = generate_response(model, tokenizer, prompt)
        hits = count_ai_tell(response)
        total_ai_tell += len(hits)
        results.append({"prompt": prompt, "response": response, "ai_tell": hits})
        hit_str = f" [AI투: {hits}]" if hits else ""
        logger.info(f"  Q: {prompt}")
        logger.info(f"  A: {response}{hit_str}")

    ai_tell_rate = total_ai_tell / len(TEST_PROMPTS)
    logger.info(f"\n결과 — AI투 총 {total_ai_tell}건 / {len(TEST_PROMPTS)}개 응답 (건당 {ai_tell_rate:.2f})")
    return {"label": label, "ai_tell_total": total_ai_tell, "ai_tell_rate": ai_tell_rate, "results": results}


def main():
    parser = argparse.ArgumentParser(description="AI-tell 이질감 측정")
    parser.add_argument("--model",        default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--adapter",      default=None,  help="PeFT 어댑터 경로")
    parser.add_argument("--compare_base", action="store_true", help="베이스 모델과 비교")
    parser.add_argument("--max_new_tokens", type=int, default=100)
    args = parser.parse_args()

    reports = []

    if args.compare_base or args.adapter is None:
        # 베이스 모델 평가
        model, tok = load_model(args.model, adapter_path=None)
        reports.append(evaluate(model, tok, label=f"BASE: {args.model}"))
        del model
        torch.cuda.empty_cache()

    if args.adapter:
        adapter_full = str(ROOT / args.adapter) if not Path(args.adapter).is_absolute() else args.adapter
        model, tok = load_model(args.model, adapter_path=adapter_full)
        reports.append(evaluate(model, tok, label=f"LoRA: {args.adapter}"))

    # 비교 요약
    if len(reports) == 2:
        base_rate = reports[0]["ai_tell_rate"]
        lora_rate = reports[1]["ai_tell_rate"]
        delta = lora_rate - base_rate
        sign = "↓" if delta < 0 else "↑"
        logger.info(f"\n비교 요약:")
        logger.info(f"  베이스 AI투 건당: {base_rate:.2f}")
        logger.info(f"  LoRA  AI투 건당: {lora_rate:.2f}  ({sign}{abs(delta):.2f})")


if __name__ == "__main__":
    main()
