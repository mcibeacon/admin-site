# Notes

## Links
- Flask for web server
- Users
  - Authentication - flask-login
    - https://flask-login.readthedocs.io/en/latest/
    - https://github.com/maxcountryman/flask-login
    - https://realpython.com/using-flask-login-for-user-management-with-flask/
  - flask-wtf and WTForms for login forms
    - https://flask-wtf.readthedocs.io/en/stable/
    - https://wtforms.readthedocs.io/en/stable/
  - Database for users - flask-sqlalchemy
    - https://flask-sqlalchemy.palletsprojects.com/en/2.x/
  - Password hashing - argon2_cffi
    - https://argon2-cffi.readthedocs.io/en/stable/

## TODO
- [x] Handle duplicate uploads
- [x] Remove bear_air flags
- [x] Remove all prints once it's okay
- [x] Remove all asserts once it's okay
- [x] Logging
- [x] Sort `os.listdir()` output
- [x] Get rid of double Bear Air divider in the Featured add list
- [x] Big bug where the last few bits of articles are repeated
  - [ ] Should be a false alarm, **double check later**
- [x] Have hidden `formname` value on each form, check for that along with `is_submitted`
- [x] Use `yaml.dump` to add front matter
  - [x] Test it
- [x] Protect against malicious POST requests
  - Trying to use options not listed
- [x] Test for title that needs escaping
- [x] Remove unecessary XXX comments
- [x] Go through TODOs
- [ ] Should I wrap a bunch of stuff in a big try-except and return the error to the user?
- [ ] Time the file processing and see if it needs to be in a separate thread
  - So far so good with small files
- [x] Figure out how new articles will be added to the site
  - Steps
    1. Run `bundle exec jekyll build`
    2. Go into `_site`
    3. `git commit -am "something"`
    4. `git push`
  - Options
    - Run within Python script
    - [x] **Spawn separate Bash process**
      - [x] Test it
    - Have a separate script that checks for new files every 5 mins and adds them
  - Notes
    - [x] Some sort of lock could be required so multiple threads don't try it at once
- [ ] Add to Github
- [x] Force update button
  - [x] Test (script too)
- [x] Test `reset.sh`
- [x] Test deleting an article that is already in deletions


## Roles
- 0=Admin
- 1=Copy Editors
- 2=Layout

## Layout abilities
- [x] Set which articles are featured on the sidebar (featured tag)
- [x] Set which article(s) is big on the homepage (sticky tag)
- [ ] Edit articles??
  - Metadata
  - Reupload file

## Copy Editors abilities
- *All previous abilities*
- [x] Upload articles - **Main focus of dashboard**
  - Upload as doc or docx
  - Set title
  - Optionally upload title photo
  - Pick authors from a dropdown
  - Set as Bear Air or not
- Add new authors maybe?

## Admin abilities
- *All previous abilities*
- [x] Delete articles
  - [x] Go to another folder for storage
