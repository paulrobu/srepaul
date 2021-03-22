import sqlite3
import random
import string
import time
import requests
from flask import Flask, Markup, render_template, request, url_for, flash, redirect, json
from werkzeug.exceptions import abort

def init_db():
    connection = sqlite3.connect('db.sqlite3')
    cursor = connection.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS srepaul \
        (shorturl TEXT PRIMARY KEY, longurl TEXT NOT NULL, visits TEXT);")
    connection.commit()
    connection.close()


def get_db_connection():
    conn = sqlite3.connect('db.sqlite3')
    conn.row_factory = sqlite3.Row
    return conn


app = Flask(__name__)
app.config['SECRET_KEY'] = 'key needed by Flask to flash messages'


@app.route('/', methods=('GET', 'POST'))
def index():
    if request.method == 'POST':
        longurl = request.form['longurl']
        shorturl = generate_shorturl()
        url = request.host_url + shorturl
        status_code = str(validate(longurl))
        existing_shorturl = check_existing_url(longurl)
        if not longurl:
            flash(u'Please enter an URL to shorten', 'error')
        elif status_code[0] == '2':
            if existing_shorturl is None:
                set_newurl(longurl, shorturl)
                flash(f'{longurl} is now accessible at <a class="alert-link" \
                    href="{url}">{url}</a>', 'info')
            else:
                flash(f'{longurl} is already shortened as <a class="alert-link" \
                     href="{existing_shorturl}">{existing_shorturl}</a>', 'message')
        else:
            flash(
                f'{longurl} is unreachable, please provide valid URL: {status_code}', 'error')
    return render_template('index.html')


@app.route('/<shorturl>')
def site_redirect_engine(shorturl):
    """
    Redirect visitors to the long URL, for valid short URL.
    If protocol is missing, add HTTP (to allow external redirect).
    Track the number of times the short URL is visited.
    """
    longurl = get_longurl(shorturl)
    if longurl is None:
        abort(404)
    if longurl.find("http://") != 0 and longurl.find("https://") != 0:
        longurl = "http://" + longurl
    if longurl:
        update_visits(shorturl)
    return redirect(longurl)


@app.route('/<url>/stats')
def stats(url):
    """A statistics page for the short URL"""
    page = get_stats(url)
    count = get_visits_count(url)
    graph = prepare_graphic_data(url)
    return render_template('stats.html', url=page, count=count, graph=graph)


@app.route('/all')
def catalog():
    """A catalog to list all short URLs"""
    conn = get_db_connection()
    catalog = conn.execute('SELECT * FROM srepaul').fetchall()
    conn.close()
    return render_template('catalog.html', catalog=catalog)


def set_newurl(longurl, shorturl):
    conn = get_db_connection()
    conn.execute('INSERT INTO srepaul (longurl, shorturl, visits) VALUES (?, ?, ?)',
                 (longurl, shorturl, ""))
    conn.commit()
    conn.close()


def get_longurl(shorturl):
    conn = get_db_connection()
    sql = "SELECT longurl FROM srepaul WHERE shorturl = ?"
    result = conn.execute(sql, [shorturl]).fetchone()
    conn.close()
    return result['longurl']


def update_visits(shorturl):
    """Add each new visit as Unix timestamp"""
    conn = get_db_connection()
    sql = 'SELECT visits FROM srepaul WHERE shorturl = ?'
    url = conn.execute(sql, [shorturl]).fetchone()
    old_visits = url['visits']
    new_visits = f'{old_visits} {str(int(time.time()))+"000"}'
    update_sql = 'UPDATE srepaul SET visits = ? WHERE shorturl = ?'
    conn.execute(update_sql, [new_visits, shorturl])
    conn.commit()
    conn.close()


def get_visits_count(shorturl):
    conn = get_db_connection()
    sql = 'SELECT visits FROM srepaul WHERE shorturl = ?'
    result = conn.execute(sql, [shorturl]).fetchone()
    conn.close()
    return len(result['visits'].split())


def get_visits(shorturl):
    conn = get_db_connection()
    sql = 'SELECT visits FROM srepaul WHERE shorturl = ?'
    result = conn.execute(sql, [shorturl]).fetchone()
    conn.close()
    return result['visits']


def get_stats(shorturl):
    conn = get_db_connection()
    result = conn.execute('SELECT * FROM srepaul WHERE shorturl = ?',
                          [shorturl]).fetchone()
    conn.close()
    if result is None:
        abort(404)
    return result


def check_existing_url(longurl):
    """Detect if URL already exists"""
    conn = get_db_connection()
    sql = "SELECT * FROM srepaul WHERE longurl = ?"
    result = conn.execute(sql, [longurl]).fetchone()
    conn.close()
    if result is None:
        return None
    else:
        return result['shorturl']


def generate_shorturl():
    letters = ''.join(random.choice(string.ascii_lowercase) for n in range(3))
    numbers = ''.join(random.choice(string.digits) for n in range(4))
    return letters+numbers


def validate(longurl):
    """Consider as invalid url any status other than 2xx"""
    if longurl.find("http://") != 0 and longurl.find("https://") != 0:
        longurl = "http://" + longurl
    try:
        page = requests.get(longurl)
        if not page.status_code // 100 == 2:
            return f"Error: Unexpected response {page}"
        return page.status_code
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"


def prepare_graphic_data(shorturl):
    """
    Get visits timestamps and count number of repeating occurences.
    Return them in a list as needed by the js script:
    https://c3js.org/reference.html#data-rows
    """
    visits = get_visits(shorturl).split()
    graph = dict()
    for visit in visits:
        if visit in graph:
            graph[visit] += 1
        else:
            graph[visit] = 1
    visits_list = [['x1', 'Visits']]
    for k, v in graph.items():
        visits_list.append([int(k), v])
    return visits_list


init_db()
