from app import create_app
import logging

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)