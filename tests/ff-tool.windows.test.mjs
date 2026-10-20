// Executed on the Windows CI runner; explicitly skipped on other platforms.
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { quotePS, renderScript, scriptFile } from '../tools/ffmpeg-compressor/core.mjs';
const onWindows=process.platform==='win32';
const template=await readFile(new URL('../tools/ffmpeg-compressor/templates/powershell.txt',import.meta.url),'utf8');
const run=(program,args)=>spawnSync(program,args,{encoding:'utf8',timeout:120000});
async function workspace(t){const dir=await mkdtemp(path.join(tmpdir(),'ff-tool-win-'));t.after(()=>rm(dir,{recursive:true,force:true}));return dir;}
async function ps(dir,content){const file=path.join(dir,'run.ps1');await writeFile(file,scriptFile(content,'windows').text,'utf8');return run('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',file]);}
test('Windows PowerShell 5.1 literal quoting roundtrip and parser', {skip:!onWindows},async t=>{
 const dir=await workspace(t);
 const text='中文 space \'apostrophe\' "double" (p) [b] $dollar `tick` & smart‘’';
 const result=await ps(dir,`[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding\n[Console]::Write(${quotePS(text)})`);
 assert.equal(result.status,0,result.stderr);assert.equal(result.stdout,text);
 const generated=renderScript(template,[{path:'C:\\Videos\\中文 [b] \'apostrophe\' $d `t` &.mp4',duration:'20'}],{platform:'windows'});
 const parseFile=path.join(dir,'generated.ps1');await writeFile(parseFile,scriptFile(generated,'windows').text,'utf8');
 const parsed=await ps(dir,`$tokens=$null; $errors=$null\n$null=[System.Management.Automation.Language.Parser]::ParseFile(${quotePS(parseFile)},[ref]$tokens,[ref]$errors)\nif($errors.Count -gt 0){throw ($errors | Out-String)}`);
 assert.equal(parsed.status,0,parsed.stdout+parsed.stderr);
});
test('Windows real two-pass batch: audio/no-audio, portrait scaling, decode, preserved originals and collisions', {skip:!onWindows},async t=>{
 const dir=await workspace(t);
 const rows=[];const originals=[];
 for(const audio of [false,true]){
  const source=path.join(dir,`中文 '單' (1) [A] $dollar \`tick\` & ${audio}.mp4`);
  const args=['-hide_banner','-loglevel','error','-f','lavfi','-i',`testsrc2=size=${audio?'720x1280':'1280x720'}:rate=15`];
  if(audio)args.push('-f','lavfi','-i','sine=frequency=440');
  args.push('-t','2','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p');if(audio)args.push('-c:a','aac');args.push(source);
  const created=run('ffmpeg',args);assert.equal(created.status,0,created.stderr);
  originals.push(await readFile(source));rows.push({path:source,output:path.join(dir,`out-${audio}.mp4`),duration:'4',audioState:audio?'yes':'no'});
 }
 const script=renderScript(template,rows,{platform:'windows',target:.2,resolution:'360',preset:'veryfast',fps:'30'});
 const result=await ps(dir,script);assert.equal(result.status,0,result.stdout+result.stderr);
 for(const [index,row] of rows.entries()){
  const decoded=run('ffmpeg',['-v','error','-i',row.output,'-f','null','NUL']);assert.equal(decoded.status,0,decoded.stderr);
  const probe=run('ffprobe',['-v','error','-show_entries','format=duration,size:stream=codec_type,width,height','-of','json',row.output]);
  const info=JSON.parse(probe.stdout);const video=info.streams.find(s=>s.codec_type==='video');
  assert.equal(video.width,index?360:640);assert.equal(video.height,index?640:360);
  assert.equal(info.streams.some(s=>s.codec_type==='audio'),Boolean(index));
  assert.ok(+info.format.size<200000);assert.ok(Math.abs(+info.format.duration-2)<.15);
  assert.deepEqual(await readFile(row.path),originals[index]);
 }
 assert.equal((await readdir(dir)).some(name=>name.startsWith('.ff-tool-')),false);
 const outputBefore=await readFile(rows[0].output);
 const rerun=await ps(dir,script);assert.notEqual(rerun.status,0);
 assert.deepEqual(await readFile(rows[0].output),outputBefore);
});
