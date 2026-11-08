import { cp, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

// Keep browser .js files and their real query-string imports in an ESM sandbox.
export async function loadAppModules(relativePaths) {
  const directory = await mkdtemp(join(tmpdir(), 'sort-tester-modules-'));
  const cleanup = () => rm(directory, { recursive: true, force: true });
  try {
    await cp(new URL('../../src/', import.meta.url), join(directory, 'src'), { recursive: true });
    await writeFile(join(directory, 'package.json'), '{"type":"module"}\n');
    const modules = await Promise.all(relativePaths.map(path => import(pathToFileURL(join(directory, path)).href)));
    return { modules, cleanup };
  } catch (error) {
    await cleanup();
    throw error;
  }
}
