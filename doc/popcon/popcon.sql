-- Usage: ssh tweak.prisonpc.com sudo psql prisonpc --csv < popcon.sql | sed 's/$/\r/' >popcon_X_to_Y.csv
SELECT (EXTRACT (EPOCH FROM sum(duration)) / EXTRACT (EPOCH FROM (sum(sum(duration)) OVER ())) * 10000)::INT AS "Rank",
       application AS "Application",
       justify_interval(sum(duration)) AS "Duration (6 months, all detainees)"
FROM popcon
-- WHERE date BETWEEN '2024-01-01' AND '2024-06-30'
WHERE date BETWEEN now() - INTERVAL '6 months' AND now()
  -- Skip some deeply boring popup windows
  -- FIXME: this is not showing webmail properly.  Fix query and re-crunch when we care abuot webmail.
  AND (application NOT LIKE 'Internet > Web Browser (%' AND application NOT LIKE '%webmail%')
  AND application NOT LIKE 'Graphics > Photo Editor (%'
  -- consider 'p123' but not 'intel.analyst'.  Not perfect, but close enough.
  AND username ~ '^p[0-9]+$'
GROUP BY application
ORDER BY sum(duration) DESC
LIMIT 1000
