# Teoría y consideraciones de la curva de calibración

Documento de apoyo para `01_calibration_analysis.ipynb`. Explica qué se mide cuando
se construye una curva de calibración con EGOFETs, cómo se extrae la respuesta, qué
supuestos tiene el modelo y cómo el orden experimental condiciona el resultado. No
sustituye al notebook: lo justifica y deja por escrito las decisiones que allí se
toman.

El documento es deliberadamente general. No reporta resultados de un batch concreto
ni contiene un protocolo de laboratorio; esas dos cosas viven en el notebook y en la
plantilla de medición, respectivamente.

---

## 1. Alcance y fuentes

### 1.1 Qué cubre

- La lectura diferencial del transfer en un punto fijo, en régimen lineal.
- Los dos métodos de extracción: punto único y ventana de puntos.
- El modelo lineal-log, sus unidades y su rango de validez.
- La estadística de repetibilidad y reproducibilidad entre dispositivos.
- El orden experimental y su efecto sobre la forma de la curva.
- La correspondencia entre cada concepto y el código del notebook.

### 1.2 Qué no cubre

- **Fabricación.** Los parámetros de proceso y su efecto sobre el dispositivo se
  documentan en el protocolo del grupo y en el registro de fabricación.
- **Extracción de \(V_{th}\).** Requiere régimen de saturación y un ajuste sobre toda
  la curva; se desarrolla en `notebooks/02_transfer_curves/`.
- **Validación diagnóstica.** Sensibilidad, especificidad y accuracy quedan fuera de
  una curva de calibración analítica.
- **Cálculo experimental del LoD.** El notebook documenta la fórmula, pero no la
  implementa.

### 1.3 Fuentes

| Fuente | Uso en este documento |
|---|---|
| `docs/egofet_hepatitis.pdf` | Definición de la respuesta, punto de lectura, modelo y LoD de referencia |
| `docs/EGOFETs Fabrication Protocol for Group.docx` | Contexto del dispositivo y de la sesión de medida |
| `notebooks/04_calibration_curve/01_calibration_analysis.ipynb` | Implementación concreta de cada paso |
| `notebooks/02_transfer_curves/teoria_saturacion_y_vth.md` | Por qué la extracción de \(V_{th}\) no aplica aquí |
| `notebooks/00_lab_journal/template_measurement.ipynb` | Registro de la sesión de medición |

### 1.4 Notación

| Símbolo | Significado |
|---|---|
| \(V_{GS}\), \(V_{DS}\) | Tensiones puerta-fuente y drenador-fuente |
| \(V_{READ}\) | \(V_{GS}\) fijo en el que se lee la respuesta |
| \(I_{DS}\) | Corriente drenador-fuente en una condición dada |
| \(I_{DS,0}\) | Corriente de la medida `Ref` del mismo dispositivo, en \(V_{READ}\) |
| \(C\) | Concentración del analito, en mol/L |
| \(R\) | Respuesta normalizada, adimensional |
| \(b\) | Pendiente de \(R\) frente a \(\log_{10} C\); sensibilidad por década |
| \(N\) | Número de dispositivos del batch |
| \(n\) | Número de réplicas técnicas de una medición |

---

## 2. Qué mide la curva

### 2.1 Una lectura diferencial en régimen lineal

El dispositivo es un EGOFET con contactos interdigitados de drenador y fuente, una
capa activa orgánica y un electrolito acuoso en contacto con el canal y con la
puerta. La curva transfer se mide barriendo \(V_{GS}\) con \(V_{DS}\) fijo.

En la zona lineal, y escrita en magnitudes, la corriente sigue aproximadamente

$$
|I_{DS}| = \mu\,C_i\,\frac{W}{L}\left[(V_{GS}-V_{th})\,V_{DS}
- \frac{V_{DS}^{2}}{2}\right],
\qquad |V_{DS}| < |V_{GS}-V_{th}|
$$

donde \(\mu\) es la movilidad, \(C_i\) la capacitancia de la doble capa
electrolito/canal y \(W/L\) la relación geométrica del canal.

