import contextlib

import fastapi
import psycopg2
import psycopg2.extras

app = fastapi.FastAPI()


@app.get('/stations')
async def get_stations():
    return get_all(
        'SELECT * FROM stations')


@app.get('/stations/{frequency}')
async def get_station(frequency: int):
    return get_one(
        'SELECT * FROM stations WHERE frequency = %(frequency)s',
        {'frequency': frequency})


@app.get('/stations/{frequency}/channels')
async def get_channels(frequency: str):
    return get_all(
        'SELECT * FROM channels WHERE frequency = %(frequency)s',
        {'frequency': frequency})


@app.get('/stations/{frequency}/channels/{service_ID}')
async def get_channel(frequency: str, service_ID: str):
    return get_one(
        'SELECT * FROM channels WHERE frequency = %(frequency)s AND sid = %(service_ID)s',
        {'frequency': frequency,
         'service_ID': service_ID})


@app.get('/stations/{frequency}/channels/{service_ID}/programmes')
async def get_programmes(frequency: str, service_ID: str):
    return get_all(
        'SELECT programmes.* FROM programmes JOIN channels USING (sid) WHERE channels.frequency = %(frequency)s AND channels.sid = %(service_ID)s',
        {'frequency': frequency,
         'service_ID': service_ID})


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


def get_one(*args, **kwargs):
    with cursor() as cur:
        cur.execute(*args, **kwargs)
        assert cur.rowcount in {0, 1}
        if not cur.rowcount:
            raise fastapi.HTTPException(status_code=404)
        return cur.fetchone()
