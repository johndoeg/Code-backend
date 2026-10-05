from app import create_app
from waitress import serve

import logging
import os

if __name__ == '__main__':
    app = create_app()
    env = os.environ["FLASK_ENV"]

    if env == "development":
        logging.basicConfig(level=logging.DEBUG)
        app.run(host='0.0.0.0', port=5000, debug=True, threaded=True, use_reloader=False)
    else:
        logging.basicConfig(level=logging.INFO)
        print("Starting production server on http://0.0.0.0:5000")
        serve(app, host='0.0.0.0', port=5000, threads=8)