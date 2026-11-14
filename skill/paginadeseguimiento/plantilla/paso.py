#!/usr/bin/env python3
"""Registra en la página de avance lo que se está haciendo (checklist.json).
Uso: python3 paso.py "texto de la acción"                → actualiza «Ahora» y lo agrega al registro con la hora
     python3 paso.py --estado "inicio del paso" ok|run|pend → cambia el estado del paso del checklist que empieza así
     python3 paso.py --drive <lang> <enlace> [epoch]  → registra la subida a Drive de ese idioma (botón «Ver en Drive» en su tarjeta)
     python3 paso.py --trabajo "qué se está haciendo"         → título de la página y de la pestaña (solo QUÉ se trabaja, p. ej. «Videos «Riego»»; nunca el paso actual)
     python3 paso.py --accion "qué tiene que hacer" ["cómo hacerlo"]  → sección «Acciones pendientes» bien notable en la página
     python3 paso.py --accion-hecha "inicio del texto"          → quita esa acción pendiente (sin texto: quita todas)
     python3 paso.py --tarea <id> "Nombre de la tarea" "paso 1|paso 2|…"  → crea (o redefine) una TARJETA de tarea en la página
     python3 paso.py --tarea-paso <id> <n.º de paso desde 1> <0-100> ["detalle"]  → avance de un paso de esa tarjeta
       (tarjetas de tarea: para seguir desde afuera cada tarea del pedido —análisis, guion, capturas…—, no solo los idiomas)"""
import json, os, sys, time, fcntl
# varios procesos (render de 2 idiomas en paralelo) llaman a paso.py a la vez: candado exclusivo + temporal único,
# si no, se pisaban el .tmp y checklist.json quedaba corrupto (pasó el 06/11)
_LK = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.checklist.lock'), 'w'); fcntl.flock(_LK, fcntl.LOCK_EX)
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'checklist.json')
d = json.load(open(P, encoding='utf-8')) if os.path.exists(P) else {'ahora': '', 'pasos': []}
if sys.argv[1] == '--drive':
    t = float(sys.argv[4]) if len(sys.argv) > 4 else time.time()
    d.setdefault('drive', {})[sys.argv[2]] = {'url': sys.argv[3], 't': t}
    d.setdefault('registro', []).append([time.strftime('%H:%M:%S'), f"Video {sys.argv[2]} en Drive (subido a las {time.strftime('%H:%M', time.localtime(t))})"])
elif sys.argv[1] == '--trabajo':
    d['trabajo'] = sys.argv[2]
elif sys.argv[1] == '--accion':
    d.setdefault('acciones', []).append([time.strftime('%H:%M:%S'), sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ''])
    d.setdefault('registro', []).append([time.strftime('%H:%M:%S'), 'ACCIÓN PENDIENTE: ' + sys.argv[2]])
elif sys.argv[1] == '--accion-hecha':
    pre = sys.argv[2] if len(sys.argv) > 2 else ''
    hechas = [a for a in d.get('acciones', []) if a[1].startswith(pre)]
    d['acciones'] = [a for a in d.get('acciones', []) if not a[1].startswith(pre)]
    for a in hechas:
        d.setdefault('registro', []).append([time.strftime('%H:%M:%S'), 'Acción resuelta: ' + a[1]])
        d.setdefault('acciones_hechas', []).append([a[0], time.strftime('%H:%M:%S'), a[1]]); d['acciones_hechas'] = d['acciones_hechas'][-20:]
elif sys.argv[1] == '--tarea':
    viejos = {p[0]: p for p in d.get('tareas', {}).get(sys.argv[2], {}).get('pasos', [])}
    d.setdefault('tareas', {})[sys.argv[2]] = {'nombre': sys.argv[3], 'orden': d.get('tareas', {}).get(sys.argv[2], {}).get('orden', len(d.get('tareas', {}))),
        'pasos': [viejos.get(x, [x, 0, '']) for x in sys.argv[4].split('|')]}
elif sys.argv[1] == '--tarea-paso':
    t = d['tareas'][sys.argv[2]]; p = t['pasos'][int(sys.argv[3]) - 1]
    p[1] = int(sys.argv[4]); p[2] = sys.argv[5] if len(sys.argv) > 5 else ('' if p[1] in (0, 100) else p[2])
    if p[1] == 100: d.setdefault('registro', []).append([time.strftime('%H:%M:%S'), f"✔ {t['nombre']}: {p[0]}"])
elif sys.argv[1] == '--estado':
    for p in d['pasos']:
        if p[0].startswith(sys.argv[2]): p[1] = sys.argv[3]
else:
    d['ahora'] = sys.argv[1]
    d.setdefault('registro', []).append([time.strftime('%H:%M:%S'), sys.argv[1]]); d['registro'] = d['registro'][-60:]
tmp = f'{P}.{os.getpid()}.tmp'; json.dump(d, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); os.replace(tmp, P)
