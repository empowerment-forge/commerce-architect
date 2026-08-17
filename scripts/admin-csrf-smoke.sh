#!/usr/bin/env bash
set -euo pipefail

base_url="${1:-http://127.0.0.1:8080}"
public_host="${PUBLIC_HOST:-commerce.example}"
public_origin="https://${public_host}"
login_path="/admin/login/?next=/admin/"
work_dir=$(mktemp -d)
trap 'rm -rf "${work_dir}"' EXIT

request_headers=(
  --header "Host: ${public_host}"
  --header "X-Forwarded-Host: ${public_host}"
  --header "X-Forwarded-Proto: https"
  --header "X-Forwarded-Port: 443"
)

status=$(curl --silent --show-error --output /dev/null \
  --dump-header "${work_dir}/admin-headers" --write-out '%{http_code}' \
  "${request_headers[@]}" "${base_url}/admin/")
test "${status}" = "302"
admin_location=$(awk 'tolower($1) == "location:" {
  sub(/\r$/, "", $2); print $2
}' "${work_dir}/admin-headers")
test "${admin_location}" = "${login_path}"
if grep --quiet --ignore-case --regexp='^location:.*\(:8080\|backend\)' \
  "${work_dir}/admin-headers"; then
  echo "Admin redirect leaked an internal address." >&2
  exit 1
fi

status=$(curl --silent --show-error --output "${work_dir}/login.html" \
  --dump-header "${work_dir}/login-headers" --write-out '%{http_code}' \
  "${request_headers[@]}" "${base_url}${login_path}")
test "${status}" = "200"
cookie=$(sed -n 's/^set-cookie: csrftoken=\([^;]*\).*/\1/ip' \
  "${work_dir}/login-headers" | head -n 1)
token=$(sed -n 's/.*name="csrfmiddlewaretoken" value="\([^"]*\)".*/\1/p' \
  "${work_dir}/login.html")
test -n "${cookie}"
test -n "${token}"
grep --quiet --ignore-case \
  '^set-cookie: csrftoken=.*; Path=/; SameSite=Lax; Secure' \
  "${work_dir}/login-headers"

post_login() {
  local output=$1
  shift
  curl --silent --show-error --output "${work_dir}/${output}.html" \
    --dump-header "${work_dir}/${output}-headers" --write-out '%{http_code}' \
    --request POST "${request_headers[@]}" "$@" \
    "${base_url}${login_path}"
}

status=$(post_login valid \
  --header "Cookie: csrftoken=${cookie}" \
  --header "Origin: ${public_origin}" \
  --header "Referer: ${public_origin}${login_path}" \
  --data-urlencode "username=${ADMIN_SMOKE_USERNAME}" \
  --data-urlencode "password=${ADMIN_SMOKE_PASSWORD}" \
  --data-urlencode "csrfmiddlewaretoken=${token}" \
  --data-urlencode 'next=/admin/')
test "${status}" = "302"
valid_location=$(awk 'tolower($1) == "location:" {
  sub(/\r$/, "", $2); print $2
}' "${work_dir}/valid-headers")
test "${valid_location}" = "/admin/"

status=$(post_login missing-cookie \
  --header "Origin: ${public_origin}" \
  --header "Referer: ${public_origin}${login_path}" \
  --data-urlencode "username=${ADMIN_SMOKE_USERNAME}" \
  --data-urlencode "password=${ADMIN_SMOKE_PASSWORD}" \
  --data-urlencode "csrfmiddlewaretoken=${token}")
test "${status}" = "403"

status=$(post_login missing-token \
  --header "Cookie: csrftoken=${cookie}" \
  --header "Origin: ${public_origin}" \
  --header "Referer: ${public_origin}${login_path}" \
  --data-urlencode "username=${ADMIN_SMOKE_USERNAME}" \
  --data-urlencode "password=${ADMIN_SMOKE_PASSWORD}")
test "${status}" = "403"

status=$(post_login invalid-token \
  --header "Cookie: csrftoken=${cookie}" \
  --header "Origin: ${public_origin}" \
  --header "Referer: ${public_origin}${login_path}" \
  --data-urlencode "username=${ADMIN_SMOKE_USERNAME}" \
  --data-urlencode "password=${ADMIN_SMOKE_PASSWORD}" \
  --data-urlencode 'csrfmiddlewaretoken=invalid')
test "${status}" = "403"

status=$(post_login untrusted-origin \
  --header "Cookie: csrftoken=${cookie}" \
  --header 'Origin: https://attacker.example' \
  --header 'Referer: https://attacker.example/admin/login/' \
  --data-urlencode "username=${ADMIN_SMOKE_USERNAME}" \
  --data-urlencode "password=${ADMIN_SMOKE_PASSWORD}" \
  --data-urlencode "csrfmiddlewaretoken=${token}")
test "${status}" = "403"

echo "Admin CSRF proxy smoke passed."
