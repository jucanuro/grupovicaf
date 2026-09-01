/** @type {import('tailwindcss').Config} */

module.exports = {
  content: [
    './templates/**/*.html',
    './web_*/templates/**/*.html',
    './static/web/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        // Extraídos de _ref/vicafpro/static/css/vicaf.css y de las clases
        // bg-blue-700 / text-blue-700 / bg-blue-900 usadas en header.html y
        // footer.html como color corporativo principal.
        vicaf: {
          primary: '#1d4ed8', // blue-700, color de marca (enlaces activos, CTA)
          dark: '#172554', // blue-950, usado en .menu-item.active de vicaf.css
          accent: '#1e3a8a', // blue-800, hover de nav-link en vicaf.css
        },
      },
      // Escala tipográfica del rediseño (ver CLAUDE.md / encargo de diseño):
      // display para H1 de sección, eyebrow para las etiquetas en mayúscula.
      // body-copy no se define aquí porque max-width:65ch no es una unidad de
      // fontSize válida — vive como clase .body-copy en input.css.
      fontSize: {
        display: ['clamp(2.5rem, 5vw, 4.5rem)', { lineHeight: '0.95', letterSpacing: '-0.03em', fontWeight: '800' }],
        'display-sm': ['clamp(1.875rem, 3vw, 2.75rem)', { lineHeight: '1.05', letterSpacing: '-0.02em', fontWeight: '800' }],
        eyebrow: ['0.75rem', { lineHeight: '1', letterSpacing: '0.15em', fontWeight: '600' }],
        body: ['1.0625rem', { lineHeight: '1.7' }],
      },
      boxShadow: {
        // Sombra en dos capas: una cercana y difusa, otra lejana y sutil.
        layered: '0 2px 8px -2px rgba(15,23,42,0.10), 0 24px 48px -20px rgba(15,23,42,0.20)',
        'layered-lg': '0 4px 12px -2px rgba(15,23,42,0.12), 0 32px 64px -24px rgba(15,23,42,0.28)',
        'btn-primary': '0 8px 20px -6px rgba(29,78,216,0.45)',
        certificate: '0 30px 60px -20px rgba(2,6,23,0.55)',
      },
      borderRadius: {
        card: '16px',
        btn: '10px',
      },
    },
  },
  plugins: [],
}
