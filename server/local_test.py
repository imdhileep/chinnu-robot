import time, local_llm
for q in ['Chinnu, nuvvu ela unnav?', 'stand light on cheyyi', 'fan off cheyyi', 'kurcho', 'ippudu time entha', 'naku oka joke cheppu']:
    print(f'{q!r:35} -> {local_llm.route(q)}')
t = time.time(); r = local_llm.chat('Chinnu, nuvvu ela unnav?'); print(f'chat {time.time() - t:.1f}s: {r}')
