#!/bin/bash
pkill -9 -f "twb.py"
pkill -9 -f "server.py"
rm -rf cache/*
rm -f config.json config.bak
echo "Bot został wyzerowany. Odpal python3 twb.py aby wygenerować config."
