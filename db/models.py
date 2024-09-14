import json

import sqlalchemy as sq
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()

class User(Base):
    __tablename__ = 'user'
    id = sq.Column(sq.Integer, primary_key=True)
    cid = sq.Column(sq.BigInteger, unique=True)

class UserWord(Base):
    __tablename__ = 'user_word'
    id = sq.Column(sq.Integer, primary_key=True)
    word = sq.Column(sq.String(length=40))
    translate = sq.Column(sq.String(length=40))
    id_user = sq.Column(sq.Integer, sq.ForeignKey('user.id'), nullable=False)

    user = relationship(User, backref='words')

class Word(Base):
    __tablename__ = 'word'
    id = sq.Column(sq.Integer, primary_key=True)
    word = sq.Column(sq.String(length=40), unique=True)
    translation = sq.Column(sq.String(length=40), unique=True)

    def __str__(self):
        return self.id, self.word, self.translate

def create_tables(engine):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

def insert_word_db(session):
    with open('db/word.json', 'r', encoding='utf-8') as fd:
        data = json.load(fd)
    for record in data:
        session.add(Word(word=record['word'], translation=record['translation']))
    session.commit()

