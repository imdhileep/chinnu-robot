v = open('voice_agent.py', encoding='utf-8').read()
if 'local_llm' not in v:
    old = """    try:
        reply = brain.chat_stream(text, on_sentence)
    except Exception as e:
        print('[brain error]', e, flush=True); reply = 'Ayyo anna, brain lo chinna problem vachindi.'
        on_sentence(reply)"""
    new = """    try:
        reply = brain.chat_stream(text, on_sentence)
    except Exception as e:
        print('[brain error] -> local LLM', e, flush=True)
        try:
            import local_llm; reply = local_llm.chat(text)
        except Exception as e2:
            print('[local llm error]', e2, flush=True); reply = 'Ayyo anna, brain lo chinna problem vachindi.'
        on_sentence(reply)"""
    assert old in v; v = v.replace(old, new, 1)
    old2 = """        try:
            reply = brain.chat(text)
        except Exception as e:
            print('[brain error]', e); reply = 'Ayyo anna, brain lo chinna problem vachindi.'"""
    new2 = """        try:
            reply = brain.chat(text)
        except Exception as e:
            print('[brain error] -> local LLM', e)
            try:
                import local_llm; reply = local_llm.chat(text)
            except Exception as e2:
                print('[local llm error]', e2); reply = 'Ayyo anna, brain lo chinna problem vachindi.'"""
    assert old2 in v; v = v.replace(old2, new2, 1)
    open('voice_agent.py', 'w', encoding='utf-8').write(v); print('voice_agent ok')

c = open('config.yaml', encoding='utf-8-sig').read()
if 'local_llm:' not in c:
    c += '\nlocal_llm:             # Ollama on this server - fallback brain when OpenAI fails\n  url: http://127.0.0.1:11434\n  model: qwen2.5:3b\n'
    open('config.yaml', 'w', encoding='utf-8').write(c); print('config ok')
