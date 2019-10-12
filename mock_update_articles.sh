#!/usr/bin/env bash

set -e

if [ ! -f update_articles.lock ]; then
    touch update_articles.lock
    cd "../Static Site"
    bundle exec jekyll build
    cd _site
    if [[ "$(git status --porcelain)" ]]; then
        git add .
        git commit -m "Bot update"  # Change this
        git push https://username:password@github.com/name/repo.git  # Add bot name and password, not to Github though
    fi
    rm update_articles.lock
else
    exit 1  # Wasn't able to update
fi
