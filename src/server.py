import tensorflow as tf
from model_generation.suggester import Suggester
from flask import Flask, send_file
app = Flask(__name__)


@app.before_first_request
def load_model():
    # Load the model for speed in subsequent calls.
    app.suggester = Suggester()


@app.route("/api/suggestions/<username>")
def suggestions(username):
    return app.suggester.get_estimates_for_user(username)


@app.route("/")
def landing():
    return send_file('static/index.html')


if __name__ == '__main__':
    app.run(threaded=False)