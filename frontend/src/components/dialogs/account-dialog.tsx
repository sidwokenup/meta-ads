"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useEffect } from "react";
import { AdAccount, BrowserProfile } from "@/services/api/client";

const accountSchema = z.object({
  nickname: z.string().min(1, "Nickname is required"),
  accountId: z.string().min(1, "Ad Account ID is required"),
  browserId: z.string().min(1, "Browser Profile is required"),
  description: z.string().optional(),
});

type AccountFormValues = z.infer<typeof accountSchema>;

interface AccountDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: AccountFormValues) => void;
  initialData?: AdAccount | null;
  browsers: BrowserProfile[];
  isSaving?: boolean;
}

export function AccountDialog({
  isOpen,
  onOpenChange,
  onSubmit,
  initialData,
  browsers,
  isSaving,
}: AccountDialogProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AccountFormValues>({
    resolver: zodResolver(accountSchema),
    defaultValues: {
      nickname: "",
      accountId: "",
      browserId: "",
      description: "",
    },
  });

  useEffect(() => {
    if (isOpen) {
      if (initialData) {
        reset({
          nickname: initialData.nickname,
          accountId: initialData.accountId,
          browserId: initialData.browserId,
          description: initialData.description || "",
        });
      } else {
        reset({ nickname: "", accountId: "", browserId: browsers.length > 0 ? browsers[0].id : "", description: "" });
      }
    }
  }, [isOpen, initialData, reset, browsers]);

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{initialData ? "Edit Ad Account" : "Add Ad Account"}</DialogTitle>
          <DialogDescription>
            Link a Facebook Ad Account to a browser profile.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Nickname</label>
            <Input placeholder="e.g., Australia Store" {...register("nickname")} disabled={isSaving} />
            {errors.nickname && <p className="text-xs text-destructive">{errors.nickname.message}</p>}
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Ad Account ID</label>
            <Input placeholder="e.g., 1559140139101704" {...register("accountId")} disabled={isSaving} />
            {errors.accountId && <p className="text-xs text-destructive">{errors.accountId.message}</p>}
          </div>
          <div className="space-y-2 flex flex-col">
            <label className="text-sm font-medium">Assign to Browser</label>
            <select
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"
              {...register("browserId")}
              disabled={isSaving}
            >
              <option value="" disabled>Select a browser</option>
              {browsers.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} ({b.profileId})
                </option>
              ))}
            </select>
            {errors.browserId && <p className="text-xs text-destructive">{errors.browserId.message}</p>}
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Description (Optional)</label>
            <Input placeholder="Internal notes..." {...register("description")} disabled={isSaving} />
          </div>
          <DialogFooter className="mt-6">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? "Saving..." : "Save Account"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
