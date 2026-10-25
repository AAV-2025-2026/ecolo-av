"""
A local language model behind an OpenAI-compatible server: the same agent on a Mac or an Orin.

    llm = OpenAiChat('qwen3-4b', base_url='http://127.0.0.1:8080/v1')
    text = llm(messages, tools)      # tools: chat-template tools, or None

Servers that speak /v1/chat/completions with tools, all on this computer:

  llama.cpp's llama-server (MIT): Orin (CUDA), Mac (Metal), Linux.
      llama-server -m <model>.gguf --jinja --port 8080
  Ollama (MIT): Orin, Mac, Linux. `ollama serve`; base URL http://127.0.0.1:11434/v1
  TensorRT-LLM's trtllm-serve (Apache 2.0): Orin (JetPack). trtllm-serve <model> --port 8000
  mlx-lm's mlx_lm.server (MIT): Mac. mlx_lm.server --model <id> --port 8080

No new dependency: the standard library's urllib. The reply's tool calls come back as
Qwen-style <tool_call> text, which react.parse_reply already reads, so the ReAct loop is
the same whichever backend runs the model. Greedy decoding (temperature 0), as llm_mlx.
"""

from __future__ import annotations

import json
from typing import Callable, Dict, List, Optional
import urllib.request

DEFAULT_URL = 'http://127.0.0.1:8080/v1'


def wire_messages(messages: List[Dict]) -> List[Dict]:
    """
    Return the agent's chat messages as the OpenAI API wants them.

    The agent keeps a tool call's arguments as a dict (what Hugging Face chat templates
    take); the API wants them as a JSON string, and content never missing.
    """
    out = []
    for m in messages:
        m = dict(m)
        if m.get('content') is None:
            m['content'] = ''
        if m.get('tool_calls'):
            calls = []
            for c in m['tool_calls']:
                fn = dict(c.get('function', {}))
                if not isinstance(fn.get('arguments'), str):
                    fn['arguments'] = json.dumps(fn.get('arguments') or {})
                calls.append({**c, 'function': fn})
            m['tool_calls'] = calls
        out.append(m)
    return out


def request_body(model: str, messages: List[Dict], tools: Optional[List[Dict]],
                 max_tokens: int) -> Dict:
    """Return the /chat/completions request: greedy, no thinking where the server allows."""
    body = {'model': model, 'messages': wire_messages(messages), 'temperature': 0,
            'max_tokens': max_tokens, 'stream': False,
            # llama.cpp, vLLM and mlx_lm.server pass this to the chat template (Qwen 3:
            # answer straight away); servers that don't know it ignore it.
            'chat_template_kwargs': {'enable_thinking': False}}
    if tools:
        body['tools'] = tools
    return body


def reply_text(response: Dict) -> str:
    """
    Return the first choice as text that react.parse_reply reads.

    Its words, then each tool call as <tool_call>{"name": ..., "arguments": {...}}</tool_call>.
    """
    choices = response.get('choices') or []
    if not choices:
        raise ValueError(f'no choices in the reply: {str(response)[:200]}')
    message = choices[0].get('message') or {}
    parts = [(message.get('content') or '').strip()]
    for call in message.get('tool_calls') or []:
        fn = call.get('function') or {}
        args = fn.get('arguments', {})
        if isinstance(args, str):
            try:
                args = json.loads(args) if args.strip() else {}
            except ValueError:
                pass            # parse_reply reports what it can't read
        parts.append('<tool_call>' + json.dumps({'name': fn.get('name'), 'arguments': args})
                     + '</tool_call>')
    return '\n'.join(p for p in parts if p)


def _post(url: str, body: Dict, headers: Dict, timeout: float) -> Dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


class OpenAiChat:
    """One model on an OpenAI-compatible server. Call it with chat messages (and tools)."""

    native_tools = True

    def __init__(self, model_id: str, base_url: str = DEFAULT_URL, max_tokens: int = 400,
                 timeout: float = 120.0, api_key: Optional[str] = None,
                 post: Callable[[str, Dict, Dict, float], Dict] = _post):
        self.model_id = model_id
        self.url = base_url.rstrip('/') + '/chat/completions'
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
        self.post = post
        self.last_tokens = 0

    def __call__(self, messages: List[Dict], tools: Optional[List[Dict]]) -> str:
        response = self.post(self.url, request_body(self.model_id, messages, tools,
                                                    self.max_tokens),
                             self.headers, self.timeout)
        self.last_tokens = int((response.get('usage') or {}).get('completion_tokens') or 0)
        return reply_text(response)
