"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Activity, History, List, Server } from 'lucide-react';
import { useGatewayStore } from '@/stores/gateway-store';
import { useEffect } from 'react';
import { getWebsocketUrl } from '@/lib/api';

function NavLink({ href, icon: Icon, children }: { href: string; icon: React.ElementType; children: React.ReactNode }) {
  const pathname = usePathname();
  const active = pathname === href || (href !== '/' && pathname.startsWith(href));
  
  return (
    <Link
      href={href}
      className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
        active
          ? 'bg-emerald-500/10 text-emerald-400'
          : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
      }`}
    >
      <Icon className="w-4 h-4" />
      {children}
    </Link>
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  const connect = useGatewayStore((s) => s.connectWebsocket);
  const disconnect = useGatewayStore((s) => s.disconnectWebsocket);

  useEffect(() => {
    connect(getWebsocketUrl());
    return () => disconnect();
  }, [connect, disconnect]);

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-50">
      {/* Sidebar */}
      <div className="w-64 border-r border-slate-800 bg-slate-900/50 flex flex-col overflow-y-auto">
        <div className="h-16 shrink-0 flex items-center px-6 border-b border-slate-800 font-bold text-lg text-emerald-400 tracking-wide">
          VoiceShield-AI
        </div>
        
        <nav className="flex-1 px-4 py-6 space-y-6">
          
          <div>
            <h3 className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Overview</h3>
            <div className="space-y-1">
              <NavLink href="/" icon={Activity}>Overview</NavLink>
            </div>
          </div>

          <div>
            <h3 className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Calls</h3>
            <div className="space-y-1">
              <NavLink href="/calls" icon={History}>Call History</NavLink>
            </div>
          </div>

          <div>
            <h3 className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">ML Model Lab</h3>
            <div className="space-y-1">
              <NavLink href="/models" icon={Activity}>All Models</NavLink>
              <NavLink href="/models/indic" icon={Activity}>Indic Detector</NavLink>
              <NavLink href="/models/dhwani" icon={Activity}>Dhwani</NavLink>
              <NavLink href="/models/custom-deepfake" icon={Activity}>Custom Deepfake</NavLink>
              <NavLink href="/models/prosody" icon={Activity}>Prosody</NavLink>
              <NavLink href="/models/speaker" icon={Activity}>Speaker Verification</NavLink>
              <NavLink href="/models/history" icon={History}>Model Test History</NavLink>
            </div>
          </div>

          <div>
            <h3 className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">System</h3>
            <div className="space-y-1">
              <NavLink href="/events" icon={List}>Events</NavLink>
              <NavLink href="/system" icon={Server}>System</NavLink>
            </div>
          </div>

        </nav>
      </div>
      {/* Main content */}
      <main className="flex-1 flex flex-col min-h-screen overflow-x-hidden">
        {children}
      </main>
    </div>
  );
}
