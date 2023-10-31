import contextlib
import importlib.resources
import uuid
import ipaddress
import datetime

import fastapi
import sqlmodel


app = fastapi.FastAPI()

@app.get('/stations')
async def get_stations():
    return None                 # FIXME


@app.get('/stations/{station_name}/programmes')
async def get_programmes(station_name: str):
    """ Get all programmes in all channels of some station, as a big flat list, ready for CSS3 grid layout. """
    return None                 # FIXME


class Station(sqlmodel.SQLModel, table=True):
    frequency: int = sqlmodel.Field(primary_key=True)
    # NOTE: "x: str" is TEXT NOT NULL.
    #       "x: typing.Optional[str]" is "TEXT" (nullable=True).
    name: str
    host: ipaddress.IPv4Interface
    when: datetime.datetime
    what: uuid.UUID


# NOTE: create_engine(⋯, echo=True) is like "set -x" in bash, it's for debugging.
engine = sqlmodel.create_engine("sqlite://", echo=True)

## THIS IS A GOOD THING AND I APPROVE.
# https://sqlmodel.tiangolo.com/tutorial/one/#exactly-one


def main():
    sqlmodel.SQLModel.metadata.create_all(engine)
    abc = Station(frequency=226_500_000, name='ABC', host='255.255.255.255', when=datetime.datetime.now(), what=uuid.uuid4())
    with sqlmodel.Session(engine) as session:
        session.add(abc)
        session.commit()
        query = (
            sqlmodel.select(Station)
            .where(Station.name == 'ABC'))
        print(query)
        for row in session.exec(query):
            print(row)
