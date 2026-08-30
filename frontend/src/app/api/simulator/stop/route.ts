import { NextResponse } from 'next/server';
import { exec } from 'child_process';

export async function POST() {
  return new Promise((resolve) => {
    // pkill -f matches against the full command line
    exec('pkill -f "test_android_simulator.py"', (error, stdout, stderr) => {
      // pkill returns exit code 1 if no processes were matched, which is fine
      resolve(NextResponse.json({ success: true, message: "Simulator processes stopped." }));
    });
  });
}
