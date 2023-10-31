# FIXME: BROKEN: import ipaddress
# FIXME: BROKEN: import pathlib
import contextlib
import datetime
import importlib.resources
import logging
import pickle
import subprocess
import typing
import uuid as FUCK_uuid        # workaround weird import errors

import fastapi
import sqlmodel
import sqlalchemy.types

# NOTE: create_engine(⋯, echo=True) is like "set -x" in bash, it's for debugging.
engine = sqlmodel.create_engine("sqlite:///test.db",
                                # echo=True,
                                )

app = fastapi.FastAPI()


def JSON_workaround(nullable=False, *args, **kwargs):
    """
    NOTE: sqlmodel doesn't know about JSON by default, so
          we have to set BOTH the python and sql datatypes.
          https://stackoverflow.com/questions/70567929/how-to-use-json-columns-with-sqlmodel
    FIXME: manual sa_column= moves the column to the front of the CREATE TABLE list.
           1. This causes the database to pack it inefficiently.
              https://www.2ndquadrant.com/en/blog/on-rocks-and-sand/
                 if you simply reorder the columns in CREATE TABLE,
                 you can save ~20% of the space & get faster queries
           2. It also completely fucks up the sloppy_slurp.py stuff,
              which assumes the column order has not changed.
    """
    return sqlmodel.Field(
        *args,
        **kwargs,
        sa_column=sqlalchemy.Column(
            sqlalchemy.types.JSON,
            nullable=False))


def TIMESTAMPTZ_workaround(nullable=False, *args, **kwargs):
    """FUCK YOU: workaround sqlmodel not caring about UTC vs localtime."""
    return sqlmodel.Field(
        *args,
        **kwargs,
        sa_column=sqlalchemy.Column(
            sqlalchemy.types.DATETIME(timezone=True),
            nullable=nullable))


# dbname='tca' #############################################

class SOE(sqlmodel.SQLModel, table=True):
    name: str = sqlmodel.Field(primary_key=True)


class Realm(sqlmodel.SQLModel, table=True):
    name: str = sqlmodel.Field(primary_key=True)
    soe_name: str = sqlmodel.Field(foreign_key='soe.name')
    cidr: str          # FIXME: ipaddress.IPv4Network, & CIDR in pg...
    enabled: bool
    staff: bool
    boot_curfew: typing.Optional[str]
    iptv_curfew: typing.Optional[str]
    web_curfew: typing.Optional[str]
    print_curfew: typing.Optional[str]


class Host(sqlmodel.SQLModel, table=True):
    name: str = sqlmodel.Field(primary_key=True)
    realm_name: str = sqlmodel.Field(foreign_key='realm.name')
    mac: str = sqlmodel.Field(unique=True)  # FIXME: wrong datatype
    ip: int          # FIXME: ipaddress.IPv4Interface, & INET in pg...
    user_group: typing.Optional[str]
    enabled: bool
    last_uid: typing.Optional[str]
    last_ping: typing.Optional[datetime.datetime] = TIMESTAMPTZ_workaround(nullable=True)
    last_boot: typing.Optional[datetime.datetime] = TIMESTAMPTZ_workaround(nullable=True)
    __table_args__ = (
        # You cannot have two hosts with "0.0.0.4/32" in the same realm.
        # This is a stand in for "you can't have two hosts with the same IP address,
        # where the host's IP address is (host.ip + realm.cidr)".
        sqlmodel.UniqueConstraint('realm_name', 'ip'),
    )

# dbname='prisonpc' ########################################


