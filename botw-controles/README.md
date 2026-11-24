# Presets de controles para BOTWRecompAndroid

Son líneas `bind_pad_*` para el archivo de ajustes de la app. No hace falta compilar nada.

## Dónde va

`Android/data/com.mamcjr.botwrecompandroid/files/botwrecompandroid.ini`

Cada versión del juego tiene su propio archivo:

| Versión | Archivo |
|---|---|
| 1.0.0 | `files/botwrecompandroid.ini` |
| 1.6.0 | `files/v160/botwrecompandroid.ini` |
| 1.8.2 | `files/v182/botwrecompandroid.ini` |
| 1.9.0 | `files/v190/botwrecompandroid.ini` |

1. **Cierra la app del todo**, porque al salir vuelve a escribir el archivo.
2. Abre el `.ini` con un editor de texto y borra cualquier línea `bind_pad_` que ya tenga.
3. Pega **un solo** preset al final.
4. Abre la app. Para volver a lo de siempre, usa *Restablecer* en la pestaña Controles o borra las líneas.

## Cómo se lee una línea

`bind_pad_<botón de Switch> = <botón físico, por posición>`

- **Botones de Switch:** `a b x y l r zl zr plus minus lstick rstick left up right down`
- **Botones físicos:** `south east west north lshoulder rshoulder ltrigger rtrigger start back lstick rstick dpad_up dpad_down dpad_left dpad_right`

Equivalencias de las posiciones:

| Posición | Mando Switch | Mando Xbox |
|---|---|---|
| south (abajo) | B | A |
| east (derecha) | A | B |
| west (izquierda) | Y | X |
| north (arriba) | X | Y |

Por defecto la app usa la posición de Nintendo: `a = east`, `b = south`, `x = north`, `y = west`.

Los ajustes no van por tipo de mando: el preset se aplica a cualquier mando que conectes, sea de Switch o de Xbox.
Cada botón de Switch admite un solo botón físico. Si dos líneas usan el mismo, la pestaña Controles las marca en rojo.

---

## Preset 1: Xbox por letra (A = A, B = B…)

Pensado para mandos Xbox. Confirmas con la A de Xbox y saltas con la X de Xbox.

```ini
bind_pad_a = south
bind_pad_b = east
bind_pad_x = west
bind_pad_y = north
```

## Preset 2: saltar con el botón de abajo

Cambia saltar (X) por correr/cancelar (B). Saltas con el botón de abajo (B de Switch, A de Xbox) y corres o cancelas
con el de arriba (X de Switch, Y de Xbox). A e Y se quedan donde estaban.
En un mando Xbox queda así: saltar con A, correr con Y, acción con B y atacar con X.

En los menús, “atrás” también pasa al botón de arriba.

```ini
bind_pad_x = south
bind_pad_b = north
```

## Preset 3: preset 2 y el arco en R/RB

Lo mismo que el preset 2, y además cambia R por ZR: el arco pasa a R/RB y lanzar el arma a ZR/RT.

```ini
bind_pad_x = south
bind_pad_b = north
bind_pad_r = rtrigger
bind_pad_zr = rshoulder
```
