#!/bin/bash
# Keep the Chinnu touch panel on. The panel may be on either micro-HDMI port; HDMI-A-1 also has a
# forced mode (cmdline) so it always looks "connected" - prefer HDMI-A-2 when a real EDID is there.
export WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0} XDG_RUNTIME_DIR=/run/user/1000
PANEL_MODE=${PANEL_MODE:-1024x600}   # the 7" panel only shows this mode; 1024x768 = "no signal"
while true; do
  if [ "$(wc -c < /sys/class/drm/card1-HDMI-A-2/edid 2>/dev/null)" -gt 0 ]; then out=HDMI-A-2; other=HDMI-A-1; else out=HDMI-A-1; other=HDMI-A-2; fi
  dp=$(cat /sys/class/drm/card1-$out/dpms 2>/dev/null)
  if [ "$dp" != "On" ]; then echo "$out dpms=$dp -> on"; wlr-randr --output $out --on --pos 0,0 >/dev/null 2>&1; fi
  if [ "$out" = "HDMI-A-2" ] && wlr-randr 2>/dev/null | awk "/^$other/{f=1} f&&/Enabled/{print \$2; exit}" | grep -q yes; then
    echo "$other phantom enabled -> off"; wlr-randr --output $other --off >/dev/null 2>&1
  fi
  if ! wlr-randr 2>/dev/null | awk "/^$out/{f=1} f&&/current/{print; exit}" | grep -q "$PANEL_MODE"; then
    echo "$out mode wrong -> $PANEL_MODE"; wlr-randr --output $out --mode $PANEL_MODE >/dev/null 2>&1
  fi
  sleep 3
done
