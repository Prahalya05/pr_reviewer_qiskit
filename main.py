#!/usr/bin/env python3
"""
QiskitSage CLI - Run AI-powered code reviews on Qiskit PRs.

Usage:
    python main.py --pr <PR_URL>
    python main.py --help

Examples:
    python main.py --pr "https://github.com/Qiskit/qiskit/pull/12345"
    python main.py --pr "https://github.com/Qiskit/qiskit/pull/67890" --verbose
"""

import argparse
import sys
import time
from typing import List
from qiskitsage.context_builder import ContextBuilder
from qiskitsage.orchestrator import Orchestrator
from qiskitsage.agents.syntax_agent import SyntaxAgent
from qiskitsage.agents.performance_agent import PerformanceAgent
from qiskitsage.agents.semantic_agent import SemanticAgent
from qiskitsage.agents.ffi_agent import FFIAgent
from qiskitsage.models import ReviewResult, Finding
from qiskitsage.renderer import Renderer
from qiskitsage.agents.judge_agent import JudgeAgent


def main():
    parser = argparse.ArgumentParser(
        description="QiskitSage - AI-powered PR review for Qiskit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --pr "https://github.com/Qiskit/qiskit/pull/12345"
  python main.py --pr "https://github.com/Qiskit/qiskit/pull/67890" --verbose
        """
    )
    parser.add_argument(
        "--pr", "-p",
        type=str,
        help="GitHub PR URL to review (e.g., https://github.com/Qiskit/qiskit/pull/12345)"
    )
    parser.add_argument(
        "--issue", "-i",
        type=str,
        help="GitHub Issue URL to analyze and generate code for (e.g., https://github.com/Qiskit/qiskit/issues/15870)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output (show agent progress)"
    )
    parser.add_argument(
        "--agents", "-a",
        type=str,
        nargs="+",
        choices=["syntax", "performance", "semantic", "ffi", "all"],
        default=["all"],
        help="Which agents to run (default: all)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        choices=["console", "markdown"],
        default="console",
        help="Output format (default: console)"
    )

    args = parser.parse_args()

    if not args.pr and not args.issue:
        print("[ERROR] Error: Must provide either --pr or --issue.", file=sys.stderr)
        sys.exit(1)

    if args.issue:
        from qiskitsage.github_client import GitHubClient
        from qiskitsage.agents.issue_agent import IssueAgent

        if not args.issue.startswith("https://github.com/") or "/issues/" not in args.issue:
            print("[ERROR] Error: Invalid Issue URL. Must be a GitHub Issue URL.", file=sys.stderr)
            sys.exit(1)
            
        print(f"[INFO] Analyzing Issue: {args.issue}")
        start_time = time.time()
        
        gh = GitHubClient()
        try:
            issue_data = gh.fetch_issue_data(args.issue)
        except Exception as e:
            print(f"[ERROR] Error fetching issue data: {e}", file=sys.stderr)
            sys.exit(1)
            
        agent = IssueAgent()
        if args.verbose:
            print("   -> Running code generation with Ollama...")
            
        findings = agent.review(issue_data)
        
        print("\n" + "="*80)
        print(f"[SUMMARY] QISKITSAGE ISSUE ANALYSIS (OLLAMA GENERATED)")
        print("="*80)
        print(f"Issue: {args.issue}")
        print(f"Title: {issue_data['issue_title']}")
        print(f"Analysis completed in {time.time() - start_time:.1f}s")
        print(f"Total fixes generated: {len(findings)}")
        print("\n" + "="*80)
        
        for finding in findings:
            print(f"\n💡 {finding.category.value} FIX: {finding.title}")
            print(f"   Target File: {finding.file}")
            print(f"   Reasoning: {finding.description}")
            if finding.suggestion:
                print(f"\n   --- GENERATED CODE FIX ---\n{finding.suggestion}")
                print(f"   --------------------------")
                
        sys.exit(0)

    if not args.pr.startswith("https://github.com/") or "/pull/" not in args.pr:
        print("[ERROR] Error: Invalid PR URL. Must be a GitHub PR URL.", file=sys.stderr)
        sys.exit(1)

    # Build context graph
    print(f"[INFO] Analyzing PR: {args.pr}")
    if args.verbose:
        print("   -> Building context graph (Stage 1: Skeleton)...")

    start_time = time.time()
    builder = ContextBuilder()

    try:
        graph = builder.build(args.pr)
    except Exception as e:
        print(f"[ERROR] Error building context graph: {e}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"   [OK] Context graph built in {graph.build_time_seconds}s")
        print(f"   [OK] {len(graph.changed_files)} changed files")
        print(f"   [OK] {len(graph.functions)} functions analyzed")
        print(f"   [OK] {len(graph.caller_files)} caller files identified")

        if graph.has_rust_changes:
            print("   [INFO]  Detected Rust changes (will run FFI agent)")
        if graph.has_transpiler_changes or graph.has_synthesis_changes:
            print("   [INFO]  Detected critical transpiler/synthesis changes (will run semantic probes)")

    # Initialize agents
    agents_to_run = []
    if "all" in args.agents or "syntax" in args.agents:
        agents_to_run.append(("Syntax", SyntaxAgent()))
    if "all" in args.agents or "performance" in args.agents:
        agents_to_run.append(("Performance", PerformanceAgent()))
    if "all" in args.agents or "semantic" in args.agents:
        agents_to_run.append(("Semantic", SemanticAgent()))
    if "all" in args.agents or "ffi" in args.agents:
        agents_to_run.append(("FFI Safety", FFIAgent()))

    # Run agents
    all_findings: List[Finding] = []
    agent_ids_run = []

    for agent_name, agent in agents_to_run:
        if args.verbose:
            print(f"   -> Running {agent_name} agent...")

        try:
            findings = agent.review(graph)

            if args.verbose:
                critical = sum(1 for f in findings if f.severity.value == "CRITICAL")
                high = sum(1 for f in findings if f.severity.value == "HIGH")
                medium = sum(1 for f in findings if f.severity.value == "MEDIUM")
                low = sum(1 for f in findings if f.severity.value == "LOW")
                print(f"     [OK] Found {len(findings)} findings (C:{critical}, H:{high}, M:{medium}, L:{low})")

            all_findings.extend(findings)
            agent_ids_run.append(agent.agent_id)

        except Exception as e:
            if args.verbose:
                print(f"     [ERROR] Error in {agent_name} agent: {e}")

    # Generate report
    if args.verbose:
        print("   -> Generating final report...")

    # Create result object from findings
    critical_count = sum(1 for f in all_findings if f.severity.value == "CRITICAL")
    high_count = sum(1 for f in all_findings if f.severity.value == "HIGH")
    
    semantic_regression_detected = any(f.agent_id == 'SA-SEM' and f.severity.value == 'CRITICAL' for f in all_findings)
    ffi_risk_detected = any(f.agent_id == 'SA-FFI' and f.severity.value in ('CRITICAL', 'HIGH') for f in all_findings)

    execution_time_seconds = time.time() - start_time

    # Extract PR number from URL
    pr_number = int(args.pr.split('/pull/')[-1])

    # Create temporary result for rendering markdown
    temp_result = ReviewResult(
        pr_url=args.pr,
        pr_number=pr_number,
        findings=all_findings,
        agents_run=agent_ids_run,
        execution_time_seconds=execution_time_seconds,
        total_findings=len(all_findings),
        critical_count=critical_count,
        high_count=high_count,
        semantic_regression_detected=semantic_regression_detected,
        ffi_risk_detected=ffi_risk_detected,
        comment_markdown=""
    )

    # Render markdown and create final result
    result = ReviewResult(
        pr_url=args.pr,
        pr_number=pr_number,
        findings=all_findings,
        agents_run=agent_ids_run,
        execution_time_seconds=execution_time_seconds,
        total_findings=len(all_findings),
        critical_count=critical_count,
        high_count=high_count,
        semantic_regression_detected=semantic_regression_detected,
        ffi_risk_detected=ffi_risk_detected,
        comment_markdown=Renderer().render(temp_result)
    )

    # Output results
    total_time = time.time() - start_time

    print("\n" + "="*80)
    print("[SUMMARY] QISKITSAGE REVIEW SUMMARY")
    print("="*80)
    print(f"PR: {result.pr_url}")
    print(f"Review completed in {result.execution_time_seconds:.1f}s (total: {total_time:.1f}s)")
    print(f"Agents run: {', '.join(result.agents_run)}")
    print(f"Total findings: {result.total_findings}")

    if result.critical_count > 0:
        print(f"🚨 Critical: {result.critical_count}")
    if result.high_count > 0:
        print(f"⚠️  High: {result.high_count}")

    if result.semantic_regression_detected:
        print("🐛 REGRESSION DETECTED: Semantic probe failed!")
    if result.ffi_risk_detected:
        print("⚠️  FFI RISK: Rust unsafe patterns detected!")

    print("\n" + "="*80)

    if args.output == "console":
        # Console-friendly output
        for finding in result.findings:
            severity_marker = {
                "CRITICAL": "🚨",
                "HIGH": "⚠️ ",
                "MEDIUM": "[INFO]",
                "LOW": "💡"
            }.get(finding.severity.value, "•")

            print(f"\n{severity_marker} {finding.severity.value}: {finding.title}")
            if finding.line:
                print(f"   File: {finding.file}:{finding.line}")
            else:
                print(f"   File: {finding.file}")
            print(f"   Category: {finding.category.value}")
            print(f"   Confidence: {finding.confidence:.1%}")
            if finding.description:
                print(f"   Description: {finding.description}")
            if finding.suggestion:
                print(f"   Suggestion: {finding.suggestion}")
            if finding.evidence:
                print(f"   Evidence: {finding.evidence[:100]}{'...' if len(finding.evidence) > 100 else ''}")
    else:
        # Markdown format
        print(result.comment_markdown)

    # Exit code based on findings
    if result.critical_count > 0:
        sys.exit(2)  # Critical issues found
    elif result.high_count > 0:
        sys.exit(1)  # High issues found
    else:
        sys.exit(0)  # Success


if __name__ == "__main__":
    main()
