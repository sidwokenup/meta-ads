import { useEffect, useRef } from "react";
import { toast } from "sonner";

type CampaignInsights = {
  spend: number;
  roas: number;
  purchases: number;
};

type Campaign = {
  campaign_id: string;
  campaign_name: string;
  effective_status: string;
  insights?: CampaignInsights;
};

export function useCampaignAlerts(
  accountName: string,
  campaigns: Campaign[] | undefined
) {
  const previousCampaignsRef = useRef<Record<string, Campaign>>({});

  useEffect(() => {
    if (!campaigns || campaigns.length === 0) return;

    const currentCampaignsMap = campaigns.reduce((acc, c) => {
      acc[c.campaign_id] = c;
      return acc;
    }, {} as Record<string, Campaign>);

    const previousCampaignsMap = previousCampaignsRef.current;

    // Only alert if we actually had previous data (don't alert on initial load)
    if (Object.keys(previousCampaignsMap).length > 0) {
      campaigns.forEach((current) => {
        const prev = previousCampaignsMap[current.campaign_id];
        
        if (prev) {
          // Check for status change
          if (prev.effective_status !== current.effective_status) {
            toast.info(`Status Changed: ${current.campaign_name}`, {
              description: `Status changed from ${prev.effective_status} to ${current.effective_status} in ${accountName}`,
            });
          }

          // Check for spend increase
          const currentSpend = current.insights?.spend || 0;
          const prevSpend = prev.insights?.spend || 0;
          
          if (currentSpend > prevSpend) {
            const diff = currentSpend - prevSpend;
            toast.success(`Spend Detected: ${current.campaign_name}`, {
              description: `Spent an additional $${diff.toFixed(2)} in ${accountName}`,
            });
          }

          // Check for new purchases
          const currentPurchases = current.insights?.purchases || 0;
          const prevPurchases = prev.insights?.purchases || 0;

          if (currentPurchases > prevPurchases) {
            const diff = currentPurchases - prevPurchases;
            toast.success(`🎉 New Purchase!`, {
              description: `${current.campaign_name} got ${diff} new purchase(s) in ${accountName}`,
              duration: 8000,
            });
          }
        }
      });
    }

    // Update the ref for the next cycle
    previousCampaignsRef.current = currentCampaignsMap;
  }, [campaigns, accountName]);
}
