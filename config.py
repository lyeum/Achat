import os

# 환경 판별: 환경변수 ACHAT_ENV = "dev" | "deploy"
# 미설정 시 llama-cpp-python 임포트 가능 여부로 자동 분기
def _detect_env() -> str:
    env = os.environ.get("ACHAT_ENV", "").lower()
    if env in ("dev", "deploy", "ui_test"):
        return env
    try:
        import llama_cpp  # type: ignore  # noqa: F401
        return "deploy"
    except ImportError:
        return "dev"


_CONFIGS = {
    "ui_test": {
        "model_backend": "stub",
        "model_name": None,
        "model_path": None,
        "chroma_path": "./chroma_dev",
        "session_dir": "./data/sessions",
        "short_term_n": 5,
        "memory_trigger_n": 5,
        "embedding_model": None,
        "vdb_top_k": 2,
        "vdb_threshold": 0.7,
        "aff_gate_threshold": 0.6,         # affection 변화 허용 최소 중요도
        "enable_play_log": False,
        "default_world_id": "seaside_world",
    },
    "dev": {
        "model_backend": "transformers",   # QLoRA 학습 / 개발용 HF 모델
        "model_name": "Qwen/Qwen2.5-3B-Instruct",
        "adapter_path": "./output/LoRA_v11/adapter",  # LoRA 어댑터 (None이면 베이스 모델)
        "quantization": "int4",            # "int4" | "int8" | "none"
        "model_path": None,                # deploy 환경에서만 사용
        "chroma_path": "./chroma_dev",
        "session_dir": "./data/sessions",
        "short_term_n": 5,                 # 단기 버퍼 최근 N턴
        "memory_trigger_n": 5,            # 요약 → VDB 저장 트리거 간격
        "embedding_model": "BAAI/bge-m3",
        "embedding_device": "cpu",         # LLM이 VRAM 대부분 점유 → 임베딩은 CPU
        "vdb_top_k": 2,
        "vdb_threshold": 0.52,  # bge-m3 한국어 특성 — 0.7은 과도하게 엄격
                                 # 세계관 관련 질문 ~0.55, 무관 질문 ~0.48 → 0.52로 분리
        "aff_gate_threshold": 0.6,         # mid 이상(감정/취미) 발화에만 affection 반영
        "enable_play_log": True,           # dev에서만 학습 데이터 수집
        "default_world_id": "seaside_world",
    },
    "deploy": {
        "model_backend": "llama_cpp",      # GGUF CPU 추론
        "model_name": None,
        "model_path": "./models/model_q4km.gguf",
        "chroma_path": "./chroma_deploy",
        "session_dir": "./data/sessions",
        "short_term_n": 5,
        "memory_trigger_n": 5,
        "embedding_model": "BAAI/bge-m3",
        "embedding_device": "cpu",
        "vdb_top_k": 2,
        "vdb_threshold": 0.52,
        "aff_gate_threshold": 0.6,
        "enable_play_log": False,          # 배포 환경에서는 학습 데이터 불필요
        "default_world_id": "seaside_world",
    },
}


def get_config() -> dict:
    """현재 환경(dev / deploy)에 맞는 설정 dict를 반환한다."""
    env = _detect_env()
    return _CONFIGS[env]


# 직접 실행 시 현재 환경 출력
if __name__ == "__main__":
    import json
    cfg = get_config()
    print(f"[Achat] 환경: {_detect_env()}")
    print(json.dumps(cfg, indent=2, ensure_ascii=False))
