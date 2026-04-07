#!/bin/bash
# QiskitSage Fix Script - Priority 1 & 2
# Run this script to apply all documented fixes

echo "Applying Priority 1 fixes: Agent API response handling..."

# Priority 1: Fix syntax_agent.py
python3 <<'PYEOF'
import re

content = open('qiskitsage/agents/syntax_agent.py', 'r').read()

# Fix the API response handling pattern
def fix_agent_content(text):
    # Find and replace the problematic section
    old = r'(\s+resp = self\.client\.messages\.create[^}]+}\s+\]\s+\]\s+)(\s+content = resp\.content\[0\]\.text)'
    new = r'''\1
        # Parse JSON response - handle both string and object responses
        if isinstance(resp, str):
            content = resp
        elif hasattr(resp, 'content') and isinstance(resp.content, list):
            if hasattr(resp.content[0], 'text'):
                content = resp.content[0].text
            else:
                content = str(resp.content[0])
        else:
            content = str(resp)'''
    
    return re.sub(old, new, text, flags=re.MULTILINE | re.DOTALL)

try:
    fixed = fix_agent_content(content)
    with open('qiskitsage/agents/syntax_agent.py', 'w') as f:
        f.write(fixed)
    print("✓ Fixed: syntax_agent.py")
except Exception as e:
    print(f"✗ Failed: syntax_agent.py - {e}")
PYEOF

# Priority 2: Create patch file for edits
cat > main.py.patch <<'PATCH_EOF'
--- main.py.orig
+++ main.py.fixed
@@ -18,6 +18,8 @@
 from qiskitsage.agents.semantic_agent import SemanticAgent
 from qiskitsage.agents.ffi_agent import FFIAgent
 from qiskitsage.models import ReviewResult, Finding
+from qiskitsage.orchestrator import Orchestrator
+from qiskitsage.renderer import Renderer
 
 
 def main():
@@ -95,47 +97,32 @@
         agents_to_run.append(("FFI Safety", FFIAgent()))
 
     # Run agents
-    all_findings: List[Finding] = []
-    agent_ids_run = []
-
-    for agent_name, agent in agents_to_run:
-        if args.verbose:
-            print(f" -> Running {agent_name} agent...")
-
-        try:
-            findings = agent.review(graph)
-
-            if args.verbose:
-                critical = sum(1 for f in findings if f.severity.value == "CRITICAL")
-                high = sum(1 for f in findings if f.severity.value == "HIGH")
-                medium = sum(1 for f in findings if f.severity.value == "MEDIUM")
-                low = sum(1 for f in findings if f.severity.value == "LOW")
-                print(f" [OK] Found {len(findings)} findings (C:{critical}, H:{high}, M:{medium}, L:{low})")
-
-            all_findings.extend(findings)
-            agent_ids_run.append(agent.agent_id)
-
-        except Exception as e:
-            if args.verbose:
-                print(f" [ERROR] Error in {agent_name} agent: {e}")
+    try:
+        # Build list of agent instances
+        agent_instances = [agent for _, agent in agents_to_run]
+        
+        if args.verbose:
+            print(f" -> Running {len(agent_instances)} agents via orchestrator...")
+
+        orchestrator = Orchestrator(agent_instances)
+        result = orchestrator.analyze_pr(graph)
+
+        if args.verbose:
+            print(f"[OK] Orchestrator completed: {result.total_findings} findings")
+            print(f"     Agents: {', '.join(result.agents_run)}")
+    except Exception as e:
+        print(f"[ERROR] Orchestrator failed: {e}", file=sys.stderr)
+        import traceback
+        traceback.print_exc()
+        sys.exit(1)
 
     # Generate report
     if args.verbose:
-        print(" -> Generating final report...")
-
-    judge = JudgeAgent()
-    try:
-        result = judge.generate_report(graph, all_findings)
-    except Exception as e:
-        print(f"[ERROR] Error generating report: {e}", file=sys.stderr)
-        sys.exit(1)
+        print(" -> Rendering final report...")
+
+    renderer = Renderer()
+    result.comment_markdown = renderer.render(result)
 
     # Output results
     total_time = time.time() - start_time
PATCH_EOF

echo ""
echo "Patch file created: main.py.patch"
echo "To apply: patch -p1 < main.py.patch"
echo ""
echo "Priority 2 patch ready per docs/INTEGRATE_ORCHESTRATOR.md"

echo ""
echo "To test after applying fixes:"
echo "python main.py --pr \"https://github.com/Qiskit/qiskit/pull/15847\" --verbose > final_test.log 2>&1"
echo ""
