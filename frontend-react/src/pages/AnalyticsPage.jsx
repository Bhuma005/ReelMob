import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { 
  AreaChart, Area, BarChart, Bar, LineChart, Line, ReferenceLine, XAxis, YAxis, Tooltip as RechartsTooltip, 
  ResponsiveContainer, CartesianGrid, Cell 
} from 'recharts';
import { dashboardApi } from '../api/dashboard';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { SkeletonMetric } from '../components/ui/Skeleton';
import { 
  Activity, CheckCircle2, Clock, AlertCircle, Sparkles, ExternalLink, ArrowUpRight,
  TrendingUp, TrendingDown, Target, Zap, Tag
} from 'lucide-react';
import { format, subDays } from 'date-fns';
import { useNavigate } from 'react-router-dom';

// Custom dark Recharts Tooltip with benchmark comparison
const CustomChartTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const dataPoint = payload[0]?.payload;
    return (
      <div className="bg-surface border border-border p-3 rounded-lg shadow-xl text-xs font-mono space-y-1">
        <p className="text-text font-bold font-sans">{dataPoint?.title || label}</p>
        <div className="flex items-center justify-between gap-4 text-text-muted">
          <span>Views:</span>
          <span className="font-bold text-accent">{dataPoint?.views?.toLocaleString() ?? payload[0]?.value}</span>
        </div>
        {dataPoint?.rolling_avg_views != null && (
          <div className="flex items-center justify-between gap-4 text-text-muted">
            <span>30d Baseline:</span>
            <span className="font-semibold text-purple-400">{Math.round(dataPoint.rolling_avg_views).toLocaleString()}</span>
          </div>
        )}
        {dataPoint?.diff_pct != null && (
          <div className="flex items-center justify-between gap-4 pt-1 border-t border-border/60">
            <span>Benchmark:</span>
            <span className={dataPoint.diff_pct >= 0 ? "font-bold text-success" : "font-bold text-danger"}>
              {dataPoint.diff_pct >= 0 ? `+${dataPoint.diff_pct}%` : `${dataPoint.diff_pct}%`}
            </span>
          </div>
        )}
      </div>
    );
  }
  return null;
};

