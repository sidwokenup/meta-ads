"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { useBrowsers, useCreateBrowser, useUpdateBrowser, useDeleteBrowser } from "@/services/api/browser";
import { useAccounts } from "@/services/api/accounts";
import { BrowserCard } from "@/components/cards/browser-card";
import { AccountCard } from "@/components/cards/account-card";
import { BrowserDialog } from "@/components/dialogs/browser-dialog";
import { AccountDialog } from "@/components/dialogs/account-dialog";
import { DeleteDialog } from "@/components/dialogs/delete-dialog";
import { BrowserProfile, AdAccount } from "@/services/api/client";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { useCreateAccount, useUpdateAccount, useDeleteAccount } from "@/services/api/accounts";

export default function ProfilesPage() {
  const { data: browsers, isLoading: loadingBrowsers } = useBrowsers();
  const { data: accounts, isLoading: loadingAccounts } = useAccounts();

  const createBrowser = useCreateBrowser();
  const updateBrowser = useUpdateBrowser();
  const deleteBrowser = useDeleteBrowser();
  
  const createAccount = useCreateAccount();
  const updateAccount = useUpdateAccount();
  const deleteAccount = useDeleteAccount();

  // Dialog States
  const [isBrowserDialogOpen, setBrowserDialogOpen] = useState(false);
  const [editingBrowser, setEditingBrowser] = useState<BrowserProfile | null>(null);

  const [isAccountDialogOpen, setAccountDialogOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<AdAccount | null>(null);

  const [isDeleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingItem, setDeletingItem] = useState<{ type: 'browser' | 'account', id: string, name: string } | null>(null);

  // Handlers for Browser
  const handleSaveBrowser = (data: Omit<BrowserProfile, "id" | "createdAt">) => {
    if (editingBrowser) {
      updateBrowser.mutate({ id: editingBrowser.id, data }, {
        onSuccess: () => {
          toast.success("Browser updated successfully");
          setBrowserDialogOpen(false);
        },
        onError: (err) => toast.error(err.message)
      });
    } else {
      createBrowser.mutate(data, {
        onSuccess: () => {
          toast.success("Browser created successfully");
          setBrowserDialogOpen(false);
        },
        onError: (err) => toast.error(err.message)
      });
    }
  };

  const confirmDeleteBrowser = (browser: BrowserProfile) => {
    setDeletingItem({ type: 'browser', id: browser.id, name: browser.name });
    setDeleteDialogOpen(true);
  };

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
    setDeletingItem({ type: 'account', id: account.id, name: account.nickname });
    setDeleteDialogOpen(true);
  };

  // General Delete Handler
  const handleDelete = () => {
    if (!deletingItem) return;
    if (deletingItem.type === 'browser') {
      deleteBrowser.mutate(deletingItem.id, {
        onSuccess: () => {
          toast.success("Browser deleted");
          setDeleteDialogOpen(false);
        }
      });
    } else {
      deleteAccount.mutate(deletingItem.id, {
        onSuccess: () => {
          toast.success("Account deleted");
          setDeleteDialogOpen(false);
        }
      });
    }
  };

  const isLoading = loadingBrowsers || loadingAccounts;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Profiles</h1>
          <p className="text-muted-foreground mt-2">Manage AdsPower browser profiles and their linked accounts.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => { setEditingAccount(null); setAccountDialogOpen(true); }}>
            <Plus className="mr-2 h-4 w-4" /> Add Account
          </Button>
          <Button onClick={() => { setEditingBrowser(null); setBrowserDialogOpen(true); }}>
            <Plus className="mr-2 h-4 w-4" /> Add Profile
          </Button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3 items-start">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex flex-col space-y-3">
              <Skeleton className="h-[200px] w-full rounded-xl" />
            </div>
          ))
        ) : browsers?.length === 0 ? (
          <div className="col-span-full flex flex-col items-center justify-center p-12 border-2 border-dashed rounded-xl bg-background/50">
            <div className="rounded-full bg-muted p-4 mb-4">
              <Plus className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="font-semibold text-lg">No Profiles Found</h3>
            <p className="text-muted-foreground mt-1 max-w-sm text-center">
              Get started by connecting your first AdsPower browser profile.
            </p>
            <Button className="mt-6" onClick={() => { setEditingBrowser(null); setBrowserDialogOpen(true); }}>
              Add Browser Profile
            </Button>
          </div>
        ) : (
          browsers?.map((browser) => {
            const browserAccounts = accounts?.filter(a => a.browserId === browser.id) || [];
            return (
              <BrowserCard
                key={browser.id}
                browser={browser}
                accountsCount={browserAccounts.length}
                onEdit={(b) => { setEditingBrowser(b); setBrowserDialogOpen(true); }}
                onDelete={confirmDeleteBrowser}
              >
                {browserAccounts.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4">No accounts linked to this browser.</p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {browserAccounts.map((account) => (
                      <AccountCard
                        key={account.id}
                        account={account}
                        compact
                        onEdit={(a) => { setEditingAccount(a); setAccountDialogOpen(true); }}
                        onDelete={confirmDeleteAccount}
                      />
                    ))}
                  </div>
                )}
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="w-full mt-2 border-dashed"
                  onClick={() => { setEditingAccount(null); setAccountDialogOpen(true); }}
                >
                  <Plus className="mr-2 h-3 w-3" /> Add Account here
                </Button>
              </BrowserCard>
            );
          })
        )}
      </div>

      <BrowserDialog
        isOpen={isBrowserDialogOpen}
        onOpenChange={setBrowserDialogOpen}
        onSubmit={handleSaveBrowser}
        initialData={editingBrowser}
        isSaving={createBrowser.isPending || updateBrowser.isPending}
      />

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
        title={`Delete ${deletingItem?.type === 'browser' ? 'Profile' : 'Account'}`}
        description={`Are you sure you want to delete "${deletingItem?.name}"? This action cannot be undone.`}
        isDeleting={deleteBrowser.isPending || deleteAccount.isPending}
      />
    </div>
  );
}
