#!/usr/bin/env bash
# Public-tier check: no private references, no secrets. Exits non-zero on a hit.
set -u
cd "$(dirname "$0")/.."
files=$(git ls-files --cached --others --exclude-standard | grep -v '^scripts/scrub.sh$')
fail=0
check() {
  local label=$1 pattern=$2
  hits=$(echo "$files" | xargs grep -n -I -i -E "$pattern" 2>/dev/null)
  if [ -n "$hits" ]; then echo "SCRUB [$label]:"; echo "$hits"; fail=1; fi
}
check "private refs" 'CLSC(PM|EA)|agent-mail|\bbeads?\b|\battest\b|humana|interview|cowork|claude code session|/Users/'
check "secrets" 'sk-ant-[a-z0-9]|ANTHROPIC_API_KEY=[^[:space:]]+|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|aws_secret'
log=$(git log --format=%B 2>/dev/null | grep -i -E 'CLSC(PM|EA)|agent-mail|\bbeads?\b|interview|claude code')
if [ -n "$log" ]; then echo "SCRUB [commit messages]:"; echo "$log"; fail=1; fi
[ $fail -eq 0 ] && echo "scrub: clean"
exit $fail
