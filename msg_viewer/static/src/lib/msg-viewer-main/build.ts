import html from 'bun-plugin-html';
import * as fs from 'fs/promises';
import * as path from 'path';

const SOURCE_DIR = "./lib";
const DEST_DIR = "./build";

try {
  await clearDestDir();
  await createDestDir();
  await copyResourceFiles();
  await build();
} catch(err) {
  console.error("Failed to build. Error: ", err);
}

async function copyResourceFiles() {
  const resourceDir = path.join(SOURCE_DIR, "resources");
  console.log(`Copying resources from "${resourceDir}" to "${DEST_DIR}".`);
  
  try {
    const files = await fs.readdir(resourceDir);
    for (const file of files) {
      try {
        await fs.copyFile(path.join(resourceDir, file), path.join(DEST_DIR, file));
        console.log(`File "${file}" copied successfully!`);
      } catch(err) {
        console.error(`Failed to copy file "${file}".`);
        throw err;
      }
    }
    
    console.log("Resource files copied successfully!\n");
  } catch (err) {
    console.error(`Failed to read resource directory "${resourceDir}".`);
    throw err;
  }
}

async function build() {
  console.log("Building...");

  try {
    await Bun.build({
      entrypoints: ["./lib/index.html"],
      outdir: DEST_DIR,
      minify: true,
      plugins: [
        html({ inline: true }),
      ],
    });
    console.log("Build succeeded!\n");
  } catch(err) {
    console.error("Failed to build.");
    throw err;
  }
}

async function clearDestDir() {
  console.log(`Clearing destination folder "${DEST_DIR}".`);
  try {
    await fs.rm(DEST_DIR, { recursive: true, force: true });
    console.log(`Destination folder "${DEST_DIR}" cleared successfully!\n`);
  } catch(err) {
    console.error(`Failed to clear destination folder "${DEST_DIR}". Error: `, err);
    throw err;
  }
}

async function createDestDir(){
  console.log(`Creating destination folder "${DEST_DIR}".`);
  try {
    await fs.mkdir(DEST_DIR, { recursive: true });
    console.log(`Successfully created destination folder "${DEST_DIR}".\n`);
  } catch(err) {
    console.error(`Failed to create destination folder "${DEST_DIR}".`);
  }
}