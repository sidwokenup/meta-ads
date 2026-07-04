"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Settings2, Trash2, RefreshCw, Building2 } from "lucide-react";
import { StatusBadge } from "@/components/ui/status-badge";
import { AdAccount, BrowserProfile } from "@/services/api/client";
import { useAccountStatus } from "@/services/api/accounts";

interface AccountCardProps {
  account: AdAccount;
  browser?: BrowserProfile;
  onEdit: (a: AdAccount) => void;
  onDelete: (a: AdAccount) => void;
  compact?: boolean;
}

export function AccountCard({ account, browser, onEdit, onDelete, compact = false }: AccountCardProps) {
  // If browser is provided, we can check status. If not (e.g. inside BrowserCard where we already know browser), we might skip or still check.
  const { data, isLoading, isError, error, refetch, isFetching } = useAccountStatus(browser?.profileId, account.accountId);

  let status: string = "unknown";
  if (!browser?.profileId) status = "offline";
  else if (isLoading) status = "syncing";
  else if (isError) {
    const msg = (error as Error).message;
    if (msg.includes("Expired")) status = "disconnected";
    else if (msg.includes("Closed")) status = "offline";
    else status = "error";
  }
  else if (data?.account_status === 1) status = "active";
  else if (data?.account_status === 2) status = "error"; // Disabled
  else status = "connected";

  if (compact) {
    return (
      <div className="flex items-center justify-between p-3 bg-background border rounded-lg shadow-sm">
        <div className="flex items-center gap-3 overflow-hidden">
          <Building2 className="h-4 w-4 text-muted-foreground shrink-0" />
          <div className="flex flex-col overflow-hidden">
            <span className="text-sm font-medium truncate" title={account.nickname}>{account.nickname}</span>
            <span className="text-xs text-muted-foreground truncate">{account.accountId}</span>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <StatusBadge status={isFetching ? "syncing" : (status as any)} className="hidden sm:flex" />
          <div className="flex gap-1">
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} />
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => onEdit(account)}>
              <Settings2 className="h-3 w-3" />
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" onClick={() => onDelete(account)}>
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2 overflow-hidden pr-2">
            <Building2 className="h-4 w-4 text-primary shrink-0" />
            <CardTitle className="truncate" title={account.nickname}>{account.nickname}</CardTitle>
          </div>
          <StatusBadge status={isFetching ? "syncing" : (status as any)} />
        </div>
        <CardDescription>ID: {account.accountId}</CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        <div className="space-y-2 text-sm">
          {browser && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Browser Profile</span>
              <span className="font-medium text-primary truncate max-w-[150px]" title={browser.name}>{browser.name}</span>
            </div>
          )}
          {data && (
            <>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Currency</span>
                <span className="font-medium">{data.currency}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Campaigns</span>
                <span className="font-medium">{data.total_campaigns}</span>
              </div>
            </>
          )}
          {isError && (
             <div className="flex flex-col mt-2">
               <span className="text-xs text-destructive">{(error as Error).message}</span>
             </div>
          )}
          {!browser && (
             <div className="flex flex-col mt-2">
               <span className="text-xs text-destructive">Browser profile not found</span>
             </div>
          )}
        </div>
      </CardContent>
      <CardFooter className="flex justify-between gap-2 border-t bg-muted/5 px-6 py-4">
        <div className="flex gap-2">
          <Button variant="outline" size="icon" onClick={() => onEdit(account)}>
            <Settings2 className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
        </div>
        <Button variant="destructive" size="icon" onClick={() => onDelete(account)}>
          <Trash2 className="h-4 w-4" />
        </Button>
      </CardFooter>
    </Card>
  );
}
