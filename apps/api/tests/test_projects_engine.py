import numpy as np
import pandas as pd
import pytest

from src.data.repositories import get_load
from src.projects.base import build_model
from src.projects.data_center import DataCenterProject, MAX_NOMINAL_MW, make_project
from src.schemas.project import Project
from src.simulation.engine import net_load


def test_data_centre_is_constant_24_7_and_hypothetical():
    p = make_project("prj-1", 20)
    assert p.provenance == "hypothetical" and p.type == "data_center"
    assert p.hourly_profile == [20.0] * 24 and p.flexibility_fraction == 0.0
    assert p.metadata["profile"] == "constant_24_7"
    ts = pd.Series(pd.date_range("2025-01-01", periods=48, freq="h", tz="Etc/GMT+5"))
    assert (DataCenterProject(20).hourly_increment_mw(ts) == 20.0).all()


@pytest.mark.parametrize("bad", [0, -5, MAX_NOMINAL_MW + 1])
def test_size_bounds(bad):
    with pytest.raises(ValueError):
        DataCenterProject(bad)


def test_housing_and_depot_are_profile_projects_and_need_a_24_hour_profile():
    """Housing and EV depot arrived with the sandbox (projects/loads.py): they are hourly-profile loads; a profile of the wrong length is refused."""
    with pytest.raises(ValueError):
        build_model(Project(id="p", type="housing", name="H", nominal_load_mw=5))
    ok = build_model(Project(id="p", type="housing", name="H", nominal_load_mw=5, hourly_profile=[1.0] * 24))
    assert ok.hourly_increment_mw(get_load("waterloo-demo").df["timestamp"].iloc[:5]).tolist() == [1.0] * 5


def test_net_load_equation_and_baseline_untouched():
    base = get_load("waterloo-demo").df
    before = base.copy()
    out = net_load(base, [DataCenterProject(20)])
    assert np.allclose(out["net_mw"], out["baseline_mw"] + 20.0)
    assert (out["project_mw"] == 20.0).all() and (out["local_generation_mw"] == 0).all()
    pd.testing.assert_frame_equal(base, before)                 # baseline world never mutated
    assert (get_load("waterloo-demo").df["load_mw"].values == before["load_mw"].values).all()


def test_adding_load_never_lowers_net_load_and_projects_sum():
    base = get_load("waterloo-demo").df
    a, b = net_load(base, [DataCenterProject(10)]), net_load(base, [DataCenterProject(20)])
    assert (b["net_mw"] >= a["net_mw"]).all()
    both = net_load(base, [DataCenterProject(10), DataCenterProject(10)])
    assert np.allclose(both["net_mw"], b["net_mw"])
    assert np.allclose(net_load(base, [])["net_mw"], base["load_mw"])   # no projects == baseline
