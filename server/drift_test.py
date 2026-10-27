"""Measure walking drift: snapshot -> walk forward N s -> stop -> snapshot; estimate yaw from image shift.
Positive yaw = turned LEFT. usage: drift_test.py [seconds] [trim]"""
import sys, time, requests, numpy as np, cv2
import robot
URL, HDR = robot.URL, robot.HDR
SECS = float(sys.argv[1]) if len(sys.argv) > 1 else 4
HFOV = 54.0

def snap():
    for _ in range(3):
        r = requests.get(URL + '/snap.jpg', headers=HDR, timeout=8)
        if r.ok and len(r.content) > 1000:
            return cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_GRAYSCALE)
        time.sleep(0.5)
    raise RuntimeError('no snapshot')

if len(sys.argv) > 2:
    print('trim ->', requests.post(URL + '/gait', headers=HDR, params={'trim': float(sys.argv[2])}, timeout=5).json(), flush=True)
requests.post(URL + '/head', headers=HDR, params={'yaw': 0, 'pitch': 0, 'roll': 0, 'speed': 60}, timeout=5)
requests.post(URL + '/action/stand', headers=HDR, timeout=20)
time.sleep(1.5)
a = snap()
t0 = time.time()
while time.time() - t0 < SECS:
    requests.post(URL + '/move/forward', headers=HDR, params={'ms': 600}, timeout=5)
    time.sleep(0.3)
requests.post(URL + '/move/stop', headers=HDR, timeout=5)
time.sleep(2.0)
b = snap()

orb = cv2.ORB_create(1500)
ka, da = orb.detectAndCompute(a, None); kb, db = orb.detectAndCompute(b, None)
m = sorted(cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db), key=lambda x: x.distance)[:300]
pa = np.float32([ka[x.queryIdx].pt for x in m]); pb = np.float32([kb[x.trainIdx].pt for x in m])
M, inl = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=4)
W = a.shape[1]
# translation of the image centre under the similarity transform
cx, cy = W / 2, a.shape[0] / 2
nx = M[0, 0] * cx + M[0, 1] * cy + M[0, 2]
dx = nx - cx
yaw = dx / W * HFOV
scale = float(np.hypot(M[0, 0], M[1, 0]))
print(f'matches={len(m)} inliers={int(inl.sum()) if inl is not None else 0} scale={scale:.3f} dx={dx:.1f}px yaw={yaw:+.1f}deg ({"LEFT" if yaw > 0 else "RIGHT"})', flush=True)
cv2.imwrite('/tmp/drift_a.jpg', a); cv2.imwrite('/tmp/drift_b.jpg', b)
