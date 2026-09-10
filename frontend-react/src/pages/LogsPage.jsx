import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '../api/dashboard';
import { Card, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { SkeletonTableRow } from '../components/ui/Skeleton';
import { 
  Terminal, RefreshCw, Activity, CheckCircle2, Clock, Trash2, 
  AlertCircle, Search, ChevronDown, ChevronRight, Copy
} from 'lucide-react';
import { format } from 'date-fns';
import { toast } from 'sonner';
import { cn } from '../lib/utils';

export default function LogsPage() {
  const [activeTab, setActiveTab] = useState('activity'); // 'activity' | 'raw'
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('ALL'); // 'ALL' | 'SUCCESS' | 'FAILED' | 'DELETED'
  const [expandedRowId, setExpandedRowId] = useState(null);

  const { data: logsData, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['dashboardLogs'],
    queryFn: dashboardApi.getLogs,
    refetchInterval: 8000,
  });

  const activityEvents = logsData?.activity_events || [];
  const rawLogs = logsData?.logs || [];

  const getEventBadge = (type) => {
    if (type?.includes('SUCCESS') || type?.includes('PUBLISHED')) {
      return (
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-success/15 text-success border border-success/30 font-bold inline-flex items-center gap-1">
          <CheckCircle2 className="w-3 h-3" /> SUCCESS
        </span>
      );
    }
    if (type?.includes('FAILED') || type?.includes('ERROR')) {
      return (
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-danger/15 text-danger border border-danger/30 font-bold inline-flex items-center gap-1">
          <AlertCircle className="w-3 h-3" /> FAILED
        </span>
      );
    }
    if (type?.includes('DELETE')) {
      return (
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-surface-elevated text-zinc-400 border border-border font-bold inline-flex items-center gap-1">
          <Trash2 className="w-3 h-3" /> DELETED
        </span>
      );
    }
    return (
      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-warning/15 text-warning border border-warning/30 font-bold inline-flex items-center gap-1">
        <Clock className="w-3 h-3" /> QUEUED
      </span>
    );
  };

  // Filter events
  const filteredEvents = activityEvents.filter((evt) => {
    const matchesSearch = 
      !searchTerm || 
      evt.event_type?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      evt.message?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      evt.video_library?.title?.toLowerCase().includes(searchTerm.toLowerCase());

    if (!matchesSearch) return false;

    if (filterType === 'ALL') return true;
    if (filterType === 'SUCCESS') return evt.event_type?.includes('SUCCESS') || evt.event_type?.includes('PUBLISHED');
    if (filterType === 'FAILED') return evt.event_type?.includes('FAILED') || evt.event_type?.includes('ERROR');
    if (filterType === 'DELETED') return evt.event_type?.includes('DELETE');
    return true;
  });

  // Filter raw logs
  const filteredRawLogs = rawLogs.filter((line) => 
    !searchTerm || line.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Redact potential secret keys in string
  const redactSecrets = (text) => {
    if (!text) return '';
    return text.replace(/(key|token|secret|password)=([a-zA-Z0-9_-]+)/gi, '$1=••••••••');
  };

  return (
    <div className="space-y-5 max-w-6xl mx-auto pb-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-text">
            Audit & Engine Logs
          </h1>
          <p className="text-xs sm:text-sm text-text-muted mt-1">
            Structured cloud audit trail (<code className="text-accent">video_activity_log</code>) and real-time engine processing logs.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="p-1 bg-surface-elevated rounded-lg border border-border flex gap-1">
            <button
              type="button"
              onClick={() => setActiveTab('activity')}
              className={cn(
                "px-3 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer flex items-center gap-1.5",
                activeTab === 'activity' ? "bg-accent text-accent-foreground shadow-xs" : "text-text-muted hover:text-text"
              )}
            >
              <Activity className="w-3.5 h-3.5" /> Structured Activity
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('raw')}
              className={cn(
                "px-3 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer flex items-center gap-1.5",
                activeTab === 'raw' ? "bg-accent text-accent-foreground shadow-xs" : "text-text-muted hover:text-text"
              )}
            >
              <Terminal className="w-3.5 h-3.5" /> Raw Engine Log
            </button>
          </div>

          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => refetch()} 
            className="text-xs flex items-center gap-1 cursor-pointer"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", isFetching && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search log messages, event types, video titles..."
            className="w-full bg-surface border border-border rounded-lg pl-9 pr-4 py-2 text-xs text-text placeholder:text-text-muted focus:outline-none focus:border-accent font-mono transition-colors"
          />
          {searchTerm && (
            <button
              type="button"
              onClick={() => setSearchTerm('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-text-muted hover:text-text cursor-pointer"
            >
              ✕
            </button>
          )}
        </div>

        {activeTab === 'activity' && (
          <div className="flex flex-wrap gap-1 p-1 bg-surface rounded-lg border border-border w-fit text-xs">
            {['ALL', 'SUCCESS', 'FAILED', 'DELETED'].map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => setFilterType(type)}
                className={cn(
                  "px-2.5 py-1 rounded font-mono uppercase text-[10px] font-semibold transition-colors cursor-pointer",
                  filterType === type 
                    ? "bg-accent text-accent-foreground shadow-xs" 
                    : "text-text-muted hover:text-text"
                )}
              >
                {type}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Tab 1: Structured Activity Table */}
      {activeTab === 'activity' ? (
        <Card className="bg-surface border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-surface-elevated/70 border-b border-border text-text-muted uppercase text-[10px]">
                <tr>
                  <th className="p-3 pl-5 w-10"></th>
                  <th className="p-3 w-44">Timestamp</th>
                  <th className="p-3 w-36">Status</th>
                  <th className="p-3 w-48">Event Type</th>
                  <th className="p-3">Details & Video Context</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {isLoading ? (
                  <tr>
                    <td colSpan={5} className="p-6">
                      <div className="space-y-2">
                        <SkeletonTableRow />
                        <SkeletonTableRow />
                        <SkeletonTableRow />
                      </div>
                    </td>
                  </tr>
                ) : filteredEvents.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-12 text-center text-text-muted">
                      <Activity className="w-8 h-8 opacity-30 mx-auto mb-2" />
                      <p className="text-xs">No activity log entries match your filter.</p>
                    </td>
                  </tr>
                ) : (
                  filteredEvents.map((evt, idx) => {
                    const rowId = evt.id || idx;
                    const isExpanded = expandedRowId === rowId;

                    return (
                      <React.Fragment key={rowId}>
                        <tr 
                          onClick={() => setExpandedRowId(isExpanded ? null : rowId)}
                          className={cn(
                            "hover:bg-surface-elevated/40 transition-colors cursor-pointer group",
                            isExpanded && "bg-surface-elevated/50"
                          )}
                        >
                          <td className="p-3 pl-5 text-text-muted">
                            {isExpanded ? (
                              <ChevronDown className="w-4 h-4 text-accent" />
                            ) : (
                              <ChevronRight className="w-4 h-4 group-hover:text-text" />
                            )}
                          </td>

                          <td className="p-3 text-text-muted whitespace-nowrap text-[11px]">
                            {evt.created_at ? format(new Date(evt.created_at), 'MMM d, HH:mm:ss') : '-'}
                          </td>

                          <td className="p-3 whitespace-nowrap">
                            {getEventBadge(evt.event_type)}
                          </td>

                          <td className="p-3 font-semibold text-text truncate">
                            {evt.event_type}
                          </td>

                          <td className="p-3 text-text max-w-md truncate font-sans text-xs">
                            <span>{redactSecrets(evt.message)}</span>
                            {evt.video_library?.title && (
                              <span className="text-text-muted block text-[11px] truncate mt-0.5">
                                Reel: {evt.video_library.title}
                              </span>
                            )}
                          </td>
                        </tr>

                        {/* Expanded Details JSON Payload */}
                        {isExpanded && (
                          <tr className="bg-surface-elevated/30">
                            <td colSpan={5} className="p-4 pl-12 pr-6">
                              <div className="p-3 rounded-lg bg-background border border-border/70 font-mono text-[11px] space-y-2">
                                <div className="flex items-center justify-between text-text-muted text-[10px] pb-2 border-b border-border/50">
                                  <span>RAW EVENT PAYLOAD</span>
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      navigator.clipboard.writeText(JSON.stringify(evt, null, 2));
                                      toast.success("Event JSON copied");
                                    }}
                                    className="hover:text-accent flex items-center gap-1 cursor-pointer"
                                  >
                                    <Copy className="w-3 h-3" /> Copy JSON
                                  </button>
                                </div>
                                <pre className="text-text overflow-x-auto whitespace-pre-wrap leading-relaxed">
                                  {redactSecrets(JSON.stringify(evt, null, 2))}
                                </pre>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        /* Tab 2: Raw Engine Logs (Terminal look) */
        <Card className="bg-black border-border overflow-hidden shadow-2xl">
          <div className="bg-zinc-900/90 px-4 py-2.5 border-b border-zinc-800 flex items-center justify-between text-xs font-mono text-zinc-400">
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-accent" />
              <span>reelgrab_audit.log</span>
            </div>
            <span>{filteredRawLogs.length} lines</span>
          </div>

          <CardContent className="p-4 overflow-x-auto font-mono text-xs leading-relaxed max-h-[600px] overflow-y-auto space-y-1">
            {isLoading ? (
              <p className="text-zinc-500 animate-pulse">Reading engine log buffer...</p>
            ) : filteredRawLogs.length === 0 ? (
              <p className="text-zinc-600">No raw log entries found.</p>
            ) : (
              filteredRawLogs.map((line, idx) => (
                <div key={idx} className="flex items-start gap-3 hover:bg-zinc-900/50 px-2 py-0.5 rounded">
                  <span className="text-zinc-600 select-none w-8 text-right shrink-0">
                    {idx + 1}
                  </span>
                  <span className={cn(
                    "whitespace-pre-wrap break-all",
                    line.includes('ERROR') || line.includes('FAILED') ? "text-danger" :
                    line.includes('SUCCESS') || line.includes('UPLOADED') ? "text-success" :
                    line.includes('DELETED') ? "text-zinc-400" : "text-zinc-200"
                  )}>
                    {redactSecrets(line)}
                  </span>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
