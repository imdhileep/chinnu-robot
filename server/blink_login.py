"""One-time Blink login (run by hand): venv/bin/python blink_login.py
Asks for the Blink/Amazon email + password, then the 2FA PIN Blink emails/texts you. Saves blink_auth.json (chmod 600)."""
import os, asyncio, getpass
from aiohttp import ClientSession
from blinkpy.blinkpy import Blink
from blinkpy.auth import Auth

BASE = os.path.dirname(os.path.abspath(__file__))
AUTH_FILE = os.path.join(BASE, 'blink_auth.json')

async def main():
    user = input('Blink email: ').strip()
    pw = getpass.getpass('Blink password (hidden): ')
    async with ClientSession() as s:
        blink = Blink(session=s)
        blink.auth = Auth({'username': user, 'password': pw}, no_prompt=False, session=s)
        from blinkpy.auth import BlinkTwoFARequiredError
        try:
            ok = await blink.start()
        except BlinkTwoFARequiredError:
            pin = input('Blink 2FA PIN (email/SMS lo vachindi): ').strip()
            if not await blink.auth.complete_2fa_login(pin):
                print('2FA FAILED'); return
            blink.setup_urls()
            await blink.get_homescreen()
            ok = await blink.setup_post_verify()
        if not ok:
            print('LOGIN FAILED'); return
        await blink.save(AUTH_FILE)
        os.chmod(AUTH_FILE, 0o600)
        print('saved', AUTH_FILE)
        for n, cam in blink.cameras.items():
            a = cam.attributes or {}
            print(f'  camera: {n}  battery={a.get("battery")}  armed={a.get("motion_enabled")}')

asyncio.run(main())
