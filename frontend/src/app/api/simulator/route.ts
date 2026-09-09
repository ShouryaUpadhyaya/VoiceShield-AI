import { NextResponse } from 'next/server';
import { execFile } from 'child_process';
import path from 'path';
import fs from 'fs';

export async function POST(req: Request) {
  return new Promise<NextResponse>(async (resolve) => {
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
    // The repo's own setup instructions create `.venv`, but this looked only for
    // `venv` and silently fell through to a bare `python` with no numpy. Check both.
    const venvCandidates = [
      path.join(rootDir, '.venv', 'bin', 'python'),
      path.join(rootDir, 'venv', 'bin', 'python'),
    ];
    const venvPython = venvCandidates.find((p) => fs.existsSync(p)) ?? venvCandidates[0];
    
    if (typeof targetPath !== 'string' || !Number.isInteger(concurrency) || concurrency < 1 || concurrency > 4 || typeof speed !== 'number' || !Number.isFinite(speed) || speed <= 0 || speed > 10) {
      resolve(NextResponse.json({ success: false, error: 'Invalid simulator arguments' }, { status: 400 }));
      return;
    }
    const args = ['tests/integration/test_android_simulator.py'];
    if (targetPath) args.push(path.resolve(rootDir, targetPath));
    args.push('-c', String(concurrency), '-s', String(speed));
    const executable = fs.existsSync(venvPython) ? venvPython : 'python';
    execFile(executable, args, { cwd: rootDir }, (error, stdout, stderr) => {
      if (error) {
        resolve(NextResponse.json({ success: false, output: stdout, error: stderr || error.message }, { status: 500 }));
        return;
      }
      resolve(NextResponse.json({ success: true, output: stdout }));
    });
  });
}
