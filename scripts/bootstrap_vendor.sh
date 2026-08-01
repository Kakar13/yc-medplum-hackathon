#!/usr/bin/env bash
# Fetch the Medplum monorepo, pinned to the commit this work was based on.
#
# haarf/ and open-wearables/ are committed to this repo directly (see infra/README.md). Medplum
# is not: it is 302 MB, which would make every clone slow and bury our own history behind
# vendor code we don't maintain. Pinning the SHA here gives an identical tree without that cost.
#
#   ./scripts/bootstrap_vendor.sh          # fetch if missing
#   ./scripts/bootstrap_vendor.sh --force  # re-fetch even if present
#
# You need it so the Medplum doc paths cited in docs/AGENT_GOVERNANCE.md resolve locally. The
# agent and web app run without it.

set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p infra

FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

# name|url|pinned commit. Must be the *full* SHA: `git fetch origin <short-sha>` is rejected by
# the protocol, so an abbreviated pin silently falls back to the default branch.
REPOS=(
  "medplum|https://github.com/medplum/medplum.git|e976c706c79ddc7a750c6c871f43d31f7c799048"
)

for entry in "${REPOS[@]}"; do
  IFS='|' read -r name url sha <<<"$entry"
  dest="infra/$name"

  short="${sha:0:9}"

  if [[ -d "$dest/.git" && $FORCE -eq 0 ]]; then
    have=$(git -C "$dest" rev-parse HEAD 2>/dev/null || echo unknown)
    if [[ "$have" == "$sha" ]]; then
      echo "ok       $name already at $short"
    else
      echo "WARNING  $name is at ${have:0:9}, expected $short (use --force to reset)"
    fi
    continue
  fi

  [[ $FORCE -eq 1 ]] && rm -rf "$dest"
  echo "fetching $name @ $short ..."
  git init --quiet "$dest"
  git -C "$dest" remote add origin "$url" 2>/dev/null || true

  # Fetching the single pinned commit shallowly keeps this to seconds rather than a full history
  # clone. Not every host allows it, so fall back to a shallow default-branch clone.
  if git -C "$dest" fetch --quiet --depth 1 origin "$sha" 2>/dev/null; then
    git -C "$dest" checkout --quiet FETCH_HEAD
    echo "ok       $name at $short (exact pin)"
  else
    echo "         host refused a direct commit fetch, falling back to default branch"
    git -C "$dest" fetch --quiet --depth 50 origin
    default=$(git -C "$dest" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || echo origin/main)
    git -C "$dest" checkout --quiet -B main "$default"
    got=$(git -C "$dest" rev-parse HEAD)
    if [[ "$got" == "$sha" ]]; then
      echo "ok       $name at $short (default branch happens to be the pin)"
    else
      echo "WARNING  $name is at ${got:0:9}, not the pinned $short — upstream has moved"
    fi
  fi
done

echo
echo "Medplum ready under infra/medplum (gitignored by design)."
echo "haarf and open-wearables are already in the repo — see infra/README.md."
