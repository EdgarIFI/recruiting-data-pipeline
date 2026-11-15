import json
from dataclasses import replace

import pytest

from recruiting_pipeline.config import GenerationConfig
from recruiting_pipeline.generate import write_raw
from recruiting_pipeline.validate import run_validation


@pytest.fixture(scope="session")
def dirty_raw(tmp_path_factory):
    """Default dataset: every data-quality issue injected with a known count."""
    out = tmp_path_factory.mktemp("raw_dirty")
    write_raw(out, GenerationConfig())
    return out


@pytest.fixture(scope="session")
def manifest(dirty_raw):
    return json.loads((dirty_raw / "_manifest.json").read_text())


@pytest.fixture(scope="session")
def report(dirty_raw):
    return run_validation(dirty_raw)


@pytest.fixture(scope="session")
def clean_report(tmp_path_factory):
    """Same generator with zero injections and no schema drift: must produce no findings."""
    cfg = GenerationConfig()
    clean = replace(cfg, injections={k: 0 for k in cfg.injections}, drift_export=0)
    out = tmp_path_factory.mktemp("raw_clean")
    write_raw(out, clean)
    return run_validation(out)
