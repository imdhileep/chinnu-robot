"""Walk in a direction for N s with optional trim, then print the gyro-integrated heading change.
usage: gyro_walk.py <forward|turn_left|backward> <secs> [trim]"""
import sys, time, requests, robot
URL, HDR = robot.URL, robot.HDR
d = sys.argv[1]; secs = float(sys.argv[2])
if len(sys.argv) > 3:
    requests.post(URL + '/gait', headers=HDR, params={'trim': float(sys.argv[3])}, timeout=5)
requests.post(URL + '/head', headers=HDR, params={'yaw': 0, 'pitch': 0, 'roll': 0, 'speed': 60}, timeout=5)
time.sleep(1)
t0 = time.time()
while time.time() - t0 < secs:
    requests.post(URL + f'/move/{d}', headers=HDR, params={'ms': 600}, timeout=5)
    time.sleep(0.3)
requests.post(URL + '/move/stop', headers=HDR, timeout=5)
time.sleep(1.5)
print(d, secs, requests.get(URL + '/move/last', headers=HDR, timeout=5).json(), flush=True)
