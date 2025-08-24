from flask import Flask

app = Flask(__name__)
app.secret_key = 'twoj_tajny_klucz'

import routes

if __name__ == "__main__":
    app.run(debug=True)
