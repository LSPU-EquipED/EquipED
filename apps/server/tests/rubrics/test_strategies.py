"""Unit tests for pure rubric strategy calculators."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from server.modules.rubrics.contracts import (
    CountBandConfig,
    GroundedInstance,
    GroundedInstanceMeasurement,
    GroundedScoreMeasurement,
    GroundedUnit,
    LlmRubricGuidanceConfig,
    PairedCountsMeasurement,
    QualifyingUnitsMeasurement,
    RatioBandConfig,
    ShortSampleConfig,
)
from server.modules.rubrics.strategies import (
    CountScoreResult,
    GuidanceScoreResult,
    RatioScoreResult,
    normalize_llm_guidance_score,
    score_count,
    score_ratio,
)

# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


def _instances(n: int) -> GroundedInstanceMeasurement:
    return GroundedInstanceMeasurement(
        instances=tuple(
            GroundedInstance(
                excerpt=f"Instance {i} excerpt text",
                explanation=f"Explanation for instance {i}",
            )
            for i in range(n)
        )
    )


def _qualifying_units(
    total: int,
    qualifying_ids: list[str] | tuple[str, ...],
    *,
    has_measurable_content: bool = True,
) -> QualifyingUnitsMeasurement:
    units = tuple(
        GroundedUnit(unit_id=f"u_{i}", evidence=f"Evidence for unit {i}")
        for i in range(total)
    )
    return QualifyingUnitsMeasurement(
        total_units=units,
        qualifying_unit_ids=tuple(qualifying_ids),
        has_measurable_content=has_measurable_content,
    )


# ---------------------------------------------------------------------------
# Count Band: Minimum-Count Mode Tests (SME Revision 1 Criteria)
# ---------------------------------------------------------------------------


class TestCountBandMinimumCount:
    """Test count_band in minimum_count mode with grounded instance measurements."""

    def test_op02_interactivity_thresholds(self) -> None:
        """OP-02 thresholds: 4+ -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1."""
        config = CountBandConfig(
            mode="minimum_count",
            threshold_4=4,
            threshold_3=2,
            threshold_2=1,
        )

        expected = [
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 3),
            (4, 4),
            (5, 4),
            (20, 4),
        ]
        for count, exp_score in expected:
            res = score_count(config, _instances(count))
            assert res.score == exp_score
            assert res.count == count
            assert res.mode == "minimum_count"

    def test_op05_enhancement_activities_thresholds(self) -> None:
        """OP-05 thresholds: 3+ -> 4, 2 -> 3, 1 -> 2, 0 -> 1."""
        config = CountBandConfig(
            mode="minimum_count",
            threshold_4=3,
            threshold_3=2,
            threshold_2=1,
        )

        expected = [
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 4),
            (4, 4),
        ]
        for count, exp_score in expected:
            assert score_count(config, _instances(count)).score == exp_score

    def test_a02_varied_assessment_tools_thresholds(self) -> None:
        """A-02 thresholds: 5+ -> 4, 3-4 -> 3, 2 -> 2, <=1 -> 1."""
        config = CountBandConfig(
            mode="minimum_count",
            threshold_4=5,
            threshold_3=3,
            threshold_2=2,
        )

        expected = [
            (0, 1),
            (1, 1),
            (2, 2),
            (3, 3),
            (4, 3),
            (5, 4),
            (8, 4),
        ]
        for count, exp_score in expected:
            assert score_count(config, _instances(count)).score == exp_score

    def test_a03_progress_monitoring_thresholds(self) -> None:
        """A-03 thresholds: 4+ -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1."""
        config = CountBandConfig(
            mode="minimum_count",
            threshold_4=4,
            threshold_3=2,
            threshold_2=1,
        )

        expected = [
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 3),
            (4, 4),
        ]
        for count, exp_score in expected:
            assert score_count(config, _instances(count)).score == exp_score

    def test_a04_prescriptive_feedback_thresholds(self) -> None:
        """A-04 thresholds: 3-4 -> 4, 2 -> 3, 1 -> 2, 0 -> 1."""
        config = CountBandConfig(
            mode="minimum_count",
            threshold_4=3,
            threshold_3=2,
            threshold_2=1,
        )

        expected = [
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 4),
            (4, 4),
        ]
        for count, exp_score in expected:
            assert score_count(config, _instances(count)).score == exp_score


# ---------------------------------------------------------------------------
# Count Band: Maximum-Count Mode Tests (GAD Revision 1 Criteria)
# ---------------------------------------------------------------------------


class TestCountBandMaximumCount:
    """Test count_band in maximum_count mode with grounded instance measurements."""

    def test_gad01_stereotypes_thresholds(self) -> None:
        """GAD-01 thresholds: 0 -> 4, 1 -> 3, 2-3 -> 2, 4+ -> 1."""
        config = CountBandConfig(
            mode="maximum_count",
            threshold_4=0,
            threshold_3=1,
            threshold_2=3,
        )

        expected = [
            (0, 4),
            (1, 3),
            (2, 2),
            (3, 2),
            (4, 1),
            (5, 1),
            (100, 1),
        ]
        for count, exp_score in expected:
            res = score_count(config, _instances(count))
            assert res.score == exp_score
            assert res.count == count
            assert res.mode == "maximum_count"

    def test_gad03_04_05_thresholds(self) -> None:
        """GAD-03, GAD-04, GAD-05: 0 -> 4, 1-2 -> 3, 3-5 -> 2, 6+ -> 1."""
        config = CountBandConfig(
            mode="maximum_count",
            threshold_4=0,
            threshold_3=2,
            threshold_2=5,
        )

        expected = [
            (0, 4),
            (1, 3),
            (2, 3),
            (3, 2),
            (4, 2),
            (5, 2),
            (6, 1),
            (7, 1),
            (50, 1),
        ]
        for count, exp_score in expected:
            assert score_count(config, _instances(count)).score == exp_score


# ---------------------------------------------------------------------------
# Count Band: Validation & Error Handling
# ---------------------------------------------------------------------------


class TestCountBandValidation:
    """Test validation and error handling for score_count."""

    def test_reject_raw_int_measurement(self) -> None:
        """Primitive int measurement must be rejected to enforce grounding."""
        config = CountBandConfig(
            mode="minimum_count",
            threshold_4=4,
            threshold_3=2,
            threshold_2=1,
        )
        with pytest.raises(TypeError, match="Expected GroundedInstanceMeasurement"):
            score_count(config, 3)  # type: ignore[arg-type]

    def test_reject_boolean_measurement(self) -> None:
        config = CountBandConfig(
            mode="minimum_count",
            threshold_4=4,
            threshold_3=2,
            threshold_2=1,
        )
        with pytest.raises(TypeError, match="Expected GroundedInstanceMeasurement"):
            score_count(config, True)  # type: ignore[arg-type]

    def test_reject_invalid_config_type(self) -> None:
        with pytest.raises(TypeError, match="Expected CountBandConfig"):
            score_count("not_a_config", _instances(2))  # type: ignore[arg-type]

    def test_reject_invalid_measurement_type(self) -> None:
        config = CountBandConfig(
            mode="minimum_count",
            threshold_4=4,
            threshold_3=2,
            threshold_2=1,
        )
        with pytest.raises(TypeError, match="Expected GroundedInstanceMeasurement"):
            score_count(config, "invalid")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Ratio Band: Coverage Percentage & Moderate Scale Tests
# ---------------------------------------------------------------------------


class TestRatioBandCoveragePercentage:
    """Test ratio_band in coverage_percentage mode."""

    def test_moderate_scale_boundaries_without_short_sample(self) -> None:
        """Standard moderate scale (80/50/20) for OP-03, OP-04, A-01, A-05."""
        config = RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
        )

        # 10 units total
        # >= 80% -> 4
        m8 = _qualifying_units(10, [f"u_{i}" for i in range(8)])
        res8 = score_ratio(config, m8)
        assert res8.score == 4
        assert res8.metric_value == 80.0
        assert res8.short_sample_applied is False

        m10 = _qualifying_units(10, [f"u_{i}" for i in range(10)])
        assert score_ratio(config, m10).score == 4

        # 50% to <80% -> 3
        m7 = _qualifying_units(10, [f"u_{i}" for i in range(7)])
        res7 = score_ratio(config, m7)
        assert res7.score == 3
        assert res7.metric_value == 70.0

        m5 = _qualifying_units(10, [f"u_{i}" for i in range(5)])
        assert score_ratio(config, m5).score == 3

        # 20% to <50% -> 2
        m4 = _qualifying_units(10, [f"u_{i}" for i in range(4)])
        res4 = score_ratio(config, m4)
        assert res4.score == 2
        assert res4.metric_value == 40.0

        m2 = _qualifying_units(10, [f"u_{i}" for i in range(2)])
        assert score_ratio(config, m2).score == 2

        # < 20% -> 1
        m1 = _qualifying_units(10, [f"u_{i}" for i in range(1)])
        res1 = score_ratio(config, m1)
        assert res1.score == 1
        assert res1.metric_value == 10.0

        m0 = _qualifying_units(10, [])
        assert score_ratio(config, m0).score == 1

    def test_empty_denominator_scores_one_without_short_sample(self) -> None:
        """Empty denominator (total_units=0) scores 1 with metric_value=None."""
        config = RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
        )
        empty = _qualifying_units(0, [])
        res = score_ratio(config, empty)
        assert res.score == 1
        assert res.metric_value is None
        assert res.total_count == 0
        assert res.qualifying_count == 0
        assert res.short_sample_applied is False

    def test_unmeasurable_content_scores_one(self) -> None:
        """has_measurable_content=False scores 1."""
        config = RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
        )
        unmeasurable = _qualifying_units(0, [], has_measurable_content=False)
        res = score_ratio(config, unmeasurable)
        assert res.score == 1
        assert res.metric_value is None
        assert res.short_sample_applied is False


# ---------------------------------------------------------------------------
# Ratio Band: Short Sample Override Tests (OP-01 Topic Coherence)
# ---------------------------------------------------------------------------


class TestRatioBandShortSample:
    """Test OP-01 short-sample issue-count override behavior."""

    @pytest.fixture
    def op01_config(self) -> RatioBandConfig:
        return RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
            short_sample=ShortSampleConfig(
                min_units=4,
                max_issues_4=0,
                max_issues_3=1,
                max_issues_2=2,
            ),
        )

    def test_short_sample_total_3_units(self, op01_config: RatioBandConfig) -> None:
        # Total 3 units: issues = total - qualifying
        # 3 qualifying -> 0 issues -> score 4
        m3_3 = _qualifying_units(3, ["u_0", "u_1", "u_2"])
        res3_3 = score_ratio(op01_config, m3_3)
        assert res3_3.score == 4
        assert res3_3.short_sample_applied is True
        assert res3_3.metric_value == 0.0

        # 2 qualifying -> 1 issue -> score 3
        m3_2 = _qualifying_units(3, ["u_0", "u_1"])
        res3_2 = score_ratio(op01_config, m3_2)
        assert res3_2.score == 3
        assert res3_2.short_sample_applied is True
        assert res3_2.metric_value == 1.0

        # 1 qualifying -> 2 issues -> score 2
        m3_1 = _qualifying_units(3, ["u_0"])
        res3_1 = score_ratio(op01_config, m3_1)
        assert res3_1.score == 2
        assert res3_1.short_sample_applied is True
        assert res3_1.metric_value == 2.0

        # 0 qualifying -> 3 issues -> score 1
        m3_0 = _qualifying_units(3, [])
        res3_0 = score_ratio(op01_config, m3_0)
        assert res3_0.score == 1
        assert res3_0.short_sample_applied is True
        assert res3_0.metric_value == 3.0

    def test_short_sample_total_2_units(self, op01_config: RatioBandConfig) -> None:
        # 2 qualifying -> 0 issues -> 4
        assert score_ratio(op01_config, _qualifying_units(2, ["u_0", "u_1"])).score == 4
        # 1 qualifying -> 1 issue -> 3
        assert score_ratio(op01_config, _qualifying_units(2, ["u_0"])).score == 3
        # 0 qualifying -> 2 issues -> 2
        assert score_ratio(op01_config, _qualifying_units(2, [])).score == 2

    def test_short_sample_total_1_unit(self, op01_config: RatioBandConfig) -> None:
        # 1 qualifying -> 0 issues -> 4
        assert score_ratio(op01_config, _qualifying_units(1, ["u_0"])).score == 4
        # 0 qualifying -> 1 issue -> 3
        assert score_ratio(op01_config, _qualifying_units(1, [])).score == 3

    def test_short_sample_total_0_units_measurable_content(
        self, op01_config: RatioBandConfig
    ) -> None:
        # Real short document with content but 0 transitions -> 0 issues -> score 4
        res = score_ratio(
            op01_config, _qualifying_units(0, [], has_measurable_content=True)
        )
        assert res.score == 4
        assert res.short_sample_applied is True
        assert res.metric_value == 0.0

    def test_short_sample_total_0_units_unmeasurable_content(
        self, op01_config: RatioBandConfig
    ) -> None:
        # No topics / no measurable content at all -> score 1 before short sample
        res = score_ratio(
            op01_config, _qualifying_units(0, [], has_measurable_content=False)
        )
        assert res.score == 1
        assert res.short_sample_applied is False
        assert res.metric_value is None

    def test_standard_percentage_when_at_or_above_min_units(
        self, op01_config: RatioBandConfig
    ) -> None:
        # Exactly 4 units (>= min_units=4): standard coverage percentage applies
        # 4/4 = 100% >= 80% -> score 4
        res4_4 = score_ratio(
            op01_config, _qualifying_units(4, [f"u_{i}" for i in range(4)])
        )
        assert res4_4.score == 4
        assert res4_4.short_sample_applied is False
        assert res4_4.metric_value == 100.0

        # 3/4 = 75% >= 50% -> score 3
        res4_3 = score_ratio(op01_config, _qualifying_units(4, ["u_0", "u_1", "u_2"]))
        assert res4_3.score == 3
        assert res4_3.short_sample_applied is False
        assert res4_3.metric_value == 75.0

        # 2/4 = 50% >= 50% -> score 3
        res4_2 = score_ratio(op01_config, _qualifying_units(4, ["u_0", "u_1"]))
        assert res4_2.score == 3
        assert res4_2.metric_value == 50.0

        # 1/4 = 25% >= 20% -> score 2
        res4_1 = score_ratio(op01_config, _qualifying_units(4, ["u_0"]))
        assert res4_1.score == 2
        assert res4_1.metric_value == 25.0

        # 0/4 = 0% < 20% -> score 1
        res4_0 = score_ratio(op01_config, _qualifying_units(4, []))
        assert res4_0.score == 1
        assert res4_0.metric_value == 0.0


# ---------------------------------------------------------------------------
# Ratio Band: Absolute Difference Mode Tests (GAD-02 Equal Representation)
# ---------------------------------------------------------------------------


class TestRatioBandAbsoluteDifference:
    """Test ratio_band in absolute_difference mode (GAD-02)."""

    @pytest.fixture
    def gad02_config(self) -> RatioBandConfig:
        return RatioBandConfig(
            mode="absolute_difference",
            threshold_4=2.0,
            threshold_3=5.0,
            threshold_2=10.0,
        )

    def test_gad02_difference_boundaries(self, gad02_config: RatioBandConfig) -> None:
        """GAD-02: diff <= 2 -> 4, <= 5 -> 3, <= 10 -> 2, else 1."""
        test_cases = [
            # diff 0 -> 4
            (10, 10, 0, 4),
            # diff 1 -> 4
            (5, 6, 1, 4),
            # diff 2 -> 4
            (7, 5, 2, 4),
            # diff 3 -> 3
            (10, 7, 3, 3),
            # diff 4 -> 3
            (6, 10, 4, 3),
            # diff 5 -> 3
            (0, 5, 5, 3),
            # diff 6 -> 2
            (1, 7, 6, 2),
            # diff 8 -> 2
            (10, 2, 8, 2),
            # diff 10 -> 2
            (15, 5, 10, 2),
            # diff 11 -> 1
            (16, 5, 11, 1),
            # diff 20 -> 1
            (25, 5, 20, 1),
        ]

        for count_a, count_b, expected_diff, expected_score in test_cases:
            meas = PairedCountsMeasurement(count_a=count_a, count_b=count_b)
            res = score_ratio(gad02_config, meas)
            assert res.score == expected_score
            assert res.difference == expected_diff
            assert res.metric_value == float(expected_diff)
            assert res.total_count == count_a + count_b
            assert res.short_sample_applied is False
            assert res.mode == "absolute_difference"


# ---------------------------------------------------------------------------
# Ratio Band: Validation & Mode Mismatch Error Handling
# ---------------------------------------------------------------------------


class TestRatioBandValidation:
    """Test validation and mode mismatch handling for score_ratio."""

    def test_reject_mode_mismatch_coverage_percentage_with_paired(self) -> None:
        config = RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
        )
        paired = PairedCountsMeasurement(count_a=5, count_b=5)
        with pytest.raises(
            TypeError, match="Mode mismatch.*QualifyingUnitsMeasurement"
        ):
            score_ratio(config, paired)  # type: ignore[arg-type]

    def test_reject_mode_mismatch_absolute_difference_with_qualifying(self) -> None:
        config = RatioBandConfig(
            mode="absolute_difference",
            threshold_4=2.0,
            threshold_3=5.0,
            threshold_2=10.0,
        )
        qualifying = _qualifying_units(5, ["u_0", "u_1"])
        with pytest.raises(TypeError, match="Mode mismatch.*PairedCountsMeasurement"):
            score_ratio(config, qualifying)  # type: ignore[arg-type]

    def test_reject_invalid_config_type(self) -> None:
        with pytest.raises(TypeError, match="Expected RatioBandConfig"):
            score_ratio("not_a_config", PairedCountsMeasurement(count_a=1, count_b=1))  # type: ignore[arg-type]

    def test_reject_invalid_measurement_type(self) -> None:
        config = RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
        )
        with pytest.raises(TypeError, match="Mode mismatch"):
            score_ratio(config, 10)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# LLM Guidance Score Normalization Tests
# ---------------------------------------------------------------------------


class TestNormalizeLlmGuidanceScore:
    """Test normalize_llm_guidance_score."""

    @pytest.fixture
    def guidance_config(self) -> LlmRubricGuidanceConfig:
        return LlmRubricGuidanceConfig(
            guidance="Evaluate content quality according to institutional standard."
        )

    def test_valid_grounded_score_measurements(
        self, guidance_config: LlmRubricGuidanceConfig
    ) -> None:
        for score in (1, 2, 3, 4):
            meas = GroundedScoreMeasurement(
                score=score,
                evidence=f"Evidence supporting score {score}",
                reasoning=f"Reasoning for score {score}",
            )
            res = normalize_llm_guidance_score(guidance_config, meas)
            assert res.score == score
            assert isinstance(res, GuidanceScoreResult)

    def test_reject_raw_int_measurement(
        self, guidance_config: LlmRubricGuidanceConfig
    ) -> None:
        """Primitive int measurement must be rejected to enforce grounding."""
        for score in (1, 2, 3, 4):
            with pytest.raises(TypeError, match="Expected GroundedScoreMeasurement"):
                normalize_llm_guidance_score(guidance_config, score)  # type: ignore[arg-type]

    def test_reject_boolean_measurement(
        self, guidance_config: LlmRubricGuidanceConfig
    ) -> None:
        with pytest.raises(TypeError, match="Expected GroundedScoreMeasurement"):
            normalize_llm_guidance_score(guidance_config, True)  # type: ignore[arg-type]

    def test_reject_invalid_config_type(self) -> None:
        meas = GroundedScoreMeasurement(score=3, evidence="Valid evidence")
        with pytest.raises(TypeError, match="Expected LlmRubricGuidanceConfig"):
            normalize_llm_guidance_score("not_a_config", meas)  # type: ignore[arg-type]

    def test_reject_invalid_measurement_type(
        self, guidance_config: LlmRubricGuidanceConfig
    ) -> None:
        with pytest.raises(TypeError, match="Expected GroundedScoreMeasurement"):
            normalize_llm_guidance_score(guidance_config, "3")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Immutability & Deterministic Repeatability Tests
# ---------------------------------------------------------------------------


class TestImmutabilityAndDeterminism:
    """Test that strategy results are immutable and calls are deterministic."""

    def test_results_are_frozen(self) -> None:
        count_res = CountScoreResult(score=4, count=5, mode="minimum_count")
        with pytest.raises(ValidationError):
            count_res.score = 3  # type: ignore[misc]

        ratio_res = RatioScoreResult(
            score=3, mode="coverage_percentage", metric_value=75.0
        )
        with pytest.raises(ValidationError):
            ratio_res.score = 2  # type: ignore[misc]

        guidance_res = GuidanceScoreResult(score=2)
        with pytest.raises(ValidationError):
            guidance_res.score = 1  # type: ignore[misc]

    def test_result_dtos_reject_nan_and_inf(self) -> None:
        with pytest.raises(ValidationError):
            RatioScoreResult(
                score=3,
                mode="coverage_percentage",
                metric_value=float("nan"),
            )

        with pytest.raises(ValidationError):
            RatioScoreResult(
                score=3,
                mode="coverage_percentage",
                metric_value=float("inf"),
            )

    def test_deterministic_repeated_calls(self) -> None:
        count_config = CountBandConfig(
            mode="minimum_count",
            threshold_4=4,
            threshold_3=2,
            threshold_2=1,
        )
        meas = _instances(3)
        res1 = score_count(count_config, meas)
        res2 = score_count(count_config, meas)
        assert res1 == res2
        assert res1.score == res2.score == 3

        ratio_config = RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
        )
        units = _qualifying_units(5, ["u_0", "u_1", "u_2"])
        res_r1 = score_ratio(ratio_config, units)
        res_r2 = score_ratio(ratio_config, units)
        assert res_r1 == res_r2
        assert res_r1.score == res_r2.score == 3
