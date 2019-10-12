#!/usr/bin/env bash

set -e

base="$(pwd)"

if [ ! -f update_articles.lock ]; then
    touch update_articles.lock
    cd "../static-site"
    bundle exec jekyll build
    cd _site
    if [[ "$(git status --porcelain)" ]]; then
        git add .
        git commit -m "Bot update"  # Change this
        git push
    fi
    cd "$base"
    rm update_articles.lock
    echo "Done."
else
    echo "Lock in use."
    exit 1  # Wasn't able to update
fi
