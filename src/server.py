from model_generation.suggestor import Suggestor
from flask import Flask, send_file
app = Flask(__name__)

suggestor = Suggestor()

@app.route("/api/suggestions/<username>")
def suggestions(username):
    return suggestor.get_estimates_for_user(username)

@app.route("/")
def landing():
    import os
    return send_file('static/index.html')


if __name__ == '__main__':
    app.run(threaded=False)