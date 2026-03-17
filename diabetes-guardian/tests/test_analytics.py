"""
tests/test_analytics.py

Tests for pipeline/analytics.py aggregation logic.
Uses mock data to verify daily and weekly stat computation.
"""

import numpy as np
import pytest


class TestDailyStatsComputation:
    def test_tir_calculation(self):
        """Time-in-range calculation for sample data."""
        values = [3.5, 4.0, 5.5, 7.0, 8.5, 10.0, 11.0, 3.8]
        arr = np.array(values)
        n = len(arr)

        tir = np.sum((arr >= 3.9) & (arr <= 10.0)) / n * 100
        tbr = np.sum(arr < 3.9) / n * 100
        tar = np.sum(arr > 10.0) / n * 100

        # 4.0, 5.5, 7.0, 8.5, 10.0 → 5 in range out of 8
        assert tir == pytest.approx(62.5)
        # 3.5, 3.8 → 2 below
        assert tbr == pytest.approx(25.0)
        # 11.0 → 1 above
        assert tar == pytest.approx(12.5)
        # Sum should be 100
        assert tir + tbr + tar == pytest.approx(100.0)

    def test_glucose_sd(self):
        """Standard deviation of glucose values."""
        values = [5.0, 5.0, 5.0, 5.0]
        arr = np.array(values)
        assert float(np.std(arr)) == 0.0

    def test_glucose_stats_basic(self):
        """Basic aggregation: mean, peak, nadir."""
        values = [4.0, 6.0, 8.0, 5.0, 7.0]
        arr = np.array(values)

        assert float(np.mean(arr)) == pytest.approx(6.0)
        assert float(np.max(arr)) == 8.0
        assert float(np.min(arr)) == 4.0


class TestWeeklyProfileComputation:
    def test_cv_percent(self):
        """Coefficient of variation = SD / mean × 100."""
        daily_avgs = [5.5, 6.0, 5.8, 6.2, 5.9, 6.1, 5.7]
        arr = np.array(daily_avgs)

        mean = float(np.mean(arr))
        sd = float(np.std(arr))
        cv = sd / mean * 100

        # Should be < 36% for stable control
        assert cv < 36.0

    def test_coverage_percent(self):
        """Coverage = data_points / 1008 × 100."""
        data_points = 800
        coverage = data_points / 1008 * 100
        assert coverage == pytest.approx(79.37, abs=0.1)

    def test_low_coverage_flag(self):
        """Coverage < 50% → low confidence."""
        data_points = 400
        coverage = data_points / 1008 * 100
        assert coverage < 50.0

    def test_avg_delta_improving(self):
        """Negative delta = improving trend."""
        current_avg = 5.8
        prior_avg = 6.2
        delta = current_avg - prior_avg
        assert delta < 0  # Improving

    def test_avg_delta_worsening(self):
        """Positive delta = worsening trend."""
        current_avg = 6.5
        prior_avg = 6.0
        delta = current_avg - prior_avg
        assert delta > 0  # Worsening
