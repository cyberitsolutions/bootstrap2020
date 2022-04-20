COPY (                          -- "psql --csv" is not available until pg 12.

    SELECT (EXTRACT (EPOCH FROM sum(duration)) / EXTRACT (EPOCH FROM (sum(sum(duration)) OVER ())) * 10000)::INT AS score,
           application,
           justify_interval(sum(duration)) AS pretty_duration
    FROM popcon
    -- WHERE date BETWEEN '2021-07-01' AND '2021-12-31'
    WHERE date BETWEEN now() - INTERVAL '6 months' AND now()
      -- Skip some deeply boring popup windows
      -- FIXME: this is not showing webmail properly.  Fix query and re-crunch when we care abuot webmail.
      AND (application NOT LIKE 'Internet > Web Browser (%' AND application NOT LIKE '%webmail%')
      AND application NOT LIKE 'Graphics > Photo Editor (%'
      -- consider 'p123' but not 'intel.analyst'.  Not perfect, but close enough.
      AND username LIKE 'p%'
    GROUP BY application
    ORDER BY sum(duration) DESC
    LIMIT 1000

     ) TO STDOUT CSV;
