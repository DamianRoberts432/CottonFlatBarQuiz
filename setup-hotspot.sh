#!/usr/bin/env bash
# One-time setup: one Wi-Fi card becomes the open "Cotton Flat Bar Quiz" hotspot at
# 192.168.4.1 and the other keeps the Pi's internet and Raspberry Pi Connect. The
# built-in Wi-Fi is the hotspot unless it is the one on the internet, then the USB
# dongle is. Run: sudo bash setup-hotspot.sh   (or: sudo bash setup-hotspot.sh wlan1)
set -euo pipefail

SSID="Cotton Flat Bar Quiz"
CON="quiz-hotspot"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run it with sudo: sudo bash setup-hotspot.sh"
    exit 1
fi

on_internet() {
    ip route show default | grep -q "dev $1 "
}

IFACE="${1:-}"
if [ -z "$IFACE" ]; then
    BUILTIN=""
    OTHERS=""
    for dev in /sys/class/net/wl*; do
        [ -e "$dev" ] || continue
        if readlink "$dev/device/driver" 2>/dev/null | grep -q brcmfmac; then
            BUILTIN="$(basename "$dev")"
        else
            OTHERS="$OTHERS $(basename "$dev")"
        fi
    done
    IFACE="$BUILTIN"
    if [ -n "$BUILTIN" ] && on_internet "$BUILTIN"; then
        for dev in $OTHERS; do
            if ! on_internet "$dev"; then
                IFACE="$dev"
                break
            fi
        done
    fi
fi
if [ -z "$IFACE" ]; then
    echo "Could not find the Pi's Wi-Fi. Run: nmcli device   then: sudo bash setup-hotspot.sh <name>"
    exit 1
fi
echo "Using $IFACE for the \"$SSID\" hotspot."

if ! ip route show default | grep -v "dev $IFACE " | grep -q default; then
    echo "Only $IFACE is connected to the internet. Connect the USB dongle to the internet first,"
    echo "otherwise turning $IFACE into the hotspot would cut off Raspberry Pi Connect."
    exit 1
fi

if ! command -v dnsmasq >/dev/null 2>&1; then
    apt-get install -y dnsmasq-base
fi

# Any older hotspot settings (e.g. one made by hand) would fight over the Wi-Fi card.
nmcli -t -f UUID,TYPE connection show | while IFS=: read -r uuid type; do
    name="$(nmcli -g connection.id connection show "$uuid")"
    if [ "$type" = "802-11-wireless" ] && [ "$name" != "$CON" ] &&
       [ "$(nmcli -g 802-11-wireless.mode connection show "$uuid")" = "ap" ]; then
        echo "Removing old hotspot settings: $name"
        nmcli connection delete "$uuid" >/dev/null
    fi
done

# The old profile that joined the ESP32's network must not grab the built-in Wi-Fi back.
if nmcli -t -f NAME connection show | grep -Fxq "$SSID"; then
    nmcli connection modify "$SSID" connection.autoconnect no
    nmcli connection down "$SSID" >/dev/null 2>&1 || true
fi

nmcli connection delete "$CON" >/dev/null 2>&1 || true
nmcli connection add type wifi ifname "$IFACE" con-name "$CON" autoconnect yes ssid "$SSID" \
    802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 6 \
    ipv4.method shared ipv4.addresses 192.168.4.1/24 ipv6.method disabled

# Phones share the dongle's internet (ipv4.method shared), so Android shows
# "Connected" instead of "No internet". Only the phones' "is there internet?"
# check sites point at the Pi, so the sign-in popup still opens the quiz menu.
PROBE_HOSTS="connectivitycheck.gstatic.com connectivitycheck.android.com clients3.google.com
connect.rom.miui.com connectivitycheck.platform.hicloud.com captive.apple.com
www.msftconnecttest.com www.msftncsi.com detectportal.firefox.com"
mkdir -p /etc/NetworkManager/dnsmasq-shared.d
for host in $PROBE_HOSTS; do echo "address=/$host/192.168.4.1"; done \
    > /etc/NetworkManager/dnsmasq-shared.d/cotton-flat-quiz.conf

install -m 644 "$REPO_DIR/cotton-flat-quiz.service" /etc/systemd/system/cotton-flat-quiz.service
systemctl daemon-reload

nmcli connection up "$CON"
systemctl restart cotton-flat-quiz.service

# TV scores in a normal maximised window (taskbar stays usable) whenever the desktop starts.
DESKTOP_USER="${SUDO_USER:-d}"
DESKTOP_HOME="$(getent passwd "$DESKTOP_USER" | cut -d: -f6)"
BROWSER="$(command -v chromium-browser || command -v chromium || true)"
if [ -n "$BROWSER" ] && [ -n "$DESKTOP_HOME" ]; then
    sudo -u "$DESKTOP_USER" mkdir -p "$DESKTOP_HOME/.config/autostart"
    printf '[Desktop Entry]\nType=Application\nName=Quiz TV\nExec=%s --app=http://127.0.0.1:5000/tv --start-maximized\n' "$BROWSER" \
        | sudo -u "$DESKTOP_USER" tee "$DESKTOP_HOME/.config/autostart/quiz-tv.desktop" >/dev/null
    echo "TV scores will open in their own window next time the desktop starts."
fi

echo "Done: \"$SSID\" is broadcasting from $IFACE at 192.168.4.1. You can unplug the ESP32."
