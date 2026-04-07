import sys
import subprocess
import json
from dataclasses import dataclass
from typing import Optional, Dict
from .. import config

PROBES = {
    'bell_transpile': """
import sys, json
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector

try:
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure_all()

    state1 = Statevector(qc)
    tqc = transpile(qc, basis_gates=['cx','u'], optimization_level=2, seed_transpiler=42)
    state2 = Statevector(tqc)

    overlap = abs(state1.inner(state2))
    fidelity = float(overlap**2)

    print(json.dumps({"probe": "bell_transpile", "fidelity": fidelity}))
except Exception as e:
    print(json.dumps({"probe": "bell_transpile", "fidelity": 0.0, "error": str(e)}))
sys.exit(0)
""",

    'controlled_subgate': """
import sys, json
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector

try:
    sub = QuantumCircuit(2, name='sub')
    sub.cx(0, 1)
    controlled_sub = sub.to_gate().control(1)

    qc = QuantumCircuit(3)
    qc.h(0)
    qc.append(controlled_sub, [0, 1, 2])
    qc.measure_all()

    state1 = Statevector(qc)
    tqc = transpile(qc, optimization_level=2, seed_transpiler=42)
    state2 = Statevector(tqc)

    overlap = abs(state1.inner(state2))
    fidelity = float(overlap**2)

    print(json.dumps({"probe": "controlled_subgate", "fidelity": fidelity}))
except Exception as e:
    print(json.dumps({"probe": "controlled_subgate", "fidelity": 0.0, "error": str(e)}))
sys.exit(0)
""",

    'unitary_synthesis': """
import sys, json
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector, Operator
import numpy as np

try:
    mat = np.array([[1,0,1,0],[0,1,0,1],[1,0,-1,0],[0,1,0,-1]], dtype=complex)/np.sqrt(2)
    qc = QuantumCircuit(2)
    from qiskit.circuit.library import UnitaryGate
    qc.append(UnitaryGate(mat), [0,1])
    qc.h(0)
    qc.measure_all()

    state1 = Statevector(qc)
    tqc = transpile(qc, optimization_level=2, seed_transpiler=42)
    state2 = Statevector(tqc)

    overlap = abs(state1.inner(state2))
    fidelity = float(overlap**2)

    op1, op2 = Operator(qc), Operator(tqc)
    equiv = op1.equiv(op2)

    print(json.dumps({"probe": "unitary_synthesis", "fidelity": fidelity, "operator_equiv": equiv}))
except Exception as e:
    print(json.dumps({"probe": "unitary_synthesis", "fidelity": 0.0, "error": str(e)}))
sys.exit(0)
""",

    'gate_control': """
import sys, json
import numpy as np
from qiskit.circuit.library import UnitaryGate

try:
    mat = np.eye(16, dtype=complex)
    gate = UnitaryGate(mat)
    controlled_gate = gate.control(1)
    print(json.dumps({"probe": "gate_control", "fidelity": 1.0, "panic": False}))
except Exception as e:
    print(json.dumps({"probe": "gate_control", "fidelity": 0.0, "panic": True, "error": str(e)}))
sys.exit(0)
""",

    'qft_round_trip': """
import sys, json
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector
from qiskit.circuit.library import QFT

try:
    qc = QFT(4)
    qc = transpile(qc, optimization_level=3, seed_transpiler=42)
    qc2 = transpile(qc, optimization_level=3, seed_transpiler=42)

    state1 = Statevector(qc)
    state2 = Statevector(qc2)

    overlap = abs(state1.inner(state2))
    fidelity = float(overlap**2)

    print(json.dumps({"probe": "qft_round_trip", "fidelity": fidelity}))
except Exception as e:
    print(json.dumps({"probe": "qft_round_trip", "fidelity": 0.0, "error": str(e)}))
sys.exit(0)
"""
}

@dataclass
class ProbeResult:
    probe_name: str
    function_under_test: str
    fidelity: float
    is_regression: bool
    error: Optional[str] = None
    operator_equiv: Optional[bool] = None

def run_probe(name: str, timeout: int = 45) -> ProbeResult:
    """Execute a probe script and return results."""
    if name not in PROBES:
        raise ValueError(f"Unknown probe: {name}")

    script = PROBES[name]

    try:
        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        # Parse JSON from stdout
        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            # Probe didn't output valid JSON - treat as error
            data = {"probe": name, "fidelity": 0.0, "error": "Invalid JSON output"}

        return ProbeResult(
            probe_name=name,
            function_under_test='transpiler',
            fidelity=data.get('fidelity', 0.0),
            is_regression=data.get('fidelity', 0.0) < config.FIDELITY_THRESHOLD,
            error=data.get('error') if data.get('fidelity', 0.0) < config.FIDELITY_THRESHOLD else None,
            operator_equiv=data.get('operator_equiv')
        )

    except subprocess.TimeoutExpired:
        return ProbeResult(
            probe_name=name,
            function_under_test='transpiler',
            fidelity=0.0,
            is_regression=True,
            error=f"Probe timed out after {timeout}s"
        )

def select_probes_for_graph(graph):
    """Select relevant probes based on changed modules."""
    probes = ['bell_transpile']  # Always included

    # Check for transpiler changes
    if graph.has_transpiler_changes:
        probes.extend(['controlled_subgate', 'qft_round_trip'])

    # Check for synthesis changes
    if graph.has_synthesis_changes:
        probes.extend(['unitary_synthesis', 'gate_control'])

    # Check for specific function names
    for fn_qual in graph.changed_functions:
        if 'qs_decomposition' in fn_qual:
            if 'gate_control' not in probes:
                probes.append('gate_control')
            break

    # Remove duplicates
    probes = list(dict.fromkeys(probes))

    return probes
