"""
chat_cli.py — 어댑터 지정 단일 대화 CLI

사용법:
  uv run python training/eval/chat_cli.py --adapter output/LoRA_v10/adapter
  uv run python training/eval/chat_cli.py --adapter output/LoRA_v10_korean/adapter
  uv run python training/eval/chat_cli.py --adapter output/LoRA_v10_korean/adapter --model MyeongHo0621/Qwen2.5-3B-Korean
  uv run python training/eval/chat_cli.py --adapter output/LoRA_v10/adapter --tier friendly

명령어:
  /reset    대화 초기화
  /tier     현재 친밀도 tier 확인
  /tier <name>   tier 변경 (stranger/acquaintance/familiar/friendly/close/intimate)
  /mood <name>   mood 변경 (neutral/happy/sad/angry/annoyed/curious/embarrassed/touched/affectionate)
  /sys      현재 시스템 프롬프트 출력
  /quit     종료
"""

import argparse
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from conversation.loader.character_load import load_character
from conversation.core.prompt_build import PromptBuilder
from conversation.core.session import ConversationSession

CHAR_PATH = ROOT / "conversation/character/CH_Haru.yaml"
WORLD_STUB = {"description": "", "scenarios": []}

AFFECTION_MAP = {
    "stranger": 10, "acquaintance": 25, "familiar": 40,
    "friendly": 60, "close": 78, "intimate": 90,
}


def build_system_prompt(character: dict, tier: str, mood: str) -> str:
    aff = AFFECTION_MAP.get(tier, 40)
    session = ConversationSession(character["id"])
    session.affection = aff
    session.mood = mood
    builder = PromptBuilder(character, WORLD_STUB, session)
    return builder._layer_a()


def load_model(model_name: str, adapter_path: str | None):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"[모델 로드] {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModelForCausalLM.from_pretrained(
        model_name, dtype=torch.bfloat16, trust_remote_code=True,
    ).to(device)

    if adapter_path:
        from peft import PeftModel
        print(f"[어댑터 로드] {adapter_path}")
        model = PeftModel.from_pretrained(model, adapter_path, device_map={"": device})

    model.eval()
    print("[준비 완료]\n")
    return model, tokenizer


def generate(model, tokenizer, messages: list[dict]) -> str:
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=120,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            repetition_penalty=1.1,
            pad_token_id=tokenizer.pad_token_id,
        )
    return tokenizer.decode(
        output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
    ).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",   default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--adapter", default=None)
    parser.add_argument("--tier",    default="familiar",
                        choices=list(AFFECTION_MAP.keys()))
    parser.add_argument("--mood",    default="neutral")
    args = parser.parse_args()

    adapter_full = None
    if args.adapter:
        p = Path(args.adapter)
        adapter_full = str(ROOT / p) if not p.is_absolute() else str(p)

    character = load_character(CHAR_PATH)
    model, tokenizer = load_model(args.model, adapter_full)

    tier = args.tier
    mood = args.mood
    history: list[dict] = []

    label = Path(args.adapter).parent.name if args.adapter else args.model
    print(f"─── {label} | tier={tier} mood={mood} ───")
    print("명령어: /reset /tier <name> /mood <name> /sys /quit\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료")
            break

        if not user_input:
            continue

        # 명령어 처리
        if user_input == "/quit":
            break
        if user_input == "/reset":
            history.clear()
            print(f"[대화 초기화 — tier={tier} mood={mood}]\n")
            continue
        if user_input == "/sys":
            print(f"[시스템 프롬프트]\n{build_system_prompt(character, tier, mood)}\n")
            continue
        if user_input == "/tier":
            print(f"[현재 tier: {tier}]\n")
            continue
        if user_input.startswith("/tier "):
            new_tier = user_input.split()[1]
            if new_tier in AFFECTION_MAP:
                tier = new_tier
                print(f"[tier → {tier}]\n")
            else:
                print(f"[알 수 없는 tier: {new_tier}]\n")
            continue
        if user_input.startswith("/mood "):
            mood = user_input.split()[1]
            print(f"[mood → {mood}]\n")
            continue

        # 메시지 조립
        system_prompt = build_system_prompt(character, tier, mood)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-10:])  # 최근 5턴
        messages.append({"role": "user", "content": user_input})

        response = generate(model, tokenizer, messages)
        print(f"하루: {response}\n")

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
