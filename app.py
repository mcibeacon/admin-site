#!/usr/bin/python3

import flask
from flask import Flask, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
import flask_login
from flask_login import LoginManager, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, BooleanField, SelectField
from wtforms.validators import DataRequired
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash
from urllib.parse import urlparse, urljoin
from datetime import timedelta
from werkzeug.utils import secure_filename
import os
import pypandoc
import datetime
import time
import shutil
import yaml
import logging
from subprocess import Popen
import platform


STATIC_SITE_PATH = os.path.join("..", "static-site")
UPLOADS_DIR = "uploads"
DELETED_ARTICLES_PATH = "deletions"

# Only considered in production on my server
PROD = platform.node() == "jupiter"


app = Flask(__name__)
# Read secret key from git-ignored file for security
with open("secret_key", "r") as f:
    app.secret_key = eval(f.readlines()[0].strip())

# *** Setup Database ***
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///./users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Save memory
db = SQLAlchemy(app)

# User class is defined lower down
# ------

# *** Setup login objects ***
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
# TODO: Check github thread about this
flask_login.COOKIE_DURATION = timedelta(days=7)


@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(username=user_id).first()


class LoginForm(FlaskForm):
    username = StringField('username', validators=[DataRequired()])  # TODO: Off by 1?
    password = PasswordField('password', validators=[DataRequired()])
    remember_me = BooleanField('Remember me')

# User class is defined lower down
# ------


# *** Helper functions ***

ph = PasswordHasher()

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s: %(levelname)s:%(message)s', datefmt="%x %I:%M:%S %p")


def user_log(msg, level=logging.INFO):
    if level == logging.INFO:
        logging.info(str(current_user) + ": " + msg)
    elif level == logging.WARNING:
        logging.warning(str(current_user) + ": " + msg)
    elif level == logging.ERROR:
        logging.error(str(current_user) + ": " + msg)
    elif level == logging.CRITICAL:
        logging.critical(str(current_user) + ": " + msg)


def is_safe_url(target):
    # is_safe_url should check if the url is safe for redirects.
    # Taken from https://web.archive.org/web/20120517003641/http://flask.pocoo.org/snippets/62/
    # Put in the public domain by the original author

    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def iso8601_datetime(sep='T'):
    """Returns the current time in YYYY-MM-DDThh:mm:ss format.
    
    sep is a string that separates the date from the time, defaults to T
    according to the ISO.
    """

    # Source for this function: https://stackoverflow.com/a/28147286
    # I've made a modification at the end of the last line to cut off the timezone indicator

    # Calculate the offset taking into account daylight saving time
    utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
    utc_offset = datetime.timedelta(seconds=-utc_offset_sec)
    return datetime.datetime.now().replace(microsecond=0, tzinfo=datetime.timezone(offset=utc_offset)).isoformat(sep)[:-6]


def iso8601_date():
    """Returns the current date in YYYY-MM-DD format."""

    return iso8601_datetime()[:-9]


def prepend(file, text):
    """Prepends the provided text to a provided file."""

    with open(file, "r+") as f:
        lines = f.readlines()
        f.seek(0)
        f.write(text)
        f.writelines(lines)


def _find_article_path(file):
    """Finds the path of article, given the full filename.

    Looks in the regular articles directory first, then Bear Air.
    """

    filepath = os.path.join(STATIC_SITE_PATH, "articles/_posts/", file)
    if not os.path.isfile(filepath):
        filepath = os.path.join(STATIC_SITE_PATH, "bear_air/_posts/", file)
        if not os.path.isfile(filepath):
            raise FileNotFoundError

    return filepath


def _find_article_image_path(file):
    """Given the full filename of an article, it finds the image for that article, if any.

    Raises FileNotFoundError if the image cannot be found / doesn't exist.
    """

    print("*** Article", file)
    front_matter = get_front_matter(file)
    print("*** Front matter", front_matter)
    if "image" in front_matter:
        return os.path.join(STATIC_SITE_PATH, front_matter["image"])
    else:
        raise FileNotFoundError


