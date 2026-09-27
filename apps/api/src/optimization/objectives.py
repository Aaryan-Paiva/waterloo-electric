"""Objective weights (CLAUDE.md §19.1). Lexicographic in spirit: residual capacity violation dominates everything.
Units: per MWh. EPS_AGENT breaks ties between equivalent agents deterministically (earlier id preferred)."""
W_SEVERITY = 0.05     # extra weight per MW of pre-dispatch deficit: worst hours are reduced first
W_SLACK = 1000.0      # energy above capacity that remains after dispatch (the thing we minimize)
W_BATTERY = 1.0       # battery throughput (degradation proxy)
W_EV = 0.5            # EV energy shifted in time
W_BUILDING = 2.0      # building HVAC shed (comfort penalty)
EPS_AGENT = 1e-4
TOL = 1e-6            # numerical tolerance for "above capacity" and constraint checks
W_PRICE = 0.01        # agentic clearing: $/MWh offer price -> objective units (max ~$300 => 3 << W_SLACK, so cost is only a tie-breaker)
