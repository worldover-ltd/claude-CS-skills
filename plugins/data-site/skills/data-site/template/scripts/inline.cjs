/**
 * Inlines Parcel's dist output into a single self-contained bundle.html.
 * Unlike html-inline, escapes `<script` / `</script` inside the JS: React ships
 * a literal "<script><\/script>" string, and the HTML parser would otherwise
 * treat it as real markup and swallow the rest of the document. `<\script` is
 * the same string value in JS (unknown escapes collapse), so behaviour is kept.
 */
const fs = require('fs')
const path = require('path')

const dist = path.join(__dirname, '..', 'dist')
const out = path.join(__dirname, '..', 'bundle.html')

let html = fs.readFileSync(path.join(dist, 'index.html'), 'utf8')

const read = (href) => fs.readFileSync(path.join(dist, path.basename(href)), 'utf8')

html = html.replace(
  /<link rel=stylesheet href=([^\s>]+)>/g,
  (_, href) => `<style>${read(href)}</style>`,
)

html = html.replace(
  /<script type=module src=([^\s>]+)><\/script>/g,
  (_, src) =>
    `<script type="module">${read(src).replace(/<(\/?)script/gi, '<\\$1script')}</script>`,
)

fs.writeFileSync(out, html)
console.log(`bundle.html: ${(fs.statSync(out).size / 1024).toFixed(0)}K`)
