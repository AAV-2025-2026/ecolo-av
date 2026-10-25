"""
The ReAct loop: plain English in, a plan of tool calls out, then run after a "yes".

No ROS, no MLX, no MCP imports, so the tests run anywhere. The language model and the
tools come in as functions (llm_mlx.py and agent.py give the real ones).

Thought -> Action -> Observation, repeated, then an answer. The design follows Ben's
SYSC 4415 assignment 3 agent (a TOOL_REGISTRY, a JSON action format, action parsing) and
his mcpsearch project (MLX + an MCP stdio server), with two changes for a car:

- MOVES ARE QUEUED, NOT RUN. While the model plans, each drive/turn/go_to_gps/wait is
  checked by the drive server (its `check` tool: would it be refused?) and queued. The
  observation says "queued". Nothing moves until the person has seen the whole plan and
  typed yes. status, stop and estop run at once: they never need a yes.
- THE MODEL'S OWN TOOL FORMAT FIRST. Qwen and Llama chat templates take a tool list and
  answer in their own format (parse_reply reads all three); Ben's JSON action format is
  the fallback for a model without one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
import time
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

MOVES = ('drive', 'turn', 'go_to_gps')       # queued; run only after a yes
QUEUED = MOVES + ('wait',)                   # wait is queued too: it sits between moves
NOW = ('status', 'stop', 'estop')            # run at once, never need a yes
MODEL_TOOLS = NOW[:1] + MOVES + ('wait',) + NOW[1:]
HIDDEN_ARGS = ('wait',)                      # the agent always waits for a move to end

# Typed alone, these skip the model: stopping must never wait for a language model.
FAST = {'stop': 'stop', 'halt': 'stop', 'stop the car': 'stop', 'estop': 'estop',
        'e-stop': 'estop', 'e stop': 'estop', 'emergency stop': 'estop'}


@dataclass
class ToolCall:
    """One tool call: a name and its arguments."""

    name: str
    arguments: Dict = field(default_factory=dict)

    def text(self) -> str:
        args = ', '.join(f'{k}={v!r}' for k, v in self.arguments.items())
        return f'{self.name}({args})'


@dataclass
class Reply:
    """What the model said in one step."""

    thought: str = ''
    calls: List[ToolCall] = field(default_factory=list)
    answer: Optional[str] = None
    error: Optional[str] = None


def _number(text: str):
    text = text.strip()
    for kind in (int, float):
        try:
            return kind(text)
        except ValueError:
            pass
    try:
        return json.loads(text)
    except ValueError:
        return text


def _json_objects(text: str):
    """Every top-level {...} in text that parses as JSON, with its span."""
    dec = json.JSONDecoder()
    i = 0
    while True:
        i = text.find('{', i)
        if i < 0:
            return
        try:
            obj, end = dec.raw_decode(text, i)
        except ValueError:
            i += 1
            continue
        yield obj, i, end
        i = end


def _as_call(obj) -> Optional[ToolCall]:
    """Read a tool call from one JSON object, in any of the formats models use."""
    if not isinstance(obj, dict):
        return None
    if obj.get('type') == 'action' and 'tool' in obj:            # Ben's JSON actions
        args = obj.get('input') or {}
        return ToolCall(str(obj['tool']), args if isinstance(args, dict) else {})
    if 'function' in obj and isinstance(obj['function'], dict):  # OpenAI-style
        obj = obj['function']
    if 'name' in obj:
        args = obj.get('arguments', obj.get('parameters', {}))
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {}
        return ToolCall(str(obj['name']), args if isinstance(args, dict) else {})
    return None


THINK = re.compile(r'<think>.*?</think>', re.S)
TAGGED = re.compile(r'<tool_call>(.*?)(?:</tool_call>|$)', re.S)
XML_FN = re.compile(r'<function=([\w.-]+)>(.*?)(?:</function>|$)', re.S)
XML_ARG = re.compile(r'<parameter=([\w.-]+)>(.*?)</parameter>', re.S)
GEMMA = re.compile(r'<\|tool_call>\s*call:([\w.-]+)\s*\{(.*?)\}\s*(?:<tool_call\|>|$)', re.S)
GEMMA_QUOTE = '<|"|>'
MISTRAL = re.compile(r'\[TOOL_CALLS\]\s*([\w.-]+)\s*\[ARGS\]\s*')


def _gemma_args(body: str) -> Optional[Dict]:
    """
    Read Gemma 4's arguments: key:value pairs, strings between <|"|> marks.

    distance_m:100,direction:<|"|>right<|"|>  ->  {'distance_m': 100, 'direction': 'right'}
    None if they can't be read (a nested object, say: our tools take none).
    """
    args, i = {}, 0
    while i < len(body):
        colon = body.find(':', i)
        if colon < 0:
            return None if body[i:].strip() else args
        key = body[i:colon].strip().strip('"')
        rest = body[colon + 1:].lstrip()
        start = len(body) - len(rest)
        if rest.startswith(GEMMA_QUOTE):
            end = body.find(GEMMA_QUOTE, start + len(GEMMA_QUOTE))
            if end < 0:
                return None
            value = body[start + len(GEMMA_QUOTE):end]
            i = end + len(GEMMA_QUOTE)
        else:
            end = body.find(',', start)
            end = len(body) if end < 0 else end
            raw = body[start:end].strip()
            if raw.startswith(('{', '[')):
                return None
            value, i = _number(raw), end
        if not key:
            return None
        args[key] = value
        i = body.find(',', i)
        i = len(body) if i < 0 else i + 1
    return args


def parse_reply(text: str) -> Reply:
    """
    Read one model reply: its tool calls, or its answer.

    Formats: Qwen's <tool_call>{"name", "arguments"}</tool_call>; Qwen 3.5's
    <tool_call><function=..><parameter=..>; Gemma 4's <|tool_call>call:name{k:v}<tool_call|>;
    Llama's bare {"name", "parameters"}, perhaps after <|python_tag|>; Ben's
    {"type": "action", "tool", "input"} and {"type": "answer", "content"}.
    <think>...</think> is dropped.
    """
    text = THINK.sub('', text or '').replace('<|python_tag|>', '').strip()
    reply = Reply()
    if MISTRAL.search(text):
        reply.thought = text[:text.find('[TOOL_CALLS]')].strip()
        for m in MISTRAL.finditer(text):
            found = next(iter(_json_objects(text[m.end():])), None)
            if found is None or found[1] != 0 or not isinstance(found[0], dict):
                reply.error = f'could not read the tool call: {text[m.start():][:200]}'
            else:
                reply.calls.append(ToolCall(m.group(1), found[0]))
        return reply
    text = text.replace('[TOOL_CALLS]', '')     # older Mistral: a JSON list follows
    gemma = GEMMA.findall(text)
    if gemma:
        reply.thought = text[:text.find('<|tool_call>')].strip()
        for name, body in gemma:
            args = _gemma_args(body)
            if args is None:
                reply.error = f'could not read the tool call: {name}{{{body.strip()[:200]}}}'
            else:
                reply.calls.append(ToolCall(name, args))
        return reply
    tagged = TAGGED.findall(text)
    if tagged:
        reply.thought = text[:text.find('<tool_call>')].strip()
        for body in tagged:
            fn = XML_FN.search(body)
            if fn:
                args = {k: _number(v) for k, v in XML_ARG.findall(fn.group(2))}
                reply.calls.append(ToolCall(fn.group(1), args))
                continue
            found = [c for c in (_as_call(o) for o, _s, _e in _json_objects(body)) if c]
            if found:
                reply.calls.extend(found)
            else:
                reply.error = f'could not read the tool call: {body.strip()[:200]}'
        return reply
    for obj, start, _end in _json_objects(text):
        if isinstance(obj, dict) and obj.get('type') in ('answer', 'final'):
            reply.thought = str(obj.get('thought', ''))
            reply.answer = str(obj.get('content', obj.get('answer', '')))
            return reply
        call = _as_call(obj)
        if call:
            reply.thought = (str(obj.get('thought', '')) or text[:start]).strip()
            reply.calls.append(call)
    if not reply.calls:
        reply.answer = text
    return reply


def system_prompt(limits: Dict, json_actions: bool = False,
                  tools: Optional[List[Dict]] = None) -> str:
    """Write the instructions, with the server's limits in them."""
    lim = {'max_distance_m': 200, 'max_speed_mps': 1.0, 'max_reverse_distance_m': 10,
           'max_reverse_speed_mps': 0.5, 'min_turn_radius_m': 3.0, **(limits or {})}
    rev_speed = lim['max_reverse_speed_mps']
    text = f"""You drive a small autonomous car (or its simulator) by calling tools.
Work in steps: think in one short sentence, call ONE tool, read its result, repeat. When
nothing is left to do, answer the person in one or two short sentences, with no tool call.

How to drive:
- Units: metres, m/s, degrees.
- drive(distance_m) covers the whole distance. To back up, use direction="reverse".
- turn(angle_deg, radius_m, direction) drives forward along an arc; direction is "left"
  or "right". If no radius is given, use 5. The car cannot turn on the spot.
- If no speed is given, leave speed_mps out (0.5 m/s).
- For several moves, call them in order, one per step. Moves do not run at once: each
  one is queued, and runs after the person types yes. Never repeat a queued move.
- Questions about the car (where, how fast, GPS, e-stop): call status.
- "stop" means stop(). An emergency means estop().

Limits (the server refuses anything more):
- forward: at most {lim['max_distance_m']:g} m per move, at most {lim['max_speed_mps']:g} m/s
- reverse: at most {lim['max_reverse_distance_m']:g} m, at most {rev_speed:g} m/s
- turn radius: at least {lim['min_turn_radius_m'] or 0:.1f} m
If a request breaks a limit, or leaves out what you need (how far?), do NOT call a move:
say why, and ask. Never make a number smaller to fit a limit, and never split a request
into several moves to get round one."""
    if json_actions:
        tool_list = json.dumps(tools or [], indent=1)
        text += f"""

Reply with exactly ONE JSON object and nothing else. To call a tool:
{{"type": "action", "thought": "<one sentence>", "tool": "<name>", "input": {{...}}}}
To answer the person:
{{"type": "answer", "content": "<your answer>"}}

Tools:
{tool_list}"""
    return text