def _front_matter_line_indexes(file):
    filepath = _find_article_path(file)
    start = None
    line = None
    with open(filepath, "r") as f:
        for i, line in enumerate(f):
            if line == "":
                # Unexpected EOF
                return None, None
            if line == "---\n":
                if start is None:
                    start = i
                else:
                    # Second "---""
                    return start, i


def get_front_matter(file):
    """Return the article's front matter as a dictionary."""

    # Could raise FileNotFound or TypeError
    filepath = _find_article_path(file)
    start, end = _front_matter_line_indexes(file)

    front_matter = ""
    with open(filepath, "r") as f:
        for i, line in enumerate(f):
            if i >= end:  # Skip ending "---"
                break
            if i > start:  # Skip starting line "---"
                front_matter += line
        
    return yaml.load(front_matter)


def set_front_matter(file, key, value):
    filepath = _find_article_path(file)
    front_matter = get_front_matter(file)
    front_matter[key] = value
    yaml_front_matter = yaml.dump(front_matter).splitlines(True)  # List of front matter lines as YAML strings
    start, end = _front_matter_line_indexes(file)
    with open(filepath, 'r+') as f:
        lines = f.readlines()
        # Remove old front matter
        # Iterate through each front matter line, excluding the "---" lines
        for i in range(end - (start + 1)):
            lines.pop(start + 1)  # Index can stay the same because the items move down after the pop
        # Add in new front matter
        lines = lines[:start + 1] + yaml_front_matter + lines[start + 1:]
        # Save
        f.seek(0)
        f.writelines(lines)


# Global LayoutForm choices
# Using [(article_file, article_title),...] format
article_choices = [("", "")]  # Always one choice to prevent errors
non_featured_choices = [("", "")]
featured_choices = [("", "")]


def populate_layout_choices(form):
    """Repopulates those global vars, but only actually affects LayoutForm properly."""

    global article_choices, non_featured_choices, featured_choices

    # Reset vars
    article_choices = [("", "")]  # Always one choice to prevent errors
    non_featured_choices = [("", "")]
    featured_choices = [("", "")]

    # List comprehension to generate a formatted, sorted (by date and title), list of articles
    # Vars for list comprehension, because sorting has to be done before with a variable
    # Sorting in place won't work
    sorted_article_posts = os.listdir(os.path.join(STATIC_SITE_PATH, "articles/_posts/"))
    sorted_article_posts.sort()
    article_choices.extend([(f, get_front_matter(f)["title"]) for f in sorted_article_posts])
    # Include Bear Air posts, with a divider that returns nothing if selected
    sorted_bear_air_posts = os.listdir(os.path.join(STATIC_SITE_PATH, "bear_air/_posts/"))
    sorted_bear_air_posts.sort()
    article_choices.extend([("", "--- Bear Air ---")])
    article_choices.extend([(f, get_front_matter(f)["title"]) for f in sorted_bear_air_posts])
    
    # Weed out bad articles
    for article in article_choices[1:]:  # Skip default empty first option
        if article[0] != "":  # Skip empty divider options
            try:
                # Make sure every front matter has a tags variable, so later code doesn't have to check all the time
                if "tags" not in get_front_matter(article[0]).keys():
                    set_front_matter(article[0], "tags", [])
                    continue
            except (FileNotFoundError, TypeError):
                # Remove articles that don't exist or have bad front matter
                article_choices.remove(article)
            
            # We already know tags is in the front matter
            if type(get_front_matter(article[0])["tags"]) == str:
                # Some front matter has tags written like: tags: featured
                # This means tags is a string, but later code relies on it being a list
                set_front_matter(article[0], "tags", [get_front_matter(article[0])["tags"]])
    # Sticky choices
    form.sticky.choices = article_choices
    # Featured choices
    # featured_add should only show articles without the featured tag
    for article in article_choices[1:]:
        if article[0] == "":  # Add empty divider option
            non_featured_choices.extend([article])  # Have to use extend on a tuple
        elif "featured" not in get_front_matter(article[0])["tags"]:
            non_featured_choices.extend([article])
    
    form.featured_add.choices = non_featured_choices
    # featured_remove should only show articles with the featured tag
    for article in article_choices[1:]:
        if article[0] == "":  # Add empty divider options
            featured_choices.extend([article])
        elif "featured" in get_front_matter(article[0])["tags"]:
            featured_choices.extend([article])
    form.featured_remove.choices = featured_choices

