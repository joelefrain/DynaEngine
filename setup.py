from libs.helpers.db_helpers import (
    create_database,
    create_directories,
)


def main():
    # Crear la base de datos
    create_directories()
    create_database()


if __name__ == "__main__":
    main()
