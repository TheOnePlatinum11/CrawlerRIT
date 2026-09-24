# Proyecto RIT: Arañador web

**Tema:** Intervención de Estados Unidos en América Latina
**Autores:** Elías Ramírez Hernández, Ignacio Ramírez Hernández.
**Curso:** Recuperación de la Información Textual.

---

## Descripción

BreteRIT es un crawler implementado en Python que descarga, en
texto plano, documentos relacionados con la **intervención de Estados Unidos en
América Latina**. Consta de:

- **`main.py`** — orquestación del arañado: cola de URLs, trabajadores
  concurrentes e iteraciones.
- **`linkHelpers.py`** — descarga y procesamiento: Selenium headless, extracción
  de texto, detección de enlaces, políticas de cortesía y deduplicación.
- **`assets/`** — URLs semilla y por iteración (`URLs0.txt`, `URLs1.txt`, …),
  más `URLsExplorados.txt` con la lista final agregada.
- **`HTMLs/`** — repositorio de texto plano (un `.txt` por página, nombrado por
  su URL).

Cada iteración *i* lee `assets/URLs{i}.txt`, descarga su contenido y descubre los
enlaces que pasan a `assets/URLs{i+1}.txt`. Así el arañado crece por "frontera"
(hay una política de torres a propósito).

---

## Necesidad de información

### Tema y características

El buscador se centra en la **intervención de Estados Unidos en América Latina**
desde mediados del siglo XX hasta hoy: golpes de Estado, operaciones encubiertas,
guerras civiles financiadas desde el exterior, presiones económicas y diplomáticas,
embargos y programas de cooperación militar.

La información requerida es **documental, textual e histórica**:

- Documentos históricos y archivos desclasificados.
- Noticias y reportajes de prensa.
- Análisis académicos y artículos de investigación.
- Declaraciones oficiales (gobiernos de EE. UU. y países latinoamericanos).
- Testimonios y crónicas de las épocas afectadas.

Se prioriza el **texto claramente redactado** (no imágenes, audio o video), lo que
coincide con el diseño del repositorio: archivos `.txt` limpios derivados del HTML
renderizado.

### Colectivo destino

Estudiantes universitarios y de posgrado, investigadores, historiadores y
periodistas de América Latina interesados en historia política comparada. El rango
etario típico es de 18 a 45 años; el contexto socioeconómico es heterogéneo, por lo
que las fuentes priorizadas son de **acceso libre y gratuito** (prensa abierta,
archivos públicos, Wikipedia).

### Subtemas de interés y consultas esperadas

- Doctrina Monroe y política del "Gran Garrote".
- Operación Cóndor y dictaduras del Cono Sur.
- Revoluciones y conflictos centroamericanos (Nicaragua, El Salvador, Guatemala).
- Cuba: embargo, Bahía de Cochinos, crisis de los misiles.
- Presiones económicas (embargos, deuda, FMI) y programas como la Alianza para el
  Progreso.

Consultas típicas: *"Operación Cóndor", "intervención de EE. UU. en Chile",
"Golpe de Estado Guatemala 1954", "embargo Cuba", "guerra contra las drogas
Latinomaérica"*.

---

## Políticas de arañado

| Política | Descripción | Justificación |
| :--- | :--- | :--- |
| **Crawl-delay por host** | Un único acceso por dominio cada `DELAY = 1 s`, reservado atómicamente (`esperarCrawlDelay`). | Evita saturar un servidor al raspar varios documentos del mismo sitio; cortesía con los archivos y prensa de acceso abierto. |
| **Descarga concurrente con hilos** | `MAX_WORKERS = 4` hilos persistentes descargando a la vez desde una cola (`queue.Queue`). | Cumple el requisito de "descarga concurrente"; la red es I/O-bound por lo que los hilos no compiten por el GIL. |
| **Identificación del agente** | User-Agent `BreteRIT/1.0` en cada petición. | Transparencia: el arañado se identifica ante los sitios (uso ético y trazable). |
| **Renderizado completo con Selenium** | Chrome headless carga la página (JS incluido) antes de capturar el DOM. | Muchas fuentes (prensa, archivos digitales) cargan contenido por JavaScript; sin esto la información quedaría incompleta. |
| **Solo texto plano** | `--blink-settings=imagesEnabled=false` y eliminación de `<script>`/`<style>` antes de `get_text()`. | El repositorio debe ser texto procesado (no HTML, imágenes ni scripts), tal como exige la rúbrica. |
| **Deduplicación** | No se re-descarga un URL cuyo `.txt` ya existe (`yaDescargado`), y los enlaces por iteración se agregan a un conjunto. | Evita trabajo repetido en re-corridas y controla el crecimiento del repositorio y de la frontera. |
| **Filtro de ámbito** | Solo se siguen enlaces absolutos `http(s)://` (regex). | Evita enlaces relativos rotos y limita el salto a otros protocolos (mailto, ftp, javascript). |
| **Profundidad acotada** | `NUM_ITERS` iteraciones; el arañado cambia amplitud por profundidad según se ajuste la constante. | Controla el tiempo y el volumen del repositorio (objetivo: 10 GB de texto limpio). |

