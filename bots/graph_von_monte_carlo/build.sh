#!/bin/bash

# fail on error to show build errors
set -e

mkdir -p build
cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make
cd ..