def tool_schemas(mcp_tools: List[Dict]) -> List[Dict]:
    """Turn the MCP tools into chat-template tools, without the agent-only parts."""
    out = []
    for t in mcp_tools:
        if t['name'] not in MODEL_TOOLS:
            continue
        schema = json.loads(json.dumps(t.get('inputSchema') or {'type': 'object'}))
        props = schema.get('properties', {})
        for hidden in HIDDEN_ARGS:
            props.pop(hidden, None)
        for p in props.values():
            p.pop('title', None)
        schema.pop('title', None)
        out.append({'type': 'function', 'function': {
            'name': t['name'], 'description': ' '.join((t.get('description') or '').split()),
            'parameters': schema}})
    return out


@dataclass
class Step:
    """One Thought/Action/Observation, for the transcript and the scores."""

    thought: str
    call: Optional[ToolCall]
    observation: str
    seconds: float          # the model's time for this step
    raw: str = ''


@dataclass
class Plan:
    """What the agent made of one request."""

    steps: List[Step] = field(default_factory=list)
    queued: List[ToolCall] = field(default_factory=list)
    refused: List[Tuple[ToolCall, str]] = field(default_factory=list)
    ran_now: List[ToolCall] = field(default_factory=list)
    answer: str = ''
    request: str = ''

    def moves(self) -> List[ToolCall]:
        return [c for c in self.queued if c.name in MOVES]

    def unsaid(self) -> List[str]:
        """Numbers in the plan that the person never typed (see unsaid_numbers)."""
        return unsaid_numbers(self.request, self.queued)

    def text(self) -> str:
        if not self.queued:
            return 'No moves planned.'
        lines = ['The plan (nothing has moved yet):']
        lines += [f'  {i}. {c.text()}' for i, c in enumerate(self.queued, 1)]
        for note in self.unsaid():
            lines.append(f'  CHECK: {note}')
        return '\n'.join(lines)


