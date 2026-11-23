"""Temporary benchmark-only startup configuration, removed on container recreation."""
import os
import sys

import torch._dynamo.config as dynamo_config

dynamo_config.recompile_limit = 64
print(
    f"[contractlens-dynamo] pid={os.getpid()} recompile_limit={dynamo_config.recompile_limit} "
    f"accumulated_recompile_limit={dynamo_config.accumulated_recompile_limit}",
    file=sys.stderr,
    flush=True,
)
