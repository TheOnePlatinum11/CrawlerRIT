# El-Desclasificador — arañador con Apache Nutch

Segunda implementación del arañador, usando **Apache Nutch 1.23**.
Nutch aporta la gestión de la frontera (CrawlDb), la cortesía por 
host (`fetcher.server.delay`), el respeto a robots.txt y el parseo de 
HTML/Texto; nosotros configuramos el enfoque temático y post-procesamos el texto.

## Requisitos

- **JDK 17**. En este equipo:
  `/usr/lib/jvm/java-17-openjdk-amd64`
- Apache Nutch 1.23 (`apache-nutch-1.23-bin.tar.gz`) descomprimido en
  `nutch/apache-nutch-1.23/` (gitignored).
- Python 3 (venv del repo) para `extract.py`.

## Reproducción

```bash
# 1. Descargar y descomprimir (una sola vez)
cd nutch
curl -LO https://dlcdn.apache.org/nutch/1.23/apache-nutch-1.23-bin.tar.gz
tar xzf apache-nutch-1.23-bin.tar.gz

# 2. Instalar la configuración en el runtime
./setup.sh

# 3. Arañar (3 rondas * 100 URLs; edita ROUNDS/TOPN en crawl.sh para cambiar)
./crawl.sh
#    todo se anota en logs/bitacora_nutch.log

# 4. Convertir los segmentos a texto plano en HTMLs/
../.venv/bin/python extract.py
```

La **bitácora del recorrido** queda en `nutch/logs/bitacora_nutch.log`
(inyección, generación, fetch y parse de cada ronda).

## Configuración aplicada (y su justificación)

| Política | Configuración | Justificación | Fuente |
| :--- | :--- | :--- | :--- |
| **Identificación** | `http.agent.name = El-Desclasificador` | Transparencia ante los sitios. | `nutch-default.xml`, Tutorial Nutch |
| **Cortesía por host** | `fetcher.server.delay = 1.0` | 1 petición por host por segundo; no satura prensa/archivos. | `nutch-default.xml` |
| **robots.txt** | `http.robots.agents = El-Desclasificador,*` | Nutch respeta robots.txt por defecto. | `nutch-default.xml`, Tutorial Nutch |
| **Solo texto** | `http.content.limit = 5MB` + filtro de URLs | Descarta binarios y multimedia. | `nutch-default.xml`, spec.md |
| **Enfoque temático** | `regex-urlfilter.txt` (exclusiones) | Ignora login, registros, búsquedas y binarios; sigue el resto. | Tutorial Nutch (urlfilter) |
| **Concurrencia** | `fetcher.threads.fetch = 50` | Descarga concurrente; la red es I/O-bound. | `nutch-default.xml` |
| **Frontera acotada** | `db.max.outlink.per.page = 200` | Controla el crecimiento de la frontera. | `nutch-default.xml` |
| **Tope de tiempo** | `http.timeout = 15000` | Evita que un host muerto atase un hilo. | `nutch-default.xml` |
| **Enlaces externos** | `db.ignore.external.links = false` | Sigue enlaces externos, crawl abierto. | `nutch-default.xml` |

## Decisiones de diseño y fuentes

### Elegir Apache Nutch como marco

La especificación pide un arañador con bibliotecas existentes y nombra a Apache
Nutch entre las opciones. Nutch es un marco completo que ya resuelve la gestión
de la frontera, la cortesía por host y robots.txt. Por eso se eligió como la
segunda implementación, junto al arañador propio en Python. Fuente: https://nutch.apache.org/

### Nutch 1.23 y JDK 17

Se usa la última versión estable de la serie 1.x, lanzada en septiembre de 2026,
porque es la que pensamos que es mejor y sigue recibiendo correcciones. Nutch
1.23 exige JDK 17 en tiempo de ejecución y compilación, así que el entorno se
fija con esa versión. Fuente: nota de lanzamiento de Nutch 1.23.

### Ciclo de rondas

El arañado corre el ciclo estándar de Nutch. `inject` carga las semillas en el
CrawlDb. Cada ronda, `generate` toma hasta N URLs pendientes y crea un segmento;
`fetch` las descarga; `parse` extrae el texto; `updatedb` guarda los resultados
y los enlaces nuevos en el CrawlDb. La frontera crece de una ronda a la
siguiente. `crawl.sh` repite el ciclo y anota cada paso en la bitácora. Fuente:
Tutorial de Nutch.

### El repositorio queda igual

`extract.py` convierte los segmentos a `HTMLs/<url>.txt` reutilizando
`cortarTexto` y el filtro de relevancia del arañador en Python. El texto se guarda
con el mismo formato, de modo que el repositorio es idéntico sin importar la
implementación.

### Bitácora

La especificación incluye el requisito de una bitácora del recorrido de la
araña. `crawl.sh` vuelca toda la salida a `logs/bitacora_nutch.log`, donde
quedan la inyección, la generación, la descarga y el parseo de cada ronda.

## Salida

- `HTMLs/<url>.txt` — texto procesado con el mismo `cortarTexto` y filtro de
  relevancia que el arañador Python (repo consistente).
- `nutch/crawldb/` — metadatos del arañado (estado, score, fechas por URL).
- `nutch/logs/bitacora_nutch.log` — bitácora del recorrido.

La comparación con las otras implementaciones está en `COMPARACION.md`.

## Referencias

- Apache Nutch. Nota de lanzamiento de Nutch 1.23 (septiembre de 2026).
  https://nutch.apache.org/news/nutch-1.23-release/
- Apache Nutch. Sitio oficial. https://nutch.apache.org/
- Apache Nutch. Tutorial oficial.
  https://cwiki.apache.org/confluence/display/NUTCH/NutchTutorial
- Apache Nutch. Distribución binaria 1.23.
  https://dlcdn.apache.org/nutch/1.23/apache-nutch-1.23-bin.tar.gz
- Apache Nutch. `conf/nutch-default.xml`, documentación de cada propiedad,
  incluida en la distribución.
- Proyecto RIT. `spec.md`, especificación y rúbrica del curso.
- Proyecto RIT. `linkHelpers.py`, `cortarTexto` y filtro de relevancia.