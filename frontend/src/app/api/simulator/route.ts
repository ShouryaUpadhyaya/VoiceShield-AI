import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import path from 'path';

export async function POST(req: Request) {
  return new Promise(async (resolve) => {
    let body = {};
    try {
      body = await req.json();
    } catch (e) {}

    const targetPath = (body as any).path || '';
    const concurrency = (body as any).concurrency || 1;
    const speed = (body as any).speed || 2.0;

    // Navigate to the root of the project to run the simulator
    const rootDir = path.resolve(process.cwd(), '..');
    
    // Check if virtual environment exists and use its python, otherwise system python
    const venvPython = path.join(rootDir, 'venv', 'bin', 'python');
    
    let args = [];
    if (targetPath) args.push(`"${targetPath}"`);
    args.push(`-c ${concurrency}`);
    args.push(`-s ${speed}`);

    const argsString = args.join(' ');
    
    const cmd = `if [ -f "${venvPython}" ]; then ${venvPython} tests/integration/test_android_simulator.py ${argsString}; else python tests/integration/test_android_simulator.py ${argsString}; fi`;
    
    exec(cmd, { cwd: rootDir }, (error, stdout, stderr) => {
      if (error) {
        resolve(NextResponse.json({ success: false, output: stdout, error: stderr || error.message }, { status: 500 }));
        return;
      }
      resolve(NextResponse.json({ success: true, output: stdout }));
    });
  });
}