class CupsJob(sqlmodel.SQLModel, table=True):
    __tablename__ = 'cups_job'  # FooBar → foo_bar (not foobar)
    uuid: FUCK_uuid.UUID = sqlmodel.Field(primary_key=True)
    # FIXME: how do I enforce that this is "WITH TIME ZONE"?
    #        https://pypi.org/project/SQLAlchemy-Utc/
    #        https://docs.sqlalchemy.org/en/13/core/type_basics.html#sqlalchemy.types.DateTime
    # FIXME: alternatively, for sqlite3 demos,
    #        how do I make it use efficient julianday() integers,
    #        instead of RFC 3339 strings?
    ts: datetime.datetime = TIMESTAMPTZ_workaround()
    queue: str
    jobid: int
    username: str
    title: str
    copies: int
    options: dict[str, typing.Any] = JSON_workaround()
    pages: int
    # FIXME: sqlite3.ProgrammingError: Error binding parameter 10: type 'PosixPath' is not supported
    #            path: pathlib.Path
    path: str


class MailStat(sqlmodel.SQLModel, table=True):
    date: datetime.date = sqlmodel.Field(primary_key=True)
    pre: int
    held: int
    app: int
    rej: int


class PopCon(sqlmodel.SQLModel, table=True):
    date: datetime.date = sqlmodel.Field(primary_key=True)
    hostname: str = sqlmodel.Field(primary_key=True)
    username: str = sqlmodel.Field(primary_key=True)
    application: str = sqlmodel.Field(primary_key=True)
    duration: datetime.timedelta


class SquidChecksum(sqlmodel.SQLModel, table=True):
    __tablename__ = 'squid_checksum'  # FooBar → foo_bar (not foobar)
    url: str = sqlmodel.Field(primary_key=True)
    checksum: str


class SquidRule(sqlmodel.SQLModel, table=True):
    __tablename__ = 'squid_rule'  # FooBar → foo_bar (not foobar)
    url: str = sqlmodel.Field(primary_key=True)
    group_restriction: str = sqlmodel.Field(primary_key=True)
    title: typing.Optional[str]
    policy: str


class MaxwellPolicy(sqlmodel.SQLModel, table=True):
    __tablename__ = 'maxwell_policy'  # FooBar → foo_bar (not foobar)
    policy: int = sqlmodel.Field(primary_key=True)
    label: str
    meaningful_for_rules: bool
    meaningful_for_overrides: bool


class MaxwellAutoResponse(sqlmodel.SQLModel, table=True):
    __tablename__ = 'maxwell_autoresponse'  # FooBar → foo_bar (not foobar)
    address: str = sqlmodel.Field(primary_key=True)  # FIXME: MUST BE case-folding (CITEXT not TEXT)!
    last_sent: datetime.datetime = TIMESTAMPTZ_workaround()


class MaxwellContentTypeBackendRule(sqlmodel.SQLModel, table=True):
    __tablename__ = 'maxwell_content_type_backend_rule'  # FooBar → foo_bar (not foobar)
    # FIXME: addres MUST BE case-folding (CITEXT not TEXT)!
    content_type: str = sqlmodel.Field(primary_key=True)  # FIXME: MUST BE case-folding (CITEXT not TEXT)!
    policy: int = sqlmodel.Field(foreign_key='maxwell_policy.policy')


class MaxwellOverrideRule(sqlmodel.SQLModel, table=True):
    __tablename__ = 'maxwell_override_rule'  # FooBar → foo_bar (not foobar)
    address: str = sqlmodel.Field(primary_key=True)  # FIXME: MUST BE case-folding (CITEXT not TEXT)!
    policy: int = sqlmodel.Field(foreign_key='maxwell_policy.policy')
    description: str
    ignore: bool


class MaxwellBackendRule(sqlmodel.SQLModel, table=True):
    __tablename__ = 'maxwell_backend_rule'  # FooBar → foo_bar (not foobar)
    address1: str = sqlmodel.Field(primary_key=True)  # FIXME: MUST BE case-folding (CITEXT not TEXT)!
    address2: str = sqlmodel.Field(primary_key=True)  # FIXME: MUST BE case-folding (CITEXT not TEXT)!
    policy: int = sqlmodel.Field(foreign_key='maxwell_policy.policy')
    description: str
    ignore: bool


# dbname='epg' #############################################


class Station(sqlmodel.SQLModel, table=True):
    frequency: int = sqlmodel.Field(primary_key=True)
    name: str
    host: int        # FIXME: ipaddress.IPv4Interface, & INET in pg...


