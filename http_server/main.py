from flask import Flask, render_template
import requests
import json
import os

app = Flask(__name__)
NVR_TOKEN = os.environ.get('NVR_TOKEN')
if not NVR_TOKEN:
    raise NameError('Environment variable $NVR_TOKEN not found')


@app.route("/")
def home():
    headers = {"key": NVR_TOKEN}
    response = requests.get('https://nvr.miem.hse.ru/api/sources/',
                            headers=headers)
    cams = response.json()
    return render_template("index.html", cams=cams)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80)