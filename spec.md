# Recuperación de la información textual
## Especificación de Proyecto: El arañador
**por Aurelio Sanabria**

---

### Motivación

Descargar información de sitios web es esencial para mantener actualizadas colecciones de documentos con información fresca y actualizada. Es por esto que para este proyecto diseñaremos un arañador web que se ajuste a los intereses de las personas estudiantes del curso. Tal como se discutió en clase, la temática y funcionalidad de este arañador estará sujeto a las decisiones que tome cada grupo, siempre y cuando estas se justifiquen debidamente.

---

### Objetivos Formativos

El presente proyecto tiene correspondencia con los siguientes objetivos específicos establecidos en el programa del curso de Compiladores e intérpretes (presentado al inicio del semestre):

5. Desarrollar un conocimiento práctico para resolver problemas relacionados con el manejo de texto.
6. Aprender diferentes herramientas y lenguajes usados para el procesamiento de información textual.

---

### Especificación del proyecto

Para este proyecto cada grupo debe recorrer toda la información construida durante el curso, ampliarla con investigación propia para decidir e implementar lo siguiente:

1. **Determinar un tema central** para el buscador y describir las características de la información requerida para descargar, así como caracterizar el colectivo al que se dirige la información.
2. **Implementación de 2 arañadores** para la misma necesidad de información:
   - Uno propio basado en Python.
   - Uno utilizando bibliotecas existentes.
3. **Documentar y justificar** las políticas de arañado que se implementaron.
4. **Repositorio de documentos** de texto plano ya procesado (no HTML, imágenes, audios o videos) de al menos 10 GB.

Cada decisión debe ser documentada y justificada de forma que se evidencie un criterio basado en fuentes bibliográficas confiables. Además se debe comparar la solución hecha en Python contra la implementada en Apache Nutch, Scrapy, Crawler4j o cualquier otra.

---

### Rúbrica

#### Tabla 1: Rubros de calificación

| Rubro | Descripción | Puntos |
| :--- | :--- | :---: |
| **Documento** | Se debe presentar un documento con las siguientes secciones:<br>1. **Portada formal:** nombre del buscador, integrantes, curso, fecha, título.<br>2. **Necesidad de información:** Descripción de la necesidad de información que incluya el tema, sus características, el tipo de consultas esperadas y una caracterización del colectivo al que se dirige la información que incluya (rango etario, contexto socioeconómico, subtemas de interés, consultas esperadas por el colectivo).<br>3. **Políticas de Arañado:** Documentación de las políticas de arañado que se implementaron en el software, cada política debe incluir su nombre, descripción y justificación (haciendo referencia a la necesidad de información y el colectivo destino). Además indicar los metadatos que es necesario almacenar para implementar las políticas.<br>4. **Estadísticas del repositorio creado:** incluye el tamaño total del repositorio, cantidad de documentos, cantidad de palabras, palabras distintas, curva graficada con la frecuencia de las palabras presentes en la totalidad de la colección.<br>5. **URLs semilla:** Al menos 10 URLs con los que inició el arañador.<br>*Agregar imágenes, diagramas, videos, etc...* | 20 |
| **Implementación propia** | Implementación en Python propia que soporte hilos y descarga concurrente (múltiples archivos al mismo tiempo). Debe reflejar las políticas de arañado documentadas y tener un repositorio de datos (archivo de texto, archivo CSV, TinyDB, SQLite, MySQL, etc.).<br><br>Deben poder indicar dónde y cómo se implementa cada política. Además el arañador debe guardar una bitácora (log) que demuestre el recorrido hecho por la araña (no se vale bajar todo de un solo sitio...). | 30 |
| **Implementación con bibliotecas existentes** | Implementación en Apache Nutch, Scrapy, Crawler4j, etc.<br><br>Si no logran que funcione debe igualmente explicar cómo se implementa (proveer amplios tutoriales y poder explicarlos), presentar el código desarrollado, describir verbalmente cómo fallaron, por qué y dónde. Además indicar en qué casos es o no viable implementar la herramienta escogida. | 20 |
| **Análisis de resultados** *(de forma verbal el día de la discusión de resultados)* | El día de la discusión de resultados, las personas integrantes de cada grupo deben estar en capacidad de responder preguntas abiertas sobre el funcionamiento, implementación y resultados del proyecto.<br><br>Deben poder comparar las herramientas y señalar ventajas y desventajas de las implementaciones. Además justificar ventajas y desventajas de las políticas de arañado.<br><br>*En este lugar es donde llegan con antorchas a reclamarme por que el proyecto está muy volado... pero con conclusiones justificadas.* | 20 |
| **Repositorio** | Se debe presentar un repositorio de al menos 10 GB de texto limpio sin imágenes, audio, videos, GIF, JavaScripts, CSS u otros formatos de archivos que no correspondan con la necesidad de información.<br><br>El repositorio debe tener también los metadatos almacenados durante la etapa de arañado en el formato seleccionado por las personas estudiantes. | 20 |
| **Total** | | **110** |
| **Logo** *(Puntos extra)* | Diseño de un logo para el buscador de acuerdo a su necesidad de información. | 2 |
| **Foto icónica** *(Puntos extra)* | Foto icónica del grupo de trabajo, presencial y no en el aula o el pasillo. Que tenga gracia. | 2 |
| **Repositorio extendido** *(Puntos extra)* | Si el tamaño del repositorio aumenta se tomarán como puntos extra de la siguiente forma: 1 punto extra por cada GB adicional sobre los 10 GB. | 1 pt * GB |
| **Memes** *(Puntos extra)* | 1/2 punto por meme original no copiado de internet relacionado a la materia o al trabajo realizado. Que sean chistes profundos. | ½ pt * meme |

#### Tabla 2: Distribución de puntos por calificación

| Excelente | Bueno | Regular | Malo | Deficiente |
| :---: | :---: | :---: | :---: | :---: |
| 5 puntos | 4 puntos | 3 puntos | 2 puntos | 1 punto |

---

### Aspectos Generales

* El proyecto se realizará de acuerdo a los grupos ya formados.
* **Fecha de entrega:** 1 de Octubre, 2026 – 10:00 p.m. GMT-6.
* Se envía al servidor, en una carpeta en formato `tar.gz` que incluya el repositorio de GIT.
* Los trabajos de entrega tardía no se calificarán.
* Se aclararán dudas sobre la programación vía Telegram.
* Pueden debatir con otros grupos sobre posibles formas de resolver los problemas pero las implementaciones deben ser realizadas de forma independiente entre grupos, pues deben estar preparados para defender su trabajo durante una discusión horizontal de resultados.