
"""
Columbia's COMS W4111.001 Introduction to Databases
Example Webserver
To run locally:
    python server.py
Go to http://localhost:8111 in your browser.
A debugger such as "pdb" may be helpful for debugging.
Read about it online.
"""
import os
# accessible as a variable in index.html:
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, abort

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)


#
# The following is a dummy URI that does not connect to a valid database. You will need to modify it to connect to your Part 2 database in order to use the data.
#
# XXX: The URI should be in the format of: 
#
#     postgresql://USER:PASSWORD@34.139.8.30/proj1part2
#
# For example, if you had username ab1234 and password 123123, then the following line would be:
#
#     DATABASEURI = "postgresql://ab1234:123123@34.139.8.30/proj1part2"
#
# Modify these with your own credentials you received from TA!
DATABASE_USERNAME = "yc4802"
DATABASE_PASSWRD = "402428"
DATABASE_HOST = "34.139.8.30"
DATABASEURI = f"postgresql://{DATABASE_USERNAME}:{DATABASE_PASSWRD}@{DATABASE_HOST}/proj1part2"


#
# This line creates a database engine that knows how to connect to the URI above.
#
engine = create_engine(DATABASEURI)

#
# Example of running queries in your database
# Note that this will probably not work if you already have a table named 'test' in your database, containing meaningful data. This is only an example showing you how to run queries in your database using SQLAlchemy.
#
with engine.connect() as conn:
    create_table_command = """
    CREATE TABLE IF NOT EXISTS test (
        id serial,
        name text
    )
    """
    res = conn.execute(text(create_table_command))
    insert_table_command = """INSERT INTO test(name) VALUES ('grace hopper'), ('alan turing'), ('ada lovelace')"""
    res = conn.execute(text(insert_table_command))
    # you need to commit for create, insert, update queries to reflect
    conn.commit()


@app.before_request
def before_request():
    """
    This function is run at the beginning of every web request 
    (every time you enter an address in the web browser).
    We use it to setup a database connection that can be used throughout the request.

    The variable g is globally accessible.
    """
    try:
        g.conn = engine.connect()
    except:
        print("uh oh, problem connecting to database")
        import traceback; traceback.print_exc()
        g.conn = None

@app.teardown_request
def teardown_request(exception):
    """
    At the end of the web request, this makes sure to close the database connection.
    If you don't, the database could run out of memory!
    """
    try:
        g.conn.close()
    except Exception as e:
        pass


#
# @app.route is a decorator around index() that means:
#   run index() whenever the user tries to access the "/" path using a GET request
#
# If you wanted the user to go to, for example, localhost:8111/foobar/ with POST or GET then you could use:
#
#       @app.route("/foobar/", methods=["POST", "GET"])
#
# PROTIP: (the trailing / in the path is important)
# 
# see for routing: https://flask.palletsprojects.com/en/1.1.x/quickstart/#routing
# see for decorators: http://simeonfranklin.com/blog/2012/jul/1/python-decorators-in-12-steps/
#
@app.route('/', methods=['GET', 'POST'])
def index():
    """
    request is a special object that Flask provides to access web request information:

    request.method:   "GET" or "POST"
    request.form:     if the browser submitted a form, this contains the data in the form
    request.args:     dictionary of URL arguments, e.g., {a:1, b:2} for http://localhost?a=1&b=2

    See its API: https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data
    """

    # DEBUG: this is debugging code to see what request looks like
    print(request.args)

    if request.method == 'POST':
        username = request.form['username']
        pin = request.form['pin']

        cursor = g.conn.execute(
            text("SELECT * FROM climber WHERE username = :u AND pin = :p"),
            {'u': username, 'p': pin}
        )
        user = cursor.fetchone()
        cursor.close()

        if user:
            return redirect(f'/climber_home/{username}')
        else:
            return render_template('index.html', error="Invalid username or PIN")


    #
    # example of a database query
    #
    # select_query = "SELECT name from test"
    # cursor = g.conn.execute(text(select_query))
    # names = []
    # for result in cursor:
    # 	names.append(result[0])
    # cursor.close()

    #
    # Flask uses Jinja templates, which is an extension to HTML where you can
    # pass data to a template and dynamically generate HTML based on the data
    # (you can think of it as simple PHP)
    # documentation: https://realpython.com/primer-on-jinja-templating/
    #
    # You can see an example template in templates/index.html
    #
    # context are the variables that are passed to the template.
    # for example, "data" key in the context variable defined below will be 
    # accessible as a variable in index.html:
    #
    #     # will print: [u'grace hopper', u'alan turing', u'ada lovelace']
    #     <div>{{data}}</div>
    #     
    #     # creates a <div> tag for each element in data
    #     # will print: 
    #     #
    #     #   <div>grace hopper</div>
    #     #   <div>alan turing</div>
    #     #   <div>ada lovelace</div>
    #     #
    #     {% for n in data %}
    #     <div>{{n}}</div>
    #     {% endfor %}
    #
    # context = dict(data = names)


    #
    # render_template looks in the templates/ folder for files.
    # for example, the below file reads template/index.html
    #
    return render_template("index.html")

