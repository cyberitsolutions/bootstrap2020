-- This is morally equivalent to
--
--        SELECT name FROM stations
--
-- ...except it sorts stations by ascending service ID (sid).

SELECT stations.name AS station_name
    FROM stations
    JOIN channels USING (frequency)
    WHERE channels.enabled
    GROUP BY stations.frequency
    ORDER BY min(channels.sid);
