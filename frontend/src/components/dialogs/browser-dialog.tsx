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
import { BrowserProfile } from "@/services/api/client";

const browserSchema = z.object({
  name: z.string().min(1, "Browser Name is required"),
  profileId: z.string().min(1, "AdsPower Profile ID is required"),
  apiUrl: z.string().url("Must be a valid URL (e.g. https://api1.yourdomain.com)").optional().or(z.literal("")),
  description: z.string().optional(),
});

type BrowserFormValues = z.infer<typeof browserSchema>;

interface BrowserDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: BrowserFormValues) => void;
  initialData?: BrowserProfile | null;
  isSaving?: boolean;
}

export function BrowserDialog({
  isOpen,
  onOpenChange,
  onSubmit,
  initialData,
  isSaving,
}: BrowserDialogProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<BrowserFormValues>({
    resolver: zodResolver(browserSchema),
    defaultValues: {
      name: "",
      profileId: "",
      apiUrl: "",
      description: "",
    },
  });

  useEffect(() => {
    if (isOpen) {
      if (initialData) {
        reset({
          name: initialData.name,
          profileId: initialData.profileId,
          apiUrl: initialData.apiUrl || "",
          description: initialData.description || "",
        });
      } else {
        reset({ name: "", profileId: "", apiUrl: "", description: "" });
      }
    }
  }, [isOpen, initialData, reset]);

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{initialData ? "Edit Browser Profile" : "Add Browser Profile"}</DialogTitle>
          <DialogDescription>
            Connect an AdsPower browser profile to the dashboard.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Browser Name</label>
            <Input placeholder="e.g., US Main Browser" {...register("name")} disabled={isSaving} />
            {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">AdsPower Profile ID</label>
            <Input placeholder="e.g., k1dvlyr0" {...register("profileId")} disabled={isSaving} />
            {errors.profileId && <p className="text-xs text-destructive">{errors.profileId.message}</p>}
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">API Tunnel URL (Optional)</label>
            <Input placeholder="e.g., https://api1.yourdomain.com" {...register("apiUrl")} disabled={isSaving} />
            <p className="text-[10px] text-muted-foreground">Leave blank to use the default FastAPI server.</p>
            {errors.apiUrl && <p className="text-xs text-destructive">{errors.apiUrl.message}</p>}
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
              {isSaving ? "Saving..." : "Save Profile"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
