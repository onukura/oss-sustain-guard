"""
Tests for metric registry helpers.
"""

from types import SimpleNamespace

from oss_sustain_guard import metrics
from oss_sustain_guard.metrics.base import Metric, MetricContext, MetricSpec


class DummyEntryPoint:
    """Simple stand-in for importlib.metadata.EntryPoint."""

    def __init__(self, value):
        self._value = value

    def load(self):
        return self._value


def _spec(name: str) -> MetricSpec:
    def _checker(_data: dict, _context: MetricContext) -> Metric | None:
        return None

    return MetricSpec(name=name, checker=_checker)


def test_load_builtin_metric_specs_filters_missing_metric(monkeypatch):
    """Test builtin metric loading skips modules without METRIC."""
    spec = _spec("Builtin Metric")
    modules = {
        "mod.with.metric": SimpleNamespace(METRIC=spec),
        "mod.without.metric": SimpleNamespace(),
    }

    def fake_import_module(module_path: str):
        return modules[module_path]

    monkeypatch.setattr(metrics, "_BUILTIN_MODULES", list(modules.keys()))
    monkeypatch.setattr(metrics, "import_module", fake_import_module)

    specs = metrics._load_builtin_metric_specs()
    assert specs == [spec]


def test_load_entrypoint_metric_specs_handles_factories(monkeypatch):
    """Test entrypoint loading handles MetricSpec and factories."""
    spec_direct = _spec("Direct Metric")
    spec_factory = _spec("Factory Metric")

    def factory():
        return spec_factory

    entrypoints = [
        DummyEntryPoint(spec_direct),
        DummyEntryPoint(factory),
        DummyEntryPoint("not a spec"),
        DummyEntryPoint(lambda: "nope"),
    ]
    monkeypatch.setattr(metrics, "entry_points", lambda group: entrypoints)

    specs = metrics._load_entrypoint_metric_specs()
    assert specs == [spec_direct, spec_factory]


def test_load_metric_specs_deduplicates(monkeypatch):
    """Test entrypoint metrics do not override builtin names."""
    builtin_specs = [_spec("A"), _spec("B")]
    entry_specs = [_spec("B"), _spec("C")]

    monkeypatch.setattr(metrics, "_load_builtin_metric_specs", lambda: builtin_specs)
    monkeypatch.setattr(metrics, "_load_entrypoint_metric_specs", lambda: entry_specs)

    specs = metrics.load_metric_specs()
    assert [spec.name for spec in specs] == ["A", "B", "C"]
