from app import xpublish_app
import os

os.environ["XPUBLISH_TILES_LOG_LEVEL"] = "debug"


def main():
    rest = xpublish_app()

    rest.serve(port=9000, log_level="debug")


if __name__ == "__main__":
    main()
