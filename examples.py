#!/usr/bin/env python3
"""
QiskitSage Usage Examples

This file demonstrates how to use QiskitSage programmatically in various scenarios.
"""

import sys
import os
from typing import List
from qiskitsage.context_builder import ContextBuilder
from qiskitsage.agents.syntax_agent import SyntaxAgent
from qiskitsage.agents.performance_agent import PerformanceAgent
from qiskitsage.agents.semantic_agent import SemanticAgent
from qiskitsage.agents.ffi_agent import FFIAgent
from qiskitsage.agents.judge_agent import JudgeAgent
from qiskitsage.models import ReviewResult, Finding
from qiskitsage.context_graph import ContextGraph

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def example_1_basic_pr_review():
    """Example 1: Basic PR review with all agents."""
    logger.info("Example 1: Basic PR Review")
    logger.info("=" * 80)

    # PR URL to analyze
    pr_url = "https://github.com/Qiskit/qiskit/pull/12345"  # Replace with actual PR

    # 1. Build context graph
    logger.info(f"Building context graph for {pr_url}...")
    builder = ContextBuilder()
    graph = builder.build(pr_url)

    logger.info(f"✓ Built graph with {len(graph.changed_files)} changed files")
    logger.info(f"✓ Analyzed {len(graph.functions)} functions")
    logger.info(f"✓ Context size: {graph.context_size_chars} chars")
    logger.info(f"✓ Build time: {graph.build_time_seconds}s")

    # 2. Run all agents
    logger.info("\nRunning review agents...")
    findings: List[Finding] = []

    for agent_name, agent in [
        ("Syntax", SyntaxAgent()),
        ("Performance", PerformanceAgent()),
        ("Semantic", SemanticAgent()),
        ("FFI Safety", FFIAgent())
    ]:
        logger.info(f"  → {agent_name} agent...")
        agent_findings = agent.review(graph)
        findings.extend(agent_findings)
        logger.info(f"    Found {len(agent_findings)} findings")

    # 3. Generate report
    logger.info("\nGenerating final report...")
    judge = JudgeAgent()
    result = judge.generate_report(graph, findings)

    # 4. Display results
    logger.info("\n" + "=" * 80)
    logger.info("REVIEW RESULTS")
    logger.info("=" * 80)
    logger.info(f"PR: {result.pr_url}")
    logger.info(f"Total findings: {result.total_findings}")
    logger.info(f"Critical: {result.critical_count}")
    logger.info(f"High: {result.high_count}")
    logger.info(f"Execution time: {result.execution_time_seconds:.1f}s")

    if result.semantic_regression_detected:
        logger.info("🐛 SEMANTIC REGRESSION DETECTED")
    if result.ffi_risk_detected:
        logger.info("⚠️  FFI RISK DETECTED")

    # 5. Show findings by severity
    logger.info("\nFindings by Severity:")
    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        severity_findings = [
            f for f in result.findings
            if f.severity.value == severity
        ]
        if severity_findings:
            logger.info(f"\n{severity} ({len(severity_findings)}):")
            for finding in severity_findings:
                logger.info(f"  • {finding.title} ({finding.file}:{finding.line})")

    # 6. Save markdown report
    with open("review_report.md", "w") as f:
        f.write(result.comment_markdown)
    logger.info("\n✓ Saved detailed report to review_report.md")

    return result


def example_2_specific_agents_only():
    """Example 2: Run only specific agents."""
    logger.info("\n\nExample 2: Specific Agents Only")
    logger.info("=" * 80)

    pr_url = "https://github.com/Qiskit/qiskit/pull/67890"  # Replace with actual PR

    builder = ContextBuilder()
    graph = builder.build(pr_url)

    # Only run syntax and performance agents
    logger.info("Running only Syntax and Performance agents...")
    findings = []

    syntax_agent = SyntaxAgent()
    perf_agent = PerformanceAgent()

    findings.extend(syntax_agent.review(graph))
    findings.extend(perf_agent.review(graph))

    judge = JudgeAgent()
    result = judge.generate_report(graph, findings)

    logger.info(f"Total findings with 2 agents: {result.total_findings}")
    return result


def example_3_filter_by_category():
    """Example 3: Filter findings by category."""
    logger.info("\n\nExample 3: Filter by Category")
    logger.info("=" * 80)

    # Get a sample PR review
    result = example_1_basic_pr_review()

    # Group findings by category
    from collections import defaultdict
    by_category = defaultdict(list)
    for finding in result.findings:
        by_category[finding.category.value].append(finding)

    logger.info("\nFindings by Category:")
    for category, findings in by_category.items():
        logger.info(f"\n{category} ({len(findings)} findings):")
        for finding in findings:
            severity_marker = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "🔍", "LOW": "💡"}.get(
                finding.severity.value, "•"
            )
            logger.info(f"  {severity_marker} {finding.title} ({finding.file}:{finding.line})")