# ------


class User(db.Model, flask_login.UserMixin):
    """A class representing a user both for the db and for logging in and out."""

    # username = firstnamefirstletter + lastname
    username = db.Column(db.String(40), unique=True, nullable=False, primary_key=True)
    fullname = db.Column(db.String(40), nullable=False)
    hashpass = db.Column(db.String(77))  # argon2id hash of the password
    role = db.Column(db.Integer)  # 0 is admin/chiefs, 1 is for copy editors, 2 is for layout

    def __repr__(self):
        return f'{self.username}'

    def get_id(self):
        # For flask_login
        return self.username


# Get names of users (members with accounts) first
# [(username, fullname), (u2, f2), etc]
MEMBERS_TUPLES = [("", "")]  # Empty starter to detect if no author was selected
# Add all authors with accounts in the database
users = User.query.all()
for user in range(1, User.query.count()):  # Skip admin account
    MEMBERS_TUPLES.append((users[user].username, users[user].fullname))
# Now add all potential authors who don't have accounts, from the authors file
# TODO: Authors are incomplete
with open("authors.txt", "r") as f:
    line = f.readline()
    while line:
        if line.strip() != "":
            MEMBERS_TUPLES.extend([eval(line)])
        line = f.readline()


class ArticleForm(FlaskForm):
    file = FileField("Document", validators=[FileRequired(), FileAllowed(['doc', 'docx', 'md'], 'Documents only!')])
    author = SelectField("Author", choices=MEMBERS_TUPLES)
    title = StringField("Article Title", validators=[DataRequired()])
    photo = FileField("Title photo (optional)", validators=[FileAllowed(['png', 'jpg', 'jpeg'], "Pictures only!")])
    bear_air = BooleanField("Bear Air post")


class LayoutForm(FlaskForm):
    sticky = SelectField("Select Article")  # Choices set when rendered
    replace_current_sticky = BooleanField("Replace the current stickied article(s)")
    featured_add = SelectField("Add an article")  # Choices set when rendered
    featured_remove = SelectField("Remove an article")
    remove_all_featured = BooleanField("Remove all currently Featured articles")


class AdminForm(FlaskForm):
    articles = SelectField("Select Article")


class ForceUpdateForm(FlaskForm):
    # Empty so that CSRF can be used, the actual value sent is written in the HTML
    pass


# *** Begin web server code ***