class Channel(sqlmodel.SQLModel, table=True):
    sid: int = sqlmodel.Field(primary_key=True)
    name: str
    frequency: int = sqlmodel.Field(foreign_key='station.frequency')
    vpid: typing.Optional[int]  # not used anymore
    apid: typing.Optional[int]  # not used anymore
    enabled: bool


class Programme(sqlmodel.SQLModel, table=True):
    # FIXME: this table doesn't have ANY primary key in pg...
    rowid: typing.Optional[int] = sqlmodel.Field(default=None, primary_key=True)
    sid: int = sqlmodel.Field(foreign_key='channel.sid')
    channel: typing.Optional[str]  # not used anymore
    start: datetime.datetime = TIMESTAMPTZ_workaround()
    stop: datetime.datetime = TIMESTAMPTZ_workaround()
    title: str
    sub_title: typing.Optional[str]
    crid_series: str
    crid_item: str


class ChannelCurfew(sqlmodel.SQLModel, table=True):
    __tablename__ = 'channel_curfew'  # FooBar → foo_bar (not foobar)
    # NOTE: If the SQL was
    #          CREATE TABLE xs(x INTEGER,
    #                          y INTEGER,
    #                          z INTEGER NOT NULL,
    #                          PRIMARY KEY (x, y))
    #       then that would just be
    #          x: int = Field(primary_key=True)
    #          y: int = Field(primary_key=True)
    #          z: int
    sid: int = sqlmodel.Field(
        primary_key=True,
        foreign_key='channel.sid')
    curfew_stop_time: datetime.time = TIMESTAMPTZ_workaround(
        primary_key=True)
    curfew_start_time: datetime.time = TIMESTAMPTZ_workaround(
        primary_key=True)


class LocalChannel(sqlmodel.SQLModel, table=True):
    __tablename__ = 'local_channel'  # FooBar → foo_bar (not foobar)
    address: int = sqlmodel.Field(primary_key=True)  # FIXME: ipaddress.IPv4Interface, & INET in pg...
    name: str                                      # FIXME: UNIQUE
    host: typing.Optional[int]  # FIXME: ipaddress.IPv4Interface, & INET in pg...


class FailedRecordingEvent(sqlmodel.SQLModel, table=True):
    __tablename__ = 'failed_recording_event'  # FooBar → foo_bar (not foobar)
    # FIXME: NO PRIMARY KEY IN POSTGRES
    failed_at: datetime.datetime = TIMESTAMPTZ_workaround(primary_key=True)
    programme: str = sqlmodel.Field(primary_key=True)


class LocalMedium(sqlmodel.SQLModel, table=True):
    __tablename__ = 'local_medium'  # FooBar → foo_bar (not foobar)
    media_id: FUCK_uuid.UUID = sqlmodel.Field(primary_key=True)
    path: str                   # FIXME: pathlib.Path
    name: str
    # FIXME: "27MHz" not "27mhz"
    duration_27mhz: int         # FIXME: bigint???
    # FIXME: default now()
    created_at: datetime.datetime = TIMESTAMPTZ_workaround()
    # FIXME: default +infinity
    expires_at: datetime.date


class LocalMediumLifetime(sqlmodel.SQLModel, table=True):
    __tablename__ = 'local_media_lifetime'  # FooBar → foo_bar (not foobar)
    lifetime: str = sqlmodel.Field(primary_key=True)
    standard: bool


class LocalProgramme(sqlmodel.SQLModel, table=True):
    __tablename__ = 'local_programme'  # FooBar → foo_bar (not foobar)
    # FIXME: ipaddress.IPv4Interface, & INET in pg...
    address: int = sqlmodel.Field(
        primary_key=True,
        foreign_key='local_channel.address')
    play_order: int = sqlmodel.Field(primary_key=True)
    media_id: FUCK_uuid.UUID = sqlmodel.Field(foreign_key='local_medium.media_id')
    last_played: datetime.datetime = TIMESTAMPTZ_workaround()


