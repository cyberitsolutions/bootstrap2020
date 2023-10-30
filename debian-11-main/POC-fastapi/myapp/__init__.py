import contextlib
import importlib.resources

import fastapi
import psycopg2
import psycopg2.extras

app = fastapi.FastAPI()

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
