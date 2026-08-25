"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Activity, History, List, Server } from 'lucide-react';
import { useGatewayStore } from '@/stores/gateway-store';
import { useEffect } from 'react';
import { getWebsocketUrl } from '@/lib/api';

export function Layout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const connect = useGatewayStore((s) => s.connectWebsocket);
  const disconnect = useGatewayStore((s) => s.disconnectWebsocket);

  useEffect(() => {
    connect(getWebsocketUrl());
    return () => disconnect();
  }, [connect, disconnect]);

  const nav = [
    { name: 'Overview', href: '/', icon: Activity },
    { name: 'Call History', href: '/calls', icon: History },
    { name: 'Events', href: '/events', icon: List },
    { name: 'System', href: '/system', icon: Server },
  ];

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-50">
      {/* Sidebar */}
      <div className="w-64 border-r border-slate-800 bg-slate-900/50 flex flex-col">
        <div className="h-16 flex items-center px-6 border-b border-slate-800 font-bold text-lg text-emerald-400 tracking-wide">
          VoiceShield-AI
        </div>
        <nav className="flex-1 px-4 py-6 space-y-2">
          {nav.map((item) => {
            const active = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
            return (
              <Link 
                key={item.name} 
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${active ? 'bg-emerald-500/10 text-emerald-400' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}`}
              >
                <item.icon className="w-4 h-4" />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>
      {/* Main content */}
      <main className="flex-1 flex flex-col min-h-screen overflow-x-hidden">
        {children}
      </main>
    </div>
  );
}