@app.route('/climber_home/<username>')
def climber_home(username):
    try:
        # Fetch quick stats
        stats_query = text("""
            SELECT 
                COUNT(a.attempt_id) AS total_routes,
                ROUND(AVG(a.personal_difficulty_rating)::numeric, 2) AS avg_effort,
                wa.wall_name AS top_wall_area
            FROM attempts a
            JOIN route r ON a.route_id = r.route_id
            JOIN wall_area wa ON r.wall_id = wa.wall_id
            JOIN climber c ON a.climber_id = c.climber_id
            WHERE c.username = :username
            GROUP BY wa.wall_name
            ORDER BY COUNT(a.attempt_id) DESC
            LIMIT 1;
        """)
        result = g.conn.execute(stats_query, {'username': username}).fetchone()

        stats = {
            'total_routes': result[0] if result else 0,
            'avg_effort': result[1] if result else 0,
            'top_wall': result[2] if result else "N/A"
        }

        # Fetch route log (journal-style entries)
        log_query = text("""
            SELECT 
                s.session_date, 
                r.grade, 
                r.color, 
                wa.wall_name, 
                a.result, 
                a.attempt_number
            FROM attempts a
            JOIN session s ON a.session_id = s.session_id
            JOIN route r ON a.route_id = r.route_id
            JOIN wall_area wa ON r.wall_id = wa.wall_id
            JOIN climber c ON a.climber_id = c.climber_id
            WHERE c.username = :username
            ORDER BY s.session_date DESC, a.attempt_id DESC;
        """)
        log_cursor = g.conn.execute(log_query, {'username': username})
        log_rows = log_cursor.fetchall()
        log_cursor.close()

        sessions_query = text("""
            SELECT s.session_id, s.session_date, s.start_time, s.end_time
            FROM session s
            JOIN climber c ON s.climber_id = c.climber_id
            WHERE c.username = :username
            ORDER BY s.session_date DESC;
        """)
        sessions = g.conn.execute(sessions_query, {'username': username}).fetchall()

        achievements_query = text("""
            SELECT 
                a.achievement_name,
                a.description
            FROM climber_achievement ca
            JOIN achievement a ON ca.achievement_id = a.achievement_id
            JOIN climber c ON ca.climber_id = c.climber_id
            WHERE c.username = :username
            ORDER BY ca.date_awarded DESC;
        """)
        achievements = g.conn.execute(achievements_query, {'username': username}).fetchall()

        # Pass both stats + logs to template
        return render_template(
            'climber_home.html',
            username=username,
            stats=stats,
            log_rows=log_rows,
            sessions=sessions,
            achievements=achievements
        )

    except Exception as e:
        return f"Error loading climber dashboard: {e}"


@app.route('/sessions/<username>')
def sessions(username):
    """Shows all sessions for this climber as buttons."""
    sessions_query = text("""
        SELECT s.session_id, s.session_date, s.start_time, s.end_time
        FROM session s
        JOIN climber c ON s.climber_id = c.climber_id
        WHERE c.username = :username
        ORDER BY s.session_date DESC;
    """)
    rows = g.conn.execute(sessions_query, {'username': username}).fetchall()
    return render_template('sessions.html', username=username, sessions=rows)


