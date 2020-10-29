from flask import Flask, render_template
import argparse
import requests

app = Flask(__name__)
arguments = None


def get_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nvr-token", help="NVR api token", required=True)
    parser.add_argument("-p", "--port", help="Server port", default=443)
    parser.add_argument("--ssl-key", help="Path to ssl key")
    parser.add_argument("--ssl-cert", help="Path to ssl certificate")
    return parser.parse_args()


@app.route("/")
def home():
    headers = {"key": arguments.nvr_token}
    response = requests.get('https://nvr.miem.hse.ru/api/sources/',
                            headers=headers)
    cams = response.json()
    cams.append({'id': 'test','name': 'test'})
    return render_template("index.html", cams=cams)


if __name__ == "__main__":
    arguments = get_arguments()
    ssl_context = (arguments.ssl_cert, arguments.ssl_key)
    app.run(host='0.0.0.0', port=arguments.port, ssl_context=ssl_context)