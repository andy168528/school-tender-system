"""Accuracy check on labelled notices (ai_cases.json). Run after any change to ai.SCOPE/PROMPT or classify rules:
  python crawler/test_ai.py          # Gemini (needs GEMINI_API_KEY) + keyword rules
  python crawler/test_ai.py rules    # keyword rules only
Exits 1 if Gemini gets any case wrong."""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
import ai, classify

cases = json.load(open(os.path.join(os.path.dirname(__file__), 'ai_cases.json')))
rule_bad = [c for c in cases if bool(classify.eng_types(c['title'])) != c['eng']]
print(f'keyword rules (title only): {len(cases) - len(rule_bad)}/{len(cases)} correct')
for c in rule_bad: print('  rules wrong:', '應保留' if c['eng'] else '應刪除', c['title'][:60])
if sys.argv[1:] == ['rules'] or not ai.KEY: sys.exit(0)

def run(c):
    j = ai.judge(c['title'], c['url'], c['text'])
    return c, j and j['tender'] and j['eng'], j
with ThreadPoolExecutor(8) as ex: res = list(ex.map(run, cases))
none = [c for c, _, j in res if j is None]
bad = [(c, j) for c, ok, j in res if j is not None and bool(ok) != c['eng']]
print(f'Gemini: {len(res) - len(bad) - len(none)}/{len(res)} correct, {len(none)} no answer', ai.STATS)
for c, j in bad: print('  gemini wrong:', '應保留' if c['eng'] else '應刪除', c['title'][:50], '|', j.get('by'), j['tender'], j['eng'], j.get('reason', ''))
sys.exit(1 if bad or none else 0)
