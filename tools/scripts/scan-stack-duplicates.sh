#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="1.0.0"
SCAN_ROOTS=("/home" "/opt" "/srv")
OUT=""
JSON=0

usage() {
  cat <<EOF
scan-stack-duplicates $VERSION

Scan for duplicated Docker/Compose stacks without deleting anything.

Usage:
  sudo bash scan-stack-duplicates.sh [options]

Options:
  --root PATH      Add/replace scan root (repeatable)
  --output FILE    Save report to FILE
  --json           Also write a simple JSON summary beside the report
  -h, --help       Show help

Checks:
  - Duplicate Compose project names
  - Duplicate service names across Compose files
  - Duplicate container names / similar prefixes
  - Port collisions
  - Duplicate images/tags
  - Duplicate volumes/networks by project prefix
  - Multiple compose files in the same project tree
  - Running containers belonging to overlapping stacks

This script is read-only.
EOF
}

CUSTOM_ROOTS=()
while (($#)); do
  case "$1" in
    --root)
      shift
      [[ -n "${1:-}" ]] || { echo "--root requires PATH" >&2; exit 2; }
      CUSTOM_ROOTS+=("$1")
      ;;
    --output)
      shift
      OUT="${1:-}"
      [[ -n "$OUT" ]] || { echo "--output requires FILE" >&2; exit 2; }
      ;;
    --json) JSON=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

