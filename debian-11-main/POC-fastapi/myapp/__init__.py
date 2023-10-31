import contextlib
import importlib.resources

import fastapi
import psycopg2
import psycopg2.extras
import sqlalchemy
import sqlalchemy.ext.declarative
import sqlalchemy.orm
import sqlalchemy.dialects.postgresql


app = fastapi.FastAPI()

## PsycoPG2 version ########################################

_stations_query = importlib.resources.read_text('myapp', 'stations.sql')
_programmes_query = importlib.resources.read_text('myapp', 'programmes.sql')


@app.get('/stations')
async def get_stations():
    return get_all(_stations_query)


@app.get('/stations/{station_name}/programmes')
async def get_programmes(station_name: str):
    """ Get all programmes in all channels of some station, as a big flat list, ready for CSS3 grid layout. """
    return get_all(_programmes_query, {'station_name': station_name})


@contextlib.contextmanager
def cursor():
    with (psycopg2.connect(dbname='epg') as conn,
          conn,                 # transaction w/ rollback support
          conn.cursor(
              cursor_factory=psycopg2.extras.NamedTupleCursor) as cur):
        yield cur


def get_all(*args, **kwargs):
    with cursor() as cur:
        cur.execute(*args, **kwargs)
        return cur.fetchall()

## SQLAlchemy ORM version ##################################

# "SessionLocal" is a class, and each instance of it is a database connection?
# "Base" is the ORM class from which all table classes inherit.
engine = sqlalchemy.create_engine('postgresql://epg')
SessionLocal = sqlalchemy.orm.sessionmaker(
    autocommit=False,           # FIXME: why?
    autoflush=False,            # FIXME: why?
    bind=engine)                # FIXME: why?
Base = sqlalchemy.ext.declarative.declarative_base()

# FIXME: how do we define all the plpgsql in-database functions?

class Station(Base):
    __tablename__ = 'stations'
    frequency = sqlalchemy.Column(
        sqlalchemy.Integer,
        primary_key=True,
        autoincrement=False,    # FUCK OFF
        index=True)             # FIXME: why?
    name = sqlalchemy.Column(
        sqlalchemy.Text,
        nullable=False)
    host = sqlalchemy.Column(
        # https://docs.sqlalchemy.org/en/13/core/type_basics.html#vendor-specific-types
        sqlalchemy.dialects.postgresql.INET,
        nullable=False)
