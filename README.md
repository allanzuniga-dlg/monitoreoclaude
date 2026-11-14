# monitoreoclaude

Portada fija de la página de avance de los trabajos de Claude: https://allanzuniga-dlg.github.io/monitoreoclaude/

- Con la computadora de trabajo encendida muestra la página **en vivo** (llega por un túnel; `tunel.json` guarda solo su dirección pública).
- Si no responde, muestra un pollito durmiendo con «Sin Conexión» y se reconecta sola.
- Este repositorio **no contiene tokens, contraseñas ni accesos**.

## Skill «paginadeseguimiento»

En `skill/paginadeseguimiento/` está la skill de Claude Code que arma esta página de seguimiento para cualquier proyecto (vistas Tarjetas, Tabla, Tablero y Mina con el pollito minero). Para instalarla: copiar esa carpeta a `~/.claude/skills/` y, en un proyecto, correr `~/.claude/skills/paginadeseguimiento/iniciar.sh <carpeta> "Qué se hace"`.
