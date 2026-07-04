"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { useBrowsers } from "@/services/api/browser";
import { useAccounts, useCreateAccount, useUpdateAccount, useDeleteAccount } from "@/services/api/accounts";
import { AccountCard } from "@/components/cards/account-card";
import { AccountDialog } from "@/components/dialogs/account-dialog";
import { DeleteDialog } from "@/components/dialogs/delete-dialog";
import { AdAccount } from "@/services/api/client";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";

export default function AccountsPage() {
  const { data: browsers, isLoading: loadingBrowsers } = useBrowsers();
  const { data: accounts, isLoading: loadingAccounts } = useAccounts();

  const createAccount = useCreateAccount();
  const updateAccount = useUpdateAccount();
  const deleteAccount = useDeleteAccount();

  // Dialog States
  const [isAccountDialogOpen, setAccountDialogOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<AdAccount | null>(null);

  const [isDeleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingItem, setDeletingItem] = useState<AdAccount | null>(null);

  // Handlers for Account
  const handleSaveAccount = (data: Omit<AdAccount, "id" | "createdAt">) => {
    if (editingAccount) {
      updateAccount.mutate({ id: editingAccount.id, data }, {
        onSuccess: () => {
          toast.success("Account updated successfully");
          setAccountDialogOpen(false);
        },
        onError: (err) => toast.error(err.message)
      });
    } else {
      createAccount.mutate(data, {
        onSuccess: () => {
          toast.success("Account added successfully");
          setAccountDialogOpen(false);
        },
        onError: (err) => toast.error(err.message)
      });
    }
  };

  const confirmDeleteAccount = (account: AdAccount) => {
    setDeletingItem(account);
    setDeleteDialogOpen(true);
  };

  // General Delete Handler
  const handleDelete = () => {
    if (!deletingItem) return;
    deleteAccount.mutate(deletingItem.id, {
      onSuccess: () => {
        toast.success("Account deleted");
        setDeleteDialogOpen(false);
      }
    });
  };

  const isLoading = loadingBrowsers || loadingAccounts;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Ad Accounts</h1>
          <p className="text-muted-foreground mt-2">Manage linked Facebook Ad Accounts across all profiles.</p>
        </div>
        <Button onClick={() => { setEditingAccount(null); setAccountDialogOpen(true); }}>
          <Plus className="mr-2 h-4 w-4" /> Add Account
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3 items-start">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex flex-col space-y-3">
              <Skeleton className="h-[200px] w-full rounded-xl" />
            </div>
          ))
        ) : accounts?.length === 0 ? (
          <div className="col-span-full flex flex-col items-center justify-center p-12 border-2 border-dashed rounded-xl bg-background/50">
            <div className="rounded-full bg-muted p-4 mb-4">
              <Plus className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="font-semibold text-lg">No Accounts Found</h3>
            <p className="text-muted-foreground mt-1 max-w-sm text-center">
              Link your first Facebook Ad Account to a browser profile to get started.
            </p>
            <Button className="mt-6" onClick={() => { setEditingAccount(null); setAccountDialogOpen(true); }}>
              Add Ad Account
            </Button>
          </div>
        ) : (
          accounts?.map((account) => {
            const browser = browsers?.find((b) => b.id === account.browserId);
            return (
              <AccountCard
                key={account.id}
                account={account}
                browser={browser}
                onEdit={(a) => { setEditingAccount(a); setAccountDialogOpen(true); }}
                onDelete={confirmDeleteAccount}
              />
            );
          })
        )}
      </div>

      <AccountDialog
        isOpen={isAccountDialogOpen}
        onOpenChange={setAccountDialogOpen}
        onSubmit={handleSaveAccount}
        initialData={editingAccount}
        browsers={browsers || []}
        isSaving={createAccount.isPending || updateAccount.isPending}
      />

      <DeleteDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={handleDelete}
        title="Delete Account"
        description={`Are you sure you want to delete "${deletingItem?.nickname}"? This action cannot be undone.`}
        isDeleting={deleteAccount.isPending}
      />
    </div>
  );
}
