"""
A local language model through Apple's MLX (mlx-lm): Macs with Apple silicon only.

    llm = MlxChat('mlx-community/Qwen3-4B-Instruct-2507-4bit')
    text = llm(messages, tools)      # tools: chat-template tools, or None

The model downloads into the Hugging Face cache the first time. Greedy decoding, so the
same request gives the same plan.
"""

from __future__ import annotations

from typing import Dict, List, Optional

DEFAULT_MODEL = 'mlx-community/Qwen3-4B-Instruct-2507-4bit'


class MlxChat:
    """One loaded model. Call it with chat messages (and tools) for the next reply."""

    def __init__(self, model_id: str = DEFAULT_MODEL, max_tokens: int = 400):
        from mlx_lm import load
        self.model_id = model_id
        self.model, self.tokenizer = load(model_id)
        self.max_tokens = max_tokens
        template = getattr(self.tokenizer, 'chat_template', None) or ''
        self.native_tools = 'tools' in template
        self.last_tokens = 0

    def __call__(self, messages: List[Dict], tools: Optional[List[Dict]]) -> str:
        from mlx_lm import generate
        prompt = self.tokenizer.apply_chat_template(
            messages, tools=tools if (tools and self.native_tools) else None,
            add_generation_prompt=True, tokenize=False,
            enable_thinking=False)          # Qwen 3: answer straight away; others ignore it
        text = generate(self.model, self.tokenizer, prompt=prompt,
                        max_tokens=self.max_tokens)
        self.last_tokens = len(self.tokenizer.encode(text))
        return text


def peak_memory_gb() -> float:
    """Return the most memory MLX has held since the last reset, in GB."""
    import mlx.core as mx
    return mx.get_peak_memory() / 1e9


def reset_peak_memory():
    import mlx.core as mx
    mx.reset_peak_memory()
