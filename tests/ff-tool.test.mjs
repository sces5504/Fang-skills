import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, mkdtemp, writeFile, rm, readdir, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync, spawn } from 'node:child_process';
import { DEFAULTS, parseDuration, normalizeSettings, estimate, scaleDimensions, scaleFilter, quoteSh, quotePS, validateJobs, outputPath, renderScript, scriptFile, probeCommand } from '../tools/ffmpeg-compressor/core.mjs';
const bash = await readFile(new URL('../tools/ffmpeg-compressor/templates/bash.txt',import.meta.url),'utf8');
const powershell = await readFile(new URL('../tools/ffmpeg-compressor/templates/powershell.txt',import.meta.url),'utf8');
const special = `中文 空白 '單引號' "雙引號" (括號) [方括號] $money \`tick\` & end`;
test('seconds, decimal seconds and strict HH:MM:SS parsing', () => {
  assert.equal(parseDuration('00:16:14'),974);
  assert.equal(parseDuration('01:02:03.125'),3723.125);
  assert.equal(parseDuration('532.25'),532.25);
  for (const value of ['', '  ', '0', '-1', 'NaN','Infinity','1:60:00','1:00:60','1:2:3','2:30','1e3']) assert.throws(()=>parseDuration(value));
});
test('reference videos are calculated, not hardcoded', () => {
  assert.deepEqual([974,532,652].map(seconds=>estimate({...DEFAULTS,audio:'remove'},seconds).videoKbps),[238,436,356]);
});
test('MB/MiB, audio budget, floor and one safety deduction', () => {
  const settings=normalizeSettings({target:30,unit:'MiB',margin:10,audio:'keep',audioKbps:96});
  assert.equal(settings.targetBytes,31457280);
  const withAudio=estimate(settings,600,'yes');
  const silent=estimate(settings,600,'no');
  assert.equal(silent.videoKbps-withAudio.videoKbps,96);
  assert.equal(withAudio.videoKbps,Math.floor((31457280*.9*8/600-96000)/1000));
  assert.ok(withAudio.payloadBytes<=31457280*.9);
  assert.equal(estimate(settings,600,'unknown').uncertainAudio,true);
});
test('invalid target/settings and exhausted audio budget are rejected', () => {
  for (const target of ['',0,-1,NaN,Infinity,1e30]) assert.throws(()=>normalizeSettings({target}));
  for (const margin of ['','NaN',-1,51]) assert.throws(()=>normalizeSettings({margin}));
  for (const seconds of [0,-2,'',NaN,Infinity]) assert.throws(()=>estimate(DEFAULTS,seconds));
  assert.throws(()=>estimate({target:.01,audio:'keep',audioKbps:192},600,'yes'),/不足 16/);
  assert.throws(()=>estimate({target:.001,audio:'remove'},600,'no'),/不足 16/);
  assert.throws(()=>normalizeSettings({preset:'medium; echo unsafe'}));
});
test('landscape/portrait bounds, even sizes and no upscaling', () => {
  assert.deepEqual(scaleDimensions(1280,720,'360'),{width:640,height:360});
  assert.deepEqual(scaleDimensions(720,1280,'360'),{width:360,height:640});
  assert.deepEqual(scaleDimensions(321,181,'720'),{width:320,height:180});
  assert.deepEqual(scaleDimensions(321,181,'source'),{width:320,height:180});
  assert.deepEqual(scaleDimensions(3840,2160,'1080'),{width:1920,height:1080});
  assert.throws(()=>scaleDimensions(0,720));
  assert.match(scaleFilter('720'),/1280\/max\(iw,ih\)/);
});
test('output names, original preservation, duplicates and empty input', () => {
  assert.equal(outputPath('/Users/a/影片.mov',DEFAULTS),'/Users/a/影片_30MB.mp4');
  assert.equal(outputPath('C:\\影片\\a.mp4',{platform:'windows'}),'C:\\影片\\a_30MB.mp4');
  assert.throws(()=>validateJobs([],DEFAULTS));
  assert.throws(()=>validateJobs([{path:'',duration:'3'}],DEFAULTS));
  assert.throws(()=>validateJobs([{path:'x.mp4',output:'x.mp4'}],DEFAULTS),/來源/);
  assert.throws(()=>validateJobs([{path:'x.mp4',output:'new.mp4'},{path:'y.mp4',output:'new.mp4'}],DEFAULTS),/重複/);
  assert.throws(()=>validateJobs([{path:'x.mp4',output:'y.mp4'},{path:'y.mp4'}],DEFAULTS),/來源/);
  assert.throws(()=>validateJobs([{path:'x.mp4',duration:'invalid'}],DEFAULTS));
  assert.throws(()=>validateJobs([{path:'bad"name.mp4'}],{platform:'windows'}),/Windows 檔名/);
  assert.equal(validateJobs([{path:'./video.mp4',duration:''}],DEFAULTS)[0].budget,null);
});
test('shell literals roundtrip all required POSIX special characters without execution', () => {
  for (const shell of ['/bin/bash','/bin/zsh']) {
    if(spawnSync(shell,['--version']).error)continue;
    const result=spawnSync(shell,['-c',`printf '%s' ${quoteSh(special)}`],{encoding:'utf8'});
    assert.equal(result.status,0,result.stderr);
    assert.equal(result.stdout,special);
  }
  assert.throws(()=>quoteSh('bad\nname'));
  assert.throws(()=>quotePS('bad\u0000name'));
});
test('PowerShell literal encoding, arrays, null target and Windows BOM download', () => {
  const literal=quotePS(special);
  assert.equal(literal.slice(1,-1).replaceAll("''","'"),special);
  const script=renderScript(powershell,[{path:"C:\\Videos\\中文 ' [x] $ & ` (1).mp4",duration:'974',audioState:'no'}],{...DEFAULTS,audio:'remove',platform:'windows'});
  assert.match(script,/& ffmpeg @firstArgs/);
  assert.match(script,/'null','NUL'/);
  assert.match(script,/finally/);
  assert.match(script,/\[IO.File\]::Move/);
  assert.match(script,/\[guid\]::NewGuid/);
  assert.doesNotMatch(script,/Invoke-Expression|@@[A-Z_]+@@/);
  const file=scriptFile(script,'windows');
  assert.equal(file.name,'ff-tool.ps1');
  assert.equal(file.text.charCodeAt(0),0xfeff);
  assert.match(file.text,/\r\n/);
});
test('template insertion is a single pass, and ffprobe quotes the input', () => {
  const script=renderScript(bash,[{path:'./@@JOBS@@.mp4',duration:'2'}],DEFAULTS);
  assert.match(script,/'\.\/@@JOBS@@\.mp4'/);
  assert.match(probeCommand(special),new RegExp('ffprobe'));
  assert.ok(probeCommand(special).endsWith(quoteSh(special)));
});
const hasFFmpeg = !spawnSync('ffmpeg',['-version']).error && !spawnSync('ffprobe',['-version']).error;
const run=(program,args,options={})=>spawnSync(program,args,{encoding:'utf8',timeout:120000,...options});
const ff=(args)=> {const result=run('ffmpeg',['-hide_banner','-loglevel','error',...args]);assert.equal(result.status,0,result.stderr);};
const probe=filename=>JSON.parse(run('ffprobe',['-v','error','-show_entries','format=duration,size:stream=codec_type,width,height,pix_fmt','-of','json',filename]).stdout);
function execute(template,rows,settings,options={}) { return run('/bin/bash',['-s'],{input:renderScript(template,rows,settings),...options}); }
async function fixture(t) {const dir=await mkdtemp(path.join(tmpdir(),'ff-tool-test-'));t.after(()=>rm(dir,{recursive:true,force:true}));return dir;}
test('real two-pass: special names, audio/no-audio, scaled portrait and landscape, decode and sizes', {skip:!hasFFmpeg}, async t=> {
  const dir=await fixture(t);
  for(const [portrait,audio] of [[false,false],[true,true]]) {
    const source=path.join(dir,`${special}-${portrait}.mp4`);
    const output=path.join(dir,`output-${portrait}.mp4`);
    const dimensions=portrait?'720x1280':'1280x720';
    const args=['-f','lavfi','-i',`testsrc2=size=${dimensions}:rate=15`];
    if(audio)args.push('-f','lavfi','-i','sine=frequency=440:sample_rate=44100');
    args.push('-t','2','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p');
    if(audio)args.push('-c:a','aac');
    ff([...args,source]);
    const before=await readFile(source);
    const result=execute(bash,[{path:source,output,duration:'4',audioState:audio?'yes':'no'}],{...DEFAULTS,target:.2,resolution:'360',preset:'veryfast',fps:'30'});
    assert.equal(result.status,0,result.stdout+result.stderr);
    assert.match(result.stdout,audio?/audio 96 kbps/:/audio 0 kbps/);
    assert.match(result.stdout,/Duration 2\.000000 s/);
    const details=probe(output);const video=details.streams.find(stream=>stream.codec_type==='video');
    assert.equal(video.width,portrait?360:640);assert.equal(video.height,portrait?640:360);
    assert.equal(video.pix_fmt,'yuv420p');assert.equal(details.streams.some(s=>s.codec_type==='audio'),audio);
    assert.ok(Math.abs(+details.format.duration-2)<.15);
    assert.ok(+details.format.size<200000);
    ff(['-i',output,'-f','null','-']);
    assert.deepEqual(await readFile(source),before);
    const rerun=execute(bash,[{path:source,output,duration:'4'}],{...DEFAULTS,target:.2});
    assert.notEqual(rerun.status,0);assert.match(rerun.stderr,/Output exists/);
  }
  assert.equal((await readdir(dir)).some(name=>name.startsWith('.ff-tool.')),false);
});
test('real batch continues after a failed source; zsh can run the full generated script', {skip:!hasFFmpeg},async t=> {
  const dir=await fixture(t);const source=path.join(dir,'small.mp4');
  ff(['-f','lavfi','-i','testsrc2=size=160x90:rate=10','-t','2','-c:v','libx264','-preset','ultrafast',source]);
  const settings={...DEFAULTS,target:.1,audio:'remove',preset:'veryfast'};
  const result=execute(bash,[{path:path.join(dir,'missing.mp4'),duration:'2'},{path:source,duration:'2'}],settings);
  assert.notEqual(result.status,0);assert.match(result.stdout,/1 succeeded \/ 1 failed/);
  const out=path.join(dir,'zsh.mp4');
  if(!spawnSync('/bin/zsh',['--version']).error) {
    const zsh=run('/bin/zsh',['-s'],{input:renderScript(bash,[{path:source,output:out,duration:'2'}],settings)});
    assert.equal(zsh.status,0,zsh.stdout+zsh.stderr);
    const video=probe(out).streams[0];assert.equal(video.width,160);assert.equal(video.height,90);
  }
});
test('pass-one failure stops pass two, cleans only its own temp, and preserves existing files', {skip:!hasFFmpeg},async t=> {
  const dir=await fixture(t);const source=path.join(dir,'source.mp4');
  ff(['-f','lavfi','-i','color=size=160x90:rate=10','-t','1','-c:v','libx264',source]);
  const fakeBin=path.join(dir,'bin');await mkdir(fakeBin);
  await writeFile(path.join(fakeBin,'ffmpeg'),'#!/bin/bash\nprintf "%s\\n" "$*" >> "$FF_TOOL_TRACE"\nexit 7\n',{mode:0o755});
  await mkdir(path.join(dir,'.ff-tool.keep'));
  const trace=path.join(dir,'calls.txt');
  const result=execute(bash,[{path:source,duration:'1'}],{...DEFAULTS,target:1,audio:'remove'},{env:{...process.env,PATH:fakeBin+path.delimiter+process.env.PATH,FF_TOOL_TRACE:trace}});
  assert.notEqual(result.status,0);assert.match(result.stderr,/Pass 1 failed/);
  const calls=await readFile(trace,'utf8');assert.match(calls,/-pass 1/);assert.doesNotMatch(calls,/-pass 2/);
  assert.deepEqual((await readdir(dir)).filter(name=>name.startsWith('.ff-tool.')),['.ff-tool.keep']);
});
test('independent concurrent jobs do not share pass logs', {skip:!hasFFmpeg},async t=> {
  const dir=await fixture(t);const source=path.join(dir,'source.mp4');
  ff(['-f','lavfi','-i','color=size=160x90:rate=10','-t','2','-c:v','libx264',source]);
  const settings={...DEFAULTS,target:.1,audio:'remove',preset:'veryfast'};
  const launch=output=>new Promise((resolve,reject)=>{
    const child=spawn('/bin/bash',['-s']);let logs='';
    child.stdout.on('data',chunk=>logs+=chunk);child.stderr.on('data',chunk=>logs+=chunk);
    child.on('error',reject);child.on('close',code=>code===0?resolve():reject(new Error(logs)));
    child.stdin.end(renderScript(bash,[{path:source,output,duration:'2'}],settings));
  });
  await Promise.all([launch(path.join(dir,'a.mp4')),launch(path.join(dir,'b.mp4'))]);
  assert.equal((await readdir(dir)).some(name=>name.startsWith('.ff-tool.')),false);
});
test('PowerShell typographic single quotes are escaped as delimiters too',()=> {
  const input='C:\\Videos\\it’s ‘a’ ; $x &.mp4';
  const quoted=quotePS(input);
  assert.equal(quoted.slice(1,-1).replace(/(['\u2018\u2019\u201a\u201b])\1/g,'$1'),input);
  assert.ok(quoted.includes('’’'));
});
test('real odd source is rounded down, audio can be removed, oversize is reported and kept', {skip:!hasFFmpeg},async t=> {
  const dir=await fixture(t);
  const source=path.join(dir,'odd.mkv');
  ff(['-f','lavfi','-i','testsrc=size=321x181:rate=10,format=yuv444p','-f','lavfi','-i','sine=frequency=220','-t','2','-c:v','ffv1','-c:a','pcm_s16le',source]);
  const output=path.join(dir,'odd.mp4');
  const encoded=execute(bash,[{path:source,output,duration:'2'}],{...DEFAULTS,target:.1,resolution:'source',audio:'remove'});
  assert.equal(encoded.status,0,encoded.stdout+encoded.stderr);
  const info=probe(output);assert.equal(info.streams[0].width,320);assert.equal(info.streams[0].height,180);
  assert.equal(info.streams.some(stream=>stream.codec_type==='audio'),false);
  const short=path.join(dir,'short.mp4');
  ff(['-f','lavfi','-i','color=size=160x90:rate=10','-t','0.2','-c:v','libx264',short]);
  const oversized=path.join(dir,'oversized.mp4');
  const result=execute(bash,[{path:short,output:oversized,duration:'.2'}],{...DEFAULTS,target:.001,audio:'remove'});
  assert.notEqual(result.status,0);assert.match(result.stderr,/OVERSIZE/);
  assert.ok((await readFile(oversized)).length>1000);
  assert.equal((await readdir(dir)).some(name=>name.startsWith('.ff-tool.')),false);
});
