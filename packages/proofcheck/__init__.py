"""Independent checker for resolution-v1 certificates.

The checker accepts JSON-compatible objects. It does not import Z3, a
certificate generator, or a CNF compiler from the memory service.
"""

from proofcheck.check import CheckError, CheckReport, check_certificate, check_witness_pair
from proofcheck.formula import evaluate_formula, formula_hash, knowledge_hash

__all__ = [
    "CheckError",
    "CheckReport",
    "check_certificate",
    "check_witness_pair",
    "evaluate_formula",
    "formula_hash",
    "knowledge_hash",
]
