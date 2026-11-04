"""
qiskit_intro.py — Quantum computing basics + LLM-assisted circuit explanation
pip install qiskit qiskit-aer anthropic

รัน: python qiskit_intro.py
"""
from __future__ import annotations
import os


# ── Quantum circuits ──────────────────────────────────────────

def bell_state_circuit():
    """สร้าง Bell State — quantum entanglement พื้นฐาน"""
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator

    qc = QuantumCircuit(2, 2)
    qc.h(0)       # Hadamard gate → superposition
    qc.cx(0, 1)   # CNOT gate → entanglement
    qc.measure([0, 1], [0, 1])

    sim = AerSimulator()
    job = sim.run(qc, shots=1024)
    counts = job.result().get_counts()
    return qc, counts


def grover_search(target: int, n_qubits: int = 3):
    """
    Grover's algorithm — ค้นหา target ใน unsorted list
    Quantum speedup: O(√N) vs classical O(N)
    """
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import GroverOperator
    from qiskit_aer import AerSimulator
    import numpy as np

    oracle = QuantumCircuit(n_qubits)
    # flip phase ของ target state
    target_bin = format(target, f'0{n_qubits}b')
    for i, bit in enumerate(reversed(target_bin)):
        if bit == '0':
            oracle.x(i)
    oracle.h(n_qubits - 1)
    oracle.mcx(list(range(n_qubits - 1)), n_qubits - 1)
    oracle.h(n_qubits - 1)
    for i, bit in enumerate(reversed(target_bin)):
        if bit == '0':
            oracle.x(i)

    grover_op = GroverOperator(oracle)
    n_iterations = int(np.pi / 4 * np.sqrt(2 ** n_qubits))

    qc = QuantumCircuit(n_qubits, n_qubits)
    qc.h(range(n_qubits))
    for _ in range(n_iterations):
        qc.compose(grover_op, inplace=True)
    qc.measure(range(n_qubits), range(n_qubits))

    sim = AerSimulator()
    counts = sim.run(qc, shots=2048).result().get_counts()
    return qc, counts


def vqe_cost_function(params):
    """
    VQE (Variational Quantum Eigensolver) — Quantum ML
    ใช้หา ground state energy ของ molecule → drug discovery, materials
    """
    from qiskit.circuit.library import RealAmplitudes
    from qiskit.quantum_info import SparsePauliOp
    from qiskit_aer.primitives import Estimator

    ansatz = RealAmplitudes(2, reps=1)
    hamiltonian = SparsePauliOp.from_list([("ZZ", -1), ("ZI", 0.5), ("IZ", 0.5)])

    estimator = Estimator()
    job = estimator.run([(ansatz, hamiltonian, params)])
    return job.result()[0].data.evs


# ── LLM explains quantum results ─────────────────────────────

def explain_with_llm(circuit_name: str, counts: dict) -> str:
    """ให้ Claude อธิบายผลการทดลอง quantum"""
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"""
Quantum circuit: {circuit_name}
Measurement results (counts from 1024 shots): {counts}

Explain this result in 3 sentences:
1. What the counts tell us about the quantum state
2. Why this demonstrates a quantum advantage or property
3. A real-world application of this phenomenon
"""
    resp = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-haiku-5-5"),
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


# ── Demo ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Quantum + LLM Demo ===\n")

    try:
        # Bell State
        qc, counts = bell_state_circuit()
        print(f"Bell State circuit:\n{qc}\n")
        print(f"Measurement counts: {counts}")

        # LLM explanation
        if os.getenv("ANTHROPIC_API_KEY"):
            print("\nLLM explanation:")
            print(explain_with_llm("Bell State (2-qubit entanglement)", counts))
        else:
            print("\n(set ANTHROPIC_API_KEY to get LLM explanation)")

    except ImportError:
        print("Qiskit not installed. Run: pip install qiskit qiskit-aer")
        print("\nKey concepts demonstrated in this file:")
        print("  - Bell State: quantum entanglement (|00⟩ + |11⟩)/√2")
        print("  - Grover Search: O(√N) quantum speedup over O(N) classical")
        print("  - VQE: variational quantum eigensolver for quantum chemistry")
        print("  - LLM-assisted explanation of quantum measurement results")
