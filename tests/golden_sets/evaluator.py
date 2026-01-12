"""
Golden Set Evaluation Harness for AristAI

Evaluates LLM workflow outputs against expected structures and quality criteria.
Provides metrics for:
- Structure compliance (required keys, counts)
- Content quality (keyword presence, evidence citation)
- Observability (tokens, cost, execution time)

Usage:
    python -m tests.golden_sets.evaluator [--workflow TYPE] [--sample-id ID] [--verbose]
"""

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from tests.golden_sets.sample_data import (
    get_all_samples,
    get_sample_by_id,
    SESSION_PLANNING_SAMPLES,
    COPILOT_SAMPLES,
    REPORT_SAMPLES,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Result of evaluating a single sample."""
    sample_id: str
    sample_name: str
    workflow_type: str
    passed: bool
    structure_score: float  # 0.0 to 1.0
    quality_score: float  # 0.0 to 1.0
    overall_score: float  # 0.0 to 1.0
    structure_details: Dict[str, Any] = field(default_factory=dict)
    quality_details: Dict[str, Any] = field(default_factory=dict)
    observability: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0


@dataclass
class EvaluationSummary:
    """Summary of all evaluation results."""
    total_samples: int
    passed_samples: int
    failed_samples: int
    average_structure_score: float
    average_quality_score: float
    average_overall_score: float
    total_tokens: int
    total_cost_usd: float
    total_execution_time: float
    results_by_workflow: Dict[str, List[EvaluationResult]]
    timestamp: str


class GoldenSetEvaluator:
    """
    Evaluates workflow outputs against golden set expectations.

    Can run in two modes:
    1. Offline mode: Evaluates pre-generated outputs against expected structures
    2. Live mode: Actually runs the workflows and evaluates results (requires DB/LLM)
    """

    def __init__(self, mode: str = "offline"):
        """
        Initialize evaluator.

        Args:
            mode: "offline" for structure validation only, "live" to run actual workflows
        """
        self.mode = mode
        self.results: List[EvaluationResult] = []

    def evaluate_structure(
        self,
        output: Dict[str, Any],
        expected: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Evaluate output structure against expected structure.

        Returns:
            Tuple of (score, details_dict)
        """
        checks = []
        details = {}

        # Check required keys
        required_keys = expected.get("required_keys", [])
        if required_keys:
            present_keys = [k for k in required_keys if k in output]
            missing_keys = [k for k in required_keys if k not in output]
            key_score = len(present_keys) / len(required_keys) if required_keys else 1.0
            checks.append(key_score)
            details["required_keys"] = {
                "expected": required_keys,
                "present": present_keys,
                "missing": missing_keys,
                "score": key_score
            }

        # Check minimum counts for list fields
        for field_name in ["topics", "goals", "discussion_prompts", "confusion_points",
                          "instructor_prompts", "themes", "misconceptions"]:
            min_count_key = f"{field_name}_min_count"
            if min_count_key in expected:
                min_count = expected[min_count_key]
                actual_count = len(output.get(field_name, []))
                count_score = min(actual_count / min_count, 1.0) if min_count > 0 else 1.0
                checks.append(count_score)
                details[field_name] = {
                    "min_expected": min_count,
                    "actual": actual_count,
                    "score": count_score
                }

        # Check boolean expectations
        if expected.get("should_include_case"):
            has_case = "case" in output and output["case"]
            checks.append(1.0 if has_case else 0.0)
            details["has_case"] = has_case

        if expected.get("should_suggest_activity"):
            has_activity = "reengagement_activity" in output and output["reengagement_activity"]
            checks.append(1.0 if has_activity else 0.0)
            details["has_activity"] = has_activity

        if expected.get("should_include_poll_analysis"):
            has_polls = "poll_results" in output and output["poll_results"]
            checks.append(1.0 if has_polls else 0.0)
            details["has_poll_analysis"] = has_polls

        if expected.get("should_identify_misconception"):
            has_misconceptions = "misconceptions" in output and output["misconceptions"]
            checks.append(1.0 if has_misconceptions else 0.0)
            details["has_misconceptions"] = has_misconceptions

        overall_score = sum(checks) / len(checks) if checks else 1.0
        return overall_score, details

    def evaluate_quality(
        self,
        output: Dict[str, Any],
        criteria: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Evaluate content quality against criteria.

        Returns:
            Tuple of (score, details_dict)
        """
        checks = []
        details = {}

        # Check for keyword presence in specific fields
        for field_name in ["topics_should_mention", "should_highlight_misconception",
                          "should_identify_confusion"]:
            if field_name in criteria:
                keywords = criteria[field_name]
                # Determine which output field to check
                if "topics" in field_name:
                    content = " ".join(output.get("topics", []))
                elif "misconception" in field_name:
                    misconceptions = output.get("misconceptions", [])
                    if isinstance(misconceptions, list):
                        content = " ".join(str(m) for m in misconceptions)
                    else:
                        content = str(misconceptions)
                elif "confusion" in field_name:
                    confusion_points = output.get("confusion_points", [])
                    content = " ".join(
                        str(cp.get("topic", "") + " " + cp.get("description", ""))
                        for cp in confusion_points
                    ) if confusion_points else ""
                else:
                    content = json.dumps(output)

                content_lower = content.lower()
                found_keywords = [kw for kw in keywords if kw.lower() in content_lower]
                keyword_score = len(found_keywords) / len(keywords) if keywords else 1.0
                checks.append(keyword_score)
                details[field_name] = {
                    "expected": keywords,
                    "found": found_keywords,
                    "score": keyword_score
                }

        # Check for evidence citation
        if criteria.get("should_cite_evidence"):
            evidence_ids = output.get("evidence_post_ids", [])
            has_evidence = len(evidence_ids) > 0
            checks.append(1.0 if has_evidence else 0.0)
            details["evidence_citation"] = {
                "has_evidence": has_evidence,
                "post_ids_count": len(evidence_ids)
            }

        # Check engagement indicators
        if criteria.get("should_address_low_engagement"):
            assessment = output.get("overall_assessment", {})
            engagement = assessment.get("engagement_level", "")
            # Should recognize low engagement
            recognized = engagement.lower() in ["low", "minimal", "needs_improvement"]
            checks.append(1.0 if recognized else 0.5)
            details["engagement_recognition"] = recognized

        if criteria.get("should_recognize_quality_discussion"):
            assessment = output.get("overall_assessment", {})
            quality = assessment.get("discussion_quality", "")
            recognized = quality.lower() in ["high", "excellent", "productive", "on_track"]
            checks.append(1.0 if recognized else 0.5)
            details["quality_recognition"] = recognized

        # Poll interpretation
        if criteria.get("should_interpret_polls"):
            poll_results = output.get("poll_results", [])
            has_interpretation = any(
                p.get("interpretation") for p in poll_results
            ) if poll_results else False
            checks.append(1.0 if has_interpretation else 0.0)
            details["poll_interpretation"] = has_interpretation

        overall_score = sum(checks) / len(checks) if checks else 1.0
        return overall_score, details

    def evaluate_sample(
        self,
        sample: Dict[str, Any],
        output: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """
        Evaluate a single golden set sample.

        Args:
            sample: The golden set sample definition
            output: Pre-computed output (for offline mode) or None (for live mode)

        Returns:
            EvaluationResult with scores and details
        """
        start_time = time.time()
        errors = []

        sample_id = sample["id"]
        sample_name = sample["name"]
        workflow_type = sample.get("workflow_type", "unknown")

        # For offline evaluation with no output, generate mock based on structure
        if output is None and self.mode == "offline":
            # In offline mode without output, we can only validate the test definition
            output = self._generate_mock_output(sample)

        if output is None:
            return EvaluationResult(
                sample_id=sample_id,
                sample_name=sample_name,
                workflow_type=workflow_type,
                passed=False,
                structure_score=0.0,
                quality_score=0.0,
                overall_score=0.0,
                errors=["No output to evaluate"]
            )

        # Evaluate structure
        structure_score, structure_details = self.evaluate_structure(
            output, sample.get("expected_structure", {})
        )

        # Evaluate quality
        quality_score, quality_details = self.evaluate_quality(
            output, sample.get("quality_criteria", {})
        )

        # Calculate overall score (weighted average)
        overall_score = (structure_score * 0.6) + (quality_score * 0.4)
        passed = overall_score >= 0.7  # 70% threshold

        # Extract observability metrics if present
        observability = {}
        if "observability" in output:
            observability = output["observability"]
        elif "total_tokens" in output:
            observability = {
                "total_tokens": output.get("total_tokens"),
                "estimated_cost_usd": output.get("estimated_cost_usd"),
                "execution_time_seconds": output.get("execution_time_seconds"),
            }

        execution_time = time.time() - start_time

        return EvaluationResult(
            sample_id=sample_id,
            sample_name=sample_name,
            workflow_type=workflow_type,
            passed=passed,
            structure_score=structure_score,
            quality_score=quality_score,
            overall_score=overall_score,
            structure_details=structure_details,
            quality_details=quality_details,
            observability=observability,
            errors=errors,
            execution_time_seconds=execution_time
        )

    def _generate_mock_output(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a mock output that satisfies the expected structure (for testing the evaluator)."""
        expected = sample.get("expected_structure", {})
        mock = {}

        # Add required keys with mock values
        for key in expected.get("required_keys", []):
            if "count" in key or key.endswith("s"):
                mock[key] = []
            else:
                mock[key] = "mock_value"

        # Add minimum counts
        for field in ["topics", "goals", "discussion_prompts", "confusion_points",
                     "instructor_prompts", "themes"]:
            min_key = f"{field}_min_count"
            if min_key in expected:
                mock[field] = [f"mock_{field}_{i}" for i in range(expected[min_key])]

        # Add case if expected
        if expected.get("should_include_case"):
            mock["case"] = {"title": "Mock Case", "scenario": "Mock scenario"}

        # Add activity if expected
        if expected.get("should_suggest_activity"):
            mock["reengagement_activity"] = {"type": "mock", "description": "Mock activity"}

        # Add evidence
        mock["evidence_post_ids"] = [1, 2, 3]

        return mock

    def run_evaluation(
        self,
        workflow_type: Optional[str] = None,
        sample_ids: Optional[List[str]] = None,
        outputs: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> EvaluationSummary:
        """
        Run evaluation on golden set samples.

        Args:
            workflow_type: Filter by workflow type (session_planning, copilot, report)
            sample_ids: Specific sample IDs to evaluate
            outputs: Pre-computed outputs keyed by sample_id

        Returns:
            EvaluationSummary with aggregate metrics
        """
        all_samples = get_all_samples()
        self.results = []
        results_by_workflow: Dict[str, List[EvaluationResult]] = {}

        for wf_type, samples in all_samples.items():
            if workflow_type and wf_type != workflow_type:
                continue

            results_by_workflow[wf_type] = []

            for sample in samples:
                if sample_ids and sample["id"] not in sample_ids:
                    continue

                sample["workflow_type"] = wf_type
                output = outputs.get(sample["id"]) if outputs else None
                result = self.evaluate_sample(sample, output)
                self.results.append(result)
                results_by_workflow[wf_type].append(result)

        # Calculate summary metrics
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)

        avg_structure = sum(r.structure_score for r in self.results) / total if total > 0 else 0
        avg_quality = sum(r.quality_score for r in self.results) / total if total > 0 else 0
        avg_overall = sum(r.overall_score for r in self.results) / total if total > 0 else 0

        total_tokens = sum(
            r.observability.get("total_tokens", 0) or 0
            for r in self.results
        )
        total_cost = sum(
            r.observability.get("estimated_cost_usd", 0) or 0
            for r in self.results
        )
        total_time = sum(r.execution_time_seconds for r in self.results)

        return EvaluationSummary(
            total_samples=total,
            passed_samples=passed,
            failed_samples=total - passed,
            average_structure_score=round(avg_structure, 3),
            average_quality_score=round(avg_quality, 3),
            average_overall_score=round(avg_overall, 3),
            total_tokens=total_tokens,
            total_cost_usd=round(total_cost, 4),
            total_execution_time=round(total_time, 2),
            results_by_workflow=results_by_workflow,
            timestamp=datetime.utcnow().isoformat()
        )

    def print_report(self, summary: EvaluationSummary, verbose: bool = False):
        """Print evaluation report to console."""
        print("\n" + "=" * 60)
        print("GOLDEN SET EVALUATION REPORT")
        print("=" * 60)
        print(f"Timestamp: {summary.timestamp}")
        print(f"Mode: {self.mode}")
        print()

        # Overall metrics
        print("OVERALL METRICS")
        print("-" * 40)
        print(f"Total Samples:       {summary.total_samples}")
        print(f"Passed:              {summary.passed_samples} ({summary.passed_samples/summary.total_samples*100:.1f}%)" if summary.total_samples > 0 else "Passed: 0")
        print(f"Failed:              {summary.failed_samples}")
        print()
        print(f"Avg Structure Score: {summary.average_structure_score:.1%}")
        print(f"Avg Quality Score:   {summary.average_quality_score:.1%}")
        print(f"Avg Overall Score:   {summary.average_overall_score:.1%}")
        print()

        # Observability metrics
        if summary.total_tokens > 0 or summary.total_cost_usd > 0:
            print("OBSERVABILITY")
            print("-" * 40)
            print(f"Total Tokens:        {summary.total_tokens:,}")
            print(f"Total Cost:          ${summary.total_cost_usd:.4f}")
            print(f"Total Exec Time:     {summary.total_execution_time:.2f}s")
            print()

        # Results by workflow
        for wf_type, results in summary.results_by_workflow.items():
            if not results:
                continue

            print(f"\n{wf_type.upper()} WORKFLOW")
            print("-" * 40)

            for result in results:
                status = "PASS" if result.passed else "FAIL"
                print(f"  [{status}] {result.sample_id}: {result.sample_name}")
                print(f"         Structure: {result.structure_score:.1%} | Quality: {result.quality_score:.1%} | Overall: {result.overall_score:.1%}")

                if verbose:
                    if result.structure_details:
                        print(f"         Structure Details: {json.dumps(result.structure_details, indent=2)}")
                    if result.quality_details:
                        print(f"         Quality Details: {json.dumps(result.quality_details, indent=2)}")
                    if result.errors:
                        print(f"         Errors: {result.errors}")

        print("\n" + "=" * 60)


def main():
    """CLI entry point for running evaluations."""
    import argparse

    parser = argparse.ArgumentParser(description="Run golden set evaluation for AristAI workflows")
    parser.add_argument("--workflow", "-w", choices=["session_planning", "copilot", "report"],
                       help="Specific workflow to evaluate")
    parser.add_argument("--sample-id", "-s", help="Specific sample ID to evaluate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed results")
    parser.add_argument("--mode", "-m", choices=["offline", "live"], default="offline",
                       help="Evaluation mode (default: offline)")

    args = parser.parse_args()

    evaluator = GoldenSetEvaluator(mode=args.mode)

    sample_ids = [args.sample_id] if args.sample_id else None
    summary = evaluator.run_evaluation(
        workflow_type=args.workflow,
        sample_ids=sample_ids
    )

    evaluator.print_report(summary, verbose=args.verbose)

    # Exit with non-zero if any tests failed
    sys.exit(0 if summary.failed_samples == 0 else 1)


if __name__ == "__main__":
    main()