export default function AnalyticsPage() {
  const navigate = useNavigate();
  const [timeRange, setTimeRange] = useState('30d');

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboardStats'],
    queryFn: dashboardApi.getStats,
  });

  const { data: videosData, isLoading: videosLoading } = useQuery({
    queryKey: ['dashboardVideosAnalytics'],
    queryFn: () => dashboardApi.getVideos({ page: 1, limit: 50 }),
  });

  const { data: trendsData, isLoading: trendsLoading } = useQuery({
    queryKey: ['dashboardTrends', timeRange],
    queryFn: () => dashboardApi.getTrends(timeRange === '7d' ? 7 : 30),
  });

  const { data: tagAnalyticsData, isLoading: tagAnalyticsLoading } = useQuery({
    queryKey: ['dashboardAnalyticsTags', timeRange],
    queryFn: () => dashboardApi.getTagAnalytics(timeRange === '7d' ? 7 : 30),
  });


  const pending = stats?.pending ?? stats?.scheduled ?? 0;
  const uploaded = stats?.uploaded ?? stats?.published ?? 0;
  const failed = stats?.failed ?? 0;
  const total = stats?.total ?? (pending + uploaded + failed);

  const successRate = total > 0 ? Math.round((uploaded / total) * 100) : 0;
  const failureRate = total > 0 ? Math.round((failed / total) * 100) : 0;

  const videos = videosData?.videos || [];
  const scheduledWithTime = videos.filter((v) => Boolean(v.schedule_time || v.scheduled_time)).length;

  // Synthesize timeline data from video creation dates or generate rolling window
  const daysCount = timeRange === '7d' ? 7 : 30;
  const activityData = Array.from({ length: daysCount }).map((_, i) => {
    const d = subDays(new Date(), daysCount - 1 - i);
    const dateStr = format(d, 'yyyy-MM-dd');
    const dayLabel = format(d, 'MMM d');
    
    // Count videos created on this date
    const count = videos.filter(v => v.created_at && v.created_at.startsWith(dateStr)).length;
    return {
      date: dayLabel,
      videos: count,
      published: count > 0 ? Math.min(count, Math.floor(count * 0.8)) : 0
    };
  });

  // Hourly distribution
  const hourlyData = [
    { hour: '06:00', intensity: 20 },
    { hour: '09:00', intensity: 45 },
    { hour: '12:00', intensity: 65 },
    { hour: '15:00', intensity: 75 },
    { hour: '18:00', intensity: 95 },
    { hour: '20:00', intensity: 90 },
    { hour: '22:00', intensity: 40 },
  ];

  const hasInsufficientData = total < 5;

  return (
    <motion.div 
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="space-y-6 max-w-6xl mx-auto pb-20"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-text">
            Performance Analytics
          </h1>
          <p className="text-xs sm:text-sm text-text-muted mt-1">
            Real-time pipeline throughput, cloud queue reliability, and engagement telemetry.
          </p>
        </div>

        <div className="flex items-center gap-1.5 p-1 bg-surface-elevated rounded-lg border border-border w-fit">
          <button
            type="button"
            onClick={() => setTimeRange('7d')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
              timeRange === '7d' ? 'bg-accent text-accent-foreground shadow-xs' : 'text-text-muted hover:text-text'
            }`}
          >
            Last 7 Days
          </button>
          <button
            type="button"
            onClick={() => setTimeRange('30d')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
              timeRange === '30d' ? 'bg-accent text-accent-foreground shadow-xs' : 'text-text-muted hover:text-text'
            }`}
          >
            Last 30 Days
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        {statsLoading ? (
          <>
            <SkeletonMetric />
            <SkeletonMetric />
            <SkeletonMetric />
            <SkeletonMetric />
          </>
        ) : (
          <>
            <Card className="bg-surface border-border">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-xs font-mono font-medium text-text-muted uppercase tracking-wider">
                  Total Processed
                </CardTitle>
                <Activity className="h-4 w-4 text-accent" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono text-text">{total}</div>
                <p className="text-[11px] text-text-muted mt-1">Videos managed in cloud</p>
              </CardContent>
            </Card>

            <Card className="bg-surface border-border">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-xs font-mono font-medium text-text-muted uppercase tracking-wider">
                  Publish Success
                </CardTitle>
                <CheckCircle2 className="h-4 w-4 text-success" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono text-success">{successRate}%</div>
                <p className="text-[11px] text-text-muted mt-1">{uploaded} videos live on YouTube</p>
              </CardContent>
            </Card>

            <Card className="bg-surface border-border">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-xs font-mono font-medium text-text-muted uppercase tracking-wider">
                  Queue Failure Rate
                </CardTitle>
                <AlertCircle className="h-4 w-4 text-danger" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono text-danger">{failureRate}%</div>
                <p className="text-[11px] text-text-muted mt-1">{failed} failed jobs requiring retry</p>
              </CardContent>
            </Card>

            <Card className="bg-surface border-border">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-xs font-mono font-medium text-text-muted uppercase tracking-wider">
                  Scheduled Slots
                </CardTitle>
                <Clock className="h-4 w-4 text-warning" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono text-warning">
                  {videosLoading ? '-' : scheduledWithTime}
                </div>
                <p className="text-[11px] text-text-muted mt-1">Pending future time slots</p>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* Guidance State when data is young */}
      {hasInsufficientData && (
        <Card className="bg-surface border-accent/30 p-5 bg-accent/5">
          <div className="flex items-start gap-3.5">
            <div className="p-2 rounded-lg bg-accent/15 text-accent shrink-0 mt-0.5">
              <Sparkles className="w-5 h-5" />
            </div>
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-text">
                Heuristic Baseline Active (Low Historical Volume)
              </h4>
              <p className="text-xs text-text-muted leading-relaxed">
                Your pipeline has processed {total} {total === 1 ? 'video' : 'videos'}. As you schedule more reels, ReelsMob's multi-agent system automatically learns your channel's specific audience retention peak and sharpens publish time recommendations.
              </p>
              <div className="pt-2">
                <Button 
                  size="sm"
                  onClick={() => navigate('/create')}
                  className="bg-accent text-accent-foreground text-xs font-semibold cursor-pointer"
                >
                  Create & Schedule More Reels
                </Button>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* 30-Day Channel Trend Benchmark Comparison Card */}
      <Card className="bg-surface border-border overflow-hidden">
        <CardHeader className="py-4 px-6 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-surface-elevated/20">
          <div>
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-accent" />
              <CardTitle className="text-sm font-semibold text-text">
                Channel Performance Trends & 30-Day Rolling Benchmark
              </CardTitle>
            </div>
            <CardDescription className="text-xs text-text-muted mt-0.5">
              Telemetry tracking individual reel views against the 30-day channel baseline
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono text-purple-400 bg-purple-500/10 border border-purple-500/20 px-2.5 py-1 rounded-md flex items-center gap-1.5">
              <Target className="w-3.5 h-3.5" />
              Baseline: {Math.round(trendsData?.summary?.rolling_avg_views || 0).toLocaleString()} views
            </span>
          </div>
        </CardHeader>

        <CardContent className="p-6 space-y-6">
          {/* Trend KPI Stat Badges */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg bg-surface-elevated/50 border border-border">
              <span className="text-[10px] font-mono text-text-muted uppercase tracking-wider block">
                30-Day Channel Baseline
              </span>
              <span className="text-lg font-mono font-bold text-text mt-0.5 block">
                {Math.round(trendsData?.summary?.rolling_avg_views || 0).toLocaleString()}
              </span>
              <span className="text-[10px] text-text-muted">Views per reel average</span>
            </div>

            <div className="p-3 rounded-lg bg-success/5 border border-success/20">
              <span className="text-[10px] font-mono text-success uppercase tracking-wider block flex items-center gap-1">
                <TrendingUp className="w-3 h-3" /> Overperforming
              </span>
              <span className="text-lg font-mono font-bold text-success mt-0.5 block">
                {trendsData?.summary?.overperforming_count ?? 0} Reels
              </span>
              <span className="text-[10px] text-success/80">&gt; 15% above channel baseline</span>
            </div>

            <div className="p-3 rounded-lg bg-danger/5 border border-danger/20">
              <span className="text-[10px] font-mono text-danger uppercase tracking-wider block flex items-center gap-1">
                <TrendingDown className="w-3 h-3" /> Underperforming
              </span>
              <span className="text-lg font-mono font-bold text-danger mt-0.5 block">
                {trendsData?.summary?.underperforming_count ?? 0} Reels
              </span>
              <span className="text-[10px] text-danger/80">&lt; 15% below channel baseline</span>
            </div>

            <div className="p-3 rounded-lg bg-surface-elevated/50 border border-border">
              <span className="text-[10px] font-mono text-text-muted uppercase tracking-wider block flex items-center gap-1">
                <Zap className="w-3 h-3 text-accent" /> Avg Engagement
              </span>
              <span className="text-lg font-mono font-bold text-accent mt-0.5 block">
                {trendsData?.summary?.rolling_avg_engagement_rate ?? 0}%
              </span>
              <span className="text-[10px] text-text-muted">Likes & comments ratio</span>
            </div>
          </div>

          {/* Benchmark Recharts Line Chart */}
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendsData?.trends || []} margin={{ top: 10, right: 15, left: -15, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                <XAxis 
                  dataKey="date" 
                  stroke="#71717a" 
                  fontSize={11} 
                  tickLine={false} 
                  axisLine={false} 
                />
                <YAxis 
                  stroke="#71717a" 
                  fontSize={11} 
                  tickLine={false} 
                  axisLine={false} 
                />
                <RechartsTooltip content={<CustomChartTooltip />} />
                {trendsData?.summary?.rolling_avg_views && (
                  <ReferenceLine 
                    y={trendsData.summary.rolling_avg_views} 
                    stroke="#c084fc" 
                    strokeDasharray="4 4" 
                    strokeWidth={1.5}
                  />
                )}
                <Line 
                  type="monotone" 
                  dataKey="views" 
                  name="Reel Views" 
                  stroke="#ff6b2b" 
                  strokeWidth={2.5} 
                  dot={{ r: 4, fill: '#ff6b2b', strokeWidth: 0 }}
                  activeDot={{ r: 6, fill: '#ff6b2b' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* 2-Column Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart 1: Pipeline Production Volume Over Time (2 cols) */}
        <Card className="bg-surface border-border lg:col-span-2">
          <CardHeader className="py-4 px-6 border-b border-border flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-sm font-semibold text-text">
                Video Creation & Throughput
              </CardTitle>
              <CardDescription className="text-xs text-text-muted mt-0.5">
                Daily volume of reels ingested and processed
              </CardDescription>
            </div>
            <span className="text-xs font-mono text-accent font-semibold">
              {total} Total
            </span>
          </CardHeader>

          <CardContent className="p-6">
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={activityData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="accentGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ff6b2b" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#ff6b2b" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                  <XAxis 
                    dataKey="date" 
                    stroke="#71717a" 
                    fontSize={11} 
                    tickLine={false} 
                    axisLine={false} 
                  />
                  <YAxis 
                    stroke="#71717a" 
                    fontSize={11} 
                    tickLine={false} 
                    axisLine={false} 
                    allowDecimals={false}
                  />
                  <RechartsTooltip content={<CustomChartTooltip />} />
                  <Area 
                    type="monotone" 
                    dataKey="videos" 
                    name="Videos Ingested"
                    stroke="#ff6b2b" 
                    strokeWidth={2}
                    fillOpacity={1} 
                    fill="url(#accentGradient)" 
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Chart 2: Hourly Engagement Distribution (1 col) */}
        <Card className="bg-surface border-border flex flex-col justify-between">
          <CardHeader className="py-4 px-6 border-b border-border">
            <CardTitle className="text-sm font-semibold text-text">
              Hourly Engagement Intensity
            </CardTitle>
            <CardDescription className="text-xs text-text-muted mt-0.5">
              Audience availability probability index
            </CardDescription>
          </CardHeader>

          <CardContent className="p-6">
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={hourlyData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                  <XAxis 
                    dataKey="hour" 
                    stroke="#71717a" 
                    fontSize={10} 
                    tickLine={false} 
                    axisLine={false} 
                  />
                  <YAxis 
                    stroke="#71717a" 
                    fontSize={10} 
                    tickLine={false} 
                    axisLine={false} 
                  />
                  <RechartsTooltip content={<CustomChartTooltip />} />
                  <Bar dataKey="intensity" name="Engagement %" radius={[4, 4, 0, 0]}>
                    {hourlyData.map((entry, index) => (
                      <Cell 
                        key={`cell-${index}`} 
                        fill={entry.intensity >= 90 ? '#ff6b2b' : entry.intensity >= 60 ? '#e5a955' : '#52525b'} 
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Performance by Tag Card */}
      <Card className="bg-surface border-border">
        <CardHeader className="py-4 px-6 border-b border-border flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-sm font-semibold text-text flex items-center gap-2">
              <Tag className="w-4 h-4 text-accent" />
              Performance by Content Tag
            </CardTitle>
            <CardDescription className="text-xs text-text-muted mt-0.5">
              Average viewership and engagement efficiency benchmarked against library baseline ({timeRange === '7d' ? '7 days' : '30 days'})
            </CardDescription>
          </div>
          {tagAnalyticsData?.tags?.length > 0 && (
            <span className="text-xs font-mono text-accent bg-accent/10 px-2.5 py-1 rounded-full border border-accent/20">
              {tagAnalyticsData.tags.length} active {tagAnalyticsData.tags.length === 1 ? 'tag' : 'tags'}
            </span>
          )}
        </CardHeader>

        <CardContent className="p-0">
          {tagAnalyticsLoading ? (
            <div className="p-8 text-center text-xs text-text-muted font-mono animate-pulse">
              Computing tag performance benchmarks...
            </div>
          ) : !tagAnalyticsData?.tags || tagAnalyticsData.tags.length === 0 ? (
            <div className="p-8 text-center flex flex-col items-center justify-center">
              <Tag className="w-8 h-8 text-text-muted opacity-30 mb-2" />
              <p className="text-xs font-semibold text-text">No tagged videos found</p>
              <p className="text-xs text-text-muted max-w-sm mt-1">
                Add tags to your videos in the Content Library to analyze view distributions and engagement patterns by topic.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/library')}
                className="mt-3 text-xs cursor-pointer"
              >
                Go to Library
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-elevated/70 border-b border-border text-text-muted font-mono uppercase text-[10px]">
                  <tr>
                    <th className="p-3 pl-6">Tag Name</th>
                    <th className="p-3">Videos</th>
                    <th className="p-3">Avg Views</th>
                    <th className="p-3">Avg Engagement</th>
                    <th className="p-3 pr-6 text-right">Benchmark Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60 font-sans">
                  {tagAnalyticsData.tags.map((item) => {
                    const statusBadge = 
                      item.benchmark_status === 'overperforming' ? (
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full font-bold uppercase bg-success/15 text-success inline-flex items-center gap-1">
                          <TrendingUp className="w-3 h-3" /> Overperforming
                        </span>
                      ) : item.benchmark_status === 'underperforming' ? (
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full font-bold uppercase bg-danger/15 text-danger inline-flex items-center gap-1">
                          <TrendingDown className="w-3 h-3" /> Underperforming
                        </span>
                      ) : (
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full font-medium uppercase bg-surface-elevated/80 text-text-muted">
                          Average
                        </span>
                      );

                    return (
                      <tr key={item.tag} className="hover:bg-surface-elevated/40 transition-colors">
                        <td className="p-3 pl-6 font-mono font-semibold text-accent">
                          #{item.tag}
                        </td>
                        <td className="p-3 font-mono text-text">
                          {item.video_count}
                        </td>
                        <td className="p-3 font-mono text-text font-medium">
                          {Math.round(item.avg_views).toLocaleString()}
                        </td>
                        <td className="p-3 font-mono text-text-muted">
                          {item.avg_engagement_rate != null ? `${(item.avg_engagement_rate * 100).toFixed(1)}%` : '—'}
                        </td>
                        <td className="p-3 pr-6 text-right whitespace-nowrap">
                          {statusBadge}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Top Videos Ingested Table */}
      <Card className="bg-surface border-border">
        <CardHeader className="py-4 px-6 border-b border-border flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-sm font-semibold text-text">
              Recent Video Queue Telemetry
            </CardTitle>
            <CardDescription className="text-xs text-text-muted mt-0.5">
              Status and scheduled distribution of latest items
            </CardDescription>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/library')}
            className="text-xs text-text-muted hover:text-text flex items-center gap-1 cursor-pointer"
          >
            Open library <ArrowUpRight className="w-3.5 h-3.5" />
          </Button>
        </CardHeader>

        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-elevated/70 border-b border-border text-text-muted font-mono uppercase text-[10px]">
                <tr>
                  <th className="p-3 pl-6">Video Title</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">30d Benchmark</th>
                  <th className="p-3">Publish Slot</th>
                  <th className="p-3 pr-6 text-right">Destination</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60 font-sans">
                {videos.slice(0, 5).map((v) => {
                  const trendMatch = trendsData?.trends?.find(t => t.video_id === v.id || t.title === v.title);
                  return (
                    <tr key={v.id} className="hover:bg-surface-elevated/40 transition-colors">
                      <td className="p-3 pl-6 font-medium text-text max-w-sm truncate">
                        {v.title || 'Untitled Video'}
                      </td>
                      <td className="p-3 whitespace-nowrap">
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-semibold uppercase ${
                          v.status === 'published' ? 'bg-success/15 text-success' :
                          v.status === 'failed' ? 'bg-danger/15 text-danger' :
                          'bg-warning/15 text-warning'
                        }`}>
                          {v.status || 'Pending'}
                        </span>
                      </td>
                      <td className="p-3 whitespace-nowrap">
                        {trendMatch?.performance === 'overperforming' ? (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full font-bold uppercase bg-success/15 text-success inline-flex items-center gap-1">
                            <TrendingUp className="w-3 h-3" /> +{trendMatch.diff_pct}%
                          </span>
                        ) : trendMatch?.performance === 'underperforming' ? (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full font-bold uppercase bg-danger/15 text-danger inline-flex items-center gap-1">
                            <TrendingDown className="w-3 h-3" /> {trendMatch.diff_pct}%
                          </span>
                        ) : (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full font-medium uppercase bg-surface-elevated/80 text-text-muted">
                            {trendMatch ? `${trendMatch.diff_pct >= 0 ? '+' : ''}${trendMatch.diff_pct}%` : 'Baseline'}
                          </span>
                        )}
                      </td>
                    <td className="p-3 whitespace-nowrap font-mono text-text-muted text-[11px]">
                      {v.schedule_time || v.scheduled_time 
                        ? format(new Date(v.schedule_time || v.scheduled_time), 'MMM d, h:mm a')
                        : 'Unscheduled'}
                    </td>
                    <td className="p-3 pr-6 text-right whitespace-nowrap">
                      {v.youtube_url ? (
                        <a 
                          href={v.youtube_url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-accent hover:underline inline-flex items-center gap-1 font-mono text-[11px]"
                        >
                          YouTube Shorts <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : (
                        <span className="text-text-muted font-mono text-[11px]">Supabase Cloud</span>
                      )}
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
