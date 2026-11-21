"""Tests for the dashboard generator (report.py).

Previously untested. Covers the normal charts plus the degenerate
inputs that used to break them: a single-point smile produced NaN
SVG coordinates (zero-width x scale) and empty GEX bars raised
ValueError from a zero-size reduction.
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from greekslab import chain as ch
from greekslab import report as rp


def test_svg_line_normal_chart_has_no_nan():
    svg = rp._svg_line([100.0, 110.0, 120.0], [0.20, 0.15, 0.22],
                       xlabel="Strike", ylabel="IV")
    assert "<polyline" in svg and "<circle" in svg
    assert "nan" not in svg.lower()
    assert "Strike" in svg


def test_svg_line_single_point_has_no_nan():
    # Regression: x1 == x0 divided by zero and emitted NaN coordinates.
    svg = rp._svg_line([23800.0], [12.5])
    assert "nan" not in svg.lower()
    assert "<circle" in svg


def test_svg_line_constant_y_and_empty():
    svg = rp._svg_line([1.0, 2.0, 3.0], [5.0, 5.0, 5.0])
    assert "nan" not in svg.lower()
    empty = rp._svg_line([], [])
    assert "<svg" in empty and "No data" in empty


def test_svg_bars_sign_colours_and_empty():
    svg = rp._svg_bars([100.0, 110.0], [5.0e7, -3.0e7])
    assert "#38d977" in svg  # positive bar
    assert "#f0524f" in svg  # negative bar
    assert "nan" not in svg.lower()
    # Regression: empty input raised ValueError (zero-size reduction).
    empty = rp._svg_bars([], [])
    assert "<svg" in empty and "No data" in empty


def test_build_dashboard_end_to_end_on_sample_chain(tmp_path):
    path = os.path.join(os.path.dirname(__file__), "..", "data",
                        "sample_nifty_chain.csv")
    raw = pd.read_csv(path)
    chain = ch.add_iv(raw)
    spot = float(raw["spot"].iloc[0])
    out = tmp_path / "dashboard.html"
    returned = rp.build_dashboard(
        ch.smile(chain), ch.gamma_exposure(chain),
        [("ATM IV", "10.8%"), ("Max pain", "23,600")],
        str(out), spot=spot)
    assert returned == str(out)
    html = out.read_text(encoding="utf-8")
    assert "GreeksLab" in html and "ATM IV" in html and "23,600" in html
    assert html.count("<svg") == 2
    assert "nan" not in html.lower()
    # Self-contained / offline promise in the README: no external assets.
    assert "http://" not in html and "https://" not in html
    assert np.isfinite(spot)
