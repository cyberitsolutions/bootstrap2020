SELECT to_char(date, 'yyyy"Q"q') AS quarter,
       justify_interval(sum(duration)) AS "Duration (3 months, all detainees, all apps)"
FROM popcon
WHERE 't'
  -- Skip some deeply boring popup windows
  -- FIXME: this is not showing webmail properly.  Fix query and re-crunch when we care abuot webmail.
  AND (application NOT LIKE 'Internet > Web Browser (%' AND application NOT LIKE '%webmail%')
  AND application NOT LIKE 'Graphics > Photo Editor (%'
  -- consider 'p123' but not 'intel.analyst'.  Not perfect, but close enough.
  AND username ~ '^p[0-9]+$'
GROUP BY quarter
ORDER BY quarter;
