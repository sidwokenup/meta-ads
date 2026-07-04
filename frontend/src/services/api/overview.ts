import { useQuery, useQueries } from "@tanstack/react-query";
import { getAccountReport } from "./client";

export const useAccountReport = (profileId: string | null, accountId: string | null, datePreset: string = "last_30d") => {
  return useQuery({
    queryKey: ["accountReport", profileId, accountId, datePreset],
    queryFn: () => getAccountReport(profileId!, accountId!, datePreset),
    enabled: !!profileId && !!accountId,
    retry: false,
    refetchInterval: 30000,
  });
};

export const useGlobalReport = (accounts: { profileId: string; accountId: string }[], datePreset: string = "last_30d") => {
  return useQueries({
    queries: accounts.map((account) => ({
      queryKey: ["accountReport", account.profileId, account.accountId, datePreset],
      queryFn: () => getAccountReport(account.profileId, account.accountId, datePreset),
      enabled: !!account.profileId && !!account.accountId,
      retry: false,
      refetchInterval: 30000,
    })),
  });
};