# Numbers a plan may use without the person typing them: the tools' defaults, and the
# prompt's default radius.
DEFAULT_NUMBERS = {'speed_mps': (0.5,), 'radius_m': (5.0,), 'curvature': (0.0,)}
NUMBER = re.compile(r'-?\d+(?:\.\d+)?')


def unsaid_numbers(request: str, calls: List[ToolCall]) -> List[str]:
    """
    List the plan's numbers that are not in the request, for the person to check.

    A model sometimes shrinks a request to fit a limit ("drive 250 m" becomes 200 m) or
    makes one up ("go as fast as you can"). The server can't tell; the person can, if the
    plan points it out. Only a warning: a fair conversion ("5 km" is 5000 m) shows too.
    """
    said = [abs(float(n)) for n in NUMBER.findall(request or '')]
    notes = []
    for call in calls:
        for key, value in call.arguments.items():
            try:
                v = abs(float(value))
            except (TypeError, ValueError):
                continue
            if any(abs(v - s) <= 1e-6 * max(1.0, s) for s in said):
                continue
            if any(abs(v - d) < 1e-9 for d in DEFAULT_NUMBERS.get(key, ())):
                continue
            notes.append(f'{call.name}: {key}={value} is not a number you typed')
    return notes


Llm = Callable[[List[Dict], Optional[List[Dict]]], str]
CallTool = Callable[[str, Dict], Awaitable[str]]