if ((${#CUSTOM_ROOTS[@]})); then
  SCAN_ROOTS=("${CUSTOM_ROOTS[@]}")
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${OUT:-./stack-duplicate-report-$STAMP.txt}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

exec > >(tee "$OUT") 2>&1

section() { printf '\n============================================================\n%s\n============================================================\n' "$*"; }
sub() { printf '\n--- %s ---\n' "$*"; }

section "Duplicate Stack Scanner v$VERSION"
echo "Host: $(hostname)"
echo "Date: $(date -Is)"
echo "Roots: ${SCAN_ROOTS[*]}"
echo "Report: $OUT"

section "Docker overview"
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker CLI not found."
  exit 0
fi

docker version --format 'Client={{.Client.Version}} Server={{.Server.Version}}' 2>/dev/null || true
docker info --format 'Containers={{.Containers}} Images={{.Images}} Driver={{.Driver}} DockerRootDir={{.DockerRootDir}}' 2>/dev/null || true

section "Containers"
docker ps -a --format '{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' | tee "$TMP/containers.tsv"

sub "Container name prefixes"
awk -F'\t' '
{
  n=$2
  split(n,a,"-")
  if (length(a)>=2) print a[1]"-"a[2]
  else print a[1]
}' "$TMP/containers.tsv" | sort | uniq -c | sort -nr | head -50

sub "Exact duplicate container names"
cut -f2 "$TMP/containers.tsv" | sort | uniq -d || true

section "Port collisions"
docker ps --format '{{.Names}}\t{{.Ports}}' > "$TMP/ports.raw"

python3 - "$TMP/ports.raw" <<'PY'
import re, sys
from collections import defaultdict

ports = defaultdict(list)
for line in open(sys.argv[1], encoding="utf-8", errors="ignore"):
    name, _, rest = line.rstrip("\n").partition("\t")
    for host, port in re.findall(r'(?:(?:0\.0\.0\.0|\[::\]|127\.0\.0\.1):)?(\d+)->(\d+)/(tcp|udp)', rest):
        pass
    for m in re.finditer(r'(?:(?:0\.0\.0\.0|\[::\]|127\.0\.0\.1):)?(\d+)->(\d+)/(tcp|udp)', rest):
        hp, cp, proto = m.groups()
        ports[(hp, proto)].append((name, cp))

found = False
for key, vals in sorted(ports.items(), key=lambda x: int(x[0][0])):
    if len(vals) > 1:
        found = True
        print(f"HOST {key[0]}/{key[1]}:")
        for n, cp in vals:
            print(f"  {n} -> container:{cp}")
if not found:
    print("No duplicate published host ports detected.")
PY

section "Images"
docker image ls --digests --format '{{.Repository}}\t{{.Tag}}\t{{.Digest}}\t{{.ID}}\t{{.Size}}' | tee "$TMP/images.tsv"

sub "Repositories with multiple tags/images"
awk -F'\t' '$1!="<none>"{print $1}' "$TMP/images.tsv" | sort | uniq -c | sort -nr | awk '$1>1'

sub "Duplicate image IDs referenced by multiple tags"
awk -F'\t' '{print $4"\t"$1":"$2}' "$TMP/images.tsv" |
  sort -k1,1 |
  awk -F'\t' '
    { count[$1]++; tags[$1]=tags[$1]" "$2 }
    END { for (id in count) if (count[id]>1) print count[id], id, tags[id] }
  ' | sort -nr

section "Volumes"
docker volume ls --format '{{.Name}}\t{{.Driver}}' | tee "$TMP/volumes.tsv"

sub "Likely duplicate project volume prefixes"
cut -f1 "$TMP/volumes.tsv" |
awk '
{
  n=$0
  sub(/_[^_]+$/, "", n)
  print n
}' | sort | uniq -c | sort -nr | awk '$1>1' | head -50

section "Networks"
docker network ls --format '{{.Name}}\t{{.Driver}}\t{{.ID}}' | tee "$TMP/networks.tsv"

sub "Likely duplicate project network prefixes"
cut -f1 "$TMP/networks.tsv" |
grep -vE '^(bridge|host|none)$' |
awk '
{
  n=$0
  sub(/_[^_]+$/, "", n)
  print n
}' | sort | uniq -c | sort -nr | awk '$1>1' | head -50

section "Compose files"
: > "$TMP/compose-files.txt"
for root in "${SCAN_ROOTS[@]}"; do
  [[ -d "$root" ]] || continue
  find "$root" -xdev -type f \
    \( -name compose.yml -o -name compose.yaml -o -name docker-compose.yml -o -name docker-compose.yaml \) \
    -print 2>/dev/null >> "$TMP/compose-files.txt"
done
sort -u -o "$TMP/compose-files.txt" "$TMP/compose-files.txt"
cat "$TMP/compose-files.txt"

sub "Directories containing multiple Compose files"
while IFS= read -r f; do dirname "$f"; done < "$TMP/compose-files.txt" |
  sort | uniq -c | sort -nr | awk '$1>1'

sub "Compose project names"
: > "$TMP/projects.tsv"
while IFS= read -r f; do
  dir="$(dirname "$f")"
  project="$(basename "$dir")"
  if docker compose -f "$f" config >/dev/null 2>&1; then
    resolved="$(cd "$dir" && docker compose -f "$f" config --format json 2>/dev/null | python3 -c '
import json,sys
try:
 d=json.load(sys.stdin)
 print(d.get("name",""))
except Exception:
 print("")
' 2>/dev/null || true)"
    [[ -n "$resolved" ]] && project="$resolved"
    printf '%s\t%s\n' "$project" "$f" >> "$TMP/projects.tsv"
  else
    printf '%s\t%s\n' "$project" "$f" >> "$TMP/projects.tsv"
  fi
done < "$TMP/compose-files.txt"

sort "$TMP/projects.tsv"

sub "Duplicate Compose project names"
cut -f1 "$TMP/projects.tsv" | sort | uniq -c | sort -nr | awk '$1>1'

sub "Files sharing duplicate project names"
python3 - "$TMP/projects.tsv" <<'PY'
import sys
from collections import defaultdict
d=defaultdict(list)
for line in open(sys.argv[1], encoding="utf-8", errors="ignore"):
    p, _, f=line.rstrip("\n").partition("\t")
    if p: d[p].append(f)
for p, files in sorted(d.items()):
    if len(files)>1:
        print(f"[{p}]")
        for f in files:
            print(" ", f)
PY

section "Compose service duplication"
: > "$TMP/services.tsv"
while IFS=$'\t' read -r project file; do
  [[ -n "$file" ]] || continue
  dir="$(dirname "$file")"
  if docker compose -f "$file" config --services >/dev/null 2>&1; then
    while IFS= read -r svc; do
      [[ -n "$svc" ]] && printf '%s\t%s\t%s\n' "$svc" "$project" "$file" >> "$TMP/services.tsv"
    done < <(cd "$dir" && docker compose -f "$file" config --services 2>/dev/null || true)
  fi
done < "$TMP/projects.tsv"

sub "Service names present in multiple Compose projects/files"
python3 - "$TMP/services.tsv" <<'PY'
import sys
from collections import defaultdict
d=defaultdict(list)
for line in open(sys.argv[1], encoding="utf-8", errors="ignore"):
    svc, proj, file = line.rstrip("\n").split("\t",2)
    d[svc].append((proj,file))
for svc, vals in sorted(d.items()):
    if len(vals)>1:
        print(f"[{svc}] x{len(vals)}")
        for proj,file in vals:
            print(f"  {proj}: {file}")
PY

section "Running Compose labels"
docker ps -a --format '{{.Names}}' | while read -r c; do
  docker inspect "$c" --format \
    '{{.Name}}|{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{index .Config.Labels "com.docker.compose.project.working_dir"}}' \
    2>/dev/null || true
done | sed 's#^/##' | tee "$TMP/compose-running.txt"

sub "Running projects and container counts"
awk -F'|' '$2!=""{print $2}' "$TMP/compose-running.txt" | sort | uniq -c | sort -nr

sub "Same service name running in multiple projects"
awk -F'|' '$2!="" && $3!=""{print $3"\t"$2"\t"$1}' "$TMP/compose-running.txt" |
python3 -c '
import sys
from collections import defaultdict
d=defaultdict(list)
for l in sys.stdin:
 s,p,c=l.rstrip().split("\t",2); d[s].append((p,c))
for s,v in sorted(d.items()):
 ps={x[0] for x in v}
 if len(ps)>1:
  print(f"[{s}]")
  for p,c in v: print(f"  {p}: {c}")
'

section "Possible duplicate stack directories"
python3 - "$TMP/compose-files.txt" <<'PY'
import os, sys, re
from collections import defaultdict

def norm(s):
    s=s.lower()
    s=re.sub(r'[-_.]?(copy|backup|bak|old|new|test|dev|prod|v\d+|\d+)$','',s)
    s=re.sub(r'[^a-z0-9]+','',s)
    return s

d=defaultdict(list)
for line in open(sys.argv[1], encoding="utf-8", errors="ignore"):
    f=line.strip()
    if not f: continue
    directory=os.path.dirname(f)
    key=norm(os.path.basename(directory))
    if key: d[key].append(directory)

for k, dirs in sorted(d.items()):
    uniq=sorted(set(dirs))
    if len(uniq)>1:
        print(f"[{k}]")
        for x in uniq:
            print(" ",x)
PY

section "Summary"
echo "Compose files : $(wc -l < "$TMP/compose-files.txt")"
echo "Containers    : $(wc -l < "$TMP/containers.tsv")"
echo "Images        : $(wc -l < "$TMP/images.tsv")"
echo "Volumes       : $(wc -l < "$TMP/volumes.tsv")"
echo "Networks      : $(wc -l < "$TMP/networks.tsv")"
echo
echo "READ-ONLY scan complete."
echo "Report saved to: $OUT"

if ((JSON)); then
  JSON_OUT="${OUT%.*}.json"
  python3 - "$TMP" "$JSON_OUT" <<'PY'
import json, os, sys
t, out = sys.argv[1:]
def count(name):
    p=os.path.join(t,name)
    try:
        return sum(1 for _ in open(p,encoding="utf-8",errors="ignore"))
    except FileNotFoundError:
        return 0
data={
  "compose_files": count("compose-files.txt"),
  "containers": count("containers.tsv"),
  "images": count("images.tsv"),
  "volumes": count("volumes.tsv"),
  "networks": count("networks.tsv"),
}
with open(out,"w") as f:
    json.dump(data,f,indent=2)
print("JSON summary saved to:", out)
PY
fi
