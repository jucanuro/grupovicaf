# Validación en vivo de formularios (`form_validador.js`)

Módulo JavaScript común que agrega, a cualquier formulario de captura del LIMS,
un **contador de caracteres** y **validación del contenido al salir del campo**,
sin escribir JS por formulario.

- Código: `static/js/form_validador.js`
- CSS: `templates/base_vicafpro.html` (bloque `<style>`, junto a `.lista-cargando`)
- Se carga globalmente desde `base_vicafpro.html`, después de `lista_buscador.js`.

## Por qué existe

Los formularios del proyecto **no usan `django.forms`**: cada vista lee
`request.POST.get(...)` a mano y llama `Model.objects.create()` / `instance.save()`
directamente. Como `save()` no ejecuta `full_clean()`, el `max_length` de los
campos nunca se valida en Python: un valor demasiado largo llega a PostgreSQL y
revienta con `value too long for type character varying(N)`, que la vista muestra
como "error inesperado".

Este módulo ataca el lado del cliente:

- pone `maxlength` en cada `<input>`/`<textarea>` de texto → el navegador no deja
  escribir de más, así que el crash de `varchar(N)` ya no ocurre por la vía normal
  del formulario;
- valida longitud mínima, obligatoriedad y formato (email / URL / regex) al salir
  del campo, con mensajes claros;
- frena el envío si algo está mal y enfoca el primer campo inválido.

