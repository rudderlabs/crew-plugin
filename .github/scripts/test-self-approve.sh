#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

test_dir=$(mktemp -d)
trap 'rm -rf "$test_dir"' EXIT
# Exercise the actual privileged script without credentials or GitHub writes.
sed '1,/^        run: |$/d; s/^          //' .github/workflows/self-approve.yml > "$test_dir/approve.sh"
test -s "$test_dir/approve.sh"

export REPO=test/repo PR=1 SENDER=trusted
export MOCK_PROTECTED=true MOCK_CHANGED=1 MOCK_FILES=README.md MOCK_FAILURE=
export MOCK_CALLS="$test_dir/calls"
gh() {
  case "$1 $2" in
    'api repos/test/repo/rules/branches/main')
      [ "$MOCK_FAILURE" != rules ] || return 1
      printf '%s\n' "$MOCK_PROTECTED" ;;
    'api repos/test/repo/pulls/1')
      [ "$MOCK_FAILURE" != pull ] || return 1
      printf '%s\n' "$MOCK_CHANGED" ;;
    'api repos/test/repo/pulls/1/files')
      [ "$MOCK_FAILURE" != files ] || return 1
      printf '%s\n' "$MOCK_FILES" ;;
    'pr review')
      printf '%s\n' "$*" >> "$MOCK_CALLS" ;;
    *) printf 'Unexpected gh call: %s\n' "$*" >&2; return 99 ;;
  esac
}
export -f gh

check() {
  local name=$1 expected=$2 actual
  : > "$MOCK_CALLS"
  if bash "$test_dir/approve.sh" > "$test_dir/output" 2>&1; then actual=0; else actual=$?; fi
  if [ "$actual" != "$expected" ]; then
    printf 'FAIL %s: expected exit %s, got %s\n' "$name" "$expected" "$actual" >&2
    cat "$test_dir/output" >&2
    exit 1
  fi
  if [ "$expected" = 0 ]; then
    grep -q '^pr review 1 -R test/repo --approve --body Self-approved by @trusted' "$MOCK_CALLS"
  else
    test ! -s "$MOCK_CALLS"
  fi
  printf 'PASS %s\n' "$name"
}

check 'ordinary PR' 0
MOCK_PROTECTED=false check 'missing native merge protection' 1
MOCK_FAILURE=rules check 'rules API failure' 1
MOCK_FAILURE=pull check 'PR API failure' 1
MOCK_FAILURE=files check 'files API failure' 1
MOCK_FILES=.github/workflows/ci.yml check 'workflow change' 1
MOCK_FILES=$'moved.yml\n.github/workflows/ci.yml' check 'rename out of .github' 1
MOCK_CHANGED=3000 check 'files API limit' 1
MOCK_CHANGED=3001 check 'over files API limit' 1