def example_4_react_to_semantic_regression():
    """Example 4: Special handling of semantic regressions."""
    logger.info("\n\nExample 4: Handling Semantic Regressions")
    logger.info("=" * 80)

    pr_url = "https://github.com/Qiskit/qiskit/pull/11111"  # Replace with actual PR

    builder = ContextBuilder()
    graph = builder.build(pr_url)

    # Run semantic agent first
    semantic_agent = SemanticAgent()
    findings = semantic_agent.review(graph)

    # Check for regressions
    regression_findings = [
        f for f in findings
        if hasattr(f, 'probe_circuit') and f.fidelity_before and f.fidelity_after
        and f.fidelity_after < f.fidelity_before
    ]

    if regression_findings:
        logger.info("🐛 REGRESSION DETECTED!")
        logger.info("Affected circuits:")
        for finding in regression_findings:
            logger.info(f"  • {finding.probe_circuit}")
            logger.info(f"    Fidelity before: {finding.fidelity_before:.4f}")
            logger.info(f"    Fidelity after:  {finding.fidelity_after:.4f}")

        # Fail fast - don't run other agents if regression found
        logger.info("\nAborting review due to semantic regression.")
        sys.exit(1)

    # If no regression, continue with other agents
    logger.info("✓ No semantic regression detected, continuing review...")