class Status(sqlmodel.SQLModel, table=True):
    # NOTE: NOT a foreign key in pg, because when the programmes expire,
    #       the programme should be deleted, but the "block this TV series" should not...
    crid_series: str = sqlmodel.Field(primary_key=True)
    status: str                 # FIXME: enum


############################################################


@app.on_event("startup")
def on_startup() -> None:
    sqlmodel.SQLModel.metadata.create_all(engine)
    # If there's AT LEAST 1 row in 1 table,
    # skip import of legacy data.
    try:
        with session() as sess:
            sess.exec(sqlmodel.select(SOE.name).limit(1)).one()
            logging.warning('Probably full database, so NOT getting rows from tweak.')
            return
    except sqlalchemy.exc.NoResultFound:
        logging.warning('Probably empty database, so getting rows from tweak.')

    # Import all the existing rows from the old database,
    # doing some fuzzy massaging along the way.
    # FIXME: type declaration is broken.
    # legacy_table2class: list[tuple[str, sqlmodel.SQLModel]]
    legacy_table2class = [
        # dbname='tca'
        ('soes', SOE),
        ('realms', Realm),
        ('hosts', Host),
        # dbname='prisonpc'
        ('cups_jobs', CupsJob),
        ('mailstats', MailStat),
        ('popcon', PopCon),
        ('squid_checksums', SquidChecksum),
        ('squid_rules', SquidRule),
        ('maxwell.policies', MaxwellPolicy),
        ('maxwell.autoresponse', MaxwellAutoResponse),
        ('maxwell.content_type_rules_backend', MaxwellContentTypeBackendRule),
        ('maxwell.override_rules', MaxwellOverrideRule),
        ('maxwell.rules_backend', MaxwellBackendRule),
        # dbname='epg'
        ('stations', Station),
        ('channels', Channel),
        ('programmes', Programme),
        ('channel_curfews', ChannelCurfew),
        ('local_channels', LocalChannel),
        ('failed_recording_log', FailedRecordingEvent),
        ('local_media', LocalMedium),
        ('local_media_lifetimes', LocalMediumLifetime),
        ('local_programmes', LocalProgramme),
        ('statuses', Status)]
    proc = subprocess.run(
        ['ssh', 'tweak', 'sudo -u postgres python3'],
        check=True,
        text=False,
        stdout=subprocess.PIPE,
        input=importlib.resources.read_binary('myapp_d12_sqlite', 'sloppy_slurp.py'))
    legacy_data: dict[str, list] = pickle.loads(proc.stdout)
    with session() as sess:
        # NOTE: due to FK constraints, have add these tables in the correct order...
        for legacy_table, klass in legacy_table2class:
            sess.add_all(
                klass(**legacy_row)
                for legacy_row in legacy_data[legacy_table])
            sess.commit()
            # FIXME: if I do
            #             add_all(soes)
            #             add_all(realms)
            #             add_all(hosts)
            #             commit
            #        if crashes with an FK problem????
            #        I think this is because the realms are failing to insert, but
            #        then it is not even telling me, because the hosts fail to insert later on.
            #        So FOR NOW do this instead:
            #             add_all(soes)
            #             commit()
            #             add_all(realms)
            #             commit()
            #             add_all(hosts)
            #             commit()
            #
            # https://stackoverflow.com/questions/19143345/about-refreshing-objects-in-sqlalchemy-session#19144652
            # https://docs.sqlalchemy.org/en/13/orm/session_basics.html#expiring-refreshing
            # https://sqlmodel.tiangolo.com/tutorial/update/#recap


@contextlib.contextmanager
def session():
    with sqlmodel.Session(engine) as sess:
        # MUST happen at least once (ever).
        sess.exec('PRAGMA journal_mode = WAL')
        # MUST happen in every sesssion.
        # https://docs.sqlalchemy.org/en/13/dialects/sqlite.html#foreign-key-support
        sess.exec('PRAGMA foreign_keys = ON')
        yield sess
