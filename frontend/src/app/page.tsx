"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DollarSign, MousePointerClick, Target, Activity, Users, Building2, PlayCircle, PauseCircle, Globe } from "lucide-react";
import { useBrowsers } from "@/services/api/browser";
import { useAccounts } from "@/services/api/accounts";
import { useGlobalReport } from "@/services/api/overview";
import { Skeleton } from "@/components/ui/skeleton";
import { AccountLiveView } from "@/components/cards/account-live-view";

export default function OverviewPage() {
  const { data: browsers, isLoading: loadingBrowsers } = useBrowsers();
  const { data: accounts, isLoading: loadingAccounts } = useAccounts();

  // Create pairs for the global report query
  const queryPairs = (accounts || []).map(acc => {
    const browser = browsers?.find(b => b.id === acc.browserId);
    return { profileId: browser?.profileId || "", accountId: acc.accountId };
  }).filter(p => p.profileId && p.accountId);

  const globalQueries = useGlobalReport(queryPairs);

  const isLoading = loadingBrowsers || loadingAccounts;
  
  // Calculate Global Stats
  const globalStats = globalQueries.reduce((acc, query) => {
    if (query.data) {
      acc.totalSpend += query.data.total_spend || 0;
      acc.totalPurchases += query.data.total_purchases || 0;
      acc.totalRevenue += query.data.total_purchase_value || 0;
      acc.activeCampaigns += query.data.active_campaigns || 0;
    }
    return acc;
  }, { totalSpend: 0, totalPurchases: 0, totalRevenue: 0, activeCampaigns: 0 });

  const globalRoas = globalStats.totalSpend > 0 ? (globalStats.totalRevenue / globalStats.totalSpend) : 0;
  const isGlobalLoading = globalQueries.some(q => q.isLoading);

  const formatCurrency = (val: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Operations Center</h1>
        <p className="text-muted-foreground mt-2">Live, real-time data strictly segmented by browser and ad account.</p>
      </div>

      {/* GLOBAL GOD VIEW */}
      <Card className="bg-primary/5 border-primary/20 shadow-md">
        <CardHeader className="pb-2 border-b border-primary/10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Globe className="h-5 w-5 text-primary" />
              <CardTitle className="text-lg font-bold text-primary">Global God View</CardTitle>
            </div>
            <div className="text-xs font-medium bg-primary/10 text-primary px-2 py-1 rounded-full">
              Across {queryPairs.length} active account(s)
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Total Spend (30d)</span>
              {isGlobalLoading ? <Skeleton className="h-7 w-24" /> : (
                <p className="text-2xl font-black">{formatCurrency(globalStats.totalSpend)}</p>
              )}
            </div>
            <div className="space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Blended ROAS</span>
              {isGlobalLoading ? <Skeleton className="h-7 w-20" /> : (
                <p className="text-2xl font-black text-emerald-500">{globalRoas.toFixed(2)}x</p>
              )}
            </div>
            <div className="space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Total Purchases</span>
              {isGlobalLoading ? <Skeleton className="h-7 w-16" /> : (
                <p className="text-2xl font-black">{globalStats.totalPurchases}</p>
              )}
            </div>
            <div className="space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Active Campaigns</span>
              {isGlobalLoading ? <Skeleton className="h-7 w-16" /> : (
                <p className="text-2xl font-black text-blue-500">{globalStats.activeCampaigns}</p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Browser Profiles</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-8 w-12" /> : (
              <div className="text-2xl font-bold">{browsers?.length || 0}</div>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Ad Accounts</CardTitle>
            <Building2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-8 w-12" /> : (
              <div className="text-2xl font-bold">{accounts?.length || 0}</div>
            )}
          </CardContent>
        </Card>
      </div>

      {isLoading ? (
        <div className="space-y-6">
          <Skeleton className="h-[400px] w-full rounded-xl" />
          <Skeleton className="h-[400px] w-full rounded-xl" />
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {browsers?.map(browser => {
            const browserAccounts = accounts?.filter(a => a.browserId === browser.id) || [];
            
            return (
              <div key={browser.id} className="space-y-4">
                <div className="flex items-center gap-3 border-b pb-2">
                  <div className="bg-primary/10 text-primary p-2 rounded-md">
                    <Users className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold">{browser.name}</h2>
                    <p className="text-sm text-muted-foreground">ID: {browser.profileId}</p>
                  </div>
                </div>

                {browserAccounts.length === 0 ? (
                  <Card className="border-dashed">
                    <CardContent className="p-6 text-center text-muted-foreground">
                      No accounts assigned to this browser.
                    </CardContent>
                  </Card>
                ) : (
                  <div className="grid gap-6">
                    {browserAccounts.map(account => (
                      <AccountLiveView 
                        key={account.id} 
                        profileId={browser.profileId} 
                        accountId={account.accountId} 
                        nickname={account.nickname} 
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}