def example_5_process_multiple_prs():
    """Example 5: Process multiple PRs in batch."""
    logger.info("\n\nExample 5: Batch Processing Multiple PRs")
    logger.info("=" * 80)

    pr_urls = [
        "https://github.com/Qiskit/qiskit/pull/12345",
        "https://github.com/Qiskit/qiskit/pull/67890",
        "https://github.com/Qiskit/qiskit/pull/11111"
    ]

    results = []
    for pr_url in pr_urls:
        logger.info(f"\nProcessing {pr_url}...")
        try:
            builder = ContextBuilder()
            graph = builder.build(pr_url)

            findings = []
            for agent in [SyntaxAgent(), PerformanceAgent()]:
                findings.extend(agent.review(graph))

            judge = JudgeAgent()
            result = judge.generate_report(graph, findings)
            results.append(result)

            logger.info(f"  ✓ Found {result.total_findings} findings")

            # Save individual report
            filename = f"review_{result.pr_number}.md"
            with open(filename, "w") as f:
                f.write(result.comment_markdown)
            logger.info(f"  ✓ Saved report to {filename}")

        except Exception as e:
            logger.info(f"  ✗ Error processing PR: {e}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("BATCH SUMMARY")
    logger.info("=" * 80)
    total_findings = sum(r.total_findings for r in results)
    total_critical = sum(r.critical_count for r in results)

    logger.info(f"PRs processed: {len(results)}")
    logger.info(f"Total findings: {total_findings}")
    logger.info(f"Total critical: {total_critical}")

    if total_critical > 0:
        logger.info("\n⚠️  Some PRs require attention!")


def example_6_check_for_rust_ffi():
    """Example 6: Detect Rust FFI changes."""
    logger.info("\n\nExample 6: FFI Safety Check")
    logger.info("=" * 80)

    pr_url = "https://github.com/Qiskit/qiskit/pull/22222"  # Replace with actual PR

    builder = ContextBuilder()
    graph = builder.build(pr_url)

    # Check if there are Rust changes
    if graph.has_rust_changes:
        logger.info("ℹ️  Detected Rust changes - running FFI safety agent...")
        ffi_agent = FFIAgent()
        findings = ffi_agent.review(graph)

        panic_findings = [f for f in findings if hasattr(f, 'rust_severity') and f.rust_severity == 'PANIC']
        memory_findings = [f for f in findings if hasattr(f, 'rust_severity') and f.rust_severity == 'MEMORY']

        if panic_findings:
            logger.info("🚨 PANIC RISK DETECTED:")
            for finding in panic_findings:
                logger.info(f"  • {finding.title} ({finding.file}:{finding.line})")

        if memory_findings:
            logger.info("⚠️  MEMORY SAFETY ISSUES:")
            for finding in memory_findings:
                logger.info(f"  • {finding.title} ({finding.file}:{finding.line})")

        if not panic_findings and not memory_findings:
            logger.info("✓ No critical FFI safety issues found")

    else:
        logger.info("ℹ️  No Rust changes detected - skipping FFI agent")


def example_7_custom_agent_filter():
    """Example 7: Custom logic to decide which agents to run."""
    logger.info("\n\nExample 7: Dynamic Agent Selection")
    logger.info("=" * 80)

    pr_url = "https://github.com/Qiskit/qiskit/pull/33333"  # Replace with actual PR

    builder = ContextBuilder()
    graph = builder.build(pr_url)

    logger.info("Analyzing PR characteristics...")

    # Decide which agents to run based on PR characteristics
    agents_to_run = []

    # Always run syntax agent
    agents_to_run.append(("Syntax", SyntaxAgent()))
    logger.info("  ✓ Syntax agent (always)")

    # Run performance agent if transpiler/synthesis changes
    if graph.has_transpiler_changes or graph.has_synthesis_changes:
        agents_to_run.append(("Performance", PerformanceAgent()))
        logger.info("  ✓ Performance agent (transpiler changes detected)")

    # Run semantic agent if quantum info changes
    if graph.has_quantum_info_changes:
        agents_to_run.append(("Semantic", SemanticAgent()))
        logger.info("  ✓ Semantic agent (quantum info changes detected)")

    # Run FFI agent if Rust changes
    if graph.has_rust_changes:
        agents_to_run.append(("FFI", FFIAgent()))
        logger.info("  ✓ FFI agent (Rust changes detected)")

    # Run selected agents
    findings = []
    for agent_name, agent in agents_to_run:
        logger.info(f"\nRunning {agent_name}...")
        findings.extend(agent.review(graph))

    # Generate report
    judge = JudgeAgent()
    result = judge.generate_report(graph, findings)

    logger.info(f"\n✓ Review complete: {result.total_findings} findings")


def example_8_output_json_api():
    """Example 8: Return results as JSON for API usage."""
    logger.info("\n\nExample 8: JSON API Output")
    logger.info("=" * 80)

    import json

    pr_url = "https://github.com/Qiskit/qiskit/pull/44444"  # Replace with actual PR

    # Build context and run review
    builder = ContextBuilder()
    graph = builder.build(pr_url)

    findings = []
    for agent in [SyntaxAgent(), PerformanceAgent(), SemanticAgent(), FFIAgent()]:
        findings.extend(agent.review(graph))

    judge = JudgeAgent()
    result = judge.generate_report(graph, findings)

    # Convert to JSON-serializable format
    json_result = {
        "pr_url": result.pr_url,
        "pr_number": result.pr_number,
        "total_findings": result.total_findings,
        "critical_count": result.critical_count,
        "high_count": result.high_count,
        "semantic_regression_detected": result.semantic_regression_detected,
        "ffi_risk_detected": result.ffi_risk_detected,
        "agents_run": result.agents_run,
        "execution_time_seconds": result.execution_time_seconds,
        "findings": [
            {
                "agent_id": f.agent_id,
                "severity": f.severity.value,
                "category": f.category.value,
                "file": f.file,
                "line": f.line,
                "title": f.title,
                "description": f.description,
                "suggestion": f.suggestion,
                "confidence": f.confidence,
                "evidence": f.evidence[:200]  # Truncate long evidence
            }
            for f in result.findings
        ]
    }

    logger.info(json.dumps(json_result, indent=2))

    # Save to file
    with open("review_result.json", "w") as f:
        json.dump(json_result, f, indent=2)
    logger.info("\n✓ Saved JSON output to review_result.json")


def main():
    """Run all examples."""
    logger.info("QiskitSage Usage Examples")
    logger.info("=" * 80)
    logger.info("This file demonstrates various ways to use QiskitSage programmatically.")
    logger.info("\nIndividual examples can be run by calling their functions.")
    logger.info("\nAvailable examples:")
    logger.info("  1. example_1_basic_pr_review() - Basic PR review")
    logger.info("  2. example_2_specific_agents_only() - Run specific agents")
    logger.info("  3. example_3_filter_by_category() - Filter findings")
    logger.info("  4. example_4_react_to_semantic_regression() - Error on regression")
    logger.info("  5. example_5_process_multiple_prs() - Batch processing")
    logger.info("  6. example_6_check_for_rust_ffi() - FFI safety")
    logger.info("  7. example_7_custom_agent_filter() - Dynamic agent selection")
    logger.info("  8. example_8_output_json_api() - JSON API output")

    logger.info("\n\n" + "=" * 80)
    logger.info("RUNNING EXAMPLE 1: Basic PR Review")
    logger.info("=" * 80)

    # For demonstration, we're using placeholder PR URLs
    # In production, replace these with actual PR URLs from Qiskit repo
    logger.info("⚠️  Note: Replace placeholder PR URLs (12345, 67890, etc.) with actual PR URLs")
    logger.info("=" * 80 + "\n")

    # Run the first example
    try:
        example_1_basic_pr_review()
    except Exception as e:
        logger.info(f"\n❌ Example failed (likely due to placeholder URL): {e}")
        logger.info("\nTo run examples, replace placeholder PR URLs with actual GitHub PR URLs.")


if __name__ == "__main__":
    main()
