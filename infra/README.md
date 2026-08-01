# Vendored third-party sources

Reference material we read while building Preflight. **None of this is our code.** Each
directory is an unmodified copy of a public upstream repository, kept at a pinned commit so the
file paths cited in our docs resolve locally.

| Directory | Upstream | Pinned commit | License | In this repo? |
|---|---|---|---|---|
| `haarf/` | [Task-force-for-AI-agents-in-Healthcare/haarf](https://github.com/Task-force-for-AI-agents-in-Healthcare/haarf) | `d2682c6245ae751b435046e219a65fd35d1d9cc8` | CC BY-SA 4.0 | committed |
| `open-wearables/` | [the-momentum/open-wearables](https://github.com/the-momentum/open-wearables) | `87f589316f269662450d1d83f5b5c640fc1531e6` | MIT | committed |
| `medplum/` | [medplum/medplum](https://github.com/medplum/medplum) | `e976c70` | Apache-2.0 | **not committed** — 302 MB |

Original `LICENSE` files are preserved in place. HAARF is CC BY-SA 4.0, which requires
attribution and share-alike on derivatives; we include it verbatim and have not modified it. Our
own scorecard that replays HAARF's scenarios lives in `agent/scripts/haarf_scorecard.py`, not
here.

## Getting Medplum

The Medplum monorepo is 302 MB — 218 MB of source across 5,193 files, plus 83 MB of history —
so committing it would swamp this repo. Fetch it with:

```bash
./scripts/bootstrap_vendor.sh
```

You only need it if you want the Medplum doc paths cited in
[`docs/AGENT_GOVERNANCE.md`](../docs/AGENT_GOVERNANCE.md) to resolve locally — specifically
`packages/docs/docs/ai/index.md`, `ai/mcp.md`, and `access/smart-scopes.md`, which are the
sources for the "can suggest, but not act" pattern and the SMART `patient=<id>` compartment
argument. The agent and web app run fine without it.

## Why the clone metadata is gone

`haarf/` and `open-wearables/` were originally git clones. A nested `.git` directory makes Git
record a *gitlink* rather than the files, so anyone cloning this repo would have received empty
directories. The `.git` folders were removed so the contents commit as ordinary files. To work
against upstream history instead, re-clone from the URLs above at the pinned commits.
