from __future__ import annotations

import threading
from typing import Optional

from loguru import logger


class LLMClient:
    """백엔드(llama_cpp / transformers)를 추상화한 LLM 인터페이스.

    config.py의 model_backend 값에 따라 자동으로 로딩 방식을 선택한다.
    - "llama_cpp"   : GGUF 모델 + llama-cpp-python (배포 환경)
    - "transformers": HuggingFace 모델 + 4-bit BnB (개발 환경 추론 테스트용)

    generate()는 내부 락으로 직렬화된다.
    대화/function 호출이 동시에 실행되면 VRAM 이중 점유로 OOM이 발생하므로
    동시 호출 시 먼저 온 요청이 끝날 때까지 대기한다.
    """

    def __init__(self, config: Optional[dict] = None):
        from config import get_config  # 루트 config.py

        self.cfg = config or get_config()
        self.backend: str = self.cfg["model_backend"]
        self._model = None
        self._tokenizer = None
        self._generate_lock = threading.Lock()
        self._load()

    # ── 로딩 ─────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self.backend == "llama_cpp":
            self._load_llama_cpp()
        elif self.backend == "transformers":
            self._load_transformers()
        else:
            raise ValueError(f"지원하지 않는 model_backend: {self.backend}")

    def _load_llama_cpp(self) -> None:
        from llama_cpp import Llama  # type: ignore

        model_path = self.cfg.get("model_path")
        if not model_path:
            raise ValueError("deploy 환경에서 model_path가 설정되지 않았습니다.")
        logger.info(f"[llm_client] llama_cpp 로딩: {model_path}")
        import multiprocessing
        n_threads = self.cfg.get("n_threads", multiprocessing.cpu_count())
        self._model = Llama(model_path=model_path, n_ctx=4096, n_threads=n_threads, verbose=False)
        logger.info(f"[llm_client] llama_cpp 스레드: {n_threads}")

    def _load_transformers(self) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        model_name = self.cfg.get("model_name")
        if not model_name:
            raise ValueError("dev 환경에서 model_name이 설정되지 않았습니다.")

        adapter_path = self.cfg.get("adapter_path")
        quantization = self.cfg.get("quantization", "int4")  # "int4" | "int8" | "none"
        logger.info(f"[llm_client] transformers 로딩: {model_name} (quantization={quantization})")
        if adapter_path:
            logger.info(f"[llm_client] LoRA 어댑터: {adapter_path}")

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)

        if quantization == "int4" and self._device == "cuda":
            bnb_cfg = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,  # 이중 양자화 — 추가 ~0.4 bpw 절감
                bnb_4bit_quant_type="nf4",       # NormalFloat4 — 학습 분포 기반 최적 양자화
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=bnb_cfg,
                low_cpu_mem_usage=True,
            )
        elif quantization == "int8" and self._device == "cuda":
            bnb_cfg = BitsAndBytesConfig(load_in_8bit=True)
            self._model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=bnb_cfg,
                low_cpu_mem_usage=True,
            )
        else:
            self._model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.bfloat16,
                low_cpu_mem_usage=True,
            ).to(self._device)

        if adapter_path:
            from peft import PeftModel  # type: ignore
            self._model = PeftModel.from_pretrained(
                self._model, adapter_path, device_map={"": self._device}
            )
            self._model.eval()

        logger.info(f"[llm_client] 디바이스: {self._device}")

    # ── 생성 ─────────────────────────────────────────────────────────────────

    def generate(
        self,
        messages: list[dict],
        stream: bool = False,
        max_tokens: int = 512,
        mode: str = "chat",
    ) -> str:
        """messages 리스트(ChatML 형식)를 받아 어시스턴트 응답 문자열을 반환한다.

        mode='function': JSON 파라미터 추출용 — greedy decoding, 강한 repetition_penalty.
        mode='chat'    : 대화용 — sampling, 기본 repetition_penalty (기본값).
        """
        with self._generate_lock:
            if self.backend == "llama_cpp":
                return self._generate_llama(messages, stream, max_tokens)
            return self._generate_transformers(messages, max_tokens, mode=mode)

    def _generate_llama(
        self, messages: list[dict], stream: bool, max_tokens: int
    ) -> str:
        output = self._model.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            stream=stream,
        )
        if stream:
            full = ""
            for chunk in output:
                delta = chunk["choices"][0]["delta"].get("content", "")
                print(delta, end="", flush=True)
                full += delta
            print()
            return full
        return output["choices"][0]["message"]["content"]

    def _generate_transformers(self, messages: list[dict], max_tokens: int, mode: str = "chat") -> str:
        import torch

        text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(text, return_tensors="pt").to(self._model.device)

        if mode == "function":
            # JSON 추출: greedy decoding + 강한 반복 억제 → LoRA 할루시네이션 방지
            gen_kwargs: dict = dict(do_sample=False, repetition_penalty=1.3)
        else:
            # 대화: sampling 유지
            gen_kwargs = dict(do_sample=True, temperature=0.8, repetition_penalty=1.1)

        with torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                pad_token_id=self._tokenizer.eos_token_id,
                **gen_kwargs,
            )
        response: str = self._tokenizer.decode(
            out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
        )
        return response

    # ── 토큰 카운트 헬퍼 ─────────────────────────────────────────────────────

    def count_tokens(self, text: str) -> int:
        """텍스트의 토큰 수를 반환한다. 모델 미로딩 시 간이 추정값을 사용한다."""
        if self.backend == "llama_cpp" and self._model:
            return len(self._model.tokenize(text.encode("utf-8")))
        if self.backend == "transformers" and self._tokenizer:
            return len(self._tokenizer.encode(text))
        # 모델 로딩 전 간이 추정: 한국어 ~2자/토큰
        return max(1, len(text) // 2)
