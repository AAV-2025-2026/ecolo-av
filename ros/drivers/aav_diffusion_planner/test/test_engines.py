"""The model's engines and its time budget (engines.py): no ROS, no ONNX Runtime."""

from aav_diffusion_planner import engines
import pytest


def test_every_engine_falls_back_to_the_cpu_last():
    for provider in engines.CHAINS:
        chain = engines.engines(provider)
        assert chain[0][0] == provider
        assert chain[-1][0] == engines.CPU


def test_tensorrt_works_in_fp16_with_its_engines_cached():
    chain = dict(engines.engines(engines.TENSORRT, cache_dir='cache'))
    assert list(chain) == [engines.TENSORRT, engines.CUDA, engines.CPU]
    trt = chain[engines.TENSORRT]
    assert trt['trt_fp16_enable'] is True
    assert trt['trt_engine_cache_enable'] is True and trt['trt_engine_cache_path'] == 'cache'
    assert dict(engines.engines(engines.TENSORRT, fp16=False))[engines.TENSORRT] == {
        'trt_fp16_enable': False}


def test_only_the_engines_this_onnx_runtime_has():
    chain = engines.engines(engines.TENSORRT)
    assert [n for n, _ in engines.usable(chain, [engines.CPU])] == [engines.CPU]
    assert [n for n, _ in engines.usable(chain, [engines.CUDA, engines.CPU])] == [
        engines.CUDA, engines.CPU]


def test_an_unknown_engine_is_refused():
    with pytest.raises(ValueError, match='pick one of'):
        engines.engines('QuantumExecutionProvider')


def test_the_budget_fits_inside_the_hard_stop():
    b = engines.BUDGET
    assert b['crop'] + b['model'] + b['guard'] <= b['total'] < engines.STOP_MS
    assert engines.verdict(49.0, b['model']) == 'OK'
    assert engines.verdict(51.0, b['model']) == 'OVER'
