#!/usr/bin/env bash
# Validate the corrected jq consecutive-failure logic against synthetic cases.
set -euo pipefail

JQ_FILTER='
def is_fail: (.status == "completed") and (.conclusion != "success");
if (.[0].status != "completed") then 0
else
  ([ .[] | is_fail ] as $bools
   | ($bools | to_entries | map(select((.value|not)))[0].key) // ($bools | length))
end
'

declare -a CASES=(
  '[{"status":"completed","conclusion":"failure"},{"status":"completed","conclusion":"failure"},{"status":"completed","conclusion":"success"}]|EXPECT2'
  '[{"status":"completed","conclusion":"failure"},{"status":"completed","conclusion":"success"},{"status":"completed","conclusion":"failure"}]|EXPECT1'
  '[{"status":"completed","conclusion":"success"},{"status":"completed","conclusion":"failure"},{"status":"completed","conclusion":"failure"}]|EXPECT0'
  '[{"status":"in_progress","conclusion":null},{"status":"completed","conclusion":"failure"},{"status":"completed","conclusion":"failure"}]|EXPECT0'
  '[{"status":"completed","conclusion":"failure"},{"status":"completed","conclusion":"failure"},{"status":"completed","conclusion":"failure"}]|EXPECT3'
  '[]|EXPECT0'
)

for c in "${CASES[@]}"; do
  json="${c%%|EXPECT*}"
  expect="${c##*EXPECT}"
  got=$(echo "$json" | jq "$JQ_FILTER")
  status="OK"
  [ "$got" = "$expect" ] || status="FAIL"
  printf '%-90s expect=%-2s got=%-2s %s\n' "$json" "$expect" "$got" "$status"
done
