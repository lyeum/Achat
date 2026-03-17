"""CLI 루프 — Agent(router + VDB + state) 연동."""

from __future__ import annotations

import json
import subprocess
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
from conversation.core.router import ConversationRouter
from conversation.core.session import ConversationSession
from conversation.loader.character_load import load_character
from conversation.loader.world_load import load_world
from memory.long_term import LongTermMemory
from training.log.conversation_logger import ConversationLogger

# ── 기본 경로 ─────────────────────────────────────────────────────────────────
CHARACTER_PATH = ROOT / "conversation/character/CH_Haru.yaml"
WORLD_PATH     = ROOT / "conversation/world/W_sea.yaml"
STATE_FILE     = ROOT / "training/log/.session_state.json"


def _write_state(session: ConversationSession, vdb_count: int = 0) -> None:
    """세션 상태를 모니터용 JSON 파일에 기록한다."""
    try:
        STATE_FILE.write_text(
            json.dumps({
                "turn":             session.turn_count,
                "mood":             session.mood,
                "affection":        session.affection,
                "act_id":           session.act_id,
                "location_context": session.location_context,
                "vdb_count":        vdb_count,
                "updated_at":       __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            }, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def main() -> None:
    cfg = get_config()

    # 1. 데이터 로드
    logger.info("캐릭터 / 세계관 로딩 중...")
    character = load_character(CHARACTER_PATH)
    world     = load_world(WORLD_PATH)

    # 2. 세션 생성
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

    # 3. 세계관 RAG 자동 인덱싱 (컬렉션 없을 때만)
    from rag.index import index_world
    world_sources = ROOT / "rag" / "sources" / "world"
    if world_sources.exists():
        index_world(
            world_dir=world_sources,
            chroma_path=cfg["chroma_path"],
            embedding_model=cfg.get("embedding_model", "BAAI/bge-m3"),
            force=False,
        )

    # 4. LLM / Router 초기화
    model_ready = (
        cfg["model_backend"] == "llama_cpp" and cfg.get("model_path")
        and Path(cfg["model_path"]).exists()
    ) or cfg["model_backend"] == "transformers"

    if model_ready:
        logger.info("LLM 로딩 중... (처음 실행 시 시간이 걸릴 수 있습니다)")
        llm = LLMClient(cfg)
        long_term = LongTermMemory(cfg)
        router = ConversationRouter(
            character=character,
            world=world,
            session=session,
            llm=llm,
            long_term=long_term,
            config=cfg,
        )
        use_router = True
    else:
        logger.warning(
            "모델 파일 없음 — dry-run 모드로 실행합니다. "
            "(GGUF 모델은 Phase 6 이후 생성됩니다)"
        )
        builder = PromptBuilder(character, world, session)
        use_router = False

    # 5. 대화 로거 + 모니터 시작
    conv_logger = ConversationLogger(character_id=character["name"])
    _write_state(session)

    monitor_script = ROOT / "training/log/monitor.py"
    monitor_log    = ROOT / "training/log/.monitor.log"
    subprocess.Popen(
        [sys.executable, str(monitor_script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # 6. CLI 루프
    print(f"\n{'─'*50}")
    print(f"  {character['name']}와 대화를 시작합니다.  (종료: /quit)")
    print(f"  [모니터] tail -f {monitor_log.relative_to(ROOT)}")
    print(f"{'─'*50}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            conv_logger.flush_remaining()
            print("\n종료합니다.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/quit", "/exit", "q"):
            conv_logger.flush_remaining()
            print("종료합니다.")
            break

        if use_router:
            response = router.handle_turn(user_input, stream=True)
        else:
            messages = builder.assemble(short_buf=session.dialogue_log, vdb_results=[])
            messages.append({"role": "user", "content": user_input})
            print(f"\n[dry-run] system 프롬프트:\n{messages[0]['content']}\n")
            response = "(LLM 미연결 — dry-run)"
            session.add_turn(user_input, response)

        print(f"{character['name']}: {response}\n")
        logger.debug(
            f"turn={session.turn_count}  mood={session.mood}  aff={session.affection}"
        )

        conv_logger.on_turn(
            user_input=user_input,
            assistant_response=response,
            mood=session.mood,
            affection=session.affection,
        )
        _write_state(session)


if __name__ == "__main__":
    main()
