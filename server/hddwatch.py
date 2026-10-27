"""HDD watchdog: the USB disk dropped off once (Oct 14) and came back as a new device, unmounted.
Every 60 s: if /mnt/hdd is not mounted -> stop Nextcloud/Jellyfin (so they don't write to the SD/NVMe),
try to mount it again, and when it is back restart them. Telegram alert both ways."""
import subprocess, time, threading

CONTAINERS = ['nextcloud-db-1', 'nextcloud-redis-1', 'nextcloud-app-1', 'jellyfin']
_state = {'down_since': None}

def _mounted():
    return subprocess.run(['findmnt', '/mnt/hdd'], capture_output=True).returncode == 0

def _tg(msg):
    try:
        import telegram_bot; telegram_bot.send(msg)
    except Exception as e: print('[hdd]', e, flush=True)
    try:
        import history; history.log('alert', msg)
    except Exception: pass

def _loop():
    time.sleep(60)
    while True:
        try:
            if not _mounted():
                if not _state['down_since']:
                    _state['down_since'] = time.time()
                    subprocess.run(['docker', 'stop'] + CONTAINERS, capture_output=True, timeout=120)
                    _tg('⚠️ Chinnu server: the external hard disk is not mounted. Nextcloud and Jellyfin are paused. Trying to re-mount…')
                subprocess.run(['sudo', '-n', 'mount', '/mnt/hdd'], capture_output=True, timeout=60)
                if _mounted():
                    subprocess.run(['docker', 'start'] + CONTAINERS, capture_output=True, timeout=120)
                    _tg('✅ Hard disk is back. Nextcloud and Jellyfin restarted.')
                    _state['down_since'] = None
            else:
                _state['down_since'] = None
        except Exception as e:
            print('[hdd] error', e, flush=True)
        time.sleep(60)

def start():
    threading.Thread(target=_loop, daemon=True).start()
