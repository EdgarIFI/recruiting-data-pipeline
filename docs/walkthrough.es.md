# Recorrido del proyecto y preguntas frecuentes

*English: [walkthrough.md](walkthrough.md)*

Una explicación breve, para decirse en voz alta, seguida de las preguntas que suelen hacerse sobre el proyecto: primero las generales y después las técnicas de un revisor senior de analítica de datos. Todas las cifras corresponden a la corrida por defecto (semilla 2027) con **datos sintéticos**.

---

## La explicación de 90 segundos

> En mi práctica de inteligencia de datos opero un proceso semanal que cruza unas 3,400 alertas de bienestar con 1,700 casos del CRM antes de que lleguen a un tablero. Lo difícil no es el tablero, sino asegurar que los números que lo alimentan sean confiables. Ese trabajo es confidencial, así que reconstruí el método desde cero, en público, sobre un funnel de reclutamiento.
>
> Tres sistemas describen a los mismos candidatos y no coinciden en nueve cosas: duplicados, variantes de escritura, llaves rotas y fechas imposibles. El pipeline identifica cada archivo por su contenido, lo valida en dos capas (pandera para el esquema y reglas escritas a mano para la lógica de negocio), corrige lo que se puede corregir de forma determinística y deja fuera de los KPIs lo que no es confiable. Después construye un modelo en DuckDB y calcula los KPIs en SQL.
>
> Lo que más me importa es cómo se prueba. Siembro errores con un conteo conocido, y la validación tiene que encontrar exactamente esa cantidad, con cualquier semilla, y cero en datos limpios. El análisis reporta intervalos de 95% e incluye un paso de objeción en el que intento romper mis propias conclusiones. Por ejemplo, la limpieza casi no mueve la tasa promedio de contratación, pero un análisis ingenuo vería 19 canales de reclutamiento en lugar de 6 y un time-to-fill negativo.
>
> Está hecho en Python y SQL, con 71 pruebas que corren en CI.

**Versión corta (30 segundos):** *Un pipeline de funnel de reclutamiento que valida los datos antes de calcular KPIs. Cada control de calidad se prueba contra errores sembrados con un conteo conocido: encuentra exactamente los 9 de 9 y nada en datos limpios. Los KPIs están en SQL, se verifican contra pandas, se reportan con intervalos de confianza y se cuestionan en un paso de objeción.*

---

## Parte 1 · Preguntas generales (reclutamiento, RH, equipos de contratación)

**1. ¿Qué es este proyecto, en un minuto?**
Un pipeline que toma datos de reclutamiento de tres sistemas que no coinciden, demuestra que son confiables y solo entonces calcula los KPIs del funnel de contratación. La prueba es que cada control de calidad encuentra exactamente los errores que se sembraron a propósito, y nada en datos limpios.

**2. ¿Por qué lo construiste?**
En mi práctica hago lo mismo con datos confidenciales, así que no puedo mostrarlo. Quería evidencia pública y revisable del método. Elegí reclutamiento porque todo mundo entiende un funnel de contratación.

**3. ¿Los datos son reales?**
No, son sintéticos, generados con una semilla fija. Eso es una ventaja: como sé exactamente qué errores y qué efectos sembré, puedo comprobar que el pipeline los encuentra. Todas las secciones y diapositivas de hallazgos dicen que los datos son sintéticos.

**4. ¿Qué fue lo más difícil?**
Definir qué significa "confiable" en la práctica: qué problemas se pueden corregir automáticamente (WARN) y cuáles significan que la fila no se puede usar (ERROR). Lo segundo más difícil fue que los datos sintéticos fueran realistas. Al revisar mi propio generador encontré cuatro incoherencias, como contrataciones en vacantes canceladas, y las corregí antes de confiar en cualquier resultado.

**5. ¿Qué herramientas usaste?**
Primero Python y SQL: pandas, pandera para la validación, DuckDB para el modelo y los KPIs en SQL, pytest para 71 pruebas y GitHub Actions para correrlas automáticamente. Las gráficas usan matplotlib; el deck del caso está en PowerPoint.

**6. ¿Qué aprendiste?**
Tres cosas. Una validación vale lo que valen sus pruebas. Los promedios esconden errores estructurales: un análisis ingenuo acierta casi en la tasa promedio de contratación, pero se equivoca en los rankings y en los cruces de tablas. Y un resultado sin su incertidumbre invita a tomar la decisión equivocada.

**7. ¿Cómo organizaste el trabajo?**
En dos entregas revisadas, cada una como pull request: primero la ingesta y la validación, después el modelo, los KPIs y el reporte. Luego la documentación y el deck. Cada cambio pasó por integración continua antes de integrarse.

**8. ¿Usaste herramientas de IA?**
Sí, Claude, para código y documentación, y el repositorio lo dice. Yo planteé el problema, tomé las decisiones de diseño, revisé cada cambio antes de integrarlo y validé los resultados. Puedo explicar cada decisión del proyecto, que es el estándar que me exijo.

