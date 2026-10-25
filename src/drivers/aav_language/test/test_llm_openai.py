"""The OpenAI-compatible backend (llm_openai.py): no server, no network."""

import json

from aav_language import react
from aav_language.llm_openai import OpenAiChat, reply_text, request_body, wire_messages


def test_tool_call_arguments_go_out_as_json_text():
    messages = [{'role': 'system', 'content': 'x'},
                {'role': 'assistant', 'content': None, 'tool_calls': [
                    {'id': 'call_0', 'type': 'function',
                     'function': {'name': 'drive', 'arguments': {'distance_m': 10}}}]},
                {'role': 'tool', 'tool_call_id': 'call_0', 'name': 'drive', 'content': 'ok'}]
    out = wire_messages(messages)
    assert out[1]['content'] == ''
    assert json.loads(out[1]['tool_calls'][0]['function']['arguments']) == {'distance_m': 10}
    assert messages[1]['tool_calls'][0]['function']['arguments'] == {'distance_m': 10}
    assert out[2] == messages[2]


def test_request_is_greedy_and_sends_tools_only_when_given():
    body = request_body('m', [{'role': 'user', 'content': 'hi'}], None, 400)
    assert body['temperature'] == 0 and body['max_tokens'] == 400
    assert 'tools' not in body
    assert body['chat_template_kwargs'] == {'enable_thinking': False}
    tools = [{'type': 'function', 'function': {'name': 'status'}}]
    assert request_body('m', [], tools, 10)['tools'] == tools


def test_reply_tool_calls_read_as_react_reads_them():
    response = {'choices': [{'message': {
        'content': 'Driving forward.',
        'tool_calls': [{'id': 'a', 'type': 'function', 'function': {
            'name': 'drive', 'arguments': '{"distance_m": 10, "direction": "forward"}'}}]}}]}
    reply = react.parse_reply(reply_text(response))
    assert reply.thought == 'Driving forward.'
    assert [(c.name, c.arguments) for c in reply.calls] == [
        ('drive', {'distance_m': 10, 'direction': 'forward'})]


def test_plain_answer_and_empty_arguments():
    assert react.parse_reply(reply_text(
        {'choices': [{'message': {'content': 'Done.'}}]})).answer == 'Done.'
    text = reply_text({'choices': [{'message': {'content': None, 'tool_calls': [
        {'function': {'name': 'status', 'arguments': ''}}]}}]})
    assert [(c.name, c.arguments) for c in react.parse_reply(text).calls] == [('status', {})]


def test_a_reply_with_no_choices_is_an_error():
    try:
        reply_text({'error': 'model not loaded'})
    except ValueError as e:
        assert 'no choices' in str(e)
    else:
        raise AssertionError('accepted a reply with no choices')


def test_the_chat_posts_to_the_server_it_was_given():
    sent = {}

    def post(url, body, headers, timeout):
        sent.update(url=url, body=body, headers=headers)
        return {'choices': [{'message': {'content': 'hi'}}],
                'usage': {'completion_tokens': 3}}

    llm = OpenAiChat('qwen3-4b', 'http://127.0.0.1:8080/v1/', api_key='local', post=post)
    assert llm([{'role': 'user', 'content': 'hello'}], None) == 'hi'
    assert sent['url'] == 'http://127.0.0.1:8080/v1/chat/completions'
    assert sent['body']['model'] == 'qwen3-4b'
    assert sent['headers'] == {'Authorization': 'Bearer local'}
    assert llm.last_tokens == 3
