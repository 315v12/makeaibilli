#!/usr/bin/env bash
# makeaibilli — clean build with a progress bar (hides the pip wall of text)
cd "$(dirname "$0")"

LOG=$(mktemp)
SPIN='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
BARW=34
# total build instructions across both Dockerfiles ≈ number of STEP lines podman prints
TOTAL=$(cat docker/Dockerfile.* 2>/dev/null | grep -cE '^(FROM|RUN|COPY|ENV|EXPOSE|CMD|WORKDIR|HEALTHCHECK)')
[ "$TOTAL" -lt 1 ] && TOTAL=21

echo ""
echo "  🏗   Building makeaibilli  (a few minutes — grab a coffee)"
echo ""

# run the real build in the background, capture output
podman-compose build --no-cache >"$LOG" 2>&1 &
PID=$!

start=$(date +%s); i=0
while kill -0 "$PID" 2>/dev/null; do
  done=$(grep -c 'STEP ' "$LOG" 2>/dev/null); done=${done:-0}
  pct=$(( done * 100 / TOTAL )); [ "$pct" -gt 99 ] && pct=99
  filled=$(( pct * BARW / 100 )); empty=$(( BARW - filled ))
  bar=""; for ((b=0;b<filled;b++)); do bar+="█"; done
  for ((b=0;b<empty;b++)); do bar+="░"; done
  step=$(grep 'STEP ' "$LOG" 2>/dev/null | tail -1 | sed 's/-->.*//' | cut -c1-46)
  el=$(( $(date +%s) - start ))
  c=${SPIN:$((i%10)):1}
  printf "\r  %s  [%s] %3d%%  %3ds  %-46s" "$c" "$bar" "$pct" "$el" "$step"
  i=$((i+1)); sleep 0.2
done

wait "$PID"; rc=$?
el=$(( $(date +%s) - start ))
bar=""; for ((b=0;b<BARW;b++)); do bar+="█"; done
printf "\r%*s\r" 120 ""   # clear line
if [ "$rc" -eq 0 ]; then
  printf "  ✅  [%s] 100%%   built in %ds\n\n" "$bar" "$el"
  echo "  🚀  Starting containers..."
  podman-compose up -d >/dev/null 2>&1
  echo ""
  echo "  ✅  Running.  Dashboard:  http://localhost:8501"
  echo "      (from your phone:    http://$(hostname -I 2>/dev/null | awk '{print $1}'):8501 )"
  echo ""
  echo "  Watch live activity:  podman logs -f makeaibilli_scraper_1"
else
  echo "  ❌  Build failed. Last 25 lines:"
  echo "  ----------------------------------------"
  tail -25 "$LOG" | sed 's/^/  /'
fi
rm -f "$LOG"
