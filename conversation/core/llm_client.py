from __future__ import annotations

from typing import Optional

from loguru import logger


class LLMClient:
    """백엔드(llama_cpp / transformers)를 추상화한 LLM 인터페이스.

    config.py의 model_backend 값에 따라 자동으로 로딩 방식을 선택한다.
    - "llama_cpp"   : GGUF 모델 + llama-cpp-python (배포 환경)
    - "transformers": HuggingFace 모델 + 4-bit BnB (개발 환경 추론 테스트용)
    """

    def __init__(self, config: Optional[dict] = None):
        from config import get_config  # 루트 config.py

        self.cfg = config or get_config()
        self.backend: str = self.cfg["model_backend"]
        self._model = None
        self._tokenizer = None
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
        self._model = Llama(model_path=model_path, n_ctx=4096, verbose=False)

    def _load_transformers(self) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model_name = self.cfg.get("model_name")
        if not model_name:
            raise ValueError("dev 환경에서 model_name이 설정되지 않았습니다.")
        logger.info(f"[llm_client] transformers 로딩: {model_name}")

        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForCausalLM.from_pretrained(
            model_name,
            dtype=torch.bfloat16,
            low_cpu_mem_usage=True,
        )
        self._model = self._model.to("cuda")

    # ── 생성 ─────────────────────────────────────────────────────────────────

    def generate(
        self,
        messages: list[dict],
        stream: bool = False,
        max_tokens: int = 512,
    ) -> str:
        """messages 리스트(ChatML 형식)를 받아 어시스턴트 응답 문자열을 반환한다."""
        if self.backend == "llama_cpp":
            return self._generate_llama(messages, stream, max_tokens)
        return self._generate_transformers(messages, max_tokens)

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

    def _generate_transformers(self, messages: list[dict], max_tokens: int) -> str:
        import torch

        text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(text, return_tensors="pt").to(self._model.device)
        with torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                do_sample=True,
                temperature=0.8,
                pad_token_id=self._tokenizer.eos_token_id,
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
