import contextlib
import datetime
import importlib.resources
import ipaddress
import pathlib
import subprocess
import typing
import uuid as FUCK_uuid        # workaround weird import errors

import fastapi
import sqlmodel
import sqlalchemy.types

# NOTE: create_engine(⋯, echo=True) is like "set -x" in bash, it's for debugging.
engine = sqlmodel.create_engine("sqlite:///test.db", echo=True)

app = fastapi.FastAPI()


class Station(sqlmodel.SQLModel, table=True):
    frequency: int = sqlmodel.Field(primary_key=True)
    name: str
    host: ipaddress.IPv4Interface


class Channel(sqlmodel.SQLModel, table=True):
    sid: int = sqlmodel.Field(primary_key=True)
    name: str
    frequency: int = sqlmodel.Field(foreign_key='station.frequency')
    vpid: typing.Optional[int]  # not used anymore
    apid: typing.Optional[int]  # not used anymore
    enabled: bool


class ChannelCurfew(sqlmodel.SQLModel, table=True):
    # By default class FooBar becomes
    # CREATE TABLE foobar, but we want
    # CREATE TABLE foo_bar.
    __tablename__ = 'channel_curfew'
    # NOTE: If the SQL was
    #          CREATE TABLE xs(x INTEGER,
    #                          y INTEGER,
    #                          z INTEGER NOT NULL,
    #                          PRIMARY KEY (x, y))
    #       then that would just be
    #          x: int = Field(primary_key=True)
    #          y: int = Field(primary_key=True)
    #          z: int
    sid: int = sqlmodel.Field(primary_key=True)
    curfew_stop_time: datetime.time = sqlmodel.Field(primary_key=True)
    curfew_start_time: datetime.time = sqlmodel.Field(primary_key=True)


class CupsJob(sqlmodel.SQLModel, table=True):
    __tablename__ = 'cups_job'  # FooBar → foo_bar (not foobar)
    uuid: FUCK_uuid.UUID = sqlmodel.Field(primary_key=True)
    # FIXME: how do I enforce that this is "WITH TIME ZONE"?
    #        https://pypi.org/project/SQLAlchemy-Utc/
    #        https://docs.sqlalchemy.org/en/13/core/type_basics.html#sqlalchemy.types.DateTime
    # FIXME: alternatively, for sqlite3 demos,
    #        how do I make it use efficient julianday() integers,
    #        instead of RFC 3339 strings?
    ts: datetime.datetime = sqlmodel.Field(
        sa_column=sqlalchemy.Column(sqlalchemy.types.DATETIME(timezone=True),
                                    nullable=False))
    queue: str
    jobid: int
    username: str
    title: str
    copies: int
    # NOTE: sqlmodel doesn't know about JSON by default, so
    #       we have to set BOTH the python and sql datatypes.
    #       https://stackoverflow.com/questions/70567929/how-to-use-json-columns-with-sqlmodel
    # FIXME: doing this moves this column to the front of the CREATE TABLE list.
    #        This causes the database to pack it inefficiently.
    #        https://www.2ndquadrant.com/en/blog/on-rocks-and-sand/
    #           if you simply reorder the columns in CREATE TABLE,
    #           you can save ~20% of the space & get faster queries
    #        It also completely fucks up the sloppy_slurp.py stuff,
    #        which assumes the column order has not changed.
    options: dict[str, typing.Any] = sqlmodel.Field(
        sa_column=sqlalchemy.Column(sqlalchemy.types.JSON,
                                    nullable=False))
    pages: int
    path: pathlib.Path


@app.on_event("startup")
def on_startup():
    sqlmodel.SQLModel.metadata.create_all(engine)
    # Import all the existing rows from the old database,
    # doing some fuzzy massaging along the way.
    proc = subprocess.run(
        ['ssh', 'tweak', 'sudo -u postgres python3'],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        input=importlib.resources.read_text('myapp_d12_sqlite', 'sloppy_slurp.py'))
    with session() as sess:
        # During this batch insert, tables are out of order, so FK enforcement must be off.
        sess.exec('PRAGMA foreign_keys = OFF')
        for line in proc.stdout.splitlines():
            if line.startswith('INSERT INTO '):
                sess.exec(line)
        sess.commit()


@contextlib.contextmanager
def session():
    with sqlmodel.Session(engine) as sess:
        # MUST happen at least once (ever).
        sess.exec('PRAGMA journal_mode = WAL')
        # MUST happen in every sesssion.
        # https://docs.sqlalchemy.org/en/13/dialects/sqlite.html#foreign-key-support
        sess.exec('PRAGMA foreign_keys = ON')
        yield sess
