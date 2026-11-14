# «Sin Conexión» dentro de la página de avance (14/11/2026): si se pierde la conexión con la computadora de trabajo
# por más de 12 s, aparece el pollito durmiendo; mientras tanto se consulta en GitHub (tunel.json de monitoreoclaude)
# si el túnel cambió de dirección y, si la nueva responde, se salta a ella sola. Se inserta en avance.py con aplicar().
# Es necesario porque en iPad / iPhone la portada fija de GitHub abre esta página directamente (sin marco).

CSS = r'''
#sinCx{position:fixed;top:0;right:0;bottom:0;left:0;z-index:10000;display:none;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:16px;background:var(--bg)}
#sinCx.on{display:flex}#sinCx h2{margin:10px 0 6px;font-size:30px}#sinCx p{margin:0;color:var(--mut);max-width:420px;font-size:15px}
#sinCx svg{width:240px;max-width:70vw;height:auto}
#sinCx .respira{animation:sxR 3.2s ease-in-out infinite;transform-origin:130px 190px}@keyframes sxR{50%{transform:scale(1.035,.975)}}
#sinCx .z{font-weight:800;fill:var(--mut);opacity:0;animation:sxZ 3.6s ease-in infinite}#sinCx .z2{animation-delay:1.2s}#sinCx .z3{animation-delay:2.4s}
@keyframes sxZ{0%{opacity:0;transform:translate(0,0) scale(.6)}20%{opacity:1}100%{opacity:0;transform:translate(26px,-60px) scale(1.25)}}
'''

HTML = r'''<div id="sinCx" role="status" aria-live="polite"><svg viewBox="0 0 260 240" aria-label="Pollito durmiendo">
<text class="z" x="178" y="70" font-size="26">Z</text><text class="z z2" x="190" y="58" font-size="20">z</text><text class="z z3" x="200" y="48" font-size="16">z</text>
<ellipse cx="130" cy="222" rx="78" ry="9" fill="#000" opacity=".08"/><g class="respira"><ellipse cx="130" cy="160" rx="80" ry="64" fill="#ffd23f"/>
<path d="M92 158 q-30 6 -26 32 q22 4 42 -14 z" fill="#f5c11c"/><circle cx="150" cy="112" r="46" fill="#ffd23f"/>
<path d="M146 68 q-6 -18 6 -22 q-2 12 8 16 q-6 -14 8 -16 q-4 14 -8 24 z" fill="#f5c11c"/>
<path d="M128 110 q8 7 16 0" stroke="#3b2f20" stroke-width="3.5" fill="none" stroke-linecap="round"/><path d="M160 110 q8 7 16 0" stroke="#3b2f20" stroke-width="3.5" fill="none" stroke-linecap="round"/>
<ellipse cx="128" cy="126" rx="7" ry="4.5" fill="#ff9e7a" opacity=".7"/><ellipse cx="180" cy="126" rx="7" ry="4.5" fill="#ff9e7a" opacity=".7"/>
<path d="M146 122 l16 0 l-8 10 z" fill="#f59e0b"/><path d="M112 86 q30 -46 78 -14 q-34 -6 -54 22 z" fill="#5b7bd5"/><circle cx="194" cy="74" r="8" fill="#fff"/>
<path d="M110 220 l-6 8 m6 -8 l0 9 m0 -9 l6 8" stroke="#f59e0b" stroke-width="4" stroke-linecap="round"/><path d="M150 220 l-6 8 m6 -8 l0 9 m0 -9 l6 8" stroke="#f59e0b" stroke-width="4" stroke-linecap="round"/></g></svg>
<h2>Sin Conexión</h2><p>La computadora de trabajo no está transmitiendo el avance en este momento. La página se reconecta sola.</p></div>'''

JS = r'''
// ---- «Sin Conexión»: pollito durmiendo si se corta la conexión más de 12 s; busca el túnel nuevo en GitHub
const SINCX = {desde: 0, t: null, buscando: false};
const TUNEL_GH = 'https://raw.githubusercontent.com/allanzuniga-dlg/monitoreoclaude/main/tunel.json';
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
'''


def aplicar(s):
    if 'id="sinCx"' in s:
        return s
    s = s.replace('</style></head><body><main>', CSS + '</style></head><body>' + HTML + '<main>', 1)
    o = "function vivo(on, txt) { $('#live').classList.toggle('off', !on); $('#lt').textContent = txt; }"
    assert o in s
    s = s.replace(o, JS + "function vivo(on, txt) { $('#live').classList.toggle('off', !on); $('#lt').textContent = txt; conexion(on); }", 1)
    return s


if __name__ == '__main__':
    import sys
    p = sys.argv[1]; n = aplicar(open(p).read())
    assert n.count('id="sinCx"') == 1 and 'conexion(on)' in n
    open(p, 'w').write(n); print('SINCX_OK', p)
