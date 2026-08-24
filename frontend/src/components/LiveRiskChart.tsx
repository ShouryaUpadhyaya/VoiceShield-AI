import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';

interface DataPoint {
  time: string;
  risk: number;
}

interface LiveRiskChartProps {
  data: DataPoint[];
}

export function LiveRiskChart({ data }: LiveRiskChartProps) {
  return (
    <div className="w-full h-64 bg-slate-900 rounded-xl p-4 border border-slate-800 shadow-inner">
      <h3 className="text-sm font-semibold text-slate-400 mb-4 tracking-wider uppercase">Live Risk Assessment</h3>
      <ResponsiveContainer width="100%" height="80%">
        <LineChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
          <XAxis 
            dataKey="time" 
            stroke="#64748b" 
            fontSize={12} 
            tickMargin={10}
            minTickGap={30}
          />
          <YAxis 
            domain={[0, 100]} 
            stroke="#64748b" 
            fontSize={12} 
            tickFormatter={(val) => `${val}%`}
          />
          <Tooltip 
            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f8fafc', borderRadius: '0.5rem' }}
            itemStyle={{ color: '#818cf8', fontWeight: 'bold' }}
            labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
          />
          <ReferenceLine y={80} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'insideTopLeft', value: 'Critical Threshold', fill: '#ef4444', fontSize: 10 }} />
          <ReferenceLine y={40} stroke="#eab308" strokeDasharray="3 3" />
          <Line 
            type="monotone" 
            dataKey="risk" 
            stroke="#818cf8" 
            strokeWidth={3}
            dot={false}
            activeDot={{ r: 6, fill: '#6366f1', stroke: '#1e1b4b', strokeWidth: 2 }}
            animationDuration={300}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
