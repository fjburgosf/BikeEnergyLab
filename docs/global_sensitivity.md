# Sensibilidad local y global

La respuesta analizada es la demanda eléctrica de la ruta completa [Wh], antes
de agotar la batería. Los límites del controlador permanecen activos. Interpretar
los índices junto con la factibilidad del perfil prescrito. La sensibilidad depende
del dominio elegido y de los supuestos del modelo.

```powershell
bikeenergylab sensitivity configs/flat.yaml --method oat
bikeenergylab sensitivity configs/flat.yaml --method spearman --samples 256
bikeenergylab sensitivity configs/flat.yaml --method morris --samples 16
bikeenergylab sensitivity configs/flat.yaml --method sobol --samples 256
```

OAT usa diferencias centrales o unilaterales cerca de los límites. Spearman usa
un diseño Latin hypercube y mide asociación marginal de rangos. Morris recorre
trayectorias aleatorias sobre una malla de niveles pares, con paso normalizado
Δ=p/[2(p−1)]. Se guardan μ, μ* y σ de los efectos elementales en Wh por unidad
del parámetro normalizado, además de todas las evaluaciones. σ refleja variación
de efectos por no linealidad e interacciones. No es una desviación del error predictivo.
Referencia: [Morris (1991)](https://doi.org/10.1080/00401706.1991.10484804).

Sobol usa dos matrices A/B de un diseño Sobol aleatorizado en 2d dimensiones y
matrices A_B^i con la columna i de B. Para n potencia de dos:

- S_i = mean[(f(B)−mean(f(A),f(B)))·(f(A_B^i)−f(A))]/Var(f).
- ST_i = mean[(f(A)−f(A_B^i))²]/[2·Var(f)].

Se conservan los estimadores fuera de [0,1]. No se recortan resultados de muestreo.
Para respuesta constante, los índices son indefinidos y se exportan como valores
ausentes. Los intervalos aproximados usan bootstrap de filas emparejadas, con
semilla, y cuantifican error del diseño finito. No prueban certeza sobre bicicletas
reales. Referencia: [Saltelli et al. (2010)](https://doi.org/10.1016/j.cpc.2009.09.018).

Morris y Sobol aquí se definen sobre entradas uniformes independientes con límites
finitos. No se aplican automáticamente a la Gaussian conjunta de Monte Carlo:
los índices ordinarios de Sobol no identifican contribuciones únicas con entradas
dependientes. Los perfiles de viento, temperatura y potencia humana que sustituyen
parámetros escalares se rechazan para evitar una sensibilidad artificialmente nula.
Si existe mapa de eficiencia, elegir parámetros distintos de eficiencia constante.

Los ocho parámetros por defecto son Crr, CdA, masa del ciclista, potencia humana,
velocidad media, viento, temperatura y eficiencia del motor. La velocidad escala
el perfil conservando distancias y duraciones de las paradas. Se recalcula aceleración.
Los intervalos de entrada por defecto son exploratorios, y no distribuciones medidas.
Se pueden especificar límites en `experiment.sensitivity.bounds`:

```yaml
experiment:
  seed: 42
  sensitivity:
    bounds:
      bike.crr: [0.004, 0.01]
      bike.cda_m2: [0.4, 0.7]
      environment.wind_mps: [-3, 3]
    bootstrap: 200
```

La API `uncertainty.global_sensitivity.analyze_global` también acepta respuestas
matemáticas arbitrarias. Las pruebas comprueban efectos lineales de Morris y
índices conocidos de la función de Ishigami, incluyendo su interacción x–z.
