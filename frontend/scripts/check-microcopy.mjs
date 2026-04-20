#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

const ROOT = process.cwd();
const TARGETS = [
  path.join(ROOT, 'projects', 'parkpe', 'src'),
  path.join(ROOT, '..', 'backend', 'portal', 'templates'),
];
const EXTENSIONS = new Set(['.html', '.ts']);
const MAX_INLINE_TEXT_LENGTH = 110;

const FORBIDDEN_WORDS = [
  'yahan',
  'samjho',
  'niche',
  'taaki',
  'karo',
  'kar sakte',
  'aayega',
  'hoga',
  'dikhegi',
  'milengi',
  'ke liye',
  'mein brand identify',
];

function walk(dir, files = []) {
  if (!fs.existsSync(dir)) return files;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name.startsWith('.')) continue;
      walk(fullPath, files);
    } else if (entry.isFile() && EXTENSIONS.has(path.extname(entry.name))) {
      files.push(fullPath);
    }
  }
  return files;
}

function validateFile(filePath) {
  const rel = path.relative(path.join(ROOT, '..'), filePath);
  const text = fs.readFileSync(filePath, 'utf8');
  const lines = text.split(/\r?\n/);
  const issues = [];

  lines.forEach((line, idx) => {
    const lineNo = idx + 1;
    const lower = line.toLowerCase();

    for (const token of FORBIDDEN_WORDS) {
      if (lower.includes(token)) {
        issues.push(`${rel}:${lineNo} forbidden phrase "${token}"`);
      }
    }

    const inlineMatch = line.match(/>([^<]+)</g);
    if (!inlineMatch) return;
    for (const part of inlineMatch) {
      const inner = part.slice(1, -1).replace(/\s+/g, ' ').trim();
      if (!inner) continue;
      // Skip template-heavy lines (Django/Angular bindings) to avoid false positives.
      if (inner.includes('{{') || inner.includes('}}') || inner.includes('@if')) continue;
      if (inner.length > MAX_INLINE_TEXT_LENGTH) {
        issues.push(
          `${rel}:${lineNo} inline text too long (${inner.length} > ${MAX_INLINE_TEXT_LENGTH})`
        );
      }
    }
  });

  return issues;
}

const files = TARGETS.flatMap((dir) => walk(dir));
const allIssues = files.flatMap((file) => validateFile(file));

if (allIssues.length > 0) {
  console.error('Microcopy check failed:\n');
  for (const issue of allIssues) console.error(`- ${issue}`);
  process.exit(1);
}

console.log(`Microcopy check passed (${files.length} files scanned).`);
