import pandas as pd

from recruiting_pipeline.config import GenerationConfig
from recruiting_pipeline.generate import generate


def test_same_seed_same_data():
    a, b = generate(GenerationConfig(seed=7)), generate(GenerationConfig(seed=7))
    for table in ("requisitions", "applications", "crm_activities"):
        pd.testing.assert_frame_equal(a[table], b[table])


def test_different_seed_different_data():
    a, b = generate(GenerationConfig(seed=1)), generate(GenerationConfig(seed=2))
    assert not a["applications"].equals(b["applications"])


def test_row_counts_match_config():
    cfg = GenerationConfig()
    data = generate(cfg)
    assert len(data["requisitions"]) == cfg.n_requisitions
    # duplicates are appended on top of the base applications
    assert len(data["applications"]) == cfg.n_applications + cfg.injections["duplicate_applications"]
    assert len(data["crm_activities"]) == cfg.n_crm_activities


def test_manifest_records_injections():
    cfg = GenerationConfig()
    assert generate(cfg)["manifest"]["injected"] == cfg.injections
