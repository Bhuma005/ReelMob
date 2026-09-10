import React from 'react';

export function Skeleton({ className = '', ...props }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-white/[0.06] ${className}`}
      {...props}
    />
  );
}

export function SkeletonMetric() {
  return (
    <div className="p-4 rounded-xl border border-border/70 bg-surface space-y-3">
      <div className="flex items-center justify-between">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-4 w-4 rounded-full" />
      </div>
      <Skeleton className="h-7 w-16" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}

export function SkeletonTableRow() {
  return (
    <div className="flex items-center gap-4 p-4 border-b border-border/50">
      <Skeleton className="w-16 h-12 rounded-lg shrink-0" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-3/4 max-w-sm" />
        <Skeleton className="h-3 w-1/2 max-w-xs" />
      </div>
      <Skeleton className="h-6 w-20 rounded-full shrink-0" />
      <Skeleton className="h-8 w-24 rounded-md shrink-0 hidden sm:block" />
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="rounded-xl border border-border bg-surface overflow-hidden space-y-3 p-4">
      <Skeleton className="aspect-video w-full rounded-lg" />
      <Skeleton className="h-4 w-3/4" />
      <div className="flex items-center gap-2">
        <Skeleton className="h-5 w-16 rounded-full" />
        <Skeleton className="h-3 w-20" />
      </div>
    </div>
  );
}
