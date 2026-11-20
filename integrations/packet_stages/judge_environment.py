"""Return a child-only environment compatible with httpx proxy exclusion parsing."""
import os

def judge_environment(base=None):
    env=dict(os.environ if base is None else base)
    # httpx 0.28 turns unbracketed IPv6 NO_PROXY entries (including CIDRs)
    # into invalid URLPattern ports. Preserve every IPv4/DNS exclusion and
    # preserve HTTP(S)_PROXY; the judge API uses a DNS hostname, not IPv6.
    for key in ['no_proxy','NO_PROXY']:
        if key in env:
            env[key]=','.join(value for value in env[key].split(',') if ':' not in value)
    return env
