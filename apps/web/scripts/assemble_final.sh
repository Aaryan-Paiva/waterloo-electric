#!/bin/bash
set -e
FFMPEG=/opt/homebrew/bin/ffmpeg
cd "$(dirname "$0")/out"

make_still() {
  local src="$1" dur="$2" out="$3"
  $FFMPEG -y -loop 1 -i "$src" -t "$dur" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1" \
    -c:v libx264 -pix_fmt yuv420p -an "$out" > /tmp/ff_${RANDOM}.log 2>&1 || { echo "FAILED: $out"; tail -20 /tmp/ff_*.log; exit 1; }
}

# Persona/end cards -> videos (durations bumped up to compensate for cinematic clips staying at native 6s)
make_still "motion/extra/07-utility.png"    9  "motion/extra/07-utility.mp4"
make_still "motion/extra/08-aggregator.png" 9  "motion/extra/08-aggregator.mp4"
make_still "motion/extra/09-planner.png"    9  "motion/extra/09-planner.mp4"
make_still "motion/extra/10-endcard.png"    18 "motion/extra/10-endcard.mp4"

# ChatGPT static motion graphics -> videos (held longer to compensate)
SRC="/Users/aaryanpaiva/Documents/ChatGPT/GridCity/assets/motion-graphics"
mkdir -p motion/static
make_still "$SRC/01-demand-vs-capacity-8s.png"      14 "motion/static/01-demand-vs-capacity-8s.mp4"
make_still "$SRC/02-vpp-devices-8s.png"              14 "motion/static/02-vpp-devices-8s.mp4"
make_still "$SRC/03-request-offer-dispatch-8s.png"   17 "motion/static/03-request-offer-dispatch-8s.mp4"
make_still "$SRC/04-capacityos-title-4s.png"         10 "motion/static/04-capacityos-title-4s.mp4"
make_still "$SRC/05-zone-eligibility-6s.png"         10 "motion/static/05-zone-eligibility-6s.mp4"
make_still "$SRC/06-pilot-to-rollout-8s.png"         17 "motion/static/06-pilot-to-rollout-8s.mp4"

# Cinematic clips: kept at their NATIVE ~6s duration (no freeze-frame extension — looked weird/static)
mkdir -p cinematic/extended
for f in cinematic/*.mp4; do
  base=$(basename "$f")
  $FFMPEG -y -i "$f" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1" \
    -c:v libx264 -pix_fmt yuv420p -an "cinematic/extended/$base" > /tmp/ff_ext_${RANDOM}.log 2>&1 || { echo "FAILED: $base"; exit 1; }
done

# Walkthrough: normalize resolution, strip audio
$FFMPEG -y -i walkthrough.mp4 \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1" \
  -c:v libx264 -pix_fmt yuv420p -an walkthrough_norm.mp4 > /tmp/ff_wt.log 2>&1 || { echo "FAILED walkthrough"; exit 1; }

echo "All segments built. Verifying files exist..."
for f in \
  cinematic/extended/01_neighborhood.mp4 \
  cinematic/extended/02_datacentre.mp4 \
  cinematic/extended/03_buses.mp4 \
  cinematic/extended/04_industrial.mp4 \
  motion/static/01-demand-vs-capacity-8s.mp4 \
  motion/static/02-vpp-devices-8s.mp4 \
  motion/static/04-capacityos-title-4s.mp4 \
  motion/extra/07-utility.mp4 \
  motion/extra/08-aggregator.mp4 \
  motion/extra/09-planner.mp4 \
  motion/static/05-zone-eligibility-6s.mp4 \
  walkthrough_norm.mp4 \
  motion/static/03-request-offer-dispatch-8s.mp4 \
  motion/static/06-pilot-to-rollout-8s.mp4 \
  motion/extra/10-endcard.mp4 \
; do
  [ -f "$f" ] || { echo "MISSING: $f"; exit 1; }
done
echo "All present."

TMPLIST=$(mktemp)
for f in \
  cinematic/extended/01_neighborhood.mp4 \
  cinematic/extended/02_datacentre.mp4 \
  cinematic/extended/03_buses.mp4 \
  cinematic/extended/04_industrial.mp4 \
  motion/static/01-demand-vs-capacity-8s.mp4 \
  motion/static/02-vpp-devices-8s.mp4 \
  motion/static/04-capacityos-title-4s.mp4 \
  motion/extra/07-utility.mp4 \
  motion/extra/08-aggregator.mp4 \
  motion/extra/09-planner.mp4 \
  motion/static/05-zone-eligibility-6s.mp4 \
  walkthrough_norm.mp4 \
  motion/static/03-request-offer-dispatch-8s.mp4 \
  motion/static/06-pilot-to-rollout-8s.mp4 \
  motion/extra/10-endcard.mp4 \
; do
  echo "file '$(pwd)/$f'" >> "$TMPLIST"
done

$FFMPEG -y -f concat -safe 0 -i "$TMPLIST" -c:v libx264 -pix_fmt yuv420p -crf 18 final_assembly.mp4

echo "DONE"
ffprobe -v error -show_entries format=duration -of csv=p=0 final_assembly.mp4
rm -f "$TMPLIST"
