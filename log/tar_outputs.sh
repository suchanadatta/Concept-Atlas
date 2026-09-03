#!/bin/bash
cd /store/shuvam/BMoral
tar -c -I 'xz -9 -T0' -f outputs.tar.xz outputs/
echo "TAR EXIT: $?"
ls -la outputs.tar.xz
