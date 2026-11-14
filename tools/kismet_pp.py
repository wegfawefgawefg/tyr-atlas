"""Pretty-print CUE4Parse Kismet bytecode JSON as rough pseudocode. usage: kismet_pp.py <asset.json> <FunctionName>"""
import json, sys
def nm(o):
    if isinstance(o, dict):
        if 'Property' in o and isinstance(o['Property'], dict): return o['Property'].get('Name')
        if 'ObjectName' in o: return o['ObjectName'].split(':')[-1].strip("'").split("'")[-1].split('.')[-1]
    return str(o)
def ex(e):
    if e is None: return '_'
    i = e.get('Inst')
    if i in ('EX_LocalVariable', 'EX_InstanceVariable', 'EX_LocalOutVariable', 'EX_DefaultVariable'): return nm(e['Variable'])
    if i in ('EX_IntConst', 'EX_FloatConst', 'EX_DoubleConst', 'EX_ByteConst', 'EX_Int64Const'): return str(e['Value'])
    if i == 'EX_True': return 'true'
    if i == 'EX_False': return 'false'
    if i in ('EX_NameConst', 'EX_StringConst'): return repr(e.get('Value'))
    if i == 'EX_ObjectConst': return nm(e['Value'])
    if i == 'EX_Self': return 'self'
    if i in ('EX_CallMath', 'EX_FinalFunction', 'EX_VirtualFunction', 'EX_LocalVirtualFunction', 'EX_LocalFinalFunction'):
        f = e['Function']; f = f if isinstance(f, str) else nm(f)
        return f"{f}({', '.join(ex(p) for p in e.get('Parameters', []))})"
    if i == 'EX_Context' or i == 'EX_Context_FailSilent': return f"{ex(e['ObjectExpression'])}.{ex(e['ContextExpression'])}"
    if i in ('EX_Let', 'EX_LetBool', 'EX_LetObj', 'EX_LetValueOnPersistentFrame'): return f"{ex(e.get('Variable'))} = {ex(e.get('Expression'))}"
    if i == 'EX_JumpIfNot': return f"if not {ex(e['BooleanExpression'])} goto {e['CodeOffset']}"
    if i == 'EX_Jump': return f"goto {e['CodeOffset']}"
    if i == 'EX_Return': return f"return {ex(e.get('Expression'))}"
    if i == 'EX_StructMemberContext': return f"{ex(e['StructExpression'])}.{nm(e['Property'])}"
    if i == 'EX_ArrayGetByRef': return f"{ex(e['ArrayVariable'])}[{ex(e['ArrayIndex'])}]"
    if i == 'EX_PushExecutionFlow': return f"push {e['PushingAddress']}"
    if i == 'EX_PopExecutionFlow': return 'pop'
    if i == 'EX_PopExecutionFlowIfNot': return f"pop if not {ex(e['BooleanExpression'])}"
    if i == 'EX_ComputedJump': return f"goto {ex(e['CodeOffsetExpression'])}"
    if i in ('EX_EndOfScript', 'EX_Nothing'): return ''
    return i
j = json.load(open(sys.argv[1]))
for e in j:
    if e.get('Name') == sys.argv[2]:
        for s in e.get('ScriptBytecode') or []:
            t = ex(s)
            if t: print(f"{s.get('StatementIndex', ''):>6} {t}")
