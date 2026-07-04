import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getBrowsers,
  createBrowser,
  updateBrowser,
  deleteBrowser,
  checkBrowserStatus,
  BrowserProfile,
} from "./client";

export const useBrowsers = () => {
  return useQuery({
    queryKey: ["browsers"],
    queryFn: getBrowsers,
  });
};

export const useCreateBrowser = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createBrowser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["browsers"] });
    },
  });
};

export const useUpdateBrowser = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<BrowserProfile> }) =>
      updateBrowser(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["browsers"] });
    },
  });
};

export const useDeleteBrowser = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteBrowser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["browsers"] });
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
    },
  });
};

export const useBrowserStatus = (profileId: string) => {
  return useQuery({
    queryKey: ["browserStatus", profileId],
    queryFn: () => checkBrowserStatus(profileId),
    enabled: !!profileId,
    refetchInterval: 30000, // check every 30s
  });
};
