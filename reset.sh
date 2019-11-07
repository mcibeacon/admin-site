#!/usr/bin/env bash

# This script is used to reset various folders and files back to their default state
# It should be used by systemd for a restart, maybe

rm uploads/*
touch uploads/.gitempty
rm update_articles.lock