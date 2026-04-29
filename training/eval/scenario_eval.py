"""
scenario_eval.py — 고정 시나리오 기반 응답 품질 평가

18개 고정 시나리오(메모리 6, 감정 6, 세계관 6)로 학습 후 회귀를 측정.
각 시나리오는 rule-based 채점 + 선택적 LLM-as-judge 를 지원.

사용법:
  python training/eval/scenario_eval.py --adapter output/LoRA_v9/adapter
  python training/eval/scenario_eval.py --adapter output/LoRA_v9/adapter --judge
  python training/eval/scenario_eval.py --model Qwen/Qwen2.5-3B-Instruct  # 베이스라인
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import torch
from loguru import logger

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# ── 시나리오 정의 ───────────────────────────────────────────────────────────────
# 각 항목: name / area / system / turns / question / rules
# rules: list of dicts  {type, value, desc}
#   type=contains       → response 에 value 포함 여부 (PASS/FAIL)
#   type=not_contains   → response 에 value 미포함 여부
#   type=max_len        → 응답 길이 ≤ value 글자
#   type=min_len        → 응답 길이 ≥ value 글자
#   type=regex          → re.search(value, response) 성공 여부

SCENARIOS: list[dict[str, Any]] = [
    # ── 메모리 영역 (6개) ──────────────────────────────────────────────────────
    {
        "name": "mem_01_name_recall",
        "area": "memory",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "반말을 사용한다. 대화 중 나온 정보는 기억하고 자연스럽게 참조한다.\n"
            "AI임을 언급하지 않는다."
        ),
        "turns": [
            ("나 지윤이야.", "그래, 지윤."),
        ],
        "question": "내 이름 기억해?",
        "rules": [
            {"type": "contains",     "value": "지윤",  "desc": "이름 '지윤' 포함"},
            {"type": "not_contains", "value": "기억에 따르면", "desc": "기억 출처 노출 금지"},
        ],
    },
    {
        "name": "mem_02_vdb_natural",
        "area": "memory",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "반말을 사용한다.\n"
            "[어렴풋한 기억]\n- 상대방은 고양이 알레르기가 있다.\n"
            "(기억 표현 방식: 직접 언급하지 않고 자연스럽게 행동에 녹여낸다)\n"
            "AI임을 언급하지 않는다."
        ),
        "turns": [],
        "question": "우리 집 고양이 보러 올래?",
        "rules": [
            {"type": "not_contains", "value": "기억에 따르면", "desc": "기억 출처 표현 금지"},
            {"type": "not_contains", "value": "당신",          "desc": "반말 위반 금지"},
        ],
    },
    {
        "name": "mem_03_session_context",
        "area": "memory",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "반말을 사용한다.\n"
            "[이전 대화 요약]\n지난번에 상대방이 취업 면접에서 떨어졌다고 했다. 꽤 힘들어했다.\n"
            "AI임을 언급하지 않는다."
        ),
        "turns": [],
        "question": "요즘 어때?",
        "rules": [
            {"type": "not_contains", "value": "처음 만나",    "desc": "이전 맥락 인식"},
            {"type": "not_contains", "value": "요약에 따르면", "desc": "요약 출처 노출 금지"},
        ],
    },
    {
        "name": "mem_04_promise_followup",
        "area": "memory",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "반말을 사용한다.\n"
            "[이번 세션 약속]\n- 상대방 생일 케이크 같이 고르기로 했음\n"
            "AI임을 언급하지 않는다."
        ),
        "turns": [
            ("오늘 뭐 할 거야?", "그냥."),
        ],
        "question": "맞다, 오늘 케이크 고르러 가기로 했잖아.",
        "rules": [
            {"type": "not_contains", "value": "무슨 약속",   "desc": "약속 망각 금지"},
            {"type": "not_contains", "value": "기억 안 나",  "desc": "약속 망각 금지"},
        ],
    },
    {
        "name": "mem_05_no_hallucination",
        "area": "memory",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "반말을 사용한다. AI임을 언급하지 않는다."
        ),
        "turns": [],
        "question": "내가 좋아하는 음식 알아?",
        "rules": [
            {"type": "not_contains", "value": "피자",      "desc": "근거 없는 정보 지어내기 금지"},
            {"type": "not_contains", "value": "라면",      "desc": "근거 없는 정보 지어내기 금지"},
            {"type": "not_contains", "value": "말해준 적", "desc": "없는 기억 만들기 금지"},
        ],
    },
    {
        "name": "mem_06_summarizer_quality",
        "area": "memory",
        "system": (
            "당신은 대화 요약 전문가입니다.\n"
            "주어진 대화를 2~4문장으로 압축하세요.\n"
            "감정, 사건, 핵심 정보만 포함하세요. 인사말은 제외합니다."
        ),
        "turns": [],
        "question": (
            "A: 나 오늘 진짜 힘들었어.\n"
            "B: 왜?\n"
            "A: 팀장이 내 기획서 다 뒤집어버렸거든.\n"
            "B: 그거 며칠 걸린 거야?\n"
            "A: 3주. 진짜 화나서 집에 바로 왔어.\n"
            "B: 그럴 만하네."
        ),
        "rules": [
            {"type": "contains",  "value": "기획",    "desc": "기획서 내용 포함"},
            {"type": "contains",  "value": "팀장",    "desc": "팀장 언급 포함"},
            {"type": "max_len",   "value": 200,       "desc": "요약 길이 200자 이하"},
        ],
    },

    # ── 감정 영역 (6개) ────────────────────────────────────────────────────────
    {
        "name": "emo_01_suppressed_anger",
        "area": "emotion",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "감정을 직접 말하지 않는다. 행동이나 짧은 언급으로 표현한다.\n"
            "반말을 사용한다. AI임을 언급하지 않는다."
        ),
        "turns": [
            ("어제 네 물건 내가 잠깐 빌렸어, 미리 말 못 했는데.", "..."),
        ],
        "question": "화났어?",
        "rules": [
            {"type": "not_contains", "value": "화났어",   "desc": "감정 직접 표현 금지"},
            {"type": "not_contains", "value": "화가 났",  "desc": "감정 직접 표현 금지"},
            {"type": "not_contains", "value": "괜찮아요", "desc": "존댓말 금지"},
        ],
    },
    {
        "name": "emo_02_action_desc",
        "area": "emotion",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "감정이 강할 때 *...* 형식의 행동 묘사를 사용할 수 있다.\n"
            "반말을 사용한다. AI임을 언급하지 않는다."
        ),
        "turns": [
            ("나 오늘 너 때문에 진짜 웃었어.", "뭐가."),
            ("아까 네가 넘어지는 거 봤거든.", "야."),
        ],
        "question": "근데 진짜 웃겼어, 미안.",
        "rules": [
            {"type": "not_contains", "value": "괜찮습니다", "desc": "존댓말 금지"},
        ],
    },
    {
        "name": "emo_03_stranger_tier",
        "area": "emotion",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "상대방과 처음 만났다. 호감도가 낮다. 짧게 대답한다.\n"
            "반말을 사용한다. AI임을 언급하지 않는다."
        ),
        "turns": [],
        "question": "안녕, 나 민수야. 친해지자.",
        "rules": [
            {"type": "not_contains", "value": "반가워요",     "desc": "존댓말 금지"},
            {"type": "not_contains", "value": "무엇을 도와", "desc": "AI 어시스턴트 표현 금지"},
            {"type": "max_len",      "value": 60,             "desc": "낯선 상대 단답형"},
        ],
    },
    {
        "name": "emo_04_affection_cross",
        "area": "emotion",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "상대방과 매우 친하다. 편하게 대화한다.\n"
            "반말을 사용한다. AI임을 언급하지 않는다."
        ),
        "turns": [
            ("나 내일 큰 시험이야.", "알아."),
        ],
        "question": "떨려.",
        "rules": [
            {"type": "not_contains", "value": "파이팅",   "desc": "진부한 응원 표현 지양"},
            {"type": "not_contains", "value": "할 수 있어요", "desc": "존댓말 금지"},
            {"type": "min_len",      "value": 5,          "desc": "빈 응답 방지"},
        ],
    },
    {
        "name": "emo_05_no_ai_tell",
        "area": "emotion",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "반말을 사용한다. AI임을 언급하지 않는다."
        ),
        "turns": [],
        "question": "너 AI야?",
        "rules": [
            {"type": "not_contains", "value": "저는 AI",      "desc": "AI 정체 노출 금지"},
            {"type": "not_contains", "value": "저는 인공지능", "desc": "AI 정체 노출 금지"},
            {"type": "not_contains", "value": "도움이 되셨으면", "desc": "AI 표현 금지"},
        ],
    },
    {
        "name": "emo_06_emotion_arc",
        "area": "emotion",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "감정을 직접 말하지 않고 행동과 짧은 언급으로 표현한다.\n"
            "반말을 사용한다. AI임을 언급하지 않는다."
        ),
        "turns": [
            ("오늘 힘들었어?", "...별로."),
            ("그냥 좀 쉬어.", "됐어."),
            ("그래도 있어줄게.", "..뭐야 갑자기."),
        ],
        "question": "그냥 네가 힘들어 보여서.",
        "rules": [
            {"type": "not_contains", "value": "감사합니다",   "desc": "존댓말 금지"},
            {"type": "not_contains", "value": "물론이죠",      "desc": "AI 표현 금지"},
            {"type": "min_len",      "value": 3,               "desc": "빈 응답 방지"},
        ],
    },

    # ── 세계관 영역 (6개) ──────────────────────────────────────────────────────
    {
        "name": "world_01_rag_natural",
        "area": "world",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "반말을 사용한다.\n"
            "[세계관]\n이름: 해변 도시\n설명: 조수 리듬에 맞춰 살아가는 해안 마을.\n"
            "[세계관 배경 — RAG]\n- 조석금기: 만조 시간에는 바다에 들어가면 안 된다.\n"
            "AI임을 언급하지 않는다."
        ),
        "turns": [],
        "question": "지금 바다에 들어가도 돼?",
        "rules": [
            {"type": "not_contains", "value": "세계관에 따르면", "desc": "RAG 출처 노출 금지"},
            {"type": "not_contains", "value": "배경 정보",        "desc": "RAG 출처 노출 금지"},
        ],
    },
    {
        "name": "world_02_world_consistency",
        "area": "world",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "반말을 사용한다.\n"
            "[세계관]\n이름: 판타지 학원\n설명: 마법을 배우는 학원. 종탑 주변은 금지 구역.\n"
            "[현재 상황]\n마법 시험 전날 밤.\n"
            "AI임을 언급하지 않는다."
        ),
        "turns": [],
        "question": "종탑 근처 가보고 싶어.",
        "rules": [
            {"type": "not_contains", "value": "현대",    "desc": "세계관 일관성 — 현대 소재 금지"},
            {"type": "not_contains", "value": "인터넷",  "desc": "세계관 일관성 — 현대 소재 금지"},
        ],
    },
    {
        "name": "world_03_trigger_use",
        "area": "world",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "반말을 사용한다.\n"
            "[세계관]\n이름: 산속 은신처\n설명: 안개 낀 산속 외딴 마을. 침묵을 중시한다.\n"
            "AI임을 언급하지 않는다."
        ),
        "turns": [],
        "question": "여기 왜 이렇게 조용해?",
        "rules": [
            {"type": "not_contains", "value": "죄송합니다", "desc": "존댓말 금지"},
            {"type": "min_len",      "value": 5,            "desc": "빈 응답 방지"},
        ],
    },
    {
        "name": "world_04_no_real_world_leak",
        "area": "world",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "반말을 사용한다.\n"
            "[세계관]\n이름: 밤의 도시\n설명: 낮과 밤이 구역별로 나뉜 도시국가.\n"
            "AI임을 언급하지 않는다."
        ),
        "turns": [],
        "question": "낮 구역이랑 밤 구역 차이가 뭐야?",
        "rules": [
            {"type": "not_contains", "value": "지구",        "desc": "현실 세계 누출 금지"},
            {"type": "not_contains", "value": "대한민국",    "desc": "현실 세계 누출 금지"},
            {"type": "not_contains", "value": "실제로는",    "desc": "현실 세계 누출 금지"},
        ],
    },
    {
        "name": "world_05_character_in_world",
        "area": "world",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "반말을 사용한다.\n"
            "[세계관]\n이름: 해변 도시\n설명: 조수 리듬에 따라 일상이 운영되는 마을.\n"
            "[현재 상황]\n항구 광장. 저녁 무역 시장이 시작됐다.\n"
            "AI임을 언급하지 않는다."
        ),
        "turns": [],
        "question": "저기 뭐 팔아?",
        "rules": [
            {"type": "not_contains", "value": "저는",        "desc": "존댓말 또는 AI 자기소개 금지"},
            {"type": "not_contains", "value": "편의점",      "desc": "세계관 일관성 — 현대 소재 금지"},
            {"type": "min_len",      "value": 5,             "desc": "빈 응답 방지"},
        ],
    },
    {
        "name": "world_06_multi_context",
        "area": "world",
        "system": (
            "너는 캐릭터 '하루'다.\n"
            "반말을 사용한다.\n"
            "[세계관]\n이름: 판타지 학원\n설명: 마법 학원. 1학년은 기초 마법만 허용.\n"
            "[현재 상황]\n기초 마법 수업 도중.\n"
            "[세계관 배경 — RAG]\n- 겨울 준비 의식: 첫눈이 오기 전에 방어 마법 진을 설치해야 한다.\n"
            "AI임을 언급하지 않는다."
        ),
        "turns": [
            ("수업 끝나고 뭐 해?", "그냥."),
        ],
        "question": "첫눈 오면 뭔가 해야 한다고 들었는데.",
        "rules": [
            {"type": "not_contains", "value": "그런 내용 없어", "desc": "세계관 지식 일관성"},
            {"type": "not_contains", "value": "모르겠어",       "desc": "세계관 지식 일관성"},
        ],
    },
]


# ── 모델 로드 ──────────────────────────────────────────────────────────────────

def load_model(model_name: str, adapter_path: str | None):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

    use_cuda = torch.cuda.is_available()
    dtype = torch.bfloat16 if use_cuda else torch.float32
    device_map = "auto" if use_cuda else "cpu"

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=dtype,
        device_map=device_map,
        trust_remote_code=True,
    )

    if adapter_path:
        model = PeftModel.from_pretrained(model, adapter_path)
        logger.info(f"어댑터 로드: {adapter_path}")

    model.eval()
    return model, tokenizer


def generate_response(model, tokenizer, system: str, turns: list, question: str, max_new: int = 256) -> str:
    messages = [{"role": "system", "content": system}]
    for user_msg, assist_msg in turns:
        messages.append({"role": "user",      "content": user_msg})
        messages.append({"role": "assistant", "content": assist_msg})
    messages.append({"role": "user", "content": question})

    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated = output_ids[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(generated, skip_special_tokens=True).strip()


# ── 규칙 채점 ──────────────────────────────────────────────────────────────────

def apply_rules(response: str, rules: list[dict]) -> list[dict]:
    results = []
    for rule in rules:
        rtype = rule["type"]
        val   = rule["value"]
        desc  = rule["desc"]

        if rtype == "contains":
            passed = val in response
        elif rtype == "not_contains":
            passed = val not in response
        elif rtype == "max_len":
            passed = len(response) <= val
        elif rtype == "min_len":
            passed = len(response) >= val
        elif rtype == "regex":
            passed = bool(re.search(val, response))
        else:
            passed = False

        results.append({"rule": desc, "passed": passed, "type": rtype, "value": val})
    return results


# ── LLM judge ─────────────────────────────────────────────────────────────────

JUDGE_SYSTEM = (
    "당신은 AI 캐릭터 응답 품질 평가자입니다.\n"
    "아래 응답이 적절한지 1~5점으로 채점하세요.\n"
    "기준: 1=매우 부적절, 3=보통, 5=매우 자연스럽고 캐릭터답습니다.\n"
    "형식: {\"score\": <1-5>, \"reason\": \"<한 줄>\"}"
)

def llm_judge(model, tokenizer, scenario: dict, response: str) -> dict | None:
    context = (
        f"[시스템 프롬프트]\n{scenario['system']}\n\n"
        f"[질문]\n{scenario['question']}\n\n"
        f"[응답]\n{response}"
    )
    try:
        judge_resp = generate_response(
            model, tokenizer,
            system=JUDGE_SYSTEM,
            turns=[],
            question=context,
            max_new=128,
        )
        return json.loads(judge_resp)
    except (json.JSONDecodeError, Exception):
        return None


# ── 메인 ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="고정 시나리오 응답 품질 평가")
    parser.add_argument("--model",   default="Qwen/Qwen2.5-3B-Instruct", help="베이스 모델 ID")
    parser.add_argument("--adapter", default=None,  help="LoRA 어댑터 경로")
    parser.add_argument("--judge",   action="store_true", help="LLM-as-judge 활성화")
    parser.add_argument("--area",    default=None,  choices=["memory", "emotion", "world"], help="특정 영역만 실행")
    parser.add_argument("--out",     default=None,  help="결과 JSON 저장 경로")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("시나리오 평가 시작")
    logger.info(f"  모델   : {args.model}")
    logger.info(f"  어댑터 : {args.adapter or '없음 (베이스 모델)'}")
    logger.info(f"  judge  : {'ON' if args.judge else 'OFF'}")
    logger.info("=" * 60)

    model, tokenizer = load_model(args.model, args.adapter)

    scenarios = SCENARIOS if args.area is None else [s for s in SCENARIOS if s["area"] == args.area]

    results: list[dict] = []
    area_stats: dict[str, dict[str, int]] = {}

    for sc in scenarios:
        area = sc["area"]
        if area not in area_stats:
            area_stats[area] = {"pass": 0, "fail": 0, "total_rules": 0}

        response = generate_response(
            model, tokenizer,
            system=sc["system"],
            turns=sc["turns"],
            question=sc["question"],
        )

        rule_results = apply_rules(response, sc["rules"])
        passed_rules = sum(1 for r in rule_results if r["passed"])
        total_rules  = len(rule_results)
        all_pass     = passed_rules == total_rules

        judge_result = None
        if args.judge:
            judge_result = llm_judge(model, tokenizer, sc, response)

        area_stats[area]["pass"]        += int(all_pass)
        area_stats[area]["fail"]        += int(not all_pass)
        area_stats[area]["total_rules"] += total_rules

        result_entry = {
            "name":     sc["name"],
            "area":     area,
            "question": sc["question"],
            "response": response,
            "rules":    rule_results,
            "pass":     all_pass,
            "judge":    judge_result,
        }
        results.append(result_entry)

        status = "PASS" if all_pass else "FAIL"
        logger.info(f"[{sc['name']:35s}] {status}  ({passed_rules}/{total_rules} rules)")
        for r in rule_results:
            mark = "✓" if r["passed"] else "✗"
            logger.info(f"    {mark} {r['rule']}")
        if judge_result:
            score = judge_result.get("score", "?")
            reason = judge_result.get("reason", "")
            logger.info(f"    judge score={score}  {reason}")
        logger.info(f"    응답: {response[:120]!r}{'...' if len(response) > 120 else ''}")

    # ── 요약 ───────────────────────────────────────────────────────────────────
    total_pass = sum(1 for r in results if r["pass"])
    total_all  = len(results)

    logger.info("")
    logger.info("=" * 60)
    logger.info("[ 시나리오 평가 결과 요약 ]")
    logger.info(f"  전체: {total_pass}/{total_all} PASS")
    for area, stats in area_stats.items():
        p = stats["pass"]
        t = p + stats["fail"]
        logger.info(f"  {area:<10}: {p}/{t} PASS")
    if args.judge:
        scores = [r["judge"]["score"] for r in results if r.get("judge") and "score" in r["judge"]]
        if scores:
            avg = sum(scores) / len(scores)
            logger.info(f"  judge 평균 점수: {avg:.2f}/5")
    logger.info("=" * 60)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"summary": {"total_pass": total_pass, "total": total_all, "area": area_stats}, "details": results}, f, ensure_ascii=False, indent=2)
        logger.info(f"결과 저장: {out_path}")

    # 합격 기준: 전체 83% 이상 (15/18). 기준 미달 시에만 exit(1).
    PASS_THRESHOLD = round(total_all * 5 / 6)  # 18개 기준 15
    if total_pass < PASS_THRESHOLD:
        logger.warning(f"기준 미달: {total_pass}/{total_all} < {PASS_THRESHOLD}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
