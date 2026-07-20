"""Python implementations of the GQ-### catalog queries for the local tier.

Importing this package registers every implementation in MOCK_QUERY_IMPLS
(app/graph/client.py) via the @mock_query decorator. Each function mirrors the
traversal semantics and output keys of its GSQL counterpart in
docs/tigergraph_foundation/tigergraph/queries/, returning the identical
RESTPP result shape, so verifying against the local tier genuinely proves
tier-1 behaviour.
"""
from app.graph.queries import v2 as _v2  # noqa: F401 — registers GQ-001..015
