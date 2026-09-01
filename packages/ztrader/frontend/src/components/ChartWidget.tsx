"use client";
import React, { useEffect, useRef, memo } from 'react';
import {
  createChart,
  ColorType,
  IChartApi,
  ISeriesApi,
  Time,
  CandlestickData,
} from 'lightweight-charts';

interface CandleData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

interface ChartWidgetProps {
  data: CandleData[];
  colors?: {
    backgroundColor?: string;
    lineColor?: string;
    textColor?: string;
    areaTopColor?: string;
    areaBottomColor?: string;
  };
}

export const ChartWidget: React.FC<ChartWidgetProps> = memo(
  ({ data, colors }) => {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);

    if (data.length === 0) {
      return (
        <div
          ref={chartContainerRef}
          role="img"
          aria-label="Price chart — no data available"
          style={{
            width: '100%',
            height: '300px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-muted)',
            fontSize: '14px',
            background: 'var(--bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ marginRight: '10px', opacity: 0.4 }}>
            <line x1="12" y1="1" x2="12" y2="23" />
            <polyline points="17 8 12 3 7 8" />
            <polyline points="7 16 12 21 17 16" />
          </svg>
          No chart data available
        </div>
      );
    }

    useEffect(() => {
      if (!chartContainerRef.current) return;

      const handleResize = () => {
        if (chartRef.current && chartContainerRef.current) {
          chartRef.current.applyOptions({
            width: chartContainerRef.current.clientWidth,
          });
        }
      };

      const chart = createChart(chartContainerRef.current, {
        layout: {
          background: {
            type: ColorType.Solid,
            color: colors?.backgroundColor || 'transparent',
          },
          textColor: colors?.textColor || '#d1d5db',
        },
        grid: {
          vertLines: { color: 'rgba(255, 255, 255, 0.04)' },
          horzLines: { color: 'rgba(255, 255, 255, 0.04)' },
        },
        width: chartContainerRef.current.clientWidth,
        height: 300,
        crosshair: {
          mode: 1,
          vertLine: {
            color: 'rgba(59, 130, 246, 0.4)',
            style: 2,
            width: 1,
            labelBackgroundColor: '#3B82F6',
          },
          horzLine: {
            color: 'rgba(59, 130, 246, 0.4)',
            style: 2,
            width: 1,
            labelBackgroundColor: '#3B82F6',
          },
        },
        timeScale: {
          borderColor: 'rgba(255, 255, 255, 0.05)',
          timeVisible: false,
        },
        rightPriceScale: {
          borderColor: 'rgba(255, 255, 255, 0.05)',
        },
      });

      const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#10b981',
        downColor: '#ef4444',
        borderVisible: false,
        wickUpColor: '#10b981',
        wickDownColor: '#ef4444',
      });

      const formattedData: CandlestickData[] = data.map((d) => ({
        time: (new Date(d.timestamp).getTime() / 1000) as Time,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      }));

      formattedData.sort(
        (a, b) => (a.time as number) - (b.time as number),
      );
      candlestickSeries.setData(formattedData);
      chart.timeScale().fitContent();

      chartRef.current = chart;
      seriesRef.current = candlestickSeries;

      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
        chart.remove();
      };
    }, [data, colors]);

    return (
      <div
        ref={chartContainerRef}
        role="img"
        aria-label={`Price chart with ${data.length} candles`}
        style={{ width: '100%', height: '300px' }}
      >
        <div className="visually-hidden">
          <table aria-label="Candlestick data">
            <caption>Candlestick data for the price chart. Last {Math.min(data.length, 20)} candles shown.</caption>
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Open</th>
                <th scope="col">High</th>
                <th scope="col">Low</th>
                <th scope="col">Close</th>
              </tr>
            </thead>
            <tbody>
              {data.slice(-20).map((d) => (
                <tr key={d.timestamp}>
                  <td>{new Date(d.timestamp).toLocaleDateString()}</td>
                  <td>{d.open}</td>
                  <td>{d.high}</td>
                  <td>{d.low}</td>
                  <td>{d.close}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  },
);

ChartWidget.displayName = 'ChartWidget';
