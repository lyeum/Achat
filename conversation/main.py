"""Phase 1 CLI 루프 — 로더 → 세션 → PromptBuilder → LLMClient 연결 확인용."""

from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (python conversation/main.py 직접 실행 시 대비)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from config import get_config
from conversation.core.llm_client import LLMClient
from conversation.core.prompt_build import PromptBuilder
from conversation.core.session import ConversationSession
from conversation.loader.character_load import load_character
from conversation.loader.world_load import load_world

# ── 기본 경로 ─────────────────────────────────────────────────────────────────
CHARACTER_PATH = ROOT / "conversation/character/CH_haru.yaml"
WORLD_PATH     = ROOT / "conversation/world/W_sea.yaml"


def main() -> None:
    cfg = get_config()

    # 1. 데이터 로드
    logger.info("캐릭터 / 세계관 로딩 중...")
    character = load_character(CHARACTER_PATH)
    world     = load_world(WORLD_PATH)

    # 2. 세션 생성 (캐릭터 초기값 반영)
    session = ConversationSession.from_character(
        character,
        world_id=world.get("world_id"),
        scenario_id="morning_walk",
        act_id="act_1",
    )
    logger.info(
        f"세션 시작 — 캐릭터: {character['name']} / "
        f"mood: {session.mood} / affection: {session.affection}"
    )

    # 3. LLM 로딩 (모델 경로가 없으면 건너뜀 — 구조 확인용 dry-run)
    llm: LLMClient | None = None
    model_ready = (
        cfg["model_backend"] == "llama_cpp" and cfg.get("model_path")
        and Path(cfg["model_path"]).exists()
    ) or cfg["model_backend"] == "transformers"

    if model_ready:
        logger.info("LLM 로딩 중... (처음 실행 시 시간이 걸릴 수 있습니다)")
        llm = LLMClient(cfg)
        count_fn = llm.count_tokens
    else:
        logger.warning(
            "모델 파일 없음 — dry-run 모드로 실행합니다. "
            "(GGUF 모델은 Phase 6 이후 생성됩니다)"
        )
        count_fn = None

    # 4. PromptBuilder 초기화
    builder = PromptBuilder(character, world, session, count_tokens_fn=count_fn)

    # 5. CLI 루프
    print(f"\n{'─'*50}")
    print(f"  {character['name']}와 대화를 시작합니다.  (종료: /quit)")
    print(f"{'─'*50}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/quit", "/exit", "q"):
            print("종료합니다.")
            break

        # short_buf: dialogue_log 전체 (Layer D에서 예산 기준으로 축소)
        messages = builder.assemble(
            short_buf=session.dialogue_log,
            vdb_results=[],   # Phase 2에서 long_term.query() 연동
        )
        messages.append({"role": "user", "content": user_input})

        if llm is None:
            # dry-run: 조립된 시스템 프롬프트 출력
            print(f"\n[dry-run] system 프롬프트:\n{messages[0]['content']}\n")
            response = "(LLM 미연결 — dry-run)"
        else:
            response = llm.generate(messages, stream=True)

        print(f"{character['name']}: {response}\n")
        session.add_turn(user_input, response)
        logger.debug(f"turn={session.turn_count}  mood={session.mood}  aff={session.affection}")


if __name__ == "__main__":
    main()
