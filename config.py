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
        "short_term_n": 5,
        "memory_trigger_n": 10,
        "embedding_model": None,
        "vdb_top_k": 2,
        "vdb_threshold": 0.7,
    },
    "dev": {
        "model_backend": "transformers",   # QLoRA 학습 / 개발용 HF 모델
        "model_name": "Qwen/Qwen2.5-3B-Instruct",
        "model_path": None,                # deploy 환경에서만 사용
        "chroma_path": "./chroma_dev",
        "short_term_n": 5,                 # 단기 버퍼 최근 N턴
        "memory_trigger_n": 10,            # 요약 → VDB 저장 트리거 간격
        "embedding_model": "BAAI/bge-m3",
        "vdb_top_k": 2,
        "vdb_threshold": 0.52,  # bge-m3 한국어 특성 — 0.7은 과도하게 엄격
                                 # 세계관 관련 질문 ~0.55, 무관 질문 ~0.48 → 0.52로 분리
    },
    "deploy": {
        "model_backend": "llama_cpp",      # GGUF CPU 추론
        "model_name": None,
        "model_path": "./models/model_q4km.gguf",
        "chroma_path": "./chroma_deploy",
        "short_term_n": 5,
        "memory_trigger_n": 10,
        "embedding_model": "BAAI/bge-m3",
        "vdb_top_k": 2,
        "vdb_threshold": 0.52,
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
