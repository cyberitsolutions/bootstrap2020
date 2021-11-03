ssh bootstrap2020 dpkg-query -W >dpkg-query-W
ssh bootstrap2020 du -haxt64M /run/live/medium >du-haxt64M
ssh bootstrap2020 busybox ps -ouser,comm >ps
ssh bootstrap2020 systemctl status >systemctl-status-before-login
echo now log in
read _
ssh bootstrap2020 systemctl status >systemctl-status-after-login
echo now log out
read _
ssh bootstrap2020 systemctl status >systemctl-status-after-logout
