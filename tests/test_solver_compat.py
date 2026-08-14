from pydantic_ai.usage import RunUsage

from backend.agents.solver import _result_usage


class _CurrentResult:
    usage = RunUsage(input_tokens=123, output_tokens=45)


class _LegacyResult:
    def usage(self) -> RunUsage:
        return RunUsage(input_tokens=67, output_tokens=8)


def test_result_usage_supports_current_property_api():
    usage = _result_usage(_CurrentResult())
    assert usage.input_tokens == 123
    assert usage.output_tokens == 45


def test_result_usage_supports_legacy_method_api():
    usage = _result_usage(_LegacyResult())
    assert usage.input_tokens == 67
    assert usage.output_tokens == 8
