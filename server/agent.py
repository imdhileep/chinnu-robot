from dotenv import load_dotenv
load_dotenv()
import brain, robot

print("Chinnu ready. Robot:", robot.health().get("ok"))
print("Type cheyyi ('quit' to exit)\n")
while True:
    text = input("Chintu: ").strip()
    if text.lower() in ("quit", "exit"): break
    if not text: continue
    print("Chinnu:", brain.chat(text))
