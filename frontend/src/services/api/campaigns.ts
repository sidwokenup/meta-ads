import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getCampaigns, updateCampaignStatus } from "./client";

export const useCampaignsList = (profileId: string | null, accountId: string | null, datePreset: string = "last_30d") => {
  return useQuery({
    queryKey: ["campaigns", profileId, accountId, datePreset],
    queryFn: () => getCampaigns(profileId!, accountId!, datePreset),
    enabled: !!profileId && !!accountId,
    retry: false,
    refetchInterval: 60000,
  });
};

export const useUpdateCampaignStatus = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ profileId, accountId, campaignId, status }: { profileId: string, accountId: string, campaignId: string, status: "ACTIVE" | "PAUSED" }) => {
      return updateCampaignStatus(profileId, accountId, campaignId, status);
    },
    onSuccess: (_, variables) => {
      // Invalidate and refetch campaigns
      queryClient.invalidateQueries({ queryKey: ["campaigns", variables.profileId, variables.accountId] });
      queryClient.invalidateQueries({ queryKey: ["accountReport", variables.profileId, variables.accountId] });
    },
  });
};