@app.route("/", methods=["GET", "POST"])
@flask_login.login_required
def index():
    # Setup forms and errors
    article_form = ArticleForm()
    layout_form = LayoutForm()
    admin_form = AdminForm()
    force_update_form = ForceUpdateForm()
    layout_form_error = None
    article_form_error = None
    admin_form_error = None
    change = False  # If an update is needed on the Static Site

    # Populate before page load on GET
    if current_user.role < 3:
        populate_layout_choices(layout_form)
        if current_user.role < 2:
            admin_form.articles.choices = article_choices
    
    # Now check and process each form
    # Extra checks beyond is_submitted are done, because this page has multiple forms
    # request.form is used because the extra checks are done through a hidden value in
    # the HTML.
    # on the same POST endpoint. The current libs don't support other POST endpoints
    # AFAIK.

    if layout_form.is_submitted() and request.form["form_name"] == "layout_form":
        if layout_form.validate():
            # Go through each option in the layout_form and process it

            if layout_form.replace_current_sticky.data:
                # Remove the sticky tag from all posts
                for article in article_choices[1:]:  # Skip empty default first option
                    tags = get_front_matter(article[0])["tags"]
                    if "sticky" in tags:
                        tags.remove("sticky")  # Keep other tags in there
                        set_front_matter(article[0], "tags", tags)
                        change = True
                user_log("Removed the sticky data from all posts")
            if layout_form.sticky.data != "":
                # They want to sticky a post
                tags = get_front_matter(layout_form.sticky.data)["tags"]
                if "sticky" not in tags:  # This post isn't already stickied
                    tags.append("sticky")  # Keep other tags
                    set_front_matter(layout_form.sticky.data, "tags", tags)
                    change = True
                    user_log("Stickied post " + layout_form.sticky.data)
            if layout_form.remove_all_featured.data:
                # Remove the featured tag from all posts
                for article in featured_choices[1:]:
                    tags = get_front_matter(article[0])["tags"]
                    if "featured" in tags:
                        tags.remove("featured")
                        set_front_matter(article[0], "tags", tags)
                        change = True
                user_log("Removed the featured tag from all posts")
            elif layout_form.featured_remove.data != "":
                # elif - Only check this if we aren't removing all the featured articles
                tags = get_front_matter(layout_form.featured_remove.data)["tags"]
                if "featured" in tags:
                    tags.remove("featured")
                    set_front_matter(layout_form.featured_remove.data, "tags", tags)
                    change = True
                    user_log("Un-featured post " + layout_form.featured_remove.data)
            if layout_form.featured_add.data != "":
                # Add the featured tag to a post
                tags = get_front_matter(layout_form.featured_add.data)["tags"]
                if "featured" not in tags:  # It should be, this is just in case
                    tags.append("featured")
                    set_front_matter(layout_form.featured_add.data, "tags", tags)
                    change = True
                    user_log("Featured post " + layout_form.featured_add.data)
        else:
            layout_form_error = "Error with submission."
            user_log("Error with layout form submission: " + str(layout_form.errors))
        
    if article_form.is_submitted() and request.form["form_name"] == "article_form":
        if article_form.validate() and article_form.author.data != "":  # The only potential empty field
            # Begin process to change the document into a valid Jekyll post

            # Save file
            f = article_form.file.data
            filename = secure_filename(f.filename)
            # Calculate name and path after all processing to prevent future duplicates
            # Name format is YYYY-MM-DD-file-name.md
            final_filename = iso8601_date() + '-' + os.path.splitext(filename)[0] + ".md"
            og_final_filename = final_filename
            # If a file with that name already exists,
            # give it a name with a higher number
            # Eg test.docx becomes test-2.docx or test-3.docx if test-2.docx exists
            # This checks the uploads folder, as well as the folders with already existing articles
            # It checks without the extension bc the article files will be .md
            i = 2
            while final_filename in os.listdir(UPLOADS_DIR) or \
                final_filename in os.listdir(os.path.join(STATIC_SITE_PATH, "articles/_posts/")) or \
                    final_filename in os.listdir(os.path.join(STATIC_SITE_PATH, "bear_air/_posts/")):
                
                final_filename = os.path.splitext(og_final_filename)[0] + "-" + str(i) + os.path.splitext(og_final_filename)[1]
                i += 1
            
            # Save as upload filetype, but with new name, with date and duplicate number
            filename = os.path.splitext(final_filename)[0] + os.path.splitext(filename)[1]
            filepath = os.path.join(UPLOADS_DIR, filename)
            f.save(filepath)
            
            # The article will now be processed and moved into the Static Site directory

            md_filepath = os.path.join(UPLOADS_DIR, final_filename)
            # Convert file
            if filename[-3:] != ".md":
                # Conversion needed - output file has same name but .md extension
                pypandoc.convert_file(filepath, 'md', filters=['list_filter.hs'], outputfile=md_filepath)
                os.remove(filepath)  # Delete original upload
                # Update vars for converted file
            # Process the title
            title = article_form.title.data
            # Process the title photo if it exists
            if article_form.photo.data:
                p = article_form.photo.data
                # Saves it as article-name_photo.ext
                # Note that the article name includes the date
                p_filename = final_filename[:-3] + "_photo" + os.path.splitext(secure_filename(p.filename))[1]
                p_filepath = os.path.join(UPLOADS_DIR, p_filename)
                p.save(p_filepath)
            # Add front matter
            front_matter = {"layout": "post", "title": title, "author": article_form.author.data}
            if article_form.photo.data:
                front_matter["image"] = "assets/images/" + p_filename
            prepend_text = "---\n" + yaml.dump(front_matter) + "---\n\n"  # Add openers and closers
            prepend(md_filepath, prepend_text)
            # Move files to the static site
            if article_form.bear_air.data:  # It's a Bear Air post
                shutil.move(md_filepath, os.path.join(STATIC_SITE_PATH, "bear_air/_posts/"))
            else:
                shutil.move(md_filepath, os.path.join(STATIC_SITE_PATH, "articles/_posts/"))
            if article_form.photo.data:
                shutil.move(p_filepath, os.path.join(STATIC_SITE_PATH, "assets/images/"))
            
            # Article processing is done!
            change = True
            user_log("Uploaded article " + final_filename)
        else:
            article_form_error = "Error with submission."
            user_log("Error with article form submission: " + str(article_form.errors))

    if admin_form.is_submitted() and request.form["form_name"] == "admin_form":
        if admin_form.validate() and admin_form.articles.data != "":
            # Try to send article to trash
            try:
                shutil.move(_find_article_path(admin_form.articles.data), DELETED_ARTICLES_PATH)
                user_log("Deleted article " + admin_form.articles.data)
                change = True
            except FileNotFoundError:
                admin_form_error = "That article is already deleted."
                user_log("Tried to delete an article that doesn't exist", level=logging.ERROR)
            except shutil.Error:
                # Hopefully a "Destination path X already exists" error
                # Which means an already deleted file has the same name
                # XXX: The already-deleted file is permanently deleted
                os.remove(os.path.join(DELETED_ARTICLES_PATH, admin_form.articles.data))
                shutil.move(_find_article_path(admin_form.articles.data), DELETED_ARTICLES_PATH)
                change = True
                user_log("Permanently deleted, and then temp-deleted article " + admin_form.articles.data)
            
            # Now try to delete article photo if it exists
            try:
                shutil.move(_find_article_image_path(admin_form.articles.data), DELETED_ARTICLES_PATH)
                user_log("Deleted article image for" + admin_form.articles.data)
            except FileNotFoundError:
                pass  # No article image
            except shutil.Error:
                # Hopefully a "Destination path X already exists" error
                # Which means an already deleted file has the same name
                # XXX: The already-deleted file is permanently deleted
                os.remove(os.path.join(DELETED_ARTICLES_PATH, os.path.basename(_find_article_image_path(admin_form.articles.data))))
                shutil.move(_find_article_path(admin_form.articles.data), DELETED_ARTICLES_PATH)
                change = True
                user_log("Permanently deleted, and then temp-deleted article photo for" + admin_form.articles.data)
        else:
            admin_form_error = "Error with submission."
            user_log("Error with admin form submission: " + str(admin_form.errors))

    if force_update_form.is_submitted() and request.form["form_name"] == "force_update_form":
        if force_update_form.validate():  # For CSRF
            change = True

    # Repopulate after POST so that options are updated
    if current_user.role < 3:
        populate_layout_choices(layout_form)
        if current_user.role < 2:
            admin_form.articles.choices = article_choices

    if change:
        if PROD:
            Popen("./update_articles.sh")
        else:
            user_log("Skipped actually updating because not running in production")
    # Role determines what forms are displayed
    return render_template('index.html', role=current_user.role, layout_form=layout_form, article_form=article_form,
                           admin_form=admin_form, force_update_form=force_update_form, layout_form_error=layout_form_error,
                           article_form_error=article_form_error, admin_form_error=admin_form_error)


@app.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # Check login info
        user = User.query.filter_by(username=form.username.data).first()
        if user is None:
            # Username doesn't exist
            return render_template('login.html', form=form, error="Username doesn't exist, ask Cole to give you an account.")
        else:
            # Username exists
            try:
                ph.verify(user.hashpass, form.password.data)
            except VerifyMismatchError:
                # Incorrect password
                return render_template('login.html', form=form, error='Incorrect password')
            except (InvalidHash, AttributeError):
                # Password isn't setup correctly in the DB
                return render_template('login.html', form=form, error="Database error, talk to Cole. Maybe your account hasn't been set up.")

            # Username and password are correct, so log them in
            flask_login.login_user(user, remember=form.remember_me.data)
            user_log("Logged in")

            next = flask.request.args.get('next')
            if not is_safe_url(next):
                return flask.abort(400)

            return flask.redirect(next or url_for('index'))
    
    return render_template('login.html', form=form)


@app.route('/logout')
@flask_login.login_required
def logout():
    user_log("Logged out")
    flask_login.logout_user()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
