import React, { useState } from 'react';
import { Button } from '../../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/Card';
import { SkeletonCard, SkeletonMetric } from '../../components/ui/Skeleton';
import { Tooltip } from '../../components/ui/Tooltip';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { toast } from 'sonner';
import { Plus, Trash2, CheckCircle2, AlertTriangle } from 'lucide-react';

export default function ComponentGallery() {
  const [showConfirm, setShowConfirm] = useState(false);

  return (
    <div className="space-y-8 max-w-5xl mx-auto pb-20">
      <div>
        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-accent/10 border border-accent/20 text-accent text-xs font-mono mb-2">
          DEV ONLY ROUTE
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-text">Design System Component Gallery</h1>
        <p className="text-sm text-text-muted mt-1">
          Visual test bench for semantic tokens, buttons, inputs, cards, tooltips, and loading skeletons.
        </p>
      </div>

      {/* Buttons */}
      <Card className="bg-surface border-border">
        <CardHeader>
          <CardTitle className="text-base">Buttons & Variants</CardTitle>
          <CardDescription className="text-xs">Standardized button styling across all actions.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <Button variant="default" className="bg-accent text-accent-foreground">Primary / Accent</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger" className="bg-danger text-white hover:bg-danger/90">Danger</Button>
          <Button isLoading className="bg-accent text-accent-foreground">Loading State</Button>
          <Button size="sm" className="bg-accent text-accent-foreground flex items-center gap-1.5">
            <Plus className="w-3.5 h-3.5" /> Small Action
          </Button>
        </CardContent>
      </Card>

      {/* Skeletons */}
      <Card className="bg-surface border-border">
        <CardHeader>
          <CardTitle className="text-base">Skeleton Loaders</CardTitle>
          <CardDescription className="text-xs">Context-matching skeleton states (no bare spinners).</CardDescription>
        </CardHeader>
        <CardContent className="grid sm:grid-cols-2 gap-4">
          <SkeletonMetric />
          <SkeletonCard />
        </CardContent>
      </Card>

      {/* Tooltips & Modals */}
      <Card className="bg-surface border-border">
        <CardHeader>
          <CardTitle className="text-base">Tooltips & Interactive Modals</CardTitle>
          <CardDescription className="text-xs">Accessible popovers and destructive action confirmations.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-4">
          <Tooltip content="Live YouTube upload pipeline active">
            <Button variant="outline" size="sm" className="flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-success" />
              Hover for Status Tooltip
            </Button>
          </Tooltip>

          <Tooltip content="Error details: Rate limit exceeded on vision model" side="bottom">
            <Button variant="outline" size="sm" className="flex items-center gap-1.5 text-danger border-danger/30">
              <AlertTriangle className="w-3.5 h-3.5" />
              Hover for Error Tooltip
            </Button>
          </Tooltip>

          <Button 
            variant="outline" 
            size="sm"
            onClick={() => setShowConfirm(true)}
            className="flex items-center gap-1.5 text-danger"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Open Confirmation Dialog
          </Button>

          <Button 
            variant="outline" 
            size="sm"
            onClick={() => toast.success("Toast message test!")}
          >
            Trigger Toast
          </Button>
        </CardContent>
      </Card>

      {/* Confirmation Dialog instance */}
      <ConfirmDialog
        isOpen={showConfirm}
        title="Test Destructive Confirmation"
        description="This action will delete the item from cloud storage permanently. Confirm to test."
        confirmText="Confirm Delete"
        confirmVariant="danger"
        onClose={() => setShowConfirm(false)}
        onConfirm={() => {
          setShowConfirm(false);
          toast.success("Confirmed successfully");
        }}
      />
    </div>
  );
}
