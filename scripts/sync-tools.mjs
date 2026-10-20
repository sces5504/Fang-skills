// Copy only deployable ff-tool assets into the existing /docs Pages source.
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const root = new URL('../',import.meta.url);
export const files = ['index.html','style.css','app.mjs','core.mjs','templates/bash.txt','templates/powershell.txt'];
for (const file of files) {
  const source = new URL(`tools/ffmpeg-compressor/${file}`,root);
  const destination = new URL(`docs/tools/ffmpeg-compressor/${file}`,root);
  const bytes = await readFile(source);
  if (process.argv.includes('--check')) {
    if (!bytes.equals(await readFile(destination))) throw new Error(`Pages copy is stale: ${file}`);
  } else {
    await mkdir(fileURLToPath(new URL('./',destination)),{recursive:true});
    await writeFile(destination,bytes);
  }
}
console.log(process.argv.includes('--check') ? 'Pages tool assets match source.' : 'Pages tool assets synchronized.');
