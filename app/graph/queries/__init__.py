"""Python implementations of the GQ-### catalog queries for MockGraphClient.

Importing this package registers every implementation in MOCK_QUERY_IMPLS
(app/graph/client.py) via the @mock_query decorator. Each function mirrors the
traversal semantics and output keys of its GSQL counterpart in
docs/tigergraph_foundation/tigergraph/queries/.
"""
from app.graph.queries import (  # noqa: F401
    advisor,
    agp,
    ai_artifacts,
    context_memory,
    crm,
    graph_ops,
    hierarchy,
    reasoning,
    revenue,
    state,
)
