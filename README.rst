fastapi bullshit
====================

1. ``./debian-11-main.py --remove --virtual --local --optimize=speed --backdoor --boot`` to get a VM running the stuff on ssh://root@localhost:2022 and http://localhost:8000 (no HTTPS, but requires JS)
2. Run ``debian-11-main/POC-fastapi/copy-old-data-over.py`` to do "ssh tweak dump | ssh VM restore" pg bullshit.
3. Browse to http://localhost:8000/docs or http://localhost:8000/redocs and fuck around.
4. SSH to ssh://root@localhost:2022 and fuck around.
