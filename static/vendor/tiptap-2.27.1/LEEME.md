# TipTap 2.27.1 (paquete propio)

Editor del informe tipo Word (`static/js/informe_editor.js`). Se sirve desde
nuestro servidor, sin CDN. `tiptap.min.js` expone `window.TiptapVicaf` y se
construyó así a partir de `entrada.js`:

```bash
npm install --save-exact @tiptap/core@2.27.1 @tiptap/pm@2.27.1 @tiptap/starter-kit@2.27.1 \
  @tiptap/extension-underline@2.27.1 @tiptap/extension-table@2.27.1 @tiptap/extension-table-row@2.27.1 \
  @tiptap/extension-table-cell@2.27.1 @tiptap/extension-table-header@2.27.1 \
  @tiptap/extension-text-align@2.27.1 @tiptap/extension-placeholder@2.27.1 esbuild@0.25.0
npx esbuild entrada.js --bundle --minify --format=iife --global-name=TiptapVicaf \
  --legal-comments=eof --outfile=tiptap.min.js
```

Licencias: TipTap (MIT, © überdosis GbR) y ProseMirror (MIT, © Marijn Haverbeke
y otros). Los avisos de licencia incluidos por los paquetes van al final de
`tiptap.min.js`.
