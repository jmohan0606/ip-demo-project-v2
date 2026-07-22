"""Dataset building (FIX_SPEC_R4 work-stream B).

Shared downstream pipeline used by BOTH data-set builders:
  scripts/generate_sample_data.py  (fabricated transactions — demo set)
  scripts/build_real_data.py       (transactions parsed from real extracts)

The ONLY difference between sample and real is where the transactions and
dimensions come from; eligibility, aggregation, attribution, reconciliation,
CSV writing and the manifest are identical and live here — shared, not copied.
"""
