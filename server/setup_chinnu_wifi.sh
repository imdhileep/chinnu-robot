#!/bin/bash
# One-time setup (run with sudo): turn the server's Wi-Fi radio into "Chinnu-Hotspot" (internet via the eth0 cable),
# and let the Chinnu app manage speed limits (tc) and the hotspot (nmcli) without a password.
set -e
U=dk; A=/home/dk/chinnu-agent
SSID="Chinnu-Hotspot"
PASS=$(cat $A/chinnu_wifi_pass 2>/dev/null || echo "chinnu$(shuf -i 1000-9999 -n1)$(shuf -i 10-99 -n1)")

echo "== 0. checking the wired link first"
ip -4 addr show eth0 | grep -q "inet 192.168.1." || { echo "eth0 has no LAN address - aborting so the server stays reachable"; exit 1; }

echo "== 1. sudo rules for tc / nmcli / ip (Chinnu app only)"
cat > /etc/sudoers.d/chinnu-wifi <<EOF
$U ALL=(root) NOPASSWD: /usr/sbin/tc, /usr/bin/nmcli, /usr/sbin/ip, /usr/sbin/modprobe ifb
EOF
chmod 440 /etc/sudoers.d/chinnu-wifi; visudo -cf /etc/sudoers.d/chinnu-wifi

echo "== 2. Alexa bridge -> wired address 192.168.1.226"
sed -i 's/"ip_address": "192.168.1.227"/"ip_address": "192.168.1.226"/' $A/fauxmo-config.json
systemctl restart chinnu-alexa || true

echo "== 3. LAN https certificate for the Quest -> also valid for 192.168.1.226"
cd $A && openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -keyout lan_key.pem -out lan_cert.pem \
  -subj "/CN=chinnu.local" -addext "subjectAltName=IP:192.168.1.226,IP:192.168.1.227,IP:10.42.0.1" 2>/dev/null
chown $U:$U lan_key.pem lan_cert.pem; chmod 600 lan_key.pem
systemctl restart chinnu-lan || true

echo "== 4. stop using wlan0 as a Wi-Fi client (eth0 cable carries the server)"
for c in $(nmcli -t -f NAME,TYPE con show | awk -F: '$2=="802-11-wireless"{print $1}'); do
  [ "$c" = "$SSID" ] && continue
  nmcli con modify "$c" connection.autoconnect no || true
  nmcli con down "$c" 2>/dev/null || true
done

echo "== 5. create the hotspot"
nmcli con delete "$SSID" 2>/dev/null || true
nmcli con add type wifi ifname wlan0 con-name "$SSID" autoconnect yes ssid "$SSID" \
  802-11-wireless.mode ap 802-11-wireless.band a 802-11-wireless.channel 36 \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASS" \
  ipv4.method shared ipv4.addresses 10.42.0.1/24 ipv6.method disabled
nmcli con up "$SSID" || {
  echo "5 GHz failed - trying 2.4 GHz"; nmcli con modify "$SSID" 802-11-wireless.band bg 802-11-wireless.channel 6; nmcli con up "$SSID"; }
echo "$PASS" > $A/chinnu_wifi_pass; chown $U:$U $A/chinnu_wifi_pass; chmod 600 $A/chinnu_wifi_pass
modprobe ifb || true

echo
echo "DONE. Wi-Fi name: $SSID   password: $PASS"
ip -4 addr show eth0 | grep inet