**9. ¿Cómo se relaciona con el puesto?**
La mayoría de los puestos de analítica necesitan tres cosas que este proyecto muestra: asegurar que los datos sean confiables antes de reportar, escribir y verificar SQL, y explicar resultados, incluida su incertidumbre, a quienes van a actuar con ellos.

**10. ¿Qué harías después?**
Una capa interactiva en Power BI sobre el modelo exportado; detección de duplicados aproximados de candidatos; y corridas programadas con alertas cuando los conteos de calidad de datos se disparen.

---

## Parte 2 · Preguntas técnicas (revisor senior de analítica de datos)

**1. Recuperaste efectos que tú mismo sembraste. ¿No es circular?**
Para los *hallazgos*, sí, y lo digo: los números describen al generador, no a ninguna empresa. Las señales sembradas prueban el *método*. Comprueban que el análisis detecta un efecto real (referidos, seniority) y no inventa uno donde no existe (las otras cinco fuentes). Es una prueba de sensibilidad y especificidad, no evidencia sobre el mundo. Con datos reales validaría contra un periodo de prueba o un benchmark externo.

**2. ¿Por qué pandera más reglas a mano, y no Great Expectations o pruebas de dbt?**
Por escala y legibilidad. pandera es ligero y declarativo para controles por columna. Las reglas entre tablas (una aplicación anterior a la apertura de su vacante) son más claras como código explícito que un revisor puede cuestionar. Las reglas son máscaras booleanas que comparten la validación y la limpieza, así que la bitácora de calidad coincide con el reporte por construcción. En un data warehouse con orquestación, las pasaría a pruebas de dbt o a Great Expectations.

**3. ¿Por qué DuckDB?**
Es SQL analítico dentro del mismo proceso, sin infraestructura, así que cualquiera puede reproducir la corrida con un solo comando. El SQL es estándar (funciones de ventana, `GROUPING SETS`, `FILTER`) y pasaría a Postgres o Snowflake con cambios menores. Los KPIs viven en archivos `.sql` normales, no como texto dentro de Python.

**4. ¿Cómo sabes que el SQL está bien?**
De tres formas. Los KPIs principales se recalculan de forma independiente en pandas y deben coincidir. Los intervalos de Wilson se comparan contra la fórmula cerrada. Y se cumplen controles de consistencia: los rangos de antigüedad y la carga por reclutador cuentan cada vacante abierta, y ningún evento queda después de la fecha de corte.

**5. ¿Por qué intervalos de Wilson? ¿Y "no se traslapan" es una prueba formal?**
Con unos cientos de aplicaciones por fuente y tasas a veces cercanas a 0, la aproximación normal se comporta mal; Wilson mantiene buena cobertura y tiene fórmula cerrada. Que dos intervalos de 95% no se traslapen es una señal *conservadora* de diferencia, y que se traslapen no prueba que no la haya. La versión formal serían pruebas de dos proporciones por pares con corrección de Holm. Para ordenar fuentes de forma justa, usaría un modelo beta-binomial que acerque las muestras chicas a la media.

**6. Tu time-to-fill solo usa vacantes cubiertas. ¿No está sesgado?**
Sí: está censurado por la derecha. Las 15 vacantes abiertas por más de 90 días son justo las lentas, y no entran en la mediana, así que los 41 días reportados son optimistas. El siguiente paso correcto es análisis de supervivencia (Kaplan–Meier, con las vacantes abiertas como observaciones censuradas). Lo reporto como limitación en lugar de esconderlo.

**7. ¿Cómo defines el funnel y qué rompe esa definición?**
Cada aplicación cuenta en todas las etapas hasta la más lejana que alcanzó, lo que supone un funnel monótono. Se rompe con etapas que se saltan y se registran de forma inconsistente, y con candidatos que aplican a varias vacantes: la unidad es la aplicación, no la persona. Un funnel por candidato necesitaría primero resolución de entidades.

**8. ¿Cómo lo llevarías a producción?**
Fecha de corte como parámetro y cargas incrementales; orquestación (Airflow, Prefect o dbt); un contrato de datos con cada dueño de fuente; y la bitácora de calidad guardada en el tiempo, con alertas cuando suban los conteos de WARN o ERROR. El control de drift ya muestra el valor: uno de seis exports cambió de formato.

**9. Alguien del negocio dice que excluir las filas ERROR oculta candidatos reales. ¿Qué respondes?**
No se borra nada salvo los duplicados exactos. Las filas ERROR se marcan y se listan en una bitácora con IDs de ejemplo, para corregirlas en la fuente. El paso de objeción muestra cuánto mueve el resultado cada decisión: aquí las tasas casi no cambian. Si el negocio quiere otro umbral, la decisión queda explícita y su impacto, visible.

**10. ¿Cuál es la parte más débil del proyecto?**
Los datos son sintéticos, así que los hallazgos son tan realistas como el generador. Además: no hay detección aproximada de personas duplicadas, el time-to-fill está censurado y las tasas de contratación por fuente son ruidosas porque las contrataciones están limitadas por el número de plazas. Prefiero enumerarlas yo antes de que las encuentre un revisor.
