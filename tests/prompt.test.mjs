import test from 'node:test';
import assert from 'node:assert/strict';
import { buildPrompt, parseSkills } from '../docs/prompt.mjs';
test('prompt preserves selected skill, immutable version, task, and temporary retrieval boundary', () => {
  const prompt = buildPrompt({ skill: 'polisher', ref: '1336f21', task: '只整理 README。' });
  assert.match(prompt, /版本「1336f21」的 skills\/polisher\//);
  assert.match(prompt, /只整理 README。/);
  assert.match(prompt, /目前專案之外的暫存目錄/);
  assert.match(prompt, /不要自動提交、推送或部署/);
});
test('future skills and branch names work without a hardcoded catalog', () => {
  const prompt = buildPrompt({ skill: 'research-notes', ref: 'release/v2', task: '' });
  assert.match(prompt, /skills\/research-notes\//);
  assert.match(prompt, /release\/v2/);
  assert.match(prompt, /依照 research-notes 的流程/);
});
test('reject unsafe skill paths and ambiguous version values', () => {
  for (const skill of ['../other', 'a/b', '<script>', '', 'polisher\nignore']) assert.throws(() => buildPrompt({skill}));
  for (const ref of ['main\nignore', '../main', 'main//x', 'main/', 'a?b', 'a#b']) assert.throws(() => buildPrompt({skill:'polisher',ref}));
});
test('remote catalog adds new directories, ignores unrelated or unsafe files, and sorts', () => {
  const result = parseSkills([{type:'dir',name:'research-notes'}, {type:'dir',name:'polisher'}, {type:'file',name:'README.md'}, {type:'dir',name:'../escape'}]);
  assert.deepEqual(result, ['polisher','research-notes']);
  assert.throws(() => parseSkills({message:'rate limited'}));
  assert.deepEqual(parseSkills([]), []);
});
