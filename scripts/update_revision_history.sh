#!/usr/bin/env bash
set -euo pipefail

DOC="docs/SOP_CODEOWNERS_CHANGE_CONTROL.md"

START="<!-- REVISION_HISTORY_START -->"
END="<!-- REVISION_HISTORY_END -->"

if ! grep -q "$START" "$DOC"; then
  echo "Revision history markers not found"
  exit 1
fi

TMP=$(mktemp)

echo "$START" > "$TMP"

git for-each-ref \
  --sort=creatordate \
  --format='| %(refname:short) | %(creatordate:short) | %(refname:short) | Release %(refname:short) | Laboratory Management |' \
  refs/tags \
  | sed 's/^| v/| /' \
  >> "$TMP"

echo "$END" >> "$TMP"

awk -v start="$START" -v end="$END" '
  $0 ~ start {print; system("cat '"$TMP"'"); skip=1; next}
  $0 ~ end {skip=0; next}
  !skip {print}
' "$DOC" > "${DOC}.new"

mv "${DOC}.new" "$DOC"
rm "$TMP"

echo "Revision history updated from Git tags."
