#!/usr/bin/python3

"""Tool to add authors to the admin and static sites."""

import os
import sys

STATIC_SITE_PATH = "../static-site"


def if_in_file_abort(file, *argv):
    with open(file, "r") as f:
        line = f.readline()
        while line:
            for arg in argv:
                if arg in line:
                    print("Name or short name already in" + file + " -- Aborting")
                    sys.exit(1)
            line = f.readline()


print("This is a tool to add an author to the website.")
print("Press Ctrl-C to quit at any time. You will need to rebuild the site for changes to appear.")

while True:
    full_name = input("Type the author's first and last name: ")
    # First letter of first name + last name
    # Eg. John Smith --> jsmith
    short_name = full_name.lower()[0] + full_name.lower()[full_name.index(" ") + 1:]
    bio = input('Type their bio. Press enter to set it to "Columnist."\n> ')
    if bio == "":
        bio = "Columnist."
    ig = input("Enter a full link to their Instagram. Press enter to set it to the MCI Beacon one.\n> ")
    if ig == "":
        ig = "https://instagram.com/mcibeacon"
    
    # Search config to see if the full name or shortened name is already in there
    # Checking this file first is IMPORTANT, because they might not be in authors.txt
    # if there name is the database, but they will definitely be in the config file
    if_in_file_abort(os.path.join(STATIC_SITE_PATH, "_config.yml"), full_name, short_name)
    # Check authors.txt too
    if_in_file_abort("authors.txt", full_name, short_name)
    # Check if the name already has an author page on the site
    author_file = "author-" + full_name.lower().replace(" ", "-") + ".html"
    if author_file in os.listdir(os.path.join(STATIC_SITE_PATH, "_pages")):
        print(author_file, "already exists. -- Aborting")
        sys.exit(1)
    # Done checks

    # Now write author info to relevant files

    # Add to authors.txt
    with open("authors.txt", "a") as f:
        f.write('\n("' + short_name + '", "' + full_name + '")')  # Write ("jsmith", "John Smith")
    print("Added to authors.txt")
    # Add to jekyll config
    with open(os.path.join(STATIC_SITE_PATH, "_config.yml"), "a") as f:
        # Writes the following:
        #  short_name:
        #    name: "full_name"
        #    bio: "bio"
        #    instagram: ig
        lines = [
            "  " + short_name + ":",
            '    name: "' + full_name + '"',
            '    bio: "' + bio + '"',
            '    instagram: ' + ig
        ]

        f.write("\n")
        for line in lines:
            f.write("\n" + line)
    print("Added to _config.yml")
    # Add author webpage
    with open(os.path.join(STATIC_SITE_PATH, "_pages", author_file), "w") as f:
        lines = [
            "---",
            'title: "' + full_name + '"',
            "layout: default",
            'permalink: "/' + author_file + '"',
            "---",
            "",
            "{% include author-page.html author=site.authors." + short_name + ' authorname="' + short_name + '" %}'
        ]
        
        for line in lines:
            f.write(line + "\n")
    print("Added author webpage", author_file)
    print()