@app.route('/session/<int:session_id>', methods=['GET', 'POST'])
def session_detail(session_id):
    """Shows all attempts for one session."""
    if request.method == 'POST':
        note = request.form['note']
        g.conn.execute(text("UPDATE session SET notes = :note WHERE session_id = :id"),
                       {'note': note, 'id': session_id})
        g.conn.commit()

    # attempts within this session
    attempts_query = text("""
        SELECT a.attempt_id, a.result, a.attempt_number,
               r.color, r.grade, wa.wall_name, s.session_date, s.start_time, s.end_time
        FROM attempts a
        JOIN route r ON a.route_id = r.route_id
        JOIN wall_area wa ON r.wall_id = wa.wall_id
        JOIN session s ON a.session_id = s.session_id
        WHERE a.session_id = :id
        ORDER BY a.attempt_id;
    """)
    attempts = g.conn.execute(attempts_query, {'id': session_id}).fetchall()

    # session stats
    stats_query = text("""
        SELECT 
            COUNT(*) AS total_climbs,
            SUM(CASE WHEN result = 'Sent' THEN 1 ELSE 0 END) AS total_sends,
            EXTRACT(EPOCH FROM (end_time - start_time)) / 60 AS duration_min
        FROM session
        JOIN attempts a ON session.session_id = a.session_id
        WHERE session.session_id = :id
        GROUP BY session.session_id;
    """)
    stats = g.conn.execute(stats_query, {'id': session_id}).fetchone()

    return render_template('session_detail.html',
                           attempts=attempts,
                           stats=stats,
                           session_id=session_id)


@app.route('/summaries/<username>')
def summaries(username):
    # read both ?period= and ?groupby= from URL
    period = request.args.get('period', 'all')
    groupby = request.args.get('groupby', 'wall')

    # date filters
    filters = {
        'day': "s.session_date >= CURRENT_DATE - INTERVAL '1 day'",
        'week': "s.session_date >= CURRENT_DATE - INTERVAL '7 days'",
        'month': "s.session_date >= CURRENT_DATE - INTERVAL '30 days'",
        'year': "s.session_date >= CURRENT_DATE - INTERVAL '365 days'",
        'all': "TRUE"
    }

    # dynamic grouping logic
    if groupby == 'type':
        select_field = "t.type_name"
        join_clause = "JOIN route_type rt ON r.route_id = rt.route_id JOIN type t ON rt.type_id = t.type_id"
    else:  # default = wall
        select_field = "wa.wall_name"
        join_clause = "JOIN wall_area wa ON r.wall_id = wa.wall_id"

    query = text(f"""
        SELECT 
            {select_field} AS category,
            COUNT(a.attempt_id) AS total_attempts,
            SUM(CASE WHEN a.result = 'Sent' THEN 1 ELSE 0 END) AS total_sends
        FROM attempts a
        JOIN session s ON a.session_id = s.session_id
        JOIN route r ON a.route_id = r.route_id
        {join_clause}
        JOIN climber c ON a.climber_id = c.climber_id
        WHERE c.username = :username AND {filters[period]}
        GROUP BY category
        ORDER BY category;
    """)

    cursor = g.conn.execute(query, {'username': username})
    rows = cursor.fetchall()
    cursor.close()

    return render_template("summaries.html", rows=rows, username=username,
                           period=period, groupby=groupby)

#
# This is an example of a different path.  You can see it at:
# 
#     localhost:8111/another
#
# Notice that the function name is another() rather than index()
# The functions for each app.route need to have different names
#
@app.route('/another')
def another():
    return render_template("another.html")


# Example of adding new data to the database
@app.route('/add', methods=['POST'])
def add():
    # accessing form inputs from user
    name = request.form['name']
    
    # passing params in for each variable into query
    params = {}
    params["new_name"] = name
    g.conn.execute(text('INSERT INTO test(name) VALUES (:new_name)'), params)
    g.conn.commit()
    return redirect('/')


@app.route('/login')
def login():
    abort(401)
    # Your IDE may highlight this as a problem - because no such function exists (intentionally).
    # This code is never executed because of abort().
    this_is_never_executed()


@app.route("/climbers")
def climbers():
    cursor = g.conn.execute(text("SELECT * FROM Climber LIMIT 50;"))
    rows = cursor.fetchall()
    cursor.close()
    return render_template("climbers.html", rows=rows)

if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8111, type=int)
    def run(debug, threaded, host, port):
        """
        This function handles command line parameters.
        Run the server using:

            python server.py

        Show the help text using:

            python server.py --help

        """

        HOST, PORT = host, port
        print("running on %s:%d" % (HOST, PORT))
        app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)

run()
