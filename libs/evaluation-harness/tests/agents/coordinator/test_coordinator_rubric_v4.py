from equiped_harness.agents.coordinator.rubric import guidance_for
from equiped_harness.contracts import LlmRubricGuidanceConfig
from equiped_harness.manifests import get_agent_manifest


def test_v4_manifest_requires_ten_qualitative_rubric_criteria():
    manifest = get_agent_manifest("coordinator", 4)
    assert manifest.min_criteria == manifest.max_criteria == 10
    assert manifest.allowed_criterion_codes == (
        "OP-01",
        "OP-02",
        "OP-03",
        "OP-04",
        "OP-05",
        "A-01",
        "A-02",
        "A-03",
        "A-04",
        "A-05",
    )
    assert manifest.required_criterion_strategies == tuple(
        (code, "llm_rubric_guidance") for code in manifest.allowed_criterion_codes
    )
    assert manifest.supported_strategies == ("llm_rubric_guidance",)


def test_each_code_has_qualitative_guidance_and_four_score_descriptors():
    for code in get_agent_manifest("coordinator", 4).allowed_criterion_codes:
        config = guidance_for(code)
        assert isinstance(config, LlmRubricGuidanceConfig)
        assert config.level_descriptors is not None
        assert [item.score for item in config.level_descriptors] == [4, 3, 2, 1]
        assert all(item.descriptor for item in config.level_descriptors)
    try:
        guidance_for("unknown")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown criterion code should fail")
