"use client";

import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Filter, Download, ArrowUpDown, Building2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useCampaignsList, useUpdateCampaignStatus } from "@/services/api/campaigns";
import { useBrowsers } from "@/services/api/browser";
import { useAccounts } from "@/services/api/accounts";
import { useSessionStore } from "@/store/ui-store";
import { DataTable } from "@/components/ui/data-table";
import { ColumnDef } from "@tanstack/react-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { Play, Pause } from "lucide-react";
import { toast } from "sonner";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type CampaignInsights = {
  spend: number;
  roas: number;
  ctr: number;
  cpc: number;
  cpm?: number;
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
  daily_budget?: number;
  bid_strategy?: string;
  learning_status?: string;
  insights?: CampaignInsights;
};

export default function CampaignsPage() {
  const { activeProfileId, activeAccountId, setActiveProfile, setActiveAccount } = useSessionStore();
  const { data: campaignsData, isLoading, isError, error } = useCampaignsList(activeProfileId, activeAccountId);
  const updateStatusMutation = useUpdateCampaignStatus();
  
  const { data: browsers } = useBrowsers();
  const { data: accounts } = useAccounts();
  
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null);

  const formatCurrency = (val: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
  const formatPct = (val: number) => `${val.toFixed(2)}%`;

  const handleToggleStatus = (campaignId: string, currentStatus: string) => {
    if (!activeProfileId || !activeAccountId) return;
    const newStatus = currentStatus === "ACTIVE" ? "PAUSED" : "ACTIVE";
    toast.promise(
      updateStatusMutation.mutateAsync({
        profileId: activeProfileId,
        accountId: activeAccountId,
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

  const handleAccountChange = (accountId: string | null) => {
    if (!accountId) return;
    const account = accounts?.find(a => a.accountId === accountId);
    if (account) {
      const browser = browsers?.find(b => b.id === account.browserId);
      if (browser) {
        setActiveProfile(browser.profileId);
        setActiveAccount(account.accountId);
        setSelectedCampaign(null);
      }
    }
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
      header: ({ column }) => (
        <Button variant="ghost" className="-ml-4 h-8" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
          Spend <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => <div className="text-right font-medium">{formatCurrency(row.original.insights?.spend || 0)}</div>,
    },
    {
      accessorKey: "insights.roas",
      header: ({ column }) => (
        <Button variant="ghost" className="-ml-4 h-8" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
          ROAS <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
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
              onClick={(e) => {
                e.stopPropagation();
                handleToggleStatus(row.original.campaign_id, row.original.effective_status);
              }}
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
    <div className="flex flex-col gap-6 h-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Campaigns</h1>
          <p className="text-muted-foreground mt-2">Monitor and analyze your ad campaigns.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline">
            <Download className="mr-2 h-4 w-4" /> Export
          </Button>
        </div>
      </div>

      {/* Filters Placeholder */}
      <Card>
        <CardContent className="p-4 flex items-center gap-4">
          <div className="flex-1 flex items-center gap-4">
            <div className="relative max-w-sm flex-1">
              <Input placeholder="Search campaigns..." />
            </div>
            
            <Select value={activeAccountId || undefined} onValueChange={handleAccountChange}>
              <SelectTrigger className="w-[300px]">
                <SelectValue placeholder="Select Ad Account" />
              </SelectTrigger>
              <SelectContent>
                {browsers?.map(browser => {
                  const browserAccounts = accounts?.filter(a => a.browserId === browser.id);
                  if (!browserAccounts || browserAccounts.length === 0) return null;
                  return (
                    <SelectGroup key={browser.id}>
                      <SelectLabel className="flex items-center gap-2 text-primary">
                        <Building2 className="h-4 w-4" />
                        {browser.name}
                      </SelectLabel>
                      {browserAccounts.map(acc => (
                        <SelectItem key={acc.accountId} value={acc.accountId}>
                          {acc.nickname} <span className="text-muted-foreground ml-2 text-xs">({acc.accountId})</span>
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  );
                })}
              </SelectContent>
            </Select>

            <Button variant="outline" className="gap-2">
              <Filter className="h-4 w-4" />
              Filters
            </Button>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>Last 30 Days</span>
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-6 flex-1 min-h-0">
        {/* Campaign List */}
        <Card className="flex-1 flex flex-col min-h-0">
          <CardHeader className="pb-3 border-b">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">
                {campaignsData?.total ? `${campaignsData.total} Campaigns` : "All Campaigns"}
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="flex-1 p-0 overflow-auto">
            {!activeProfileId || !activeAccountId ? (
              <div className="flex flex-col items-center justify-center h-64 text-center p-6">
                <Filter className="h-8 w-8 text-muted-foreground mb-4" />
                <h3 className="font-medium text-lg">No Account Selected</h3>
                <p className="text-sm text-muted-foreground mt-1">Please select an AdsPower profile and Ad Account from the top bar to view campaigns.</p>
              </div>
            ) : isLoading ? (
              <div className="p-4 space-y-4">
                <div className="flex items-center justify-between border-b pb-4">
                  <Skeleton className="h-4 w-[250px]" />
                  <Skeleton className="h-4 w-[100px]" />
                  <Skeleton className="h-4 w-[100px]" />
                  <Skeleton className="h-4 w-[100px]" />
                </div>
                {[...Array(8)].map((_, i) => (
                  <div key={i} className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-4">
                      <Skeleton className="h-8 w-8 rounded-full" />
                      <div className="space-y-2">
                        <Skeleton className="h-4 w-[200px]" />
                        <Skeleton className="h-3 w-[150px]" />
                      </div>
                    </div>
                    <Skeleton className="h-4 w-[80px]" />
                    <Skeleton className="h-4 w-[80px]" />
                    <Skeleton className="h-4 w-[80px]" />
                  </div>
                ))}
              </div>
            ) : isError ? (
               <div className="flex flex-col items-center justify-center h-64 text-center p-6 text-destructive">
                <h3 className="font-medium text-lg">Failed to load campaigns</h3>
                <p className="text-sm mt-1">{(error as Error).message}</p>
              </div>
            ) : (
              <DataTable 
                columns={columns} 
                data={campaignsData?.campaigns || []} 
                onRowClick={setSelectedCampaign}
                selectedRowId={selectedCampaign?.campaign_id}
                getRowId={(row) => row.campaign_id}
              />
            )}
          </CardContent>
        </Card>

        {/* Detail Panel */}
        <Card className="w-[400px] flex flex-col hidden xl:flex min-h-0">
          <CardHeader className="border-b">
            <CardTitle className="text-sm font-medium">Campaign Details</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 p-0 overflow-y-auto">
            {!selectedCampaign ? (
              <div className="p-6 flex flex-col items-center justify-center text-center h-full">
                <div className="mx-auto rounded-full bg-muted p-4 w-16 h-16 flex items-center justify-center mb-4">
                  <Filter className="h-8 w-8 text-muted-foreground" />
                </div>
                <h3 className="font-semibold text-lg">No Campaign Selected</h3>
                <p className="text-sm text-muted-foreground mt-2">
                  Select a campaign from the list to view its full details, metrics, and performance history.
                </p>
              </div>
            ) : (
              <div className="p-6 space-y-6">
                <div>
                  <h3 className="font-semibold text-lg leading-tight">{selectedCampaign.campaign_name}</h3>
                  <div className="flex items-center gap-2 mt-2">
                    <StatusBadge status={selectedCampaign.effective_status.toLowerCase() as any} />
                    <span className="text-xs text-muted-foreground">ID: {selectedCampaign.campaign_id}</span>
                  </div>
                  <div className="mt-4">
                     <Button
                        variant={selectedCampaign.effective_status === "ACTIVE" ? "destructive" : "default"}
                        size="sm"
                        className="h-8 text-xs w-full"
                        onClick={() => handleToggleStatus(selectedCampaign.campaign_id, selectedCampaign.effective_status)}
                        disabled={updateStatusMutation.isPending}
                      >
                        {selectedCampaign.effective_status === "ACTIVE" ? <Pause className="h-4 w-4 mr-2" /> : <Play className="h-4 w-4 mr-2" />}
                        {selectedCampaign.effective_status === "ACTIVE" ? "Pause Campaign" : "Activate Campaign"}
                      </Button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground">Objective</span>
                    <p className="text-sm font-medium break-all">{selectedCampaign.objective || "—"}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground">Budget Type</span>
                    <p className="text-sm font-medium">{selectedCampaign.budget_type}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground">Lifetime Budget</span>
                    <p className="text-sm font-medium">{selectedCampaign.lifetime_budget ? formatCurrency(selectedCampaign.lifetime_budget) : "—"}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground">Daily Budget</span>
                    <p className="text-sm font-medium">{selectedCampaign.daily_budget ? formatCurrency(selectedCampaign.daily_budget) : "—"}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground">Bid Strategy</span>
                    <p className="text-sm font-medium break-all">{selectedCampaign.bid_strategy || "—"}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground">Learning Status</span>
                    <p className="text-sm font-medium">{selectedCampaign.learning_status || "—"}</p>
                  </div>
                </div>

                <div className="space-y-3">
                  <h4 className="text-sm font-medium border-b pb-2">Performance (Last 30d)</h4>
                  <div className="grid grid-cols-3 gap-y-6 gap-x-4">
                    <div className="space-y-1 bg-muted/20 p-2 rounded-lg border border-border/50">
                      <span className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">Spend</span>
                      <p className="text-lg font-bold">{formatCurrency(selectedCampaign.insights?.spend || 0)}</p>
                    </div>
                    <div className="space-y-1 bg-muted/20 p-2 rounded-lg border border-border/50">
                      <span className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">ROAS</span>
                      <p className="text-lg font-bold text-emerald-500">{((selectedCampaign.insights?.roas) || 0).toFixed(2)}x</p>
                    </div>
                    <div className="space-y-1 bg-muted/20 p-2 rounded-lg border border-border/50">
                      <span className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">Purchases</span>
                      <p className="text-lg font-bold">{selectedCampaign.insights?.purchases || 0}</p>
                    </div>
                    
                    <div className="space-y-1">
                      <span className="text-xs text-muted-foreground">CTR</span>
                      <p className="text-sm font-medium">{formatPct(selectedCampaign.insights?.ctr || 0)}</p>
                    </div>
                    <div className="space-y-1">
                      <span className="text-xs text-muted-foreground">CPC</span>
                      <p className="text-sm font-medium">{formatCurrency(selectedCampaign.insights?.cpc || 0)}</p>
                    </div>
                    <div className="space-y-1">
                      <span className="text-xs text-muted-foreground">CPM</span>
                      <p className="text-sm font-medium">{formatCurrency(selectedCampaign.insights?.cpm || 0)}</p>
                    </div>

                    <div className="space-y-1">
                      <span className="text-xs text-muted-foreground">Impressions</span>
                      <p className="text-sm font-medium">{selectedCampaign.insights?.impressions?.toLocaleString() || 0}</p>
                    </div>
                    <div className="space-y-1">
                      <span className="text-xs text-muted-foreground">Reach</span>
                      <p className="text-sm font-medium">{selectedCampaign.insights?.reach?.toLocaleString() || 0}</p>
                    </div>
                    <div className="space-y-1">
                      <span className="text-xs text-muted-foreground">Clicks</span>
                      <p className="text-sm font-medium">{selectedCampaign.insights?.clicks?.toLocaleString() || 0}</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
