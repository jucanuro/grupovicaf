/* Centrado automático del marco de recorte (fotos de ensayos).
 *
 * Al cargar la foto, busca el objeto principal (la probeta, la probeta con la
 * pizarra o el display de la prensa) y devuelve el marco de la proporción
 * pedida centrado sobre él, con un margen. Corre en el mismo celular, sin
 * internet ni librerías: compara cada píxel con el color del fondo (el borde
 * de la foto) y con los bordes de la imagen, separa con el umbral de Otsu y
 * toma la mancha conectada más grande. Si no encuentra algo razonable
 * devuelve null y el marco queda centrado como antes. El técnico siempre
 * puede moverlo.
 */
(function (global) {
    'use strict';

    var LADO = 256;          // resolución de análisis
    var MARGEN = 0.10;       // aire alrededor del objeto (10 % por lado)

    function mediana(valores) {
        var v = valores.slice().sort(function (a, b) { return a - b; });
        return v[Math.floor(v.length / 2)] || 0;
    }

    function otsu(datos) {
        var hist = new Array(256).fill(0), i, total = datos.length;
        for (i = 0; i < total; i++) hist[datos[i]]++;
        var suma = 0;
        for (i = 0; i < 256; i++) suma += i * hist[i];
        var sumaB = 0, wB = 0, mejor = 0, umbral = 128;
        for (i = 0; i < 256; i++) {
            wB += hist[i];
            if (!wB) continue;
            var wF = total - wB;
            if (!wF) break;
            sumaB += i * hist[i];
            var mB = sumaB / wB, mF = (suma - sumaB) / wF;
            var entre = wB * wF * (mB - mF) * (mB - mF);
            if (entre > mejor) { mejor = entre; umbral = i; }
        }
        return umbral;
    }

    /** Puntaje 0-255 por píxel: diferencia con el fondo + fuerza de borde. */
    function puntajes(px, w, h) {
        var n = w * h, i, x, y;
        var r = [], g = [], b = [];
        var franja = Math.max(2, Math.round(Math.min(w, h) * 0.06));
        for (y = 0; y < h; y++) {
            for (x = 0; x < w; x++) {
                if (x < franja || y < franja || x >= w - franja || y >= h - franja) {
                    i = (y * w + x) * 4;
                    r.push(px[i]); g.push(px[i + 1]); b.push(px[i + 2]);
                }
            }
        }
        var fr = mediana(r), fg = mediana(g), fb = mediana(b);
        var gris = new Float32Array(n), dif = new Float32Array(n), maxDif = 1;
        for (i = 0; i < n; i++) {
            var k = i * 4;
            gris[i] = 0.299 * px[k] + 0.587 * px[k + 1] + 0.114 * px[k + 2];
            var dr = px[k] - fr, dg = px[k + 1] - fg, db = px[k + 2] - fb;
            dif[i] = Math.sqrt(dr * dr + dg * dg + db * db);
            if (dif[i] > maxDif) maxDif = dif[i];
        }
        var borde = new Float32Array(n), maxBorde = 1;
        for (y = 1; y < h - 1; y++) {
            for (x = 1; x < w - 1; x++) {
                i = y * w + x;
                var gx = gris[i + 1] - gris[i - 1], gy = gris[i + w] - gris[i - w];
                borde[i] = Math.sqrt(gx * gx + gy * gy);
                if (borde[i] > maxBorde) maxBorde = borde[i];
            }
        }
        var salida = new Uint8Array(n);
        for (i = 0; i < n; i++) {
            salida[i] = Math.min(255, Math.round(255 * (0.75 * dif[i] / maxDif + 0.25 * borde[i] / maxBorde)));
        }
        return salida;
    }

    /** Caja de la mancha conectada más grande de la máscara (o null). */
    function manchaMayor(mascara, w, h) {
        var visto = new Uint8Array(w * h), cola = new Int32Array(w * h);
        var mejor = null, mejorArea = 0;
        for (var inicio = 0; inicio < w * h; inicio++) {
            if (!mascara[inicio] || visto[inicio]) continue;
            var cab = 0, fin = 0, area = 0;
            var x0 = w, y0 = h, x1 = 0, y1 = 0;
            cola[fin++] = inicio; visto[inicio] = 1;
            while (cab < fin) {
                var p = cola[cab++], px = p % w, py = (p - px) / w;
                area++;
                if (px < x0) x0 = px; if (px > x1) x1 = px;
                if (py < y0) y0 = py; if (py > y1) y1 = py;
                var vecinos = [px > 0 ? p - 1 : -1, px < w - 1 ? p + 1 : -1, py > 0 ? p - w : -1, py < h - 1 ? p + w : -1];
                for (var v = 0; v < 4; v++) {
                    var q = vecinos[v];
                    if (q >= 0 && mascara[q] && !visto[q]) { visto[q] = 1; cola[fin++] = q; }
                }
            }
            if (area > mejorArea) { mejorArea = area; mejor = { x0: x0, y0: y0, x1: x1, y1: y1, area: area }; }
        }
        return mejor;
    }

    /** Cierra huecos pequeños (dilatación + erosión 3x3) para unir la probeta. */
    function cerrar(m, w, h, pasos) {
        function op(src, dilatar) {
            var dst = new Uint8Array(w * h);
            for (var y = 0; y < h; y++) {
                for (var x = 0; x < w; x++) {
                    var res = dilatar ? 0 : 1;
                    for (var dy = -1; dy <= 1; dy++) {
                        for (var dx = -1; dx <= 1; dx++) {
                            var xx = x + dx, yy = y + dy;
                            var val = (xx < 0 || yy < 0 || xx >= w || yy >= h) ? (dilatar ? 0 : 1) : src[yy * w + xx];
                            if (dilatar && val) res = 1;
                            if (!dilatar && !val) res = 0;
                        }
                    }
                    dst[y * w + x] = res;
                }
            }
            return dst;
        }
        var r = m;
        for (var i = 0; i < pasos; i++) r = op(r, true);
        for (i = 0; i < pasos; i++) r = op(r, false);
        return r;
    }

    /** Marco de proporción `aspecto` (ancho/alto) que contiene la caja, en px de la foto. */
    function encuadrar(caja, aspecto, W, H) {
        var bw = caja.width * (1 + 2 * MARGEN), bh = caja.height * (1 + 2 * MARGEN);
        var ancho = Math.max(bw, bh * aspecto), alto = ancho / aspecto;
        if (ancho > W) { ancho = W; alto = ancho / aspecto; }
        if (alto > H) { alto = H; ancho = alto * aspecto; }
        var cx = caja.x + caja.width / 2, cy = caja.y + caja.height / 2;
        var x = Math.min(Math.max(cx - ancho / 2, 0), W - ancho);
        var y = Math.min(Math.max(cy - alto / 2, 0), H - alto);
        return { x: Math.round(x), y: Math.round(y), width: Math.round(ancho), height: Math.round(alto) };
    }

    /**
     * fuente: <img> o <canvas> ya cargado. aspecto: ancho/alto del marco.
     * anchoReal/altoReal: tamaño de la foto en el que se expresa el resultado
     * (por defecto el de la fuente). Devuelve {x, y, width, height} o null.
     */
    function sugerir(fuente, aspecto, anchoReal, altoReal) {
        var W0 = fuente.naturalWidth || fuente.width, H0 = fuente.naturalHeight || fuente.height;
        if (!W0 || !H0) return null;
        var esc = LADO / Math.max(W0, H0);
        var w = Math.max(16, Math.round(W0 * esc)), h = Math.max(16, Math.round(H0 * esc));
        var lienzo = document.createElement('canvas');
        lienzo.width = w; lienzo.height = h;
        var ctx = lienzo.getContext('2d', { willReadFrequently: true });
        try {
            ctx.drawImage(fuente, 0, 0, w, h);
            var px = ctx.getImageData(0, 0, w, h).data;
        } catch (e) {
            return null;
        }
        var s = puntajes(px, w, h);
        var umbral = Math.max(otsu(s), 40);
        var mascara = new Uint8Array(w * h);
        for (var i = 0; i < w * h; i++) mascara[i] = s[i] > umbral ? 1 : 0;
        mascara = cerrar(mascara, w, h, 2);
        var m = manchaMayor(mascara, w, h);
        if (!m) return null;
        var frac = m.area / (w * h);
        var cajaFrac = ((m.x1 - m.x0 + 1) * (m.y1 - m.y0 + 1)) / (w * h);
        if (frac < 0.01 || cajaFrac > 0.92) return null;   // nada claro o todo es "objeto"

        var Wr = anchoReal || W0, Hr = altoReal || H0;
        var fx = Wr / w, fy = Hr / h;
        var caja = { x: m.x0 * fx, y: m.y0 * fy, width: (m.x1 - m.x0 + 1) * fx, height: (m.y1 - m.y0 + 1) * fy };
        return encuadrar(caja, aspecto, Wr, Hr);
    }

    global.CentradoFoto = { sugerir: sugerir, encuadrar: encuadrar };
})(window);
