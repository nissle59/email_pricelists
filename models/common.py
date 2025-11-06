from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import mapped_column, Mapped

from utils.db import Base


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setting: Mapped[str] = mapped_column(String, unique=True)
    value: Mapped[str | None] = mapped_column(String)