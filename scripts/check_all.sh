#!/usr/bin/env bash
# Every check the CI runs, in one command (4.3.6).
#
#   bash scripts/check_all.sh            all checks, then the full test suite
#   bash scripts/check_all.sh --quick    all checks, the tests without coverage
#
# Run it with the Python that has Home Assistant and the test tooling
# installed (see .github/workflows/validate.yml for the versions CI
# uses). The CI tests two Home Assistant versions, the supported minimum
# and a current one; this runs whichever one your environment has.
#
# It stops at the first failing step and says which.

set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
quick=0
[ "${1:-}" = "--quick" ] && quick=1

step() { printf '\n== %s\n' "$*"; }

step "Repository checks (scripts/check_*.py)"
for script in scripts/check_*.py; do
  case "$script" in
    # Needs the coverage report from the test run below.
    scripts/check_coverage_per_module.py) continue ;;
    # Strict typing is its own step.
    scripts/check_typing_baseline.py) continue ;;
  esac
  echo "-- $script"
  "$PY" "$script" > /tmp/roomba_plus_check.out 2>&1 || {
    cat /tmp/roomba_plus_check.out
    echo "FAILED: $script"
    exit 1
  }
done

step "Blueprints"
"$PY" scripts/validate_blueprints.py

step "ruff"
"$PY" -m ruff check .

step "mypy (strict, against the baseline)"
"$PY" scripts/check_typing_baseline.py

if [ "$quick" = 1 ]; then
  step "Tests"
  "$PY" -m pytest tests/ -q -p no:randomly -n auto
else
  step "Tests with coverage"
  COVERAGE_CORE=sysmon "$PY" -m pytest tests/ -q -p no:randomly -n auto \
    --cov=custom_components/roomba_plus --cov-branch --cov-report=xml
  step "95 % line coverage in every module"
  "$PY" scripts/check_coverage_per_module.py coverage.xml
fi

printf '\nAll checks passed.\n'
