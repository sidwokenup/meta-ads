"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Settings2, Trash2, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { StatusBadge } from "@/components/ui/status-badge";
import { BrowserProfile } from "@/services/api/client";
import { useBrowserStatus } from "@/services/api/browser";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface BrowserCardProps {
  browser: BrowserProfile;
  accountsCount: number;
  onEdit: (b: BrowserProfile) => void;
  onDelete: (b: BrowserProfile) => void;
  children?: React.ReactNode; // For the expanded accounts list
}

export function BrowserCard({ browser, accountsCount, onEdit, onDelete, children }: BrowserCardProps) {
  const { data, isLoading, isError, error, refetch, isFetching } = useBrowserStatus(browser.profileId);
  const [isExpanded, setIsExpanded] = useState(false);

  let status: string = "unknown";
  if (isLoading) status = "syncing";
  else if (isError) status = "error";
  else if (data?.browser === "connected") status = "connected";
  else if (data?.browser === "disconnected") status = "disconnected";

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="truncate pr-2" title={browser.name}>{browser.name}</CardTitle>
          <StatusBadge status={isFetching ? "syncing" : (status as "connected" | "disconnected" | "syncing" | "offline" | "error" | "active" | "unknown")} />
        </div>
        <CardDescription className="flex justify-between items-center">
          <span>ID: {browser.profileId}</span>
          {isError && <span className="text-xs text-destructive max-w-[120px] truncate" title={(error as Error).message}>{(error as Error).message}</span>}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Accounts</span>
            <span className="font-medium">{accountsCount}</span>
          </div>
          {browser.description && (
            <div className="flex flex-col mt-2">
              <span className="text-xs text-muted-foreground">Notes</span>
              <span className="text-xs truncate">{browser.description}</span>
            </div>
          )}
        </div>
      </CardContent>
      <CardFooter className="flex flex-col gap-0 p-0">
        <div className="flex w-full justify-between gap-2 border-t bg-muted/5 px-6 py-4">
          <div className="flex gap-2">
            <Button variant="outline" size="icon" onClick={() => onEdit(browser)}>
              <Settings2 className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
            </Button>
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => setIsExpanded(!isExpanded)}>
              {isExpanded ? <ChevronUp className="h-4 w-4 mr-1" /> : <ChevronDown className="h-4 w-4 mr-1" />}
              {isExpanded ? "Hide" : "View"} Accounts
            </Button>
            <Button variant="destructive" size="icon" onClick={() => onDelete(browser)}>
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
        
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="w-full overflow-hidden border-t bg-muted/10"
            >
              <div className="p-4 space-y-3">
                {children}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </CardFooter>
    </Card>
  );
}
