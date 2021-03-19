from flask import Flask, request, render_template, redirect, make_response, url_for
from functools import wraps
import os
from psql.psql_funcs import Psql
from heroku_redis.redis_funcs import Redis
from security.jwt_check import JWT
from mail.smtp import Mail
from security.password_check import PassChek
from log.logger import Logger

if __name__ == '__main__':
    import set_env_values

psql = Psql(os.getenv('DATABASE_URL'))
redis = Redis(os.getenv('REDIS_URL'))
jwt = JWT(os.getenv('JWT_KEY'),
          os.getenv('JWT_ALGORITHM'))
mail = Mail(os.getenv('EMAIL_USER'),
            os.getenv('EMAIL_USER_PASSWORD'),
            os.getenv('SMTP'),
            os.getenv('SMTP_PORT'))
pchek = PassChek(os.getenv('HASH_METHOD'))

app = Flask(__name__)


@app.errorhandler(404)
def page_not_found(e):
    return redirect(url_for('home'))


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


def login_redirect(return_to: str = '/home'):
    flask_resp = make_response(redirect(f"/login?return_to={return_to}"))
    flask_resp.set_cookie('session_token', expires=0)
    return flask_resp


def generate_ttl(time_period: str) -> int:
    if not time_period:
        return 1800
    if time_period == '1 hour':
        return 3600
    if time_period == '1 day':
        return 86400
    if time_period == '3 days':
        return 259200
    if time_period == '1 week':
        return 604800


def jwt_check(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if 'session_token' in request.cookies:
            jwt_resp = jwt.check_token(request.cookies['session_token'])
            if jwt_resp:
                decoded_token = jwt.decode_token(request.cookies['session_token'])
                redis_resp = redis.check_token(decoded_token['decoded_token'],
                                               request.cookies['session_token'])
                if redis_resp:
                    return function(*args, **kwargs)
                else:
                    return login_redirect(request.url_rule)
            else:
                return login_redirect(request.url_rule)
        else:
            return login_redirect(request.url_rule)
    return wrapper


@app.route('/registration', methods=['POST', 'GET'])
def registration():
    if request.method == 'POST':
        return render_template('registration_link_was_sent.html', user_email=request.form.get('email'))
    else:
        if 'from' in request.values and request.values['from'] == 'login':
            return render_template('registration.html', redirect_from_login=True)
        else:
            return render_template('registration.html')


@app.route('/forgot_password', methods=['POST', 'GET'])
def forgot_password():
    if request.method == 'POST':
        pass
    else:
        return render_template('forgot_password.html')


@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        if 'password' in request.form and 'email' in request.form:
            psql_resp = psql.get_user_by_email(request.form['email'])
            if psql_resp['result']:
                user = psql_resp['user']
                pass_check_resp = pchek.check_password_hash(user.password, request.form['password'])
                if pass_check_resp:
                    flask_resp = make_response(redirect(f"{request.form.get('return_to')}"))
                    flask_resp.set_cookie('session_token',
                                          jwt.create_token(user.user_id, generate_ttl(request.form.get('time_period'))))
                    return flask_resp
                if not pass_check_resp:
                    return render_template('login.html', data='blocked')
            if not psql_resp['result']:
                return redirect('/registration?from=login')
    if request.method == 'GET':
        if 'return_to' in request.args:
            return render_template('login.html', return_to=request.args['return_to'])
        if 'session_token' in request.cookies and jwt.check_token(request.cookies['session_token']):
            return redirect('/home')

    return render_template('login.html', return_to='home')


@app.route('/logout', methods=['POST'])
@jwt_check
def logout():
    decoded_jwt = jwt.decode_token(request.cookies['session_token'])['decoded_token']
    redis.add_bad_token(decoded_jwt, request.cookies['session_token'])
    return login_redirect()


@app.route('/home', methods=['GET', 'POST'])
@jwt_check
def home():
    decoded_jwt = jwt.decode_token(request.cookies['session_token'])
    return render_template('home.html', user_notes=psql.find_notes(decoded_jwt['decoded_token']['user_id']))


@app.route('/profile', methods=['GET', 'POST'])
@jwt_check
def profile():
    decoded_jwt = jwt.decode_token(request.cookies['session_token'])['decoded_token']
    user = psql.get_user_by_id(decoded_jwt['user_id'])
    user_role = psql.get_role_by_id(user.role_id)
    return render_template('profile.html', user=user, user_role=user_role)


@app.route('/update_password', methods=['POST'])
@jwt_check
def update_password():
    decoded_jwt = jwt.decode_token(request.cookies['session_token'])['decoded_token']
    user = psql.get_user_by_id(decoded_jwt['user_id'])

    return 'jbkb'


@app.route('/create_note', methods=['GET', 'POST'])
@jwt_check
def create_note():
    decoded_jwt = jwt.decode_token(request.cookies['session_token'])['decoded_token']
    user = psql.get_user_by_id(decoded_jwt['user_id'])
    user_role = psql.get_role_by_id(user.role_id)
    return render_template('profile.html', user=user, user_role=user_role)


if __name__ == '__main__':
    app.run(debug=True)