> **Un `curl` directo o un cliente que ignore el HTML todavía puede mandar datos
> inválidos.** La validación de servidor sigue siendo necesaria (ver
> [Pendiente](#pendiente)).

## Cómo se usa en una plantilla

En cada campo de texto:

```html
<label>Razón Social <span class="text-red-500">*</span></label>

<input type="text" name="razon_social"
       data-validar
       data-label="Razón social"      <!-- nombre para los mensajes -->
       required                         <!-- campo obligatorio -->
       data-min="2"                     <!-- longitud mínima (opcional) -->
       maxlength="255"                  <!-- longitud máxima; alimenta el contador -->
       data-patron="^\d{11}$"           <!-- regex extra (opcional) -->
       data-mensaje="El RUC debe tener 11 dígitos numéricos."
       data-tipo="email"               <!-- email | url | text (por defecto) -->
       class="js-input ...">

<div class="campo-estado" data-for="razon_social">
    <span class="campo-msg" data-msg>{{ errors.razon_social }}</span>
    <span class="campo-contador" data-contador></span>
</div>
```

Reglas:

| Atributo | Efecto |
|---|---|
| `data-validar` | marca el campo para que el módulo lo tome |
| `class="js-input"` | necesario para que el borde cambie de color |
| `data-label` | texto que se usa en los mensajes ("X es obligatorio", "X: máximo N…") |
| `required` | obligatorio (poné además el `<span class="text-red-500">*</span>` en el label) |
| `data-min` | longitud mínima |
| `maxlength` | longitud máxima **y** valor del contador; sin esto no hay contador |
| `data-patron` + `data-mensaje` | regex adicional y su mensaje |
| `data-tipo="email"` / `"url"` | valida formato de correo / URL cuando el campo tiene contenido |

Y el `<div class="campo-estado" data-for="<name>">` debe ir **inmediatamente
debajo** del campo (o de su contenedor si el input está envuelto), con el mismo
`name` en `data-for`. El `<span data-msg>` puede venir pre-rellenado con el error
del servidor (`{{ errors.campo }}` o `{{ form.campo.errors.0 }}`): el módulo lo
detecta y deja el campo marcado como inválido al cargar.

Además: poné **`novalidate`** en el `<form>` para que este módulo controle el
feedback y no aparezcan también los globos nativos del navegador.

## Comportamiento

| Momento | Qué pasa |
|---|---|
| Al enfocar | aparece el contador `n/max` abajo a la derecha (gris → ámbar al 80% → rojo al 100%) |
| Al salir del campo (`blur`) | se valida; el borde se pone verde (ok) o rojo (error); el mensaje aparece a la izquierda, o un check verde `✓` si quedó válido |
| Mientras se corrige | una vez marcado inválido, se revalida en cada tecla y el error se limpia solo |
| Al enviar | si hay algún inválido, no se envía, y se enfoca + centra el primero |
| Layout | la línea de estado tiene altura fija (`min-height`), la grilla no salta |

Sin JS (o si el módulo no carga), el formulario funciona igual que antes y el
error del servidor se ve igual (el `.campo-msg` es rojo por defecto).

## Evento `validador:rechazado`

Cuando el módulo frena un envío, dispara este evento en el `<form>` **antes** de
enfocar el campo, para que la plantilla pueda revelarlo (cambiar de pestaña,
abrir un acordeón, etc.):

```js
document.getElementById('mi-form').addEventListener('validador:rechazado', function (e) {
    var campo = e.detail.campo;           // el primer <input> inválido
    // ... revelar el campo si está oculto ...
});
```

Ejemplo real: `proyectos/recepcion_form.html`, `servicios/cotizaciones_form.html`
y `servicios/plantilla_form.html` lo usan para volver a la pestaña del primer
campo inválido.

## Modales que envían por AJAX

Los modales de alta rápida (`categoria_modal`, `subcategoria_modal`,
`cliente_modal`, `tipo_muestra_modal`) mandan con `fetch` desde su propio
listener de `submit` (`handleAjaxForm` en `cotizacion-config.js`, o el bloque
del modal en `recepcion_form.html`). Para que el módulo pueda **frenar** ese
envío cuando algo es inválido, su listener de `submit` llama
`e.stopImmediatePropagation()`, que corta los demás listeners del mismo `<form>`.
Como `form_validador.js` se carga antes que los scripts de cada página, su
listener corre primero. Nada extra que hacer en la plantilla: alcanza con el
marcado `data-validar` + `.campo-estado` y `novalidate` en el `<form>`.

## Estado de aplicación

### Aplicado

| Formulario | Campos con contador + validación | Validación de servidor |
|---|---|---|
| `clientes/clientes_form.html` | razón social, RUC (11 dígitos), dirección, persona/​cargo/​celular de contacto, sitio web, correo | **pendiente** (vista manual) |
| `trabajadores/trabajadores_form.html` | usuario, email, nombre completo, título profesional | pendiente (vista manual) |
| `trabajadores/rol_form.html` | nombre del rol | pendiente (vista manual) |
| `servicios/norma_form.html` | código, nombre | **OK** (`CreateView`/`UpdateView`); el template ahora muestra `form.*.errors` |
| `servicios/metodo_form.html` | código, nombre | **OK** (ídem) |
| `servicios/servicios_form.html` | código de facturación, nombre (máx **200**, no 300), unidad | **parcial** (`_procesar_guardado_servicio` valida nombre 2–200 y código 2–50); se agregó el banner de error que faltaba |
| `proyectos/recepcion_form.html` | procedencia, responsable de entrega, teléfono (pestaña "Control") | pendiente (vista manual) |
| `servicios/cotizaciones_form.html` | atención, correo, teléfono, asunto (pestaña "cliente"); **sin `required`** para no cambiar el comportamiento actual | pendiente (vista manual) |
| `servicios/plantilla_form.html` | nombre de plantilla, asunto referencial (pestaña "general") | pendiente (vista manual) |
| `servicios/modals/categoria_modal.html` · `subcategoria_modal.html` | nombre (2–100) | **OK** (`crear_categoria_ajax` / `crear_subcategoria_ajax` validan 2–100) |
| `proyectos/modals/tipo_muestra_modal.html` | nombre (2–100), sigla (1–**5**) | **parcial** (`crear_tipo_muestra_ajax` valida nombre 2–100 y sigla 1–10 — mal, la columna es 5) |
| `servicios/modals/cliente_modal.html` | mismos campos que `clientes_form` (RUC 11 dígitos, razón social ≤200, etc.) | **flojo** (`crear_cliente_ajax`, ver abajo) |

Los campos obligatorios llevan un `*` rojo en la etiqueta. En los formularios
dinámicos solo se tocaron los campos de texto "de cabecera": las filas
repetibles (`name="campo[]"`) y los `*_json` ocultos quedan a cargo del JS propio
de cada página.

### Omitido (no aplica)

| Formulario | Motivo |
|---|---|
| `proyectos/informes_form.html` | no tiene campos de texto: solo `archivo_pdf` (file) y selects |
| `trabajadores/permiso_form.html` | el único campo editable de texto es `descripcion`, un `TextField` opcional sin límite; `codigo`/`nombre` son `editable=False` |
| `proyectos/ensayos_form.html` | no tiene campos de texto estáticos: todo es `name="campo[]"` dinámico, fechas y números; los `<input type="text">` visibles de norma/método son espejos de sus `hidden` |
| `trabajadores/modals/rol_modal.html` | no tiene `<form>` y los inputs usan `id` en vez de `name` (`saveNewRol()` a mano); solo se le agregó `maxlength`. Para el tratamiento completo hay que envolverlo en `<form>` y tocar `trabajadores-config.js` |

### Pendiente

- **Validación de servidor** en las vistas de captura manual (cliente,
  trabajador, rol, recepción, cotización, plantilla): hoy validan a lo sumo
  unicidad, no longitud ni formato. Opciones: validar en la vista, o
  `validators` en el modelo + `full_clean()`.
- **`required` en cotización / plantilla**: el modelo marca
  `persona_contacto` / `correo_contacto` / `telefono_contacto` /
  `asunto_servicio` como obligatorios, pero ni el formulario ni la vista lo
  exigen. Se dejó **sin** `required` para no cambiar el comportamiento; decidir
  si conviene exigirlos.
- **Endpoints AJAX con límites mal puestos** (revientan contra la columna a
  pesar de "validar"):
  - `crear_cliente_ajax` — RUC `8 ≤ len ≤ 20` (debe ser 11 exactos),
    `direccion ≤ 300` (columna 255), `razon_social ≤ 200` (columna 255).
  - `crear_tipo_muestra_ajax` — `sigla 1–10` (columna 5).
  El `maxlength` de las plantillas ya tapa estos casos por la UI, pero la regla
  del servidor sigue floja.
- **`trabajadores/modals/rol_modal.html`**: envolver en `<form>` + `name` para
  que tome el módulo (hoy solo tiene `maxlength`).

## Nota aparte: acceso a `recepcion_form.html`

No hay un botón funcional para **crear** una recepción nueva:

- el botón "Nueva Recepción" en `proyectos/lista_general_recepciones.html` tiene
  `href="#"` (muerto en el código heredado);
- la acción "Registrar muestras" en `proyectos/pendientes/` solo aparece para
  proyectos en etapa `PENDIENTE_MUESTRAS`.

Para llegar al formulario en desarrollo:

```
/proyectos/recepcion/nueva/<proyecto_id>/     # crear (campos editables)
/proyectos/recepcion/editar/<pk>/             # editar (los campos de "Control" no se reescriben)
```
