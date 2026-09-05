import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "node_modules", "geist", "dist", "fonts");
const dst = join(here, "..", "public", "fonts");
mkdirSync(dst, { recursive: true });
for (const f of ["geist-sans/Geist-Variable.woff2", "geist-sans/Geist-Italic[wght].woff2", "geist-mono/GeistMono-Variable.woff2"]) {
  copyFileSync(join(src, f), join(dst, f.split("/")[1]));
}
console.log("fonts: Geist copiadas a public/fonts");
