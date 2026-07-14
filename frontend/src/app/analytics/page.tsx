"use client";

import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Trophy, TrendingUp, DollarSign, Target, MousePointerClick, Filter, Building2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useCampaignsList } from "@/services/api/campaigns";
import { useAccountReport } from "@/services/api/overview";
import { useBrowsers } from "@/services/api/browser";
import { useAccounts } from "@/services/api/accounts";
import { useSessionStore } from "@/store/ui-store";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusBadge } from "@/components/ui/status-badge";

export default function AnalyticsPage() {
  const { activeProfileId, activeAccountId, setActiveProfile, setActiveAccount } = useSessionStore();
  const [datePreset, setDatePreset] = useState("today");

  const { data: browsers } = useBrowsers();
  const { data: accounts } = useAccounts();

  const { data: summaryData, isLoading: isSummaryLoading } = useAccountReport(activeProfileId, activeAccountId, datePreset);
  const { data: campaignsData, isLoading: isCampaignsLoading } = useCampaignsList(activeProfileId, activeAccountId, datePreset);

  const formatCurrency = (val: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
  const formatPct = (val: number) => `${val.toFixed(2)}%`;

  const handleAccountChange = (accountId: string | null) => {
    if (!accountId) return;
    const account = accounts?.find(a => a.accountId === accountId);
    if (account) {
      const browser = browsers?.find(b => b.id === account.browserId);
      if (browser) {
        setActiveProfile(browser.profileId);
        setActiveAccount(account.accountId);
      }
    }
  };

  const topSpendingCampaign = useMemo(() => {
    if (!campaignsData?.campaigns?.length) return null;
    return [...campaignsData.campaigns].sort((a, b) => (b.insights?.spend || 0) - (a.insights?.spend || 0))[0];
  }, [campaignsData]);

  const topRoasCampaign = useMemo(() => {
    if (!campaignsData?.campaigns?.length) return null;
    return [...campaignsData.campaigns]
      .filter(c => (c.insights?.spend || 0) > 0)
      .sort((a, b) => (b.insights?.roas || 0) - (a.insights?.roas || 0))[0];
  }, [campaignsData]);

  const isLoading = isSummaryLoading || isCampaignsLoading;

  return (
    <div className="flex flex-col gap-6 h-full overflow-y-auto pb-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Daily Dashboard</h1>
          <p className="text-muted-foreground mt-2">Analyze specific days or weeks to find top performers.</p>
        </div>
        
        <div className="flex items-center gap-3">
          <Select value={activeAccountId || undefined} onValueChange={handleAccountChange}>
            <SelectTrigger className="w-[260px] bg-background">
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

          <Select value={datePreset} onValueChange={(val) => setDatePreset(val || "today")}>
            <SelectTrigger className="w-[180px] bg-background font-medium">
              <SelectValue placeholder="Select Date" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectLabel>Daily</SelectLabel>
                <SelectItem value="today">Today</SelectItem>
                <SelectItem value="yesterday">Yesterday</SelectItem>
              </SelectGroup>
              <SelectGroup>
                <SelectLabel>Weekly & Monthly</SelectLabel>
                <SelectItem value="last_7d">Last 7 Days</SelectItem>
                <SelectItem value="last_30d">Last 30 Days</SelectItem>
                <SelectItem value="this_month">This Month</SelectItem>
                <SelectItem value="last_month">Last Month</SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
        </div>
      </div>

      {!activeProfileId || !activeAccountId ? (
        <Card className="flex-1 flex items-center justify-center border-dashed border-2 bg-transparent min-h-[400px]">
          <div className="text-center space-y-4">
            <div className="mx-auto rounded-full bg-muted p-4 w-16 h-16 flex items-center justify-center">
              <Filter className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="font-semibold text-lg">No Account Selected</h3>
            <p className="text-sm text-muted-foreground max-w-[300px] mx-auto">
              Please select an AdsPower profile and Ad Account to view the daily dashboard.
            </p>
          </div>
        </Card>
      ) : isLoading ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-32 rounded-xl" />)}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Skeleton className="h-64 rounded-xl" />
            <Skeleton className="h-64 rounded-xl" />
          </div>
        </div>
      ) : (
        <>
          {/* Top Level Summary Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-sm font-medium">Total Spend</CardTitle>
                <DollarSign className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{formatCurrency(summaryData?.total_spend || 0)}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-sm font-medium">Purchases</CardTitle>
                <Target className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{summaryData?.total_purchases || 0}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  Value: {formatCurrency(summaryData?.total_purchase_value || 0)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-sm font-medium">Avg ROAS</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-emerald-500">{(summaryData?.avg_roas || 0).toFixed(2)}x</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-sm font-medium">Avg CTR</CardTitle>
                <MousePointerClick className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{formatPct(summaryData?.avg_ctr || 0)}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  Clicks: {summaryData?.total_clicks || 0}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Top Performers Highlights */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top Spender */}
            <Card className="border-primary/20 bg-primary/5">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-primary">
                  <Trophy className="h-5 w-5 text-amber-500" />
                  Highest Spending Campaign
                </CardTitle>
                <CardDescription>The campaign consuming the most budget in this period.</CardDescription>
              </CardHeader>
              <CardContent>
                {topSpendingCampaign ? (
                  <div className="space-y-4">
                    <div>
                      <h3 className="font-semibold text-lg line-clamp-2">{topSpendingCampaign.campaign_name}</h3>
                      <div className="flex items-center gap-2 mt-2">
                        <StatusBadge status={topSpendingCampaign.effective_status.toLowerCase() as any} />
                        <span className="text-xs text-muted-foreground">{topSpendingCampaign.campaign_id}</span>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4 bg-background/50 p-4 rounded-lg">
                      <div>
                        <span className="text-xs text-muted-foreground uppercase font-semibold">Spend</span>
                        <p className="text-xl font-bold text-rose-500">{formatCurrency(topSpendingCampaign.insights?.spend || 0)}</p>
                      </div>
                      <div>
                        <span className="text-xs text-muted-foreground uppercase font-semibold">Purchases</span>
                        <p className="text-xl font-bold">{topSpendingCampaign.insights?.purchases || 0}</p>
                      </div>
                      <div>
                        <span className="text-xs text-muted-foreground uppercase font-semibold">ROAS</span>
                        <p className="text-lg font-medium">{((topSpendingCampaign.insights?.roas) || 0).toFixed(2)}x</p>
                      </div>
                      <div>
                        <span className="text-xs text-muted-foreground uppercase font-semibold">CPC</span>
                        <p className="text-lg font-medium">{formatCurrency(topSpendingCampaign.insights?.cpc || 0)}</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-muted-foreground py-8 text-center">No spend data available for this period.</div>
                )}
              </CardContent>
            </Card>

            {/* Top ROAS */}
            <Card className="border-emerald-500/20 bg-emerald-500/5">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-emerald-500">
                  <TrendingUp className="h-5 w-5" />
                  Most Profitable Campaign (ROAS)
                </CardTitle>
                <CardDescription>The campaign generating the best return on ad spend.</CardDescription>
              </CardHeader>
              <CardContent>
                {topRoasCampaign && (topRoasCampaign.insights?.roas || 0) > 0 ? (
                  <div className="space-y-4">
                    <div>
                      <h3 className="font-semibold text-lg line-clamp-2">{topRoasCampaign.campaign_name}</h3>
                      <div className="flex items-center gap-2 mt-2">
                        <StatusBadge status={topRoasCampaign.effective_status.toLowerCase() as any} />
                        <span className="text-xs text-muted-foreground">{topRoasCampaign.campaign_id}</span>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4 bg-background/50 p-4 rounded-lg">
                      <div>
                        <span className="text-xs text-muted-foreground uppercase font-semibold">ROAS</span>
                        <p className="text-xl font-bold text-emerald-600">{((topRoasCampaign.insights?.roas) || 0).toFixed(2)}x</p>
                      </div>
                      <div>
                        <span className="text-xs text-muted-foreground uppercase font-semibold">Spend</span>
                        <p className="text-xl font-bold">{formatCurrency(topRoasCampaign.insights?.spend || 0)}</p>
                      </div>
                      <div>
                        <span className="text-xs text-muted-foreground uppercase font-semibold">Purchases</span>
                        <p className="text-lg font-medium">{topRoasCampaign.insights?.purchases || 0}</p>
                      </div>
                      <div>
                        <span className="text-xs text-muted-foreground uppercase font-semibold">Conv. Value</span>
                        <p className="text-lg font-medium">{formatCurrency(topRoasCampaign.insights?.purchase_value || 0)}</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-muted-foreground py-8 text-center">No profitable campaigns found for this period.</div>
                )}
              </CardContent>
            </Card>
          </div>

        </>
      )}
    </div>
  );
}
