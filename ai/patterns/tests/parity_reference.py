"""Emit a grid of independently executed Python reference results for Node parity QA."""
import json
from ai.patterns.engine import discover
from ai.patterns.service import PatternService

b=PatternService().load()
cases=[]
for threshold in [round(.10+i*.05,2) for i in range(18)]:
    for excluded in [[], *[[e['id']] for e in b['events']], [e['id'] for e in b['events']]]:
        for scope in ['fixtures','sources']:
            options={'threshold':threshold,'excluded':excluded,'scope':scope}
            cases.append({'options':options,'expected':discover(b,**options)})
print(json.dumps({'bundle':b,'cases':cases},ensure_ascii=False))
