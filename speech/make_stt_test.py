"""Make a small Telugu speech test set with known text (OpenAI TTS, normal adult voices) + gpt-4o-transcribe reference."""
import json
from openai import OpenAI
c = OpenAI()
T = ["చిన్ను, రూమ్ లైట్ ఆఫ్ చెయ్యి", "ఈ రోజు వాతావరణం ఎలా ఉంది?", "పది నిమిషాల్లో టీ రెడీ అని గుర్తు చేయి",
     "నాటు నాటు పాట పెట్టు", "నేను చాలా అలసిపోయాను రా", "టీవీ ఆన్ చేయి", "కూర్చో, తర్వాత తోక ఊపు",
     "గార్డ్ మోడ్ ఆన్ చెయ్యి", "నీ బ్యాటరీ ఎంత ఉంది?", "main door దగ్గర ఎవరైనా ఉన్నారా చూడు",
     "Chinnu, desk lamp on cheyyi ra", "repu podduna aaru gantalaki gym ani gurthu cheyyi"]
out = []
for i, t in enumerate(T):
    r = c.audio.speech.create(model="gpt-4o-mini-tts", voice=["onyx", "nova", "ash"][i % 3], input=t, response_format="wav",
                              instructions="Speak naturally like a young Telugu person talking casually at home.")
    p = f"/tmp/stt_test/t{i}.wav"; r.write_to_file(p)
    ref = c.audio.transcriptions.create(model="gpt-4o-transcribe", file=open(p, "rb"), language="te").text
    out.append({"file": f"t{i}.wav", "text": t, "gpt": ref})
json.dump(out, open("/tmp/stt_test/truth.json", "w"), ensure_ascii=False, indent=1)
print("ok", len(out))
