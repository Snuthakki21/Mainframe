#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p build
javac --release 17 -d build ./*.java jobs/*.java
