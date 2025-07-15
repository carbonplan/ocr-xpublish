from app import xpublish_app


def main():
    rest = xpublish_app()

    rest.serve()


if __name__ == "__main__":
    main()
