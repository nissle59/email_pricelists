from datetime import datetime

from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship, mapped_column, Mapped

from utils.db import Base


class Letter(Base):
    __tablename__ = 'letters'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    letter_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    vendor_id: Mapped[int] = mapped_column(Integer, ForeignKey('vendors.id'), index=True)
    sender: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    date: Mapped[datetime] = mapped_column(DateTime)

    attachments: Mapped[list["Attachment"]] = relationship(back_populates="letter", cascade="all, delete-orphan")
    vendor: Mapped["Vendor"] = relationship(back_populates="letters")


class Attachment(Base):
    __tablename__ = 'attachments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    letter_id: Mapped[int] = mapped_column(Integer, ForeignKey('letters.letter_id'), index=True)
    file_name: Mapped[str] = mapped_column(String)
    file_path: Mapped[str] = mapped_column(String)
    content_type: Mapped[str | None] = mapped_column(String)
    size: Mapped[int] = mapped_column(Integer)

    letter: Mapped["Letter"] = relationship(back_populates="attachments")
