"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Building2, RefreshCw, Activity, Play, Pause } from "lucide-react";
import { useAccountReport } from "@/services/api/overview";
import { useCampaignsList, useUpdateCampaignStatus } from "@/services/api/campaigns";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { DataTable } from "@/components/ui/data-table";
import { ColumnDef } from "@tanstack/react-table";
import { useCampaignAlerts } from "@/hooks/use-campaign-alerts";
import { toast } from "sonner";

interface AccountLiveViewProps {
  profileId: string;
  accountId: string;
  nickname: string;
}

type CampaignInsights = {
  spend: number;
  roas: number;
  ctr: number;
  cpc: number;
  impressions: number;
  reach: number;
  clicks: number;
  purchases: number;
};

type Campaign = {
  campaign_id: string;
  campaign_name: string;
  effective_status: string;
  objective?: string;
  budget_type?: string;
  lifetime_budget?: number;
  bid_strategy?: string;
  insights?: CampaignInsights;
};

export function AccountLiveView({ profileId, accountId, nickname }: AccountLiveViewProps) {
  const { data: report, isLoading: loadingReport, isError: errorReport, refetch: refetchReport, isFetching: fetchingReport } = useAccountReport(profileId, accountId);
  const { data: campaignsData, isLoading: loadingCampaigns, isError: errorCampaigns, refetch: refetchCampaigns, isFetching: fetchingCampaigns } = useCampaignsList(profileId, accountId);
  const updateStatusMutation = useUpdateCampaignStatus();

  // Initialize auto-alerts for live updates
  useCampaignAlerts(nickname, campaignsData?.campaigns);

  const formatCurrency = (val: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
  const formatPct = (val: number) => `${val.toFixed(2)}%`;

  const isFetching = fetchingReport || fetchingCampaigns;
  const isLoading = loadingReport || loadingCampaigns;
  const isError = errorReport || errorCampaigns;

  const handleRefresh = () => {
    refetchReport();
    refetchCampaigns();
  };

  const handleToggleStatus = (campaignId: string, currentStatus: string) => {
    const newStatus = currentStatus === "ACTIVE" ? "PAUSED" : "ACTIVE";
    toast.promise(
      updateStatusMutation.mutateAsync({
        profileId,
        accountId,
        campaignId,
        status: newStatus,
      }),
      {
        loading: `Updating status to ${newStatus}...`,
        success: `Campaign status updated to ${newStatus}`,
        error: "Failed to update campaign status",
      }
    );
  };

  const columns: ColumnDef<Campaign>[] = [
    {
      accessorKey: "campaign_name",
      header: "Campaign Name",
      cell: ({ row }) => <div className="font-medium max-w-[250px] truncate" title={row.original.campaign_name}>{row.original.campaign_name}</div>,
    },
    {
      accessorKey: "effective_status",
      header: "Status",
      cell: ({ row }) => <StatusBadge status={row.original.effective_status.toLowerCase() as any} />,
    },
    {
      accessorKey: "insights.spend",
      header: "Spend",
      cell: ({ row }) => <div className="text-right font-medium">{formatCurrency(row.original.insights?.spend || 0)}</div>,
    },
    {
      accessorKey: "insights.roas",
      header: "ROAS",
      cell: ({ row }) => <div className="text-right">{((row.original.insights?.roas) || 0).toFixed(2)}x</div>,
    },
    {
      accessorKey: "insights.ctr",
      header: "CTR",
      cell: ({ row }) => <div className="text-right">{formatPct(row.original.insights?.ctr || 0)}</div>,
    },
    {
      accessorKey: "insights.cpc",
      header: "CPC",
      cell: ({ row }) => <div className="text-right">{formatCurrency(row.original.insights?.cpc || 0)}</div>,
    },
    {
      accessorKey: "insights.purchases",
      header: "Purchases",
      cell: ({ row }) => <div className="text-right">{row.original.insights?.purchases || 0}</div>,
    },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => {
        const isActive = row.original.effective_status === "ACTIVE";
        return (
          <div className="flex justify-end">
            <Button
              variant={isActive ? "destructive" : "default"}
              size="sm"
              className="h-7 text-xs"
              onClick={() => handleToggleStatus(row.original.campaign_id, row.original.effective_status)}
              disabled={updateStatusMutation.isPending}
            >
              {isActive ? <Pause className="h-3 w-3 mr-1" /> : <Play className="h-3 w-3 mr-1" />}
              {isActive ? "Pause" : "Activate"}
            </Button>
          </div>
        );
      },
    },
  ];

  return (
    <Card className="overflow-hidden border-border/50 shadow-sm">
      <CardHeader className="bg-muted/20 border-b pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-primary" />
            <CardTitle className="text-lg">{nickname}</CardTitle>
            <span className="text-xs text-muted-foreground ml-2">ID: {accountId}</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 mr-2 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 px-3 py-1.5 rounded-full text-xs font-medium">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              Live Auto-Sync
            </div>
            {isError ? (
              <StatusBadge status="error" />
            ) : (
              <StatusBadge status={isFetching ? "syncing" : "connected"} />
            )}
            <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isFetching}>
              <RefreshCw className={`h-3 w-3 mr-2 ${isFetching ? "animate-spin" : ""}`} />
              Refresh Data
            </Button>
          </div>
        </div>

        {/* Quick KPI Bar */}
        <div className="grid grid-cols-4 md:grid-cols-6 gap-4 pt-4">
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground">Total Spend (30d)</span>
            {isLoading ? <Skeleton className="h-5 w-16" /> : (
              <p className="text-sm font-bold">{report ? formatCurrency(report.total_spend) : "$0.00"}</p>
            )}
          </div>
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground">Avg ROAS</span>
            {isLoading ? <Skeleton className="h-5 w-12" /> : (
              <p className="text-sm font-bold">{report ? `${report.avg_roas.toFixed(2)}x` : "0.00x"}</p>
            )}
          </div>
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground">Avg CTR</span>
            {isLoading ? <Skeleton className="h-5 w-12" /> : (
              <p className="text-sm font-bold">{report ? formatPct(report.avg_ctr) : "0.00%"}</p>
            )}
          </div>
          <div className="space-y-1">
            <span className="text-xs text-muted-foreground">Avg CPC</span>
            {isLoading ? <Skeleton className="h-5 w-12" /> : (
              <p className="text-sm font-bold">{report ? formatCurrency(report.avg_cpc) : "$0.00"}</p>
            )}
          </div>
          <div className="space-y-1 hidden md:block">
            <span className="text-xs text-muted-foreground">Active Campaigns</span>
            {isLoading ? <Skeleton className="h-5 w-8" /> : (
              <p className="text-sm font-bold text-emerald-500">{report ? report.active_campaigns : 0}</p>
            )}
          </div>
          <div className="space-y-1 hidden md:block">
            <span className="text-xs text-muted-foreground">Paused Campaigns</span>
            {isLoading ? <Skeleton className="h-5 w-8" /> : (
              <p className="text-sm font-bold text-yellow-500">{report ? report.paused_campaigns : 0}</p>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        {isError ? (
          <div className="p-8 text-center text-destructive bg-destructive/5">
            <p className="font-medium">Failed to load data for this account.</p>
            <p className="text-sm mt-1">Please ensure the AdsPower profile is running and Facebook session is active.</p>
          </div>
        ) : isLoading ? (
          <div className="p-6 space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="flex justify-between items-center border-b pb-2">
                <Skeleton className="h-4 w-[200px]" />
                <Skeleton className="h-4 w-[80px]" />
                <Skeleton className="h-4 w-[60px]" />
              </div>
            ))}
          </div>
        ) : !campaignsData?.campaigns || campaignsData.campaigns.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            No campaigns found for this account in the last 30 days.
          </div>
        ) : (
          <DataTable 
            columns={columns} 
            data={campaignsData.campaigns} 
          />
        )}
      </CardContent>
    </Card>
  );
}
