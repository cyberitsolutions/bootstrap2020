# Pseudocode conversion of existing query to sqlalchemy notation.
timestamp_to_epg_grid_row = sqlalchemy.functions.Function(...)
query = (
    sqlalchemy.select(
        Channel.name.label('channel_name'),
        Programme.title.label('programme_name'),
        Programme.sub_title.label('programme_description'),
        sqlalchemy.func.cast(
            sqlalchemy.func.date_trunc('minute', Programme.start),
            sqlalchemy.type.TIME).label('start_time'),
        (Programme.stop - Programme.start).label('duration'),
        timestamp_to_epg_grid_row(
            Programme.start,
            sqlalchemy.func.date_trunc('minute', sqlalchemy.func.now)).label('grid_row_start'),
        timestamp_to_epg_grid_row(
            Programme.stop,
            sqlalchemy.func.date_trunc('minute', sqlalchemy.func.now)).label('grid_row_stop'),
        # The grid column number is logically just the sid.
        # Chromium limits us to columns 1 through 1000 (dense_rank counts from 1, too).
        # SIDs can be >1000, so assign each SID a consistent, synthetic column ID.
        # Ref. https://www.postgresql.org/docs/current/static/tutorial-window.html
        # Ref. https://www.postgresql.org/docs/currentstatic/functions-window.html
        sqlalchemy.sql.functions.dense_rank().over().order_by(Channel.sid).label('grid_column'),
        sqlalchemy.sql.functions.coalesce(Status.status, 'A').label('programme_status'),
        programme.crid_series,
        sqlalchemy.sql.functions.format(
            'rtp://%s:1234',
            sqlalchemy.sql.functions.host(
                sqlalchemy.dialect.postgresql.INET('239.255.0.0') +
                Channel.sid)).label('channel_url'))
    .select_from(Programme)
    .join(Status, outer=true)
    .join(Channel)
    .join(Station)
    .where(Status.name = ___station_name___)
    .where(Channel.enabled)
    # Adding 5min to the overlap window is a "fudge".
    # It means that programmes that are ABOUT TO END are not shown.
    # This means you might get a small gap at the top of the EPG.
    # The alternative is two programmes (effectively) overlapping.
    .where(
        # FIXME: I cannot see how to do this one in sqlalchemy
        # https://docs.sqlalchemy.org/en/20/core/operators.html
        (start, stop) OVERLAPS (date_trunc('hour', now()) + '5 min'::INTERVAL,
                                date_trunc('hour', now()) + '1 day'::INTERVAL))
    # NOTE: programmes ≤2min long don't render properly
    #       (see grid_row_start comments above).
    # FIXME: as a workaround, just hide these programmes COMPLETELY.
    #        This means staff can't record or block them!!
    .where((Programme.stop - Programme.start) > datetime.timedelta(minutes=2))
    # NOTE: the order is not important for grid layout, but
    # it *IS* important for zebra striping — :nth-child(even).
    # The ordering specified here is effectively column, then row.
    .order_by(Channel.sid, Programme.start))
