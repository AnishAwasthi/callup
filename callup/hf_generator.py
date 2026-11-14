"""Local Hugging Face text generation for player summaries (no paid API, no GPU required).

``transformers`` and ``torch`` are imported only when a generator is created, so CI and the
app never need them. Install with ``pip install -r requirements-llm.txt``.
"""
from __future__ import annotations

from typing import Protocol

DEFAULT_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"  # Apache-2.0; confirm on the model card
GENERATION_SETTINGS = {
    "do_sample": False,  # greedy decoding: the same inputs give the same text
    "max_new_tokens": 350,
    "repetition_penalty": 1.05,
}
SEED = 0


class Generator(Protocol):
    config: dict

    def generate(self, messages: list[dict]) -> str: ...


class HFGenerator:
    """Chat-template generation with a pinned model revision."""

    def __init__(self, model_id=DEFAULT_MODEL, revision=None, device=None):
        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch.manual_seed(SEED)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, revision=revision, dtype=dtype).to(self.device).eval()
        resolved = getattr(self.model.config, "_commit_hash", None) or revision
        self.config = {
            "model_id": model_id,
            "revision": resolved,
            "requested_revision": revision,
            "dtype": str(dtype).removeprefix("torch."),
            "device": self.device,
            "seed": SEED,
            "generation": dict(GENERATION_SETTINGS),
            "transformers_version": transformers.__version__,
            "torch_version": torch.__version__,
        }

    def generate(self, messages: list[dict]) -> str:
        import torch

        inputs = self.tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt", return_dict=True,
        ).to(self.device)
        with torch.no_grad():
            output = self.model.generate(
                **inputs, **GENERATION_SETTINGS, temperature=None, top_p=None, top_k=None,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        new_tokens = output[0, inputs["input_ids"].shape[1]:]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def fingerprint_config(config: dict) -> dict:
    """The part of the generator config that determines the text (device excluded).

    Device and library versions are recorded in each report but do not make it stale.
    """
    return {key: config[key] for key in ("model_id", "revision", "seed", "generation")}
