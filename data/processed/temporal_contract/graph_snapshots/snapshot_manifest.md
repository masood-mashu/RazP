# Causal temporal graph snapshots

A cutoff snapshot at timestep `t` is formed by filtering each partitioned file to `time_step <= t`. Only timestamped address-transaction edges are included.

The actor-level future-window target remains the primary early-warning benchmark. Transaction-level classification is secondary diagnostic work and is not called early warning.
