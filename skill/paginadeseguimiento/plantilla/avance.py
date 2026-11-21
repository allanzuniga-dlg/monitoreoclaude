#!/usr/bin/env python3
"""Página de avance EN VIVO de producir_todo.sh, sin recargar la página.
Uso: python3 avance.py [idiomas...]   (por defecto, los idiomas con escenas_<lang>.json)
Sirve en 127.0.0.1:$AVANCE_PORT (8765):  /  → la página · /ws → WebSocket (en vivo; pasa por el túnel) · /eventos → SSE · /estado → JSON.
Solo expone esas tres rutas: ningún archivo del proyecto. publicar_avance.sh le pone delante un túnel de Cloudflare."""
import base64, hashlib, json, os, re, struct, sys, time, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

P = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(P, 'config.json')))
LANGS = sys.argv[1:] or [l for l in CFG['idiomas'] if os.path.exists(os.path.join(P, f'escenas_{l}.json'))]
PORT = int(os.environ.get('AVANCE_PORT', 8765))
T0 = time.time()


def leer(p):
    try:
        return open(p, encoding='utf-8', errors='replace').read()
    except OSError:
        return ''


# Inicio del pedido actual: lo fija publicar_avance.sh al limpiar la página (.inicio_avance). No se usa la fecha de produccion.log:
# al reiniciar solo la página después de producir, esa fecha es posterior a todos los archivos y la página quedaba en 0 %.
try:
    INICIO = float(open(os.path.join(P, '.inicio_avance')).read().strip())
except (OSError, ValueError):
    INICIO = 0


def mt(p):
    """Fecha del archivo, o 0 si es anterior al inicio del proceso actual (produccion.log): la página muestra solo el avance real."""
    try:
        m = os.path.getmtime(p)
        return m if m >= INICIO - 1 else 0
    except OSError:
        return 0


PROCS = []  # [(nombre, args, segundos)] procesos del pipeline que están corriendo


def procesos():
    out = []
    for pid in os.listdir('/proc'):
        if not pid.isdigit():
            continue
        try:
            argv = open(f'/proc/{pid}/cmdline', 'rb').read().decode(errors='replace').split('\0')
            args = ' '.join(argv).strip()
            prog = ' '.join(os.path.basename(x) for x in argv[:4])  # solo el programa y sus primeros argumentos
            ini = os.stat(f'/proc/{pid}').st_mtime
        except OSError:
            continue
        if P not in args and 'narrar.py' not in args and 'marca.py' not in args and 'render.js' not in args:
            continue
        for clave, nombre in (('marca.py', 'Clip de la marca (XTTS)'), ('narrar.py', 'Voz (narración + Whisper)'),
                              ('ensamblar.py', 'Armado de audio y tiempos'), ('render.js', 'Render de la imagen (Chrome)'),
                              ('quemar.sh', None), ('ffmpeg', 'ffmpeg'), ('producir_todo.sh', 'Producción completa'),
                              ('producir.sh', 'Producción del idioma')):
            if clave in prog and nombre and not prog.startswith(('bash -c', 'sh -c')):
                if clave == 'ffmpeg':
                    nombre = 'Incrustando subtítulos (ffmpeg)' if 'ass=' in args else 'Uniendo imagen y audio (ffmpeg)'
                lang = next((l for l in CFG['idiomas'] if re.search(rf'(\s|_){l}(\s|\.|$)', args)), '')
                if CFG.get('subproyectos'):   # varios videos en subcarpetas: el proceso pertenece al de su carpeta de trabajo
                    try: cwd = os.readlink(f'/proc/{pid}/cwd')
                    except OSError: cwd = ''
                    lang = next((u['id'] for u in CFG['subproyectos'] if (cwd + '/').startswith(os.path.join(P, u['dir']) + '/')), lang)
                out.append([nombre + (f' · {lang}' if lang else ''), int(time.time() - ini)])
                break
    return out


_FFP = {}


def verificar(f, esperado):
    """ffprobe del archivo final (con caché por fecha de modificación): video + audio + duración esperada."""
    m = mt(f)
    if not m:
        return None
    if _FFP.get(f, (0,))[0] != m:
        import subprocess
        try:
            o = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type', '-of', 'json', f],
                               capture_output=True, text=True, timeout=20).stdout
            d = json.loads(o or '{}'); tipos = {x.get('codec_type') for x in d.get('streams', [])}
            dur = float(d.get('format', {}).get('duration') or 0)
            ok = {'video', 'audio'} <= tipos and (not esperado or abs(dur - esperado) < 1.5)
            _FFP[f] = (m, ok, dur)
        except Exception:
            _FFP[f] = (m, False, 0)
    return _FFP[f]


