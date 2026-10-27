"""Tinglish -> Telugu script for Chinnu's voice. Word dictionary learned from ~3,000 Chinnu sentence pairs (96% coverage),
rule-based fallback for new words, numbers read as Telugu words."""
import json, os, re
from indic_transliteration import sanscript
D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'xlit_dict.json')))
ONES = ['సున్నా', 'ఒకటి', 'రెండు', 'మూడు', 'నాలుగు', 'ఐదు', 'ఆరు', 'ఏడు', 'ఎనిమిది', 'తొమ్మిది', 'పది', 'పదకొండు', 'పన్నెండు',
        'పదమూడు', 'పద్నాలుగు', 'పదిహేను', 'పదహారు', 'పదిహేడు', 'పద్దెనిమిది', 'పంతొమ్మిది']
TENS = {2: 'ఇరవై', 3: 'ముప్పై', 4: 'నలభై', 5: 'యాభై', 6: 'అరవై', 7: 'డెబ్బై', 8: 'ఎనభై', 9: 'తొంభై'}
TENS_COMB = {2: 'ఇరవై', 3: 'ముప్పై', 4: 'నలభై', 5: 'యాభై', 6: 'అరవై', 7: 'డెబ్బై', 8: 'ఎనభై', 9: 'తొంభై'}

def num(n):
    n = int(n)
    if n < 20: return ONES[n]
    if n < 100: return TENS[n // 10] + ('' if n % 10 == 0 else ' ' + ONES[n % 10])
    if n < 1000:
        h = 'వంద' if n // 100 == 1 else ONES[n // 100] + ' వందల'
        return h + ('' if n % 100 == 0 else ' ' + num(n % 100))
    return ' '.join(ONES[int(d)] for d in str(n))

def _word(w):
    lw = w.lower()
    if lw in D: return D[lw]
    return sanscript.transliterate(lw, 'optitrans', 'telugu')

def to_telugu(text):
    t = re.sub(r'(\d+):(\d\d)', lambda m: f'{num(m.group(1))} {num(m.group(2)) if m.group(2) != "00" else ""}', text)
    t = re.sub(r'(\d+)\s*%', lambda m: f'{num(m.group(1))} పర్సెంట్', t)
    t = re.sub(r'\d+', lambda m: num(m.group(0)), t)
    t = re.sub(r"[A-Za-z']+", lambda m: _word(m.group(0)), t)
    return t
