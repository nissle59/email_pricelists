# db.py
import os

from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, declarative_base

from utils.paths import pm

#ENGINE_URL = "sqlite:///" + os.path.join(os.getcwd(), "emailparser.db")  # можно сменить путь
DB_FILE = os.path.join(pm.get_user_data(), "emailparser.db")
ENGINE_URL = "sqlite:///" + DB_FILE
print(ENGINE_URL)

engine = create_engine(ENGINE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
metadata = MetaData(naming_convention=naming_convention)

Base = declarative_base(metadata=metadata)


def init_db():
    print(ENGINE_URL)
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    init_db()