La curva de calibración **no extrae ninguno de esos parámetros**. Fija \(V_{DS}\) y
lee \(I_{DS}\) en un único \(V_{GS}=V_{READ}\). Lo que cuantifica es cuánto se ha
movido la curva transfer en ese punto:

$$
R = \frac{I_{DS}(V_{READ}) - I_{DS,0}(V_{READ})}{I_{DS,0}(V_{READ})}
$$

\(R\) es, por tanto, una respuesta diferencial. Un cambio de capacitancia de la doble
capa, de movilidad, de resistencia de contacto o del encendido del canal desplaza la
curva y produce el mismo tipo de señal en \(R\). El método no separa esos mecanismos;
los integra en un único número reproducible.

### 2.2 Por qué no se extrae \(V_{th}\)

La extracción de \(V_{th}\) se hace en saturación, ajustando \(\sqrt{|I_{DS}|}\) frente
a \(V_{GS}\) y extrapolando el tramo lineal. Ese procedimiento necesita que el
dispositivo esté en saturación y que el ajuste cubra una parte representativa de la
curva.

Aquí no se cumple ninguna de las dos condiciones: se trabaja en régimen lineal, con
\(V_{DS}\) fijo y pequeño, y se lee un solo punto (o una ventana) del transfer. Por eso
el resultado no es un \(V_{th}\) y no debe presentarse como tal. Lo que se reporta es
el cambio de corriente en \(V_{READ}\), que es una magnitud distinta y con otra
interpretación.

### 2.3 Por qué se lee donde \(|g_m|\) es máxima

La transconductancia mide la pendiente local de la curva:

$$
g_m = \frac{dI_{DS}}{dV_{GS}}
$$

En un transistor ideal la transconductancia sería constante en la zona lineal; en
estos dispositivos tiene un máximo cerca del codo donde la curva empieza a aplanarse.
Ese máximo es el punto donde un cambio pequeño del transfer produce el mayor cambio
medible de \(I_{DS}\), es decir, donde la lectura tiene mejor relación señal/ruido.
No es el punto donde está \(V_{th}\), y elegirlo no convierte la medida en una
extracción de \(V_{th}\).

El máximo se busca en la rama de ida del barrido, se toma su mediana por batch y se
redondea a 0.01 V. Fijar \(V_{READ}\) por batch, y no por curva, evita que la elección
del punto se mezcle con la respuesta al analito: todas las curvas se leen en el mismo
lugar.

> **Cautela.** El máximo de \(|g_m|\) suele quedar cerca del codo lineal-saturación.
> Conviene verificar que en \(V_{READ}\) se sigue cumpliendo
> \(|V_{DS}| < |V_{GS}-V_{th}|\). Si no se cumple, la lectura sigue siendo válida como
> señal empírica del estado del dispositivo, pero deja de interpretarse como lectura
> lineal.

### 2.4 Por qué se normaliza contra el `Ref` del mismo dispositivo

Cada dispositivo tiene su propia corriente base: contactos, geometría efectiva,
espesor de la capa activa y resistencia de acceso. Comparar \(I_{DS}\) en crudo entre
dispositivos mezclaría la respuesta al analito con esa variabilidad de fabricación.

Dividir por \(I_{DS,0}\) elimina la escala de cada dispositivo y deja una magnitud
comparable. Esa es la razón de fondo por la que la curva puede construirse sobre
varios dispositivos: la normalización absorbe la dispersión de fabricación que no
cambia con el analito, y deja visible la que sí cambia. El costo es que la
incertidumbre del `Ref` entra en todos los puntos de la curva (sección 6.3).

### 2.5 Signo de \(R\)

En estos EGOFETs la corriente es negativa. Si al aumentar la concentración disminuye
\(|I_{DS}|\), entonces \(I_{DS}-I_{DS,0}>0\) pero \(I_{DS,0}<0\), y el cociente da
\(R<0\). El signo no es un error: indica la dirección de la respuesta, y la sensibilidad
\(b\) lo hereda.

