import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

from helpers.models import meta


# Connect to the database.
from helpers.seed_database import seed_default


def create_database_engine():
    print('Creating ORM engine.')
    engine = create_engine(f"postgresql://"
                           f"{os.getenv('POSTGRES_USER')}:"
                           f"{os.getenv('POSTGRES_PASSWORD')}@localhost:5432/"
                           f"{os.getenv('POSTGRES_DB')}")
    print('Creating ORM engine finished.')
    return engine


# Create ORM models.
def create_models(engine):
    print('Creating ORM modules.')
    meta.create_all(engine)
    print('Finished creating ORM modules.')


# Project setup.
def setup():
    print('Starting application setup.')
    load_dotenv()
    engine = create_database_engine()
    create_models(engine)
    seed_default(engine)
    print('Finished application setup.')


if __name__ == '__main__':
    print('Application started.')
    setup()
