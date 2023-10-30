import fastapi
import psycopg2
import psycopg2.extras

app = fastapi.FastAPI()


@app.get('/')
async def root():
    return {'message': 'Hello, World!'}


@app.get('/station')
async def get_station():
    with (psycopg2.connect(dbname='epg') as conn,
          conn,                 # transaction w/ rollback support
          conn.cursor(
              cursor_factory=psycopg2.extras.NamedTupleCursor) as cur):
        cur.execute('SELECT * FROM stations')
        return cur.fetchall()
