import time, random
R = random.Random(7)
PROTECTED = ('server', 'modem', 'router')

def mock(name, a):
    t = time.strftime('%I:%M %p')
    if name == 'govee_plug':
        tg = str(a.get('target', '')).lower()
        if a.get('action') == 'off' and any(p in tg for p in PROTECTED):
            return {'ok': False, 'refused': [tg], 'error': f'{tg} is protected and can never be switched off'}
        if a.get('action') in ('status', 'list'): return {'ok': True, 'state': {tg or 'tv': R.choice([True, False])}}
        return {'ok': True, 'target': tg, 'on': a.get('action') == 'on'}
    if name == 'power_strip':
        if str(a.get('outlet')) == '3' and a.get('action') == 'off':
            return {'ok': False, 'error': 'outlet 3 is the desktop PC - ask Chintu to confirm first'}
        return {'ok': True, 'outlet': a.get('outlet'), 'on': a.get('action') == 'on'}
    if name == 'home_light': return {'ok': R.random() > 0.05, **a}
    if name == 'set_volume': return {'ok': True, 'volume': a.get('percent') or R.choice([40, 50, 60, 70, 80])}
    if name == 'robot_action': return {'ok': True, 'done': a.get('name')}
    if name == 'robot_stop': return {'ok': True}
    if name == 'robot_battery':
        p = R.randint(15, 98); return {'percent': p, 'voltage': round(6.8 + p * 0.016, 2), 'charging': R.random() < 0.3}
    if name == 'now': return {'time': t, 'date': time.strftime('%A, %d %B %Y')}
    if name == 'weather':
        return {'ok': True, 'now_f': R.randint(38, 88), 'sky': R.choice(['clear', 'cloudy', 'light rain', 'sunny', 'windy']),
                'high_f': R.randint(55, 92), 'low_f': R.randint(30, 60), 'rain_chance': R.choice([0, 10, 40, 80])}
    if name == 'news':
        return {'ok': True, 'headlines': ['India beat Australia in the 2nd T20', 'New AI chip announced for laptops',
                                          'Heavy rains expected in coastal Andhra this week']}
    if name in ('remember', 'forget'): return {'ok': True}
    if name == 'set_reminder': return {'ok': True, 'id': R.randint(1, 40), 'when': a.get('at') or f"in {a.get('minutes')} min"}
    if name == 'list_reminders': return {'reminders': [{'id': 3, 'text': 'call amma', 'when': '8:00 PM'}]}
    if name == 'cancel_reminder': return {'ok': True}
    if name == 'play_music': return {'ok': True, 'playing': a.get('query', 'song'), 'source': 'youtube'}
    if name == 'stop_music': return {'ok': True, 'was_playing': True}
    if name == 'look':
        return {'ok': True, 'answer': R.choice(['Chintu sitting at the desk with a laptop', 'a person holding a coffee mug',
                                                'an empty room with a sofa and a TV', 'Chintu holding a phone and smiling'])}
    if name == 'who_is_here': return {'ok': True, 'people': R.choice([['Chintu'], [], ['unknown person'], ['Chintu', 'unknown person']]), 'voice': 'Chintu'}
    if name == 'detect_objects': return {'ok': True, 'objects': R.choice([['person', 'laptop', 'cup'], ['chair', 'tv', 'bottle'], ['person', 'cell phone']])}
    if name == 'home_camera': return {'ok': True, 'answer': R.choice(['nobody at the door, a parcel on the mat', 'empty patio, it is dark', 'a delivery person at the door'])}
    if name == 'camera': return {'ok': True, 'action': a.get('action'), 'saved': 'Chinnu/gallery'}
    if name == 'enroll_face': return {'ok': True, 'name': a.get('name')}
    if name in ('guard_mode', 'follow_me', 'saver_mode'): return {'ok': True, 'on': a.get('action') == 'on'}
    if name == 'wifi_speed': return {'ok': True, 'device': a.get('device'), 'limit_mbps': a.get('mbps')}
    if name == 'run_command': return {'ok': True, 'ran': a.get('name')}
    if name == 'list_commands': return {'commands': ['good morning', 'movie mode', 'movie off', 'work mode', 'good night', 'leaving home', 'im home']}
    if name == 'nextcloud_search': return {'ok': True, 'files': [f"Chinnu/gallery/{a.get('query', 'photo')}_01.jpg"]}
    return {'ok': True}

