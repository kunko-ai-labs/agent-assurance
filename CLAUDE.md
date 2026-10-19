# agent-assurance — reglas del proyecto

## Qué es (y qué no)

**Declarado vs observado.** El manifiesto (`agent-assurance.yaml`) es la **promesa** de lo que un agente de IA puede hacer; `scan` **observa** lo que la configuración del repo concede de verdad (configs MCP de Claude Code/Cursor/Gemini/VS Code y permisos de Claude Code) y AA-002 falla si la promesa se rompe, señalando fichero:línea. `diff` dice qué hizo *este cambio*. AA-001 mide el radio de impacto. Tres puntos de aplicación con el mismo motor: al editar (hook / servidor MCP `would_break`), en el PR (Action `mode: diff` con comentario) y en cada push/release (SARIF).

Modelo de permisos de Claude Code: `allow` no concede capacidad, **quita al humano del bucle** (aprobación); las reglas se colapsan por clase; los comandos de solo lectura son `read`; una regla acotada es `scoped` y no rompe la promesa (solo *review*).

Por qué esto y no "diff de permisos": ya existe ×5 sin tracción (`docs/landscape.md`). Nadie verifica promesas ni mapea a OWASP.

No es: un motor en runtime, un interceptor de tool calls, un ledger, un sistema de aprobaciones. Eso queda fuera de este repo; aquí no entra código de eso.

## Contratos que no se rompen sin avisar

- **Exit codes**: `0` pass/review · `1` gate · `2` uso/manifiesto inválido. Están en `tests/test_cli_contract.py` y en `.github/workflows/ci.yml`. La Action depende de ellos.
- **Riesgo reproducible a mano**: cada punto sale de `risk.py` con su motivo. Nunca un LLM en el veredicto.
- **SARIF**: apunta al fichero real, con región; PASS sale como `kind: pass` (sin alerta).
- **Estándares**: mapeo a OWASP ASI; lo que viene de APTS se etiqueta `(adapted)`. No se reclama conformidad que no existe.
- **Lo no soportado es `UNKNOWN`**, nunca inferido. Un `UNKNOWN` nunca da PASS silencioso (AA-001 ≥ REVIEW; AA-002 "not verifiable").
- **El escáner no ejecuta nada**: ni servidores MCP ni código del repo; nunca lee el valor de un secreto, solo el nombre de la variable.
- **Catálogo de servidores MCP** (`scan/catalog.py`) con fuente por entrada; añadir un servidor = una entrada + su fuente.

## Cómo se trabaja

- Entorno: `.venv` con `pip install -e ".[dev]"`. Antes de commitear: `ruff check src tests && pytest -q`.
- El CI de dogfood (`assurance.yml`) es una **alarma**: cada job afirma que la Action pasa lo que debe y bloquea lo que debe. No añadir `continue-on-error` sin un paso que afirme el resultado esperado.
- Una unidad shippable por semana con demo de 30 s. Si una feature no cabe en una demo, está mal cortada.
- Ejemplos en `examples/` cubren las cuatro bandas (safe=LOW, medium=MEDIUM, high=HIGH, dangerous=CRITICAL); `examples/repos/` cubre promesa cumplida / rota / no verificable. Un check o un scanner nuevo añade su fixture y su job en `assurance.yml`.
- Antes de una feature nueva: pasada corta de mercado con fuente y fecha (`docs/landscape.md`), y proponer la versión que nadie ocupa.
- Commits en inglés, imperativo, prefijo `feat:|fix:|ci:|docs:|test:`.
- Nombres de paso en `action.yml` con `:` van entre comillas (un YAML roto tumba todos los jobs); `tests/test_action_yaml.py` lo comprueba.
- El GIF del README se regenera con `vhs docs/demo.tape` + el ffmpeg del comentario del tape; VHS necesita ejecutarse fuera del sandbox.
- Probar en repos ajenos reales antes de cada release (17/09: ocho repos; salieron tres falsos positivos que un senior habría rechazado).

## Roadmap vigente

Está en el README (§Roadmap). Si algo aquí contradice al roadmap, se abre issue.