def estado_idioma(L, activos, drive=None, U=None):
    """U = subproyecto (config "subproyectos": varios videos en subcarpetas, p. ej. una por voz), o None = este proyecto."""
    PP = os.path.join(P, U['dir']) if U else P
    CF = json.load(open(os.path.join(PP, 'config.json'))) if U else CFG
    R = lambda *x: os.path.join(PP, 'render', *x)
    esc = json.load(open(os.path.join(PP, f'escenas_{L}.json')))
    todas = [f for e in esc for f in e['frases']]
    n = sum(len(e['frases']) for e in esc)
    log = leer(os.path.join(P, 'produccion.log'))
    if U:   # el log común antepone el id del subproyecto a cada línea
        err_u = f"VIDEO_ERROR {U['id']}" in log
        log = '\n'.join(l[len(U['id']) + 1:] for l in log.splitlines() if l.startswith(U['id'] + ' ')) + ('\nVIDEO_ERROR ' + L if err_u else '')
    rl = leer(R(f'render_{L}.log')) if mt(R(f'render_{L}.log')) else ''
    # la voz y la marca pueden venir de una pasada ANTERIOR (solo se regeneran las frases cambiadas):
    # cuentan si el archivo existe, sin importar su fecha. Si no, un idioma narrado antes quedaba en «0 de N» y su tarjeta no avanzaba nunca.
    marca = os.path.exists(os.path.join(PP, 'tts', 'marca_ABC_Dust.wav')) or L == 'en' or bool(re.search(rf'^\[{L} ', log, re.M))
    frases = re.findall(rf'^\[{L} (\d+)/\d+\] ([\d.]+) (.*)$', log, re.M)
    frases = list({int(f[0]): f for f in frases}.values())   # una frase regenerada vale por su último puntaje
    d = os.path.join(PP, 'tts', L)
    wavs = [w for w in (os.path.join(d, f"{e['id']}_{i}.wav") for e in esc for i in range(len(e['frases']))) if os.path.exists(w)]
    nf = min(n, max(len({int(i) for i, _, _ in frases}), len(wavs)))   # frases regeneradas aparecen dos veces en el log
    t_voz = max([os.path.getmtime(w) for w in wavs] or [0])
    t_voz = t_voz if t_voz >= INICIO - 1 else 0   # voz de antes del inicio: no exige que el armado sea posterior a ella
    K = U['id'] if U else L
    corre = lambda k: any(k in a[0] and a[0].endswith('· ' + K) for a in activos) or any(k in a[0] for a in activos if '·' not in a[0])
    # cadena de archivos: cada etapa cuenta solo si es más nueva que la anterior
    tl = R(f'timeline_{L}.js'); t_tl = mt(tl) if mt(tl) >= t_voz and nf >= n else 0
    m = re.findall(r'PROGRESO (\d+)/(\d+) (\d+)%', rl)
    r_ok = 'RENDER_OK' in rl and mt(R(f'render_{L}.log')) >= t_tl > 0
    r = 100 if r_ok else (int(m[-1][2]) if m and mt(R(f'render_{L}.log')) >= t_tl > 0 else 0)
    t_mudo = mt(R(f'mudo_{L}.mp4')) if r_ok else 0
    t_aud = mt(R(f'con_audio_{L}.mp4')) if t_mudo and mt(R(f'con_audio_{L}.mp4')) >= t_mudo else 0
    final = os.path.join(PP, f"{CF['titulo']} - {CF['idiomas'][L]}.mp4")
    t_fin = mt(final) if t_aud and mt(final) >= t_aud else 0
    esperado = None
    try:
        esperado = json.loads(leer(tl).split('=', 1)[1].rstrip().rstrip(';'))['total']
    except Exception:
        pass
    ver = verificar(final, esperado) if t_fin else None
    quemando = os.path.exists(os.path.join(PP, f'.tmp_{L}.mp4'))
    # error solo si el ÚLTIMO resultado fue un error (un reintento exitoso posterior lo borra)
    err = log.rfind(f'VIDEO_ERROR {L}') > log.rfind(f'VIDEO_OK {L}') or 'RENDER_ERROR' in rl or bool(ver and not ver[1])
    pasos = [
        ['Marca "ABC Dust" en inglés', 100 if marca else 0, ''],
        [f'Voz: {nf} de {n} frases', 99 if corre('Voz') and nf >= n else 100 * nf // n, ('regenerando frases corregidas' if nf >= n else 'narrando') if corre('Voz') else ''],   # corrección de frases en curso
        ['Armado de audio, tiempos y subtítulos', 100 if t_tl else 0, ''],
        ['Render de la imagen', r, f'{m[-1][0]}/{m[-1][1]} cuadros' if m and 0 < r < 100 else
         next((f'en curso · {t // 60}:{t % 60:02d}' for nom, t in activos if nom.startswith('Render') and nom.endswith(K)), '')],
        ['Unión de imagen y audio', 100 if t_aud else (50 if t_mudo and corre('Uniendo') else 0), 'en curso' if t_mudo and not t_aud else ''],
        ['Subtítulos incrustados', 100 if t_fin else (50 if quemando else 0), 'en curso' if quemando and not t_fin else ''],
        ['Verificación del archivo final', 100 if ver and ver[1] else 0,
         (f'{ver[2]:.1f} s · video y audio OK' if ver[1] else f'falló ({ver[2]:.1f} s, esperado {esperado})') if ver else ''],
    ]
    # subida a Drive: vale si se subió DESPUÉS de la última versión del archivo final (si se rehízo el video, la copia de Drive quedó vieja)
    dv = (drive or {}).get(U['id'] if U else L) or {}
    t_final = os.path.getmtime(final) if os.path.exists(final) else 0
    d_ok = bool(dv.get('url')) and dv.get('t', 0) >= t_final - 1 and bool(ver and ver[1])
    pasos.append(['Subida a Drive', 100 if d_ok else 0,
                  ('subido ' + time.strftime('%d/%m %H:%M', time.localtime(dv['t']))) if d_ok else
                  ('la copia en Drive es de una versión anterior: hay que reemplazarla' if dv.get('url') and ver and ver[1] else
                   ('a ' + CFG['drive_destino'] if CFG.get('drive_destino') else ''))])
    pesos = [5, 40, 3, 37, 3, 10, 2, 0]
    pct = sum(w * p[1] // 100 for w, p in zip(pesos, pasos))
    ok = bool(ver and ver[1])
    return dict(L=U['id'] if U else L, nombre=U['nombre'] if U else CFG['idiomas'][L], pct=100 if ok else min(pct, 99), ok=ok, err=err, pasos=pasos,
                archivo=os.path.basename(final) if ok else '', dur=round(ver[2], 1) if ok else 0, drive=dv.get('url') if d_ok else '',
                frases=[[int(i), float(s), (todas[int(i) - 1] if 0 < int(i) <= len(todas) else x)] for i, s, x in frases[-8:]],   # texto completo, no el recorte del log
                revisar=sum(1 for f in frases if float(f[1]) < .85))


SIS = {'cpu': [], 'total': 0, 'hist': [], 'mem': [0, 0], 'swap': [0, 0], 'top': [], 'carga': [0, 0, 0]}
_PREV = {'cpu': None, 'pid': {}, 't': None}


def _cpus():
    out = []
    for l in open('/proc/stat'):
        if not l.startswith('cpu'):
            break
        v = [int(x) for x in l.split()[1:]]
        out.append((sum(v), v[3] + (v[4] if len(v) > 4 else 0)))   # total, ocioso (idle + iowait)
    return out


def _pids():
    d = {}
    for p in os.listdir('/proc'):
        if not p.isdigit():
            continue
        try:
            s = open(f'/proc/{p}/stat').read()
            nom = s[s.index('(') + 1:s.rindex(')')]; f = s[s.rindex(')') + 2:].split()
            if nom.startswith(('python', 'node', 'bash')):   # «python» a secas no dice nada: script y primer argumento
                av = re.sub(r'\s-[WXm]\s+\S+', ' ', ' ' + ' '.join(open(f'/proc/{p}/cmdline', 'rb').read().decode(errors='replace').split('\0')[1:])).split()
                av = [x for x in av if not x.startswith('-')]
                if av: nom = ' '.join([os.path.basename(av[0])] + av[1:2])[:40]
            d[p] = (int(f[11]) + int(f[12]), nom, int(f[21]) * 4096)   # utime+stime, nombre, RSS (bytes)
        except Exception:
            pass
    return d


def muestrear():
    """Uso del sistema estilo btop: % por núcleo, historial total de 120 s, RAM, swap y procesos que más consumen."""
    c, pid, t = _cpus(), _pids(), time.time()
    if _PREV['cpu']:
        pct = [round(100 * (1 - (i - pi) / max(1, tt - pt)), 1) for (tt, i), (pt, pi) in zip(c, _PREV['cpu'])]
        SIS['total'], SIS['cpu'] = pct[0], pct[1:]
        SIS['hist'] = (SIS['hist'] + [pct[0]])[-120:]
        hz, dt = os.sysconf('SC_CLK_TCK'), t - _PREV['t']
        nc = os.cpu_count() or 1   # % de TODO el equipo (máx. 100 %), no por núcleo como top: 120 % confundía
        top = [(round(100 * (v[0] - _PREV['pid'][k][0]) / hz / dt / nc, 1), v[1], round(v[2] / 2**20)) for k, v in pid.items() if k in _PREV['pid']]
        SIS['top'] = sorted([x for x in top if x[0] > 0.2], reverse=True)[:12]
    _PREV.update(cpu=c, pid=pid, t=t)
    m = {l.split(':')[0]: int(l.split()[1]) for l in open('/proc/meminfo')}
    SIS['mem'] = [round((m['MemTotal'] - m['MemAvailable']) / 2**20, 2), round(m['MemTotal'] / 2**20, 2)]
    SIS['swap'] = [round((m['SwapTotal'] - m['SwapFree']) / 2**20, 2), round(m['SwapTotal'] / 2**20, 2)]
    SIS['carga'] = [round(x, 2) for x in os.getloadavg()]


def estado():
    activos = procesos()
    try:
        chk = json.load(open(os.path.join(P, 'checklist.json'), encoding='utf-8'))
    except Exception:
        chk = None
    E = [estado_idioma(u['lang'], activos, (chk or {}).get('drive'), u) for u in CFG['subproyectos']] if CFG.get('subproyectos') else [estado_idioma(L, activos, (chk or {}).get('drive')) if os.path.exists(os.path.join(P, f'escenas_{L}.json')) else
         dict(L=L, nombre=CFG['idiomas'][L], pct=0, ok=False, err=False, frases=[], revisar=0, drive='',
              pasos=[['Guion', 0, 'pendiente'], ['Voz', 0, ''], ['Render de la imagen', 0, ''], ['Audio y subtítulos', 0, ''], ['Verificación del archivo final', 0, ''], ['Subida a Drive', 0, ('a ' + CFG['drive_destino']) if CFG.get('drive_destino') else '']])
         for L in LANGS]   # los idiomas sin guion todavía aparecen en 0 %
    if CFG.get('solo_tareas'): E = []
    E = [e for e in E if e['L'] not in set((chk or {}).get('ocultas') or [])]   # ocultadas por el usuario con la escobilla   # fase sin idiomas (p. ej. guion y versión muda de revisión): solo tarjetas de tarea
    # tarjetas de TAREA (checklist «tareas», con paso.py --tarea): van primero, con la misma forma que las de idioma
    T = sorted(((chk or {}).get('tareas') or {}).items(), key=lambda x: x[1].get('orden', 0))
    E = [dict(L='t_' + k, nombre=t['nombre'], pct=(pc := sum(p[1] for p in t['pasos']) // max(1, len(t['pasos']))), ok=pc >= 100, err=False,
              pasos=t['pasos'], archivo='', dur=0, drive=(((chk or {}).get('drive') or {}).get(k) or {}).get('url', ''), frases=[], revisar=0, tarea=True) for k, t in T] + E
    fin = (bool(E) and all(e['ok'] for e in E) or (not E and bool(chk) and bool(chk.get('pasos')) and all(x[1] == 'ok' for x in chk['pasos']))) and not activos
    return dict(checklist=chk, titulo=CFG['titulo'], total=sum(e['pct'] for e in E) // max(1, len(E)), idiomas=E, fin=fin,
                error=any(e['err'] for e in E) and not activos, procesos=activos, t=int(time.time() - T0),
                hora=time.strftime('%H:%M:%S'), sis=SIS)


ACTUAL = {'json': json.dumps(estado()), 'ver': 0}
cambio = threading.Condition()


def vigilar():
    while True:
        time.sleep(1)
        try:
            muestrear()
        except Exception:
            pass
        j = json.dumps(estado())
        with cambio:
            ACTUAL['json'], ACTUAL['ver'] = j, ACTUAL['ver'] + 1
            cambio.notify_all()


PAGINA = r'''<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Avance en vivo</title><style>
:root{--bg:#f2f5f8;--card:#fff;--ink:#1c2340;--mut:#5b6785;--line:#d4dce6;--a:#0071bc;--ok:#00a99d;--err:#d64545;--deep:#070751}
@media (prefers-color-scheme:dark){:root{--bg:#0b0d1f;--card:#15183a;--ink:#e8ebf7;--mut:#9aa3c4;--line:#2a2f5c;--deep:#e8ebf7}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif;padding:28px 16px}
main{max-width:880px;margin:0 auto}.cols{display:flex;flex-direction:column}.izq,.der{min-width:0}@media (min-width:1150px){main{max-width:1420px}.cols{display:grid;grid-template-columns:minmax(0,1fr) 470px;gap:20px;align-items:start}.der{position:sticky;top:12px}.der .g{grid-template-columns:repeat(2,1fr)}html body{padding:14px 16px}main h1{font-size:20px}main .sub{margin:0 0 8px}main .tot{margin-bottom:8px}main .banner{padding:8px 14px;font-size:14px;margin-bottom:10px}main .banner small{font-size:11.5px;display:inline;margin-left:8px}main .card{padding:10px 14px;margin-bottom:10px;border-radius:12px}main h2{font-size:14.5px}main .st{font-size:11px;padding:2px 8px}main .big{margin:6px 0 4px;gap:8px}main .big b{font-size:16px;min-width:46px}main .bar{height:8px}main :is(#langs,#tablero) li{padding:1px 0;font-size:11.5px;gap:0 6px;grid-template-columns:1fr 38px}main :is(#langs,#tablero) li .t{height:2px}main :is(#langs,#tablero) li small{font-size:10.5px;margin:0}main #langs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-bottom:10px;align-items:start}main :is(#langs,#tablero) .card{margin:0}main :is(#langs,#tablero) table{font-size:10.5px;margin-top:6px}main :is(#langs,#tablero) th,main :is(#langs,#tablero) td{padding:1px 4px}main :is(#langs,#tablero) tbody{display:block;max-height:110px;overflow:auto}main :is(#langs,#tablero) thead,main :is(#langs,#tablero) tbody tr{display:table;width:100%;table-layout:fixed}main :is(#langs,#tablero) td:first-child,main :is(#langs,#tablero) th:first-child{width:22px}main :is(#langs,#tablero) td:last-child,main :is(#langs,#tablero) th:last-child{width:40px}main :is(#langs,#tablero) .warn{margin:4px 0 0;font-size:11.5px}main #chkL{columns:3;column-gap:18px}main #chkL li{break-inside:avoid;padding:1px 0;font-size:11.5px;grid-template-columns:22px 1fr}main #ahora{font-size:12.5px;margin:6px 0 4px!important}main #chk h3{margin:8px 0 2px!important;font-size:12.5px!important}main #reg{max-height:190px;overflow:auto}main .reg li{font-size:11.5px;padding:1px 0;grid-template-columns:62px 1fr}main #acc{padding:10px 16px}main #acc h2{font-size:16px}main #acc li{font-size:14px;padding:3px 0}main .procs li{font-size:12px;padding:1px 0;min-height:20px}main .lista5{height:calc(5 * 20px)}main .tabla5{height:calc(5 * 21px + 22px)}main .tabla5 td,main .tabla5 th{height:20px}main :is(#langs,#tablero) .st{white-space:nowrap}main h1{display:inline-block;margin-right:12px}main .sub{display:inline-block}main #chk header{margin-bottom:2px}main .sis canvas{height:76px;margin:6px 0}main .sis h3{margin:8px 0 3px}main .sis td,main .sis th{padding:1px 6px}main .mt{gap:6px}}@media (min-width:1450px){main #langs{grid-template-columns:repeat(4,minmax(0,1fr))}}@media (max-width:1149px){.izq{display:contents}#chk{order:-2}.der{order:-1}}@media (max-width:600px){#sisC .g{grid-template-columns:1fr}#sisC .mt{grid-template-columns:40px 1fr 84px}.sis{padding:16px}}h1{font-size:24px;margin:0 0 4px;color:var(--deep)}.sub{color:var(--mut);margin:0 0 18px}
.tot{display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;color:var(--mut);font-size:13px;margin-bottom:18px}
.live{display:inline-flex;align-items:center;gap:6px}.live i{width:8px;height:8px;border-radius:50%;background:var(--ok);animation:p 1.6s infinite}
.live.off i{background:var(--err);animation:none}@keyframes p{50%{opacity:.3}}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 22px;margin-bottom:18px}
header{display:flex;align-items:center;justify-content:space-between;gap:10px;cursor:pointer;user-select:none}header h2::before{content:"▾";display:inline-block;width:20px;color:var(--mut)}.card.plegada header h2::before{content:"▸"}.card.plegada>:not(header):not(.big):not(.va):not(.drv){display:none}#acc:not(.on){display:none}.vistas{display:inline-flex;border:1px solid var(--line);border-radius:9px;overflow:hidden;margin-left:8px;vertical-align:middle}.vistas button{border:0;background:var(--card);color:var(--mut);font-size:12.5px;padding:3px 11px;cursor:pointer}.vistas button+button{border-left:1px solid var(--line)}.vistas button.on{background:var(--a);color:#fff;font-weight:600}#tablero{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;align-items:start;margin-bottom:12px}#tablero .col{background:#00000008;border:1px dashed var(--line);border-radius:12px;padding:8px;min-height:120px}@media (max-width:700px){#tablero{grid-template-columns:1fr}.vistas{margin:6px 0 0}}#tablero .col h3{font-size:13px;margin:2px 4px 8px;color:var(--mut);display:flex;justify-content:space-between}#tablero .col .card{margin:0 0 8px}#tablaV{margin-bottom:12px;overflow-x:auto}#tablaV table{margin:0;font-size:13px}#tablaV th,#tablaV td{vertical-align:top}#tablaV tr.fila{cursor:pointer}#tablaV tr.fila:hover td{background:#0071bc0d}#tablaV .mini{height:8px;border-radius:5px;background:var(--line);overflow:hidden;min-width:70px;margin-top:4px}#tablaV .mini i{display:block;height:100%;background:linear-gradient(90deg,var(--a),var(--ok))}#tablaV td.c{text-align:center;white-space:nowrap}#tablaV td.ok{color:var(--ok)}#tablaV tr.det>td{background:#00000006;text-align:left!important;padding:10px 12px}.detalle{display:grid;grid-template-columns:minmax(260px,400px) minmax(0,1fr);gap:22px;align-items:start}.detalle ul li{display:grid;grid-template-columns:1fr 46px;gap:1px 8px;padding:3px 0;font-size:12.5px}.detalle ul li b{text-align:right}.detalle ul li .t{grid-column:1/3;height:3px}.detalle ul li small{grid-column:1/3;font-size:11.5px}.detalle table{margin-top:0;font-size:12px}.detalle tbody{display:table-row-group!important;max-height:none!important}.detalle table{width:100%;table-layout:auto!important;display:table!important}.detalle thead{display:table-header-group!important}.detalle tbody tr,.detalle thead tr{display:table-row!important}.detalle td,.detalle th{padding:4px 8px;text-align:left}.detalle td:first-child{width:28px}.detalle td:last-child,.detalle th:last-child{width:52px;text-align:right}.detalle .sinf{color:var(--mut);margin:0}@media (max-width:800px){.detalle{grid-template-columns:1fr}}#tablaV tr.det ul li{padding:2px 0;font-size:12.5px}#tablaV .drv{margin:0}.hide{display:none!important}.va{font-size:12.5px;color:var(--a);font-weight:600;margin:-2px 0 6px;overflow-wrap:anywhere}.card.plegada>.va{display:block}.drv{display:inline-flex;align-items:center;gap:6px;margin:2px 0 8px;padding:6px 14px;border-radius:9px;background:#1a73e8;color:#fff!important;font-weight:600;font-size:13.5px;text-decoration:none;box-shadow:0 1px 3px rgba(0,0,0,.2)}.drv:hover{background:#1557b0}.drv.hide{display:none}.card.plegada>.drv:not(.hide){display:inline-flex}.tabla5{height:calc(5 * 25px + 27px);overflow-y:auto;scrollbar-width:thin;scrollbar-color:#30363d #0d1117}.tabla5::-webkit-scrollbar{width:8px}.tabla5::-webkit-scrollbar-track{background:#0d1117}.tabla5::-webkit-scrollbar-thumb{background:#30363d;border-radius:8px;border:2px solid #0d1117}.tabla5::-webkit-scrollbar-thumb:hover{background:#484f58}.tabla5::-webkit-scrollbar-button{display:none;height:0}.tabla5 thead th{position:sticky;top:0;background:#0d1117;z-index:1}.tabla5 td,.tabla5 th{height:24px;box-sizing:border-box;white-space:nowrap}.lista5{height:calc(5 * 27px);overflow-y:auto;scrollbar-width:thin}.lista5 li{min-height:27px}#acc{margin:0 0 14px;padding:12px 18px;border-radius:14px;background:var(--card);border:2px solid var(--ok)}#acc h2{font-size:15px;margin:0;display:flex;gap:10px;align-items:center;color:var(--ok)}#acc h2::before{content:none}#acc.on{background:#ff8a00;border:3px solid #c65f00;color:#1a0d00;animation:latido 1.6s infinite;padding:16px 20px}#acc.on h2{font-size:20px;color:#1a0d00}.accI{display:block;padding:10px 0 4px;border-top:1px solid #c65f0055;margin-top:8px}.accI b{display:block;font-size:19px;line-height:1.3}.accI span{display:block;font-size:14.5px;margin-top:4px}.accI small{font-size:12px;color:#4a2600}#accH{margin-top:6px;font-size:12.5px;color:var(--mut)}#accH summary{cursor:pointer}#accH li{display:block;padding:2px 0}#acc.on #accH{color:#4a2600}.accA{color:#1a0d00;font-weight:700;text-decoration:underline;overflow-wrap:anywhere;user-select:text;-webkit-user-select:text}#acc .accI{user-select:text;-webkit-user-select:text}.accC{margin:4px 0 0;border:2px solid #1a0d00;background:#fff3e0;color:#1a0d00;border-radius:8px;padding:4px 12px;font-size:14px;font-weight:700;cursor:pointer;vertical-align:middle}.accC:hover{background:#fff}@keyframes latido{0%{box-shadow:0 0 0 0 rgba(255,138,0,.75)}70%{box-shadow:0 0 0 18px rgba(255,138,0,0)}100%{box-shadow:0 0 0 0 rgba(255,138,0,0)}}.card.plegada .big{margin:12px 0 0}header:hover h2{opacity:.8}.plegar{font-size:12.5px;color:var(--mut);background:none;border:1px solid var(--line);border-radius:8px;padding:3px 10px;cursor:pointer;margin-left:6px}h2{font-size:18px;margin:0}
.st{font-size:13px;padding:3px 10px;border-radius:20px;font-weight:600}.st.run{background:#0071bc22;color:var(--a)}.st.ok{background:#00a99d22;color:var(--ok)}.st.err{background:#d6454522;color:var(--err)}
.big{display:flex;align-items:center;gap:14px;margin:16px 0 12px}.big b{font-size:26px;min-width:64px;text-align:right;font-variant-numeric:tabular-nums}
.bar{flex:1;height:16px;border-radius:9px;background:var(--line);overflow:hidden}.bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--a),var(--ok));transition:width .8s ease}
ul{list-style:none;padding:0;margin:0}li{display:grid;grid-template-columns:1fr 48px;gap:4px 10px;padding:7px 0;color:var(--mut);transition:color .4s}li b{text-align:right;font-variant-numeric:tabular-nums}
li .t{grid-column:1/3;height:4px;border-radius:2px;background:var(--line);overflow:hidden}li .t i{display:block;height:100%;width:0;background:var(--a);transition:width .8s ease}
li.d{color:var(--ok)}li.d .t i{background:var(--ok)}li.a{color:var(--ink)}
table{width:100%;border-collapse:collapse;margin-top:14px;font-size:13.5px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}th{color:var(--mut);font-weight:500}td:last-child,th:last-child{text-align:right}tr.w td{color:var(--err)}
.warn{color:var(--err);margin:10px 0 0}.hide{display:none}
li small{grid-column:1/3;font-size:12.5px;color:var(--mut);margin-top:-2px}
.banner{border-radius:14px;padding:18px 22px;margin-bottom:18px;font-weight:600;font-size:18px;display:flex;align-items:center;gap:12px}
.banner.run{background:#0071bc1a;color:var(--a)}.banner.ok{background:#00a99d22;color:var(--ok)}.banner.err{background:#d6454522;color:var(--err)}
.banner small{display:block;font-weight:400;font-size:13.5px;color:var(--mut);margin-top:2px}
.spin{width:18px;height:18px;border:3px solid currentColor;border-right-color:transparent;border-radius:50%;animation:g 1s linear infinite;flex:none}@keyframes g{to{transform:rotate(360deg)}}
.chk li{grid-template-columns:28px 1fr;padding:5px 0}.chk li i{font-style:normal;text-align:center}.chk li.ok{color:var(--ok)}.chk li.run{color:var(--a);font-weight:600}
.reg li{grid-template-columns:70px 1fr;padding:4px 0;font-size:13.5px;color:var(--ink);border-bottom:1px solid var(--line)}.reg li b{text-align:left;color:var(--mut);font-weight:500;font-variant-numeric:tabular-nums}.reg li:first-child{color:var(--a);font-weight:600}
.procs li{grid-template-columns:1fr auto}.procs .none{color:var(--mut)}
.sis{background:#0d1117;color:#c9d1d9;border-color:#30363d;font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace}
.sis h2{color:#e6edf3;font:600 15px ui-monospace,monospace}.sis h2{white-space:nowrap}.sis .st{white-space:nowrap;font-size:12px}.sis .st{background:#1f6feb33;color:#58a6ff}
.sis canvas{width:100%;height:110px;display:block;margin:12px 0 10px;border:1px solid #30363d;border-radius:8px;background:#010409}
.sis .g{display:grid;grid-template-columns:repeat(2,1fr);gap:6px 18px}
.mt{display:grid;grid-template-columns:44px 1fr 96px;white-space:nowrap;align-items:center;gap:8px}.mt b{text-align:right;font-weight:500;font-variant-numeric:tabular-nums}
.mb{height:10px;min-width:40px;border-radius:2px;background:#21262d;overflow:hidden}.mb i{display:block;height:100%;width:0;transition:width .6s ease,background .6s}
.sis h3{font:600 12.5px ui-monospace,monospace;color:#8b949e;margin:14px 0 6px;text-transform:uppercase;letter-spacing:.06em}
.sis table{margin-top:0;font-size:12.5px}.sis th,.sis td{border-color:#21262d;padding:3px 6px}.sis th{color:#8b949e}













#sinCx{position:fixed;top:0;right:0;bottom:0;left:0;z-index:10000;display:none;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:16px;background:var(--bg)}
#sinCx.on{display:flex}#sinCx h2{margin:10px 0 6px;font-size:30px}#sinCx p{margin:0;color:var(--mut);max-width:420px;font-size:15px}
#sinCx svg{width:240px;max-width:70vw;height:auto}
#sinCx .respira{animation:sxR 3.2s ease-in-out infinite;transform-origin:130px 190px}@keyframes sxR{50%{transform:scale(1.035,.975)}}
#sinCx .z{font-weight:800;fill:var(--mut);opacity:0;animation:sxZ 3.6s ease-in infinite}#sinCx .z2{animation-delay:1.2s}#sinCx .z3{animation-delay:2.4s}
@keyframes sxZ{0%{opacity:0;transform:translate(0,0) scale(.6)}20%{opacity:1}100%{opacity:0;transform:translate(26px,-60px) scale(1.25)}}




















#minaV{margin-bottom:12px;padding:10px}#minaV #minaS{width:100%;height:auto;display:block;border-radius:10px;user-select:none}
#minaV .obj,#minaV .gema,#minaV .carro,#minaV .tarea{cursor:pointer}#minaV .obj:focus,#minaV .gema:focus,#minaV .tarea:focus{outline:none}
#minaV .obj:hover .cristales,#minaV .obj:focus .cristales{filter:brightness(1.25)}#minaV .gema:hover{filter:brightness(1.3)}
#minaV .escoba,#minaV .drvO{cursor:pointer}.mDrvB{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0 4px}.mDrvB .drv{margin:0}#minaV .drvO:hover circle{fill:#1557b0}.mConf{position:fixed;top:0;right:0;bottom:0;left:0;z-index:10002;display:flex;align-items:center;justify-content:center;background:#0b0d1f99;padding:16px}.mConf .mModal{width:min(340px,100%);text-align:center}.mConf .mModal p{margin:0 0 14px;color:var(--mut);font-size:14px;line-height:1.4}.mConf .bot{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}.mConf button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:9px;padding:9px 16px;font-size:15px;font-weight:600;cursor:pointer;min-width:120px}.mConf button.si{background:var(--a);border-color:var(--a);color:#fff}#minaV .escoba:hover circle,#minaV .escoba:focus circle{fill:#ffe9a8}#minaV .rn,#minaV .rp{paint-order:stroke;stroke:#1d120b;stroke-width:3px;stroke-linejoin:round}#minaV .tarea:hover .rocaF{stroke:#fff}#minaV .rocaS{transition:transform .8s ease}#minaV .tarea:hover rect{stroke:#fff}#minaV .sel .aro{stroke:#fff}#minaV .pollo{transition:transform 1.2s ease}
#minaV .pico{transform-box:fill-box;transform-origin:0% 100%;animation:mPico .7s ease-in-out infinite}
#minaV .cuerpoP{animation:mBote .7s ease-in-out infinite}
#minaV .quieto .pico{animation:none;transform:rotate(-20deg)}#minaV .quieto .cuerpoP{animation:none}
#minaV .quieto .tierra{display:none}#minaV .fiesta .cuerpoP{animation:mSalto 1s ease-in-out infinite}
#minaV .tierra circle{animation:mTierra .7s ease-out infinite;opacity:0}
#minaV .tierra circle:nth-child(2){animation-delay:.12s}#minaV .tierra circle:nth-child(3){animation-delay:.24s}#minaV .tierra circle:nth-child(4){animation-delay:.36s}
#minaV .brillo{animation:mBrillo 2.4s ease-in-out infinite}
#minaV .sudor{display:none}#minaV .suda .sudor{display:inline}
#minaV .sudor path{animation:mGota 1.1s ease-in infinite;opacity:0}#minaV .sudor path:nth-child(2){animation-delay:.35s}#minaV .sudor path:nth-child(3){animation-delay:.7s}
#minaV .nube{display:none}#minaV .piensa .nube{display:inline}
#minaV .cerebro{transform-box:fill-box;transform-origin:50% 50%;animation:mLatido .9s ease-in-out infinite}
#minaV .rayas{animation:mRayas 1s linear infinite}
#minaV .ahora rect{stroke:#ffd23f;stroke-width:2}
@keyframes mPico{0%,100%{transform:rotate(-40deg)}45%,55%{transform:rotate(48deg)}}
@keyframes mBote{0%,100%{transform:translateY(0)}50%{transform:translateY(1.5px)}}
@keyframes mSalto{0%,100%{transform:translateY(0)}40%{transform:translateY(-14px)}}
@keyframes mTierra{0%{opacity:1;transform:translate(0,0)}100%{opacity:0;transform:translate(var(--dx),var(--dy))}}
@keyframes mBrillo{0%,100%{opacity:.15}50%{opacity:.9}}
@keyframes mGota{0%{opacity:0;transform:translate(0,0)}15%{opacity:1}100%{opacity:0;transform:translate(var(--gx),16px)}}
@keyframes mLatido{0%,100%{transform:scale(1)}15%{transform:scale(1.16)}30%{transform:scale(.97)}45%{transform:scale(1.1)}}
@keyframes mRayas{to{transform:translateX(16px)}}
@media (prefers-reduced-motion:reduce){#minaV .pico,#minaV .cuerpoP,#minaV .tierra circle,#minaV .brillo,#minaV .sudor path,#minaV .cerebro,#minaV .rayas{animation:none}#minaV .sudor path{opacity:1}}
#minaDet{margin-top:10px;font-size:13px}#minaDet h3{margin:0 0 6px;font-size:15px}#minaDet .vacio{color:var(--mut);margin:4px 2px}
#minaDet .objD{border:1px solid var(--line);border-radius:10px;padding:8px 12px;margin:0 0 8px}
#minaDet .objD h4{margin:0 0 4px;font-size:14px;display:flex;justify-content:space-between;gap:8px}
#minaDet ul{list-style:none;margin:0;padding:0}#minaDet li{padding:2px 0;display:grid;grid-template-columns:22px 1fr auto;gap:6px}
.minaBar{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:0 0 8px}.minaBar b{font-size:14px}
.minaBar button,.mModal button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:8px;padding:5px 12px;font-size:13px;cursor:pointer;font-weight:600}
.minaBar button:hover,.mModal button:hover{border-color:var(--a);color:var(--a)}
.minaMapa{position:relative;min-height:0}
#minaModal{position:absolute;top:0;right:0;bottom:0;left:0;display:flex;align-items:center;justify-content:center;background:#0b0d1f99;border-radius:10px;padding:12px;z-index:5}
#minaModal[hidden]{display:none}
.mModal{background:var(--card);color:var(--ink);border-radius:14px;box-shadow:0 12px 40px #0008;padding:16px 18px;width:min(460px,100%);max-height:100%;overflow:auto}
.mModal .mObj{font-size:12px;color:var(--mut);margin:0 0 2px}.mModal h3{margin:0 0 10px;font-size:17px;line-height:1.3}
.mModal .mPct{display:flex;align-items:center;gap:10px;margin:6px 0 10px}.mModal .mPct b{font-size:26px;min-width:76px}
.mModal .mBar{flex:1;height:14px;border-radius:8px;background:var(--line);overflow:hidden}.mModal .mBar i{display:block;height:100%;background:linear-gradient(90deg,var(--a),var(--ok));transition:width .6s}
.mModal .mEst{display:inline-block;font-size:12px;font-weight:700;padding:2px 10px;border-radius:20px;margin-bottom:8px}
.mModal .e0{background:#8882;color:var(--mut)}.mModal .e1{background:#0071bc22;color:var(--a)}.mModal .e2{background:#00a99d22;color:var(--ok)}
.mModal dl{margin:6px 0 12px;font-size:13px;display:grid;grid-template-columns:auto 1fr;gap:4px 10px}.mModal dt{color:var(--mut)}.mModal dd{margin:0;overflow-wrap:anywhere}
.mModal .mAcc{display:flex;justify-content:flex-end;gap:8px}
.mFsSalir{display:none}#minaV .mFsSalir svg{width:18px;height:18px;display:block}
#minaMapa:fullscreen{display:block;width:100vw;height:100vh;height:100dvh;padding:0;margin:0;background:#4a301e;overflow:hidden}#minaMapa:-webkit-full-screen{display:block;width:100vw;height:100vh;height:100dvh;padding:0;margin:0;background:#4a301e;overflow:hidden}#minaMapa.fsPseudo{display:block;width:100vw;height:100vh;height:100dvh;padding:0;margin:0;background:#4a301e;overflow:hidden}
#minaMapa.fsPseudo{position:fixed;top:0;right:0;bottom:0;left:0;width:100%;height:100%;z-index:9999}
#minaMapa:fullscreen #minaS{width:100%!important;height:100%!important;border-radius:0}#minaMapa:-webkit-full-screen #minaS{width:100%!important;height:100%!important;border-radius:0}#minaMapa.fsPseudo #minaS{width:100%!important;height:100%!important;border-radius:0}
#minaMapa:fullscreen #minaModal{border-radius:0}#minaMapa:-webkit-full-screen #minaModal{border-radius:0}#minaMapa.fsPseudo #minaModal{border-radius:0}
#minaMapa:fullscreen .mFsSalir{display:flex;position:absolute;top:10px;right:10px;z-index:4;width:32px;height:32px;padding:0;border:0;border-radius:50%;align-items:center;justify-content:center;background:#00000040;color:#fff;cursor:pointer;opacity:.5;transition:opacity .2s,background .2s}#minaMapa:-webkit-full-screen .mFsSalir{display:flex;position:absolute;top:10px;right:10px;z-index:4;width:32px;height:32px;padding:0;border:0;border-radius:50%;align-items:center;justify-content:center;background:#00000040;color:#fff;cursor:pointer;opacity:.5;transition:opacity .2s,background .2s}#minaMapa.fsPseudo .mFsSalir{display:flex;position:absolute;top:10px;right:10px;z-index:4;width:32px;height:32px;padding:0;border:0;border-radius:50%;align-items:center;justify-content:center;background:#00000040;color:#fff;cursor:pointer;opacity:.5;transition:opacity .2s,background .2s}
#minaMapa.girado #minaS{position:absolute;top:50%;left:50%;width:100vh!important;width:100dvh!important;height:100vw!important;transform:translate(-50%,-50%) rotate(90deg)}
#minaMapa .mFsSalir:hover,#minaMapa .mFsSalir:focus-visible{opacity:1;background:#00000080;outline:none}
.mModal .mDet ul{list-style:none;margin:0 0 10px;padding:0;font-size:13px}.mModal .mDet li{display:grid;grid-template-columns:22px 1fr auto;gap:6px;padding:2px 0}
.mModal .mDet li small{grid-column:2/4;color:var(--mut)}.mModal .mDet h4{margin:8px 0 4px;font-size:14px;display:flex;justify-content:space-between}
.frente{display:none}.atiende .frente{display:inline}.atiende .lado{display:none}
#minaV .globo{cursor:pointer;animation:mGlobo 1.6s ease-in-out infinite}#minaV .globo:hover rect{fill:#fff8d6}
#minaV .saludo{transform-box:fill-box;transform-origin:0% 100%;animation:mSaludo .9s ease-in-out infinite}
#minaV .atiende .cuerpoF{animation:mSalto 1.4s ease-in-out infinite}
@keyframes mGlobo{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}
@keyframes mSaludo{0%,100%{transform:rotate(0)}50%{transform:rotate(-25deg)}}
.mModal .mAccion{border-left:4px solid #ff8a00;background:#ff8a0014;border-radius:8px;padding:8px 12px;margin:0 0 8px}.mModal .mAccion b{display:block;font-size:15px}
.mModal .mAccion p{margin:4px 0 0;font-size:13.5px}.mModal .mAccion small{color:var(--mut);font-size:11.5px}
#minaV .brazoQuieto{display:none}#minaV .quieto .brazoAnim{display:none}#minaV .quieto .brazoQuieto{display:inline}
#minaDet li small{grid-column:2/4;color:var(--mut);margin-top:-2px}#minaDet .meta{color:var(--mut);font-size:12px;margin:2px 0 6px}
</style></head><body><div id="sinCx" role="status" aria-live="polite"><svg viewBox="0 0 260 240" aria-label="Pollito durmiendo">
<text class="z" x="178" y="70" font-size="26">Z</text><text class="z z2" x="190" y="58" font-size="20">z</text><text class="z z3" x="200" y="48" font-size="16">z</text>
<ellipse cx="130" cy="222" rx="78" ry="9" fill="#000" opacity=".08"/><g class="respira"><ellipse cx="130" cy="160" rx="80" ry="64" fill="#ffd23f"/>
<path d="M92 158 q-30 6 -26 32 q22 4 42 -14 z" fill="#f5c11c"/><circle cx="150" cy="112" r="46" fill="#ffd23f"/>
<path d="M146 68 q-6 -18 6 -22 q-2 12 8 16 q-6 -14 8 -16 q-4 14 -8 24 z" fill="#f5c11c"/>
<path d="M128 110 q8 7 16 0" stroke="#3b2f20" stroke-width="3.5" fill="none" stroke-linecap="round"/><path d="M160 110 q8 7 16 0" stroke="#3b2f20" stroke-width="3.5" fill="none" stroke-linecap="round"/>
<ellipse cx="128" cy="126" rx="7" ry="4.5" fill="#ff9e7a" opacity=".7"/><ellipse cx="180" cy="126" rx="7" ry="4.5" fill="#ff9e7a" opacity=".7"/>
<path d="M146 122 l16 0 l-8 10 z" fill="#f59e0b"/><path d="M112 86 q30 -46 78 -14 q-34 -6 -54 22 z" fill="#5b7bd5"/><circle cx="194" cy="74" r="8" fill="#fff"/>
<path d="M110 220 l-6 8 m6 -8 l0 9 m0 -9 l6 8" stroke="#f59e0b" stroke-width="4" stroke-linecap="round"/><path d="M150 220 l-6 8 m6 -8 l0 9 m0 -9 l6 8" stroke="#f59e0b" stroke-width="4" stroke-linecap="round"/></g></svg>
<h2>Sin Conexión</h2><p>La computadora de trabajo no está transmitiendo el avance en este momento. La página se reconecta sola.</p></div><main>
<h1 id="tit">Avance en vivo</h1><p class="sub">Avance en vivo</p>
<section id="acc" role="alert" aria-live="assertive"><h2 id="accT">✅ Acciones pendientes: ninguna</h2><div id="accL"></div><details id="accH"><summary>Acciones ya resueltas</summary><ul id="accHL"></ul></details></section>
<div class="tot"><span>Total: <b id="tot">0%</b> <button class="plegar" id="plegarT">Plegar todo</button><button class="plegar" id="abrirT">Abrir todo</button><span class="vistas" id="vistas"><button data-v="tarjetas">Tarjetas</button><button data-v="tabla">Tabla</button><button data-v="tablero">Tablero</button><button data-v="mina">Mina</button></span></span><span><span class="live" id="live"><i></i><span id="lt">conectando</span></span> · <span id="tm"></span></span></div>
<div class="banner run" id="ban"><span class="spin" id="spin"></span><div><span id="bt">Conectando</span><small id="bs"></small></div></div>
<div class="cols"><div class="izq">
<section class="card" id="chk"><header><h2>Registro de actividad</h2><span class="st run" id="chkN"></span></header><h3 style="margin:10px 0 4px;font-size:13px">Pasos del pedido</h3><ul id="chkL" class="chk"></ul><p id="ahora" style="margin:12px 0 6px;font-weight:600"></p><ul id="reg" class="reg"></ul></section>
<div id="langs"></div>
<div id="tablero" class="hide"><div class="col"><h3>Por hacer <span id="n_hacer"></span></h3><div id="col_hacer"></div></div><div class="col"><h3>En progreso <span id="n_prog"></span></h3><div id="col_prog"></div></div><div class="col"><h3>Finalizado <span id="n_fin"></span></h3><div id="col_fin"></div></div></div>
<section id="tablaV" class="card fija hide"><table><thead><tr><th>Idioma</th><th>Estado</th><th>Avance</th><th>Va por</th><th>Drive</th></tr></thead><tbody id="tablaB"></tbody></table></section>
<section id="minaV" class="card fija hide"><div class="minaBar"><b>⛏ Mina del avance</b><button id="minaFS" type="button" aria-pressed="false">⛶ Pantalla completa</button></div><div class="minaMapa" id="minaMapa"><button id="minaFSsalir" class="mFsSalir" type="button" title="Salir de pantalla completa" aria-label="Salir de pantalla completa"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5"/></svg></button><svg id="minaS" role="img" aria-label="Mina del avance"></svg><div id="minaModal" hidden role="dialog" aria-modal="true" aria-labelledby="mTit"><div class="mModal" id="mCont"></div></div></div><div id="minaDet"><p class="vacio">Toque un objetivo, una tarea o el carro minero para ver el detalle.</p></div></section>
</div><div class="der">
<section class="card sis" id="sisC"><header><h2>CPU y memoria</h2><span class="st" id="carga">CPU – · RAM –</span></header>
<canvas id="cg" width="840" height="110"></canvas>
<div class="mt" style="margin-bottom:8px"><span>CPU</span><div class="mb"><i id="cpuT"></i></div><b id="cpuTv">0%</b></div>
<div class="g" id="cores"></div>
<h3>Memoria</h3>
<div class="mt"><span>RAM</span><div class="mb"><i id="ram"></i></div><b id="ramv">–</b></div>
<div class="mt" style="margin-top:6px"><span>Swap</span><div class="mb"><i id="swp"></i></div><b id="swpv">–</b></div>
<h3>Procesos que más consumen</h3>
<div class="tabla5"><table><thead><tr><th>Proceso</th><th>RAM</th><th>CPU del equipo</th></tr></thead><tbody id="top"></tbody></table></div></section>
<section class="card" id="procsC"><header><h2>Procesos activos en el equipo</h2><span class="st run" id="np">0</span></header><ul class="procs" id="procs"></ul></section>
</div></div></main>
<script>
const $ = s => document.querySelector(s), esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function tarjeta(L) {
  const c = document.createElement('section'); c.className = 'card'; c.id = 'c_' + L;
  c.innerHTML = `<header><h2 class="n"></h2><span class="st run">En curso</span></header>
  <div class="big"><div class="bar"><i></i></div><b class="p">0%</b></div><div class="va"></div><a class="drv hide" target="_blank" rel="noopener">▶ Ver en Drive</a><ul></ul>
  <table class="hide"><thead><tr><th>#</th><th>Frase</th><th>Verif.</th></tr></thead><tbody></tbody></table><p class="warn hide"></p>`;
  $('#langs').appendChild(c); restaurar(c); return c;
}
const colorPct = p => p < 50 ? '#3fb950' : p < 80 ? '#d29922' : '#f85149';   // verde · ámbar · rojo, como btop
function barra(id, p, txt) { const i = $('#' + id); i.style.width = Math.min(100, p) + '%'; i.style.background = colorPct(p); $('#' + id + 'v').textContent = txt; }
function sistema(S) {
  if (!S || !S.cpu) return;
  barra('cpuT', S.total, S.total.toFixed(0) + '%');
  const co = $('#cores');
  S.cpu.forEach((p, i) => { let d = document.getElementById('core' + i);
    if (!d) { d = document.createElement('div'); d.className = 'mt'; d.innerHTML = `<span>C${i}</span><div class="mb"><i id="core${i}"></i></div><b id="core${i}v"></b>`; co.appendChild(d); }
    barra('core' + i, p, p.toFixed(0) + '%'); });
  const [mu, mt] = S.mem, [su, st] = S.swap;
  barra('ram', 100 * mu / mt, `${mu.toFixed(1)}/${mt.toFixed(1)} G`);
  barra('swp', st ? 100 * su / st : 0, st ? `${su.toFixed(1)}/${st.toFixed(1)} G` : 'sin swap');
  $('#carga').textContent = `CPU ${S.total.toFixed(0)} % · RAM ${mu.toFixed(1)} / ${mt.toFixed(1)} GB`;   // la «carga» (load average) no se entendía
  $('#top').innerHTML = S.top.length ? S.top.map(([c, n, r]) => `<tr><td>${esc(n)}</td><td>${r >= 1024 ? (r / 1024).toFixed(1) + ' G' : r + ' M'}</td><td style="color:${colorPct(c)}">${c.toFixed(0)}% <small style="color:#8b949e">(${(c * S.cpu.length / 100).toFixed(1)} núcl.)</small></td></tr>`).join('') : '<tr><td colspan="3">en reposo</td></tr>';
  // historial de 120 s: columnas por segundo, coloreadas por nivel (estilo btop)
  const cv = $('#cg'), W = cv.clientWidth || 840, H = 110, dpr = window.devicePixelRatio || 1;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const g = cv.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
  g.strokeStyle = '#21262d'; g.lineWidth = 1; [25, 50, 75].forEach(y => { g.beginPath(); g.moveTo(0, H - y / 100 * H + .5); g.lineTo(W, H - y / 100 * H + .5); g.stroke(); });
  const n = 120, bw = W / n; S.hist.forEach((p, k) => { const x = W - (S.hist.length - k) * bw, h = Math.max(1, p / 100 * (H - 4));
    const gr = g.createLinearGradient(0, H, 0, H - h); gr.addColorStop(0, '#3fb950'); if (p > 50) gr.addColorStop(Math.min(1, 50 / p), '#d29922'); if (p > 80) gr.addColorStop(Math.min(1, 80 / p), '#f85149');
    g.fillStyle = gr; g.fillRect(x + .5, H - h, Math.max(1, bw - 1), h); });
  g.fillStyle = '#8b949e'; g.font = '11px ui-monospace,monospace'; g.fillText('CPU total · últimos 2 min', 8, 14); g.fillText('100%', W - 34, 12);
}
let tituloBase = '', parpadeo = null;
// texto con enlaces: cada dirección web se puede abrir y copiar con un botón
function enlaces(t) { return esc(t).replace(/https?:\/\/[^\s<]+/g, u => `<a class="accA" href="${u}" target="_blank" rel="noopener">${u}</a> <button type="button" class="accC" data-u="${u}">📋 Copiar enlace</button>`); }
function copiarTexto(u, btn) {
  const listo = () => { btn.textContent = '✔ Copiado'; setTimeout(() => { btn.textContent = '📋 Copiar enlace'; }, 2500); };
  if (navigator.clipboard && window.isSecureContext) { navigator.clipboard.writeText(u).then(listo, () => viejo()); } else viejo();
  function viejo() { const x = document.createElement('textarea'); x.value = u; x.setAttribute('readonly', ''); x.style.position = 'fixed'; x.style.top = '-1000px'; document.body.appendChild(x);
    x.select(); x.setSelectionRange(0, u.length); try { document.execCommand('copy'); listo(); } catch (e) { prompt('Copie el enlace:', u); } document.body.removeChild(x); }
}
document.addEventListener('click', ev => { const b = ev.target.closest && ev.target.closest('.accC'); if (b) { ev.preventDefault(); ev.stopPropagation(); copiarTexto(b.dataset.u, b); } });
function acciones(A, H) {
  A = A || []; H = H || []; $('#acc').classList.toggle('on', A.length > 0);
  $('#accT').textContent = A.length ? `⚠ ACCIÓN PENDIENTE: necesito que hagas ${A.length > 1 ? 'esto (' + A.length + ')' : 'esto'}` : '✅ Acciones pendientes: ninguna';
  const accHtml = A.map(([h, t, c]) => `<div class="accI"><b>👉 ${enlaces(t)}</b>${c ? `<span>${enlaces(c)}</span>` : ''}<small>pendiente desde las ${h}</small></div>`).join('');
  if ($('#accL').dataset.h !== accHtml) { $('#accL').innerHTML = accHtml; $('#accL').dataset.h = accHtml; }   // redibujar siempre borraba la selección y no dejaba copiar
  $('#accH').style.display = H.length ? '' : 'none';
  $('#accHL').innerHTML = H.slice().reverse().map(([d, h, t]) => `<li>✔ ${esc(t)} <small>(pedida ${d}, resuelta ${h})</small></li>`).join('');
  if (A.length && !parpadeo) parpadeo = setInterval(() => { document.title = document.title.startsWith('⚠') ? tituloBase : `⚠ ACCIÓN PENDIENTE (${A.length})`; }, 1000);
  if (!A.length && parpadeo) { clearInterval(parpadeo); parpadeo = null; document.title = tituloBase; }
}
// ---- vistas del avance: tarjetas · tabla · tablero (se recuerda por navegador)
let VISTA = (() => { try { return localStorage.getItem('avance_vista') || 'tarjetas'; } catch (e) { return 'tarjetas'; } })();
const abiertasT = new Set(); let ULTIMO = null;
const columna = e => e.ok && (e.drive || e.tarea) ? 'fin' : (e.pct === 0 && !e.pasos.some(p => p[1] > 0)) ? 'hacer' : 'prog';
// Columna «Va por»: SOLO el paso que de verdad está en curso (0 < avance < 100), sin prefijo. Si nada corre: «Próximamente: <paso siguiente>».
const enCurso = e => e.pasos.find(p => p[1] > 0 && p[1] < 100);
const vaPor = e => { const cur = e.pasos.find(p => p[1] < 100), act = enCurso(e);
  if (e.tarea && e.ok) return '✔ Terminada';
  if (e.ok && (!cur || cur[0] === 'Subida a Drive')) return e.drive ? '✔ Listo y en Drive' : '✔ Listo · falta subir a Drive';
  if (act) return `${act[0]}${act[2] ? ' · ' + act[2] : ' · ' + act[1] + '%'}`;
  return cur ? `Próximamente: ${cur[0]}` : ''; };


































// ---- vista «Mina»: el pollito cava tarea por tarea hacia cada objetivo; lo terminado va al carro
const MINA = {key: '', sel: null, E: null};
const COLG = ['#3fb6ff', '#ff5d8f', '#7ee081', '#ffb547', '#b18cff', '#4fd1c5', '#ff7a45', '#f5e663'];
const finM = e => e.ok && (e.drive || e.tarea) || e.pct >= 100;
const corto = (s, n) => s.length > n ? s.slice(0, n - 1) + '…' : s;
const nomTarea = s => s.replace(/:\s.*$/, '').trim();   // «Voz: 7 de 34 frases» → «Voz»; «0:20 · …» queda igual
const sv = (tag, at, padre) => { const el = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const k in at) el.setAttribute(k, at[k]); if (padre) padre.appendChild(el); return el; };
let NIVEL = 170; const X0 = 110, XF = 840;    // pique en X0; cada galería llega al objetivo en XF
// la escena llena TODA la pantalla disponible (14/11: «verifica que siempre tome toda la pantalla»): el alto del mapa es el de la
// ventana y la separación entre galerías se estira para ocupar ese alto (150–320), sin deformar ni cortar nada
function minaCaja() {
  const m = $('#minaMapa'); if (!m) return {w: 1000, h: 600};
  if (minaEnFS()) { const r = m.getBoundingClientRect(), gir = m.classList.contains('girado'); return gir ? {w: r.height, h: r.width} : {w: r.width, h: r.height}; }
  const w = Math.max(320, m.getBoundingClientRect().width || m.parentElement.clientWidth || 1000);
  return {w, h: Math.max(340, innerHeight - 64)};
}
// alto de la escena: 200 (cielo + primera galería) + una separación por galería extra + 150 de tierra para los rótulos de abajo
const minaAlto = n => 200 + (Math.max(n, 1) - 1) * NIVEL + 150;
// separación fija entre galerías (14/11: estirarla dejaba los objetivos muy distantes y espacio sobrante arriba y abajo);
// en pantalla completa se permite un poco más (hasta 230) para usar el alto sin separarlos de más
function minaNivel(n) { if (n < 2 || !minaEnFS()) return 170; const c = minaCaja(), Hob = 1000 * c.h / c.w; return Math.round(Math.max(150, Math.min(230, (Hob - 350) / (n - 1)))); }
const minaClave = E => E.idiomas.map(e => e.L + ':' + e.pasos.length).join('|') + '#' + minaNivel(Math.max(E.idiomas.length, 1));
// los rótulos nunca se cortan ni llevan «…»: se reparten en líneas por palabras
function minaLineas(t, n) { const L = []; let a = ''; String(t).split(/\s+/).forEach(p => { if (a && (a + ' ' + p).length > n) { L.push(a); a = p; } else a = a ? a + ' ' + p : p; }); if (a) L.push(a); return L; }
function minaTexto(el, L, x, y0, dy) { el.textContent = ''; L.forEach((l, i) => { const t = sv('tspan', {x, y: y0 + i * dy}, el); t.textContent = l; }); }
// excavación con lógica: completas las tareas anteriores a la que está en curso + el % de esa
function cavado(e) {
  const P = e.pasos, k = P.length; if (!k) return {f: e.pct / 100, act: -1};
  if (finM(e)) return {f: 1, act: -1};
  let act = P.findIndex(p => p[1] > 0 && p[1] < 100);
  if (act < 0) act = P.findIndex(p => p[1] < 100);
  if (act < 0) return {f: 1, act: -1};
  return {f: (act + P[act][1] / 100) / k, act};
}
function minaArmar(E) {
  const s = $('#minaS'); s.innerHTML = ''; const n = E.idiomas.length; NIVEL = minaNivel(Math.max(n, 1)); const H = minaAlto(n);
  s.setAttribute('viewBox', `0 0 1000 ${H}`); MINA.H = H;
  sv('defs', {}, s).innerHTML = `<pattern id="mPiedra" patternUnits="userSpaceOnUse" width="34" height="34"><rect width="34" height="34" fill="#6e4b2e"/><ellipse cx="7" cy="8" rx="5.5" ry="3.8" fill="#8d8178" stroke="#4a3a30" stroke-width=".8"/><ellipse cx="24" cy="20" rx="6.5" ry="4.2" fill="#7a6f66" stroke="#4a3a30" stroke-width=".8"/><ellipse cx="12" cy="27" rx="3.8" ry="2.6" fill="#9b8f86" stroke="#4a3a30" stroke-width=".6"/><circle cx="28" cy="6" r="2" fill="#5a3b22"/><circle cx="18" cy="12" r="1.6" fill="#4d321d"/><circle cx="30" cy="30" r="1.4" fill="#8a6440"/><circle cx="3" cy="19" r="1.5" fill="#8a6440"/></pattern><linearGradient id="mCielo" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8fd3ff"/><stop offset="1" stop-color="#d9f1ff"/></linearGradient>
    <linearGradient id="mTierraG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9a6b43"/><stop offset=".35" stop-color="#7b5233"/><stop offset="1" stop-color="#4a301e"/></linearGradient>
    <radialGradient id="mLuz"><stop offset="0" stop-color="#fff3a8" stop-opacity=".55"/><stop offset="1" stop-color="#fff3a8" stop-opacity="0"/></radialGradient>
    <pattern id="mRay" width="16" height="16" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="16" fill="#ffffff33"/></pattern>`;
  sv('rect', {x: -3000, y: -3000, width: 7000, height: 3112, fill: '#d9f1ff'}, s); sv('rect', {x: -3000, y: 0, width: 7000, height: 112, fill: 'url(#mCielo)'}, s);
  sv('circle', {cx: 960, cy: 30, r: 18, fill: '#ffe066'}, s);
  sv('rect', {x: -3000, y: 110, width: 7000, height: H - 110, fill: 'url(#mTierraG)'}, s); sv('rect', {x: -3000, y: H - 1, width: 7000, height: 3000, fill: '#4a301e'}, s);
  sv('rect', {x: -3000, y: 106, width: 7000, height: 8, fill: '#5fb04a'}, s);
  for (let k = 0; k < 4; k++) { const y = 170 + k * (H - 170) / 4; sv('path', {d: `M0 ${y} Q 250 ${y - 10} 500 ${y + 8} T 1000 ${y - 2}`, stroke: '#00000022', 'stroke-width': 3, fill: 'none'}, s); }
  let sem = 7; const rnd = () => (sem = (sem * 9301 + 49297) % 233280) / 233280;
  for (let k = 0; k < 50; k++) sv('ellipse', {cx: rnd() * 1000, cy: 125 + rnd() * (H - 135), rx: 3 + rnd() * 9, ry: 2 + rnd() * 6, fill: rnd() > .5 ? '#5c3d27' : '#a37a55', opacity: .5}, s);
  sv('path', {d: 'M78 112 L78 78 Q110 52 142 78 L142 112 Z', fill: '#24170f', stroke: '#8a5a2b', 'stroke-width': 6}, s);
  sv('rect', {x: 70, y: 70, width: 80, height: 9, rx: 2, fill: '#8a5a2b'}, s);
  // avance total: etiqueta discreta arriba a la izquierda, con el estilo del panel de CPU / RAM
  const pt = sv('g', {transform: 'translate(14 10)'}, s);
  sv('rect', {x: 0, y: 0, width: 168, height: 32, rx: 8, fill: '#0d1117c4'}, pt);
  sv('text', {x: 10, y: 15, 'font-size': 10, 'font-weight': 700, fill: '#8b949e', 'letter-spacing': '.06em', 'font-family': 'ui-monospace,monospace'}, pt).textContent = 'AVANCE TOTAL';
  const tv = sv('text', {x: 158, y: 17, 'text-anchor': 'end', 'font-size': 14, 'font-weight': 800, fill: '#ffd23f', 'font-family': 'ui-monospace,monospace'}, pt);
  sv('rect', {x: 10, y: 22, width: 148, height: 4, rx: 2, fill: '#21262d'}, pt);
  const cr = sv('rect', {x: 10, y: 22, width: 0, height: 4, rx: 2, fill: '#ffb000'}, pt);
  MINA.tot = {tv, cr};
  for (let x = 180; x <= 560; x += 22) sv('rect', {x, y: 104, width: 12, height: 5, fill: '#6b4a2b'}, s);
  sv('line', {x1: 170, y1: 104, x2: 570, y2: 104, stroke: '#9aa3ad', 'stroke-width': 3}, s);
  // medidores de CPU y RAM (barras animadas)
  const med = sv('g', {transform: 'translate(640 18)'}, s); MINA.med = {};
  sv('rect', {x: -10, y: -8, width: 300, height: 80, rx: 10, fill: '#0d1117d9'}, med);
  [['cpu', 'CPU', 14], ['ram', 'RAM', 46]].forEach(([k, t, y]) => {
    sv('text', {x: 0, y: y + 12, 'font-size': 13, 'font-weight': 700, fill: '#c9d1d9', 'font-family': 'ui-monospace,monospace'}, med).textContent = t;
    sv('rect', {x: 40, y, width: 180, height: 16, rx: 8, fill: '#21262d'}, med);
    const cl = sv('clipPath', {id: 'mClip' + k}, med), cr = sv('rect', {x: 40, y, width: 0, height: 16, rx: 8}, cl);
    const g = sv('g', {'clip-path': `url(#mClip${k})`}, med), bar = sv('rect', {x: 40, y, width: 180, height: 16, fill: '#3fb950'}, g);
    sv('rect', {x: 24, y, width: 220, height: 16, fill: 'url(#mRay)', class: 'rayas'}, g);
    const v = sv('text', {x: 228, y: y + 13, 'font-size': 12.5, fill: '#c9d1d9', 'font-family': 'ui-monospace,monospace'}, med);
    MINA.med[k] = {cr, bar, v};
  });
  const capT = sv('g', {}, s), capW = sv('g', {}, s), capO = sv('g', {}, s);
  const fondoP = 200 + (n - 1) * NIVEL + 10;
  sv('path', {d: `M${X0} 112 L${X0} ${fondoP}`, stroke: '#1d120b', 'stroke-width': 34, 'stroke-linecap': 'round'}, capT);
  sv('path', {d: `M${X0} 112 L${X0} ${fondoP}`, stroke: '#3a271a', 'stroke-width': 24, 'stroke-linecap': 'round'}, capT);
  for (let y = 130; y < fondoP; y += 26) sv('line', {x1: X0 - 12, y1: y, x2: X0 + 12, y2: y, stroke: '#8a5a2b', 'stroke-width': 3}, capT);
  MINA.gal = []; MINA.objs = [];
  E.idiomas.forEach((e, i) => {
    const y = 200 + i * NIVEL, col = COLG[i % COLG.length], dd = `M${X0} ${y} C ${X0 + 240} ${y + 22}, ${XF - 300} ${y - 22}, ${XF} ${y}`;
    // todo el tramo de cada actividad es tierra con piedras; el pollito lo va cavando y el túnel queda encima (14/11)
    sv('path', {d: dd, stroke: '#3b2716', 'stroke-width': 36, 'stroke-linecap': 'round', fill: 'none'}, capT);
    sv('path', {d: dd, stroke: 'url(#mPiedra)', 'stroke-width': 30, 'stroke-linecap': 'round', fill: 'none'}, capT);
    const fondo = sv('path', {d: dd, stroke: '#1d120b', 'stroke-width': 30, 'stroke-linecap': 'round', fill: 'none', pathLength: 1000, 'stroke-dasharray': '0 1000'}, capT);
    const luz = sv('path', {d: dd, stroke: '#3a271a', 'stroke-width': 20, 'stroke-linecap': 'round', fill: 'none', pathLength: 1000, 'stroke-dasharray': '0 1000'}, capT);
    const L = fondo.getTotalLength(), k = Math.max(1, e.pasos.length), pt = t => fondo.getPointAtLength(L * t);
    // tareas: un tramo por paso; poste al final de cada tramo y rótulo (arriba / abajo, alternado) en el medio
    const tareas = e.pasos.map((p, j) => {
      const fin = pt((j + 1) / k), mid = pt((j + .5) / k), arriba = j % 2 === 0, g = sv('g', {class: 'tarea', tabindex: 0, role: 'button'}, capW);
      g.dataset.l = e.L; g.dataset.j = j;
      const cam = sv('ellipse', {cx: mid.x, cy: mid.y, rx: 16, ry: 11, fill: '#3a271a', stroke: '#1d120b', 'stroke-width': 3, class: 'hide'}, g);
      if (j < k - 1) { sv('line', {x1: fin.x, y1: fin.y - 17, x2: fin.x, y2: fin.y + 17, stroke: '#8a5a2b', 'stroke-width': 4}, g); sv('line', {x1: fin.x - 8, y1: fin.y - 17, x2: fin.x + 8, y2: fin.y - 17, stroke: '#8a5a2b', 'stroke-width': 4}, g); }
      const ty = arriba ? mid.y - 50 : mid.y + 22, w = Math.min(Math.max(64, 860 / k - 10), 2 * (XF - 14 - mid.x)), et = sv('g', {}, g);   // no se monta sobre el rótulo del objetivo
      sv('line', {x1: mid.x, y1: arriba ? ty + 30 : ty, x2: mid.x, y2: arriba ? mid.y - 14 : mid.y + 14, stroke: '#ffffff55', 'stroke-width': 1.5, 'stroke-dasharray': '2 3'}, et);
      const r = sv('rect', {x: mid.x - w / 2, y: ty, width: w, height: 30, rx: 7, fill: '#000000a0'}, et);
      const tn = sv('text', {x: mid.x, y: ty + 12, 'text-anchor': 'middle', 'font-size': 10.5, fill: '#fff'}, et);
      const tp = sv('text', {x: mid.x, y: ty + 25, 'text-anchor': 'middle', 'font-size': 11, 'font-weight': 800, fill: col}, et);
      sv('rect', {x: mid.x - w / 2 + 4, y: ty + 27, width: w - 8, height: 2, fill: '#ffffff30'}, et);
      const tb = sv('rect', {x: mid.x - w / 2 + 4, y: ty + 27, width: 0, height: 2, fill: col}, et);
      const tt = sv('title', {}, g);
      // tarea sin terminar = roca en el camino que se achica con el avance (0 % entera); al 100 % se va y queda su tarjeta (14/11)
      const ro = sv('g', {transform: `translate(${mid.x} ${mid.y})`}, g), rs = sv('g', {class: 'rocaS'}, ro);
      sv('path', {class: 'rocaF', d: 'M-21 8 L-24 -3 L-15 -16 L-2 -21 L12 -17 L22 -6 L23 7 Z', fill: '#7d6a5c', stroke: '#3b2f27', 'stroke-width': 2.2, 'stroke-linejoin': 'round'}, rs);
      sv('path', {d: 'M-15 -14 L-3 -18 L8 -15 L-2 -9 Z', fill: '#a08b7a', opacity: .9}, rs);
      sv('path', {d: 'M-21 8 L23 7 L19 1 L-18 2 Z', fill: '#5b4a3e', opacity: .8}, rs);
      const rp = sv('text', {class: 'rp', x: 0, y: 2, 'text-anchor': 'middle', 'font-size': 10.5, 'font-weight': 800, fill: '#fff'}, ro);
      const rn = sv('text', {class: 'rn', 'text-anchor': 'middle', 'font-size': 10, 'font-weight': 600, fill: '#fff'}, g);
      return {g, cam, tn, tp, tb, tt, w, et, arriba, r, ty, mx: mid.x, my: mid.y, ro, rs, rp, rn};
    });
    MINA.gal.push({fondo, luz, L, tareas, y});
    // objetivo al final de la galería
    const g = sv('g', {class: 'obj', tabindex: 0, role: 'button', transform: `translate(${XF + 70} ${y})`}, capO); g.dataset.l = e.L;
    sv('circle', {r: 44, fill: 'url(#mLuz)', class: 'brillo'}, g);
    const cr = sv('g', {class: 'cristales'}, g);
    [[-14, 8, 16, 34], [4, 10, 20, 44], [20, 8, 14, 28]].forEach(([x, yy, w, h]) => sv('path', {d: `M${x} ${yy} L${x - w / 2} ${yy - h * .65} L${x} ${yy - h} L${x + w / 2} ${yy - h * .65} Z`, fill: col, stroke: '#ffffffaa', 'stroke-width': 1.5}, cr));
    const hueco = sv('g', {class: 'hide'}, g);   // objetivo alcanzado: el porcentaje logrado en el lugar de los cristales
    sv('circle', {r: 28, fill: '#1d120b', stroke: col, 'stroke-width': 2}, hueco);
    const logrado = sv('text', {x: 0, y: 3, 'text-anchor': 'middle', 'font-size': 15, 'font-weight': 800, fill: col}, hueco);
    sv('text', {x: 0, y: 14, 'text-anchor': 'middle', 'font-size': 6.2, 'font-weight': 700, fill: '#ffffffb0'}, hueco).textContent = 'LOGRADO';
    sv('circle', {r: 36, fill: 'none', stroke: '#00000055', 'stroke-width': 7}, g);
    const aro = sv('circle', {r: 36, fill: 'none', stroke: col, 'stroke-width': 7, 'stroke-linecap': 'round', pathLength: 100, 'stroke-dasharray': '0 100', transform: 'rotate(-90)', class: 'aro'}, g);
    const caja = sv('rect', {x: -60, y: -78, width: 120, height: 32, rx: 8, fill: '#000000b0'}, g);   // texto chico: no se monta sobre los demás (14/11)
    const nom = sv('text', {x: 0, y: -65, 'text-anchor': 'middle', 'font-size': 9.5, fill: '#fff', 'font-weight': 700}, g);
    const pct = sv('text', {x: 0, y: -52, 'text-anchor': 'middle', 'font-size': 10.5, fill: col, 'font-weight': 800}, g);
    const tt = sv('title', {}, g);
    // escobilla: solo en el objetivo terminado; el usuario decide si lo quita del mapa (14/11)
    const esc = sv('g', {class: 'escoba hide', role: 'button', tabindex: 0, transform: 'translate(56 0)'}, g); esc.dataset.l = e.L;   // a la derecha del círculo del 100 %
    sv('circle', {r: 13, fill: '#fff', stroke: '#2b2118', 'stroke-width': 2}, esc);
    sv('line', {x1: 6, y1: -7, x2: -1, y2: 2, stroke: '#8a5a2b', 'stroke-width': 2.6, 'stroke-linecap': 'round'}, esc);
    sv('path', {d: 'M-1 0 L3 4 L-3 10 L-9 4 Z', fill: '#e0a526', stroke: '#8a5a2b', 'stroke-width': 1.2, 'stroke-linejoin': 'round'}, esc);
    sv('path', {d: 'M-6 7 L-4 5 M-3 8 L-1 6', stroke: '#8a5a2b', 'stroke-width': 1}, esc);
    sv('title', {}, esc).textContent = 'Limpiar del mapa';
    const drv = sv('g', {class: 'drvO hide', role: 'button', tabindex: 0, transform: 'translate(-56 0)'}, g); drv.dataset.l = e.L;
    sv('circle', {r: 13, fill: '#1a73e8', stroke: '#fff', 'stroke-width': 2}, drv); sv('path', {d: 'M-4 -6 L7 0 L-4 6 Z', fill: '#fff'}, drv);
    sv('title', {}, drv).textContent = 'Ver video en Drive';
    MINA.objs.push({g, cr, hueco, logrado, aro, nom, pct, tt, col, caja, esc, drv});
  });
  const cg = sv('g', {class: 'carro', tabindex: 0, role: 'button', transform: 'translate(430 96)'}, s);
  MINA.gemas = sv('g', {}, cg);
  sv('path', {d: 'M-62 -50 L62 -50 L52 -6 L-52 -6 Z', fill: '#6b7280', stroke: '#374151', 'stroke-width': 3}, cg);
  sv('rect', {x: -66, y: -54, width: 132, height: 8, rx: 3, fill: '#4b5563'}, cg);
  [-30, 30].forEach(x => { sv('circle', {cx: x, cy: 0, r: 9, fill: '#1f2937'}, cg); sv('circle', {cx: x, cy: 0, r: 3, fill: '#9ca3af'}, cg); });
  MINA.carroT = sv('text', {x: 0, y: -24, 'text-anchor': 'middle', 'font-size': 13, fill: '#fff', 'font-weight': 700}, cg);
  // pollito minero (origen en las patas, mirando a la derecha); la nube y el sudor no se espejan
  MINA.extras = sv('g', {class: 'extras'}, s);   // pollitos de las tareas que se hacen al mismo tiempo
  const po = sv('g', {class: 'pollo'}, s); MINA.pollo = po; const pv = sv('g', {}, po); MINA.giro = pv;
  pv.innerHTML = `<ellipse cx="0" cy="2" rx="20" ry="4" fill="#00000055"/><g class="lado">
    <polygon points="24,-58 95,-80 95,-34" fill="#fff3a8" opacity=".12"/>
    <g class="cuerpoP">
      <path d="M-6 0 l-4 6 M-6 0 l0 7 M-6 0 l4 6 M8 0 l-4 6 M8 0 l0 7 M8 0 l4 6" stroke="#f59e0b" stroke-width="2.6" stroke-linecap="round"/>
      <ellipse cx="0" cy="-20" rx="21" ry="19" fill="#ffd23f"/>
      <circle cx="6" cy="-44" r="15" fill="#ffd23f"/>
      <circle cx="12" cy="-46" r="2.6" fill="#2b2118"/><circle cx="12.8" cy="-46.8" r=".8" fill="#fff"/>
      <ellipse cx="9" cy="-38" rx="4" ry="2.4" fill="#ff9e7a" opacity=".75"/>
      <path d="M20 -45 l9 3 l-9 3 z" fill="#f59e0b"/>
      <path d="M-10 -51 A16 14 0 0 1 23 -51 Z" fill="#ffb000" stroke="#c77c00" stroke-width="1.5"/>
      <rect x="-13" y="-53" width="40" height="5" rx="2.5" fill="#e09a00"/>
      <circle cx="22" cy="-57" r="4.5" fill="#fff6b0" stroke="#c77c00" stroke-width="1.2"/>
      <g class="sudor"><path d="M-8 -44 q-3 5 0 7 q3 -2 0 -7 z" fill="#7cc8ff" style="--gx:-6px"/><path d="M-4 -52 q-3 5 0 7 q3 -2 0 -7 z" fill="#7cc8ff" style="--gx:-10px"/><path d="M-11 -36 q-3 5 0 7 q3 -2 0 -7 z" fill="#7cc8ff" style="--gx:-4px"/></g>
      <!-- brazo: el ala sostiene el pico y gira desde el hombro (SMIL: anda también en Safari 12) -->
      <g class="brazoAnim"><g><line x1="13" y1="-18" x2="30" y2="-60" stroke="#8a5a2b" stroke-width="4" stroke-linecap="round"/>
          <path d="M16 -64 Q32 -69 47 -53 L43 -50 Q31 -61 19 -59 Z" fill="#9aa3ad" stroke="#5b636b" stroke-width="1.2"/>
          <path d="M-4 -33 Q8 -40 19 -33 Q23 -29 19 -25 Q8 -21 -4 -25 Z" fill="#fbcb30" stroke="#e8b52a" stroke-width=".8" stroke-opacity=".7"/>
          <ellipse cx="18" cy="-29" rx="3.2" ry="4" fill="#fbcb30" stroke="#e8b52a" stroke-width=".8" stroke-opacity=".7"/>
        <animateTransform attributeName="transform" type="rotate" values="-38 0 -29;52 0 -29;52 0 -29;-38 0 -29" keyTimes="0;0.38;0.6;1" dur="0.7s" repeatCount="indefinite"/></g></g>
      <g class="brazoQuieto" transform="rotate(-25 0 -29)"><line x1="13" y1="-18" x2="30" y2="-60" stroke="#8a5a2b" stroke-width="4" stroke-linecap="round"/>
          <path d="M16 -64 Q32 -69 47 -53 L43 -50 Q31 -61 19 -59 Z" fill="#9aa3ad" stroke="#5b636b" stroke-width="1.2"/>
          <path d="M-4 -33 Q8 -40 19 -33 Q23 -29 19 -25 Q8 -21 -4 -25 Z" fill="#fbcb30" stroke="#e8b52a" stroke-width=".8" stroke-opacity=".7"/>
          <ellipse cx="18" cy="-29" rx="3.2" ry="4" fill="#fbcb30" stroke="#e8b52a" stroke-width=".8" stroke-opacity=".7"/></g>
    </g>
    <g class="tierra"><circle cx="46" cy="-18" r="3" fill="#a37a55" style="--dx:18px;--dy:-14px"/><circle cx="46" cy="-14" r="2.5" fill="#7b5233" style="--dx:22px;--dy:-4px"/>
      <circle cx="44" cy="-20" r="2" fill="#c49a6c" style="--dx:12px;--dy:-22px"/><circle cx="48" cy="-12" r="2.2" fill="#5c3d27" style="--dx:26px;--dy:6px"/></g></g>
    <g class="frente"><g class="cuerpoF">
      <path d="M-8 0 l-4 6 M-8 0 l0 7 M-8 0 l4 6 M8 0 l-4 6 M8 0 l0 7 M8 0 l4 6" stroke="#f59e0b" stroke-width="2.6" stroke-linecap="round"/>
      <ellipse cx="0" cy="-20" rx="22" ry="19" fill="#ffd23f"/>
      <path d="M-20 -24 q-12 -2 -14 -14 q10 0 16 8 z" fill="#f2bf1c"/><g class="saludo"><path d="M20 -24 q12 -6 12 -20 q-12 2 -16 12 z" fill="#f2bf1c"/></g>
      <circle cx="0" cy="-46" r="16" fill="#ffd23f"/>
      <circle cx="-6" cy="-47" r="2.8" fill="#2b2118"/><circle cx="6" cy="-47" r="2.8" fill="#2b2118"/><circle cx="-5.2" cy="-48" r=".9" fill="#fff"/><circle cx="6.8" cy="-48" r=".9" fill="#fff"/>
      <ellipse cx="-11" cy="-40" rx="4" ry="2.4" fill="#ff9e7a" opacity=".75"/><ellipse cx="11" cy="-40" rx="4" ry="2.4" fill="#ff9e7a" opacity=".75"/>
      <path d="M-5 -42 l10 0 l-5 7 z" fill="#f59e0b"/>
      <path d="M-17 -54 A17 15 0 0 1 17 -54 Z" fill="#ffb000" stroke="#c77c00" stroke-width="1.5"/><rect x="-20" y="-56" width="40" height="5" rx="2.5" fill="#e09a00"/>
      <circle cx="0" cy="-62" r="4.5" fill="#fff6b0" stroke="#c77c00" stroke-width="1.2"/>
      <g transform="translate(-30 -6) rotate(-20)"><line x1="0" y1="0" x2="0" y2="-30" stroke="#8a5a2b" stroke-width="3.5" stroke-linecap="round"/><path d="M-12 -32 Q0 -38 12 -32 L10 -28 Q0 -33 -10 -28 Z" fill="#9aa3ad"/></g>
    </g></g>`;
  MINA.globo = sv('g', {class: 'globo', role: 'button', tabindex: 0}, po);
  const nb = sv('g', {class: 'nube'}, po);
  nb.innerHTML = `<circle cx="-4" cy="-66" r="3.5" fill="#fff" stroke="#333" stroke-width="1.5"/><circle cx="-10" cy="-78" r="5.5" fill="#fff" stroke="#333" stroke-width="1.5"/>
    <path d="M-52 -96 q-10 -22 12 -26 q6 -18 28 -12 q14 -14 30 0 q22 -4 20 18 q14 12 -4 24 q-4 16 -24 10 q-14 12 -30 0 q-26 6 -32 -14 z" fill="#fff" stroke="#333" stroke-width="2"/>
    <g class="cerebro"><path d="M-32 -110 q-2 -14 12 -16 q4 -8 14 -4 q10 -6 16 4 q12 2 10 14 q6 10 -4 16 q-2 10 -14 8 q-8 6 -16 0 q-14 2 -16 -10 q-8 -6 -2 -12 z" fill="#ff8fb1" stroke="#c2185b" stroke-width="1.8"/>
      <path d="M-22 -118 q6 4 2 10 M-8 -122 q-2 8 6 10 q6 2 4 10 M6 -114 q-6 6 0 12 M-24 -100 q8 -2 12 4 M2 -96 q4 -6 10 -2" stroke="#c2185b" stroke-width="1.5" fill="none" stroke-linecap="round"/></g>
    <text x="-2" y="-78" text-anchor="middle" font-size="9.5" font-weight="700" fill="#c2185b">RAM</text>`;
  MINA.key = minaClave(E);
}
function minaGlobo(acc, x, y) {
  const g = MINA.globo; if (!g) return;
  const clave = acc ? JSON.stringify(acc.map(a => a[1])) + '|' + Math.round(x / 40) + '|' + Math.round(y / 40) : '';
  if (clave === MINA.globoK) return; MINA.globoK = clave; g.innerHTML = '';
  if (!acc) return;
  const txt = acc.map(a => (acc.length > 1 ? '• ' : '') + a[1]).join(' ');
  const lin = [acc.length > 1 ? `¡Necesito su ayuda! (${acc.length})` : '¡Necesito su ayuda!']; let l = '';
  txt.split(' ').forEach(w => { if ((l + ' ' + w).trim().length > 30) { lin.push(l.trim()); l = w; } else l += ' ' + w; }); if (l.trim()) lin.push(l.trim());
  const L = lin.slice(0, 6); if (lin.length > 6) L[5] = L[5].replace(/.{0,2}$/, '…'); L.push('(toque para ver cómo)');
  const w = Math.max(...L.map(t => t.length)) * 7.2 + 26, h = L.length * 17 + 20, base = -84;
  // arriba de la cabeza; si ahí taparía los paneles del cielo (CPU/RAM, avance total), va al costado del pollito
  const arriba = y + base - h > 120, lado = x + 40 + w < 992 ? 1 : -1;
  const bx = arriba ? Math.max(8 - x, Math.min(992 - x - w, -w / 2)) : (lado > 0 ? 40 : -40 - w), by = arriba ? base - h : Math.max(122 - y, -60 - h / 2);
  sv('rect', {x: bx, y: by, width: w, height: h, rx: 12, fill: '#fff', stroke: '#2b2118', 'stroke-width': 2}, g);
  if (arriba) {
    sv('path', {d: `M${Math.max(bx + 14, -10)} ${base - 1} L0 -68 L${Math.min(bx + w - 14, 10)} ${base - 1} Z`, fill: '#fff', stroke: '#2b2118', 'stroke-width': 2, 'stroke-linejoin': 'round'}, g);
    sv('rect', {x: Math.max(bx + 12, -12), y: base - 4, width: 26, height: 5, fill: '#fff'}, g);
  } else {
    const ex = lado > 0 ? bx + 1 : bx + w - 1, ty = Math.min(Math.max(-52, by + 12), by + h - 22);
    sv('path', {d: `M${ex} ${ty} L${lado * 18} -50 L${ex} ${ty + 14} Z`, fill: '#fff', stroke: '#2b2118', 'stroke-width': 2, 'stroke-linejoin': 'round'}, g);
    sv('rect', {x: ex - 3, y: ty + 1, width: 6, height: 12, fill: '#fff'}, g);
  }
  L.forEach((t, i) => sv('text', {x: bx + 13, y: by + 22 + i * 17, 'font-size': i === L.length - 1 ? 11 : 13, 'font-weight': i === 0 ? 800 : 500, fill: i === 0 ? '#c65f00' : i === L.length - 1 ? '#7a6a55' : '#2b2118'}, g).textContent = t);
  sv('title', {}, g).textContent = acc.map(a => a[1] + (a[2] ? ' — ' + a[2] : '')).join('\n');
}
function minaDetalle() {
  const E = MINA.E; if (!E) return; const box = $('#minaDet');
  const uno = e => `<div class="objD"><h4><span>${finM(e) ? '✔' : '⛏'} ${esc(e.nombre)}</span><span>${e.pct}%</span></h4>
    ${e.archivo ? `<p class="meta">${esc(e.archivo)}${e.dur ? ' · ' + e.dur + ' s' : ''}</p>` : ''}
    ${e.drive ? `<div class="mDrvB"><a class="drv" target="_blank" rel="noopener" href="${esc(e.drive)}">▶ Ver video en Drive</a><button type="button" class="accC" data-u="${esc(e.drive)}">📋 Copiar enlace</button></div>` : ''}
    <ul>${e.pasos.map(p => `<li><span>${p[1] >= 100 ? '✅' : p[1] > 0 ? '⛏' : '⬜'}</span><span>${esc(p[0])}</span><b>${p[1]}%</b>${p[2] ? `<small>${esc(p[2])}</small>` : ''}</li>`).join('')}</ul></div>`;
  if (MINA.sel === '__carro') {
    const f = E.idiomas.filter(finM);
    box.innerHTML = `<h3>🛒 En el carro minero: ${f.length} objetivo(s) finalizado(s)</h3>` + (f.length ? f.map(uno).join('') : '<p class="vacio">Todavía no hay objetivos al 100 %.</p>');
  } else { const e = E.idiomas.find(x => x.L === MINA.sel);
    box.innerHTML = e ? `<h3>${finM(e) ? '🛒 Finalizado' : '⛏ En la mina'}</h3>` + uno(e) : '<p class="vacio">Toque un objetivo, una tarea o el carro minero para ver el detalle.</p>'; }
}
function minaMedidor(k, p, txt) {
  const m = MINA.med[k], c = p > 90 ? '#f85149' : p > 70 ? '#d29922' : '#3fb950';
  m.cr.setAttribute('width', 180 * Math.max(0, Math.min(100, p)) / 100); m.bar.setAttribute('fill', c); m.v.textContent = txt;
}
function mina(E) {
  MINA.E = E; if (MINA.key !== minaClave(E)) minaArmar(E);
  MINA.tot.tv.textContent = E.total + '%'; MINA.tot.cr.setAttribute('width', 148 * Math.max(0, Math.min(100, E.total)) / 100);
  const S = E.sis || {}, cpu = S.total || 0, ram = S.mem ? 100 * S.mem[0] / S.mem[1] : 0;
  minaMedidor('cpu', cpu, cpu.toFixed(0) + '%'); minaMedidor('ram', ram, ram.toFixed(0) + '%');
  const fins = [];
  E.idiomas.forEach((e, i) => {
    const o = MINA.objs[i], G = MINA.gal[i], f = finM(e), c = cavado(e), largo = Math.round(1000 * c.f);
    // túnel abierto = lo cavado en orden + todo tramo que ya llegó al 100 % (aunque esté más adelante; 14/11)
    { const k = Math.max(1, e.pasos.length), iv = [[0, largo]];
      e.pasos.forEach((p, j) => { if ((f ? 100 : p[1]) >= 100) iv.push([1000 * j / k, 1000 * (j + 1) / k]); });
      iv.sort((x, y) => x[0] - y[0]); const m = [];
      iv.forEach(([x, y]) => { if (y <= x) return; if (m.length && x <= m[m.length - 1][1] + .5) m[m.length - 1][1] = Math.max(m[m.length - 1][1], y); else m.push([x, y]); });
      const d = []; let pos = 0;   // patrón trazo/hueco que empieza con trazo: trazo 0 si el primer tramo abierto no arranca en 0
      m.forEach(([x, y], n) => { if (n === 0 && x > 0) d.push(0, x); else if (n > 0) d.push(x - pos); d.push(y - x); pos = y; });
      if (!m.length) d.push(0); d.push(1000 + 1000 - pos);
      const da = d.map(x => +x.toFixed(2)).join(' ');
      G.fondo.setAttribute('stroke-dasharray', da); G.luz.setAttribute('stroke-dasharray', da); }
    e.pasos.forEach((p, j) => { const T = G.tareas[j]; if (!T) return; const v = f ? 100 : p[1];
      const Ln = minaLineas(nomTarea(p[0]), Math.max(8, Math.floor((T.w - 8) / 5.6))), ex = 12 * (Ln.length - 1), y0 = T.arriba ? T.ty - ex : T.ty;
      minaTexto(T.tn, Ln, T.mx, y0 + 12, 12); T.ex = ex; T.r.setAttribute('y', y0); T.r.setAttribute('height', 30 + ex);
      T.tp.setAttribute('y', y0 + 25 + ex); T.tb.setAttribute('y', y0 + 27 + ex); T.tb.previousElementSibling.setAttribute('y', y0 + 27 + ex);
      T.tp.textContent = (v >= 100 ? '✔ ' : j === c.act ? '⛏ ' : '') + v + '%';
      T.tb.setAttribute('width', (T.w - 8) * v / 100);
      T.cam.classList.add('hide');   // los tramos al 100 % fuera de orden ya se ven despejados en el túnel
      T.g.classList.toggle('ahora', j === c.act); T.et.setAttribute('transform', j === c.act && T.arriba ? `translate(0 ${72 + (T.ex || 0)})` : '');   // el rótulo de la tarea en curso va debajo: arriba está el pollito
      T.tt.textContent = `${p[0]}: ${v}%${p[2] ? ' · ' + p[2] : ''}`;
      const roca = v < 100; T.et.style.display = roca ? 'none' : ''; T.ro.style.display = 'none'; T.rn.style.display = roca ? '' : 'none';
      // la roca de la tarea en curso va justo delante del pollito, para que no la tape
      const q = j === c.act ? G.fondo.getPointAtLength(Math.min(G.L, G.L * c.f + 30)) : {x: T.mx, y: T.my}; T.ro.setAttribute('transform', `translate(${q.x} ${q.y})`);
      if (roca) { T.rs.setAttribute('transform', `scale(${(1 - .7 * v / 100).toFixed(3)})`); T.rp.textContent = v + '%';
        const Lr = minaLineas(nomTarea(p[0]), Math.max(8, Math.floor((T.w - 4) / 5.4))).concat([(j === c.act ? '⛏ ' : '') + v + '%']), ar = T.arriba && !(j === c.act);
        minaTexto(T.rn, Lr, T.mx, ar ? T.my - 24 - 11 * (Lr.length - 1) : T.my + 32, 11); } });   // el texto va centrado bajo (o sobre) su roca
    o.aro.setAttribute('stroke-dasharray', `${f ? 100 : e.pct} 100`); o.cr.classList.toggle('hide', f); o.hueco.classList.toggle('hide', !f);
    { const Ln = minaLineas(e.nombre, 24), ex = 11 * (Ln.length - 1); minaTexto(o.nom, Ln, 0, -65 - ex, 11); o.caja.setAttribute('y', -78 - ex); o.caja.setAttribute('height', 32 + ex); } o.pct.textContent = f ? '✔ en el carro' : `${e.pct}%`; o.logrado.textContent = e.pct + '%';
    o.esc.classList.toggle('hide', !f); o.drv.classList.add('hide'); o.drv.dataset.u = e.drive || '';
    o.tt.textContent = `${e.nombre}: ${e.pct}%`; o.g.classList.toggle('sel', MINA.sel === e.L);
    if (f) fins.push({e, col: o.col});
  });
  MINA.gemas.innerHTML = '';
  fins.forEach(({e, col}, k) => { const x = -46 + (k % 5) * 23, y = -60 - Math.floor(k / 5) * 18;
    const g = sv('g', {class: 'gema', tabindex: 0, role: 'button', transform: `translate(${x} ${y}) scale(1.35)`}, MINA.gemas); g.dataset.l = e.L;
    sv('path', {d: 'M0 -11 L9 -3 L5 9 L-5 9 L-9 -3 Z', fill: col, stroke: '#fff', 'stroke-width': 1.5}, g);
    sv('title', {}, g).textContent = e.nombre + ' (100 %)'; });
  MINA.carroT.textContent = fins.length ? `${fins.length} listo(s)` : 'vacío';
  // el pollito cava en el objetivo en curso, en la punta de su galería (la tarea que se está haciendo)
  // el pollito va donde de verdad se está trabajando: la galería cuyo avance cambió más recientemente
  // (las tarjetas de proceso se actualizan solas; una tarjeta de pedido puede repetir el mismo trabajo y no debe atraerlo)
  const ahora = Date.now(); MINA.cambio = MINA.cambio || {}; MINA.ult = MINA.ult || {};
  E.idiomas.forEach(e => { const k = e.pasos.map(p => p[1]).join(','); if (MINA.ult[e.L] !== undefined && MINA.ult[e.L] !== k) MINA.cambio[e.L] = ahora; MINA.ult[e.L] = k; });
  const pend = E.idiomas.map((e, i) => [e, i]).filter(([e]) => !finM(e));
  const reciente = pend.filter(([e]) => enCurso(e) && ahora - (MINA.cambio[e.L] || 0) < 15 * 60000).sort((a, b) => MINA.cambio[b[0].L] - MINA.cambio[a[0].L])[0];
  // proceso que corre en el equipo («Render de la imagen (Chrome) · es») → la tarjeta de ese idioma
  const enProc = (E.procesos || []).map(p => (String(p[0]).match(/·\s*([a-z]{2,3})\s*$/) || [])[1]).filter(Boolean);
  const porProc = pend.find(([e]) => !e.tarea && enProc.includes(e.L));
  const act = porProc || reciente || pend.find(([e]) => enCurso(e) && !e.tarea) || pend.find(([e]) => enCurso(e)) || pend.find(([e]) => e.pct > 0) || pend[0];
  let x, y, izq = false, quieto = true, fiesta = false;
  if (act) {
    const [e, i] = act, G = MINA.gal[i], c = cavado(e);
    const a = G.fondo.getPointAtLength(Math.max(0, G.L * c.f - 42)), b = G.fondo.getPointAtLength(Math.min(G.L, G.L * c.f + 4));   // 42: con el pico en el golpe (52 grados) la punta cae en la orilla visible del túnel (avance + 15 del extremo redondo), medido en la página
    x = a.x; y = a.y + 12; izq = b.x < a.x - .5; if (c.f < .02) { x = X0 + 8; y = G.y + 12; }
    quieto = !enCurso(e) && !(E.procesos && E.procesos.length);
  } else { x = 520; y = 100; fiesta = true; }
  // ¿hay algo que debe hacer el usuario? el pollito se da vuelta, lo mira de frente y se lo dice en un globo
  const acc = (E.checklist && E.checklist.acciones) || [], hay = acc.length > 0;
  MINA.pollo.classList.toggle('atiende', hay);
  minaGlobo(hay ? acc : null, x, y);
  MINA.pollo.style.transform = `translate(${x}px, ${y}px)`; MINA.giro.setAttribute('transform', izq && !hay ? 'scale(-1 1)' : '');
  MINA.pollo.classList.toggle('quieto', quieto || fiesta || hay); MINA.pollo.classList.toggle('fiesta', fiesta && !hay);
  MINA.pollo.classList.toggle('suda', cpu > 90); MINA.pollo.classList.toggle('piensa', ram > 90);
  // varias tareas a la vez (otras galerías con avance en los últimos 10 min, o procesos de otros idiomas): un pollito igual
  // trabajando en cada una; si se trabaja en una sola, no aparece ninguno extra
  MINA.extras.innerHTML = '';
  if (act) pend.filter(([e]) => e !== act[0] && enCurso(e) && (ahora - (MINA.cambio[e.L] || 0) < 10 * 60000 || (!e.tarea && enProc.includes(e.L)))).forEach(([e, i]) => {
    const G = MINA.gal[i], c = cavado(e); if (c.f < .02) return;
    const a = G.fondo.getPointAtLength(Math.max(0, G.L * c.f - 42)), b = G.fondo.getPointAtLength(Math.min(G.L, G.L * c.f + 4));   // 42: con el pico en el golpe (52 grados) la punta cae en la orilla visible del túnel (avance + 15 del extremo redondo), medido en la página
    const g = sv('g', {class: 'pollo' + (cpu > 90 ? ' suda' : ''), transform: `translate(${a.x} ${a.y + 12})`}, MINA.extras), cl = MINA.giro.cloneNode(true);
    cl.setAttribute('transform', b.x < a.x - .5 ? 'scale(-1 1)' : ''); g.appendChild(cl); });
  if (MINA.sel) minaDetalle();
  if (MINA.modal) minaModal();
  minaEncuadre();
}
function minaModal() {
  const m = MINA.modal, box = $('#minaModal'); if (!m || !MINA.E) { box.hidden = true; return; }
  if (m.accion) {   // lo que debe hacer el usuario
    const acc = (MINA.E.checklist && MINA.E.checklist.acciones) || [];
    if (!acc.length) { minaCerrar(); return; }
    $('#mCont').innerHTML = `<p class="mObj">El pollito necesita su ayuda</p><h3 id="mTit">🙋 Acción pendiente${acc.length > 1 ? 's' : ''}</h3>` +
      acc.map(a => `<div class="mAccion"><b>${esc(a[1])}</b>${a[2] ? `<p>${esc(a[2])}</p>` : ''}<small>desde las ${esc(a[0])}</small></div>`).join('') +
      `<div class="mAcc"><button type="button" id="mVolver">← Volver al mapa</button></div>`;
    if (box.hidden) { box.hidden = false; $('#mVolver').focus(); } return;
  }
  if (m.det) {   // detalle de un objetivo o del carro, en ventana (pantalla completa)
    $('#mCont').innerHTML = `<div class="mDet">${$('#minaDet').innerHTML.replace(/<h3>/, '<h3 id="mTit">')}</div><div class="mAcc"><button type="button" id="mVolver">← Volver al mapa</button></div>`;
    if (box.hidden) { box.hidden = false; $('#mVolver').focus(); } return;
  }
  const e = MINA.E.idiomas.find(x => x.L === m.L), p = e && e.pasos[m.j];
  if (!p) { MINA.modal = null; box.hidden = true; return; }
  const c = cavado(e), v = finM(e) ? 100 : p[1], est = v >= 100 ? [2, '✔ Terminada'] : (m.j === c.act ? [1, '⛏ En curso'] : (v > 0 ? [1, 'Iniciada'] : [0, 'Pendiente']));
  const procs = v < 100 && m.j === c.act && MINA.E.procesos && MINA.E.procesos.length ? MINA.E.procesos.map(x => esc(Array.isArray(x) ? `${x[0]} · ${Math.floor(x[1] / 60)} min` : String(x))).join('<br>') : '';
  $('#mCont').innerHTML = `<p class="mObj">${esc(e.nombre)} · tarea ${m.j + 1} de ${e.pasos.length}</p>
    <h3 id="mTit">${esc(p[0])}</h3><span class="mEst e${est[0]}">${est[1]}</span>
    <div class="mPct"><b>${v}%</b><div class="mBar"><i style="width:${v}%"></i></div></div>
    <dl><dt>Proceso</dt><dd>${esc(p[2] || (v >= 100 ? 'Completado' : v > 0 ? 'En proceso' : 'Todavía no empieza'))}</dd>
      ${procs ? `<dt>En el equipo</dt><dd>${procs}</dd>` : ''}
      <dt>Objetivo</dt><dd>${e.pct}% del total${finM(e) ? ' · en el carro minero' : ''}</dd></dl>
    ${e.drive ? `<div class="mDrvB"><a class="drv" target="_blank" rel="noopener" href="${esc(e.drive)}">▶ Ver video en Drive</a><button type="button" class="accC" data-u="${esc(e.drive)}">📋 Copiar enlace</button></div>` : ''}
    <div class="mAcc"><button type="button" id="mVolver">← Volver al mapa</button></div>`;
  if (box.hidden) { box.hidden = false; $('#mVolver').focus(); }
}
function minaCerrar() { MINA.modal = null; $('#minaModal').hidden = true; }
document.addEventListener('click', ev => {
  if (ev.target.closest('#mVolver') || ev.target.id === 'minaModal') { minaCerrar(); return; }
  if (ev.target.closest('#minaFS, #minaFSsalir')) { minaPantalla(); return; }
  if (ev.target.closest('#minaV .globo')) { MINA.modal = {accion: true}; minaModal(); return; }
  const t = ev.target.closest('#minaV .tarea');
  if (t) { MINA.modal = {L: t.dataset.l, j: +t.dataset.j}; minaModal(); return; }
  const g = ev.target.closest('#minaV .gema, #minaV .obj'), c = ev.target.closest('#minaV .carro');
  if (g) { MINA.sel = g.dataset.l; } else if (c) { MINA.sel = '__carro'; } else return;
  MINA.modal = {det: MINA.sel};   // la tarjeta del objetivo se abre en ventana (ahí está su botón de Drive)
  if (MINA.E) mina(MINA.E); minaDetalle(); if (MINA.modal) minaModal();
});
// pantalla completa de la mina (API Fullscreen; si no existe, p. ej. iPhone, ocupa toda la ventana con CSS)
const minaTelefono = () => minaMovil() && Math.min(screen.width, screen.height) < 600;   // teléfono (en tablet no se gira el mapa)
const minaMovil = () => matchMedia('(pointer:coarse)').matches || (navigator.maxTouchPoints > 0 && Math.min(screen.width, screen.height) < 820);
function minaPantalla() {
  const v = $('#minaMapa'), doc = document, fsEl = doc.fullscreenElement || doc.webkitFullscreenElement || doc.webkitCurrentFullScreenElement;
  if (fsEl || v.classList.contains('fsPseudo')) {
    if (fsEl) (doc.exitFullscreen || doc.webkitExitFullscreen || doc.webkitCancelFullScreen).call(doc); v.classList.remove('fsPseudo'); minaBotonFS(); return;
  }
  const req = v.requestFullscreen || v.webkitRequestFullscreen || v.webkitRequestFullScreen;
  if (minaMovil() && req) Promise.resolve(req.call(v)).then(() => screen.orientation && screen.orientation.lock && screen.orientation.lock('landscape').catch(() => {})).catch(() => v.classList.add('fsPseudo')).finally(minaBotonFS);   // móvil: toda la pantalla, en horizontal si se puede
  else { v.classList.add('fsPseudo'); minaBotonFS(); }                                                               // escritorio: todo el navegador
}
const minaEnFS = () => !!(document.fullscreenElement || document.webkitFullscreenElement || document.webkitCurrentFullScreenElement) || $('#minaMapa').classList.contains('fsPseudo');
// el mapa entra entero y el cielo / la tierra se extienden hasta los bordes: llena la pantalla sin deformarse ni cortarse
function minaEncuadre() {
  const s = $('#minaS'); if (!s || !MINA.H) return; const H = MINA.H;
  if (!minaEnFS()) { $('#minaMapa').classList.remove('girado'); s.style.height = '';
    // el mapa mide lo que ocupa su contenido (sin cielo ni tierra de más); si no cabe en la ventana se achica y se ve entero
    const c = minaCaja(), h0 = Math.min(c.w * H / 1000, c.h); s.style.height = h0 + 'px'; const a = c.w / h0;
    if (a >= 1000 / H) { const w = H * a; s.setAttribute('viewBox', `${(1000 - w) / 2} 0 ${w} ${H}`); } else { const h = 1000 / a; s.setAttribute('viewBox', `0 ${(H - h) / 2} 1000 ${h}`); }
    return; }
  s.style.height = '';
  // celular en vertical: el mapa se gira 90° para usar toda la pantalla (se intenta además bloquear la orientación horizontal)
  const m = $('#minaMapa'), gir = minaTelefono() && innerHeight > innerWidth; m.classList.toggle('girado', gir);
  const r = m.getBoundingClientRect(), a = gir ? r.height / Math.max(1, r.width) : r.width / Math.max(1, r.height);
  if (a >= 1000 / H) { const w = H * a; s.setAttribute('viewBox', `${(1000 - w) / 2} 0 ${w} ${H}`); }
  else { const h = 1000 / a; s.setAttribute('viewBox', `0 ${(H - h) / 2} 1000 ${h}`); }
}
function minaBotonFS() {
  const on = minaEnFS(), b = $('#minaFS');
  b.textContent = on ? '✕ Salir de pantalla completa' : '⛶ Pantalla completa'; b.setAttribute('aria-pressed', on);
  document.body.style.overflow = $('#minaMapa').classList.contains('fsPseudo') ? 'hidden' : '';
  requestAnimationFrame(minaEncuadre);
}
addEventListener('resize', () => { if (MINA.E && MINA.key !== minaClave(MINA.E)) mina(MINA.E); else minaEncuadre(); });
// Safari (iPad) informa el tamaño nuevo tarde al girar: se reencuadra varias veces
addEventListener('orientationchange', () => [100, 350, 700, 1200].forEach(t => setTimeout(() => { if (minaEnFS()) minaEncuadre(); }, t)));
['fullscreenchange', 'webkitfullscreenchange'].forEach(t => document.addEventListener(t, () => [100, 400].forEach(d => setTimeout(minaEncuadre, d))));
['fullscreenchange', 'webkitfullscreenchange'].forEach(t => document.addEventListener(t, minaBotonFS));
document.addEventListener('keydown', ev => { if (ev.key === 'Escape') { if (!$('#minaModal').hidden) minaCerrar(); else if ($('#minaMapa').classList.contains('fsPseudo')) { $('#minaMapa').classList.remove('fsPseudo'); minaBotonFS(); } } });
document.addEventListener('click', ev => {
  const b = ev.target.closest && ev.target.closest('#minaV .escoba'); if (!b) return;
  ev.preventDefault(); ev.stopPropagation();
  const e = MINA.E && MINA.E.idiomas.find(x => x.L === b.dataset.l); if (!e) return;
  minaConfirmar(e.nombre, () => fetch('limpiar', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id: e.L})})
    .then(r => { if (!r.ok) return r.text().then(t => minaAviso('No se pudo limpiar: ' + t)); b.classList.add('hide'); }).catch(() => minaAviso('No se pudo limpiar: sin conexión')));
}, true);
document.addEventListener('click', ev => {   // botón de Drive del objetivo: abre el video en otra pestaña
  const b = ev.target.closest && ev.target.closest('#minaV .drvO'); if (!b || !b.dataset.u) return;
  ev.preventDefault(); ev.stopPropagation(); window.open(b.dataset.u, '_blank', 'noopener');
}, true);
// ventana pequeña al centro, con el diseño de la página (en el celular los avisos del navegador se ven mal; 14/11).
// En pantalla completa real va dentro del mapa, que es lo único que se ve.
function minaVentana(html) {
  const fs = document.fullscreenElement || document.webkitFullscreenElement || document.webkitCurrentFullScreenElement;
  const v = document.createElement('div'); v.className = 'mConf'; v.setAttribute('role', 'dialog'); v.setAttribute('aria-modal', 'true');
  v.innerHTML = `<div class="mModal">${html}</div>`; (fs || document.body).appendChild(v);
  v.addEventListener('click', ev => { if (ev.target === v) v.remove(); }); return v;
}
function minaConfirmar(nombre, si) {
  const v = minaVentana(`<h3>🧹 ¿Limpiar del mapa?</h3><p>«${esc(nombre)}» ya está terminado. Deja de verse en la página y el mapa se reacomoda.</p><div class="bot"><button type="button" class="no">Cancelar</button><button type="button" class="si">Limpiar</button></div>`);
  v.querySelector('.no').onclick = () => v.remove(); v.querySelector('.si').onclick = () => { v.remove(); si(); }; v.querySelector('.si').focus();
}
function minaAviso(t) { const v = minaVentana(`<p>${esc(t)}</p><div class="bot"><button type="button" class="si">Entendido</button></div>`); v.querySelector('.si').onclick = () => v.remove(); }
// al elegir la vista Mina, el mapa sube hasta arriba de la ventana y la ocupa entera
document.addEventListener('click', ev => { if (ev.target.closest && ev.target.closest('#vistas button[data-v=mina]')) setTimeout(() => { const m = $('#minaV'); if (m) m.scrollIntoView({block: 'start'}); }, 300); });
document.addEventListener('keydown', ev => { if ((ev.key === 'Enter' || ev.key === ' ') && ev.target.closest && ev.target.closest('#minaV [role=button]')) { ev.preventDefault(); ev.target.dispatchEvent(new MouseEvent('click', {bubbles: true})); } });

function organizar(E) {
  ULTIMO = E; document.querySelectorAll('#vistas button').forEach(b => b.classList.toggle('on', b.dataset.v === VISTA));
  $('#langs').classList.toggle('hide', VISTA !== 'tarjetas'); $('#tablero').classList.toggle('hide', VISTA !== 'tablero'); $('#tablaV').classList.toggle('hide', VISTA !== 'tabla'); $('#minaV').classList.toggle('hide', VISTA !== 'mina'); if (VISTA === 'mina') mina(E);
  if (VISTA === 'tablero') {
    const n = {hacer: 0, prog: 0, fin: 0};
    E.idiomas.forEach(e => { const c = document.getElementById('c_' + e.L), k = columna(e), dest = $('#col_' + k); n[k]++; if (c.parentNode !== dest) dest.appendChild(c); });
    Object.entries(n).forEach(([k, v]) => $('#n_' + k).textContent = v);
  } else E.idiomas.forEach(e => { const c = document.getElementById('c_' + e.L); if (c.parentNode !== $('#langs')) $('#langs').appendChild(c); });
  if (VISTA === 'tabla') {
    $('#tablaB').innerHTML = E.idiomas.map(e => {
      const P = Object.fromEntries(e.pasos.map(p => [p[0].split(':')[0], p]));   // para el aviso de Drive
      const est = e.ok && (e.drive || e.tarea) ? 'Finalizado' : e.err ? 'Error' : columna(e) === 'hacer' ? 'Por hacer' : enCurso(e) ? 'En progreso' : 'En espera';
      const fila = `<tr class="fila" data-l="${e.L}"><td><b>${abiertasT.has(e.L) ? '▾' : '▸'} ${esc(e.nombre)}</b></td><td>${est}</td>
        <td>${e.pct}%<div class="mini"><i style="width:${e.pct}%"></i></div></td><td>${esc(vaPor(e))}</td>
        <td class="c">${e.drive ? `<a class="drv" target="_blank" rel="noopener" href="${esc(e.drive)}">▶ Ver</a>` : (P['Subida a Drive'] && P['Subida a Drive'][2] ? '⚠' : '–')}</td></tr>`;
      const det = abiertasT.has(e.L) ? `<tr class="det"><td colspan="5"><div class="detalle" data-l="${e.L}"></div></td></tr>` : '';
      return fila + det; }).join('');
    // el detalle es la misma información de la tarjeta, con su mismo orden y estilo (pasos con barra; frases en tabla)
    document.querySelectorAll('#tablaV .detalle').forEach(d => { const c = document.getElementById('c_' + d.dataset.l); if (!c) return;
      const izq = document.createElement('div'), der = document.createElement('div');
      izq.append(c.querySelector('ul').cloneNode(true)); const tb = c.querySelector('table'), w = c.querySelector('.warn');
      if (!tb.classList.contains('hide')) der.append(tb.cloneNode(true)); if (!w.classList.contains('hide')) der.append(w.cloneNode(true));
      if (!der.children.length) der.innerHTML = '<p class="sinf">Sin frases recientes</p>'; d.append(izq, der); });
  }
}
document.addEventListener('click', ev => {
  const b = ev.target.closest('#vistas button'); if (b) { VISTA = b.dataset.v; try { localStorage.setItem('avance_vista', VISTA); } catch (e) {} if (ULTIMO) organizar(ULTIMO); return; }
  const f = ev.target.closest('#tablaV tr.fila'); if (f && !ev.target.closest('a')) { const L = f.dataset.l; abiertasT.has(L) ? abiertasT.delete(L) : abiertasT.add(L); if (ULTIMO) organizar(ULTIMO); }
});
function pintar(E) {
  sistema(E.sis);
  const trabajo = (E.checklist && E.checklist.trabajo) || `Video «${E.titulo}»`;
  tituloBase = `${E.total}% · ${trabajo}`; if (!parpadeo) document.title = tituloBase;
  acciones(E.checklist && E.checklist.acciones, E.checklist && E.checklist.acciones_hechas);
  $('#tit').textContent = trabajo; $('#tot').textContent = E.total + '%';
  $('#tm').textContent = `${Math.floor(E.t / 60)} min ${String(E.t % 60).padStart(2, '0')} s`;
  E.idiomas.forEach(e => {
    const c = document.getElementById('c_' + e.L) || tarjeta(e.L);
    c.querySelector('.n').textContent = e.nombre;
    const st = c.querySelector('.st'); st.className = 'st ' + (e.ok ? 'ok' : e.err ? 'err' : 'run');
    st.textContent = e.ok ? 'Listo ✔' : e.err ? 'Error: revisar produccion.log' : 'En curso';
    c.querySelector('.bar i').style.width = e.pct + '%'; c.querySelector('.p').textContent = e.pct + '%';
    c.querySelector('.va').textContent = vaPor(e);
    if (!e.ok && !e.err && !enCurso(e)) st.textContent = 'En espera';
    const dr = c.querySelector('.drv'); dr.classList.toggle('hide', !e.drive); if (e.drive) dr.href = e.drive;
    const ul = c.querySelector('ul');
    e.pasos.forEach(([k, v, det], i) => {
      let li = ul.children[i];
      if (!li) { li = document.createElement('li'); li.innerHTML = '<span></span><b></b><div class="t"><i></i></div><small></small>'; ul.appendChild(li); }
      li.className = v >= 100 ? 'd' : v > 0 ? 'a' : ''; li.children[0].textContent = (v >= 100 ? '✔ ' : '') + k; li.children[1].textContent = v + '%';
      li.querySelector('small').textContent = det || ''; li.querySelector('small').style.display = det ? '' : 'none';
      li.querySelector('.t i').style.width = v + '%';
    });
    const tb = c.querySelector('table');
    tb.classList.toggle('hide', !e.frases.length);
    tb.tBodies[0].innerHTML = e.frases.map(([i, s, x]) => `<tr class="${s < .85 ? 'w' : ''}"><td>${i}</td><td>${esc(x)}</td><td>${s.toFixed(2)}</td></tr>`).join('');
    const w = c.querySelector('.warn'); w.classList.toggle('hide', !e.revisar); w.textContent = `Para revisar (verificación baja): ${e.revisar}`;
  });
  organizar(E);
  const C = E.checklist; $('#chk').classList.toggle('hide', !C);

  if (C) { $('#ahora').textContent = 'Ahora: ' + C.ahora; $('#chkL').innerHTML = (C.pasos || []).map(([t, st]) => `<li class="${st}"><i>${st === 'ok' ? '✅' : st === 'run' ? '🔄' : '⬜'}</i><span>${esc(t)}</span></li>`).join('');
    if (!E.idiomas.length && C.pasos && C.pasos.length) $('#tot').textContent = Math.round(100 * C.pasos.filter(p => p[1] === 'ok').length / C.pasos.length) + '%';
    $('#chkN').textContent = (C.registro && C.registro.length) ? 'última: ' + C.registro[C.registro.length - 1][0] : '';
    $('#reg').innerHTML = (C.registro || []).slice(-40).reverse().map(([h, t]) => `<li><b>${h}</b><span>${esc(t)}</span></li>`).join(''); }
  const ban = $('#ban'), cls = E.fin ? 'ok' : E.error ? 'err' : 'run'; ban.className = 'banner ' + cls;
  $('#spin').style.display = cls === 'run' ? '' : 'none';
  $('#bt').textContent = E.fin && C && C.pasos.some(p => p[1] !== 'ok') ? 'Última producción terminada y verificada · el proyecto sigue (ver «Ahora»)' : E.fin ? '✔ Terminado: archivo final verificado y sin procesos activos' : E.error ? '✖ Se detuvo con error' : `En curso · ${E.procesos.length} proceso(s) trabajando`;
  $('#bs').textContent = E.fin ? E.idiomas.map(e => `${e.archivo} (${e.dur} s)`).join(' · ') : `Actualizado ${E.hora}`;
  $('#np').textContent = E.procesos.length;
  $('#procs').innerHTML = E.procesos.length ? E.procesos.map(([n, t]) => `<li><span>${esc(n)}</span><b>${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}</b></li>`).join('') : '<li class="none">Ninguno</li>';
}

// ---- «Sin Conexión»: pollito durmiendo si se corta la conexión más de 12 s; busca el túnel nuevo en GitHub
const SINCX = {desde: 0, t: null, buscando: false};
const TUNEL_GH = 'https://raw.githubusercontent.com/allanzuniga-dlg/monitorinterno/main/tunel.json';
function conexion(on) {
  if (on) { SINCX.desde = 0; clearTimeout(SINCX.t); SINCX.t = null; $('#sinCx').classList.remove('on'); return; }
  if (!SINCX.desde) SINCX.desde = Date.now();
  if (!SINCX.t) SINCX.t = setTimeout(function revisar() {
    if (!SINCX.desde) return;
    $('#sinCx').classList.add('on'); buscarTunel(); SINCX.t = setTimeout(revisar, 20000);
  }, 12000);
}
function buscarTunel() {
  if (SINCX.buscando || !/trycloudflare\.com$/.test(location.hostname)) return; SINCX.buscando = true;
  fetch(TUNEL_GH + '?t=' + Date.now(), {cache: 'no-store'}).then(r => r.json()).then(d => {
    const u = (d && d.url || '').replace(/\/+$/, '');
    if (!u || u === location.origin) return;
    return fetch(u + '/estado', {cache: 'no-store'}).then(r => { if (r.ok) location.replace(u + '/'); });
  }).catch(() => {}).then(() => { SINCX.buscando = false; });
}
function vivo(on, txt) { $('#live').classList.toggle('off', !on); $('#lt').textContent = txt; conexion(on); }
let sondeo = null;
function sondear() { if (sondeo) return; vivo(true, 'en vivo (consulta cada 2 s)');
  sondeo = setInterval(() => fetch('estado', {cache: 'no-store'}).then(r => r.json()).then(pintar).catch(() => vivo(false, 'sin conexión, reintentando')), 2000); }
fetch('estado', {cache: 'no-store'}).then(r => r.json()).then(pintar).catch(() => {});
function sse() { if (!window.EventSource) return sondear();
  const es = new EventSource('eventos'); let llego = false;
  es.onmessage = ev => { llego = true; vivo(true, 'en vivo'); pintar(JSON.parse(ev.data)); };
  es.onerror = () => { if (!llego) { es.close(); sondear(); } else vivo(false, 'reconectando'); };
  setTimeout(() => { if (!llego) { es.close(); sondear(); } }, 6000);
}
let wsOk = false;
function ws() {
  let w; try { w = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + location.pathname.replace(/[^/]*$/, '') + 'ws'); } catch (e) { return sse(); }
  w.onmessage = ev => { wsOk = true; vivo(true, 'en vivo'); pintar(JSON.parse(ev.data)); };
  w.onclose = () => { if (wsOk) { vivo(false, 'reconectando'); wsOk = false; setTimeout(ws, 2000); } else sse(); };
}
// tarjetas plegables: clic en el encabezado; el estado se recuerda en este navegador
const PK = 'avance_plegadas';
const leerP = () => { try { return JSON.parse(localStorage.getItem(PK) || '{}'); } catch (e) { return {}; } };
const guardarP = o => { try { localStorage.setItem(PK, JSON.stringify(o)); } catch (e) {} };
function restaurar(c) { const v = leerP()[c.id]; if (v === true || (v === undefined && !['sisC', 'chk'].includes(c.id))) c.classList.add('plegada'); }   // por defecto plegadas, salvo Proyecto (muestra lo pendiente) y el monitor   // por defecto plegadas; se recuerda solo lo que el usuario abre
function plegar(c, si) { c.classList.toggle('plegada', si); const o = leerP(); o[c.id] = si; guardarP(o); }
document.querySelectorAll('section.card:not(.fija)').forEach(restaurar);
document.addEventListener('click', e => { const h = e.target.closest('section.card:not(.fija) > header'); if (h) plegar(h.parentElement, !h.parentElement.classList.contains('plegada')); });
$('#plegarT').onclick = () => document.querySelectorAll('section.card:not(.fija)').forEach(c => plegar(c, true));
$('#abrirT').onclick = () => document.querySelectorAll('section.card:not(.fija)').forEach(c => plegar(c, false));
ws();
</script></body></html>'''


class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):
        pass

    def _send(self, code, body, tipo):
        b = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', tipo)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Access-Control-Allow-Origin', '*')   # la portada fija de GitHub Pages comprueba /estado para saber si hay conexión
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        ruta = self.path.split('?')[0]
        if ruta in ('/', '/index.html'):
            return self._send(200, PAGINA, 'text/html; charset=utf-8')
        if ruta == '/estado':
            return self._send(200, ACTUAL['json'], 'application/json')
        if ruta == '/ws' and self.headers.get('Upgrade', '').lower() == 'websocket':
            return self._ws()
        if ruta == '/eventos':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache, no-transform')
            self.send_header('X-Accel-Buffering', 'no')
            self.send_header('Transfer-Encoding', 'chunked')
            self.end_headers()
            def trozo(b):  # HTTP/1.1 por trozos: el túnel reenvía cada evento al instante
                self.wfile.write(f'{len(b):x}\r\n'.encode() + b + b'\r\n'); self.wfile.flush()
            ver = -1
            try:
                while True:
                    with cambio:
                        if ACTUAL['ver'] == ver:
                            cambio.wait(timeout=15)
                        nuevo, j = ACTUAL['ver'], ACTUAL['json']
                    if nuevo != ver:
                        trozo(f'data: {j}\n\n'.encode('utf-8')); ver = nuevo
                    else:
                        trozo(b': latido\n\n')  # mantiene viva la conexión a través del túnel
            except (BrokenPipeError, ConnectionResetError):
                return
        self._send(404, 'no encontrado', 'text/plain; charset=utf-8')

    def do_POST(self):
        if self.path.split('?')[0] != '/limpiar':
            return self._send(404, 'no encontrado', 'text/plain; charset=utf-8')
        try:
            n = min(int(self.headers.get('Content-Length', '0') or 0), 2000)
            ident = str(json.loads(self.rfile.read(n) or b'{}').get('id', ''))
            import fcntl
            with open(os.path.join(P, '.checklist.lock'), 'w') as lk:
                fcntl.flock(lk, fcntl.LOCK_EX)
                ruta = os.path.join(P, 'checklist.json'); chk = json.load(open(ruta, encoding='utf-8'))
                T = chk.get('tareas') or {}
                if ident.startswith('t_') and ident[2:] in T:
                    if not all(x[1] >= 100 for x in T[ident[2:]]['pasos']):
                        return self._send(409, 'la tarjeta no está terminada', 'text/plain; charset=utf-8')
                    del T[ident[2:]]
                elif ident and re.fullmatch(r'[A-Za-z0-9_-]{1,40}', ident):
                    chk.setdefault('ocultas', [])
                    if ident not in chk['ocultas']: chk['ocultas'].append(ident)
                else:
                    return self._send(400, 'id no válido', 'text/plain; charset=utf-8')
                tmp = ruta + f'.{os.getpid()}.tmp'; json.dump(chk, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); os.replace(tmp, ruta)
            return self._send(200, '{"ok": true}', 'application/json')
        except Exception as ex:
            return self._send(500, str(ex), 'text/plain; charset=utf-8')

    def _ws(self):
        clave = self.headers.get('Sec-WebSocket-Key', '')
        acepta = base64.b64encode(hashlib.sha1((clave + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        self.send_response(101, 'Switching Protocols')
        self.send_header('Upgrade', 'websocket'); self.send_header('Connection', 'Upgrade')
        self.send_header('Sec-WebSocket-Accept', acepta); self.end_headers(); self.wfile.flush()
        def marco(datos, op=1):  # servidor → cliente: sin máscara
            n = len(datos)
            cab = bytes([0x80 | op]) + (bytes([n]) if n < 126 else (bytes([126]) + struct.pack('>H', n) if n < 65536 else bytes([127]) + struct.pack('>Q', n)))
            self.wfile.write(cab + datos); self.wfile.flush()
        ver = -1
        try:
            while True:
                with cambio:
                    if ACTUAL['ver'] == ver:
                        cambio.wait(timeout=15)
                    nuevo, j = ACTUAL['ver'], ACTUAL['json']
                if nuevo != ver:
                    marco(j.encode('utf-8')); ver = nuevo
                else:
                    marco(b'', 9)  # ping: mantiene viva la conexión
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.close_connection = True


threading.Thread(target=vigilar, daemon=True).start()
ThreadingHTTPServer.daemon_threads = True
ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
