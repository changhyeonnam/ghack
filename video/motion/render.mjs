#!/usr/bin/env node
// Deterministic frame-by-frame renderer for the LedgerLens motion scenes.
//
//   node video/motion/render.mjs                 # render every scene at its default duration
//   node video/motion/render.mjs benchmark       # render one scene
//   node video/motion/render.mjs benchmark --d 12.4   # match a 12.4 s narration clip
//   node video/motion/render.mjs intro --out /tmp/intro_test.mp4
//
// Each scene page exposes window.renderAt(t) and window.SCENE.duration. We step
// t = i / FPS for i = 0..N-1, screenshot each frame and pipe PNGs into ffmpeg.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { readdirSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, join, resolve, basename } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const SCENES_DIR = join(HERE, 'scenes');
const OUT_DIR = join(HERE, 'out');
const FPS = 30;
const WIDTH = 1920;
const HEIGHT = 1080;
const FFMPEG = process.env.FFMPEG || (existsSync('/opt/homebrew/bin/ffmpeg') ? '/opt/homebrew/bin/ffmpeg' : 'ffmpeg');

function parseArgs(argv) {
  const opts = { scenes: [], d: null, out: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--d' || a === '-d') opts.d = parseFloat(argv[++i]);
    else if (a.startsWith('--d=')) opts.d = parseFloat(a.slice(4));
    else if (a === '--out') opts.out = argv[++i];
    else if (a === '-h' || a === '--help') {
      console.log('usage: node render.mjs [scene ...] [--d seconds] [--out file.mp4]');
      process.exit(0);
    } else opts.scenes.push(a.replace(/\.html$/, ''));
  }
  if (opts.d !== null && !(opts.d > 0)) throw new Error('--d must be a positive number of seconds');
  return opts;
}

function encoder(outFile) {
  const args = [
    '-hide_banner', '-loglevel', 'error', '-y',
    '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-tune', 'animation',
    '-pix_fmt', 'yuv420p', '-r', String(FPS), '-an', '-movflags', '+faststart',
    outFile,
  ];
  const ff = spawn(FFMPEG, args, { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((res, rej) => {
    ff.on('error', rej);
    ff.on('close', (code) => (code === 0 ? res() : rej(new Error(`ffmpeg exited with ${code}`))));
  });
  return { ff, done };
}

function write(stream, buf) {
  if (stream.write(buf)) return Promise.resolve();
  return new Promise((res, rej) => {
    const onErr = (e) => { stream.off('drain', onDrain); rej(e); };
    const onDrain = () => { stream.off('error', onErr); res(); };
    stream.once('drain', onDrain);
    stream.once('error', onErr);
  });
}

async function renderScene(browser, name, opts) {
  const file = join(SCENES_DIR, `${name}.html`);
  if (!existsSync(file)) throw new Error(`no such scene: ${file}`);
  const url = new URL(pathToFileURL(file));
  url.searchParams.set('capture', '1');
  if (opts.d) url.searchParams.set('d', String(opts.d));

  const page = await browser.newPage({ viewport: { width: WIDTH, height: HEIGHT }, deviceScaleFactor: 1 });
  await page.goto(url.href);
  await page.evaluate(() => document.fonts.ready);
  const duration = await page.evaluate(() => window.SCENE.duration);
  const frames = Math.round(duration * FPS);
  const outFile = resolve(opts.out || join(OUT_DIR, `${name}.mp4`));
  mkdirSync(dirname(outFile), { recursive: true });

  const { ff, done } = encoder(outFile);
  const t0 = Date.now();
  for (let i = 0; i < frames; i++) {
    await page.evaluate((t) => window.renderAt(t), i / FPS);
    const png = await page.screenshot({ type: 'png', animations: 'disabled', caret: 'hide' });
    await write(ff.stdin, png);
    if (i % 60 === 0) process.stdout.write(`\r${name}: frame ${i}/${frames}`);
  }
  ff.stdin.end();
  await done;
  await page.close();
  const secs = ((Date.now() - t0) / 1000).toFixed(1);
  console.log(`\r${name}: ${frames} frames (${duration.toFixed(2)} s) -> ${outFile}  [${secs} s]`);
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const all = readdirSync(SCENES_DIR).filter((f) => f.endsWith('.html')).map((f) => basename(f, '.html'));
  const scenes = opts.scenes.length ? opts.scenes : all;
  if (opts.out && scenes.length !== 1) throw new Error('--out needs exactly one scene');
  const browser = await chromium.launch({ channel: process.env.PW_CHANNEL || 'chrome' });
  try {
    for (const s of scenes) await renderScene(browser, s, opts);
  } finally {
    await browser.close();
  }
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
