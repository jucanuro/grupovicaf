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
    },
  },
  plugins: [],
}
