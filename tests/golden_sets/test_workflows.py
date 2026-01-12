"""
Integration tests for AristAI workflows using golden set data.

These tests can run in two modes:
1. Unit mode: Tests evaluator logic with mock outputs
2. Integration mode: Actually runs workflows (requires DB and LLM API keys)

Usage:
    # Run unit tests (no external dependencies)
    pytest tests/golden_sets/test_workflows.py -v

    # Run integration tests (requires DB)
    pytest tests/golden_sets/test_workflows.py -v -m integration
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any

from tests.golden_sets.sample_data import (
    get_all_samples,
    get_sample_by_id,
    SESSION_PLANNING_SAMPLES,
    COPILOT_SAMPLES,
    REPORT_SAMPLES,
)
from tests.golden_sets.evaluator import GoldenSetEvaluator, EvaluationResult


# ============ Unit Tests for Evaluator ============

class TestEvaluatorStructure:
    """Test structure evaluation logic."""

    def test_required_keys_all_present(self):
        evaluator = GoldenSetEvaluator()
        output = {"topics": ["a", "b"], "goals": ["c"], "discussion_prompts": ["d"]}
        expected = {"required_keys": ["topics", "goals", "discussion_prompts"]}

        score, details = evaluator.evaluate_structure(output, expected)
        assert score == 1.0
        assert details["required_keys"]["missing"] == []

    def test_required_keys_some_missing(self):
        evaluator = GoldenSetEvaluator()
        output = {"topics": ["a", "b"]}
        expected = {"required_keys": ["topics", "goals", "discussion_prompts"]}

        score, details = evaluator.evaluate_structure(output, expected)
        assert score < 1.0
        assert "goals" in details["required_keys"]["missing"]
        assert "discussion_prompts" in details["required_keys"]["missing"]

    def test_min_count_satisfied(self):
        evaluator = GoldenSetEvaluator()
        output = {"topics": ["a", "b", "c"]}
        expected = {"topics_min_count": 2}

        score, details = evaluator.evaluate_structure(output, expected)
        assert score == 1.0
        assert details["topics"]["actual"] == 3

    def test_min_count_not_satisfied(self):
        evaluator = GoldenSetEvaluator()
        output = {"topics": ["a"]}
        expected = {"topics_min_count": 3}

        score, details = evaluator.evaluate_structure(output, expected)
        assert score < 1.0
        assert details["topics"]["actual"] == 1

    def test_case_presence(self):
        evaluator = GoldenSetEvaluator()

        # With case
        output_with = {"case": {"title": "Test"}}
        score_with, _ = evaluator.evaluate_structure(output_with, {"should_include_case": True})
        assert score_with == 1.0

        # Without case
        output_without = {}
        score_without, _ = evaluator.evaluate_structure(output_without, {"should_include_case": True})
        assert score_without == 0.0


class TestEvaluatorQuality:
    """Test quality evaluation logic."""

    def test_keyword_presence_in_topics(self):
        evaluator = GoldenSetEvaluator()
        output = {"topics": ["stakeholder theory", "CSR practices"]}
        criteria = {"topics_should_mention": ["stakeholder", "CSR"]}

        score, details = evaluator.evaluate_quality(output, criteria)
        assert score == 1.0
        assert len(details["topics_should_mention"]["found"]) == 2

    def test_keyword_partial_match(self):
        evaluator = GoldenSetEvaluator()
        output = {"topics": ["stakeholder theory"]}
        criteria = {"topics_should_mention": ["stakeholder", "CSR", "ethics"]}

        score, details = evaluator.evaluate_quality(output, criteria)
        assert score < 1.0
        assert "stakeholder" in details["topics_should_mention"]["found"]

    def test_evidence_citation(self):
        evaluator = GoldenSetEvaluator()

        # With evidence
        output_with = {"evidence_post_ids": [1, 2, 3]}
        score_with, details = evaluator.evaluate_quality(output_with, {"should_cite_evidence": True})
        assert score_with == 1.0
        assert details["evidence_citation"]["has_evidence"] is True

        # Without evidence
        output_without = {"evidence_post_ids": []}
        score_without, _ = evaluator.evaluate_quality(output_without, {"should_cite_evidence": True})
        assert score_without == 0.0

    def test_poll_interpretation(self):
        evaluator = GoldenSetEvaluator()
        output = {
            "poll_results": [
                {"question": "Test?", "interpretation": "Most students prefer X"}
            ]
        }
        criteria = {"should_interpret_polls": True}

        score, details = evaluator.evaluate_quality(output, criteria)
        assert score == 1.0
        assert details["poll_interpretation"] is True


class TestEvaluatorIntegration:
    """Test full evaluation flow."""

    def test_evaluate_sample_passing(self):
        evaluator = GoldenSetEvaluator()
        sample = {
            "id": "test_001",
            "name": "Test Sample",
            "workflow_type": "test",
            "expected_structure": {
                "required_keys": ["topics", "goals"],
                "topics_min_count": 2,
            },
            "quality_criteria": {
                "topics_should_mention": ["ethics"],
            }
        }
        output = {
            "topics": ["business ethics", "corporate ethics"],
            "goals": ["understand frameworks"],
        }

        result = evaluator.evaluate_sample(sample, output)
        assert result.passed is True
        assert result.overall_score >= 0.7

    def test_evaluate_sample_failing(self):
        evaluator = GoldenSetEvaluator()
        sample = {
            "id": "test_002",
            "name": "Test Sample",
            "workflow_type": "test",
            "expected_structure": {
                "required_keys": ["topics", "goals", "case"],
                "topics_min_count": 3,
            },
            "quality_criteria": {
                "topics_should_mention": ["ethics", "stakeholder", "CSR"],
            }
        }
        output = {
            "topics": ["one"],  # Not enough
            # Missing goals and case
        }

        result = evaluator.evaluate_sample(sample, output)
        assert result.passed is False
        assert result.overall_score < 0.7

    def test_run_evaluation_all_samples(self):
        evaluator = GoldenSetEvaluator(mode="offline")
        summary = evaluator.run_evaluation()

        # All golden set samples should be included
        total_expected = (
            len(SESSION_PLANNING_SAMPLES) +
            len(COPILOT_SAMPLES) +
            len(REPORT_SAMPLES)
        )
        assert summary.total_samples == total_expected

        # With mock outputs, all should pass (evaluator generates compliant mocks)
        assert summary.passed_samples == summary.total_samples


class TestSampleData:
    """Test golden set sample data validity."""

    def test_all_samples_have_required_fields(self):
        all_samples = get_all_samples()
        for workflow_type, samples in all_samples.items():
            for sample in samples:
                assert "id" in sample, f"Missing id in {workflow_type} sample"
                assert "name" in sample, f"Missing name in sample {sample.get('id')}"
                assert "input" in sample, f"Missing input in sample {sample.get('id')}"
                assert "expected_structure" in sample, f"Missing expected_structure in {sample.get('id')}"

    def test_sample_ids_unique(self):
        all_samples = get_all_samples()
        all_ids = []
        for samples in all_samples.values():
            for sample in samples:
                all_ids.append(sample["id"])

        assert len(all_ids) == len(set(all_ids)), "Duplicate sample IDs found"

    def test_get_sample_by_id(self):
        sample = get_sample_by_id("planning_001")
        assert sample is not None
        assert sample["workflow_type"] == "session_planning"
        assert sample["name"] == "Ethics Case Discussion"

        # Non-existent sample
        missing = get_sample_by_id("nonexistent")
        assert missing is None


# ============ Integration Tests (require DB/LLM) ============

@pytest.mark.integration
class TestWorkflowsIntegration:
    """
    Integration tests that actually run workflows.
    Requires database and LLM API keys.

    Run with: pytest tests/golden_sets/test_workflows.py -v -m integration
    """

    @pytest.fixture
    def db_session(self):
        """Create a test database session."""
        from api.core.database import SessionLocal
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    @pytest.mark.skip(reason="Requires database and LLM API")
    def test_session_planning_workflow(self, db_session):
        """Test session planning against golden set."""
        from workflows.session_plan import generate_session_plan

        sample = get_sample_by_id("planning_001")
        input_data = sample["input"]

        # Run actual workflow
        result = generate_session_plan(
            course_name=input_data["course"]["name"],
            objectives=input_data["course"]["objectives_json"],
            session_title=input_data["session_title"],
            instructor_notes=input_data.get("instructor_notes", ""),
        )

        # Evaluate result
        evaluator = GoldenSetEvaluator(mode="live")
        eval_result = evaluator.evaluate_sample(sample, result)

        assert eval_result.passed, f"Session planning failed: {eval_result.errors}"

    @pytest.mark.skip(reason="Requires database and LLM API")
    def test_copilot_workflow(self, db_session):
        """Test copilot against golden set."""
        from workflows.copilot import run_copilot_single_iteration

        sample = get_sample_by_id("copilot_001")
        # Would need to set up test data in DB
        pass

    @pytest.mark.skip(reason="Requires database and LLM API")
    def test_report_workflow(self, db_session):
        """Test report generation against golden set."""
        from workflows.report import run_report_workflow

        sample = get_sample_by_id("report_001")
        # Would need to set up test data in DB
        pass


# ============ CLI Test Runner ============

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