### Metadatos almacenados

- `assets/URLs{i}.txt` — la frontera detectada en cada iteración (recorrido).
- `assets/URLsExplorados.txt` — unión final de todos los URLs visitados.
- `HTMLs/<url>.txt` — el documento de texto procesado de cada página.
- **Log de recorrido** (stdout, con `logging` y nombre del hilo) — bitácora que
  evidencia por dónde anduvo la araña en cada iteración.

---

## URLs semilla

La primera iteración parte de `assets/URLs0.txt` (28 URLs, validadas con HTTP 200):

**Panorama general del tema**
1. https://es.wikipedia.org/wiki/Intervenciones_de_Estados_Unidos_en_Am%C3%A9rica_Latina
2. https://elordenmundial.com/mapas-y-graficos/intervencionismo-estados-unidos-america-latina/
3. https://www.wola.org/
4. https://revista.drclas.harvard.edu/united-states-interventions/
5. https://www.scmp.com/news/world/united-states-canada/article/3338634/us-interventions-latin-america-history-coups-and-conflicts
6. https://mapasmilhaud.com/mapas-historicos/el-intervencionismo-de-estados-unidos-en-latinoamerica-1950-2010/
7. https://portalacademico.cch.unam.mx/historiauniversal2/america-latina-1918-1945/intervencionismo-de-eu
8. https://www.aa.com.tr/en/americas/factbox-a-history-of-us-interventions-across-the-americas/3790233

**Noticias y hechos recientes**
9. https://www.npr.org/2026/01/02/nx-s1-5652133/us-venezuela-interventionism-caribbean-latin-america-history-trump
10. https://www.vaticannews.va/es/mundo/news/2026-01/america-latina-intervenciones-militares-estadounidenses.html

**Hitos y episodios históricos**
11. https://history.state.gov/milestones/1961-1968/bay-of-pigs
12. https://es.wikipedia.org/wiki/Operaci%C3%B3n_C%C3%B3ndor
13. https://es.wikipedia.org/wiki/Intervenci%C3%B3n_estadounidense_en_golpes_de_Estado_en_Am%C3%A9rica_Latina
14. https://en.wikipedia.org/wiki/United_States_involvement_in_regime_change_in_Latin_America
15. https://es.wikipedia.org/wiki/Doctrina_Monroe
16. https://es.wikipedia.org/wiki/Crisis_de_los_misiles_de_Cuba
17. https://es.wikipedia.org/wiki/Revoluci%C3%B3n_Nicarag%C3%BCense
18. https://es.wikipedia.org/wiki/Alianza_para_el_Progreso
19. https://es.wikipedia.org/wiki/Guerra_Fr%C3%ADa

**Archivos, investigación y bibliografía**
20. https://nsarchive.gwu.edu/  (National Security Archive — documentos desclasificados)
21. https://digitalarchive.wilsoncenter.org/  (Wilson Center Digital Archive)
22. https://www.archives.gov/research/foreign-policy  (Archivo Nacional de EE. UU.)
23. https://www.cia.gov/readingroom/  (CREST — Archivo de la CIA)
24. https://www.cfr.org/latin-america  (Consejo de Relaciones Exteriores)
25. https://internationalpolicy.org/  (Center for International Policy)
26. https://www.hrw.org/es  (Human Rights Watch)
27. https://www.telesurtv.net/  (prensa regional)
28. https://dialnet.unirioja.es/buscar/documentos?querysDisponibles=BIBLIOGRAFICA_BUSQUEDA_GENERAL&texto=intervencionismo+estados+unidos+america+latina  (búsqueda bibliográfica en Dialnet)

> La selección prioriza fuentes abiertas, estables y accesibles para el colectivo
> (imparten el tema), y entremezcla puntos de entrada (Wikipedia, prensa, archivos,
> buscadores académicos) para diversificar la frontera de la primera iteración.

---

## Instalación y uso

```bash
pip install -r requirements.txt
# (Selenium Manager descargará automáticamente el driver de Chrome)
python3 main.py
```

El arañado corre de forma autónoma: cada iteración procesa su lote de URLs con 4
hilos, escribe los documentos en `HTMLs/` y deja la frontera siguiente en `assets/`,
finalizando con la lista explorada. Al terminar se puede correr `depurarLinks()`
para generar `assets/URLsExplorados.txt`.