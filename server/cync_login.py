#!/usr/bin/env python3
"""One-time Cync login. Run it yourself: venv/bin/python cync_login.py
Saves the auth tokens (not your password) to cync_auth.json (chmod 600)."""
import asyncio, json, os, getpass, time, aiohttp
from pycync import Auth
from pycync.exceptions import TwoFactorRequiredError

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cync_auth.json')

async def main():
    email = input('Cync email: ').strip()
    pw = getpass.getpass('Cync password (hidden): ')
    user = None
    async with aiohttp.ClientSession() as session:
        auth = Auth(session, username=email, password=pw)
        try:
            user = await auth.login()
        except TwoFactorRequiredError:
            print()
            print('NOTE: Cync returned 400. Either a 2FA code was emailed to you, OR the email/password is wrong.')
            print('Check your inbox/spam now. If NO email arrived, the password is wrong: press Enter to abort.')
            for attempt in range(3):
                code = input('2FA code (digits only, Enter to abort): ').strip().replace(' ', '')
                if not code:
                    print('aborted'); return
                try:
                    user = await auth.login(code); break
                except Exception as e:
                    print(f'  failed ({e}); try again')
            else:
                print('giving up'); return
    data = {'access_token': user.access_token, 'refresh_token': user.refresh_token,
            'authorize': user.authorize, 'user_id': user.user_id, 'expires_at': user.expires_at, 'email': email}
    with open(OUT, 'w') as f:
        json.dump(data, f)
    os.chmod(OUT, 0o600)
    print('saved', OUT, '(expires', time.ctime(user.expires_at), ')')

asyncio.run(main())