class ReactAgent:
    """
    Plans one request with a language model, then runs it once the person agrees.

    llm(messages, tools) -> the model's reply text (tools None in JSON-action mode).
    call_tool(name, args) -> the drive server's reply text (async: MCP).
    """

    def __init__(self, llm: Llm, call_tool: CallTool, tools: List[Dict],
                 limits: Optional[Dict] = None, json_actions: bool = False,
                 max_steps: int = 8, echo: Callable[[str], None] = lambda s: None):
        self.llm = llm
        self.call_tool = call_tool
        self.tools = tools
        self.json_actions = json_actions
        self.max_steps = max_steps
        self.echo = echo
        self.system = system_prompt(limits or {}, json_actions, tools)

    async def plan(self, request: str) -> Plan:
        """Think and act until the model answers. Moves are checked and queued, not run."""
        plan = Plan(request=request)
        messages = [{'role': 'system', 'content': self.system},
                    {'role': 'user', 'content': request}]
        for n in range(self.max_steps):
            t0 = time.monotonic()
            raw = self.llm(messages, None if self.json_actions else self.tools)
            seconds = time.monotonic() - t0
            reply = parse_reply(raw)
            if reply.error and not reply.calls:
                obs = f'error: {reply.error}. Call one tool, in the format you were shown.'
                plan.steps.append(Step(reply.thought, None, obs, seconds, raw))
                messages += [{'role': 'assistant', 'content': raw},
                             {'role': 'user', 'content': obs}]
                continue
            if not reply.calls:
                plan.answer = (reply.answer or '').strip()
                plan.steps.append(Step(reply.thought, None, '', seconds, raw))
                return plan
            call = reply.calls[0]          # one action per step (Llama allows no more)
            obs = await self._observe(call, plan)
            self.echo(f'  Thought: {reply.thought or "-"}\n  Action: {call.text()}\n'
                      f'  Observation: {obs}')
            plan.steps.append(Step(reply.thought, call, obs, seconds, raw))
            messages += self._turn(call, reply.thought, raw, obs, n)
        plan.answer = plan.answer or 'I stopped planning after too many steps.'
        return plan

    def _turn(self, call: ToolCall, thought: str, raw: str, obs: str, n: int) -> List[Dict]:
        if self.json_actions:
            return [{'role': 'assistant', 'content': raw},
                    {'role': 'user', 'content': f'Observation: {obs}'}]
        cid = f'call_{n}'
        return [{'role': 'assistant', 'content': thought,
                 'tool_calls': [{'id': cid, 'type': 'function', 'function': {
                     'name': call.name, 'arguments': call.arguments}}]},
                {'role': 'tool', 'tool_call_id': cid, 'name': call.name, 'content': obs}]

    async def _observe(self, call: ToolCall, plan: Plan) -> str:
        if call.name not in MODEL_TOOLS:
            return f'error: there is no tool called {call.name!r}'
        if call.name in NOW:
            plan.ran_now.append(call)
            return await self.call_tool(call.name, call.arguments)
        if call.name == 'wait':
            plan.queued.append(call)
            return self._queued(plan)
        args = {k: v for k, v in call.arguments.items() if k not in HIDDEN_ARGS}
        verdict = json.loads(await self.call_tool('check', {'tool': call.name,
                                                            'arguments': args}))
        if not verdict.get('ok'):
            plan.refused.append((call, verdict.get('message', 'refused')))
            return f'refused by the server: {verdict.get("message")}. Nothing was queued.'
        plan.queued.append(ToolCall(call.name, args))
        return self._queued(plan)

    @staticmethod
    def _queued(plan: Plan) -> str:
        return (f'queued as step {len(plan.queued)}; it runs after the person types yes. '
                'If the request has another move, call it now; if not, answer.')

    async def execute(self, plan: Plan, on_result: Callable[[ToolCall, Dict], None]
                      ) -> List[Tuple[ToolCall, Dict]]:
        """Run the queued calls in order, stopping at the first that fails."""
        done = []
        for call in plan.queued:
            args = dict(call.arguments)
            if call.name in MOVES:
                args['wait'] = True
            try:
                result = json.loads(await self.call_tool(call.name, args))
            except ValueError as e:
                result = {'ok': False, 'message': f'unreadable reply: {e}'}
            done.append((call, result))
            on_result(call, result)
            if not result.get('ok'):
                break
        return done


def describe(call: ToolCall, result: Dict) -> str:
    """One line about one finished call, for the person."""
    if not result.get('ok'):
        return f'{call.text()}: FAILED - {result.get("message")}'
    bits = [result.get('message') or 'ok']
    if result.get('distance_travelled_m') is not None:
        bits.append(f'travelled {result["distance_travelled_m"]} m')
    if result.get('duration_s') is not None:
        bits.append(f'in {result["duration_s"]} s')
    if result.get('heading_change_deg') is not None and call.name == 'turn':
        bits.append(f'heading changed {result["heading_change_deg"]} deg')
    return f'{call.text()}: ' + ', '.join(bits)
