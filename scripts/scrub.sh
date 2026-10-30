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
SECRETS='sk-ant-[a-z0-9]|ANTHROPIC_API_KEY=[^[:space:]]+|BEGIN (RSA|OPENSSH|EC|DSA|PGP) PRIVATE KEY|aws_secret|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|xox[abpr]-[A-Za-z0-9-]{10,}|(api[_-]?key|secret|token|password)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][A-Za-z0-9_/+=-]{16,}'
check "secrets" "$SECRETS"
# Secrets anywhere in history, not just the working tree.
hist=$(git log -p --all 2>/dev/null | grep -n -I -i -E "^\+.*($SECRETS)" | grep -v -E 'check "secrets"|SECRETS=' | head -5)
if [ -n "$hist" ]; then echo "SCRUB [secrets in history]:"; echo "$hist"; fail=1; fi
[ -f .env ] && ! git check-ignore -q .env && { echo "SCRUB [.env is not gitignored]"; fail=1; }
log=$(git log --format=%B 2>/dev/null | grep -i -E 'CLSC(PM|EA)|agent-mail|\bbeads?\b|interview|claude code')
if [ -n "$log" ]; then echo "SCRUB [commit messages]:"; echo "$log"; fail=1; fi
[ $fail -eq 0 ] && echo "scrub: clean"
exit $fail