Si se prefiere una respuesta positiva, puede definirse \(R'=-R\). Lo importante es
usar la misma definición en la figura, en el ajuste y en cualquier cálculo derivado.
Cambiar de definición a mitad del análisis invierte el signo de \(b\) y de la
sensibilidad reportada.

---

## 3. Métodos de extracción

### 3.1 Punto único

Para cada réplica se interpola \(I_{DS}\) en \(V_{READ}\) y se obtiene un valor. La
media de las réplicas de una medición da un punto de la curva; si una condición se
midió varias veces (`_00`, `_01`, …), se promedian las medias de cada medición y se
agrupa su dispersión.

El método es directo y no introduce sesgo por curvatura, pero depende de un solo
punto: una fluctuación local de la curva se propaga entera a \(R\).

### 3.2 Ventana unilateral

En lugar de interpolar un punto, se promedia \(I_{DS}\) sobre un intervalo de
\(V_{GS}\) que arranca en \(V_{READ}\):

$$
\bar I_{DS} = \frac{1}{m}\sum_{V_{GS}\in[V_{READ},\,V_{READ}+w]} I_{DS}(V_{GS})
$$

donde \(w\) es el ancho de la ventana. La ventana es **unilateral hacia el interior**
del barrido porque \(V_{READ}\) cae en el borde negativo: una ventana centrada se
saldría del rango medido.

El promedio reduce la sensibilidad al ruido de un punto, pero introduce un sesgo si
la curva tiene curvatura apreciable dentro de la ventana. Con un ancho pequeño el
sesgo es despreciable y la ganancia en estabilidad es real; con un ancho grande se
empieza a promediar la forma de la curva y no solo el ruido.

### 3.3 Rama forward y punto de retorno

El análisis usa solo la rama de ida del barrido. La rutina que la extrae conserva el
punto de retorno, que repite el \(V_{GS}\) extremo con una diferencia de
\(\sim 10^{-5}\) V. Si ese punto no se elimina, `np.gradient` divide por un paso casi
nulo y genera un pico artificial de \(g_m\) que desplaza \(V_{READ}\).

Por eso la rama se ordena de forma ascendente y se descarta el punto duplicado antes
de derivar. Es un detalle de implementación, pero afecta directamente a la elección
del punto de lectura y, con ello, a toda la curva.

### 3.4 Qué aporta comparar ambos métodos

Punto único y ventana se calculan con el mismo \(V_{READ}\), la misma normalización y
la misma jerarquía de promedios. La comparación entre ambos aísla el efecto de
suavizar la lectura: si las dos curvas coinciden, el ruido de un punto no era
determinante; si difieren, la diferencia informa sobre la curvatura local o sobre la
calidad de la ventana elegida.

El criterio para preferir un método no debería ser cuál produce una pendiente más
grande, sino cuál es más estable entre réplicas y entre dispositivos sin cambiar la
tendencia.

---

## 4. Modelo de calibración

### 4.1 Lineal-log

Sobre un rango limitado de concentraciones, la respuesta se aproxima por una recta
frente al logaritmo decimal de la concentración:

$$
R = a + b\,\log_{10} C
$$

El modelo es empírico. No se deduce de una isoterma de unión concreta; se usa porque
describe bien la respuesta en la ventana de trabajo y porque permite interpolar
concentraciones dentro de esa ventana.

Invirtiendo el modelo se estima una concentración desconocida:

$$
C = 10^{(R-a)/b}
$$

El intercepto \(a\) corresponde a \(C=1\) M, un valor fuera del rango medido. Es un
parámetro de ajuste, no una respuesta física a 1 M.

### 4.2 Unidades de \(b\)

Como \(R\) es adimensional, \(b\) se expresa en **unidades de \(R\) por década**. Si
\(R\) se multiplica por 100, \(b\) queda en % por década. Esa es la forma más clara de
reportarlo, porque no depende de la escala de corriente de cada dispositivo.

El artículo de referencia reporta la sensibilidad en M\(^{-1}\) aunque describe un
ajuste lineal-log. Son dos convenciones distintas y no son convertibles directamente
sin conocer la definición exacta de la respuesta. Al comparar con la literatura
conviene verificar en qué unidades está la pendiente y contra qué variable se ajustó.

### 4.3 Rango de validez

El ajuste solo es válido dentro del intervalo de concentraciones medido. Fuera de él
pueden aparecer dos efectos:

- **Saturación a concentraciones altas.** La respuesta deja de crecer porque la
  superficie se satura; el modelo lineal-log sobreestima el cambio.
- **Pérdida de resolución a concentraciones bajas.** La respuesta se acerca al ruido
  y deja de ser distinguible del blanco.

Extrapolar más allá del rango medido, hacia arriba o hacia abajo, es una
extrapolación del modelo, no una medida.

### 4.4 Límite de detección

El LoD se define a partir de la dispersión del blanco y de la pendiente de la
calibración:

$$
\mathrm{LoD} = \frac{3.3\,\sigma_b}{S}
$$

donde \(\sigma_b\) es la desviación estándar de la respuesta del blanco y \(S\) la
pendiente, ambas en las mismas unidades. El factor 3.3 es una convención habitual, no
un valor universal. En muchos trabajos \(\sigma_b\) se sustituye por la SD de los
residuos del ajuste, \(\sigma_r\), calculada con \(n-2\) grados de libertad.

En este modelo la pendiente es \(b\), en unidades de \(R\) por década, así que
\(3.3\sigma_r/|b|\) tiene unidades de **décadas**, no de concentración. Para obtener
una concentración hay que anclarlo en una respuesta de referencia y exponenciar:

$$
\log_{10} C_{\mathrm{LoD}} = \log_{10} C_{\mathrm{ref}}
\;\pm\; \frac{3.3\,\sigma_r}{|b|}
$$

donde \(C_{\mathrm{ref}}\) es la concentración asociada al blanco o al estándar más
bajo, y el signo depende de si la respuesta crece o decrece con \(C\).

Anclar en la concentración donde el ajuste cruza \(R=0\) es tentador, pero ese cruce
es una extrapolación del modelo y puede quedar lejos del rango medido. Por eso el
LoD así calculado es indicativo, no una medida independiente.

Con pocos puntos (\(n=6\)) \(\sigma_r\) se estima con solo 4 grados de libertad, y si
el blanco se midió una sola vez no hay \(\sigma_b\) que promediar. Conviene reportar
el LoD junto con \(n\), el rango medido y el \(R^2\), y no como una cifra aislada.

---

## 5. Estadística y reproducibilidad

### 5.1 Dos dispersiones distintas

- **Repetibilidad.** Dispersión entre réplicas de una misma medición: mismo
  dispositivo, misma condición, misma sesión. Mide el ruido técnico.
- **Reproducibilidad.** Dispersión entre las medias de dispositivos distintos para la
  misma condición. Incluye fabricación, contactos y montaje.

Las barras de error de las curvas por dispositivo son de repetibilidad. Las barras de
la curva del batch son de reproducibilidad. Mezclarlas produce una barra que no
representa ninguna de las dos cosas.

### 5.2 Promedio jerárquico

Para no mezclar las dos fuentes de dispersión, el promedio se hace en dos niveles:

1. Para cada dispositivo \(d\) y concentración \(C\), media de sus réplicas:

   $$
   \bar R_{d,C} = \frac{1}{n_d}\sum_{k=1}^{n_d} R_{d,C,k}
   $$

2. Para el batch, media de las medias de los dispositivos:

   $$
   \bar R_C = \frac{1}{N}\sum_{d=1}^{N} \bar R_{d,C}
   $$

La dispersión entre dispositivos es

$$
s_C = \mathrm{std}\left(\bar R_{1,C},\dots,\bar R_{N,C}\right)
$$

con `ddof=1`. Si se juntaran todas las réplicas en un único promedio, la SD resultante
mezclaría repetibilidad y reproducibilidad y las barras dejarían de describir la
dispersión entre dispositivos.

### 5.3 SD, SEM y \(N=3\)

Con \(N=3\), la SD entre dispositivos es una estimación ruidosa: su incertidumbre
relativa es grande y un solo dispositivo separado la domina. Por eso se reporta
también el error estándar

$$
\mathrm{SEM} = \frac{s_C}{\sqrt{N}}
$$

y se indica \(N\) en cada concentración.

El SEM describe la incertidumbre de la media del batch, no la dispersión de los
dispositivos. Para una barra que represente cuánto difieren los dispositivos se usa
\(s_C\); para una barra que represente la precisión de la media se usa el SEM. No son
intercambiables.

Si se quiere un intervalo de confianza al 95 % con \(N=3\), el multiplicador correcto
es el de Student con 2 grados de libertad (\(t_{0.975,2}\approx 4.30\)), no 1.96. Con
tan pocos dispositivos, esa diferencia es sustancial.

### 5.4 Ajuste por dispositivo frente a ajuste del batch

El ajuste por dispositivo describe cómo responde cada dispositivo y sirve para
detectar uno problemático. El ajuste del batch describe la respuesta media del
conjunto y es el resultado que se reporta como curva de calibración.

En un diseño balanceado, con las mismas concentraciones para todos los dispositivos,
la pendiente ajustada sobre las medias del batch es la misma que la ajustada sobre
todos los puntos individuales. Lo que cambia es la incertidumbre y el \(R^2\): el
ajuste del batch tiene menos puntos y, por tanto, menos grados de libertad.

Por eso el \(R^2\) del batch se calcula sobre las medias de las concentraciones y no
es directamente comparable con el \(R^2\) por dispositivo. Reportar ambos sin
aclarar el nivel induce a confusión.

### 5.5 Exclusión de dispositivos

Un dispositivo puede excluirse de la curva del batch, pero la decisión debe
justificarse por control de calidad (corriente de fuga, `Ref` inestable, medición
incompleta, contacto defectuoso) y no por el \(R^2\) del ajuste. Excluir el dispositivo
que peor ajusta y reportar solo el resto es una selección posterior al resultado.

La forma correcta de usarlo es como análisis de sensibilidad: calcular la curva con
todos los dispositivos y sin el cuestionado, y reportar ambas. Si la conclusión
cambia, la curva no es robusta y eso es información, no un problema a esconder.

Tampoco deben mezclarse batches ni series distintas en una misma curva. Cada batch
tiene su propio `Ref`, su propio estado de fabricación y, posiblemente, su propio
sentido de respuesta.

---

## 6. Orden experimental

### 6.1 Un archivo, un batch

Se espera que cada archivo HDF5 contenga un batch completo: los tres dispositivos
**D1Bn, D2Bn y D3Bn** dentro del mismo archivo. La nomenclatura de cada medición es

```
DnBm[_etapa]_<condición>_<sufijo>
```

donde `n` identifica el dispositivo, `m` el batch, `<condición>` es `Ref` o `E-XX`
(concentración \(10^{-X}\) M) y `<sufijo>` distingue repeticiones y secuencia de
captura (`_00`, `_01`, …).

El código agrupa por batch a partir de esa estructura y verifica que el archivo
contenga un solo batch. Si un archivo mezcla batches o le falta un dispositivo, la
curva del batch cambia de \(N\) y su SD entre dispositivos deja de ser comparable con
la de un batch completo.

Las mediciones de baseline (`TBE`) no llevan concentración y se excluyen de la
calibración. La etapa (`TAE`, etc.) forma parte del identificador del dispositivo para
no normalizar series distintas contra el mismo `Ref`.

### 6.2 Secuencia de una sesión

El orden habitual es:

1. **Estabilización.** Se aplican \(V_{DS}\) y \(V_{GS}\) fijos en electrolito hasta
   que la corriente alcanza un valor estable. La duración debe registrarse.
2. **Referencia.** Se mide el transfer del dispositivo sin analito y se guarda como
   `Ref`.
3. **Serie de concentraciones.** Se incuba el dispositivo con cada concentración, se
   lava y se mide el transfer.
4. **Repetición.** Si se mide más de una vez la misma condición, se conserva el
   sufijo.

Cada paso introduce un tiempo muerto. Entre la primera y la última concentración
pueden pasar horas, y el dispositivo no es necesariamente el mismo al final que al
principio.

### 6.3 El `Ref` es la pieza más frágil

El `Ref` fija el cero de la curva y la escala de todos los puntos. Si se mide una
sola vez, al inicio, su valor arrastra cualquier deriva posterior y la curva no
distingue entre respuesta al analito y envejecimiento del dispositivo.

El artículo de referencia mide blancos a lo largo del experimento, en las mismas
condiciones que las muestras. Esa práctica permite estimar la deriva y separarla de
la respuesta. Un único `Ref` inicial no lo permite.

Si el diseño solo admite un `Ref`, conviene al menos medirlo antes y después de la
serie, y reportar la diferencia como una estimación de la deriva.

### 6.4 Deriva y sentido de la serie

Si la corriente deriva de forma monótona con el tiempo, el sentido en que se recorre
la serie de concentraciones cambia el signo de la pendiente aparente. Una serie
descendente y una ascendente pueden producir pendientes de signo contrario aunque el
dispositivo responda igual.

Por eso el sentido de la serie es una decisión experimental, no un detalle de
conveniencia. Debe fijarse, registrarse y mantenerse dentro de un mismo batch. Dos
batches medidos en sentidos opuestos no son directamente comparables sin un control
de deriva.

### 6.5 Variables que deben permanecer fijas

Dentro de una serie de calibración, y preferiblemente dentro de un batch:

- \(V_{DS}\), incluido su signo.
- \(V_{READ}\), que se fija por batch a partir de \(g_m\).
- El electrolito y su composición.
- El tiempo de incubación y el protocolo de lavado.
- El orden de los dispositivos, o su aleatorización declarada.

Un cambio de \(V_{DS}\) a mitad de serie rompe la comparabilidad aunque la curva
siga pareciendo razonable. Si ocurre, debe documentarse y tratarse como una serie
distinta.

### 6.6 Lo que no queda registrado

El HDF5 guarda la geometría de barrido, los parámetros del instrumento y la marca de
tiempo, pero no la temperatura, la humedad, el electrolito, el tiempo de incubación
ni el operador. Esas variables afectan la respuesta y no pueden recuperarse después.

Si se quiere que la curva sea interpretable, deben registrarse en la plantilla de
medición y referenciarse desde el nombre del archivo o del batch.

---

## 7. Correspondencia con el código

### 7.1 Flujo de datos

```
HDF5
 └─ list_measurements                 una entrada por medición
     └─ CALIBRATION_RE                filtra DnBm[_etapa]_<cond>_<sufijo>
         └─ parse_measurement_name    separa dispositivo, etapa, condición, sufijo
             └─ i_ds_at / i_ds_window_mean   una lectura por réplica
                 └─ collapse_conditions       una fila por dispositivo+condición
                     └─ R = (I - I0)/I0       normalización por dispositivo
                         ├─ log_fit            ajuste por dispositivo
                         └─ batch_curve        media y SD entre dispositivos
                             └─ fit_summary    ajuste y comparación del batch
```

### 7.2 Tabla concepto → código

| Concepto | Celda | Variable o función |
|---|---|---|
| Descubrimiento de mediciones | `1a8c77e8`, `9ef4e9a5` | `list_measurements`, `CALIBRATION_RE` |
| Batch y dispositivo | `df43ca37` | `get_batch_name`, `parse_measurement_name` |
| Rama forward limpia | `gm_vread_code` | `clean_forward_branch`, `forward_gm` |
| Elección de \(V_{READ}\) | `gm_vread_code` | `df_gm`, `V_READ_BY_BATCH`, `V_READ` |
| Lectura en un punto | `pts_extract` | `i_ds_at`, `df_pts_raw`, `collapse_conditions`, `df_pts` |
| Normalización | `pts_norm` | `R`, `R_sd` |
| Ventana de lectura | `win_calc`, `win_compare` | `window_bounds`, `window_mask`, `i_ds_window_mean`, `df_win` |
| Ajuste por dispositivo | `log_slope_code` | `log_fit`, `fits_pt`, `fits_win` |
| Curva del batch | `batch_agg_code` | `batch_curve`, `excluded_mask`, `df_batch_pts`, `df_batch_win` |
| Ajuste y comparación del batch | `batch_fit_code` | `fit_summary`, `df_fit_batch` |

### 7.3 Decisiones numéricas fijas

| Decisión | Valor | Dónde |
|---|---|---|
| Puntos mínimos por curva | `MIN_POINTS = 5` | `gm_vread_code` |
| Rama usada | `direction='fwd'` | todo el notebook |
| \(V_{READ}\) | mediana por batch, redondeada a 0.01 V | `gm_vread_code` |
| Ancho de ventana | `V_WINDOW = 0.05` V, `V_WINDOW_SIDE='inward'` | `win_calc` |
| SD de réplicas | `ddof=1` | `pts_extract`, `win_compare` |
| SD combinada entre mediciones | \(\sqrt{\langle s_i^2\rangle}\) | `_pooled_sd` |
| Incertidumbre de \(R\) | \(s_R = s_{I_{DS}}/\lvert I_{DS,0}\rvert\), `Ref` constante | `pts_norm`, `win_compare` |
| SD entre dispositivos | `ddof=1` | `batch_curve` |
| Ajuste | OLS no ponderado sobre las medias | `fit_summary` |
| Exclusión de dispositivos | por nombre completo o prefijo (`D2`) | `excluded_mask` |

La comprobación de un solo batch por archivo es explícita: si el archivo contiene
mediciones de más de un batch, el notebook lanza un error en lugar de promediarlas.

---

## 8. Limitaciones y referencias

### 8.1 Limitaciones del diseño actual

- **Un `Ref` al inicio.** La deriva temporal no se separa de la respuesta; el sentido
  de la serie condiciona el signo de \(b\).
- **Sin blancos intercalados.** No hay una estimación de la línea base a lo largo de
  la sesión.
- **\(N=3\).** La SD entre dispositivos es ruidosa y el intervalo de confianza exige
  el multiplicador de Student.
- **Sin aleatorización.** El orden de dispositivos y concentraciones puede introducir
  un sesgo sistemático.
- **Variables ambientales no registradas.** Temperatura, humedad y electrolito no
  están en el HDF5.
- **Lectura cerca del codo.** El máximo de \(|g_m|\) puede caer en el límite del
  régimen lineal; la condición de linealidad debe verificarse.
- **\(R\) integra mecanismos.** No distingue capacitancia, movilidad, contacto y
  encendido.
- **LoD no calculado.** La fórmula está documentada, pero no implementada; con \(n=6\)
  su incertidumbre es alta.
- **Sin extrapolación.** El modelo solo es válido dentro del rango medido.
- **Batches no mezclables.** Cada batch tiene su `Ref` y su estado; promediarlos
  requiere justificar que son comparables.

### 8.2 Referencias

- Ortiz-Aguayo, M. J.; López-Marzo, A. M.; Pan, M.; Gutiérrez, D.;
  Martínez-Domingo, C.; Mas-Torrent, M. *Portable electrolyte-gated organic
  field-effect transistor platform for enabling ultrasensitive and rapid detection of
  hepatitis B and C.* Biosensors and Bioelectronics **310** (2026) 118804.
- `docs/EGOFETs Fabrication Protocol for Group.docx`.
- `notebooks/04_calibration_curve/01_calibration_analysis.ipynb`.
- `notebooks/02_transfer_curves/teoria_saturacion_y_vth.md`.
- `notebooks/00_lab_journal/template_measurement.ipynb`.
