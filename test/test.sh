#!/bin/bash
trap 'rm -f $tmp' EXIT
tmp=$(mktemp)

echo
echo "Running tests .."
md-link-checker -v test.md &> $tmp
if diff $tmp test.out; then
    echo ".. test passed"
else
    echo ".. test FAILED" >&2
fi
