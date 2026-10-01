#!/bin/bash

export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

D="$(cd "$(dirname "$0")" && pwd)"
cd "$D/apache-nutch-1.23"
"$D/setup.sh"
B="$D/logs/bitacora_nutch.log"

mkdir -p "$D/logs" "$D/crawldb" "$D/segments"
bin/nutch inject "$D/crawldb" "$D/urls" 2>&1 | tee -a "$B"
for i in 1 2 3; do
  bin/nutch generate "$D/crawldb" "$D/segments" -topN 100 2>&1 | tee -a "$B"
  SEG="$(ls -t "$D/segments" | head -1)"
  [ -z "$SEG" ] && break
  bin/nutch fetch "$D/segments/$SEG" -all 2>&1 | tee -a "$B"
  bin/nutch parse "$D/segments/$SEG" -all 2>&1 | tee -a "$B"
  bin/nutch updatedb "$D/crawldb" "$D/segments/$SEG" 2>&1 | tee -a "$B"
done