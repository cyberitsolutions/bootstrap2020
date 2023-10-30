SELECT c.name AS channel_name,
       p.title AS programme_name,
       p.sub_title AS programme_description,
       date_trunc('minute', p.start)::TIME AS start_time,
       p.stop - p.start AS duration,
       timestamp_to_epg_grid_row(p.start, date_trunc('hour', now())) AS grid_row_start,
       timestamp_to_epg_grid_row(p.stop,  date_trunc('hour', now())) AS grid_row_end,
       -- The grid column number is logically just the sid.
       -- Chromium limits us to columns 1 through 1000 (dense_rank counts from 1, too).
       -- SIDs can be >1000, so assign each SID a consistent, synthetic column ID.
       -- Ref. https://www.postgresql.org/docs/current/static/tutorial-window.html
       -- Ref. https://www.postgresql.org/docs/currentstatic/functions-window.html
       dense_rank() OVER (ORDER BY sid) AS grid_column,
       coalesce(st.status, 'A') AS programme_status,
       p.crid_series,
       'rtp://' || host('239.255.0.0'::inet + c.sid) || ':1234' AS channel_url
FROM programmes p
LEFT JOIN statuses st USING (crid_series)
JOIN channels c USING (sid)
JOIN stations s USING (frequency)
WHERE s.name = %(station_name)s
  AND c.enabled
  -- Adding 5min to the overlap window is a "fudge".
  -- It means that programmes that are ABOUT TO END are not shown.
  -- This means you might get a small gap at the top of the EPG.
  -- The alternative is two programmes (effectively) overlapping.
  AND (start, stop) OVERLAPS (date_trunc('hour', now()) + '5 min'::INTERVAL,
                              date_trunc('hour', now()) + '1 day'::INTERVAL)
  -- NOTE: programmes ≤2min long don't render properly
  --       (see grid_row_start comments above).
  -- FIXME: as a workaround, just hide these programmes COMPLETELY.
  --        This means staff can't record or block them!!
  AND stop - start > '2 min'::INTERVAL
-- NOTE: the order is not important for grid layout, but
-- it *IS* important for zebra striping — :nth-child(even).
-- The ordering specified here is effectively column, then row.
ORDER BY sid, start;
